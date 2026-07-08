"""Unit tests for pure helpers in character_seeding.

These functions are exercised indirectly via create_character /
update_character, but a regression in (e.g.) the proficiency-bucket
heuristic could go unnoticed when the integration tests happen to
seed a class whose grants don't trip the bug. Direct tests pin the
edge cases.
"""

from app.schemas.char_sheet_specific import CharacterClassEntry
from app.schemas.char_sheet_global import SheetStyle
from app.services.character_seeding import (
    _parse_proficiencies,
    _parse_saving_throws,
    default_money,
    prof_bonus_for,
    seed_profs_from_primary,
    seed_saves_from_primary,
)


class TestParseSavingThrows:
    def test_full_attribute_names(self):
        assert _parse_saving_throws("Strength, Constitution") == ["STR", "CON"]

    def test_short_codes(self):
        assert _parse_saving_throws("DEX, INT") == ["DEX", "INT"]

    def test_blank_returns_empty(self):
        assert _parse_saving_throws("") == []
        assert _parse_saving_throws(None) == []
        assert _parse_saving_throws("-") == []
        assert _parse_saving_throws("   ") == []

    def test_unknown_tokens_dropped(self):
        """Garbage in ingest data shouldn't crash seeding."""
        assert _parse_saving_throws("Strength, Wibble, CON") == ["STR", "CON"]

    def test_dedupes_preserving_order(self):
        assert _parse_saving_throws("STR, Strength, CON") == ["STR", "CON"]


class TestParseProficiencies:
    def test_armor_and_shield_route_to_armor_bucket(self):
        result = _parse_proficiencies("Light Armor, Shields, Simple Weapons")
        assert "Light Armor" in result["armor"]
        assert "Shields" in result["armor"]
        assert "Simple Weapons" in result["weapon"]

    def test_blank_returns_empty_buckets(self):
        assert _parse_proficiencies("") == {"weapon": [], "armor": []}
        assert _parse_proficiencies(None) == {"weapon": [], "armor": []}
        assert _parse_proficiencies("-") == {"weapon": [], "armor": []}

    def test_dedupes_within_bucket(self):
        result = _parse_proficiencies("Longswords, Longswords, Light Armor")
        assert result["weapon"] == ["Longswords"]
        assert result["armor"] == ["Light Armor"]


class TestProfBonusFor:
    def test_dnd5e_table(self):
        # 5e PB: L1-4 → 2, L5-8 → 3, L9-12 → 4, L13-16 → 5, L17-20 → 6
        assert prof_bonus_for(1, SheetStyle.DND5E) == 2
        assert prof_bonus_for(4, SheetStyle.DND5E) == 2
        assert prof_bonus_for(5, SheetStyle.DND5E) == 3
        assert prof_bonus_for(12, SheetStyle.DND5E) == 4
        assert prof_bonus_for(20, SheetStyle.DND5E) == 6

    def test_a5e_uses_same_table(self):
        assert prof_bonus_for(7, SheetStyle.A5E) == 3

    def test_shadowdark_always_zero(self):
        assert prof_bonus_for(1, SheetStyle.SHADOWDARK) == 0
        assert prof_bonus_for(20, SheetStyle.SHADOWDARK) == 0

    def test_zero_or_negative_clamps_to_level_1(self):
        """Level should never push PB below the L1 baseline."""
        assert prof_bonus_for(0, SheetStyle.DND5E) == 2
        assert prof_bonus_for(-5, SheetStyle.DND5E) == 2


class TestSeedSavesFromPrimary:
    def test_returns_six_attribute_entries(self):
        classes = [CharacterClassEntry(name="Fighter", level=1, saving_throw_grants=["STR", "CON"])]
        saves = seed_saves_from_primary(classes)
        assert len(saves) == 6
        assert {s["attribute"] for s in saves} == {"STR", "DEX", "CON", "INT", "WIS", "CHA"}

    def test_only_primary_grants_proficiency(self):
        classes = [
            CharacterClassEntry(name="Fighter", level=1, saving_throw_grants=["STR", "CON"]),
            CharacterClassEntry(name="Wizard",  level=1, saving_throw_grants=["INT", "WIS"]),
        ]
        saves = {s["attribute"]: s["proficiency"] for s in seed_saves_from_primary(classes)}
        # Multiclass rule: only first class grants saves.
        assert saves["STR"] == 2
        assert saves["CON"] == 2
        assert saves["INT"] == 0
        assert saves["WIS"] == 0

    def test_empty_classes_returns_zero_proficiencies(self):
        saves = seed_saves_from_primary([])
        assert all(s["proficiency"] == 0 for s in saves)


class TestSeedProfsFromPrimary:
    def test_only_primary_grants_weapons_and_armor(self):
        classes = [
            CharacterClassEntry(
                name="Fighter", level=1,
                proficiency_grants={"weapon": ["Longswords"], "armor": ["Heavy Armor"]},
            ),
            CharacterClassEntry(
                name="Wizard", level=1,
                proficiency_grants={"weapon": ["Daggers"], "armor": []},
            ),
        ]
        out = seed_profs_from_primary(classes)
        assert out == {"weapon": ["Longswords"], "armor": ["Heavy Armor"]}

    def test_empty_classes_returns_empty_buckets(self):
        assert seed_profs_from_primary([]) == {"weapon": [], "armor": []}

    def test_handles_missing_grants(self):
        classes = [CharacterClassEntry(name="Custom", level=1)]
        assert seed_profs_from_primary(classes) == {"weapon": [], "armor": []}


class TestDefaultMoney:
    def test_dnd5e_seeds_five_currencies(self):
        money = default_money(SheetStyle.DND5E)
        assert set(money.keys()) == {"CP", "SP", "EP", "GP", "PP"}
        assert all(v == 0 for v in money.values())

    def test_a5e_seeds_five_currencies(self):
        money = default_money(SheetStyle.A5E)
        assert set(money.keys()) == {"CP", "SP", "EP", "GP", "PP"}

    def test_shadowdark_seeds_only_gp(self):
        assert default_money(SheetStyle.SHADOWDARK) == {"GP": 0}

    def test_um5_seeds_only_dollars(self):
        # Ultramodern5 uses a modern dollar economy, not fantasy coinage.
        assert default_money(SheetStyle.UM5) == {"$": 0}
