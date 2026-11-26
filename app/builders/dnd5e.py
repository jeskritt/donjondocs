"""
AI Helper Docstring
Purpose: Concrete execution of the Builder pattern for D&D 5e (2014 / SRD 5.1 and 2024 / SRD 5.2) logic.
Interactions:
- `app.builders.base.py`: Inherits `BaseSheetBuilder` functionality.
- `app.builders.__init__.py`: Dispatches `SheetStyle.DND5E` (`DnD2014Builder`) and `SheetStyle.DND5E_2024` (`DnD2024Builder`).
"""

from app.builders.base import BaseSheetBuilder


class DnD2014Builder(BaseSheetBuilder):
    def build_details(self):
        super().build_details()
        # Drop Destiny
        self.view_data['details']['destiny'] = None
        return self

    def build_combat_stats(self):
        super().build_combat_stats()
        # Rename fatigue label to Exhaustion (D&D 5e terminology)
        self.view_data['combat']['fatigue_label'] = 'Exhaustion'
        self.view_data['combat']['exhaustion_label'] = 'Exhaustion'
        return self

    def build_combat_maneuvers(self):
        # DnD 5e does not use Combat Maneuvers (A5e only)
        self.view_data['combat_maneuvers'] = None
        return self


def default_weapon_mastery_limit(character) -> int:
    """Compute the default 2024 D&D 5e Weapon Mastery cap from class levels.

    SRD 5.2 scaling:
    - Fighter: 3 (L1–3), 4 (L4–9), 5 (L10–15), 6 (L16+)
    - Barbarian: 2 (L1–3), 3 (L4–9), 4 (L10+)
    - Paladin / Ranger / Rogue: 2
    - Other classes: 0 (can still be overridden per-character, e.g. Weapon Master feat).
    """
    total = 0
    for ce in getattr(character, "classes", []) or []:
        cname = (ce.name or "").strip().lower()
        lvl = int(ce.level or 1)
        if cname == "fighter":
            total += 6 if lvl >= 16 else (5 if lvl >= 10 else (4 if lvl >= 4 else 3))
        elif cname == "barbarian":
            total += 4 if lvl >= 10 else (3 if lvl >= 4 else 2)
        elif cname in {"paladin", "ranger", "rogue"}:
            total += 2
    return total


class DnD2024Builder(DnD2014Builder):
    """Builder for D&D 5e (2024 / SRD 5.2) sheets.

    Shares the core 5e view structure with `DnD2014Builder` and adds lightweight
    2024 terminology/rules hints (Species label, Weapon Mastery tracking, and
    2024 Exhaustion penalty tooltip).
    """

    def build_combat_stats(self):
        super().build_combat_stats()
        self.view_data['combat']['exhaustion_tooltip'] = (
            "2024 rules: Each level imposes −2 to D20 Tests and −5 ft Speed (6 = Death)."
        )
        return self

    def build_style_flags(self):
        super().build_style_flags()
        self.view_data['style_flags']['species_label'] = 'Species'
        self.view_data['style_flags']['show_weapon_mastery'] = True
        self.view_data['style_flags']['weapon_mastery_default_limit'] = default_weapon_mastery_limit(self.character)
        return self
