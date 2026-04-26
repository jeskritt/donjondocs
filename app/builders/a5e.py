"""
AI Helper Docstring
Purpose: Concrete Builder for Advanced 5e (Level Up). Mutes alignments and flaws in UI descriptions.
Interactions:
- `app.builders.base.py`: Inherits from `BaseSheetBuilder`.
"""

from app.builders.base import BaseSheetBuilder

class A5eBuilder(BaseSheetBuilder):
    def build_details(self):
        super().build_details()
        # A5E has everything generally, but some specific description suppressions per prompt
        self.view_data['details']['alignment_suppressed'] = True
        self.view_data['details']['ideals_suppressed'] = True
        self.view_data['details']['bonds_suppressed'] = True
        self.view_data['details']['flaws_suppressed'] = True
        return self

    def build_combat_stats(self):
        super().build_combat_stats()
        self.view_data['combat']['show_strife'] = True
        return self
