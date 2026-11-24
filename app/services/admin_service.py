"""
AI Helper Docstring
Purpose: Admin-only operational services — inspecting seeded global catalog counts, safely re-ingesting bundled `data/` rule files, and generating password-reauthenticated database backup downloads with rate-limiting and audit logging.
Interactions:
- `app.cli.ingest.run_ingestion_in_session`: executes the idempotent upsert against the fixed server-side `data/` directory.
- `app.services.backup_service.create_backup`: snapshots user-owned tables with optional password-hash exclusion.
- `app.security.verify_password`: enforces admin password re-authentication before exporting backups.
- `app.ui.pages.admin`: primary caller for Admin UI actions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli.ingest import run_ingestion_in_session
from app.models.char_sheet import (
    GlobalAbility,
    GlobalArmor,
    GlobalAttribute,
    GlobalClass,
    GlobalItem,
    GlobalSkill,
    GlobalSpell,
    GlobalWeapon,
)
from app.models.user import User
from app.security import verify_password
from app.services._errors import ServiceError
from app.services.backup_service import create_backup
from app.user_context import UserContext
from app.user_roles import UserRole

logger = logging.getLogger(__name__)

# Fixed server-side data directory (never caller-supplied).
REPO_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Single-flight lock preventing concurrent reseed clicks from overlapping upserts.
_INGEST_LOCK = asyncio.Lock()

# Per-admin backup rate limit: max 2 downloads per hour.
BACKUP_MAX_PER_WINDOW = 2
BACKUP_WINDOW_SECONDS = 3600.0
_backup_timestamps: dict[str, list[float]] = defaultdict(list)

_GLOBAL_TABLES: tuple[tuple[str, type], ...] = (
    ("attributes", GlobalAttribute),
    ("skills", GlobalSkill),
    ("classes", GlobalClass),
    ("weapons", GlobalWeapon),
    ("armor", GlobalArmor),
    ("items", GlobalItem),
    ("spells", GlobalSpell),
    ("abilities", GlobalAbility),
)


class AdminServiceError(ServiceError):
    """Raised when an admin-only operation fails validation, auth, or rate limits."""


def reset_backup_rate_limit() -> None:
    """Clear in-memory admin backup rate-limit buckets (used by tests)."""
    _backup_timestamps.clear()


def _require_admin(current_user: UserContext) -> None:
    if current_user.role != UserRole.ADMIN:
        raise AdminServiceError("Admin privileges required.", status_code=403)


async def get_global_table_stats(
    session: AsyncSession,
    current_user: UserContext,
) -> list[dict[str, int | str]]:
    """Return seeded (`owner_id IS NULL`) row counts grouped by rule system source."""
    _require_admin(current_user)
    by_source: dict[str, dict[str, int]] = {}
    for col_key, model in _GLOBAL_TABLES:
        stmt = (
            select(model.source, func.count())
            .where(model.owner_id.is_(None))
            .group_by(model.source)
        )
        rows = (await session.execute(stmt)).all()
        for src, cnt in rows:
            src_name = src or "(unspecified)"
            bucket = by_source.setdefault(
                src_name, {k: 0 for k, _ in _GLOBAL_TABLES}
            )
            bucket[col_key] = int(cnt)

    out: list[dict[str, int | str]] = []
    for src_name in sorted(by_source.keys()):
        counts = by_source[src_name]
        total = sum(counts.values())
        out.append({"source": src_name, **counts, "total": total})
    return out


async def reseed_global_data(
    session: AsyncSession,
    current_user: UserContext,
    *,
    data_dir: Path | None = None,
) -> dict[str, int]:
    """Re-ingest bundled `data/` CSV and JSON rulebooks idempotently.

    Only mutates seeded rows (`owner_id IS NULL`). User-owned custom entries,
    characters, users, allies, notes, and creatures are untouched.
    """
    _require_admin(current_user)
    target_dir = data_dir if data_dir is not None else REPO_DATA_DIR
    if not target_dir.is_dir():
        raise AdminServiceError(f"Data directory not found: {target_dir}", status_code=500)

    if _INGEST_LOCK.locked():
        raise AdminServiceError("A data reseed is already in progress. Please wait.", status_code=409)

    async with _INGEST_LOCK:
        report = await run_ingestion_in_session(session, str(target_dir))

    logger.info(
        "Admin reseed completed by %s: files=%d inserted=%d updated=%d",
        current_user.username,
        report["files"],
        report["inserted"],
        report["updated"],
    )
    return report


async def create_verified_admin_backup(
    session: AsyncSession,
    current_user: UserContext,
    password: str,
    *,
    include_passwords: bool = False,
) -> tuple[str, bytes, dict[str, int]]:
    """Re-verify the admin's password, enforce rate limits, and emit a JSON backup.

    Defaults to `include_passwords=False` so credential hashes are not exported
    unless the admin explicitly opts in.
    """
    _require_admin(current_user)
    if not password:
        raise AdminServiceError("Password re-authentication is required.", status_code=401)

    # Sliding-window rate limit per admin account.
    now = time.monotonic()
    recent = [t for t in _backup_timestamps[current_user.id] if now - t < BACKUP_WINDOW_SECONDS]
    _backup_timestamps[current_user.id] = recent
    if len(recent) >= BACKUP_MAX_PER_WINDOW:
        raise AdminServiceError(
            f"Backup rate limit reached (max {BACKUP_MAX_PER_WINDOW} downloads per hour).",
            status_code=429,
        )

    db_user = (
        await session.execute(select(User).where(User.id == current_user.id))
    ).scalars().first()
    if db_user is None or not db_user.is_active or not verify_password(password, db_user.hashed_password):
        logger.warning("Failed admin backup password check for user=%s", current_user.username)
        raise AdminServiceError("Invalid password.", status_code=401)

    envelope = await create_backup(session, include_passwords=include_passwords)
    _backup_timestamps[current_user.id].append(now)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = "full" if include_passwords else "nopasswords"
    filename = f"donjondocs-backup-{suffix}-{stamp}.json"
    payload = envelope.model_dump_json(indent=2).encode("utf-8")

    summary = {
        "users": len(envelope.users),
        "characters": len(envelope.characters),
        "creatures": len(envelope.creatures),
        "custom_globals": sum(len(v) for v in envelope.user_globals.values()),
        "addons": sum(len(v) for v in envelope.character_addons.values()),
    }
    logger.warning(
        "Admin DB backup downloaded by %s (include_passwords=%s, users=%d, characters=%d, creatures=%d)",
        current_user.username,
        include_passwords,
        summary["users"],
        summary["characters"],
        summary["creatures"],
    )
    return filename, payload, summary
