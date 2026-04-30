"""
Tests for app.services.ally_service.

Validates RBAC (owner-only / admin override), CRUD round-trip, and
cascade-on-character-delete.
"""

import pytest
import pytest_asyncio

from app.models.character import CharacterRecord
from app.models.character_addons import CharacterAlly
from app.models.user import User, UserRole
from app.schemas.ally import AllyCreate, AllyUpdate
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.char_sheet_specific import CharacterClassEntry
from app.security import hash_password
from app.services._errors import CharacterServiceError
from app.services.ally_service import (
    create_ally,
    delete_ally,
    list_allies,
    update_ally,
)
from app.services.character_service import create_character, delete_character


def _classes() -> list[CharacterClassEntry]:
    return [CharacterClassEntry(name="Fighter", level=1)]


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    user = User(
        username="ally_owner",
        email="ally_owner@test.com",
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
        username="ally_stranger",
        email="ally_stranger@test.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.STANDARD,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin(db_session) -> User:
    user = User(
        username="ally_admin",
        email="ally_admin@test.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.ADMIN,
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
async def test_create_and_list(db_session, owner, character):
    payload = AllyCreate(name="Goblin Scout", ally_type="Stat Block", body_md="**HP** 7")
    row = await create_ally(db_session, character.id, payload, owner)
    assert row.id and row.character_id == character.id

    rows = await list_allies(db_session, character.id, owner)
    assert [r.name for r in rows] == ["Goblin Scout"]


@pytest.mark.asyncio
async def test_update_partial_fields(db_session, owner, character):
    row = await create_ally(
        db_session, character.id,
        AllyCreate(name="A", ally_type="Pet", body_md="orig"),
        owner,
    )
    updated = await update_ally(
        db_session, row.id, AllyUpdate(name="A renamed"), owner,
    )
    # name changed; body and type preserved.
    assert updated.name == "A renamed"
    assert updated.ally_type == "Pet"
    assert updated.body_md == "orig"


@pytest.mark.asyncio
async def test_stranger_cannot_list(db_session, owner, stranger, character):
    await create_ally(db_session, character.id, AllyCreate(name="x", ally_type="Pet"), owner)
    with pytest.raises(CharacterServiceError, match="Access denied"):
        await list_allies(db_session, character.id, stranger)


@pytest.mark.asyncio
async def test_stranger_cannot_update_or_delete(db_session, owner, stranger, character):
    row = await create_ally(db_session, character.id, AllyCreate(name="x", ally_type="Pet"), owner)
    with pytest.raises(CharacterServiceError, match="Access denied"):
        await update_ally(db_session, row.id, AllyUpdate(name="hacked"), stranger)
    with pytest.raises(CharacterServiceError, match="Access denied"):
        await delete_ally(db_session, row.id, stranger)


@pytest.mark.asyncio
async def test_admin_can_modify_any(db_session, owner, admin, character):
    row = await create_ally(db_session, character.id, AllyCreate(name="x", ally_type="Pet"), owner)
    updated = await update_ally(db_session, row.id, AllyUpdate(name="audited"), admin)
    assert updated.name == "audited"


@pytest.mark.asyncio
async def test_missing_ally_returns_404(db_session, owner):
    with pytest.raises(CharacterServiceError, match="not found") as exc:
        await update_ally(db_session, "no-such-id", AllyUpdate(name="x"), owner)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cascade_delete_on_character_delete(db_session, owner, character):
    await create_ally(db_session, character.id, AllyCreate(name="a", ally_type="Pet"), owner)
    await create_ally(db_session, character.id, AllyCreate(name="b", ally_type="Pet"), owner)

    await delete_character(db_session, character.id, owner)

    # Allies should be gone via cascade.
    from sqlalchemy import select
    remaining = (
        await db_session.execute(
            select(CharacterAlly).where(CharacterAlly.character_id == character.id)
        )
    ).scalars().all()
    assert remaining == []
