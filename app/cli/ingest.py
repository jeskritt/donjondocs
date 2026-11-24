"""
AI Helper Docstring
Purpose: Automation pipeline for parsing CSV game data (Weapons, Armor, Classes, Skills, Items, Attributes) into SQLite lookup tables. Extracts armor AC stats (base_ac, dex_cap, is_shield) from CSV formats.
Interactions:
- `app.models.char_sheet.py`: Uses `GlobalClass` and others as the core ORM objects for `session.add`.
- `app.database.py`: Establishes its own async pipeline during module runtime.
"""

import asyncio
import csv
import glob
import json
import os
import re
import sys

from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_factory, engine, Base
from app.schemas.char_sheet_global import SheetStyle
from app.models.char_sheet import (
    GlobalAbility,
    GlobalClass,
    GlobalAttribute,
    GlobalSkill,
    GlobalItem,
    GlobalWeapon,
    GlobalArmor,
    GlobalCombatManeuver,
    GlobalSpell,
    GlobalDestiny
)

_ATTR_ALIAS = {
    "strength": "STR", "str": "STR",
    "dexterity": "DEX", "dex": "DEX",
    "constitution": "CON", "con": "CON",
    "intelligence": "INT", "int": "INT",
    "wisdom": "WIS", "wis": "WIS",
    "charisma": "CHA", "cha": "CHA",
    "vigor": "VIG", "vig": "VIG",  # Ultramodern5 optional 7th attribute
    # Shadowrun: Anarchy 2.0 attributes
    "agility": "AGI", "agi": "AGI",
    "willpower": "WIL", "wil": "WIL",
    "logic": "LOG", "log": "LOG",
}


def normalize_attribute(value: str | None) -> str | None:
    """Convert a full attribute name ('Dexterity') or existing alias to a 3-letter code."""
    if value is None:
        return None
    v = value.strip().lower()
    return _ATTR_ALIAS.get(v, value.strip())


def get_style_from_filename(filename: str) -> SheetStyle:
    low = filename.lower()
    if "phb2014" in low:
        return SheetStyle.DND5E
    elif "levelup" in low or "a5e" in low:
        return SheetStyle.A5E
    elif "shadowdark" in low:
        return SheetStyle.SHADOWDARK
    elif "um5" in low or "ultramodern" in low:
        return SheetStyle.UM5
    elif "voidrunner" in low:
        return SheetStyle.VOIDRUNNER
    elif "sra2" in low or "anarchy" in low:
        return SheetStyle.SHADOWRUN_ANARCHY_2
    return SheetStyle.DND5E # default

_DEX_CAP_PATTERNS = (
    re.compile(r'^\s*\+?\s*Dex(?:\s*mod)?\s*$', re.IGNORECASE),  # "-"/"DEX mod"
    re.compile(r'unlimited', re.IGNORECASE),
)


def parse_armor_stats(armor_type: str | None, armor_class: str | None,
                      max_dex: str | None) -> tuple[int | None, int | None, bool]:
    """Extract (base_ac, dex_cap, is_shield) from the CSV's armor_class / max_dex / type cells.

    Handles the three CSV flavors in `data/`:
      PHB:        base is a plain int, `Max Dex` is "-"/"0"/"2".  Shield row uses `Armor Type == "Shield"`.
      A5e:        same, but `Max Dex` of "Unlimited" means no cap; shields use "+N" in `Armor Class`.
      Shadowdark: base may be "11 + DEX mod" (uncapped light) or a plain int.

    Returns (None, None, False) if the cells are too malformed to parse — the
    sheet math then falls back on `c.ac.base` as today.
    """
    is_shield = (armor_type or "").strip().lower() == "shield"
    ac_str = (armor_class or "").strip()

    if is_shield:
        # Strip leading "+" and parse as bonus. "+2" → 2, "2" → 2.
        m = re.match(r'^\+?\s*(\d+)', ac_str)
        return (int(m.group(1)) if m else 0, None, True)

    # Non-shield: pull the first integer run as base_ac. Catches "11", "11 + DEX mod", "15".
    m = re.match(r'^(\d+)', ac_str)
    base_ac = int(m.group(1)) if m else None

    # Dex cap: a plain integer means a hard cap (Medium = 2, Heavy = 0);
    # any "Dex"-shaped marker or "Unlimited" means no cap.
    cap_raw = (max_dex or "").strip()
    ac_mentions_dex = bool(re.search(r'dex', ac_str, re.IGNORECASE))
    is_light = (armor_type or "").strip().lower() == "light"

    if not cap_raw or cap_raw in {"-", "—"}:
        # PHB light armor: "-" means uncapped. Shadowdark armor doesn't list
        # caps; infer from whether the AC string mentions DEX (e.g.
        # "11 + DEX mod" ⇒ uncapped; a plain "15" ⇒ no dex contribution).
        if is_light or ac_mentions_dex:
            dex_cap = None
        else:
            dex_cap = 0
    elif any(p.search(cap_raw) for p in _DEX_CAP_PATTERNS):
        dex_cap = None
    else:
        try:
            dex_cap = int(cap_raw)
        except ValueError:
            dex_cap = None

    return base_ac, dex_cap, False


def normalize_key(key: str) -> str:
    key = key.lower().strip()
    if 'name' in key and 'weapon' in key: return 'name'
    if 'name' in key and 'armor' in key: return 'name'
    if 'type' in key and 'weapon' in key: return 'type'
    if 'type' in key and 'armor' in key: return 'type'
    if 'cost' in key: return 'value'
    if 'properties' in key: return 'notes'
    if 'armor class' in key or 'ac' in key: return 'armor_class'
    if 'strength' in key: return 'strength_requirement'
    if 'stealth' in key: return 'disadvantage_on_stealth'
    if 'item' == key: return 'name'
    # Skills CSV columns
    if key == 'skill': return 'name'
    if key == 'ability': return 'attribute'
    if 'example uses' in key: return 'example_uses'
    return key


_JSON_KIND_TO_MODEL = {
    "attributes": GlobalAttribute,
    "skills": GlobalSkill,
    "weapons": GlobalWeapon,
    "armor": GlobalArmor,
    "equipment": GlobalItem,
    "items": GlobalItem,
    "spells": GlobalSpell,
    "abilities": GlobalAbility,
    "shadow_amps": GlobalAbility,
    "classes": GlobalClass,
    "combat_maneuvers": GlobalCombatManeuver,
    "destinies": GlobalDestiny,
}


async def _upsert_global_row(session, ModelCls, style: SheetStyle, parsed_row: dict) -> str:
    """Upsert one seeded (`owner_id IS NULL`) row; returns `'inserted'` or `'updated'`."""
    name = parsed_row["name"]
    stmt = select(ModelCls).where(
        ModelCls.name == name,
        ModelCls.source == style.value,
        ModelCls.owner_id.is_(None),
    ).limit(1)
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if obj:
        for k, v in parsed_row.items():
            setattr(obj, k, v)
        return "updated"
    parsed_row["source"] = style.value
    obj = ModelCls(**parsed_row)
    session.add(obj)
    return "inserted"


async def ingest_json_file(session, filepath: str) -> dict[str, int]:
    """Ingest a rich JSON rulebook catalog file (`{"style", "kind", "items": [...]}`).

    Non-string values on string-typed ORM columns (e.g. structured dicts/lists
    on `GlobalAbility.features` or `GlobalItem.effects`) are JSON-serialized
    automatically so rich catalog metadata round-trips cleanly.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict) or "items" not in payload:
        print(f"Skipping malformed JSON catalog {filepath}")
        return {"inserted": 0, "updated": 0}

    style = SheetStyle(payload["style"])
    kind = str(payload.get("kind", "")).strip().lower()
    ModelCls = _JSON_KIND_TO_MODEL.get(kind)
    if ModelCls is None:
        print(f"Skipping unknown JSON catalog kind {kind!r} in {filepath}")
        return {"inserted": 0, "updated": 0}

    valid_cols = {c.name: c for c in ModelCls.__table__.columns}
    counts = {"inserted": 0, "updated": 0}
    print(f"Ingesting {os.path.basename(filepath)} ({kind}) as {style.value}...")

    for raw in payload["items"]:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        parsed_row: dict = {}
        for k, v in raw.items():
            if k not in valid_cols or k in {"id", "source", "owner_id", "created_at", "updated_at"}:
                continue
            if k == "attribute" and ModelCls is GlobalSkill and isinstance(v, str):
                parsed_row[k] = normalize_attribute(v)
            elif isinstance(v, (dict, list)):
                parsed_row[k] = json.dumps(v, ensure_ascii=False)
            else:
                parsed_row[k] = v

        # For JSON armor rows that supply numeric `base_ac` directly (e.g. SRA2
        # flat armor ratings), preserve it rather than running 5e AC regex parsing.
        if ModelCls is GlobalArmor and "base_ac" not in parsed_row and parsed_row.get("armor_class"):
            base_ac, dex_cap, is_shield = parse_armor_stats(
                parsed_row.get("type"),
                parsed_row.get("armor_class"),
                raw.get("max_dex"),
            )
            parsed_row["base_ac"] = base_ac
            parsed_row["dex_cap"] = dex_cap
            parsed_row["is_shield"] = is_shield

        status = await _upsert_global_row(session, ModelCls, style, parsed_row)
        counts[status] += 1

    return counts


async def ingest_file(session, filepath: str) -> dict[str, int]:
    if filepath.lower().endswith(".json"):
        return await ingest_json_file(session, filepath)

    filename = os.path.basename(filepath)
    style = get_style_from_filename(filename)

    if "armor" in filename:
        ModelCls = GlobalArmor
    elif "weapon" in filename:
        ModelCls = GlobalWeapon
    elif "equipment" in filename:
        ModelCls = GlobalItem
    elif "classes" in filename:
        ModelCls = GlobalClass
    elif "attributes" in filename:
        ModelCls = GlobalAttribute
    elif "skills" in filename:
        ModelCls = GlobalSkill
    else:
        print(f"Skipping unknown file prefix for {filename}")
        return {"inserted": 0, "updated": 0}

    print(f"Ingesting {filename} as {style.value}...")

    valid_keys = [c.name for c in ModelCls.__table__.columns]
    counts = {"inserted": 0, "updated": 0}

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed_row = {}
            raw_max_dex = None
            for k, v in row.items():
                if not k: continue
                norm_k = normalize_key(k)
                if k.strip().lower().replace(' ', '') in {'maxdex', 'max_dex'}:
                    raw_max_dex = v
                if norm_k in valid_keys:
                    if norm_k == 'disadvantage_on_stealth':
                        parsed_row[norm_k] = "Yes" if "Disadvantage" in str(v) else None
                    elif norm_k == 'attribute' and ModelCls is GlobalSkill:
                        parsed_row[norm_k] = normalize_attribute(v)
                    else:
                        parsed_row[norm_k] = v

            if ModelCls is GlobalArmor:
                base_ac, dex_cap, is_shield = parse_armor_stats(
                    parsed_row.get('type'),
                    parsed_row.get('armor_class'),
                    raw_max_dex,
                )
                parsed_row['base_ac'] = base_ac
                parsed_row['dex_cap'] = dex_cap
                parsed_row['is_shield'] = is_shield

            if 'name' not in parsed_row: continue
            status = await _upsert_global_row(session, ModelCls, style, parsed_row)
            counts[status] += 1

    return counts


async def run_ingestion_in_session(session, data_dir: str) -> dict[str, int]:
    """Ingest all `*.csv` and `**/*.json` catalogs under `data_dir` using an existing session."""
    csv_files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    json_files = sorted(glob.glob(os.path.join(data_dir, "**", "*.json"), recursive=True))
    files = csv_files + json_files
    report = {"files": len(files), "inserted": 0, "updated": 0}
    if not files:
        print(f"No CSV or JSON files found in {data_dir}")
        return report

    for f in files:
        c = await ingest_file(session, f)
        report["inserted"] += c["inserted"]
        report["updated"] += c["updated"]
    await session.commit()
    return report


async def run_ingestion(data_dir: str) -> dict[str, int]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        report = await run_ingestion_in_session(session, data_dir)
    print(f"Ingestion complete ({report['files']} files, +{report['inserted']} inserted, ~{report['updated']} updated).")
    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.cli.ingest <data_dir>")
        sys.exit(1)
    
    get_settings()
    asyncio.run(run_ingestion(sys.argv[1]))
