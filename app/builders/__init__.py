from typing import Protocol

from app.builders.base import BaseSheetBuilder
from app.builders.dnd5e import DnD2014Builder, DnD2024Builder
from app.builders.a5e import A5eBuilder
from app.builders.shadowdark import ShadowdarkBuilder
from app.builders.shadowrun_anarchy import ShadowrunAnarchyBuilder
from app.builders.um5 import Um5Builder
from app.builders.voidrunner import VoidrunnerBuilder
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.registry import CharacterModel


class SheetBuilder(Protocol):
    def build(self) -> dict: ...


_BUILDERS: dict[SheetStyle, type] = {
    SheetStyle.DND5E: DnD2014Builder,
    SheetStyle.DND5E_2024: DnD2024Builder,
    SheetStyle.A5E: A5eBuilder,
    SheetStyle.SHADOWDARK: ShadowdarkBuilder,
    SheetStyle.UM5: Um5Builder,
    SheetStyle.VOIDRUNNER: VoidrunnerBuilder,
    SheetStyle.SHADOWRUN_ANARCHY_2: ShadowrunAnarchyBuilder,
}


def get_builder(character: CharacterModel) -> SheetBuilder:
    try:
        cls = _BUILDERS[character.style]
    except KeyError as e:
        raise NotImplementedError(
            f"SheetStyle {character.style!r} has no builder yet"
        ) from e
    return cls(character)
