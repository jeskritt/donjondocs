"""Unit and integration tests for cross-system Stat Block Seeding & Library Picker."""

from __future__ import annotations

import json
from pathlib import Path

from app.cli.ingest import run_ingestion_in_session
from app.models.char_sheet import GlobalItem
from app.models.user import User, UserRole
from app.rule_systems import SheetStyle
from app.schemas.creature import CreatureCreate
from app.security import hash_password
from app.services.ally_service import list_allies
from app.services.character_service import import_character
from app.services.creature_service import create_creature
from app.services.global_items_service import list_abilities, list_items
from app.services.stat_block_library import (
    extract_ability_stat_block,
    extract_item_stat_block,
    list_ally_presets,
)
from app.user_context import UserContext

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_DATA_DIR = REPO_ROOT / "data"


async def test_extract_ability_stat_block_cyberdeck_vs_vehicle_vs_ally_only(db_session, test_user):
    await run_ingestion_in_session(db_session, str(REPO_DATA_DIR / "sra2"))
    abilities = await list_abilities(
        db_session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_id=test_user.id
    )
    by_name = {a.name: a for a in abilities}

    # Cyberdecks stay inline on Shadow Amps (no Allies stat block).
    deck = extract_ability_stat_block(by_name["MCT 360 (Cyberdeck)"])
    assert deck["amp_type"] == "Cyberdeck"
    assert deck["ally_type"] is None
    assert deck["stat_block_md"] == ""
    assert deck["stat_block_only"] is False
    assert "Matrix Damage Monitor:" in deck["summary"]

    # Vehicles and Drones keep a concise summary inline and seed Allies & Stat Blocks.
    bike = extract_ability_stat_block(by_name["Harley-Davidson Centaur (Vehicle)"])
    assert bike["amp_type"] == "Vehicle or Drone"
    assert bike["ally_type"] == "Vehicle"
    assert bike["stat_block_only"] is False
    assert "Pilot" in bike["stat_block_md"]
    assert "Combat Bike" in bike["summary"]

    drone = extract_ability_stat_block(by_name["MCT Gnat (Flying Microdrone)"])
    assert drone["ally_type"] == "Drone"
    assert drone["stat_block_only"] is False
    assert "Pilot" in drone["stat_block_md"]

    # Allies-only catalog entries (Spirits / NPC Threats) are hidden from Add Amp.
    spirit = extract_ability_stat_block(by_name["Spirit of Fire"])
    assert spirit["stat_block_only"] is True
    assert spirit["ally_type"] == "Spirit"
    assert "Spirit" in spirit["stat_block_md"]


async def test_extract_item_stat_block_json_and_legacy_csv(db_session, test_user):
    # Structured JSON item (future Stage 2/3 catalog format).
    json_item = GlobalItem(
        name="Riding Horse",
        type="Mount",
        value="75 gp",
        weight="-",
        effects=json.dumps({
            "summary": "Large beast, speed 60 ft.",
            "ally_type": "Companion",
            "stat_block_md": "> ## Riding Horse\n> *Large beast*",
        }),
        description="A trained riding horse.",
        source=SheetStyle.A5E.value,
    )
    info = extract_item_stat_block(json_item)
    assert info["summary"] == "Large beast, speed 60 ft."
    assert info["description"] == "A trained riding horse."
    assert info["ally_type"] == "Companion"
    assert "## Riding Horse" in info["stat_block_md"]

    # Regular gear item with rich Markdown description stays inline (no Ally seed).
    kit_item = GlobalItem(
        name="Poisoner's Kit",
        type="Tool",
        value="50 gp",
        weight="2 lb.",
        effects="Craft & apply poisons",
        description="### Poisoner's Kit\nIncludes vials, mortar, and reagents.",
        source=SheetStyle.A5E.value,
    )
    kit_info = extract_item_stat_block(kit_item)
    assert kit_info["ally_type"] is None
    assert kit_info["stat_block_md"] == ""
    assert "### Poisoner's Kit" in kit_info["description"]

    # Legacy CSV UM5 vehicle item synthesizes a starter Markdown stat block.
    await run_ingestion_in_session(db_session, str(REPO_DATA_DIR))
    um5_items = await list_items(db_session, SheetStyle.UM5, owner_id=test_user.id)
    um5_vehicles = [i for i in um5_items if (i.type or "").lower() == "vehicle"]
    assert um5_vehicles
    veh_info = extract_item_stat_block(um5_vehicles[0])
    assert veh_info["ally_type"] == "Vehicle"
    assert f"## {um5_vehicles[0].name}" in veh_info["stat_block_md"]


async def test_list_ally_presets_combines_library_and_creatures_and_respects_visibility(
    db_session, test_user
):
    await run_ingestion_in_session(db_session, str(REPO_DATA_DIR))

    other_user = User(
        username="other_gm",
        email="other_gm@example.com",
        hashed_password=hash_password("TestPass123!"),
        role=UserRole.STANDARD,
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    owner_ctx = UserContext.from_user(test_user)
    other_ctx = UserContext.from_user(other_user)

    await create_creature(
        db_session,
        owner_ctx,
        CreatureCreate(name="Freki the Mastiff", creature_type="Beast", body_md="**AC** 12", is_public=False),
    )
    await create_creature(
        db_session,
        other_ctx,
        CreatureCreate(name="Public Warhorse", creature_type="Beast", body_md="**AC** 11", is_public=True),
    )
    await create_creature(
        db_session,
        other_ctx,
        CreatureCreate(name="Secret Boss", creature_type="Monstrosity", body_md="**AC** 20", is_public=False),
    )
    await create_creature(
        db_session,
        other_ctx,
        CreatureCreate(name="Airship Skiff", creature_type="Vehicle", body_md="**AC** 15", is_public=True),
    )

    # Shadowrun: Anarchy 2.0 gets Spirits/Vehicles/Drones/Contacts + visible Creatures (no Cyberdecks, no private other).
    sra2_presets = await list_ally_presets(db_session, SheetStyle.SHADOWRUN_ANARCHY_2, owner_ctx)
    sra2_names = {p.name for p in sra2_presets}
    assert "Harley-Davidson Centaur (Vehicle)" in sra2_names
    assert "Spirit of Fire" in sra2_names
    assert "Freki the Mastiff" in sra2_names
    assert "Public Warhorse" in sra2_names
    assert "Secret Boss" not in sra2_names
    assert "MCT 360 (Cyberdeck)" not in sra2_names

    # Ultramodern5 gets legacy CSV Vehicles + visible Creatures.
    um5_presets = await list_ally_presets(db_session, SheetStyle.UM5, owner_ctx)
    assert any(p.source_group == "Library" and p.ally_type == "Vehicle" for p in um5_presets)
    assert any(p.source_group == "Creature Catalog" and p.name == "Freki the Mastiff" for p in um5_presets)

    # Shadowdark skips all Vehicle presets (including public Vehicle creatures).
    sd_presets = await list_ally_presets(db_session, SheetStyle.SHADOWDARK, owner_ctx)
    sd_names = {p.name for p in sd_presets}
    assert "Freki the Mastiff" in sd_names
    assert "Airship Skiff" not in sd_names
    assert all(p.ally_type != "Vehicle" for p in sd_presets)


async def test_kestrel_example_imports_with_linked_motorcycle_ally(db_session, test_user):
    owner_ctx = UserContext.from_user(test_user)
    kestrel_path = REPO_ROOT / "examples" / "Kestrel (SRA2).json"
    envelope = json.loads(kestrel_path.read_text(encoding="utf-8"))

    rec = await import_character(
        db_session,
        name=envelope["name"],
        style=SheetStyle(envelope["style"]),
        character_data=envelope["character_data"],
        current_user=owner_ctx,
        version=envelope["version"],
        allies=envelope.get("allies"),
        notes=envelope.get("notes"),
    )
    allies = await list_allies(db_session, rec.id, owner_ctx)
    assert len(allies) == 1
    bike_ally = allies[0]
    assert bike_ally.name == "Harley-Davidson Centaur"
    assert bike_ally.ally_type == "Vehicle"
    assert "Damage Thresholds:" in bike_ally.body_md

    amps_by_id = {a["id"]: a for a in rec.character_data["shadow_amps"]}
    # Motorcycle Amp automatically relinked to the freshly generated Ally UUID.
    assert amps_by_id["amp-bike"]["ally_id"] == bike_ally.id
    # Cyberdeck stays inline on Shadow Amps with no Ally link.
    assert amps_by_id["amp-deck"].get("ally_id") is None
    assert "Matrix Damage Monitor:" in amps_by_id["amp-deck"]["body_md"]
