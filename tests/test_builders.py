"""
AI Helper Docstring
Purpose: Pytest suite running Builder factories against multiple Mock models. Covers style-specific suppression (Shadowdark), AC computation with armor/shield/DEX interactions, archetype display, defense fields, and extra magic resource passthrough.
Interactions:
- Requires testing explicit outputs from `app.builders.*`.
"""

import pytest

from app.schemas.char_sheet_specific import (
    Character, Race, CharacterStat, CharacterProficiency,
    CharacterSkillSimple, CharacterSavingThrowSimple,
    AbilityScore, MagicResource, DarkParams,
)
from app.schemas.char_sheet_global import SheetStyle, MagicType
from app.builders import get_builder
from app.builders.dnd5e import DnD2014Builder
from app.builders.shadowdark import ShadowdarkBuilder
from app.builders.a5e import A5eBuilder
from app.builders.um5 import Um5Builder
from app.builders.voidrunner import VoidrunnerBuilder

def create_mock_character(style: SheetStyle) -> Character:
    return Character(
        owner_id="fake-user-123",
        style=style,
        name="Test",
        race=Race(ancestry="Human", culture=None, lineage=None),
        background="Outlander",
        destiny={"name": "Slay the dragon", "src_inspiration": "Honor", "inspiration_feat": "Brave", "fullfillment": "Dragon Slayer"},
        prof_bonus=2,
        ac=CharacterStat(base=10, misc=0),
        initiative=CharacterStat(base=0, misc=0),
        inspiration=True,
        conditions=[],
        speed=30,
        size="Medium",
        proficiency=CharacterProficiency(
            weapon=[], armor=[], language=[], instrument=[], tool=[], game=[]
        ),
        experience_points=0
    )

def test_builder_factory_returns_correct_instance():
    c_dnd = create_mock_character(SheetStyle.DND5E)
    c_sd = create_mock_character(SheetStyle.SHADOWDARK)
    c_a5e = create_mock_character(SheetStyle.A5E)
    c_um5 = create_mock_character(SheetStyle.UM5)
    c_vr = create_mock_character(SheetStyle.VOIDRUNNER)

    assert isinstance(get_builder(c_dnd), DnD2014Builder)
    assert isinstance(get_builder(c_sd), ShadowdarkBuilder)
    assert isinstance(get_builder(c_a5e), A5eBuilder)
    assert isinstance(get_builder(c_um5), Um5Builder)
    # Voidrunner extends A5e, so its builder is also an A5eBuilder instance.
    assert isinstance(get_builder(c_vr), VoidrunnerBuilder)
    assert isinstance(get_builder(c_vr), A5eBuilder)


@pytest.mark.parametrize("style,expected", [
    (SheetStyle.DND5E, True),
    (SheetStyle.A5E, True),
    (SheetStyle.UM5, True),
    (SheetStyle.VOIDRUNNER, True),   # inherits the 5e-family cap
    (SheetStyle.SHADOWDARK, False),  # no attunement concept
])
def test_show_attunement_style_flag(style, expected):
    vd = get_builder(create_mock_character(style)).build()
    assert vd["style_flags"]["show_attunement"] is expected


@pytest.mark.parametrize("style", [SheetStyle.GENEFUNK, SheetStyle.CARBON])
def test_builder_factory_raises_for_unimplemented_styles(style):
    c = create_mock_character(style)
    with pytest.raises(NotImplementedError):
        get_builder(c)


def test_um5_builder_inherits_dnd_view_model():
    """UM5 shares the vanilla-5e view model: it builds cleanly, drops Destiny,
    uses 'Exhaustion' wording, and suppresses combat maneuvers (all from the
    DnD2014Builder baseline it extends)."""
    c_um5 = create_mock_character(SheetStyle.UM5)
    view_data = get_builder(c_um5).build()

    assert view_data['details']['destiny'] is None
    assert view_data['combat']['exhaustion_label'] == 'Exhaustion'
    assert view_data['combat_maneuvers'] is None


def test_um5_vigor_disabled_hides_seventh_attribute_and_vig_skills():
    """With Vigor off, the builder shows only the six core attributes and hides
    any VIG-keyed skill that happens to linger in the blob."""
    c = create_mock_character(SheetStyle.UM5).model_copy(update={
        "vigor_enabled": False,
        "skills": [
            CharacterSkillSimple(name="Athletics", attribute="STR"),
            CharacterSkillSimple(name="Induce", attribute="VIG"),
        ],
    })
    vd = get_builder(c).build()
    labels = [a["label"] for a in vd["attributes"]]
    assert labels == ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    assert vd["vigor_enabled"] is False
    skill_names = [s["name"] for s in vd["skills"]]
    assert "Athletics" in skill_names
    assert "Induce" not in skill_names  # VIG skill hidden while Vigor is off


def test_um5_vigor_enabled_shows_seventh_attribute_and_vig_skills():
    """With Vigor on, a seventh VIG attribute row (with its save) and the
    VIG-keyed skills appear."""
    c = create_mock_character(SheetStyle.UM5).model_copy(update={
        "vigor_enabled": True,
        "skills": [
            CharacterSkillSimple(name="Athletics", attribute="STR"),
            CharacterSkillSimple(name="Induce", attribute="VIG"),
        ],
        "saving_throws": [CharacterSavingThrowSimple(attribute="VIG", proficiency=2)],
    })
    vd = get_builder(c).build()
    labels = [a["label"] for a in vd["attributes"]]
    assert labels == ["STR", "DEX", "CON", "INT", "WIS", "CHA", "VIG"]
    assert vd["vigor_enabled"] is True
    skill_names = [s["name"] for s in vd["skills"]]
    assert "Induce" in skill_names


def test_um5_dark_resource_derivations():
    """A DARK magic resource derives vessel/river/VR (with misc) and a
    Vigor-based spell DC."""
    c = create_mock_character(SheetStyle.UM5).model_copy(update={
        "vigor_enabled": True,
        "vig_score": AbilityScore(base=16),   # +3 modifier
        "magic_resources": [MagicResource(
            name="Dark", magic_type=MagicType.DARK, attribute="VIG",
            current=[8], maximum=[12],
            dark=DarkParams(vessel_misc=2, river_misc=1, vr_base=2, vr_misc=1),
        )],
    })
    res = get_builder(c).build()["magic"]["resources"][0]
    assert res["magic_type"] == MagicType.DARK.value
    dk = res["dark"]
    assert dk["dark_current"] == 8
    assert dk["vessel_total"] == 14      # 12 base + 2 misc
    assert dk["river_total"] == 4        # +3 Vigor mod + 1 misc
    assert dk["vr_total"] == 3           # 2 base + 1 misc
    # Spell DC = 8 + prof(2) + Vigor mod(3): confirms VIG drives casting.
    assert res["spell_dc_total"] == 13


def test_non_dark_resource_has_no_dark_block():
    c = create_mock_character(SheetStyle.DND5E).model_copy(update={
        "magic_resources": [MagicResource(
            name="Spell Points", magic_type=MagicType.POINTS, attribute="INT",
            current=[5], maximum=[10],
        )],
    })
    res = get_builder(c).build()["magic"]["resources"][0]
    assert "dark" not in res


def test_voidrunner_inherits_a5e_chassis():
    """Voidrunner runs on the full A5e view model: the Strife track shows, combat
    maneuvers are present (not nulled), and the A5e detail suppressions apply."""
    c_vr = create_mock_character(SheetStyle.VOIDRUNNER)
    vd = get_builder(c_vr).build()

    assert vd['combat']['show_strife'] is True
    assert vd['combat_maneuvers'] is not None          # A5e keeps maneuvers
    assert vd['combat']['exhaustion_label'] == 'Fatigue'  # A5e wording, not "Exhaustion"
    assert vd['details']['alignment_suppressed'] is True


def test_voidrunner_psionics_resource_matches_points():
    """A PSIONICS resource derives spell attack/DC exactly like a POINTS pool of the
    same ability + proficiency — the psionics label reuses the Spell-Points math."""
    ability_score = AbilityScore(base=16)  # +3 modifier
    psionics = create_mock_character(SheetStyle.VOIDRUNNER).model_copy(update={
        "int_score": ability_score,
        "magic_resources": [MagicResource(
            name="Psionics", magic_type=MagicType.PSIONICS, attribute="INT",
            current=[5], maximum=[10],
        )],
    })
    points = create_mock_character(SheetStyle.VOIDRUNNER).model_copy(update={
        "int_score": ability_score,
        "magic_resources": [MagicResource(
            name="Points", magic_type=MagicType.POINTS, attribute="INT",
            current=[5], maximum=[10],
        )],
    })
    psi_res = get_builder(psionics).build()["magic"]["resources"][0]
    pts_res = get_builder(points).build()["magic"]["resources"][0]

    assert psi_res["magic_type"] == MagicType.PSIONICS.value
    # DC = 8 + prof(2) + INT mod(3) = 13; attack = prof(2) + INT mod(3) = 5.
    assert psi_res["spell_dc_total"] == 13
    assert psi_res["spell_attack_total"] == 5
    # Same derivation as a POINTS pool, and no DARK-only block.
    assert psi_res["spell_dc_total"] == pts_res["spell_dc_total"]
    assert psi_res["spell_attack_total"] == pts_res["spell_attack_total"]
    assert "dark" not in psi_res

def test_shadowdark_builder_nulls_fields():
    c_sd = create_mock_character(SheetStyle.SHADOWDARK)
    builder = get_builder(c_sd)
    view_data = builder.build()

    # Shadowdark should null out destiny and inspiration
    assert view_data['top_bar']['inspiration'] is None
    assert view_data['details']['destiny'] is None
    # Shadowdark should suppress combat maneuvers
    assert view_data['combat_maneuvers'] is None
    # Style flags disable skill system and proficiency bonus
    assert view_data['style_flags']['has_skills'] is False
    assert view_data['style_flags']['show_prof_bonus'] is False


def test_dnd5e_and_a5e_builders_set_default_style_flags():
    for style in (SheetStyle.DND5E, SheetStyle.A5E):
        view_data = get_builder(create_mock_character(style)).build()
        assert view_data['style_flags']['has_skills'] is True
        assert view_data['style_flags']['show_prof_bonus'] is True

def test_dnd5e_builder_nulls_destiny_and_renames_fatigue():
    c_dnd = create_mock_character(SheetStyle.DND5E)
    builder = get_builder(c_dnd)
    view_data = builder.build()

    assert view_data['details']['destiny'] is None
    assert view_data['combat'].get('fatigue_label') == 'Exhaustion'
    # DnD 5e should suppress combat maneuvers
    assert view_data['combat_maneuvers'] is None

def test_a5e_builder_retains_destiny_and_suppresses_alignments():
    c_a5e = create_mock_character(SheetStyle.A5E)
    builder = get_builder(c_a5e)
    view_data = builder.build()

    # Suppressed options
    assert view_data['details']['alignment_suppressed'] is True
    assert view_data['details']['ideals_suppressed'] is True
    assert view_data['details']['bonds_suppressed'] is True
    assert view_data['details']['flaws_suppressed'] is True
    assert view_data['details']['destiny']['name'] == "Slay the dragon"
    assert view_data['details']['destiny']['src_inspiration'] == "Honor"


def test_top_bar_emits_classes_list_for_multiclass():
    """top_bar.classes should contain one entry per class with level + archetype."""
    from app.schemas.char_sheet_specific import CharacterClassEntry

    c = create_mock_character(SheetStyle.DND5E)
    c.classes = [
        CharacterClassEntry(name="Fighter", level=3, hit_dice="d10"),
        CharacterClassEntry(name="Wizard", level=2, archetype="Evoker", hit_dice="d6"),
    ]
    # Re-trigger the validator to sync character_class/level from classes list
    c = type(c)(**c.model_dump())

    view_data = get_builder(c).build()
    assert view_data['top_bar']['level'] == 5
    assert "Fighter 3" in view_data['top_bar']['character_class']
    assert "Wizard 2" in view_data['top_bar']['character_class']
    emitted = view_data['top_bar']['classes']
    assert len(emitted) == 2
    wiz = next(e for e in emitted if e['name'] == 'Wizard')
    assert wiz['archetype'] == 'Evoker'
    assert wiz['level'] == 2


def test_top_bar_initiative_uses_dex_modifier_plus_misc():
    """Initiative on the top bar = DEX modifier + initiative.misc (base ignored)."""
    from app.schemas.char_sheet_specific import AbilityScore

    # DEX 14 (+2) + misc 2 → +4
    c = create_mock_character(SheetStyle.DND5E)
    c.dex_score = AbilityScore(base=14)
    c.initiative = CharacterStat(base=99, misc=2)  # base must be ignored
    view_data = get_builder(c).build()
    assert view_data['top_bar']['initiative'] == "+4"

    # DEX 8 (-1) + misc 0 → -1
    c2 = create_mock_character(SheetStyle.DND5E)
    c2.dex_score = AbilityScore(base=8)
    c2.initiative = CharacterStat(base=5, misc=0)
    view_data2 = get_builder(c2).build()
    assert view_data2['top_bar']['initiative'] == "-1"


def test_combat_emits_per_class_hit_dice():
    from app.schemas.char_sheet_specific import CharacterClassEntry

    c = create_mock_character(SheetStyle.DND5E)
    c.classes = [
        CharacterClassEntry(name="Fighter", level=3, hit_dice="d10",
                            hit_dice_current=3, hit_dice_max=3),
        CharacterClassEntry(name="Wizard", level=2, hit_dice="d6",
                            hit_dice_current=2, hit_dice_max=2),
    ]
    c = type(c)(**c.model_dump())

    view_data = get_builder(c).build()
    hd = view_data['combat']['hit_dice']
    assert len(hd) == 2
    by_class = {x['class_name']: x for x in hd}
    assert by_class['Fighter']['die'] == 'd10'
    assert by_class['Wizard']['die'] == 'd6'
    assert by_class['Fighter']['current'] == 3
    assert by_class['Wizard']['maximum'] == 2


def test_combat_hit_dice_empty_when_no_die_seeded():
    """Classes without hit_dice (e.g. brand-new custom) are omitted from the HD list."""
    from app.schemas.char_sheet_specific import CharacterClassEntry

    c = create_mock_character(SheetStyle.DND5E)
    c.classes = [CharacterClassEntry(name="Custom", level=1)]  # no hit_dice
    c = type(c)(**c.model_dump())

    view_data = get_builder(c).build()
    assert view_data['combat']['hit_dice'] == []


def test_builder_emits_skill_notes():
    """Skill.notes should round-trip through the builder's view data."""
    from app.schemas.char_sheet_specific import CharacterSkillSimple

    c = create_mock_character(SheetStyle.DND5E)
    c.skills = [
        CharacterSkillSimple(name="Perception", attribute="WIS",
                             notes="Hears whispers in the wind."),
        CharacterSkillSimple(name="Athletics", attribute="STR"),
    ]
    c = type(c)(**c.model_dump())

    view_data = get_builder(c).build()
    by_name = {s['name']: s for s in view_data['skills']}
    assert by_name['Perception']['notes'] == "Hears whispers in the wind."
    assert by_name['Athletics']['notes'] is None


# ---------------------------------------------------------------------------
# Actions card
# ---------------------------------------------------------------------------

def _char_with_str(style, str_total=10, prof=2):
    """Helper: build a character with a specific STR total and prof bonus."""
    from app.schemas.char_sheet_specific import AbilityScore
    c = create_mock_character(style)
    c.prof_bonus = prof
    c.str_score = AbilityScore(base=str_total, racial=0, level=0, misc=0)
    return type(c)(**c.model_dump())


def test_actions_empty_by_default():
    c = create_mock_character(SheetStyle.DND5E)
    view_data = get_builder(c).build()
    assert view_data['actions'] == []


def test_action_attack_bonus_math_proficient_str():
    """STR 18 (mod +4), prof 2, proficient=True, attack_misc=1 → +7 attack."""
    from app.schemas.char_sheet_specific import CharacterAction
    c = _char_with_str(SheetStyle.DND5E, str_total=18, prof=2)
    c.actions = [CharacterAction(
        name="Longsword", attribute="STR", proficient=True,
        attack_misc=1, damage="1d8 slashing",
        show_attack_bonus=True, show_attack_dc=False,
    )]
    c = type(c)(**c.model_dump())

    a = get_builder(c).build()['actions'][0]
    assert a['attack_bonus'] == 7  # 4 + 2 + 1
    assert a['attack_dc'] == 14     # 8 + 4 + 2 + 0 (still computed, hidden)
    assert a['show_attack_bonus'] is True
    assert a['show_attack_dc'] is False


def test_action_attack_dc_math_and_non_proficient():
    """Non-proficient: prof bonus NOT included. DC = 8 + attr_mod + 0 + dc_misc."""
    from app.schemas.char_sheet_specific import CharacterAction
    from app.schemas.char_sheet_specific import AbilityScore
    c = create_mock_character(SheetStyle.DND5E)
    c.prof_bonus = 3
    c.int_score = AbilityScore(base=16)  # +3 mod
    c.actions = [CharacterAction(
        name="Magic Missile", attribute="INT", proficient=False,
        dc_misc=2, show_attack_dc=True,
    )]
    c = type(c)(**c.model_dump())

    a = get_builder(c).build()['actions'][0]
    assert a['attack_bonus'] == 3   # 3 (INT) + 0 (no prof) + 0
    assert a['attack_dc'] == 13      # 8 + 3 + 0 + 2
    assert a['show_attack_dc'] is True


# ---------------------------------------------------------------------------
# Ability tracker
# ---------------------------------------------------------------------------

def test_ability_without_tracker_emits_none():
    from app.schemas.char_sheet_specific import CharacterAbilityEntry
    c = create_mock_character(SheetStyle.DND5E)
    c.abilities = [CharacterAbilityEntry(name="Second Wind", source="Class")]
    c = type(c)(**c.model_dump())
    feat = get_builder(c).build()['features'][0]
    assert feat['tracker'] is None


def test_ability_with_tracker_roundtrips():
    from app.schemas.char_sheet_specific import CharacterAbilityEntry, AbilityTracker
    c = create_mock_character(SheetStyle.DND5E)
    c.abilities = [CharacterAbilityEntry(
        name="Action Surge", source="Class",
        tracker=AbilityTracker(current=1, maximum=1, reset_on="short"),
    )]
    c = type(c)(**c.model_dump())
    feat = get_builder(c).build()['features'][0]
    assert feat['tracker'] == {"name": "", "current": 1, "maximum": 1, "reset_on": "short"}


# ---------------------------------------------------------------------------
# Magic resources
# ---------------------------------------------------------------------------

def test_magic_empty_by_default():
    c = create_mock_character(SheetStyle.DND5E)
    vd = get_builder(c).build()
    assert vd['magic']['resources'] == []
    assert vd['magic']['spells'] == []


def test_magic_resource_attack_and_dc_math_int():
    """INT 16 (+3), prof 3, spell_attack_misc=1, spell_dc_misc=2 → attack +7, DC 16."""
    from app.schemas.char_sheet_specific import MagicResource, AbilityScore
    from app.schemas.char_sheet_global import MagicType

    c = create_mock_character(SheetStyle.DND5E)
    c.prof_bonus = 3
    c.int_score = AbilityScore(base=16)
    c.magic_resources = [MagicResource(
        name="Wizard Slots", attribute="INT", magic_type=MagicType.PERLEVEL,
        spell_attack_misc=1, spell_dc_misc=2,
        current=[4, 2], maximum=[4, 2],
    )]
    c = type(c)(**c.model_dump())

    r = get_builder(c).build()['magic']['resources'][0]
    assert r['spell_attack_total'] == 7   # 3 prof + 3 INT + 1
    assert r['spell_dc_total'] == 16       # 8 + 3 prof + 3 INT + 2
    assert r['attribute'] == "INT"
    assert r['current'] == [4, 2]


def test_magic_resource_no_attribute_flat_casting():
    """attribute=None → attr_mod=0; attack = prof + 0 + misc, DC = 8 + prof + 0 + misc."""
    from app.schemas.char_sheet_specific import MagicResource
    from app.schemas.char_sheet_global import MagicType

    c = create_mock_character(SheetStyle.DND5E)
    c.prof_bonus = 2
    c.magic_resources = [MagicResource(
        name="Innate", attribute=None, magic_type=MagicType.POINTS,
        spell_attack_misc=3,
    )]
    c = type(c)(**c.model_dump())

    r = get_builder(c).build()['magic']['resources'][0]
    assert r['spell_attack_total'] == 5  # 2 + 0 + 3
    assert r['spell_dc_total'] == 10     # 8 + 2 + 0 + 0


def test_magic_spells_roundtrip():
    from app.schemas.char_sheet_specific import CharacterSpell
    c = create_mock_character(SheetStyle.DND5E)
    c.spells = [CharacterSpell(
        name="Fireball", level=3, resource_name="Wizard Slots",
        casting_time="1 action", spell_range="150 feet",
        duration="Instantaneous", ritual=False, concentration=False,
    )]
    c = type(c)(**c.model_dump())
    spells = get_builder(c).build()['magic']['spells']
    assert len(spells) == 1
    assert spells[0]['name'] == "Fireball"
    assert spells[0]['level'] == 3
    assert spells[0]['casting_time'] == "1 action"
    assert spells[0]['spell_range'] == "150 feet"
    assert spells[0]['duration'] == "Instantaneous"
    assert spells[0]['ritual'] is False
    assert spells[0]['concentration'] is False


# ---------------------------------------------------------------------------
# Combat maneuvers suppression
# ---------------------------------------------------------------------------

def test_combat_maneuvers_emitted_for_a5e():
    from app.schemas.char_sheet_specific import CharacterCombatManeuver
    c = create_mock_character(SheetStyle.A5E)
    c.combat_maneuvers = [CharacterCombatManeuver(
        name="Rushing Strike", tradition="Tempest", degree=2, exertion_cost=1,
        action_type="A", stance=False,
    )]
    c.known_traditions = "Tempest, Mirror's Glint"
    c.exertion_max = 5
    c.exertion_current = 3
    c.maneuvers_known = 4
    c.max_degree = 3
    c = type(c)(**c.model_dump())
    vd = get_builder(c).build()
    cm = vd['combat_maneuvers']
    assert cm is not None
    assert cm['maneuvers'][0]['name'] == "Rushing Strike"
    assert cm['maneuvers'][0]['degree'] == 2
    assert cm['known_traditions'] == "Tempest, Mirror's Glint"
    assert cm['exertion_current'] == 3
    assert cm['exertion_max'] == 5
    assert cm['maneuvers_known'] == 4
    assert cm['max_degree'] == 3


def test_combat_maneuver_dc_and_attack():
    from app.schemas.char_sheet_specific import CharacterCombatManeuver, AbilityScore
    c = create_mock_character(SheetStyle.A5E)
    c.prof_bonus = 3
    c.str_score = AbilityScore(base=16)  # +3
    c.dex_score = AbilityScore(base=14)  # +2
    c.maneuver_attack_misc = 1
    c.maneuver_dc_misc = 2
    c = type(c)(**c.model_dump())
    cm = get_builder(c).build()['combat_maneuvers']
    # max(STR+3, DEX+2) = 3; attack = 3 prof + 3 + 1 misc = 7
    assert cm['maneuver_attack'] == 7
    # dc = 8 + 3 prof + 3 + 2 misc = 16
    assert cm['maneuver_dc'] == 16


def test_combat_maneuvers_none_for_dnd5e():
    c = create_mock_character(SheetStyle.DND5E)
    vd = get_builder(c).build()
    assert vd['combat_maneuvers'] is None


def test_combat_maneuvers_none_for_shadowdark():
    c = create_mock_character(SheetStyle.SHADOWDARK)
    vd = get_builder(c).build()
    assert vd['combat_maneuvers'] is None


def test_action_no_attribute_zero_mod():
    """attribute=None falls back to zero attr_mod."""
    from app.schemas.char_sheet_specific import CharacterAction
    c = create_mock_character(SheetStyle.DND5E)
    c.prof_bonus = 2
    c.actions = [CharacterAction(
        name="Generic", attribute=None, proficient=True,
        attack_misc=5,
    )]
    c = type(c)(**c.model_dump())

    a = get_builder(c).build()['actions'][0]
    assert a['attack_bonus'] == 7  # 0 + 2 + 5
    assert a['attack_dc'] == 10    # 8 + 0 + 2 + 0


# ---------------------------------------------------------------------------
# Phase 1: top bar & details
# ---------------------------------------------------------------------------

def test_top_bar_drops_background():
    """Background was cluttering the top-bar subtitle; now lives only on the Description card."""
    c = create_mock_character(SheetStyle.DND5E)
    top = get_builder(c).build()['top_bar']
    assert 'background' not in top


def test_top_bar_single_class_with_archetype():
    from app.schemas.char_sheet_specific import CharacterClassEntry
    c = create_mock_character(SheetStyle.DND5E)
    c.classes = [CharacterClassEntry(name="Fighter", level=5, archetype="Champion")]
    c = type(c)(**c.model_dump())
    top = get_builder(c).build()['top_bar']
    assert top['character_class'] == "Fighter (Champion)"


def test_top_bar_multiclass_with_archetypes():
    from app.schemas.char_sheet_specific import CharacterClassEntry
    c = create_mock_character(SheetStyle.DND5E)
    c.classes = [
        CharacterClassEntry(name="Fighter", level=3, archetype="Champion"),
        CharacterClassEntry(name="Wizard", level=2, archetype="Evoker"),
    ]
    c = type(c)(**c.model_dump())
    top = get_builder(c).build()['top_bar']
    assert top['character_class'] == "Fighter 3 (Champion) / Wizard 2 (Evoker)"


def test_top_bar_multiclass_mixed_archetype():
    """Some classes may lack an archetype — only the ones that have it get a paren."""
    from app.schemas.char_sheet_specific import CharacterClassEntry
    c = create_mock_character(SheetStyle.DND5E)
    c.classes = [
        CharacterClassEntry(name="Fighter", level=3),
        CharacterClassEntry(name="Wizard", level=2, archetype="Evoker"),
    ]
    c = type(c)(**c.model_dump())
    top = get_builder(c).build()['top_bar']
    assert top['character_class'] == "Fighter 3 / Wizard 2 (Evoker)"


def test_details_emits_roleplay_fields():
    c = create_mock_character(SheetStyle.DND5E)
    c.personality = "Calm under pressure."
    c.ideals = "Honor."
    c.bonds = "My hometown."
    c.flaws = "Quick to anger."
    c.appearance = "Tall, auburn hair."
    c.backstory = "Raised in the mountains."
    c = type(c)(**c.model_dump())
    details = get_builder(c).build()['details']
    assert details['personality'] == "Calm under pressure."
    assert details['ideals'] == "Honor."
    assert details['bonds'] == "My hometown."
    assert details['flaws'] == "Quick to anger."
    assert details['appearance'] == "Tall, auburn hair."
    assert details['backstory'] == "Raised in the mountains."


def test_a5e_suppresses_ideals_bonds_flaws_but_not_personality():
    """A5e still emits the field values — the suppression flags are what hides them in UI."""
    c = create_mock_character(SheetStyle.A5E)
    details = get_builder(c).build()['details']
    assert details['ideals_suppressed'] is True
    assert details['bonds_suppressed'] is True
    assert details['flaws_suppressed'] is True
    # personality/appearance/backstory are not suppressed
    assert 'personality_suppressed' not in details


# ---------------------------------------------------------------------------
# Phase 4: AC computation from equipped armor & shields
# ---------------------------------------------------------------------------

def _make_ac_character(dex_total: int, ac_base: int = 10, ac_misc: int = 0,
                      inventory=None) -> Character:
    """Factory focused on AC math — pinpoints DEX + inventory, leaves the rest default."""
    from app.schemas.char_sheet_specific import AbilityScore, InventoryItem

    c = create_mock_character(SheetStyle.DND5E)
    c.dex_score = AbilityScore(base=dex_total, racial=0, level=0, misc=0)
    c.ac = CharacterStat(base=ac_base, misc=ac_misc)
    c.inventory = inventory or []
    return c


def test_ac_no_armor_adds_full_dex():
    from app.builders.base import _compute_ac

    c = _make_ac_character(dex_total=14)  # +2 DEX
    bd = _compute_ac(c)
    assert bd["total"] == 10 + 2  # c.ac.base + dex
    assert bd["armor_locked"] is False
    assert bd["shield"] == 0


def test_ac_light_armor_uncapped_dex():
    from app.schemas.char_sheet_specific import InventoryItem
    from app.builders.base import _compute_ac

    leather = InventoryItem(
        item_type="armor", name="Leather", equipped=True,
        base_ac=11, dex_cap=None, is_shield=False,
    )
    c = _make_ac_character(dex_total=16, inventory=[leather])  # +3 DEX
    bd = _compute_ac(c)
    assert bd["total"] == 11 + 3
    assert bd["base"] == 11
    assert bd["dex"] == 3
    assert bd["armor_locked"] is True


def test_ac_heavy_armor_caps_dex_to_zero():
    from app.schemas.char_sheet_specific import InventoryItem
    from app.builders.base import _compute_ac

    plate = InventoryItem(
        item_type="armor", name="Plate", equipped=True,
        base_ac=18, dex_cap=0, is_shield=False,
    )
    c = _make_ac_character(dex_total=18, inventory=[plate])  # +4 DEX — but cap is 0
    bd = _compute_ac(c)
    assert bd["total"] == 18
    assert bd["dex"] == 0


def test_ac_medium_armor_caps_dex_to_two():
    from app.schemas.char_sheet_specific import InventoryItem
    from app.builders.base import _compute_ac

    scale = InventoryItem(
        item_type="armor", name="Scale Mail", equipped=True,
        base_ac=14, dex_cap=2, is_shield=False,
    )
    c = _make_ac_character(dex_total=18, inventory=[scale])  # +4 DEX capped at 2
    assert _compute_ac(c)["total"] == 14 + 2


def test_ac_shield_stacks_on_top_of_armor():
    from app.schemas.char_sheet_specific import InventoryItem
    from app.builders.base import _compute_ac

    leather = InventoryItem(
        item_type="armor", name="Leather", equipped=True,
        base_ac=11, dex_cap=None, is_shield=False,
    )
    shield = InventoryItem(
        item_type="armor", name="Shield", equipped=True,
        base_ac=2, dex_cap=None, is_shield=True,
    )
    c = _make_ac_character(dex_total=14, inventory=[leather, shield])  # +2
    bd = _compute_ac(c)
    assert bd["total"] == 11 + 2 + 2
    assert bd["shield"] == 2


def test_ac_unequipped_armor_is_ignored():
    from app.schemas.char_sheet_specific import InventoryItem
    from app.builders.base import _compute_ac

    # Armor in inventory but not worn — must not drive AC.
    leather = InventoryItem(
        item_type="armor", name="Leather", equipped=False,
        base_ac=11, dex_cap=None, is_shield=False,
    )
    c = _make_ac_character(dex_total=14, ac_base=12, inventory=[leather])
    assert _compute_ac(c)["total"] == 12 + 2
    assert _compute_ac(c)["armor_locked"] is False


def test_ac_misc_adds_to_total_when_armored():
    from app.schemas.char_sheet_specific import InventoryItem
    from app.builders.base import _compute_ac

    leather = InventoryItem(
        item_type="armor", name="Leather", equipped=True,
        base_ac=11, dex_cap=None, is_shield=False,
    )
    c = _make_ac_character(dex_total=12, ac_misc=1, inventory=[leather])  # +1 DEX
    assert _compute_ac(c)["total"] == 11 + 1 + 1


def test_top_bar_ac_uses_computed_total():
    """build_top_bar's ac chip reflects equipped-armor math, not just c.ac.base + misc."""
    from app.schemas.char_sheet_specific import InventoryItem

    plate = InventoryItem(
        item_type="armor", name="Plate", equipped=True,
        base_ac=18, dex_cap=0, is_shield=False,
    )
    c = _make_ac_character(dex_total=18, ac_base=10, ac_misc=0, inventory=[plate])
    vd = get_builder(c).build()
    assert vd['top_bar']['ac'] == 18
    assert vd['ac_breakdown']['armor_locked'] is True


def test_combat_emits_defense_fields():
    c = create_mock_character(SheetStyle.DND5E)
    c.resistances = "Fire, Cold"
    c.immunities = "Poison"
    c.vulnerabilities = "Radiant"
    vd = get_builder(c).build()
    assert vd['combat']['resistances'] == "Fire, Cold"
    assert vd['combat']['immunities'] == "Poison"
    assert vd['combat']['vulnerabilities'] == "Radiant"


def test_combat_defense_fields_default_empty():
    c = create_mock_character(SheetStyle.DND5E)
    vd = get_builder(c).build()
    assert vd['combat']['resistances'] == ""
    assert vd['combat']['immunities'] == ""
    assert vd['combat']['vulnerabilities'] == ""


def test_magic_extra_resource_passthrough():
    from app.schemas.char_sheet_specific import MagicResource, ExtraResource
    from app.schemas.char_sheet_global import MagicType

    c = create_mock_character(SheetStyle.DND5E)
    c.magic_resources = [
        MagicResource(
            name="Sorcerer Slots",
            magic_type=MagicType.PERLEVEL,
            attribute="CHA",
            current=[4, 3],
            maximum=[4, 3],
            extra_resource=ExtraResource(name="Sorcery Points", current=3, maximum=5, reset_on="long"),
        )
    ]
    vd = get_builder(c).build()
    er = vd['magic']['resources'][0]['extra_resource']
    assert er is not None
    assert er['name'] == "Sorcery Points"
    assert er['current'] == 3
    assert er['maximum'] == 5
    assert er['reset_on'] == "long"


def test_magic_extra_resource_none_when_absent():
    from app.schemas.char_sheet_specific import MagicResource
    from app.schemas.char_sheet_global import MagicType

    c = create_mock_character(SheetStyle.DND5E)
    c.magic_resources = [
        MagicResource(name="Wizard Slots", magic_type=MagicType.PERLEVEL, attribute="INT", current=[4], maximum=[4])
    ]
    vd = get_builder(c).build()
    assert vd['magic']['resources'][0]['extra_resource'] is None


def test_details_emits_description_fields():
    c = create_mock_character(SheetStyle.DND5E)
    c.age = "142"
    c.gender = "Male"
    c.height = "4'2\""
    c.weight = "150 lbs"
    c.eyes = "Brown"
    c.hair = "Black"
    c.skin = "Tan"
    c.alignment = "Chaotic Good"
    c.title = "Lord"
    c.deity = "Moradin"
    vd = get_builder(c).build()
    d = vd['details']
    assert d['age'] == "142"
    assert d['gender'] == "Male"
    assert d['height'] == "4'2\""
    assert d['weight'] == "150 lbs"
    assert d['eyes'] == "Brown"
    assert d['hair'] == "Black"
    assert d['skin'] == "Tan"
    assert d['alignment'] == "Chaotic Good"
    assert d['title'] == "Lord"
    assert d['deity'] == "Moradin"


def test_details_description_fields_default_empty():
    c = create_mock_character(SheetStyle.DND5E)
    vd = get_builder(c).build()
    d = vd['details']
    for key in ('age', 'gender', 'height', 'weight', 'eyes', 'hair', 'skin', 'alignment', 'title', 'deity'):
        assert d[key] == ""


# ---------------------------------------------------------------------------
# Extended-view descriptions: notes/description reach the cards via view-model
# ---------------------------------------------------------------------------

def test_inventory_notes_roundtrip():
    """InventoryItem.notes (the equipment markdown description) must survive the builder."""
    from app.schemas.char_sheet_specific import InventoryItem

    c = create_mock_character(SheetStyle.DND5E)
    c.inventory = [
        InventoryItem(item_type="weapon", name="Dagger",
                      notes="A **wicked** blade.\n\n- keen edge"),
        InventoryItem(item_type="item", name="Torch"),  # no note
    ]
    c = type(c)(**c.model_dump())

    inv = get_builder(c).build()['inventory']
    by_name = {i['name']: i for i in inv}
    assert by_name['Dagger']['notes'] == "A **wicked** blade.\n\n- keen edge"
    assert by_name['Torch']['notes'] == ""


def test_magic_spell_description_roundtrips():
    """CharacterSpell.description must survive the builder for the extended view."""
    from app.schemas.char_sheet_specific import CharacterSpell

    c = create_mock_character(SheetStyle.DND5E)
    c.spells = [CharacterSpell(name="Bless", level=1,
                               description="Up to **three** creatures gain +1d4.")]
    c = type(c)(**c.model_dump())

    spells = get_builder(c).build()['magic']['spells']
    assert spells[0]['description'] == "Up to **three** creatures gain +1d4."


def test_combat_maneuver_description_roundtrips():
    """CharacterCombatManeuver.description must survive the builder for the extended view."""
    from app.schemas.char_sheet_specific import CharacterCombatManeuver

    c = create_mock_character(SheetStyle.A5E)
    c.combat_maneuvers = [CharacterCombatManeuver(
        name="Rushing Strike", tradition="Tempest", degree=2,
        description="Move up to your speed, then *strike*.",
    )]
    c = type(c)(**c.model_dump())

    cm = get_builder(c).build()['combat_maneuvers']
    assert cm['maneuvers'][0]['description'] == "Move up to your speed, then *strike*."

