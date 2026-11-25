"""Integration tests for Level Up: Advanced 5e rich JSON catalogs."""

from __future__ import annotations

from pathlib import Path

from app.cli.ingest import run_ingestion_in_session
from app.rule_systems import SheetStyle
from app.services.global_items_service import (
    list_armor,
    list_classes,
    list_combat_maneuvers,
    list_destinies,
    list_items,
    list_skills,
    list_spells,
    list_weapons,
)
from app.services.stat_block_library import extract_item_stat_block, list_ally_presets
from app.user_context import UserContext

REPO_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


async def test_ingest_a5e_json_catalogs_is_idempotent_and_complete(db_session, test_user):
    report1 = await run_ingestion_in_session(db_session, str(REPO_DATA_DIR / "a5e"))
    assert report1["files"] == 10
    assert report1["inserted"] > 900

    # Second run updates in place with zero duplicates.
    report2 = await run_ingestion_in_session(db_session, str(REPO_DATA_DIR / "a5e"))
    assert report2["inserted"] == 0
    assert report2["updated"] == report1["inserted"]

    skills = await list_skills(db_session, SheetStyle.A5E, owner_id=test_user.id)
    classes = await list_classes(db_session, SheetStyle.A5E, owner_id=test_user.id)
    destinies = await list_destinies(db_session, SheetStyle.A5E, owner_id=test_user.id)
    weapons = await list_weapons(db_session, SheetStyle.A5E, owner_id=test_user.id)
    armor = await list_armor(db_session, SheetStyle.A5E, owner_id=test_user.id)
    items = await list_items(db_session, SheetStyle.A5E, owner_id=test_user.id)
    maneuvers = await list_combat_maneuvers(db_session, SheetStyle.A5E, owner_id=test_user.id)
    spells = await list_spells(db_session, SheetStyle.A5E, owner_id=test_user.id)

    assert len(skills) == 20
    assert len(classes) == 14
    assert len(destinies) == 10
    assert len(weapons) == 61
    assert len(armor) == 22
    assert len(items) >= 200
    assert len(maneuvers) >= 160
    assert len(spells) >= 360

    # Armor numeric breakdown is parsed cleanly from JSON `max_dex`.
    plate = next(a for a in armor if a.name == "Full plate (steel)")
    assert plate.base_ac == 18
    assert plate.dex_cap == 0
    assert plate.is_shield is False
    assert "Low-Maintenance" in (plate.description or "")

    tower = next(a for a in armor if a.name == "Tower Shield")
    assert tower.is_shield is True
    assert tower.base_ac == 2

    # Destinies populate inspiration/fulfillment fields.
    chaos = next(d for d in destinies if d.name == "Chaos")
    assert chaos.src_inspiration
    assert chaos.inspiration_feat
    assert chaos.fullfillment

    # Gear: Poisoner's kit stays inline with rich rules; Mastiff & Cloud galleon seed Allies.
    items_by_name = {i.name: i for i in items}
    pk_info = extract_item_stat_block(items_by_name["Poisoner's kit"])
    assert pk_info["ally_type"] is None
    assert "harvest poisons" in pk_info["description"].lower()

    mastiff_info = extract_item_stat_block(items_by_name["Mastiff"])
    assert mastiff_info["ally_type"] == "Companion"
    assert "## Mastiff" in mastiff_info["stat_block_md"]

    galleon_info = extract_item_stat_block(items_by_name["Cloud galleon"])
    assert galleon_info["ally_type"] == "Vehicle"
    assert "## Cloud galleon" in galleon_info["stat_block_md"]

    # Allies Library exposes Beasts/Familiars, Mounts, and Vehicles for A5e.
    owner = UserContext.from_user(test_user)
    presets = await list_ally_presets(db_session, SheetStyle.A5E, owner)
    preset_names = {p.name for p in presets}
    assert "Mastiff" in preset_names
    assert "Owl" in preset_names
    assert "Brown Bear" in preset_names
    assert "Cloud galleon" in preset_names

    # Spot-check Combat Maneuver and Spell metadata.
    cyb = next(m for m in maneuvers if m.name == "Catch Your Breath")
    assert cyb.tradition == "Adamant Mountain"
    assert cyb.tier == "1"
    assert cyb.exertion == "2"

    fireball = next(s for s in spells if s.name == "Fireball")
    assert fireball.level == "3"
    assert fireball.school == "Evocation"
    assert fireball.casting_time == "1 action"
