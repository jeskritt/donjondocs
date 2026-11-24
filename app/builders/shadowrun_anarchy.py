"""
AI Helper Docstring
Purpose: Pure schema → view-model builder for Shadowrun: Anarchy 2.0 (`AnarchyCharacter`). Computes Essence & cumulative threshold alerts, metatype caps, Skill/Specialization Dice Pools & Risk Reduction (`RR`, capped at 3), Wound Monitor box counts & precalculated Physical/Mental Wound Thresholds, dynamic `STR+X` Weapon DVs, Nuyen character-cost breakdown, and the official Risk/Glitch reference table.
Interactions:
- `app.schemas.shadowrun_anarchy.AnarchyCharacter`: input model.
- `app.builders.__init__.get_builder`: dispatches `SheetStyle.SHADOWRUN_ANARCHY_2` here.
- `app.ui.components.sheet_anarchy.*`: consumes the `view_data` dict produced by `build()`.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.shadowrun_anarchy import (
    METATYPE_RULES,
    AmpType,
    AnarchyCharacter,
    Metatype,
)

# Risk Dice & Glitch reference table (Shadowrun: Anarchy 2.0 sheet, p. 322).
RISK_TABLE: list[dict[str, str]] = [
    {"rr": "0", "low": "1 die", "normal": "2 dice", "high": "4 dice", "extreme": "6+ dice"},
    {"rr": "1", "low": "3 dice", "normal": "5 dice", "high": "7 dice", "extreme": "10+ dice"},
    {"rr": "2", "low": "5 dice", "normal": "8 dice", "high": "11 dice", "extreme": "13+ dice"},
    {"rr": "3", "low": "8 dice", "normal": "12 dice", "high": "15 dice", "extreme": "N/A"},
]

GLITCH_SCALE = "Remaining 1s: 0 = no effect · 1 = minor glitch · 2 = critical glitch (+1 Edge) · 3+ = disaster (+2 Edge)"

_STR_FORMULA_RE = re.compile(r"^\s*\(?\s*STR\s*(?:([+-])\s*(\d+))?\s*\)?\s*$", re.IGNORECASE)

# Canonical skill display order by category.
SKILL_CATEGORY_ORDER = ("General", "Fighting", "Technical", "Social", "Magic")


class ShadowrunAnarchyBuilder:
    """Transform an `AnarchyCharacter` into a render-ready view-model dict."""

    def __init__(self, character: AnarchyCharacter):
        self.c = character

    def _attr_map(self) -> dict[str, int]:
        return {
            "STR": self.c.strength,
            "AGI": self.c.agility,
            "WIL": self.c.willpower,
            "LOG": self.c.logic,
            "CHA": self.c.charisma,
        }

    def _metatype_info(self) -> dict[str, Any]:
        return METATYPE_RULES.get(self.c.metatype, METATYPE_RULES[Metatype.HUMAN])

    def _compute_essence(self) -> dict[str, Any]:
        lost = sum(max(0.0, float(a.essence_cost or 0.0)) for a in self.c.shadow_amps)
        current = round(max(0.0, 6.0 - lost), 2)
        penalties: list[str] = []
        magic_cancel = 0
        heal_cancel = 0
        if current <= 5:
            magic_cancel += 1
        if current <= 4:
            heal_cancel += 1
        if current <= 3:
            magic_cancel += 1
        if current <= 2:
            heal_cancel += 1
        if magic_cancel:
            penalties.append(f"Cancel {magic_cancel} hit{'s' if magic_cancel > 1 else ''} on magic Tests")
        if heal_cancel:
            penalties.append(f"Cancel {heal_cancel} hit{'s' if heal_cancel > 1 else ''} on healing Tests")
        if current <= 1:
            penalties.append("Disadvantage on most social Tests")
        if current <= 0:
            penalties.append("Essence depleted (character dies)")

        # Display clean "6" or "3.5" instead of "6.0".
        display = f"{current:g}"
        return {
            "current": current,
            "lost": round(lost, 2),
            "display": display,
            "penalties": penalties,
            "is_critical": current <= 1,
        }

    def _collect_amp_modifiers(self) -> dict[str, Any]:
        rr_attr: dict[str, int] = {}
        rr_skill: dict[str, int] = {}
        rr_spec: dict[str, int] = {}
        armor_bonus = 0
        extra_light = 0
        extra_serious = 0
        unarmed_dv_bonus = 0
        mental_protection = 0

        for amp in self.c.shadow_amps:
            for eff in amp.effects:
                val = int(eff.value or 0)
                target_norm = (eff.target or "").strip().lower()
                if eff.kind == "rr_attr" and target_norm:
                    rr_attr[target_norm.upper()] = rr_attr.get(target_norm.upper(), 0) + val
                elif eff.kind == "rr_skill" and target_norm:
                    rr_skill[target_norm] = rr_skill.get(target_norm, 0) + val
                elif eff.kind == "rr_spec" and target_norm:
                    rr_spec[target_norm] = rr_spec.get(target_norm, 0) + val
                elif eff.kind == "armor_bonus":
                    armor_bonus += val
                elif eff.kind == "light_wound_box":
                    extra_light += val
                elif eff.kind == "serious_wound_box":
                    extra_serious += val
                elif eff.kind == "unarmed_dv_bonus":
                    unarmed_dv_bonus += val
                elif eff.kind == "mental_protection":
                    mental_protection += val

        return {
            "rr_attr": rr_attr,
            "rr_skill": rr_skill,
            "rr_spec": rr_spec,
            # Rules p. 64: Armor +1 (max +1), +1 light box (max +1), +1 serious box (max +1)
            "armor_bonus": min(1, max(0, armor_bonus)),
            "extra_light": min(1, max(0, extra_light)),
            "extra_serious": min(1, max(0, extra_serious)),
            "unarmed_dv_bonus": min(2, max(0, unarmed_dv_bonus)),
            "mental_protection": max(0, mental_protection),
        }

    def _compute_wounds(self, mods: dict[str, Any]) -> dict[str, Any]:
        light_max = 2 + mods["extra_light"]
        serious_max = 1 + mods["extra_serious"]

        # Normalize box lists to the derived box count without losing checked state.
        light_boxes = [
            bool(self.c.wounds.light[i]) if i < len(self.c.wounds.light) else False
            for i in range(light_max)
        ]
        serious_boxes = [
            bool(self.c.wounds.serious[i]) if i < len(self.c.wounds.serious) else False
            for i in range(serious_max)
        ]
        incap = bool(self.c.wounds.incapacitated)
        stim = bool(self.c.wounds.stim_patch_active)

        light_checked = sum(light_boxes)
        serious_checked = sum(serious_boxes)

        status_text = "Healthy"
        status_severity = "ok"
        penalty_note = ""
        if incap:
            status_text = "Incapacitated"
            status_severity = "critical"
            penalty_note = "Cannot act or attempt any Test. Stabilize if dying."
        elif serious_checked > 0:
            status_text = f"{serious_checked} Serious"
            status_severity = "warning" if stim else "danger"
            penalty_note = (
                "Stim patch active — serious wound Disadvantage suppressed (+1 light wound after 15 min)."
                if stim
                else "Disadvantage on all Tests until serious wounds are healed."
            )
        elif light_checked > 0:
            status_text = f"{light_checked} Light"
            status_severity = "warning"
            penalty_note = "Disadvantage until end of next narration after taking a light wound."

        # Precalculated Wound Thresholds (p. 70)
        amp_armor = mods["armor_bonus"]
        str_val = self.c.strength
        wil_val = self.c.willpower
        mental_prot = mods["mental_protection"]

        def _row(label: str, base: int) -> dict[str, Any]:
            return {
                "label": label,
                "light": base,
                "serious": base + 3,
                "incap": base + 6,
            }

        no_armor_label = f"No armor (+{amp_armor} Amp)" if amp_armor else "No armor"
        thresholds = [_row(no_armor_label, str_val + amp_armor)]

        main_armor = next((a for a in self.c.armor if a.slot == "main"), None)
        alt_armor = next((a for a in self.c.armor if a.slot == "alternate"), None)

        if main_armor is not None:
            tot = main_armor.rating + amp_armor
            thresholds.append(
                _row(f"Main armor ({main_armor.name} {main_armor.rating})", str_val + tot)
            )
        if alt_armor is not None:
            tot = alt_armor.rating + amp_armor
            thresholds.append(
                _row(f"Alternate armor ({alt_armor.name} {alt_armor.rating})", str_val + tot)
            )

        mental_label = f"Mental (+{mental_prot} prot.)" if mental_prot else "Mental"
        thresholds.append(_row(mental_label, wil_val + mental_prot))

        return {
            "light_boxes": light_boxes,
            "serious_boxes": serious_boxes,
            "incapacitated": incap,
            "stim_patch_active": stim,
            "status_text": status_text,
            "status_severity": status_severity,
            "penalty_note": penalty_note,
            "thresholds": thresholds,
            "amp_armor_bonus": amp_armor,
        }

    def _compute_skills(self, attrs: dict[str, int], mods: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, sk in enumerate(self.c.skills):
            attr_code = (sk.attribute or "AGI").upper()
            attr_val = attrs.get(attr_code, 0)
            skill_key = sk.name.strip().lower()

            base_rr = min(
                3,
                mods["rr_attr"].get(attr_code, 0) + mods["rr_skill"].get(skill_key, 0),
            )
            specs_out: list[dict[str, Any]] = []
            for s_idx, sp in enumerate(sk.specializations):
                sp_attr = (sp.attribute or attr_code).upper()
                sp_attr_val = attrs.get(sp_attr, 0)
                spec_key = sp.name.strip().lower()
                # Match either bare spec name ("pistols") or qualified ("ranged weapons (pistols)")
                qualified_key = f"{skill_key} ({spec_key})"
                sp_rr = min(
                    3,
                    mods["rr_attr"].get(sp_attr, 0)
                    + mods["rr_skill"].get(skill_key, 0)
                    + mods["rr_spec"].get(spec_key, 0)
                    + mods["rr_spec"].get(qualified_key, 0),
                )
                specs_out.append({
                    "index": s_idx,
                    "name": sp.name,
                    "attribute": sp_attr,
                    "bonus": sp.bonus,
                    "dp": sk.rating + sp.bonus + sp_attr_val,
                    "rr": sp_rr,
                })

            out.append({
                "index": idx,
                "name": sk.name,
                "category": sk.category,
                "rating": sk.rating,
                "attribute": attr_code,
                "alt_attributes": [a.upper() for a in sk.alt_attributes],
                "dp": sk.rating + attr_val,
                "rr": base_rr,
                "specializations": specs_out,
                "example_uses": sk.example_uses,
                # Rules p. 60: Skills at rating 4+ also function as Knowledge Skills.
                "counts_as_knowledge": sk.rating >= 4,
            })
        return out

    def _eval_weapon_dv(self, raw_dv: str, is_unarmed: bool, unarmed_bonus: int) -> str:
        text = (raw_dv or "").strip()
        m = _STR_FORMULA_RE.match(text)
        if m:
            sign, offset_s = m.group(1), m.group(2)
            offset = int(offset_s) if offset_s else 0
            if sign == "-":
                offset = -offset
            val = self.c.strength + offset + (unarmed_bonus if is_unarmed else 0)
            return str(max(0, val))
        if is_unarmed and unarmed_bonus:
            try:
                return str(int(text) + unarmed_bonus)
            except ValueError:
                pass
        return text or str(self.c.strength)

    def _compute_weapons(self, mods: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, w in enumerate(self.c.weapons):
            is_unarmed = w.weapon_type.lower() == "unarmed" or w.name.strip().lower() == "unarmed"
            dv_val = self._eval_weapon_dv(w.dv, is_unarmed, mods["unarmed_dv_bonus"])
            out.append({
                "index": idx,
                "id": w.id,
                "name": w.name,
                "weapon_type": w.weapon_type,
                "dv_raw": w.dv,
                "dv_computed": dv_val,
                "ranges": [
                    ("Close", w.range_close),
                    ("Short", w.range_short),
                    ("Med", w.range_medium),
                    ("Long", w.range_long),
                ],
                "skill": w.skill,
                "specialization": w.specialization,
                "notes": w.notes,
                "is_custom": w.is_custom,
            })
        return out

    def _compute_nuyen_value(self) -> dict[str, int]:
        """Compute total nuyen invested across character traits (cheat sheet p. 85)."""
        caps: dict[str, int] = self._metatype_info()["caps"]
        attrs = self._attr_map()

        attr_cost = 0
        for code, val in attrs.items():
            cap = caps.get(code, 4)
            # Base 1 is free; points 2..(cap-1) cost 10,000¥; final point (cap) costs 20,000¥.
            if val <= 1:
                continue
            if val >= cap:
                attr_cost += max(0, cap - 2) * 10_000 + 20_000
                if val > cap:
                    attr_cost += (val - cap) * 20_000
            else:
                attr_cost += (val - 1) * 10_000

        skill_cost = 0
        spec_cost = 0
        for sk in self.c.skills:
            r = sk.rating
            skill_cost += min(r, 5) * 2_500 + max(0, r - 5) * 5_000
            spec_cost += len(sk.specializations) * 2_500

        knowledge_cost = len([k for k in self.c.knowledge_skills if k.strip()]) * 2_500
        amp_cost = sum(max(0, a.rating) * 5_000 for a in self.c.shadow_amps)
        weapon_cost = 0
        for w in self.c.weapons:
            wt = w.weapon_type.lower()
            if wt == "unarmed" or w.name.strip().lower() == "unarmed":
                continue
            weapon_cost += 5_000 if "spec" in wt else 2_500
        armor_cost = sum(max(0, ar.rating) * 2_500 for ar in self.c.armor)
        spell_cost = len(self.c.spells) * 5_000
        gear_cost = sum(max(0, eq.cost) for eq in self.c.equipment)

        total = (
            attr_cost + skill_cost + spec_cost + knowledge_cost
            + amp_cost + weapon_cost + armor_cost + spell_cost + gear_cost
        )
        return {
            "attributes": attr_cost,
            "skills": skill_cost + spec_cost + knowledge_cost,
            "shadow_amps": amp_cost,
            "gear_and_spells": weapon_cost + armor_cost + spell_cost + gear_cost,
            "total": total,
        }

    def build(self) -> dict[str, Any]:
        attrs = self._attr_map()
        meta = self._metatype_info()
        caps: dict[str, int] = meta["caps"]
        essence = self._compute_essence()
        mods = self._collect_amp_modifiers()
        wounds = self._compute_wounds(mods)
        skills = self._compute_skills(attrs, mods)
        weapons = self._compute_weapons(mods)
        nuyen_audit = self._compute_nuyen_value()

        is_awakened = any(a.amp_type == AmpType.AWAKENED for a in self.c.shadow_amps) or bool(self.c.spells)
        sustained_count = sum(1 for sp in self.c.spells if sp.duration == "S" and sp.sustained_active)

        active_keywords = [k for k in self.c.keywords if k and k.strip()]

        return {
            "system_family": "sra2",
            "style_flags": {
                "show_phb_toggle": False,
                "is_awakened": is_awakened,
            },
            "top_bar": {
                "name": self.c.name,
                "metatype": self.c.metatype.value,
                "racial_quality": meta["racial_quality"],
                "keywords_summary": " · ".join(active_keywords[:3]) if active_keywords else self.c.metatype.value,
                "edge_current": self.c.edge_current,
                "edge_base": self.c.edge_base,
                "essence_display": essence["display"],
                "essence_critical": essence["is_critical"],
                "wound_status": wounds["status_text"],
                "wound_severity": wounds["status_severity"],
                "nuyen": self.c.nuyen,
            },
            "attributes": [
                {
                    "code": code,
                    "field": field,
                    "label": label,
                    "value": attrs[code],
                    "max": caps[code],
                }
                for code, field, label in (
                    ("STR", "strength", "Strength"),
                    ("AGI", "agility", "Agility"),
                    ("WIL", "willpower", "Willpower"),
                    ("LOG", "logic", "Logic"),
                    ("CHA", "charisma", "Charisma"),
                )
            ],
            "essence": essence,
            "edge": {
                "current": self.c.edge_current,
                "base": self.c.edge_base,
                "metatype_default": meta["edge_base"],
            },
            "wounds": wounds,
            "skills": skills,
            "skill_categories": list(SKILL_CATEGORY_ORDER),
            "shadow_amps": [
                {
                    "index": idx,
                    "id": amp.id,
                    "name": amp.name,
                    "amp_type": amp.amp_type.value,
                    "rating": amp.rating,
                    "cost_nuyen": amp.rating * 5_000,
                    "essence_cost": amp.essence_cost,
                    "essence_display": f"{amp.essence_cost:g}" if amp.essence_cost else "—",
                    "effects": [e.model_dump() for e in amp.effects],
                    "body_md": amp.body_md,
                    "is_custom": amp.is_custom,
                }
                for idx, amp in enumerate(self.c.shadow_amps)
            ],
            "weapons": weapons,
            "spells": [
                {
                    "index": idx,
                    "id": sp.id,
                    "name": sp.name,
                    "category": sp.category,
                    "subtype": sp.subtype,
                    "duration": sp.duration,
                    "threshold": sp.threshold,
                    "sustained_active": sp.sustained_active,
                    "notes": sp.notes,
                    "is_custom": sp.is_custom,
                }
                for idx, sp in enumerate(self.c.spells)
            ],
            "sustained_spell_count": sustained_count,
            "armor": [
                {
                    "index": idx,
                    "id": ar.id,
                    "name": ar.name,
                    "rating": ar.rating,
                    "slot": ar.slot,
                    "notes": ar.notes,
                    "is_custom": ar.is_custom,
                }
                for idx, ar in enumerate(self.c.armor)
            ],
            "equipment": [
                {
                    "index": idx,
                    "id": eq.id,
                    "name": eq.name,
                    "category": eq.category,
                    "cost": eq.cost,
                    "notes": eq.notes,
                    "is_custom": eq.is_custom,
                }
                for idx, eq in enumerate(self.c.equipment)
            ],
            "keywords": list(self.c.keywords),
            "dispositions": list(self.c.dispositions),
            "cues": list(self.c.cues),
            "knowledge_skills": list(self.c.knowledge_skills),
            "nuyen": self.c.nuyen,
            "nuyen_audit": nuyen_audit,
            "bio": self.c.bio,
            "risk_table": RISK_TABLE,
            "glitch_scale": GLITCH_SCALE,
        }
