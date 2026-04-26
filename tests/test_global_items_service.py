"""
Tests for global_items_service: listing + owner scoping for classes / skills /
attributes / weapons / armor / items, and the add_custom_class helper.

Primary concern: a user's custom entries must NEVER leak into another user's
list results. Globals (owner_id IS NULL) are visible to everyone.
"""

import pytest
import pytest_asyncio

from app.models.char_sheet import (
    GlobalClass, GlobalSkill, GlobalAttribute,
    GlobalWeapon, GlobalArmor, GlobalItem,
)
from app.schemas.char_sheet_global import SheetStyle
from app.services.global_items_service import (
    list_classes, list_skills, list_attributes,
    list_weapons, list_armor, list_items,
    add_custom_class,
)


STYLE = SheetStyle.DND5E


@pytest_asyncio.fixture
async def seeded_globals(db_session):
    """Seed a small set of global (owner_id=None) rows for each type."""
    db_session.add_all([
        GlobalClass(name="Fighter", source=STYLE.value, hit_dice="d10",
                    primary_ability="STR", saving_throws="STR, CON",
                    proficiencies="All armor, shields, simple weapons"),
        GlobalSkill(name="Athletics", source=STYLE.value, attribute="STR"),
        GlobalAttribute(name="Strength", alias="STR", source=STYLE.value),
        GlobalWeapon(name="Longsword", source=STYLE.value),
        GlobalArmor(name="Chain Mail", source=STYLE.value),
        GlobalItem(name="Torch", source=STYLE.value),
    ])
    await db_session.flush()


@pytest.mark.asyncio
async def test_list_classes_returns_global_rows(db_session, seeded_globals):
    rows = await list_classes(db_session, STYLE, owner_id="user-a")
    names = [r.name for r in rows]
    assert "Fighter" in names


@pytest.mark.asyncio
async def test_list_classes_scopes_custom_to_owner(db_session, seeded_globals):
    db_session.add(GlobalClass(name="SecretClass", source=STYLE.value,
                               hit_dice="d6", primary_ability="INT",
                               saving_throws="INT, WIS", proficiencies="",
                               owner_id="user-a"))
    await db_session.flush()

    a_rows = await list_classes(db_session, STYLE, owner_id="user-a")
    b_rows = await list_classes(db_session, STYLE, owner_id="user-b")

    a_names = [r.name for r in a_rows]
    b_names = [r.name for r in b_rows]
    assert "SecretClass" in a_names
    assert "SecretClass" not in b_names  # must not leak
    # Global row visible to both
    assert "Fighter" in a_names and "Fighter" in b_names


@pytest.mark.asyncio
async def test_list_skills_scopes_custom(db_session, seeded_globals):
    db_session.add(GlobalSkill(name="PrivateSkill", source=STYLE.value,
                               attribute="INT", owner_id="user-a"))
    await db_session.flush()

    b_rows = await list_skills(db_session, STYLE, owner_id="user-b")
    assert all(r.name != "PrivateSkill" for r in b_rows)
    assert any(r.name == "Athletics" for r in b_rows)


@pytest.mark.asyncio
async def test_list_attributes_scopes_custom(db_session, seeded_globals):
    db_session.add(GlobalAttribute(name="Guts", alias="GTS",
                                   source=STYLE.value, owner_id="user-a"))
    await db_session.flush()

    b_rows = await list_attributes(db_session, STYLE, owner_id="user-b")
    assert all(r.name != "Guts" for r in b_rows)


@pytest.mark.asyncio
async def test_list_weapons_does_not_leak(db_session, seeded_globals):
    # Pre-existing data-leak bug: other users' custom weapons must not appear.
    db_session.add(GlobalWeapon(name="SecretBlade", source=STYLE.value,
                                owner_id="user-a"))
    await db_session.flush()

    b_rows = await list_weapons(db_session, STYLE, owner_id="user-b")
    assert all(r.name != "SecretBlade" for r in b_rows)
    assert any(r.name == "Longsword" for r in b_rows)


@pytest.mark.asyncio
async def test_list_armor_does_not_leak(db_session, seeded_globals):
    db_session.add(GlobalArmor(name="SecretPlate", source=STYLE.value,
                               owner_id="user-a"))
    await db_session.flush()
    b_rows = await list_armor(db_session, STYLE, owner_id="user-b")
    assert all(r.name != "SecretPlate" for r in b_rows)


@pytest.mark.asyncio
async def test_list_items_does_not_leak(db_session, seeded_globals):
    db_session.add(GlobalItem(name="SecretPotion", source=STYLE.value,
                              owner_id="user-a"))
    await db_session.flush()
    b_rows = await list_items(db_session, STYLE, owner_id="user-b")
    assert all(r.name != "SecretPotion" for r in b_rows)


@pytest.mark.asyncio
async def test_list_filters_by_style(db_session, seeded_globals):
    # A class registered under a different style should not appear.
    db_session.add(GlobalClass(name="DarkKnight", source=SheetStyle.SHADOWDARK.value,
                               hit_dice="d8", primary_ability="STR",
                               saving_throws="-", proficiencies=""))
    await db_session.flush()

    dnd_rows = await list_classes(db_session, STYLE, owner_id="user-a")
    assert all(r.name != "DarkKnight" for r in dnd_rows)

    sd_rows = await list_classes(db_session, SheetStyle.SHADOWDARK, owner_id="user-a")
    assert any(r.name == "DarkKnight" for r in sd_rows)


@pytest.mark.asyncio
async def test_add_custom_class_scopes_to_owner(db_session):
    row = await add_custom_class(
        db_session,
        owner_id="user-a",
        style=STYLE,
        name="MadMage",
        hit_dice="d6",
        saving_throws="INT, WIS",
    )
    assert row.owner_id == "user-a"
    assert row.source == STYLE.value
    # Only user-a should see it
    a_rows = await list_classes(db_session, STYLE, owner_id="user-a")
    b_rows = await list_classes(db_session, STYLE, owner_id="user-b")
    assert any(r.name == "MadMage" for r in a_rows)
    assert all(r.name != "MadMage" for r in b_rows)
