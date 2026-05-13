"""
AI Helper Docstring
Purpose: Pydantic schemas for `Creature` rows — `CreatureCreate` / `CreatureUpdate` payloads and `Creature` read response. Mirrors the Allies pattern but the parent is the User, not a CharacterRecord.
Interactions:
- `app.services.creature_service`: input/output of every CRUD function.
- `app.api.creature_routes`: validates inbound JSON and shapes outbound JSON.
- `app.services.creature_io`: the export envelope serialises a `Creature`; import re-validates against `CreatureCreate`.
"""

"""Pydantic schemas for creature catalog rows."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreatureBase(BaseModel):
    """Fields common to create + read.

    The string-valued metadata fields (`creature_type`, `size`,
    `challenge_rating`, `habitat`) are intentionally free-text at the
    schema layer; the UI validates against the canonical lists in
    `app.schemas.char_sheet_global` so foreign imports don't lose data.
    """

    name: str = Field(..., min_length=1, max_length=120)
    body_md: str = ""
    creature_type: str = Field(default="", max_length=120)
    size: str = Field(default="", max_length=20)
    challenge_rating: str = Field(default="", max_length=10)
    habitat: str = Field(default="Any", max_length=200)
    is_public: bool = False
    columns: int = Field(default=1, ge=1, le=2)


class CreatureCreate(CreatureBase):
    """Inbound payload to create a new creature."""


class CreatureUpdate(BaseModel):
    """Inbound payload to edit an existing creature — all fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    body_md: str | None = None
    creature_type: str | None = Field(default=None, max_length=120)
    size: str | None = Field(default=None, max_length=20)
    challenge_rating: str | None = Field(default=None, max_length=10)
    habitat: str | None = Field(default=None, max_length=200)
    is_public: bool | None = None
    columns: int | None = Field(default=None, ge=1, le=2)


class Creature(CreatureBase):
    """Outbound representation of a Creature row.

    `owner_username` is denormalised at the API layer (the route batches
    user lookups for the list endpoint and a single lookup for get/copy)
    so the catalog UI can render "Owned by: <name>" without an extra
    round-trip. Defaults to None when the route layer hasn't populated it
    — services / tests that build Creature responses straight from an
    ORM row are not required to fill it in.
    """

    id: str
    owner_id: str
    owner_username: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
