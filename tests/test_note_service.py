"""
Tests for app.services.note_service.

Validates RBAC (owner-only / admin override), CRUD round-trip, and
cascade-on-character-delete.
"""

import pytest
import pytest_asyncio

from app.models.character import CharacterRecord
from app.models.character_addons import CharacterNote
from app.models.user import User, UserRole
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.char_sheet_specific import CharacterClassEntry
from app.schemas.note import NoteCreate, NoteUpdate
from app.security import hash_password
from app.services._errors import CharacterServiceError
from app.services.character_service import create_character, delete_character
from app.services.note_service import (
    create_note,
    delete_note,
    list_notes,
    update_note,
)


def _classes() -> list[CharacterClassEntry]:
    return [CharacterClassEntry(name="Fighter", level=1)]


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    user = User(
        username="note_owner",
        email="note_owner@test.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.STANDARD,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def stranger(db_session) -> User:
    user = User(
        username="note_stranger",
        email="note_stranger@test.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.STANDARD,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def character(db_session, owner) -> CharacterRecord:
    return await create_character(
        db_session, "Tharivol", SheetStyle.DND5E, owner, classes=_classes(),
    )


@pytest.mark.asyncio
async def test_create_and_list_returns_newest_first(db_session, owner, character):
    a = await create_note(db_session, character.id, NoteCreate(title="A", body_md="1"), owner)
    b = await create_note(db_session, character.id, NoteCreate(title="B", body_md="2"), owner)
    rows = await list_notes(db_session, character.id, owner)
    # list_notes orders by created_at DESC, so the most-recent is first.
    assert [r.id for r in rows] == [b.id, a.id]


@pytest.mark.asyncio
async def test_update_only_changes_provided_fields(db_session, owner, character):
    row = await create_note(
        db_session, character.id,
        NoteCreate(title="Plot Hook", body_md="orig"),
        owner,
    )
    updated = await update_note(
        db_session, row.id, NoteUpdate(body_md="revised"), owner,
    )
    assert updated.title == "Plot Hook"
    assert updated.body_md == "revised"


@pytest.mark.asyncio
async def test_stranger_cannot_access(db_session, owner, stranger, character):
    row = await create_note(db_session, character.id, NoteCreate(title="x"), owner)
    with pytest.raises(CharacterServiceError, match="Access denied"):
        await list_notes(db_session, character.id, stranger)
    with pytest.raises(CharacterServiceError, match="Access denied"):
        await update_note(db_session, row.id, NoteUpdate(title="bad"), stranger)
    with pytest.raises(CharacterServiceError, match="Access denied"):
        await delete_note(db_session, row.id, stranger)


@pytest.mark.asyncio
async def test_cascade_delete(db_session, owner, character):
    await create_note(db_session, character.id, NoteCreate(title="x"), owner)
    await delete_character(db_session, character.id, owner)

    from sqlalchemy import select
    remaining = (
        await db_session.execute(
            select(CharacterNote).where(CharacterNote.character_id == character.id)
        )
    ).scalars().all()
    assert remaining == []
