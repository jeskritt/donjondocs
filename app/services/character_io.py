"""
AI Helper Docstring
Purpose: Pure helpers for the versioned character export/import envelope. Owns `EXPORT_VERSION`, the registered N→N+1 migrators in `_MIGRATIONS`, `migrate_character_data` chain runner, and `export_filename_for` sanitization.
Interactions:
- `app.services.character_service.export_character` / `import_character`: only callers.
- `app.api.character_routes`: imports `EXPORT_VERSION` and `export_filename_for` for the HTTP envelope and Content-Disposition header.
- Bumping `EXPORT_VERSION`: any schema change to `Character` in `app/schemas/char_sheet_specific.py` requires a new `_migrate_vN_to_vN+1` registered in `_MIGRATIONS`.
"""

"""Character export/import helpers: version envelope and migration chain.

The import/export functions in `character_service` wrap RBAC + session
concerns around these pure helpers. Schema changes to `character_data`
bump `EXPORT_VERSION` and register an `N → N+1` migrator in `_MIGRATIONS`
so older exports still import cleanly.
"""

import re
from typing import Callable

from app.services._errors import CharacterServiceError


EXPORT_VERSION = 7

# Hard cap on uploaded import payloads (shared by REST API and NiceGUI upload
# dialogs). A real character export is a few KB; 1 MiB leaves comfortable
# headroom while preventing OOM-by-upload DoS (security audit finding #3).
MAX_IMPORT_BYTES = 1 * 1024 * 1024

_CTRL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def export_filename_for(name: str) -> str:
    """Sanitize a character name for use as an export filename stem.

    Strips HTTP header/control characters (`\\r`, `\\n`, NUL, `;`, `"`), maps
    path separators (`/` and `\\`) to `_`, and falls back to `"character"` if
    nothing usable remains.
    """
    cleaned = _CTRL_CHARS_RE.sub("", name)
    cleaned = cleaned.replace('"', "").replace(";", "").replace("/", "_").replace("\\", "_")
    return cleaned.strip() or "character"


def _migrate_v3_to_v4(data: dict) -> dict:
    """v4: currency moves from `equipment.money` (nested) to a flat
    top-level `currency` dict on Character.

    Drops the entire `equipment` envelope — its only payload was
    `money`, and the wrapper class has been removed.
    """
    equipment = data.pop("equipment", None) or {}
    if "currency" not in data:
        data["currency"] = equipment.get("money") or {}
    return data


def _migrate_v4_to_v5(data: dict) -> dict:
    """v5: add `death_save_successes` and `death_save_failures` int counters
    to Character. Pydantic supplies defaults on validation, but record the
    explicit zero here so re-exported v5 files round-trip cleanly.
    """
    data.setdefault("death_save_successes", 0)
    data.setdefault("death_save_failures", 0)
    return data


def _migrate_v5_to_v6(data: dict) -> dict:
    """v6: envelope-level change only — `allies` and `notes` are now sibling
    keys to `character_data` in the export envelope (rows in the new
    `character_allies` and `character_notes` tables, not fields on the
    `Character` schema). The character_data blob itself is unchanged, so
    this migrator is a pass-through. The caller (`import_character`)
    handles the new envelope keys separately.
    """
    return data


def _migrate_v6_to_v7(data: dict) -> dict:
    """v7: add `is_custom: bool` to every InventoryItem. False means the
    entry is a pristine snapshot of a global library row; True means the
    user authored it via Add-Custom or has edited the row's display fields.
    Pydantic supplies the default on validation, but record the explicit
    False here so re-exported v7 files round-trip cleanly.
    """
    inv = data.get("inventory")
    if isinstance(inv, list):
        for entry in inv:
            if isinstance(entry, dict):
                entry.setdefault("is_custom", False)
    return data


_MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    # Keyed by source version. Each entry migrates a character_data dict
    # from version N up to version N+1. When EXPORT_VERSION bumps, add
    # the N → N+1 migrator here so old exports still import cleanly.
    3: _migrate_v3_to_v4,
    4: _migrate_v4_to_v5,
    5: _migrate_v5_to_v6,
    6: _migrate_v6_to_v7,
}


def migrate_character_data(data: dict, from_version: int) -> dict:
    """Apply migrators to bring character_data from from_version to EXPORT_VERSION."""
    if from_version > EXPORT_VERSION:
        raise CharacterServiceError(
            f"Import version {from_version} is newer than supported "
            f"(expected <= {EXPORT_VERSION}). Upgrade the app to import this file."
        )
    current = data
    version = from_version
    while version < EXPORT_VERSION:
        migrator = _MIGRATIONS.get(version)
        if migrator is None:
            raise CharacterServiceError(
                f"No migration available from character_data version {version} "
                f"to {version + 1}."
            )
        current = migrator(current)
        version += 1
    return current
