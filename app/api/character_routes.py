"""
AI Helper Docstring
Purpose: REST endpoints for character side-effects that don't belong on the NiceGUI sheet page — rest mechanics, JSON export download, JSON import upload, and the list/create endpoints for the per-character ally and note addons. Translates `CharacterServiceError` into HTTP status codes; everything else delegates to the relevant service.
Interactions:
- `app.services.character_service`: `rest_character`, `export_character`, `import_character`.
- `app.services.ally_service` / `note_service`: list/create entry points.
- `app.services.character_io`: `EXPORT_VERSION` for the envelope; `export_filename_for` for Content-Disposition.
- `app.api.deps`: `get_current_user` (JWT cookie) and `get_db` (async session).
- Hard cap on import payload size (`MAX_IMPORT_BYTES = 1 MiB`) — defense against the OOM-by-upload finding from the security audit.
"""

"""Character REST routes.

POST   /api/characters/{id}/rest    — apply a short or long rest to a character.
GET    /api/characters/{id}/export  — download character as JSON.
POST   /api/characters/import       — upload a JSON file to create a character.
GET    /api/characters/{id}/allies  — list allies for a character.
POST   /api/characters/{id}/allies  — add a new ally.
GET    /api/characters/{id}/notes   — list notes for a character.
POST   /api/characters/{id}/notes   — add a new note.

Per-row ally/note edits (PATCH/DELETE) live on a sibling router in
`character_addons_routes.py` because they're keyed by their own id, not
the parent character's id, and don't share the `/api/characters` prefix.
"""

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, read_json_upload
from app.models.user import User
from app.schemas.ally import Ally, AllyCreate
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.note import Note, NoteCreate
from app.services.ally_service import create_ally, list_allies
from app.services.character_io import EXPORT_VERSION, MAX_IMPORT_BYTES, export_filename_for
from app.services.character_service import (
    CharacterServiceError,
    export_character,
    import_character,
    rest_character,
)
from app.services.note_service import create_note, list_notes
from app.user_context import UserContext


router = APIRouter()


# MAX_IMPORT_BYTES is imported from app.services.character_io (re-exported here
# for existing callers/tests) and enforced both via Content-Length and a
# streaming read accumulator below.


class RestRequest(BaseModel):
    kind: Literal["short", "long"]
    options: dict = Field(default_factory=dict)


@router.post("/{character_id}/rest")
async def rest_endpoint(
    character_id: str,
    body: RestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    rec = await rest_character(db, character_id, body.kind, body.options, UserContext.from_user(current_user))
    return {
        "id": rec.id,
        "hp_current": rec.character_data.get("hp_current"),
        "hp_max": rec.character_data.get("hp_max"),
    }


@router.get("/{character_id}/export")
async def export_endpoint(
    character_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    data = await export_character(db, character_id, UserContext.from_user(current_user))
    content = json.dumps(data, indent=2, default=str)
    safe_name = export_filename_for(data["name"])
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.json"'},
    )


def _parse_envelope(raw: bytes) -> dict[str, Any]:
    """Decode the raw upload as a JSON envelope dict containing character_data."""
    try:
        envelope = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON file.")

    if not isinstance(envelope, dict) or "character_data" not in envelope:
        raise HTTPException(status_code=400, detail="Missing 'character_data' in import file.")
    return envelope


def _coerce_style(style_str: str) -> SheetStyle:
    try:
        return SheetStyle(style_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown style: {style_str}")


@router.post("/import")
async def import_endpoint(
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    raw = await read_json_upload(file, MAX_IMPORT_BYTES)
    envelope = _parse_envelope(raw)

    name = envelope.get("name", "Imported Character")
    style = _coerce_style(envelope.get("style", SheetStyle.DND5E.value))

    version = envelope.get("version", EXPORT_VERSION)
    if not isinstance(version, int):
        raise HTTPException(status_code=400, detail="Envelope 'version' must be an integer.")

    try:
        rec = await import_character(
            db, name, style, envelope["character_data"], UserContext.from_user(current_user), version=version,
            allies=envelope.get("allies"),
            notes=envelope.get("notes"),
        )
    except CharacterServiceError:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Character data failed validation.")

    return {"id": rec.id, "name": rec.name}


# ---------------------------------------------------------------------------
# Allies — list / create on a character
# ---------------------------------------------------------------------------

@router.get("/{character_id}/allies", response_model=list[Ally])
async def list_allies_endpoint(
    character_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    rows = await list_allies(db, character_id, UserContext.from_user(current_user))
    return [Ally.model_validate(r) for r in rows]


@router.post("/{character_id}/allies", response_model=Ally, status_code=201)
async def create_ally_endpoint(
    character_id: str,
    payload: AllyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = await create_ally(db, character_id, payload, UserContext.from_user(current_user))
    return Ally.model_validate(row)


# ---------------------------------------------------------------------------
# Notes — list / create on a character
# ---------------------------------------------------------------------------

@router.get("/{character_id}/notes", response_model=list[Note])
async def list_notes_endpoint(
    character_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    rows = await list_notes(db, character_id, UserContext.from_user(current_user))
    return [Note.model_validate(r) for r in rows]


@router.post("/{character_id}/notes", response_model=Note, status_code=201)
async def create_note_endpoint(
    character_id: str,
    payload: NoteCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = await create_note(db, character_id, payload, UserContext.from_user(current_user))
    return Note.model_validate(row)
