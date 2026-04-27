"""Direct tests for character_io: migration chain + filename sanitizer.

These exercise the pure helpers in isolation. The end-to-end import
path is also covered via TestExportImport in test_character_service.py,
but those tests can't catch a regression in `migrate_character_data`'s
chain logic that happens to round-trip cleanly through the current
EXPORT_VERSION. These can.
"""

import pytest

from app.services import character_io
from app.services._errors import CharacterServiceError
from app.services.character_io import (
    EXPORT_VERSION,
    _migrate_v3_to_v4,
    export_filename_for,
    migrate_character_data,
)


class TestMigrateCharacterData:
    def test_noop_when_already_at_target(self):
        data = {"name": "X", "currency": {"GP": 1}}
        out = migrate_character_data(data, EXPORT_VERSION)
        assert out == data

    def test_runs_single_v3_to_v4_step(self):
        data = {"equipment": {"money": {"GP": 5}}}
        out = migrate_character_data(data, 3)
        assert out["currency"] == {"GP": 5}
        assert "equipment" not in out

    def test_rejects_version_newer_than_supported(self):
        with pytest.raises(CharacterServiceError, match="newer than supported"):
            migrate_character_data({}, EXPORT_VERSION + 1)

    def test_raises_on_missing_migrator(self, monkeypatch):
        """If a chain hop has no registered migrator, refuse the import.

        Strip the v3 migrator so v3→v4 has nothing to call. Without
        this guard, old data would silently land in a half-migrated
        state.
        """
        monkeypatch.setattr(character_io, "_MIGRATIONS", {})
        with pytest.raises(CharacterServiceError, match="No migration available"):
            migrate_character_data({}, 3)

    def test_walks_multi_step_chain(self, monkeypatch):
        """Hand-roll a 1→2→3→…→EXPORT_VERSION chain and verify each hop fires once."""
        called = []

        def step(n):
            def _m(data):
                called.append(n)
                return data
            return _m

        chain = {n: step(n) for n in range(1, character_io.EXPORT_VERSION)}
        monkeypatch.setattr(character_io, "_MIGRATIONS", chain)
        migrate_character_data({}, 1)
        assert called == list(range(1, character_io.EXPORT_VERSION))


class TestMigrateV3ToV4:
    """Pin the I2 migrator behaviour directly (also covered indirectly
    via test_v3_envelope_currency_migrates_from_equipment).
    """

    def test_hoists_equipment_money_to_currency(self):
        data = {"name": "X", "equipment": {"money": {"GP": 42, "SP": 7}}}
        out = _migrate_v3_to_v4(data)
        assert out["currency"] == {"GP": 42, "SP": 7}
        assert "equipment" not in out

    def test_handles_missing_equipment(self):
        """Rare in real exports but possible — a v3 doc with no money
        block still needs to come out shaped like v4."""
        data = {"name": "X"}
        out = _migrate_v3_to_v4(data)
        assert out["currency"] == {}
        assert "equipment" not in out

    def test_preserves_existing_currency(self):
        """If both keys are set (paranoid mid-migration state), keep
        the existing top-level currency rather than overwriting."""
        data = {
            "currency": {"GP": 999},
            "equipment": {"money": {"GP": 1}},
        }
        out = _migrate_v3_to_v4(data)
        assert out["currency"] == {"GP": 999}
        assert "equipment" not in out


class TestExportFilenameFor:
    def test_strips_double_quotes(self):
        assert export_filename_for('Bobby "Tables" Drop') == "Bobby Tables Drop"

    def test_replaces_slash(self):
        assert export_filename_for("Wizard/Cleric") == "Wizard_Cleric"

    def test_passes_safe_names_through(self):
        assert export_filename_for("Tharivol") == "Tharivol"
