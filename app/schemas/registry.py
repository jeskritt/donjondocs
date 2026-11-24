"""
AI Helper Docstring
Purpose: Central schema dispatcher mapping `(SheetStyle, character_data dict)` to the right Pydantic character model (`Character` for 5e-family systems, `AnarchyCharacter` for Shadowrun: Anarchy 2.0). Keeps every caller free of scattered `if style == ...` schema switches.
Interactions:
- `app.rule_systems.{SheetStyle, SystemFamily, system_family_for}`: determines family.
- `app.schemas.char_sheet_specific.Character`: 5e-family model.
- `app.schemas.shadowrun_anarchy.AnarchyCharacter`: Shadowrun: Anarchy 2.0 model.
- Called by `app.services.character_service`, `app.services.backup_service`, and `app.ui.pages.character_sheet`.
"""

from __future__ import annotations

from typing import Union

from app.rule_systems import SheetStyle, SystemFamily, system_family_for
from app.schemas.char_sheet_specific import Character
from app.schemas.shadowrun_anarchy import AnarchyCharacter

CharacterModel = Union[Character, AnarchyCharacter]


def parse_character(style: SheetStyle, data: dict) -> CharacterModel:
    """Validate and instantiate the appropriate Pydantic character model for `style`."""
    family = system_family_for(style)
    if family == SystemFamily.SHADOWRUN_ANARCHY_2:
        return AnarchyCharacter(**data)
    return Character(**data)
