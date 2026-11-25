"""Integration tests covering all 6 rule systems' rich JSON catalogs under data/."""

from __future__ import annotations

from pathlib import Path

from app.cli.ingest import run_ingestion_in_session
from app.rule_systems import SheetStyle
from app.services.global_items_service import (
    list_armor,
    list_attributes,
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


async def test_full_data_dir_json_only_ingestion_all_six_systems_and_idempotency(
    db_session, test_user
):
    # Confirm no legacy CSV files remain in data/ — all 6 systems are rich JSON.
    assert list(REPO_DATA_DIR.glob("*.csv")) == []

    report1 = await run_ingestion_in_session(db_session, str(REPO_DATA_DIR))
    assert report1["files"] == 49
    assert report1["inserted"] > 2300

    # Re-running ingestion updates every seeded row in place with zero duplicates.
    report2 = await run_ingestion_in_session(db_session, str(REPO_DATA_DIR))
    assert report2["inserted"] == 0
    assert report2["updated"] == report1["inserted"]

    owner = UserContext.from_user(test_user)

    # --- D&D 5e 2014 (SRD 5.1) ---
    dnd_spells = await list_spells(db_session, SheetStyle.DND5E, owner_id=test_user.id)
    dnd_items = await list_items(db_session, SheetStyle.DND5E, owner_id=test_user.id)
    dnd_armor = await list_armor(db_session, SheetStyle.DND5E, owner_id=test_user.id)
    dnd_presets = await list_ally_presets(db_session, SheetStyle.DND5E, owner)
    assert len(dnd_spells) == 319
    assert len(dnd_items) >= 170
    assert any(a.name == "Plate" and a.base_ac == 18 and a.dex_cap == 0 for a in dnd_armor)
    assert any(p.name == "Mastiff" for p in dnd_presets)
    assert any(p.name == "Owl" for p in dnd_presets)

    # --- Ultramodern5 ---
    um5_attrs = await list_attributes(db_session, SheetStyle.UM5, owner_id=test_user.id)
    um5_spells = await list_spells(db_session, SheetStyle.UM5, owner_id=test_user.id)
    um5_items = await list_items(db_session, SheetStyle.UM5, owner_id=test_user.id)
    um5_presets = await list_ally_presets(db_session, SheetStyle.UM5, owner)
    assert len(um5_attrs) == 7  # Includes Vigor
    assert len(um5_spells) >= 150
    biofort = next(i for i in um5_items if i.name == "Biofort")
    assert "+2 bonus to Constitution" in (biofort.description or "")
    apc = next(i for i in um5_items if i.name == "APC")
    assert extract_item_stat_block(apc)["ally_type"] == "Vehicle"
    assert any(p.name == "XR-0 Bodyguard Android" for p in um5_presets)

    # --- Voidrunner ---
    vr_powers = await list_spells(db_session, SheetStyle.VOIDRUNNER, owner_id=test_user.id)
    vr_maneuvers = await list_combat_maneuvers(db_session, SheetStyle.VOIDRUNNER, owner_id=test_user.id)
    vr_destinies = await list_destinies(db_session, SheetStyle.VOIDRUNNER, owner_id=test_user.id)
    vr_items = await list_items(db_session, SheetStyle.VOIDRUNNER, owner_id=test_user.id)
    vr_presets = await list_ally_presets(db_session, SheetStyle.VOIDRUNNER, owner)
    assert len(vr_powers) >= 70
    assert len(vr_maneuvers) >= 40
    assert len(vr_destinies) == 12
    drone = next(i for i in vr_items if i.name == "Combat drone")
    assert extract_item_stat_block(drone)["ally_type"] == "Drone"
    hover = next(i for i in vr_items if i.name == "Hovercycle")
    assert extract_item_stat_block(hover)["ally_type"] == "Vehicle"
    assert any(p.name == "Construction Robot" for p in vr_presets)

    # --- Shadowdark RPG ---
    sd_classes = await list_classes(db_session, SheetStyle.SHADOWDARK, owner_id=test_user.id)
    sd_weapons = await list_weapons(db_session, SheetStyle.SHADOWDARK, owner_id=test_user.id)
    sd_items = await list_items(db_session, SheetStyle.SHADOWDARK, owner_id=test_user.id)
    sd_presets = await list_ally_presets(db_session, SheetStyle.SHADOWDARK, owner)
    assert len(sd_classes) == 4
    assert len(sd_weapons) == 15
    assert len(sd_items) == 18
    assert all(p.ally_type != "Vehicle" for p in sd_presets)
    torch = next(i for i in sd_items if i.name == "Torch")
    assert "1 hour" in (torch.description or "")
