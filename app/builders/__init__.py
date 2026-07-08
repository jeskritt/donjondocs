from app.builders.base import BaseSheetBuilder
from app.builders.dnd5e import DnD2014Builder
from app.builders.a5e import A5eBuilder
from app.builders.shadowdark import ShadowdarkBuilder
from app.builders.um5 import Um5Builder
from app.schemas.char_sheet_global import SheetStyle
from app.schemas.char_sheet_specific import Character

_BUILDERS: dict[SheetStyle, type[BaseSheetBuilder]] = {
    SheetStyle.DND5E: DnD2014Builder,
    SheetStyle.A5E: A5eBuilder,
    SheetStyle.SHADOWDARK: ShadowdarkBuilder,
    SheetStyle.UM5: Um5Builder,
}


def get_builder(character: Character) -> BaseSheetBuilder:
    try:
        cls = _BUILDERS[character.style]
    except KeyError as e:
        raise NotImplementedError(
            f"SheetStyle {character.style!r} has no builder yet"
        ) from e
    return cls(character)
