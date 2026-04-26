"""
AI Helper Docstring
Purpose: Interface and Factory for interpreting character data into Frontend-ready View models via the `BaseSheetBuilder`. Includes armor-driven AC computation (`_compute_ac`), archetype-aware class display, defense fields (resistances/immunities/vulnerabilities), and extra magic resource passthrough.
Interactions:
- `app.schemas.char_sheet_specific.py`: The factory intakes `Character` payloads.
- `app.ui.pages.character_sheet.py`: Outputs normalized dictionaries dictating exactly how NiceGUI cards should render.
"""

from typing import Dict, Any

from app.schemas.char_sheet_specific import Character, AbilityScore
from app.schemas.char_sheet_global import SheetStyle

_PROF_MULT = {0: 0.0, 1: 0.5, 2: 1.0, 3: 2.0}

# Default saves for all 6 attributes when a character has none saved yet
_DEFAULT_ATTRS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]


def _score_total(s: AbilityScore) -> int:
    return s.base + s.racial + s.level + s.misc


def _modifier(total: int) -> int:
    return (total - 10) // 2


def _fmt_mod(mod: int) -> str:
    return f"+{mod}" if mod >= 0 else str(mod)


def _compute_ac(character: Character) -> dict:
    """Derive total AC from (equipped armor, equipped shield, DEX, misc).

    When an armor item is equipped, it locks the base: the wearer's manually
    set `c.ac.base` no longer applies, and the DEX contribution is clamped by
    the armor's dex_cap (None = uncapped). Shields stack on top of whatever
    is already there. With nothing equipped, the user's `c.ac.base` is the
    floor so unarmored characters (monks, Shadowdark) still render correctly.
    """
    dex_mod = _modifier(_score_total(character.dex_score))

    equipped_armor = next(
        (i for i in character.inventory
         if i.equipped and i.item_type == "armor" and not i.is_shield),
        None,
    )
    equipped_shield = next(
        (i for i in character.inventory if i.equipped and i.is_shield),
        None,
    )

    if equipped_armor and equipped_armor.base_ac is not None:
        base = equipped_armor.base_ac
        dex_contrib = dex_mod if equipped_armor.dex_cap is None else min(dex_mod, equipped_armor.dex_cap)
        armor_locked = True
        armor_name = equipped_armor.name
    else:
        base = character.ac.base
        dex_contrib = dex_mod
        armor_locked = False
        armor_name = None

    shield_bonus = equipped_shield.base_ac if (equipped_shield and equipped_shield.base_ac is not None) else 0
    misc = character.ac.misc
    total = base + dex_contrib + shield_bonus + misc

    return {
        "total": total,
        "base": base,
        "dex": dex_contrib,
        "shield": shield_bonus,
        "misc": misc,
        "armor_locked": armor_locked,
        "armor_name": armor_name,
        "shield_name": equipped_shield.name if equipped_shield else None,
    }


class BaseSheetBuilder:
    def __init__(self, character: Character):
        self.character = character
        self.view_data: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _attr_totals(self) -> dict[str, int]:
        c = self.character
        return {
            "STR": _score_total(c.str_score),
            "DEX": _score_total(c.dex_score),
            "CON": _score_total(c.con_score),
            "INT": _score_total(c.int_score),
            "WIS": _score_total(c.wis_score),
            "CHA": _score_total(c.cha_score),
        }

    def _attr_mods(self) -> dict[str, int]:
        return {k: _modifier(v) for k, v in self._attr_totals().items()}

    # ------------------------------------------------------------------
    # Build steps
    # ------------------------------------------------------------------

    def build_top_bar(self):
        c = self.character
        # Build display string with archetypes when present.
        # Single class: "Fighter (Champion)". Multi: "Fighter 3 (Champion) / Wizard 2 (Evoker)".
        if len(c.classes) == 1:
            only = c.classes[0]
            class_display = f"{only.name} ({only.archetype})" if only.archetype else only.name
        else:
            parts = []
            for ce in c.classes:
                label = f"{ce.name} {ce.level}"
                if ce.archetype:
                    label += f" ({ce.archetype})"
                parts.append(label)
            class_display = " / ".join(parts)

        ac_breakdown = _compute_ac(c)
        self.view_data['ac_breakdown'] = ac_breakdown

        self.view_data['top_bar'] = {
            'name': c.name,
            'race': f"{c.race.ancestry} {c.race.culture or ''}".strip(),
            'character_class': class_display,
            'level': c.level,
            'classes': [
                {
                    'name': ce.name,
                    'archetype': ce.archetype,
                    'level': ce.level,
                }
                for ce in c.classes
            ],
            'prof_bonus': f"+{c.prof_bonus}",
            'ac': ac_breakdown["total"],
            'hp_current': c.hp_current,
            'hp_max': c.hp_max,
            'initiative': _fmt_mod(c.initiative.base + c.initiative.misc),
            'speed': c.speed,
            'inspiration': c.inspiration,
            'conditions': c.conditions,
            'rest_options': ['Short Rest', 'Long Rest'],
        }
        return self

    def build_attributes(self):
        """Build the six ability scores with their saving throw data merged in.

        Saving throws are always 1-per-attribute. If the character has no saved
        saving_throws list (legacy characters), defaults to proficiency=0, misc=0
        so the save bonus equals just the ability modifier.
        """
        c = self.character

        # Build a map of attribute → save data (fallback to unproficient zero defaults)
        save_map = {st.attribute: st for st in c.saving_throws}

        scores = [
            ("STR", c.str_score),
            ("DEX", c.dex_score),
            ("CON", c.con_score),
            ("INT", c.int_score),
            ("WIS", c.wis_score),
            ("CHA", c.cha_score),
        ]

        attributes = []
        for label, s in scores:
            total = _score_total(s)
            mod = _modifier(total)

            st = save_map.get(label)
            save_prof = st.proficiency if st else 0
            save_misc = st.misc if st else 0
            save_bonus = int(c.prof_bonus * _PROF_MULT.get(save_prof, 0))
            save_total = mod + save_bonus + save_misc

            attributes.append({
                "label": label,
                "total": total,
                "modifier": mod,
                "base": s.base,
                "racial": s.racial,
                "level": s.level,
                "misc": s.misc,
                # Save data merged in — always in sync with the ability score
                "save_proficiency": save_prof,
                "save_misc": save_misc,
                "save_total": save_total,
            })

        self.view_data['attributes'] = attributes
        return self

    def build_skills_view(self):
        c = self.character
        mods = self._attr_mods()
        skills = []
        for sk in c.skills:
            attr_mod = mods.get(sk.attribute, 0)
            prof_bonus = int(c.prof_bonus * _PROF_MULT.get(sk.proficiency, 0))
            total = attr_mod + prof_bonus + sk.misc
            skills.append({
                "name": sk.name,
                "attribute": sk.attribute,
                "total": total,
                "proficiency": sk.proficiency,
                "misc": sk.misc,
                "notes": sk.notes,
            })
        self.view_data['skills'] = skills
        return self

    def build_combat_stats(self):
        c = self.character
        self.view_data['combat'] = {
            "saves": [],
            "defenses": [],
            "hp_temp": c.hp_temp,
            "exhaustion": c.exhaustion,
            "exhaustion_label": "Fatigue",
            "strife": c.strife,
            "show_strife": False,
            "resistances": c.resistances,
            "immunities": c.immunities,
            "vulnerabilities": c.vulnerabilities,
            # Per-class hit dice for HP / short-rest consumption. Empty list if
            # the character has no class entries with seeded hit dice.
            "hit_dice": [
                {
                    "class_name": ce.name,
                    "die": ce.hit_dice,
                    "current": ce.hit_dice_current if ce.hit_dice_current is not None else ce.level,
                    "maximum": ce.hit_dice_max if ce.hit_dice_max is not None else ce.level,
                }
                for ce in c.classes
                if ce.hit_dice
            ],
        }
        return self

    def build_features(self):
        c = self.character
        self.view_data['features'] = [
            {
                "name": a.name,
                "source": a.source,
                "description": a.description,
                "sub_abilities": [
                    {"name": s.name, "description": s.description, "effect": s.effect}
                    for s in a.sub_abilities
                ],
                "tracker": a.tracker.model_dump() if a.tracker else None,
            }
            for a in c.abilities
        ]
        return self

    def build_inventory(self):
        c = self.character
        self.view_data['inventory'] = [item.model_dump() for item in c.inventory]
        return self

    def build_actions(self):
        """Emit quick-reference actions with derived attack_bonus / attack_dc.

        For each CharacterAction, compute:
          attr_mod   = _modifier(score_for(attribute).total) if attribute set, else 0
          attack_bonus = attr_mod + (prof_bonus if proficient) + attack_misc
          attack_dc    = 8 + attr_mod + (prof_bonus if proficient) + dc_misc

        The show_attack_bonus / show_attack_dc flags are passed through; the UI
        decides whether to render the derived fields.
        """
        c = self.character
        mods = self._attr_mods()
        actions_view = []
        for a in c.actions:
            attr_mod = mods.get(a.attribute, 0) if a.attribute else 0
            prof = c.prof_bonus if a.proficient else 0
            attack_bonus = attr_mod + prof + a.attack_misc
            attack_dc = 8 + attr_mod + prof + a.dc_misc
            actions_view.append({
                "name": a.name,
                "attribute": a.attribute,
                "proficient": a.proficient,
                "damage": a.damage,
                "range": a.range,
                "notes": a.notes,
                "show_attack_bonus": a.show_attack_bonus,
                "show_attack_dc": a.show_attack_dc,
                "attack_bonus": attack_bonus,
                "attack_dc": attack_dc,
            })
        self.view_data['actions'] = actions_view
        return self

    def build_magic(self):
        """Emit `view_data['magic']` with derived spell_attack / spell_dc per resource.

        For each `MagicResource` on the character:
          attr_mod     = _modifier(score_for(attribute).total) if attribute set, else 0
          spell_attack = prof_bonus + attr_mod + spell_attack_misc
          spell_dc     = 8 + prof_bonus + attr_mod + spell_dc_misc

        Spells are emitted as-is (grouped under their resource_name on the UI side).
        """
        c = self.character
        mods = self._attr_mods()
        resources_view = []
        for r in c.magic_resources:
            attr_mod = mods.get(r.attribute, 0) if r.attribute else 0
            spell_attack = c.prof_bonus + attr_mod + r.spell_attack_misc
            spell_dc = 8 + c.prof_bonus + attr_mod + r.spell_dc_misc
            resources_view.append({
                "name": r.name,
                "source": r.source,
                "magic_type": r.magic_type.value if hasattr(r.magic_type, "value") else r.magic_type,
                "attribute": r.attribute,
                "spell_attack_total": spell_attack,
                "spell_dc_total": spell_dc,
                "current": r.current,
                "maximum": r.maximum,
                "extra_resource": r.extra_resource.model_dump() if r.extra_resource else None,
            })
        self.view_data['magic'] = {
            "resources": resources_view,
            "spells": [s.model_dump() for s in c.spells],
        }
        return self

    def build_combat_maneuvers(self):
        """Emit `view_data['combat_maneuvers']` as a dict with header stats and maneuver list.

        Computes maneuver DC (8 + prof + max(STR,DEX) + misc) and attack bonus
        (prof + max(STR,DEX) + misc), mirroring spell attack/DC on magic resources.

        Subclasses may override this to emit None when the rule system doesn't
        support combat maneuvers (e.g. DnD 5e, Shadowdark).
        """
        c = self.character
        mods = self._attr_mods()
        best_mod = max(mods.get("STR", 0), mods.get("DEX", 0))
        attack = c.prof_bonus + best_mod + c.maneuver_attack_misc
        dc = 8 + c.prof_bonus + best_mod + c.maneuver_dc_misc
        self.view_data['combat_maneuvers'] = {
            "maneuvers": [m.model_dump() for m in c.combat_maneuvers],
            "known_traditions": c.known_traditions,
            "maneuver_dc": dc,
            "maneuver_attack": attack,
            "exertion_current": c.exertion_current,
            "exertion_max": c.exertion_max,
            "maneuvers_known": c.maneuvers_known,
            "max_degree": c.max_degree,
        }
        return self

    def build_details(self):
        c = self.character
        self.view_data['details'] = {
            'destiny': c.destiny.model_dump() if c.destiny and c.destiny.name else None,
            'background': c.background,
            'size': c.size,
            'experience_points': c.experience_points,
            'personality': c.personality,
            'ideals': c.ideals,
            'bonds': c.bonds,
            'flaws': c.flaws,
            'appearance': c.appearance,
            'backstory': c.backstory,
            'age': c.age,
            'gender': c.gender,
            'height': c.height,
            'weight': c.weight,
            'eyes': c.eyes,
            'hair': c.hair,
            'skin': c.skin,
            'alignment': c.alignment,
            'title': c.title,
            'deity': c.deity,
        }
        return self

    def build_style_flags(self):
        """Per-style capability flags consumed by the UI layer.

        Defaults assume the D&D 5e / A5E family; ShadowdarkBuilder overrides
        those that don't apply (skill system, proficiency bonus).
        """
        self.view_data['style_flags'] = {
            'has_skills': True,
            'show_prof_bonus': True,
        }
        return self

    def build(self):
        self.build_top_bar()
        self.build_attributes()   # saves now embedded per attribute
        self.build_skills_view()
        self.build_combat_stats()
        self.build_features()
        self.build_actions()
        self.build_magic()
        self.build_combat_maneuvers()
        self.build_inventory()
        self.build_details()
        self.build_style_flags()
        return self.view_data


