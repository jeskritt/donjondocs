"""
AI Helper Docstring
Purpose: All write/read operations on `CharacterRecord` with owner-based RBAC. Owns character creation (with seeding), updates to the JSON `character_data` blob, listing, deletion, the rest mechanics entry point, and the export/import dispatch (including the per-character ally and note addons).
Interactions:
- `app.models.character.CharacterRecord`: target ORM row (1:1 per character).
- `app.models.character_addons.{CharacterAlly, CharacterNote}`: addon rows packed into the export envelope and recreated on import.
- `app.services.character_seeding`: initial `character_data` for a fresh character.
- `app.services.character_mechanics.apply_rest`: pure helper used by `rest_character`.
- `app.services.character_io`: `EXPORT_VERSION`, `migrate_character_data`, filename helper.
- `app.api.character_routes` and `app.ui.pages.character_sheet`: only callers; ServiceErrors are raised here and translated by routes/pages.
- Enforces `STANDARD_CHARACTER_LIMIT` for non-premium/admin users via row-locked count.
"""

"""Character service logic with RBAC constraints."""

from datetime import datetime, timezone
from typing import Any, Sequence
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import CharacterRecord
from app.models.character_addons import CharacterAlly, CharacterNote
from app.models.user import User
from app.rule_systems import SystemFamily, system_family_for
from app.schemas.ally import AllyCreate
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.char_sheet_specific import Character, CharacterClassEntry
from app.schemas.note import NoteCreate
from app.schemas.registry import parse_character
from app.services._errors import CharacterServiceError
from app.services.character_io import (
    EXPORT_VERSION,
    export_filename_for,
    migrate_character_data,
)
from app.services.character_mechanics import apply_rest
from app.services.character_seeding import (
    build_blank_anarchy_character_data,
    build_blank_character_data,
    prof_bonus_for,
    seed_classes_from_db,
    seed_profs_from_primary,
    seed_saves_from_primary,
)
from app.user_context import UserContext
from app.user_roles import UserRole


STANDARD_CHARACTER_LIMIT = 25


async def _assert_within_character_limit(
    session: AsyncSession, owner: UserContext
) -> None:
    """Enforce the Standard-tier character limit without a TOCTOU race.

    Locks the owner's user row (`SELECT ... FOR UPDATE`) before counting so
    concurrent create/import requests from the same owner serialize on that
    row, even under Postgres. SQLite's file-level write lock makes the lock
    a no-op there, but also makes the race impossible in practice.
    """
    if owner.role != UserRole.STANDARD:
        return
    await session.execute(
        select(User.id).where(User.id == owner.id).with_for_update()
    )
    count = (
        await session.execute(
            select(func.count())
            .select_from(CharacterRecord)
            .where(CharacterRecord.owner_id == owner.id)
        )
    ).scalar_one()
    if count >= STANDARD_CHARACTER_LIMIT:
        raise CharacterServiceError(
            f"Standard users are limited to {STANDARD_CHARACTER_LIMIT} "
            "characters. Please upgrade to Premium.",
            status_code=403,
        )


async def list_user_characters(session: AsyncSession, user_id: str) -> Sequence[CharacterRecord]:
    """Return all characters owned by a specific user."""
    stmt = (
        select(CharacterRecord)
        .where(CharacterRecord.owner_id == user_id)
        .order_by(CharacterRecord.updated_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_character(session: AsyncSession, character_id: str, current_user: UserContext) -> CharacterRecord:
    """Get a single character by ID, ensuring ownership or admin access."""
    stmt = select(CharacterRecord).where(CharacterRecord.id == character_id)
    result = await session.execute(stmt)
    char = result.scalars().first()

    if not char:
        raise CharacterServiceError("Character not found.", status_code=404)

    if char.owner_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise CharacterServiceError("Access denied.", status_code=403)

    return char


async def create_character(
    session: AsyncSession,
    name: str,
    style: SheetStyle,
    current_user: UserContext,
    classes: list[CharacterClassEntry] | None = None,
    ancestry: str = "Human",
    culture: str | None = None,
    background: str = "Peasant",
    vigor_enabled: bool = False,
    *,
    metatype: str = "Human",
    keywords: list[str] | None = None,
) -> CharacterRecord:
    """Create a new character for a user, enforcing limits.

    Dispatches by `SystemFamily`:
    - 5e family: requires at least one `CharacterClassEntry`, seeds hit dice,
      saves, and weapon/armor proficiencies from `GlobalClass`.
    - Shadowrun: Anarchy 2.0: seeds attributes, metatype starting Edge, the 14
      Anarchy skills, and an Unarmed attack entry (no classes required).
    """
    family = system_family_for(style)
    if family == SystemFamily.DND5E:
        if not classes:
            raise CharacterServiceError("At least one class is required.")
        await _assert_within_character_limit(session, current_user)
        seeded_classes = await seed_classes_from_db(session, style, current_user.id, classes)
        blank_data = await build_blank_character_data(
            session, name, style, current_user, seeded_classes,
            ancestry, culture, background, vigor_enabled=vigor_enabled,
        )
    else:
        await _assert_within_character_limit(session, current_user)
        blank_data = await build_blank_anarchy_character_data(
            session, name, current_user, metatype=metatype, keywords=keywords,
        )

    new_char = CharacterRecord(
        name=name,
        style=style,
        owner_id=current_user.id,
        character_data=blank_data,
    )

    session.add(new_char)
    await session.commit()
    await session.refresh(new_char)

    return new_char


async def delete_character(session: AsyncSession, character_id: str, current_user: UserContext) -> None:
    """Delete a character, ensuring ownership or admin access."""
    char = await get_character(session, character_id, current_user)
    await session.delete(char)
    await session.commit()


async def rest_character(
    session: AsyncSession,
    character_id: str,
    kind: str,
    options: dict | None,
    current_user: UserContext,
) -> CharacterRecord:
    """Authorize and apply a rest/reset. Persists the updated character_data blob."""
    char = await get_character(session, character_id, current_user)
    new_data = apply_rest(char.character_data, kind, options, style=char.style)
    char.character_data = new_data
    await session.commit()
    await session.refresh(char)
    return char


async def update_character(session: AsyncSession, character_id: str, update_data: dict, current_user: UserContext) -> CharacterRecord:
    """Update a character's internal data representation.

    For 5e-family sheets, when `classes` is part of the update:
      - prof_bonus is re-derived from the new total level
      - saves and weapon/armor proficiencies are re-seeded from the (new)
        primary class (classes[0]). Language/tool/instrument/game entries are
        preserved since they aren't class-granted.
    prof_bonus is not user-editable — it scales from class levels.
    """
    char = await get_character(session, character_id, current_user)

    # Merge existing data with updates
    current_data = dict(char.character_data)
    current_data.update(update_data)

    if "classes" in update_data and system_family_for(char.style) == SystemFamily.DND5E:
        style = SheetStyle(current_data.get("style", SheetStyle.DND5E.value))
        raw_entries = [CharacterClassEntry(**c) for c in current_data.get("classes", [])]
        # Always re-seed from GlobalClass so save/prof grants stay correct even
        # when the caller passed bare name+level dicts from a form.
        class_entries = await seed_classes_from_db(session, style, char.owner_id, raw_entries)
        total_level = sum(c.level for c in class_entries)

        current_data["classes"] = [c.model_dump() for c in class_entries]
        current_data["level"] = total_level
        current_data["prof_bonus"] = prof_bonus_for(total_level, style)
        current_data["character_class"] = (
            class_entries[0].name if len(class_entries) == 1
            else " / ".join(f"{c.name} {c.level}" for c in class_entries)
        ) if class_entries else ""

        # Re-seed saves + weapon/armor profs from the new primary class.
        # Preserve language/tool/instrument/game entries (not class-granted).
        current_data["saving_throws"] = seed_saves_from_primary(class_entries)
        new_profs = seed_profs_from_primary(class_entries)
        existing_profs = dict(current_data.get("proficiency", {}))
        existing_profs["weapon"] = new_profs["weapon"]
        existing_profs["armor"] = new_profs["armor"]
        for key in ("language", "instrument", "tool", "game"):
            existing_profs.setdefault(key, [])
        current_data["proficiency"] = existing_profs

    char.character_data = current_data
    if "name" in update_data:
        char.name = update_data["name"]

    await session.commit()
    await session.refresh(char)
    return char


async def export_character(
    session: AsyncSession,
    character_id: str,
    current_user: UserContext,
) -> dict:
    """Export a character as a versioned JSON-serializable dict.

    Allies and notes are packed at envelope level (sibling keys to
    `character_data`) — they live in their own tables. Each entry
    carries only the fields the importer needs to recreate it; `id`
    and `character_id` are intentionally omitted because the importer
    assigns fresh UUIDs and a new parent.
    """
    rec = await get_character(session, character_id, current_user)
    allies_rows = (
        await session.execute(
            select(CharacterAlly)
            .where(CharacterAlly.character_id == character_id)
            .order_by(CharacterAlly.created_at.asc())
        )
    ).scalars().all()
    notes_rows = (
        await session.execute(
            select(CharacterNote)
            .where(CharacterNote.character_id == character_id)
            .order_by(CharacterNote.created_at.desc())
        )
    ).scalars().all()
    return {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "name": rec.name,
        "style": rec.style.value,
        "character_data": rec.character_data,
        "allies": [
            {"name": a.name, "ally_type": a.ally_type, "body_md": a.body_md}
            for a in allies_rows
        ],
        "notes": [
            {"title": n.title, "body_md": n.body_md} for n in notes_rows
        ],
    }


async def import_character(
    session: AsyncSession,
    name: str,
    style: SheetStyle,
    character_data: dict,
    current_user: UserContext,
    version: int = EXPORT_VERSION,
    allies: list[dict[str, Any]] | None = None,
    notes: list[dict[str, Any]] | None = None,
) -> CharacterRecord:
    """Import a character from an exported JSON envelope.

    Validates data against the Character schema, overrides owner_id,
    generates a fresh ID, and enforces character count limits. When the
    envelope version is older than EXPORT_VERSION, character_data is run
    through the migration chain before validation.

    `allies` and `notes` are accepted as opt-in lists at envelope level
    (added in EXPORT_VERSION 6). Each entry is validated against
    `AllyCreate` / `NoteCreate` before insert; an invalid entry rolls back
    the whole import. Older exports without these keys import cleanly with
    no addon rows.
    """
    await _assert_within_character_limit(session, current_user)

    character_data = migrate_character_data(character_data, version, style=style)

    character_data["owner_id"] = str(current_user.id)
    character_data["style"] = style.value
    character_data["name"] = name

    parse_character(style, character_data)

    # Validate addon payloads up front so we don't half-create the character.
    ally_payloads = [AllyCreate(**a) for a in (allies or [])]
    note_payloads = [NoteCreate(**n) for n in (notes or [])]

    new_char = CharacterRecord(
        id=str(uuid.uuid4()),
        name=name,
        style=style,
        owner_id=current_user.id,
        character_data=character_data,
    )
    session.add(new_char)
    await session.flush()

    for payload in ally_payloads:
        session.add(CharacterAlly(
            character_id=new_char.id,
            name=payload.name,
            ally_type=payload.ally_type,
            body_md=payload.body_md,
        ))
    for payload in note_payloads:
        session.add(CharacterNote(
            character_id=new_char.id,
            title=payload.title,
            body_md=payload.body_md,
        ))

    await session.commit()
    await session.refresh(new_char)
    return new_char
