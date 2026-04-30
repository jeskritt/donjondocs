"""
AI Helper Docstring
Purpose: User-data backup/restore for the whole DB. Snapshots the `users` and `characters` tables plus user-owned rows in the nine `global_*` lookup tables (rows with non-null `owner_id`) into a single versioned JSON envelope, and restores from that envelope in either merge or replace mode.
Interactions:
- `app.models.user.User`, `app.models.character.CharacterRecord`, `app.models.char_sheet.*`: the source/target tables.
- `app.services.character_io`: `EXPORT_VERSION` and `migrate_character_data` are reused so each character's `character_data` blob is normalized to the latest version at backup time and re-validated on restore.
- `app.schemas.char_sheet_specific.Character`: validates each character's blob during restore before any DB writes.
- `cli.py`: only caller in production. The `backup` and `restore` subcommands wrap these functions.
- Bulk rule data (rows with `owner_id IS NULL` in the `global_*` tables) is intentionally excluded — that data is reproducible from `data/*.csv` via `python -m app.cli.ingest`.
"""

"""Backup and restore for user-owned data only.

The backup envelope is a single JSON document with a `backup_version`,
the source DB's alembic revision, the current `character_data` schema
version, and three buckets of rows: `users`, `characters`, and
`user_globals` (a dict of table_name → rows).

Restore validates each character against the current `Character`
schema *before* any writes. Schema drift is caught up front via the
alembic-revision check (override with `force=True`).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import char_sheet as global_models
from app.models.character import CharacterRecord
from app.models.user import User
from app.rule_systems import SheetStyle
from app.schemas.char_sheet_specific import Character
from app.services.character_io import EXPORT_VERSION, migrate_character_data
from app.user_roles import UserRole


BACKUP_VERSION = 1

# Per-user global tables in dependency-safe insert order. Restore in
# REPLACE mode deletes in reverse to satisfy the FK from each global_*
# table to `users` (these FKs do NOT have ON DELETE CASCADE — see
# app/models/char_sheet.py).
USER_GLOBAL_MODELS: list[tuple[str, type]] = [
    ("global_ability", global_models.GlobalAbility),
    ("global_attribute", global_models.GlobalAttribute),
    ("global_class", global_models.GlobalClass),
    ("global_skill", global_models.GlobalSkill),
    ("global_item", global_models.GlobalItem),
    ("global_weapon", global_models.GlobalWeapon),
    ("global_armor", global_models.GlobalArmor),
    ("global_combat_maneuver", global_models.GlobalCombatManeuver),
    ("global_spell", global_models.GlobalSpell),
    ("global_destiny", global_models.GlobalDestiny),
]


class BackupServiceError(Exception):
    """Caller-friendly failures from create_backup / restore_backup."""


class RestoreMode(str, Enum):
    MERGE = "merge"
    REPLACE = "replace"


class BackupEnvelope(BaseModel):
    """Top-level backup file format. Bump `backup_version` on breaking changes."""

    backup_version: int = BACKUP_VERSION
    exported_at: str
    alembic_revision: str | None
    character_data_version: int
    users: list[dict]
    characters: list[dict]
    user_globals: dict[str, list[dict]]


class RestoreReport(BaseModel):
    """Counts returned to the caller so the CLI can print a summary."""

    mode: RestoreMode
    dry_run: bool
    users_inserted: int = 0
    users_updated: int = 0
    characters_inserted: int = 0
    characters_updated: int = 0
    user_globals_inserted: int = 0
    user_globals_updated: int = 0


def _model_columns(model: type) -> list[str]:
    return [c.name for c in model.__table__.columns]


def _serialize(value: Any) -> Any:
    """Make a column value JSON-friendly: datetimes → ISO, enums → value."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _row_to_dict(row: Any, columns: list[str]) -> dict:
    return {c: _serialize(getattr(row, c)) for c in columns}


def _parse_iso(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


async def _get_alembic_revision(session: AsyncSession) -> str | None:
    """Return the current alembic head, or None if untstamped/missing.

    Tolerates a missing `alembic_version` table — common in test DBs
    bootstrapped with `Base.metadata.create_all`. Rolls back the implicit
    transaction on failure so the caller's session stays usable.
    """
    try:
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        row = result.first()
        return row[0] if row else None
    except SQLAlchemyError:
        await session.rollback()
        return None


async def create_backup(session: AsyncSession) -> BackupEnvelope:
    """Read all user-owned rows from the bound DB and return an envelope.

    Read-only — does not commit or rollback. Each character's
    `character_data` is migrated up to `EXPORT_VERSION` so the envelope
    is always at the latest version and round-trips cleanly on restore.
    """
    revision = await _get_alembic_revision(session)

    user_cols = _model_columns(User)
    user_rows = (await session.execute(select(User))).scalars().all()
    users = [_row_to_dict(u, user_cols) for u in user_rows]

    char_cols = _model_columns(CharacterRecord)
    char_rows = (await session.execute(select(CharacterRecord))).scalars().all()
    characters: list[dict] = []
    for c in char_rows:
        d = _row_to_dict(c, char_cols)
        # Bring the blob up to the current schema before snapshotting.
        d["character_data"] = migrate_character_data(
            dict(c.character_data or {}), EXPORT_VERSION
        )
        characters.append(d)

    user_globals: dict[str, list[dict]] = {}
    for table_name, model in USER_GLOBAL_MODELS:
        cols = _model_columns(model)
        stmt = select(model).where(model.owner_id.isnot(None))
        rows = (await session.execute(stmt)).scalars().all()
        user_globals[table_name] = [_row_to_dict(r, cols) for r in rows]

    return BackupEnvelope(
        backup_version=BACKUP_VERSION,
        exported_at=datetime.now(timezone.utc).isoformat(),
        alembic_revision=revision,
        character_data_version=EXPORT_VERSION,
        users=users,
        characters=characters,
        user_globals=user_globals,
    )


def _prepare_user_row(raw: dict) -> dict:
    out = dict(raw)
    for k in ("created_at", "updated_at", "last_login"):
        if k in out:
            out[k] = _parse_iso(out.get(k))
    role = out.get("role")
    if role is not None and not isinstance(role, UserRole):
        out["role"] = UserRole(role)
    return out


def _prepare_character_row(raw: dict, source_version: int) -> dict:
    out = dict(raw)
    for k in ("created_at", "updated_at"):
        if k in out:
            out[k] = _parse_iso(out.get(k))
    style = out.get("style")
    if style is not None and not isinstance(style, SheetStyle):
        out["style"] = SheetStyle(style)
    out["character_data"] = migrate_character_data(
        dict(out.get("character_data") or {}), source_version
    )
    return out


def _prepare_global_row(raw: dict) -> dict:
    out = dict(raw)
    for k in ("created_at", "updated_at"):
        if k in out:
            out[k] = _parse_iso(out.get(k))
    return out


async def _upsert(session: AsyncSession, model: type, row: dict) -> bool:
    """Insert or update by primary key. Returns True if inserted, False if updated.

    Existing rows are mutated field-by-field (skipping `id`); fresh rows
    are added via session.add. The caller is responsible for the flush.
    """
    pk = row["id"]
    existing = await session.get(model, pk)
    if existing is None:
        session.add(model(**row))
        return True
    for k, v in row.items():
        if k == "id":
            continue
        setattr(existing, k, v)
    return False


async def restore_backup(
    session: AsyncSession,
    envelope: BackupEnvelope,
    *,
    mode: RestoreMode = RestoreMode.MERGE,
    dry_run: bool = False,
    force: bool = False,
) -> RestoreReport:
    """Apply an envelope to the bound DB. Commits on success, rolls back on dry-run or failure.

    - MERGE: upsert every row by primary key. Existing rows updated, new rows
      inserted, unrelated rows untouched.
    - REPLACE: wipe `users`, `characters`, and user-owned `global_*` rows
      (in FK-safe order), then insert everything fresh from the envelope.
    - dry_run: validate + apply + count, then rollback so the DB is unchanged.
    - force: skip the alembic-revision compatibility check.
    """
    current_rev = await _get_alembic_revision(session)
    if not force and envelope.alembic_revision != current_rev:
        raise BackupServiceError(
            f"Alembic revision mismatch: backup={envelope.alembic_revision!r} "
            f"current={current_rev!r}. Use --force to override."
        )

    # Pre-validate every character before any writes so we fail fast and don't
    # leave a half-restored DB even mid-transaction.
    prepared_chars: list[dict] = []
    for idx, raw in enumerate(envelope.characters):
        try:
            prepped = _prepare_character_row(raw, envelope.character_data_version)
            Character(**prepped["character_data"])
        except Exception as e:
            raise BackupServiceError(
                f"Invalid character_data at characters[{idx}] "
                f"(id={raw.get('id')!r}, name={raw.get('name')!r}): {e}"
            ) from e
        prepared_chars.append(prepped)

    report = RestoreReport(mode=mode, dry_run=dry_run)

    try:
        if mode == RestoreMode.REPLACE:
            # FK-safe wipe: globals → characters → users.
            for _, model in reversed(USER_GLOBAL_MODELS):
                await session.execute(delete(model).where(model.owner_id.isnot(None)))
            await session.execute(delete(CharacterRecord))
            await session.execute(delete(User))
            await session.flush()

        for raw in envelope.users:
            inserted = await _upsert(session, User, _prepare_user_row(raw))
            if inserted:
                report.users_inserted += 1
            else:
                report.users_updated += 1
        await session.flush()

        for prepped in prepared_chars:
            inserted = await _upsert(session, CharacterRecord, prepped)
            if inserted:
                report.characters_inserted += 1
            else:
                report.characters_updated += 1
        await session.flush()

        for table_name, model in USER_GLOBAL_MODELS:
            for raw in envelope.user_globals.get(table_name, []):
                inserted = await _upsert(session, model, _prepare_global_row(raw))
                if inserted:
                    report.user_globals_inserted += 1
                else:
                    report.user_globals_updated += 1
        await session.flush()

        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    except Exception:
        await session.rollback()
        raise

    return report
