"""
AI Helper Docstring
Purpose: Build the initial `character_data` blob for a freshly created character — class entries, saves/skills proficiencies derived from primary ability, prof bonus, and a default Character schema instance. Per-`SheetStyle` quirks live here (Shadowdark drops prof bonus, etc.).
Interactions:
- `app.models.char_sheet.GlobalClass`: hydrates `CharacterClassEntry` rows from the global lookup table (filtered by style, with custom `owner_id` rows visible to the owner).
- `app.schemas.char_sheet_specific.Character` / `CharacterClassEntry`: the schema this module emits.
- `app.services.character_service.create_character`: primary caller.
- `app.ui.pages.character_sheet`: also imports the `_seed_*` underscore aliases to re-seed after a class change; rename pending.
"""

"""Character seeding: per-rule-system defaults for fresh characters.

Public surface:
- `seed_classes_from_db` — hydrate `CharacterClassEntry` rows from `GlobalClass`
- `prof_bonus_for` — 5e proficiency-bonus table (Shadowdark → 0)
- `seed_saves_from_primary` / `seed_profs_from_primary` — multiclass rules
- `build_blank_character_data` — assemble the initial `character_data` blob

The leading-underscore aliases (`_seed_classes_from_db`, `_aggregate_saves`,
`_aggregate_proficiencies`) are kept for `app/ui/pages/character_sheet.py`
which still reaches into the seeding internals to reseed after a
class change. A future cleanup can rename those import sites.
"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.char_sheet import GlobalClass
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.char_sheet_specific import CharacterClassEntry
from app.user_context import UserContext


_ATTR_ALIAS = {
    "strength": "STR", "str": "STR",
    "dexterity": "DEX", "dex": "DEX",
    "constitution": "CON", "con": "CON",
    "intelligence": "INT", "int": "INT",
    "wisdom": "WIS", "wis": "WIS",
    "charisma": "CHA", "cha": "CHA",
    "vigor": "VIG", "vig": "VIG",  # Ultramodern5 optional 7th attribute
}


def _parse_saving_throws(raw: str | None) -> list[str]:
    """Parse a GlobalClass.saving_throws string into a list of attribute short codes.

    Accepts formats like "Strength, Constitution" or "STR, CON". "-" or blank means none.
    Unknown tokens are dropped rather than crashing ingest-driven data.
    """
    if not raw or raw.strip() in {"-", ""}:
        return []
    out: list[str] = []
    for tok in raw.split(","):
        key = tok.strip().lower()
        code = _ATTR_ALIAS.get(key)
        if code and code not in out:
            out.append(code)
    return out


def _parse_proficiencies(raw: str | None) -> dict[str, list[str]]:
    """Parse a GlobalClass.proficiencies CSV-ish string into {"weapon": [...], "armor": [...]}.

    Heuristic: tokens containing "armor" or "shield" go to armor, everything else to weapon.
    """
    result: dict[str, list[str]] = {"weapon": [], "armor": []}
    if not raw or raw.strip() in {"-", ""}:
        return result
    for tok in raw.split(","):
        name = tok.strip()
        if not name:
            continue
        low = name.lower()
        bucket = "armor" if ("armor" in low or "shield" in low) else "weapon"
        if name not in result[bucket]:
            result[bucket].append(name)
    return result


async def seed_classes_from_db(
    session: AsyncSession,
    style: SheetStyle,
    owner_id: str,
    entries: list[CharacterClassEntry],
) -> list[CharacterClassEntry]:
    """Look up each entry's class in GlobalClass and fill in hit_dice, saving_throw_grants,
    and proficiency_grants (unless the caller already supplied them)."""
    seeded: list[CharacterClassEntry] = []
    for entry in entries:
        stmt = select(GlobalClass).where(
            GlobalClass.name == entry.name,
            GlobalClass.source == style.value,
        ).where(
            or_(GlobalClass.owner_id.is_(None), GlobalClass.owner_id == owner_id)
        ).limit(1)
        row = (await session.execute(stmt)).scalars().first()

        data = entry.model_dump()
        if row is not None:
            if not data.get("hit_dice"):
                data["hit_dice"] = row.hit_dice
            if not data.get("saving_throw_grants"):
                data["saving_throw_grants"] = _parse_saving_throws(row.saving_throws)
            if not data.get("proficiency_grants"):
                data["proficiency_grants"] = _parse_proficiencies(row.proficiencies)
        # Always seed hit-dice current/max from level if not provided
        if data.get("hit_dice_current") is None:
            data["hit_dice_current"] = data["level"]
        if data.get("hit_dice_max") is None:
            data["hit_dice_max"] = data["level"]
        seeded.append(CharacterClassEntry(**data))
    return seeded


def prof_bonus_for(total_level: int, style: SheetStyle) -> int:
    """Standard 5e table: L1-4=2, L5-8=3, L9-12=4, L13-16=5, L17-20=6.

    Shadowdark doesn't use proficiency bonus — always 0.
    """
    if style == SheetStyle.SHADOWDARK:
        return 0
    return 2 + max(0, (max(1, total_level) - 1) // 4)


def seed_saves_from_primary(classes: list[CharacterClassEntry],
                            include_vigor: bool = False) -> list[dict]:
    """5e multiclass rule: only the FIRST class grants save proficiencies.
    Returns a full save list with proficiency=2 on granted attrs.

    `include_vigor` appends a 7th VIG save (Ultramodern5 optional Vigor
    attribute). Callers pass the character's `vigor_enabled` here so the save
    list stays in sync every time it is rebuilt — otherwise the Vigor save
    would be silently dropped on the next identity/ability edit.
    """
    granted: set[str] = set(classes[0].saving_throw_grants) if classes else set()
    attrs = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    if include_vigor:
        attrs.append("VIG")
    return [
        {"attribute": attr, "proficiency": 2 if attr in granted else 0, "misc": 0}
        for attr in attrs
    ]


def classes_require_vigor(classes: list[CharacterClassEntry]) -> bool:
    """True if any class grants a Vigor (VIG) save — e.g. the Ultramodern5 Magus.

    Such a class is a Vigor caster, so Vigor must be force-enabled on the
    character regardless of the create/edit toggle. Data-driven (reads the
    parsed save grants) rather than matching class names.
    """
    return any("VIG" in (c.saving_throw_grants or []) for c in classes)


def seed_profs_from_primary(classes: list[CharacterClassEntry]) -> dict[str, list[str]]:
    """5e multiclass rule: only the FIRST class grants weapon/armor proficiencies.
    Returns `{"weapon": [...], "armor": [...]}` (empty lists when no classes).
    """
    if not classes:
        return {"weapon": [], "armor": []}
    grants = classes[0].proficiency_grants or {}
    return {
        "weapon": list(grants.get("weapon", [])),
        "armor": list(grants.get("armor", [])),
    }


def default_money(style: SheetStyle) -> dict[str, int]:
    if style == SheetStyle.SHADOWDARK:
        return {"GP": 0}
    if style == SheetStyle.UM5:
        # Ultramodern5 uses a modern dollar economy, not fantasy coinage.
        return {"$": 0}
    return {"CP": 0, "SP": 0, "EP": 0, "GP": 0, "PP": 0}


# Back-compat aliases — `app/ui/pages/character_sheet.py` still imports these
# names via a function-scope import to reseed after a class change. Renaming
# the call site is a separate cleanup; keep the aliases here so the public
# move from `character_service` to `character_seeding` doesn't break that page.
_seed_classes_from_db = seed_classes_from_db
_aggregate_saves = seed_saves_from_primary
_aggregate_proficiencies = seed_profs_from_primary


async def build_blank_character_data(
    session: AsyncSession,
    name: str,
    style: SheetStyle,
    owner: UserContext,
    seeded_classes: list[CharacterClassEntry],
    ancestry: str,
    culture: str | None,
    background: str,
    vigor_enabled: bool = False,
) -> dict:
    """Construct the initial `character_data` blob for a fresh character.

    Pre-condition: `seeded_classes` must already have hit_dice / save grants
    / proficiency grants populated (call `seed_classes_from_db` first).

    `vigor_enabled` opts the character into the Ultramodern5 Vigor attribute:
    a VIG save and any Vigor-keyed skills are seeded only when it is True
    ("don't populate unless enabled"). A Vigor-caster class (e.g. the Magus)
    force-enables it regardless.
    """
    vigor_enabled = vigor_enabled or classes_require_vigor(seeded_classes)
    saving_throws = seed_saves_from_primary(seeded_classes, include_vigor=vigor_enabled)
    prof_aggregate = seed_profs_from_primary(seeded_classes)
    total_level = sum(c.level for c in seeded_classes)

    # Seed attribute score entries from the style's GlobalAttribute aliases.
    # The schema fixes the six score fields (str_score/dex_score/...), but we
    # pull the alias set from the DB to: (a) verify ingest has populated the
    # style's attributes, and (b) stay extensible if a future style registers a
    # seventh attribute. If the DB is unpopulated we fall back to the canonical
    # six so character creation never hard-fails.
    from app.services.global_items_service import list_attributes, list_skills
    attr_rows = await list_attributes(session, style, owner_id=owner.id)

    # Seed the full skill list for this style so the character starts with
    # every standard skill at proficiency=0. The "Add Skill" UI is reserved
    # for custom / DM-added entries. Shadowdark has no skill system.
    skills_seed: list[dict] = []
    if style != SheetStyle.SHADOWDARK:
        skill_rows = await list_skills(session, style, owner_id=owner.id)
        for s in skill_rows:
            attr = _ATTR_ALIAS.get((s.attribute or "").strip().lower(), (s.attribute or "STR").strip().upper())
            # Vigor-keyed skills only seed when the character opts into Vigor.
            if attr == "VIG" and not vigor_enabled:
                continue
            skills_seed.append({
                "name": s.name,
                "attribute": attr,
                "proficiency": 0,
                "misc": 0,
                "example_uses": s.example_uses,
            })
    _ALIAS_TO_FIELD = {
        "STR": "str_score", "DEX": "dex_score", "CON": "con_score",
        "INT": "int_score", "WIS": "wis_score", "CHA": "cha_score",
        "VIG": "vig_score",
    }
    aliases = [r.alias for r in attr_rows if r.alias in _ALIAS_TO_FIELD] or list(_ALIAS_TO_FIELD.keys())
    score_defaults = {
        _ALIAS_TO_FIELD[a]: {"base": 10, "racial": 0, "level": 0, "misc": 0}
        for a in aliases
    }
    # Starting HP: first class's hit die face at level 1 (no CON mod known yet).
    first_hit_die = seeded_classes[0].hit_dice or "d8"
    try:
        hp_default = int(first_hit_die.lstrip("dD"))
    except ValueError:
        hp_default = 10
    classes_json = [c.model_dump() for c in seeded_classes]

    return {
        "name": name,
        "style": style.value,
        "owner_id": owner.id,
        "race": {"ancestry": ancestry, "culture": culture, "lineage": None},
        "background": background,
        "destiny": {"name": "Survive"},
        "prof_bonus": prof_bonus_for(total_level, style),
        "ac": {"base": 10, "misc": 0},
        "initiative": {"base": 0, "misc": 0},
        "conditions": [],
        "inspiration": False if style == SheetStyle.SHADOWDARK else True,
        "speed": 30,
        "size": "Medium",
        "proficiency": {
            "weapon": prof_aggregate["weapon"],
            "armor": prof_aggregate["armor"],
            "language": [],
            "instrument": [],
            "tool": [],
            "game": [],
        },
        "experience_points": 0,
        "classes": classes_json,
        "character_class": classes_json[0]["name"],
        "level": total_level,
        "hp_current": hp_default,
        "hp_max": hp_default,
        "hp_temp": 0,
        "exhaustion": 0,
        "strife": 0,
        "vigor_enabled": vigor_enabled,
        **score_defaults,
        "saving_throws": saving_throws,
        "skills": skills_seed,
        "abilities": [],
        "actions": [],
        "inventory": [],
        "currency": default_money(style),
    }
