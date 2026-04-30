"""
AI Helper Docstring
Purpose: All write/read operations on `CharacterNote` with owner-based RBAC. RBAC is enforced by routing through `character_service.get_character`, which raises 403/404 for non-owners and missing characters before any addon mutation.
Interactions:
- `app.models.character_addons.CharacterNote`: target ORM row.
- `app.services.character_service.get_character`: every CRUD entry validates parent-character ownership through this function.
- `app.api.character_routes`: thin REST routes that delegate here.
- `app.ui.components.sheet.notes`: NiceGUI page that calls list/create/update/delete via a service session.
- `app.services.character_io`: bulk operations during per-character export/import.
"""

"""Character note CRUD with RBAC via parent character ownership."""

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character_addons import CharacterNote
from app.schemas.note import NoteCreate, NoteUpdate
from app.services._errors import CharacterServiceError
from app.services.character_service import get_character
from app.user_context import UserContext


async def list_notes(
    session: AsyncSession, character_id: str, current_user: UserContext
) -> Sequence[CharacterNote]:
    """List notes for a character. Raises 403/404 via get_character."""
    await get_character(session, character_id, current_user)
    stmt = (
        select(CharacterNote)
        .where(CharacterNote.character_id == character_id)
        .order_by(CharacterNote.created_at.desc())
    )
    return (await session.execute(stmt)).scalars().all()


async def create_note(
    session: AsyncSession,
    character_id: str,
    payload: NoteCreate,
    current_user: UserContext,
) -> CharacterNote:
    """Add a new note to a character the user owns (or as admin)."""
    await get_character(session, character_id, current_user)
    note = CharacterNote(
        character_id=character_id,
        title=payload.title,
        body_md=payload.body_md,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


async def _get_note_for_user(
    session: AsyncSession, note_id: str, current_user: UserContext
) -> CharacterNote:
    """Load a note and verify its parent character is accessible to the user."""
    note = await session.get(CharacterNote, note_id)
    if note is None:
        raise CharacterServiceError("Note not found.", status_code=404)
    await get_character(session, note.character_id, current_user)
    return note


async def update_note(
    session: AsyncSession,
    note_id: str,
    payload: NoteUpdate,
    current_user: UserContext,
) -> CharacterNote:
    """Update mutable fields on a note; only set fields that were provided."""
    note = await _get_note_for_user(session, note_id, current_user)
    diff = payload.model_dump(exclude_unset=True)
    for key, value in diff.items():
        setattr(note, key, value)
    await session.commit()
    await session.refresh(note)
    return note


async def delete_note(
    session: AsyncSession, note_id: str, current_user: UserContext
) -> None:
    """Delete a note. RBAC via parent character."""
    note = await _get_note_for_user(session, note_id, current_user)
    await session.delete(note)
    await session.commit()
