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

from typing import Callable

from app.services._errors import CharacterServiceError


EXPORT_VERSION = 4


def export_filename_for(name: str) -> str:
    """Sanitize a character name for use as an export filename stem."""
    return name.replace('"', "").replace("/", "_")


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


_MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    # Keyed by source version. Each entry migrates a character_data dict
    # from version N up to version N+1. When EXPORT_VERSION bumps, add
    # the N → N+1 migrator here so old exports still import cleanly.
    3: _migrate_v3_to_v4,
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
