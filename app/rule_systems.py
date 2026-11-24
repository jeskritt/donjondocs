"""Rule system identifiers shared across models, schemas, and services.

This module is a dependency-free leaf so both the ORM (`app.models`) and
the Pydantic schemas (`app.schemas`) can import `SheetStyle` and
`SystemFamily` without creating a reverse `models -> schemas` import.
"""

import enum


class SheetStyle(str, enum.Enum):
    """The style of the character sheet."""

    DND5E = "Dungeons & Dragons 5e"
    A5E = "Level Up: Advanced 5e"
    UM5 = "Ultramodern 5e"
    VOIDRUNNER = "Voidrunner"
    SHADOWDARK = "Shadowdark RPG"
    SHADOWRUN_ANARCHY_2 = "Shadowrun: Anarchy 2.0"
    GENEFUNK = "GeneFunk 2090"
    CARBON = "Carbon 2185"


class SystemFamily(str, enum.Enum):
    """High-level mechanical family governing schema, builder, and UI dispatch.

    All 5e-derived systems share `Character` / `BaseSheetBuilder` / the 5e
    sheet card layout. Non-5e systems (starting with Shadowrun: Anarchy 2.0)
    get their own dedicated schema, builder, seeding, and UI card package.
    """

    DND5E = "5e"
    SHADOWRUN_ANARCHY_2 = "sra2"


def system_family_for(style: SheetStyle) -> SystemFamily:
    """Return the mechanical system family for a given `SheetStyle`."""
    if style == SheetStyle.SHADOWRUN_ANARCHY_2:
        return SystemFamily.SHADOWRUN_ANARCHY_2
    return SystemFamily.DND5E
