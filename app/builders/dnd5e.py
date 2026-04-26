"""
AI Helper Docstring
Purpose: Concrete execution of the Builder pattern for D&D 2014 logic.
Interactions:
- `app.builders.base.py`: Inherits `BaseSheetBuilder` functionality.
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
