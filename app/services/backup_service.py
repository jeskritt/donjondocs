"""
AI Helper Docstring
Purpose: User-data backup/restore for the whole DB. Snapshots the `users`, `characters`, and `creatures` tables, the per-character `character_allies`/`character_notes` addons, plus user-owned rows in the `global_*` lookup tables (rows with non-null `owner_id`) into a single versioned JSON envelope, and restores from that envelope in either merge or replace mode.
Interactions:
- `app.models.user.User`, `app.models.character.CharacterRecord`, `app.models.creature.Creature`, `app.models.char_sheet.*`: the source/target tables.
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
from app.models.character_addons import CharacterAlly, CharacterNote
from app.models.creature import Creature
from app.models.user import User
from app.rule_systems import SheetStyle
from app.schemas.registry import parse_character
from app.services.character_io import EXPORT_VERSION, migrate_character_data
from app.user_roles import UserRole

# Sentinel written into `users.hashed_password` when inserting a user from a
# passwordless backup (`include_passwords=False`). `verify_password()` rejects
# any non-`$argon2`/`$2` string, so the account stays locked until an admin
# runs `reset-password` (CLI or Admin UI).
LOCKED_PASSWORD_SENTINEL = "!LOCKED-PASSWORD-RESET-REQUIRED!"


# v2 added the `character_allies` and `character_notes` buckets at envelope
# level. v3 added the `creatures` bucket. Older backups still load — missing
# keys default to empty lists, so nothing is destroyed by restoring an older
# artifact. Restore compatibility is gated on `alembic_revision`, not this
# number, so no restore-side version check keys off it.
BACKUP_VERSION = 3

# Per-character relational addons. These tables have ON DELETE CASCADE on
# their FK to `characters`, so REPLACE-mode restore wipes them implicitly
# when characters are deleted; we still insert in (parent, addon) order.
CHARACTER_ADDON_MODELS: list[tuple[str, type]] = [
    ("character_allies", CharacterAlly),
    ("character_notes", CharacterNote),
]

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
    # Per-character relational addons (added in BACKUP_VERSION 2). Defaulted
    # to {} so v1 envelopes loaded into a v2 codebase parse cleanly with
    # empty addon buckets.
    character_addons: dict[str, list[dict]] = {}
    # User-owned creature catalog rows (added in BACKUP_VERSION 3). Defaulted
    # to [] so pre-v3 envelopes parse cleanly with an empty creature bucket.
    creatures: list[dict] = []
    # False when exported via Admin UI with "Exclude password hashes" enabled.
    includes_passwords: bool = True


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
    character_addons_inserted: int = 0
    character_addons_updated: int = 0
    creatures_inserted: int = 0
    creatures_updated: int = 0


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


async def create_backup(
    session: AsyncSession,
    *,
    include_passwords: bool = True,
) -> BackupEnvelope:
    """Read all user-owned rows from the bound DB and return an envelope.

    Read-only — does not commit or rollback. Each character's
    `character_data` is migrated up to `EXPORT_VERSION` so the envelope
    is always at the latest version and round-trips cleanly on restore.

    When `include_passwords=False` (used by Admin UI downloads when the admin
    chooses not to export credential hashes), `hashed_password` is omitted from
    exported `users` rows. On restore, MERGE preserves existing passwords and
    new inserts receive `LOCKED_PASSWORD_SENTINEL` until reset.
    """
    revision = await _get_alembic_revision(session)

    user_cols = _model_columns(User)
    if not include_passwords:
        user_cols = [c for c in user_cols if c != "hashed_password"]
    user_rows = (await session.execute(select(User))).scalars().all()
    users = [_row_to_dict(u, user_cols) for u in user_rows]

    char_cols = _model_columns(CharacterRecord)
    char_rows = (await session.execute(select(CharacterRecord))).scalars().all()
    characters: list[dict] = []
    for c in char_rows:
        d = _row_to_dict(c, char_cols)
        # Bring the blob up to the current schema before snapshotting.
        d["character_data"] = migrate_character_data(
            dict(c.character_data or {}), EXPORT_VERSION, style=c.style
        )
        characters.append(d)

    user_globals: dict[str, list[dict]] = {}
    for table_name, model in USER_GLOBAL_MODELS:
        cols = _model_columns(model)
        stmt = select(model).where(model.owner_id.isnot(None))
        rows = (await session.execute(stmt)).scalars().all()
        user_globals[table_name] = [_row_to_dict(r, cols) for r in rows]

    character_addons: dict[str, list[dict]] = {}
    for table_name, model in CHARACTER_ADDON_MODELS:
        cols = _model_columns(model)
        rows = (await session.execute(select(model))).scalars().all()
        character_addons[table_name] = [_row_to_dict(r, cols) for r in rows]

    # Every creature has an owner, so back up all rows (like characters); there
    # is no owner_id-null "global" variant to filter out.
    creature_cols = _model_columns(Creature)
    creature_rows = (await session.execute(select(Creature))).scalars().all()
    creatures = [_row_to_dict(r, creature_cols) for r in creature_rows]

    return BackupEnvelope(
        backup_version=BACKUP_VERSION,
        exported_at=datetime.now(timezone.utc).isoformat(),
        alembic_revision=revision,
        character_data_version=EXPORT_VERSION,
        users=users,
        characters=characters,
        user_globals=user_globals,
        character_addons=character_addons,
        creatures=creatures,
        includes_passwords=include_passwords,
    )


def _prepare_user_row(raw: dict) -> dict:
    out = dict(raw)
    for k in ("created_at", "updated_at", "last_login"):
        if k in out:
            out[k] = _parse_iso(out.get(k))
    role = out.get("role")
    if role is not None and not isinstance(role, UserRole):
        out["role"] = UserRole(role)
    # Drop explicit None/empty hashed_password so _upsert_user preserves an
    # existing hash on MERGE and falls back to LOCKED_PASSWORD_SENTINEL on insert.
    if not out.get("hashed_password"):
        out.pop("hashed_password", None)
    return out


def _prepare_character_row(raw: dict, source_version: int) -> dict:
    out = dict(raw)
    for k in ("created_at", "updated_at"):
        if k in out:
            out[k] = _parse_iso(out.get(k))
    style = out.get("style")
    if style is not None and not isinstance(style, SheetStyle):
        style = SheetStyle(style)
        out["style"] = style
    out["character_data"] = migrate_character_data(
        dict(out.get("character_data") or {}), source_version, style=style
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
        if model is User and "hashed_password" not in row:
            row = {**row, "hashed_password": LOCKED_PASSWORD_SENTINEL}
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
            parse_character(prepped["style"], prepped["character_data"])
        except Exception as e:
            raise BackupServiceError(
                f"Invalid character_data at characters[{idx}] "
                f"(id={raw.get('id')!r}, name={raw.get('name')!r}): {e}"
            ) from e
        prepared_chars.append(prepped)

    report = RestoreReport(mode=mode, dry_run=dry_run)

    try:
        if mode == RestoreMode.REPLACE:
            # FK-safe wipe: addons → globals → characters → users.
            # Character addons must go before characters because their FK
            # cascade may not be honored by SQLite without PRAGMA enabled,
            # and explicit deletes are portable across backends.
            for _, model in reversed(CHARACTER_ADDON_MODELS):
                await session.execute(delete(model))
            for _, model in reversed(USER_GLOBAL_MODELS):
                await session.execute(delete(model).where(model.owner_id.isnot(None)))
            await session.execute(delete(CharacterRecord))
            # Creatures reference only `users`; delete them before users so the
            # FK holds without relying on cascade (portable across backends).
            await session.execute(delete(Creature))
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

        # Creatures only need their owner (users) present, which is now flushed.
        # Restore preserves every column verbatim, including `is_public` — this
        # is a faithful snapshot, not an import (import/copy force is_public off).
        for raw in envelope.creatures:
            inserted = await _upsert(session, Creature, _prepare_global_row(raw))
            if inserted:
                report.creatures_inserted += 1
            else:
                report.creatures_updated += 1
        await session.flush()

        for table_name, model in USER_GLOBAL_MODELS:
            for raw in envelope.user_globals.get(table_name, []):
                inserted = await _upsert(session, model, _prepare_global_row(raw))
                if inserted:
                    report.user_globals_inserted += 1
                else:
                    report.user_globals_updated += 1
        await session.flush()

        # Character addons go after characters so FK constraints are satisfied.
        for table_name, model in CHARACTER_ADDON_MODELS:
            for raw in envelope.character_addons.get(table_name, []):
                inserted = await _upsert(session, model, _prepare_global_row(raw))
                if inserted:
                    report.character_addons_inserted += 1
                else:
                    report.character_addons_updated += 1
        await session.flush()

        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    except Exception:
        await session.rollback()
        raise

    return report
