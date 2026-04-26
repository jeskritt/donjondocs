"""Rule system identifiers shared across models, schemas, and services.

This module is a dependency-free leaf so both the ORM (`app.models`) and
the Pydantic schemas (`app.schemas`) can import `SheetStyle` without
creating a reverse `models -> schemas` import.
"""

import enum


class SheetStyle(str, enum.Enum):
    """The style of the character sheet."""

    DND5E = "Dungeons & Dragons 5e"
    A5E = "Level Up: Advanced 5e"
    UM5 = "Ultramodern 5e"
    SHADOWDARK = "Shadowdark RPG"
    GENEFUNK = "GeneFunk 2090"
    CARBON = "Carbon 2185"
