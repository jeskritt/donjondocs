"""
AI Helper Docstring
Purpose: REST surface for the Creature Catalog. Thin wrappers around `creature_service` + `creature_io` + `creature_parser` with `Depends(get_current_user)` on every route. Filenames, byte caps, and envelope validation mirror the character endpoints so the UI's import/export flow can be cloned with minimal changes.
Interactions:
- `app.services.creature_service`: CRUD + visibility filter + copy.
- `app.services.creature_io`: versioned envelope + migration chain.
- `app.services.creature_parser`: best-effort metadata extraction.
- `app.api.deps`: `get_db`, `get_current_user`.
- `main.py`: mounts this router at `/api/creatures`.

Routes:
  GET    /api/creatures                  — list visible (own + public), optional q/type/size narrowing
  POST   /api/creatures                  — create
  GET    /api/creatures/{id}             — fetch one (visible only)
  PATCH  /api/creatures/{id}             — update (owner/admin)
  DELETE /api/creatures/{id}             — delete (owner/admin)
  POST   /api/creatures/{id}/copy        — duplicate; new owner = current user, is_public reset
  POST   /api/creatures/{id}/parse       — run the body-md parser, return extracted metadata
  GET    /api/creatures/{id}/export      — download envelope
  POST   /api/creatures/import           — upload envelope (is_public always reset on import)
"""

"""Creature catalog REST routes."""

import json
from typing import Annotated, Any, Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.creature import Creature as CreatureORM
from app.models.user import User
from app.schemas.creature import Creature, CreatureCreate, CreatureUpdate
from app.services._errors import CreatureServiceError
from app.services.creature_io import (
    EXPORT_VERSION,
    export_filename_for,
    migrate_creature_data,
)
from app.services.creature_parser import parse_stat_block
from app.services.creature_service import (
    copy_creature,
    create_creature,
    delete_creature,
    get_creature,
    list_creatures_visible_to,
    update_creature,
)
from app.user_context import UserContext


router = APIRouter()


async def _owner_username_map(
    db: AsyncSession, rows: Iterable[CreatureORM]
) -> dict[str, str]:
    """Batch-fetch `username` for the distinct owner ids in `rows`.

    Single query keeps the catalog list endpoint at O(2) round trips. The
    map is used to populate the denormalised `owner_username` field on the
    response model so the UI can render "Owned by: <name>" inline.
    """
    owner_ids = {r.owner_id for r in rows}
    if not owner_ids:
        return {}
    stmt = select(User.id, User.username).where(User.id.in_(owner_ids))
    result = await db.execute(stmt)
    return {uid: uname for uid, uname in result.all()}


def _to_response(row: CreatureORM, owner_map: dict[str, str]) -> Creature:
    payload = Creature.model_validate(row)
    payload.owner_username = owner_map.get(row.owner_id)
    return payload


# Same 1 MiB cap as the character import — defence-in-depth against
# OOM-by-upload (security audit F-03).
MAX_IMPORT_BYTES = 1 * 1024 * 1024


def _matches_filters(
    creature: Creature,
    q: str | None,
    type_filter: str | None,
    size_filter: str | None,
) -> bool:
    """In-memory filter shared between list endpoint variants."""
    if q:
        if q.lower() not in creature.name.lower():
            return False
    if type_filter:
        # creature_type is comma-joined; match any chip.
        chips = {c.strip().lower() for c in creature.creature_type.split(",")}
        if type_filter.lower() not in chips:
            return False
    if size_filter:
        if creature.size.lower() != size_filter.lower():
            return False
    return True


@router.get("", response_model=list[Creature])
async def list_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str | None = Query(default=None, description="Substring match on name."),
    type_filter: str | None = Query(default=None, alias="type", description="Canonical type chip."),
    size_filter: str | None = Query(default=None, alias="size", description="Canonical size."),
):
    """List every creature visible to the user, optionally narrowed.

    Visibility = `is_public OR owner_id == me`. The narrowing happens in
    memory so the caller can flip filters without re-rounding the DB; if
    catalogs grow large this can be pushed into the query.
    """
    rows = await list_creatures_visible_to(db, UserContext.from_user(current_user))
    filtered = [r for r in rows if _matches_filters(r, q, type_filter, size_filter)]
    owner_map = await _owner_username_map(db, filtered)
    return [_to_response(r, owner_map) for r in filtered]


@router.post("", response_model=Creature, status_code=201)
async def create_endpoint(
    payload: CreatureCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = await create_creature(db, UserContext.from_user(current_user), payload)
    owner_map = await _owner_username_map(db, [row])
    return _to_response(row, owner_map)


@router.get("/{creature_id}", response_model=Creature)
async def get_endpoint(
    creature_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = await get_creature(db, creature_id, UserContext.from_user(current_user))
    return _to_response(row, await _owner_username_map(db, [row]))


@router.patch("/{creature_id}", response_model=Creature)
async def update_endpoint(
    creature_id: str,
    payload: CreatureUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = await update_creature(db, creature_id, payload, UserContext.from_user(current_user))
    return _to_response(row, await _owner_username_map(db, [row]))


@router.delete("/{creature_id}", status_code=204)
async def delete_endpoint(
    creature_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await delete_creature(db, creature_id, UserContext.from_user(current_user))
    return Response(status_code=204)


@router.post("/{creature_id}/copy", response_model=Creature, status_code=201)
async def copy_endpoint(
    creature_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    row = await copy_creature(db, creature_id, UserContext.from_user(current_user))
    return _to_response(row, await _owner_username_map(db, [row]))


@router.post("/{creature_id}/parse")
async def parse_endpoint(
    creature_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Run the body-md parser on a creature and return the extracted fields.

    Read-only — the caller decides whether to apply the changes via a
    subsequent PATCH. RBAC gate is the same visibility check as GET.
    """
    row = await get_creature(db, creature_id, UserContext.from_user(current_user))
    return parse_stat_block(row.body_md)


@router.get("/{creature_id}/export")
async def export_endpoint(
    creature_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Download a single-creature envelope as JSON."""
    row = await get_creature(db, creature_id, UserContext.from_user(current_user))
    envelope = {
        "version": EXPORT_VERSION,
        "exported_at": row.updated_at.isoformat(),
        "creature_data": Creature.model_validate(row).model_dump(
            exclude={"id", "owner_id", "created_at", "updated_at"}
        ),
    }
    content = json.dumps(envelope, indent=2, default=str)
    safe_name = export_filename_for(row.name)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.json"'},
    )


async def _read_import_file(file: UploadFile) -> bytes:
    """Validate the upload and return its raw bytes — same shape as the
    character import helper but local to this router so the file stays
    self-contained."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are accepted.")

    declared = file.size if file.size is not None else None
    if declared is not None and declared > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Import file exceeds {MAX_IMPORT_BYTES} bytes.",
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_IMPORT_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Import file exceeds {MAX_IMPORT_BYTES} bytes.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _parse_envelope(raw: bytes) -> dict[str, Any]:
    try:
        envelope = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON file.")
    if not isinstance(envelope, dict) or "creature_data" not in envelope:
        raise HTTPException(status_code=400, detail="Missing 'creature_data' in import file.")
    return envelope


@router.post("/import", response_model=Creature, status_code=201)
async def import_endpoint(
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a creature from an exported envelope.

    `is_public` from the envelope is always reset to False — the importer
    opts into sharing explicitly after the row exists.
    """
    raw = await _read_import_file(file)
    envelope = _parse_envelope(raw)

    version = envelope.get("version", EXPORT_VERSION)
    if not isinstance(version, int):
        raise HTTPException(status_code=400, detail="Envelope 'version' must be an integer.")

    data = envelope["creature_data"]
    try:
        data = migrate_creature_data(dict(data), version)
    except CreatureServiceError:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Creature data failed migration.")

    data["is_public"] = False  # never trust the envelope's visibility on import
    try:
        payload = CreatureCreate.model_validate(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Creature data failed validation.")

    row = await create_creature(db, UserContext.from_user(current_user), payload)
    owner_map = await _owner_username_map(db, [row])
    return _to_response(row, owner_map)
