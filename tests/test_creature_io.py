"""
AI Helper Docstring
Purpose: Direct tests for `creature_io` — version chain runner, filename sanitizer, and the "newer-than-supported" guard. Mirrors the character_io test pattern.
Interactions:
- Targets `app.services.creature_io.{EXPORT_VERSION, export_filename_for, migrate_creature_data}`.
"""

import pytest

from app.services._errors import CreatureServiceError
from app.services.creature_io import (
    EXPORT_VERSION,
    export_filename_for,
    migrate_creature_data,
)


class TestExportFilename:
    def test_strips_quotes(self):
        assert export_filename_for('Bobby "Tables"') == "Bobby Tables.creature"

    def test_strips_slashes(self):
        assert export_filename_for("Pit Fiend / Devil Lord") == "Pit Fiend _ Devil Lord.creature"

    def test_blank_becomes_creature(self):
        assert export_filename_for("   ") == "creature.creature"


class TestMigrateCreatureData:
    def test_noop_at_current_version(self):
        data = {"name": "X"}
        assert migrate_creature_data(data, EXPORT_VERSION) == data

    def test_rejects_newer(self):
        with pytest.raises(CreatureServiceError, match="newer than supported"):
            migrate_creature_data({}, EXPORT_VERSION + 1)

    def test_rejects_missing_migrator(self):
        """Today the chain is empty (v1 only). A hypothetical v0 input
        would have no migrator registered → reject explicitly."""
        if EXPORT_VERSION <= 1:
            with pytest.raises(CreatureServiceError, match="No migration available"):
                migrate_creature_data({}, 0)
