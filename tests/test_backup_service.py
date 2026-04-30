"""
Tests for app.services.backup_service.

Covers:
- Round-trip: source DB → envelope → fresh target DB matches the source.
- Excludes CSV-style globals (rows where owner_id IS NULL).
- Dry-run: validation + counts succeed but the target DB is unchanged.
- Merge mode preserves untouched rows in the target.
- Replace mode wipes the target and loads only what's in the envelope.
- Alembic revision mismatch rejects without --force.
- Invalid character_data aborts the whole restore (no partial writes).
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import char_sheet as global_models
from app.models.character import CharacterRecord
from app.models.user import User
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.char_sheet_specific import CharacterClassEntry
from app.security import hash_password
from app.services.backup_service import (
    BackupServiceError,
    RestoreMode,
    create_backup,
    restore_backup,
)
from app.services.character_service import create_character
from app.user_roles import UserRole


def _default_classes() -> list[CharacterClassEntry]:
    return [CharacterClassEntry(name="Fighter", level=1)]


@pytest_asyncio.fixture
async def seed_user(db_session) -> User:
    """A standard user that owns characters and custom globals in the source DB."""
    user = User(
        username="backup_owner",
        email="owner@test.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.STANDARD,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seed_character(db_session, seed_user) -> CharacterRecord:
    return await create_character(
        db_session, "Tharivol", SheetStyle.DND5E, seed_user,
        classes=_default_classes(),
    )


@pytest_asyncio.fixture
async def seed_custom_item(db_session, seed_user) -> global_models.GlobalItem:
    """A user-owned global row — must appear in the backup."""
    item = global_models.GlobalItem(
        name="Sunblade of Tharivol",
        source="homebrew",
        owner_id=seed_user.id,
    )
    db_session.add(item)
    await db_session.flush()
    await db_session.refresh(item)
    return item


@pytest_asyncio.fixture
async def seed_csv_item(db_session) -> global_models.GlobalItem:
    """A bulk-rule global row (owner_id IS NULL) — must NOT appear in the backup."""
    item = global_models.GlobalItem(
        name="Longsword",
        source="SRD",
        owner_id=None,
    )
    db_session.add(item)
    await db_session.flush()
    await db_session.refresh(item)
    return item


@pytest_asyncio.fixture
async def target_engine():
    """Independent in-memory engine that plays the role of a restore target."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def target_session(target_engine) -> AsyncSession:
    factory = async_sessionmaker(target_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


async def _new_session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory()


@pytest.mark.asyncio
async def test_backup_round_trip(
    db_session, target_engine,
    seed_user, seed_character, seed_custom_item, seed_csv_item,
):
    """End-to-end: source → envelope → target. Rows match; CSV globals excluded."""
    # Source side: db_session is already populated by fixtures.
    await db_session.commit()
    envelope = await create_backup(db_session)

    # Sanity: CSV-style global must not be in the envelope.
    backed_items = envelope.user_globals["global_item"]
    assert all(row["owner_id"] is not None for row in backed_items)
    assert any(row["name"] == "Sunblade of Tharivol" for row in backed_items)
    assert not any(row["name"] == "Longsword" for row in backed_items)

    # Restore into the empty target engine.
    factory = async_sessionmaker(target_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as target:
        report = await restore_backup(target, envelope, mode=RestoreMode.MERGE)
        assert report.users_inserted == 1
        assert report.characters_inserted == 1
        assert report.user_globals_inserted == 1

    # Verify in a fresh session so we read committed state.
    async with factory() as verify:
        users = (await verify.execute(select(User))).scalars().all()
        chars = (await verify.execute(select(CharacterRecord))).scalars().all()
        items = (await verify.execute(select(global_models.GlobalItem))).scalars().all()

    assert {u.id for u in users} == {seed_user.id}
    assert users[0].email == seed_user.email
    assert users[0].hashed_password == seed_user.hashed_password
    assert {c.id for c in chars} == {seed_character.id}
    assert chars[0].name == "Tharivol"
    assert chars[0].character_data["name"] == "Tharivol"
    assert {i.id for i in items} == {seed_custom_item.id}


@pytest.mark.asyncio
async def test_restore_dry_run_does_not_write(
    db_session, target_engine, seed_user, seed_character,
):
    """--dry-run validates and counts but rolls back, so the target stays empty."""
    await db_session.commit()
    envelope = await create_backup(db_session)

    factory = async_sessionmaker(target_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as target:
        report = await restore_backup(target, envelope, mode=RestoreMode.MERGE, dry_run=True)
        # Counts reflect what *would* have happened.
        assert report.users_inserted == 1
        assert report.characters_inserted == 1

    async with factory() as verify:
        users = (await verify.execute(select(User))).scalars().all()
        chars = (await verify.execute(select(CharacterRecord))).scalars().all()

    assert users == []
    assert chars == []


@pytest.mark.asyncio
async def test_restore_merge_preserves_untouched_rows(
    db_session, target_engine, seed_user, seed_character,
):
    """Merge mode must not delete rows in the target that aren't in the envelope."""
    await db_session.commit()
    envelope = await create_backup(db_session)

    factory = async_sessionmaker(target_engine, class_=AsyncSession, expire_on_commit=False)

    # Pre-seed the target with an unrelated user that the envelope does NOT contain.
    async with factory() as target:
        existing = User(
            username="prior",
            email="prior@test.com",
            hashed_password=hash_password("Other123!"),
            role=UserRole.STANDARD,
        )
        target.add(existing)
        await target.commit()
        prior_id = existing.id

    async with factory() as target:
        await restore_backup(target, envelope, mode=RestoreMode.MERGE)

    async with factory() as verify:
        users = (await verify.execute(select(User))).scalars().all()

    user_ids = {u.id for u in users}
    assert prior_id in user_ids
    assert seed_user.id in user_ids


@pytest.mark.asyncio
async def test_restore_replace_wipes_and_loads(
    db_session, target_engine, seed_user, seed_character,
):
    """Replace mode wipes user-data tables before loading the envelope."""
    await db_session.commit()
    envelope = await create_backup(db_session)

    factory = async_sessionmaker(target_engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as target:
        existing = User(
            username="prior",
            email="prior@test.com",
            hashed_password=hash_password("Other123!"),
            role=UserRole.STANDARD,
        )
        target.add(existing)
        await target.commit()

    async with factory() as target:
        await restore_backup(target, envelope, mode=RestoreMode.REPLACE)

    async with factory() as verify:
        users = (await verify.execute(select(User))).scalars().all()

    assert {u.id for u in users} == {seed_user.id}


@pytest.mark.asyncio
async def test_restore_rejects_alembic_mismatch(
    db_session, target_engine, seed_user, seed_character,
):
    """Without --force, a mismatched alembic_revision must abort the restore."""
    await db_session.commit()
    envelope = await create_backup(db_session)
    # Both DBs are unstamped (None). Forge a non-None backup rev to trigger mismatch.
    envelope.alembic_revision = "deadbeef00"

    factory = async_sessionmaker(target_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as target:
        with pytest.raises(BackupServiceError, match="Alembic revision mismatch"):
            await restore_backup(target, envelope, mode=RestoreMode.MERGE)

    # And --force lets it through.
    async with factory() as target:
        report = await restore_backup(target, envelope, mode=RestoreMode.MERGE, force=True)
        assert report.users_inserted == 1


@pytest.mark.asyncio
async def test_restore_rejects_invalid_character_data(
    db_session, target_engine, seed_user, seed_character,
):
    """A corrupt character_data blob aborts the whole restore — no partial writes."""
    await db_session.commit()
    envelope = await create_backup(db_session)
    # Wipe the blob so the Character schema rejects it.
    envelope.characters[0]["character_data"] = {"this": "is not a character"}

    factory = async_sessionmaker(target_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as target:
        with pytest.raises(BackupServiceError, match="Invalid character_data"):
            await restore_backup(target, envelope, mode=RestoreMode.MERGE)

    # Pre-validation runs before any writes, so target stays empty.
    async with factory() as verify:
        users = (await verify.execute(select(User))).scalars().all()
        chars = (await verify.execute(select(CharacterRecord))).scalars().all()
    assert users == []
    assert chars == []
