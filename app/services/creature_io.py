"""
AI Helper Docstring
Purpose: Versioned export/import envelope for creature catalog rows. Mirrors the character envelope pattern but on a fresh, independent version chain — creatures are user-owned resources, not character-owned, so the two chains never need to cross.
Interactions:
- `app.api.creature_routes`: builds the export envelope and validates inbound imports.
- `app.services.creature_service`: provides the Creature row that gets serialised / created.

Bumping `EXPORT_VERSION`: any schema change to `Creature` in
`app/schemas/creature.py` requires a new `_migrate_vN_to_vN+1` registered
in `_MIGRATIONS` so older exports still import cleanly.
"""

"""Creature catalog export/import — versioned envelope + migration chain."""

import re
from typing import Callable

from app.services._errors import CreatureServiceError


EXPORT_VERSION = 1

# Hard cap on uploaded import payloads (shared by REST API and NiceGUI upload
# dialogs — security audit finding #3).
MAX_IMPORT_BYTES = 1 * 1024 * 1024

_CTRL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def export_filename_for(name: str) -> str:
    """Sanitize a creature name for use as an export filename stem.

    Same rules as the character helper — strip control chars, quotes,
    semicolons, and path separators — plus a `.creature` suffix so the file
    is visually distinct from character exports in a download folder.
    """
    cleaned = _CTRL_CHARS_RE.sub("", name)
    cleaned = cleaned.replace('"', "").replace(";", "").replace("/", "_").replace("\\", "_")
    safe = cleaned.strip() or "creature"
    return f"{safe}.creature"


# No migrators yet — v1 is the first published shape. When the Creature
# schema changes, register a v1→v2 entry and bump EXPORT_VERSION.
_MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


def migrate_creature_data(data: dict, from_version: int) -> dict:
    """Bring a `creature_data` dict from `from_version` up to `EXPORT_VERSION`."""
    if from_version > EXPORT_VERSION:
        raise CreatureServiceError(
            f"Import version {from_version} is newer than supported "
            f"(expected <= {EXPORT_VERSION}). Upgrade the app to import this file."
        )
    current = data
    version = from_version
    while version < EXPORT_VERSION:
        migrator = _MIGRATIONS.get(version)
        if migrator is None:
            raise CreatureServiceError(
                f"No migration available from creature_data version {version} "
                f"to {version + 1}.",
                status_code=400,
            )
        current = migrator(current)
        version += 1
    return current
