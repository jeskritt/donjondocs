"""
AI Helper Docstring
Purpose: Unified stat-block preset extractor and library listing service shared across all rule systems. Bridges `GlobalAbility` (Shadowrun Vehicles/Drones/Contacts/Spirits/Threats), `GlobalItem` (5e/A5e/UM5/Voidrunner Vehicles/Mounts/Drones/Pets), and the user-visible `Creature` catalog into a single `StatBlockPreset` format consumed by `allies.py`, `shadow_amps.py`, and `equipment.py`.
Interactions:
- `app.services.global_items_service.{list_abilities, list_items}`: system-scoped rulebook catalogs.
- `app.services.creature_service.list_creatures_visible_to`: user's own + public Creature Catalog entries.
- `app.ui.components.sheet.allies`: populates the "Seed from Library / Creature Catalog" dropdown.
- `app.ui.components.sheet_anarchy.shadow_amps` & `app.ui.components.sheet.equipment`: drives the "Also create stat block in Allies & Stat Blocks" checkbox.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.char_sheet import GlobalAbility, GlobalItem
from app.rule_systems import SheetStyle
from app.services.creature_service import list_creatures_visible_to
from app.services.global_items_service import list_abilities, list_items
from app.user_context import UserContext

# Item `type` values (case-insensitive) that represent entities working *with*
# a character and warrant seeding an Allies & Stat Blocks entry even when
# backed by a legacy CSV row without an explicit JSON `stat_block_md`.
STAT_BLOCK_ITEM_TYPES: dict[str, str] = {
    "vehicle": "Vehicle",
    "vehicles": "Vehicle",
    "mech": "Vehicle",
    "starship": "Vehicle",
    "drone": "Drone",
    "drones": "Drone",
    "robot": "Companion",
    "mount": "Companion",
    "mounts": "Companion",
    "pet": "Pet",
    "companion": "Companion",
}


@dataclass(frozen=True)
class StatBlockPreset:
    """One selectable entry in the Allies & Stat Blocks library picker."""

    key: str
    label: str
    name: str
    ally_type: str
    body_md: str
    source_group: str  # "Library" | "Creature Catalog"


def _parse_json_dict(raw: str | None) -> dict | None:
    if not raw or not isinstance(raw, str):
        return None
    stripped = raw.strip()
    if not stripped.startswith("{"):
        return None
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def extract_ability_stat_block(row: GlobalAbility) -> dict:
    """Extract structured Amp metadata and optional Allies stat block from a `GlobalAbility` row."""
    meta = _parse_json_dict(row.features) or {}
    return {
        "amp_type": meta.get("amp_type"),
        "rating": int(meta.get("rating", 1) or 0),
        "essence_cost": float(meta.get("essence_cost", 0.0) or 0.0),
        "effects": meta.get("effects") if isinstance(meta.get("effects"), list) else [],
        "ally_type": meta.get("ally_type"),
        "stat_block_md": meta.get("stat_block_md") or "",
        "stat_block_only": bool(meta.get("stat_block_only", False)),
        "summary": row.description or "",
    }


def _synthesize_legacy_vehicle_md(row: GlobalItem, ally_type: str) -> str:
    """Build a clean starter Markdown stat block for legacy CSV Vehicle/Mount items."""
    details = []
    if row.value:
        details.append(f"**Cost:** {row.value}")
    if row.weight and row.weight not in {"-", "—"}:
        details.append(f"**Weight:** {row.weight}")
    meta_line = " &emsp; ".join(details)
    summary = (row.description or row.effects or "").strip()
    lines = [
        "___",
        f"> ## {row.name}",
        f"> *{ally_type} ({row.source})*",
        "> ___",
    ]
    if meta_line:
        lines.append(f"> {meta_line}")
    if summary:
        lines.append(f"> {summary}")
    lines.extend([
        "> ___",
        "> ### Notes & Modifications",
        "> *Customize speed, armor, HP, crew, and mounted armament here.*",
    ])
    return "\n".join(lines)


def extract_item_stat_block(row: GlobalItem) -> dict:
    """Extract inline summary/description and optional Allies stat block from a `GlobalItem` row.

    Supports both:
    - Rich JSON catalogs where `row.effects` is a JSON dict with `summary`,
      `ally_type`, and `stat_block_md`.
    - Legacy CSV catalogs where `row.type` is e.g. `"Vehicle"` or `"Mount"`
      (synthesizes a starter Markdown stat block pre-filled with the CSV stats).
    """
    effects_json = _parse_json_dict(row.effects)
    if effects_json is not None:
        return {
            "summary": str(effects_json.get("summary") or ""),
            "description": row.description or "",
            "ally_type": effects_json.get("ally_type"),
            "stat_block_md": str(effects_json.get("stat_block_md") or ""),
        }

    inferred_type = STAT_BLOCK_ITEM_TYPES.get((row.type or "").strip().lower())
    stat_md = _synthesize_legacy_vehicle_md(row, inferred_type) if inferred_type else ""
    return {
        "summary": row.effects or "",
        "description": row.description or "",
        "ally_type": inferred_type,
        "stat_block_md": stat_md,
    }


async def list_ally_presets(
    session: AsyncSession,
    style: SheetStyle,
    current_user: UserContext,
) -> list[StatBlockPreset]:
    """Return combined System Library + Creature Catalog stat blocks for `Allies & Stat Blocks`.

    Shadowdark characters intentionally skip Vehicle items (matching `ally_type_options`).
    """
    presets: list[StatBlockPreset] = []
    seen_keys: set[str] = set()

    # 1. System-scoped GlobalAbility stat blocks (e.g., Shadowrun Vehicles, Drones, Contacts, Spirits, Threats).
    ability_rows = await list_abilities(session, style, owner_id=current_user.id)
    for row in ability_rows:
        info = extract_ability_stat_block(row)
        stat_md = (info["stat_block_md"] or "").strip()
        ally_type = info["ally_type"]
        if not stat_md or not ally_type:
            continue
        if style == SheetStyle.SHADOWDARK and ally_type == "Vehicle":
            continue
        key = f"lib:ability:{row.id}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        presets.append(
            StatBlockPreset(
                key=key,
                label=f"[Library · {ally_type}] {row.name}",
                name=row.name,
                ally_type=str(ally_type),
                body_md=stat_md,
                source_group="Library",
            )
        )

    # 2. System-scoped GlobalItem stat blocks (e.g., UM5/Voidrunner Vehicles, A5e/5e Mounts & Companions).
    item_rows = await list_items(session, style, owner_id=current_user.id)
    for row in item_rows:
        info = extract_item_stat_block(row)
        stat_md = (info["stat_block_md"] or "").strip()
        ally_type = info["ally_type"]
        if not stat_md or not ally_type:
            continue
        if style == SheetStyle.SHADOWDARK and ally_type == "Vehicle":
            continue
        key = f"lib:item:{row.id}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        presets.append(
            StatBlockPreset(
                key=key,
                label=f"[Library · {ally_type}] {row.name}",
                name=row.name,
                ally_type=str(ally_type),
                body_md=stat_md,
                source_group="Library",
            )
        )

    # 3. User-visible Creature Catalog entries (own + public shared creatures).
    creatures = await list_creatures_visible_to(session, current_user)
    for cr in creatures:
        ctype_low = (cr.creature_type or "").lower()
        if "vehicle" in ctype_low:
            inferred_ally_type = "Vehicle"
        elif style == SheetStyle.SHADOWRUN_ANARCHY_2:
            inferred_ally_type = "NPC / Threat"
        else:
            inferred_ally_type = "Companion"
        if style == SheetStyle.SHADOWDARK and inferred_ally_type == "Vehicle":
            continue
        tag = cr.creature_type or inferred_ally_type
        key = f"catalog:creature:{cr.id}"
        presets.append(
            StatBlockPreset(
                key=key,
                label=f"[Creature Catalog · {tag}] {cr.name}",
                name=cr.name,
                ally_type=inferred_ally_type,
                body_md=cr.body_md or "",
                source_group="Creature Catalog",
            )
        )

    return presets
