"""
AI Helper Docstring
Purpose: All read/write operations on the `Creature` catalog with owner-or-admin RBAC. Visibility filter (`is_public OR owner_id == me`) keeps the catalog query single-round-trip; per-row authorisation enforces "edit only what you own" outside of admin overrides.
Interactions:
- `app.models.creature.Creature`: target ORM row.
- `app.schemas.creature.{Creature, CreatureCreate, CreatureUpdate}`: typed payloads.
- `app.user_context.UserContext`: identity for RBAC decisions (passed by routes/UI).
- `app.api.creature_routes`: REST surface delegates here.
- `app.ui.pages.creatures`: NiceGUI page calls these via `service_session()`.
"""

"""Creature catalog CRUD with visibility filter and owner/admin RBAC."""

from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.creature import Creature
from app.schemas.creature import CreatureCreate, CreatureUpdate
from app.services._errors import CreatureServiceError
from app.user_context import UserContext
from app.user_roles import UserRole


def _can_edit(creature: Creature, user: UserContext) -> bool:
    """Owner or admin may edit; everyone else is read-only on public rows."""
    return creature.owner_id == user.id or user.role == UserRole.ADMIN


async def list_creatures_visible_to(
    session: AsyncSession, user: UserContext
) -> Sequence[Creature]:
    """Return every creature visible to the user — own + public, ordered by name."""
    stmt = (
        select(Creature)
        .where(or_(Creature.is_public.is_(True), Creature.owner_id == user.id))
        .order_by(Creature.name.asc())
    )
    return (await session.execute(stmt)).scalars().all()


async def get_creature(
    session: AsyncSession, creature_id: str, user: UserContext
) -> Creature:
    """Fetch a single creature if the user is allowed to see it.

    Raises 404 when missing, 403 when present but not visible. Used by
    view/export paths.
    """
    creature = await session.get(Creature, creature_id)
    if creature is None:
        raise CreatureServiceError("Creature not found.", status_code=404)
    if not creature.is_public and creature.owner_id != user.id and user.role != UserRole.ADMIN:
        # Don't 404 on "exists but private to someone else" — be explicit.
        raise CreatureServiceError("You don't have access to this creature.", status_code=403)
    return creature


async def create_creature(
    session: AsyncSession, user: UserContext, payload: CreatureCreate
) -> Creature:
    """Create a creature owned by the current user.

    `is_public` from the payload is honoured (lets the create dialog ship
    a creature as public in one click). Copy and import paths force False
    instead — see `copy_creature` and the route layer.
    """
    creature = Creature(
        owner_id=user.id,
        name=payload.name,
        body_md=payload.body_md,
        creature_type=payload.creature_type,
        size=payload.size,
        challenge_rating=payload.challenge_rating,
        habitat=payload.habitat,
        is_public=payload.is_public,
        columns=payload.columns,
    )
    session.add(creature)
    await session.commit()
    await session.refresh(creature)
    return creature


async def update_creature(
    session: AsyncSession,
    creature_id: str,
    payload: CreatureUpdate,
    user: UserContext,
) -> Creature:
    """Patch a creature; only owner/admin may write."""
    creature = await session.get(Creature, creature_id)
    if creature is None:
        raise CreatureServiceError("Creature not found.", status_code=404)
    if not _can_edit(creature, user):
        raise CreatureServiceError("Only the owner can edit this creature.", status_code=403)
    diff = payload.model_dump(exclude_unset=True)
    for key, value in diff.items():
        setattr(creature, key, value)
    await session.commit()
    await session.refresh(creature)
    return creature


async def delete_creature(
    session: AsyncSession, creature_id: str, user: UserContext
) -> None:
    """Remove a creature; only owner/admin may delete."""
    creature = await session.get(Creature, creature_id)
    if creature is None:
        raise CreatureServiceError("Creature not found.", status_code=404)
    if not _can_edit(creature, user):
        raise CreatureServiceError("Only the owner can delete this creature.", status_code=403)
    await session.delete(creature)
    await session.commit()


async def copy_creature(
    session: AsyncSession, source_id: str, user: UserContext
) -> Creature:
    """Duplicate a visible creature, re-assigning ownership and resetting visibility.

    Anyone who can view a creature can copy it — that's the point of the
    public flag. The copy lands private regardless of the source's
    visibility so the new owner opts in explicitly.
    """
    source = await get_creature(session, source_id, user)
    copy = Creature(
        owner_id=user.id,
        name=source.name,
        body_md=source.body_md,
        creature_type=source.creature_type,
        size=source.size,
        challenge_rating=source.challenge_rating,
        habitat=source.habitat,
        is_public=False,  # always reset on copy
        columns=source.columns,
    )
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    return copy
