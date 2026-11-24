"""Unit tests for Shadowrun: Anarchy 2.0 schema and pure builder."""

import json
from pathlib import Path

from app.builders import get_builder
from app.rule_systems import SheetStyle
from app.schemas.registry import parse_character
from app.schemas.shadowrun_anarchy import (
    AmpEffect,
    AmpType,
    AnarchyArmor,
    AnarchyCharacter,
    AnarchyEquipmentItem,
    AnarchySkill,
    AnarchySpecialization,
    AnarchySpell,
    AnarchyWeapon,
    Metatype,
    ShadowAmp,
    WoundMonitor,
)


def _sample_runner(**overrides) -> AnarchyCharacter:
    base = dict(
        name="Razor",
        metatype=Metatype.ORK,
        strength=3,
        agility=4,
        willpower=2,
        logic=2,
        charisma=3,
        edge_current=3,
        edge_base=3,
        keywords=["Ork", "Seattle", "Street Samurai", "Lone Star", "Low Lifestyle"],
        skills=[
            AnarchySkill(
                name="Athletics",
                category="General",
                rating=3,
                attribute="STR",
                alt_attributes=["AGI"],
                specializations=[AnarchySpecialization(name="ranged defense", attribute="AGI")],
            ),
            AnarchySkill(
                name="Ranged Weapons",
                category="Fighting",
                rating=5,
                attribute="AGI",
                specializations=[AnarchySpecialization(name="rifles", attribute="AGI")],
            ),
            AnarchySkill(
                name="Close Combat",
                category="Fighting",
                rating=3,
                attribute="AGI",
                specializations=[AnarchySpecialization(name="unarmed", attribute="AGI")],
            ),
        ],
        shadow_amps=[
            ShadowAmp(
                name="Cybernetic Eyes",
                amp_type=AmpType.CYBERWARE,
                rating=8,
                essence_cost=1.0,
                effects=[AmpEffect(kind="rr_skill", target="Ranged Weapons", value=1)],
            ),
            ShadowAmp(
                name="Wired Reflexes",
                amp_type=AmpType.CYBERWARE,
                rating=6,
                essence_cost=1.0,
            ),
            ShadowAmp(
                name="Reflex Recorders",
                amp_type=AmpType.BIOWARE,
                rating=4,
                essence_cost=0.5,
                effects=[AmpEffect(kind="rr_spec", target="unarmed", value=1)],
            ),
            ShadowAmp(
                name="Customized Shotgun",
                amp_type=AmpType.EQUIPMENT,
                rating=2,
                essence_cost=0.0,
                effects=[AmpEffect(kind="rr_spec", target="rifles", value=1)],
            ),
        ],
        weapons=[
            AnarchyWeapon(name="Unarmed", weapon_type="Unarmed", dv="STR"),
            AnarchyWeapon(name="Knife", weapon_type="Weapon", dv="STR+1"),
            AnarchyWeapon(name="Shotgun", weapon_type="Weapon", dv="8"),
        ],
        armor=[
            AnarchyArmor(name="Kevlar Vest", rating=3, slot="main"),
            AnarchyArmor(name="Armored Clothes", rating=1, slot="alternate"),
        ],
        equipment=[
            AnarchyEquipmentItem(name="Fake SIN", cost=2500),
        ],
    )
    base.update(overrides)
    return AnarchyCharacter(**base)


def test_builder_dispatch_and_no_phb_toggle():
    c = _sample_runner()
    vd = get_builder(c).build()
    assert vd["system_family"] == "sra2"
    assert vd["style_flags"]["show_phb_toggle"] is False
    assert vd["top_bar"]["metatype"] == "Ork"
    assert vd["top_bar"]["racial_quality"] == "Low-light vision"


def test_essence_and_cumulative_penalties():
    c = _sample_runner()
    vd = get_builder(c).build()
    # 6.0 - (1.0 + 1.0 + 0.5) = 3.5 -> Essence <= 5 (-1 magic) and <= 4 (-1 healing)
    assert vd["essence"]["current"] == 3.5
    assert vd["essence"]["display"] == "3.5"
    assert any("1 hit on magic" in p for p in vd["essence"]["penalties"])
    assert any("1 hit on healing" in p for p in vd["essence"]["penalties"])
    assert vd["essence"]["is_critical"] is False

    # Heavy chrome (5.5 essence lost -> 0.5 remaining -> <=1 social disadvantage + critical)
    heavy = _sample_runner(
        shadow_amps=[
            ShadowAmp(name=f"Chrome {i}", amp_type=AmpType.CYBERWARE, rating=1, essence_cost=1.0)
            for i in range(5)
        ] + [ShadowAmp(name="Bio", amp_type=AmpType.BIOWARE, rating=2, essence_cost=0.5)]
    )
    vd_heavy = get_builder(heavy).build()
    assert vd_heavy["essence"]["current"] == 0.5
    assert vd_heavy["essence"]["is_critical"] is True
    assert any("2 hits on magic" in p for p in vd_heavy["essence"]["penalties"])
    assert any("2 hits on healing" in p for p in vd_heavy["essence"]["penalties"])
    assert any("social Tests" in p for p in vd_heavy["essence"]["penalties"])


def test_skill_dice_pools_and_rr_stacking_cap():
    c = _sample_runner()
    vd = get_builder(c).build()
    by_name = {s["name"]: s for s in vd["skills"]}

    # Athletics: 3 + STR(3) = 6; ranged defense: 3 + 2 + AGI(4) = 9
    assert by_name["Athletics"]["dp"] == 6
    assert by_name["Athletics"]["specializations"][0]["dp"] == 9

    # Ranged Weapons: 5 + AGI(4) = 9, RR=1 (smartlink); rifles: 5 + 2 + 4 = 11, RR=2 (smartlink + stock)
    assert by_name["Ranged Weapons"]["dp"] == 9
    assert by_name["Ranged Weapons"]["rr"] == 1
    assert by_name["Ranged Weapons"]["specializations"][0]["dp"] == 11
    assert by_name["Ranged Weapons"]["specializations"][0]["rr"] == 2

    # Close Combat (unarmed): 3 + 2 + 4 = 9, RR=1
    assert by_name["Close Combat"]["specializations"][0]["dp"] == 9
    assert by_name["Close Combat"]["specializations"][0]["rr"] == 1

    # RR must cap at 3 even if stacked beyond 3
    capped = _sample_runner(
        shadow_amps=[
            ShadowAmp(
                name="Overstacked",
                amp_type=AmpType.CYBERWARE,
                rating=10,
                essence_cost=1.0,
                effects=[
                    AmpEffect(kind="rr_attr", target="AGI", value=2),
                    AmpEffect(kind="rr_skill", target="Ranged Weapons", value=2),
                    AmpEffect(kind="rr_spec", target="rifles", value=2),
                ],
            )
        ]
    )
    rw = next(s for s in get_builder(capped).build()["skills"] if s["name"] == "Ranged Weapons")
    assert rw["rr"] == 3
    assert rw["specializations"][0]["rr"] == 3


def test_wound_thresholds_boxes_and_stim_patch():
    c = _sample_runner(
        shadow_amps=[
            ShadowAmp(
                name="Aluminum Bone Lacing",
                amp_type=AmpType.CYBERWARE,
                rating=5,
                essence_cost=1.0,
                effects=[
                    AmpEffect(kind="light_wound_box", value=1),
                    AmpEffect(kind="unarmed_dv_bonus", value=1),
                ],
            ),
            ShadowAmp(
                name="Dermal Plating",
                amp_type=AmpType.CYBERWARE,
                rating=2,
                essence_cost=1.0,
                effects=[AmpEffect(kind="armor_bonus", value=1)],
            ),
        ],
        wounds=WoundMonitor(light=[True, False], serious=[True], incapacitated=False, stim_patch_active=False),
    )
    vd = get_builder(c).build()
    # +1 light box -> 3 total light boxes, preserving checked state
    assert vd["wounds"]["light_boxes"] == [True, False, False]
    assert vd["wounds"]["status_text"] == "1 Serious"
    assert vd["wounds"]["status_severity"] == "danger"

    # Thresholds with STR=3, amp armor +1, Main armor 3 (total +4), Mental WIL=2
    thr = {row["label"]: row for row in vd["wounds"]["thresholds"]}
    assert thr["No armor (+1 Amp)"]["light"] == 4
    assert thr["Main armor (Kevlar Vest 3)"]["light"] == 7
    assert thr["Main armor (Kevlar Vest 3)"]["serious"] == 10
    assert thr["Main armor (Kevlar Vest 3)"]["incap"] == 13
    assert thr["Mental"]["light"] == 2

    # Unarmed DV evaluates STR(3) + 1 (Aluminum Bone Lacing) = 4; Knife STR+1 = 4
    weapons = {w["name"]: w for w in vd["weapons"]}
    assert weapons["Unarmed"]["dv_computed"] == "4"
    assert weapons["Knife"]["dv_computed"] == "4"
    assert weapons["Shotgun"]["dv_computed"] == "8"

    # Stim patch suppresses serious Disadvantage severity from danger -> warning
    c.wounds.stim_patch_active = True
    vd_stim = get_builder(c).build()
    assert vd_stim["wounds"]["status_severity"] == "warning"
    assert "Stim patch active" in vd_stim["wounds"]["penalty_note"]


def test_nuyen_audit_and_example_kestrel_parses():
    example_path = Path(__file__).resolve().parents[1] / "examples" / "Kestrel (SRA2).json"
    envelope = json.loads(example_path.read_text(encoding="utf-8"))
    style = SheetStyle(envelope["style"])
    parsed = parse_character(style, envelope["character_data"])
    assert isinstance(parsed, AnarchyCharacter)

    vd = get_builder(parsed).build()
    assert vd["essence"]["current"] == 4.0  # 2 cyberware amps (-2.0)
    assert len(vd["wounds"]["light_boxes"]) == 3  # Aluminum Bone Lacing
    assert vd["nuyen_audit"]["total"] > 0
    assert len(vd["risk_table"]) == 4


def test_awakened_flag_and_sustained_spell_count():
    mage = _sample_runner(
        shadow_amps=[ShadowAmp(name="Awakened", amp_type=AmpType.AWAKENED, rating=5)],
        spells=[
            AnarchySpell(name="Invisibility", category="Illusion", duration="S", sustained_active=True),
            AnarchySpell(name="Heal", category="Health", duration="I", sustained_active=False),
        ],
    )
    vd = get_builder(mage).build()
    assert vd["style_flags"]["is_awakened"] is True
    assert vd["sustained_spell_count"] == 1
