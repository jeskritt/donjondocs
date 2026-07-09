"""
AI Helper Docstring
Purpose: Integration tests for the CSV ingest pipeline covering classes, armor, weapons, equipment, skills, and armor AC stat extraction (base_ac, dex_cap, is_shield).
Interactions:
- Tracks against async `session.execute` queries from `conftest.py`. Operates directly over `app.cli.ingest.py`.
"""

import pytest
import os
import tempfile
import csv

from sqlalchemy import select

from app.cli.ingest import ingest_file, normalize_key, get_style_from_filename
from app.models.char_sheet import GlobalClass
from app.schemas.char_sheet_global import SheetStyle

@pytest.mark.asyncio
async def test_ingest_classes_phb2014(db_session):
    # Create a temporary CSV file imitating classes_phb2014.csv
    csv_content = [
        ["name", "hit_dice", "primary_ability", "saving_throws", "proficiencies"],
        ["Fighter", "d10", "Strength", "Strength, Constitution", "All armor, shields, simple and martial weapons"],
        ["Wizard", "d6", "Intelligence", "Intelligence, Wisdom", "Daggers, darts, slings, quarterstaffs, light crossbows"]
    ]
    
    with tempfile.NamedTemporaryFile(mode="w", prefix="classes_", suffix="_phb2014.csv", delete=False, newline="") as tf:
        writer = csv.writer(tf)
        writer.writerows(csv_content)
        filepath = tf.name

    try:
        # Run the ingestion function
        await ingest_file(db_session, filepath)
        # Assuming db_session changes need to be fully committed or flushed depending on test config
        # the session might autocommit inside ingest_file. Let's check DB.
        
        stmt = select(GlobalClass).where(GlobalClass.name == "Fighter")
        result = await db_session.execute(stmt)
        fighter = result.scalars().first()
        
        assert fighter is not None
        assert fighter.name == "Fighter"
        assert fighter.source == "Dungeons & Dragons 5e"
        assert fighter.owner_id is None
        assert fighter.hit_dice == "d10"
        
        stmt = select(GlobalClass).where(GlobalClass.name == "Wizard")
        result = await db_session.execute(stmt)
        wizard = result.scalars().first()
        
        assert wizard is not None
        assert wizard.hit_dice == "d6"
        assert wizard.source == "Dungeons & Dragons 5e"
    
    finally:
        os.remove(filepath)

def test_normalize_key():
    assert normalize_key("Weapon Name") == "name"
    assert normalize_key("Armor Class") == "armor_class"
    assert normalize_key("Cost") == "value"
    assert normalize_key("Stealth") == "disadvantage_on_stealth"
    assert normalize_key("Item") == "name"
    assert normalize_key("Armor Type") == "type"

def test_get_style_from_filename():
    assert get_style_from_filename("weapons_phb2014.csv") == SheetStyle.DND5E
    assert get_style_from_filename("armor_a5e.csv") == SheetStyle.A5E
    assert get_style_from_filename("classes_shadowdark.csv") == SheetStyle.SHADOWDARK
    assert get_style_from_filename("classes_um5.csv") == SheetStyle.UM5
    assert get_style_from_filename("weapon_ultramodern.csv") == SheetStyle.UM5
    assert get_style_from_filename("random.csv") == SheetStyle.DND5E


# ---------------------------------------------------------------------------
# New tests for BUG-04: cover armor, weapon, equipment, unknown, upsert paths
# ---------------------------------------------------------------------------

from app.models.char_sheet import GlobalArmor, GlobalWeapon, GlobalItem

@pytest.mark.asyncio
async def test_ingest_armor_a5e(db_session):
    csv_content = [
        ["Armor Name", "Armor Type", "Cost", "Armor Class (AC)", "Strength", "Stealth", "Weight", "Notes"],
        ["Chain Mail", "Heavy", "75 gp", "16", "13", "Disadvantage", "55 lb.", "-"],
        ["Leather", "Light", "10 gp", "11 + Dex modifier", "-", "-", "10 lb.", "-"],
    ]

    with tempfile.NamedTemporaryFile(mode="w", prefix="armor_", suffix="_a5e.csv", delete=False, newline="") as tf:
        writer = csv.writer(tf)
        writer.writerows(csv_content)
        filepath = tf.name

    try:
        await ingest_file(db_session, filepath)

        stmt = select(GlobalArmor).where(GlobalArmor.name == "Chain Mail")
        result = await db_session.execute(stmt)
        chain_mail = result.scalars().first()

        assert chain_mail is not None
        assert chain_mail.source == "Level Up: Advanced 5e"
        assert chain_mail.armor_class == "16"
        assert chain_mail.strength_requirement == "13"
        # disadvantage_on_stealth is coerced to string by SQLAlchemy
        assert chain_mail.disadvantage_on_stealth  # truthy - "Disadvantage" was present
        assert chain_mail.owner_id is None

        stmt = select(GlobalArmor).where(GlobalArmor.name == "Leather")
        result = await db_session.execute(stmt)
        leather = result.scalars().first()
        assert leather is not None
    finally:
        os.remove(filepath)


@pytest.mark.asyncio
async def test_ingest_weapon_phb2014(db_session):
    csv_content = [
        ["Weapon Name", "Weapon Type", "Cost", "Damage", "Weight", "Properties"],
        ["Longsword", "Martial Melee", "15 gp", "1d8 slashing", "3 lb.", "Versatile (1d10)"],
    ]

    with tempfile.NamedTemporaryFile(mode="w", prefix="weapon_", suffix="_phb2014.csv", delete=False, newline="") as tf:
        writer = csv.writer(tf)
        writer.writerows(csv_content)
        filepath = tf.name

    try:
        await ingest_file(db_session, filepath)

        stmt = select(GlobalWeapon).where(GlobalWeapon.name == "Longsword")
        result = await db_session.execute(stmt)
        longsword = result.scalars().first()

        assert longsword is not None
        assert longsword.source == "Dungeons & Dragons 5e"
        assert longsword.damage == "1d8 slashing"
        assert longsword.notes == "Versatile (1d10)"
        assert longsword.owner_id is None
    finally:
        os.remove(filepath)


@pytest.mark.asyncio
async def test_ingest_equipment_shadowdark(db_session):
    csv_content = [
        ["Item", "Cost", "Weight"],
        ["Torch", "1 gp", "1 lb."],
    ]

    with tempfile.NamedTemporaryFile(mode="w", prefix="equipment_", suffix="_shadowdark.csv", delete=False, newline="") as tf:
        writer = csv.writer(tf)
        writer.writerows(csv_content)
        filepath = tf.name

    try:
        await ingest_file(db_session, filepath)

        stmt = select(GlobalItem).where(GlobalItem.name == "Torch")
        result = await db_session.execute(stmt)
        torch = result.scalars().first()

        assert torch is not None
        assert torch.source == "Shadowdark RPG"
        assert torch.value == "1 gp"
        assert torch.owner_id is None
    finally:
        os.remove(filepath)


@pytest.mark.asyncio
async def test_ingest_equipment_type_and_effects_columns(db_session):
    """Equipment CSVs may carry Type + Effects columns (used by the UM5 vehicle /
    cybernetics / ammo gear); they must land on GlobalItem.type / .effects."""
    csv_content = [
        ["Item", "Cost", "Weight", "Type", "Effects"],
        ["4-wheel ATV", "$500", "-", "Vehicle", "Cap 2; Speed 30 ft.; HP 20; Size M"],
    ]
    with tempfile.NamedTemporaryFile(mode="w", prefix="equipment_vehicles_", suffix="_um5.csv", delete=False, newline="") as tf:
        csv.writer(tf).writerows(csv_content)
        filepath = tf.name
    try:
        await ingest_file(db_session, filepath)
        atv = (await db_session.execute(
            select(GlobalItem).where(GlobalItem.name == "4-wheel ATV")
        )).scalars().first()
        assert atv is not None
        assert atv.source == "Ultramodern 5e"
        assert atv.value == "$500"
        assert atv.type == "Vehicle"
        assert "Speed 30 ft." in (atv.effects or "")
    finally:
        os.remove(filepath)


@pytest.mark.asyncio
async def test_ingest_unknown_file_skipped(db_session, capsys):
    """An unrecognized file prefix should be silently skipped with a print message."""
    with tempfile.NamedTemporaryFile(mode="w", prefix="spells_", suffix="_phb2014.csv", delete=False, newline="") as tf:
        writer = csv.writer(tf)
        writer.writerows([["name"], ["Fireball"]])
        filepath = tf.name

    try:
        await ingest_file(db_session, filepath)
        captured = capsys.readouterr()
        assert "Skipping unknown file prefix" in captured.out
    finally:
        os.remove(filepath)


@pytest.mark.asyncio
async def test_ingest_skills_phb2014(db_session):
    """Skills CSVs populate GlobalSkill with example_uses + normalized attribute codes."""
    from app.models.char_sheet import GlobalSkill

    csv_content = [
        ["Skill", "Ability", "Example Uses", "Specialties"],
        ["Athletics", "Strength", "Climbing, swimming, jumping.", ""],
        ["Arcana", "Intelligence", "Recall lore about spells and magical traditions.", "Runes, Planes"],
    ]

    with tempfile.NamedTemporaryFile(mode="w", prefix="skills_", suffix="_phb2014.csv", delete=False, newline="") as tf:
        writer = csv.writer(tf)
        writer.writerows(csv_content)
        filepath = tf.name

    try:
        await ingest_file(db_session, filepath)

        stmt = select(GlobalSkill).where(GlobalSkill.name == "Athletics")
        ath = (await db_session.execute(stmt)).scalars().first()
        assert ath is not None
        assert ath.attribute == "STR"  # normalized from "Strength"
        assert "Climbing" in (ath.example_uses or "")
        assert ath.owner_id is None

        stmt = select(GlobalSkill).where(GlobalSkill.name == "Arcana")
        arc = (await db_session.execute(stmt)).scalars().first()
        assert arc is not None
        assert arc.attribute == "INT"
        assert arc.specialties == "Runes, Planes"
    finally:
        os.remove(filepath)


@pytest.mark.asyncio
async def test_ingest_upsert_updates_existing_row(db_session):
    """Running ingest twice with the same name+source should update, not duplicate."""
    csv_v1 = [
        ["name", "hit_dice", "primary_ability", "saving_throws", "proficiencies"],
        ["Ranger", "d10", "Dexterity", "Strength, Dexterity", "Light+medium armor, shields, simple+martial weapons"],
    ]
    csv_v2 = [
        ["name", "hit_dice", "primary_ability", "saving_throws", "proficiencies"],
        ["Ranger", "d10", "Dexterity & Wisdom", "Strength, Dexterity", "Light+medium armor, shields, simple+martial weapons"],
    ]

    for csv_content in (csv_v1, csv_v2):
        with tempfile.NamedTemporaryFile(mode="w", prefix="classes_", suffix="_phb2014.csv", delete=False, newline="") as tf:
            writer = csv.writer(tf)
            writer.writerows(csv_content)
            filepath = tf.name

        try:
            await ingest_file(db_session, filepath)
        finally:
            os.remove(filepath)

    stmt = select(GlobalClass).where(GlobalClass.name == "Ranger")
    result = await db_session.execute(stmt)
    rangers = result.scalars().all()

    assert len(rangers) == 1
    assert rangers[0].primary_ability == "Dexterity & Wisdom"


# ---------------------------------------------------------------------------
# Phase 4: armor AC numerics come through ingest
# ---------------------------------------------------------------------------

def test_parse_armor_stats_light_uncapped():
    from app.cli.ingest import parse_armor_stats
    # PHB Leather: Light / "11" / "-"  → base 11, uncapped, not shield
    assert parse_armor_stats("Light", "11", "-") == (11, None, False)


def test_parse_armor_stats_medium_capped_at_two():
    from app.cli.ingest import parse_armor_stats
    # PHB Hide: Medium / "12" / "2"  → base 12, cap 2, not shield
    assert parse_armor_stats("Medium", "12", "2") == (12, 2, False)


def test_parse_armor_stats_heavy_cap_zero():
    from app.cli.ingest import parse_armor_stats
    # PHB Plate: Heavy / "18" / "0"  → base 18, cap 0, not shield
    assert parse_armor_stats("Heavy", "18", "0") == (18, 0, False)


def test_parse_armor_stats_shield_from_type():
    from app.cli.ingest import parse_armor_stats
    # PHB Shield: type "Shield" / "2" / "-"  → base 2, cap None, shield
    assert parse_armor_stats("Shield", "2", "-") == (2, None, True)


def test_parse_armor_stats_a5e_shield_plus_prefix():
    from app.cli.ingest import parse_armor_stats
    # A5e shields encode the bonus as "+2"; the parser strips the plus.
    assert parse_armor_stats("Shield", "+2", "-") == (2, None, True)


def test_parse_armor_stats_a5e_light_unlimited():
    from app.cli.ingest import parse_armor_stats
    # A5e light armor says "Unlimited" in the Max Dex column.
    assert parse_armor_stats("Light", "11", "Unlimited") == (11, None, False)


def test_parse_armor_stats_shadowdark_flex_format():
    from app.cli.ingest import parse_armor_stats
    # Shadowdark light armor: "11 + DEX mod" with "-" cap → uncapped.
    assert parse_armor_stats("-", "11 + DEX mod", "-") == (11, None, False)
    # Shadowdark plate is a flat number with no DEX marker — no dex contribution.
    assert parse_armor_stats("-", "15", "-") == (15, 0, False)


@pytest.mark.asyncio
async def test_ingest_armor_populates_ac_numerics(db_session):
    from app.models.char_sheet import GlobalArmor
    csv_content = [
        ["Armor Name", "Armor Type", "Cost", "Armor Class (AC)", "Max Dex",
         "Strength", "Stealth", "Weight", "Notes"],
        ["Leather", "Light", "10 gp", "11", "-", "-", "-", "10 lb.", "-"],
        ["Plate", "Heavy", "1500 gp", "18", "0", "15", "Disadvantage", "65 lb.", "-"],
        ["Shield", "Shield", "10 gp", "2", "-", "-", "-", "6 lb.", "-"],
    ]

    with tempfile.NamedTemporaryFile(mode="w", prefix="armor_", suffix="_phb2014.csv",
                                     delete=False, newline="") as tf:
        writer = csv.writer(tf)
        writer.writerows(csv_content)
        filepath = tf.name

    try:
        await ingest_file(db_session, filepath)

        rows = (await db_session.execute(select(GlobalArmor))).scalars().all()
        by_name = {r.name: r for r in rows}

        assert by_name["Leather"].base_ac == 11
        assert by_name["Leather"].dex_cap is None
        assert by_name["Leather"].is_shield is False

        assert by_name["Plate"].base_ac == 18
        assert by_name["Plate"].dex_cap == 0

        assert by_name["Shield"].is_shield is True
        assert by_name["Shield"].base_ac == 2
    finally:
        os.remove(filepath)

