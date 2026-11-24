"""
AI Helper Docstring
Purpose: Pure functions that compute the post-rest state of a character_data dict (HP, hit dice, magic resources, exhaustion, exertion, conditions). No I/O, no RBAC — safe to unit-test directly.
Interactions:
- `app.services.character_service.rest_character`: only caller; wraps these helpers with the DB session + ownership check.
- Operates on dicts shaped like the `Character` Pydantic schema; never instantiates the schema itself.
- Raises `CharacterServiceError` when the rest kind is unknown or required inputs (hit dice, classes) are malformed.
"""

"""Pure rest-mechanics helpers for character_data.

`apply_rest` is the single public entry point: given a character_data
dict, a rest kind (`"short"` or `"long"`), and optional flags, return
the post-rest dict. No DB, no RBAC — `character_service.rest_character`
wraps this in the persistence + authorization layer.
"""

from app.rule_systems import SheetStyle, SystemFamily, system_family_for
from app.services._errors import CharacterServiceError


def _hit_die_avg(die: str | None) -> int:
    """Average roll on a hit die (e.g. 'd10' → 6). Unknown/missing → 0."""
    if not die:
        return 0
    try:
        faces = int(die.lstrip("dD"))
    except ValueError:
        return 0
    # Standard 5e "half+1" average: d10 → 6, d8 → 5, d6 → 4
    return faces // 2 + 1


def _attr_mod(score_dict: dict) -> int:
    total = int(score_dict.get("base", 10)) + int(score_dict.get("racial", 0)) \
          + int(score_dict.get("level", 0)) + int(score_dict.get("misc", 0))
    return (total - 10) // 2


def _restore_hp(data: dict, kind: str, classes: list[dict],
                 con_mod: int, options: dict) -> None:
    if kind == "short":
        spends = options.get("hit_dice_spent", {}) or {}
        hp_gain = 0
        for c in classes:
            n = int(spends.get(c["name"], 0) or 0)
            avail = int(c.get("hit_dice_current") or 0)
            n = max(0, min(n, avail))
            if n:
                c["hit_dice_current"] = avail - n
                hp_gain += n * max(1, _hit_die_avg(c.get("hit_dice")) + con_mod)
        hp_max = int(data.get("hp_max", 0))
        hp_cur = int(data.get("hp_current", 0))
        data["hp_current"] = min(hp_max, hp_cur + hp_gain)
    else:
        data["hp_current"] = int(data.get("hp_max", 0))
        data["hp_temp"] = 0
        data["exhaustion"] = max(0, int(data.get("exhaustion", 0)) - 1)


def _recover_hit_dice(data: dict, classes: list[dict], options: dict) -> None:
    total_level = sum(int(c.get("level", 1)) for c in classes) or 1
    regain_budget = max(1, total_level // 2)
    regain_map = options.get("hit_dice_regain") or {}
    if not regain_map:
        remaining = regain_budget
        regain_map = {c["name"]: 0 for c in classes}
        while remaining > 0 and any(
            (c.get("hit_dice_max") or 0) - (c.get("hit_dice_current") or 0)
            > regain_map.get(c["name"], 0) for c in classes
        ):
            for c in classes:
                deficit = (c.get("hit_dice_max") or 0) - (c.get("hit_dice_current") or 0) - regain_map.get(c["name"], 0)
                if deficit > 0 and remaining > 0:
                    regain_map[c["name"]] = regain_map.get(c["name"], 0) + 1
                    remaining -= 1
    for c in classes:
        n = int(regain_map.get(c["name"], 0) or 0)
        cur = int(c.get("hit_dice_current") or 0)
        mx = int(c.get("hit_dice_max") or 0)
        c["hit_dice_current"] = min(mx, cur + n)


def _refill_magic_resources(data: dict, kind: str, options: dict) -> None:
    _LONG_REST_TYPES = frozenset((
        "Slots / Level", "Shadowdark", "Spell Points",
        "PERLEVEL", "SHADOWDARK", "POINTS", "Slots", "SLOTS",
    ))
    reset_window = {"short"} if kind == "short" else {"short", "long"}

    resources = []
    for r in data.get("magic_resources", []) or []:
        rd = dict(r)
        mt = rd.get("magic_type")
        if kind == "short" and options.get("regain_slots"):
            if mt in ("Slots", "SLOTS") and rd.get("maximum") is not None:
                rd["current"] = list(rd["maximum"])
        elif kind == "long":
            if mt in _LONG_REST_TYPES and rd.get("maximum") is not None:
                rd["current"] = list(rd["maximum"])
        er = rd.get("extra_resource")
        if er and er.get("reset_on") in reset_window:
            rd["extra_resource"] = {**er, "current": er.get("maximum", 0)}
        resources.append(rd)
    data["magic_resources"] = resources


def _reset_trackers(data: dict, kind: str) -> None:
    reset_window = {"short"} if kind == "short" else {"short", "long"}
    abilities = []
    for a in data.get("abilities", []) or []:
        ad = dict(a)
        t = ad.get("tracker")
        if t and t.get("reset_on") in reset_window:
            ad["tracker"] = {**t, "current": t.get("maximum", 0)}
        abilities.append(ad)
    data["abilities"] = abilities
    data["exertion_current"] = data.get("exertion_max", 0)


def _apply_anarchy_reset(data: dict, kind: str) -> dict:
    """Apply Shadowrun: Anarchy 2.0 session/downtime resets."""
    wounds = dict(data.get("wounds") or {})
    if kind == "new_run":
        data["edge_current"] = int(data.get("edge_base", 3))
        wounds["stim_patch_active"] = False
        data["wounds"] = wounds
        return data
    if kind == "heal_all":
        wounds["light"] = [False for _ in (wounds.get("light") or [False, False])]
        wounds["serious"] = [False for _ in (wounds.get("serious") or [False])]
        wounds["incapacitated"] = False
        wounds["stim_patch_active"] = False
        data["wounds"] = wounds
        return data
    raise CharacterServiceError(
        f"Rest kind {kind!r} is not supported for Shadowrun: Anarchy 2.0 (expected 'new_run' or 'heal_all')."
    )


def apply_rest(
    character_data: dict,
    kind: str,
    options: dict | None = None,
    style: SheetStyle | None = None,
) -> dict:
    options = options or {}
    data = dict(character_data)

    resolved_style = style
    if resolved_style is None and data.get("style"):
        try:
            resolved_style = SheetStyle(data["style"])
        except ValueError:
            resolved_style = None

    if resolved_style is not None and system_family_for(resolved_style) == SystemFamily.SHADOWRUN_ANARCHY_2:
        return _apply_anarchy_reset(data, kind)

    con_mod = _attr_mod(data.get("con_score", {}))
    classes = [dict(c) for c in data.get("classes", [])]

    if kind == "short":
        _restore_hp(data, kind, classes, con_mod, options)
        data["classes"] = classes
        _refill_magic_resources(data, kind, options)
    elif kind == "long":
        _restore_hp(data, kind, classes, con_mod, options)
        _recover_hit_dice(data, classes, options)
        data["classes"] = classes
        _refill_magic_resources(data, kind, options)
    else:
        raise CharacterServiceError(f"Unknown rest kind: {kind}")

    _reset_trackers(data, kind)
    return data
