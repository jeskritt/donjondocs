"""
AI Helper Docstring
Purpose: Concrete Builder for Shadowdark RPG ruleset. Explicitly overrides/nulls fields not relevant to its harsh, gritty OSR setting (destiny, inspiration).
Interactions:
- `app.builders.base.py`: Inherits from `BaseSheetBuilder`.
"""

from app.builders.base import BaseSheetBuilder

class ShadowdarkBuilder(BaseSheetBuilder):
    def build_top_bar(self):
        super().build_top_bar()
        # Inspiration doesn't exist in Shadowdark in the same way (typically luck tokens, but prompt says none)
        self.view_data['top_bar']['inspiration'] = None
        return self

    def build_details(self):
        super().build_details()
        # Null out destiny for SD
        self.view_data['details']['destiny'] = None
        return self

    def build_combat_maneuvers(self):
        # Shadowdark drops Combat Maneuvers entirely
        self.view_data['combat_maneuvers'] = None
        return self

    def build_style_flags(self):
        super().build_style_flags()
        self.view_data['style_flags']['has_skills'] = False
        self.view_data['style_flags']['show_prof_bonus'] = False
        return self
