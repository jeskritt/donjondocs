"""
AI Helper Docstring
Purpose: REST endpoints keyed by addon id (PATCH/DELETE on a single ally or note). Lives in its own router because the URL prefix differs from the per-character collection routes (`/api/allies/{id}` vs. `/api/characters/{character_id}/allies`).
Interactions:
- `app.services.ally_service`, `app.services.note_service`: every route is a thin wrapper.
- `app.api.deps.get_current_user`, `get_db`: shared FastAPI dependencies.
- `app.api.character_routes`: list/create endpoints under `/api/characters/{id}/...` are there.
- `main.py`: mounts both `allies_router` and `notes_router` at their respective prefixes.
"""

"""Per-row ally / note edit and delete routes.

PATCH  /api/allies/{ally_id}   — update an ally
DELETE /api/allies/{ally_id}   — delete an ally
PATCH  /api/notes/{note_id}    — update a note
DELETE /api/notes/{note_id}    — delete a note
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.ally import Ally, AllyUpdate
from app.schemas.note import Note, NoteUpdate
from app.services.ally_service import delete_ally, update_ally
from app.services.note_service import delete_note, update_note
from app.user_context import UserContext


allies_router = APIRouter()
notes_router = APIRouter()


@allies_router.patch("/{ally_id}", response_model=Ally)
async def update_ally_endpoint(
    ally_id: str,
    payload: AllyUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = await update_ally(db, ally_id, payload, UserContext.from_user(current_user))
    return Ally.model_validate(row)


@allies_router.delete("/{ally_id}", status_code=204)
async def delete_ally_endpoint(
    ally_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await delete_ally(db, ally_id, UserContext.from_user(current_user))


@notes_router.patch("/{note_id}", response_model=Note)
async def update_note_endpoint(
    note_id: str,
    payload: NoteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = await update_note(db, note_id, payload, UserContext.from_user(current_user))
    return Note.model_validate(row)


@notes_router.delete("/{note_id}", status_code=204)
async def delete_note_endpoint(
    note_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await delete_note(db, note_id, UserContext.from_user(current_user))
