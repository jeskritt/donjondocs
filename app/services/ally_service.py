"""
AI Helper Docstring
Purpose: All write/read operations on `CharacterAlly` with owner-based RBAC. RBAC is enforced by routing through `character_service.get_character`, which raises 403/404 for non-owners and missing characters before any addon mutation.
Interactions:
- `app.models.character_addons.CharacterAlly`: target ORM row.
- `app.services.character_service.get_character`: every CRUD entry validates parent-character ownership through this function.
- `app.api.character_routes`: thin REST routes that delegate here.
- `app.ui.components.sheet.allies`: NiceGUI page that calls list/create/update/delete via a service session.
- `app.services.character_io`: bulk operations during per-character export/import.
"""

"""Character ally CRUD with RBAC via parent character ownership."""

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character_addons import CharacterAlly
from app.schemas.ally import AllyCreate, AllyUpdate
from app.services._errors import CharacterServiceError
from app.services.character_service import get_character
from app.user_context import UserContext


async def list_allies(
    session: AsyncSession, character_id: str, current_user: UserContext
) -> Sequence[CharacterAlly]:
    """List allies for a character. Raises 403/404 via get_character."""
    await get_character(session, character_id, current_user)
    stmt = (
        select(CharacterAlly)
        .where(CharacterAlly.character_id == character_id)
        .order_by(CharacterAlly.created_at.asc())
    )
    return (await session.execute(stmt)).scalars().all()


async def create_ally(
    session: AsyncSession,
    character_id: str,
    payload: AllyCreate,
    current_user: UserContext,
) -> CharacterAlly:
    """Add a new ally to a character the user owns (or as admin)."""
    await get_character(session, character_id, current_user)
    ally = CharacterAlly(
        character_id=character_id,
        name=payload.name,
        ally_type=payload.ally_type,
        body_md=payload.body_md,
    )
    session.add(ally)
    await session.commit()
    await session.refresh(ally)
    return ally


async def _get_ally_for_user(
    session: AsyncSession, ally_id: str, current_user: UserContext
) -> CharacterAlly:
    """Load an ally and verify its parent character is accessible to the user."""
    ally = await session.get(CharacterAlly, ally_id)
    if ally is None:
        raise CharacterServiceError("Ally not found.", status_code=404)
    # Ownership of the ally is implied by ownership of its parent character.
    await get_character(session, ally.character_id, current_user)
    return ally


async def update_ally(
    session: AsyncSession,
    ally_id: str,
    payload: AllyUpdate,
    current_user: UserContext,
) -> CharacterAlly:
    """Update mutable fields on an ally; only set fields that were provided."""
    ally = await _get_ally_for_user(session, ally_id, current_user)
    diff = payload.model_dump(exclude_unset=True)
    for key, value in diff.items():
        setattr(ally, key, value)
    await session.commit()
    await session.refresh(ally)
    return ally


async def delete_ally(
    session: AsyncSession, ally_id: str, current_user: UserContext
) -> None:
    """Delete an ally. RBAC via parent character."""
    ally = await _get_ally_for_user(session, ally_id, current_user)
    await session.delete(ally)
    await session.commit()
