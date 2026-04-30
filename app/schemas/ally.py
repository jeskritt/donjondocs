"""
AI Helper Docstring
Purpose: Pydantic models for the per-character `CharacterAlly` rows — Create / Update payloads (used by services + API) and Read response.
Interactions:
- `app.services.ally_service`: input/output of every CRUD function.
- `app.api.character_routes`: validates inbound JSON and shapes outbound JSON.
- `app.services.character_io` (export/import): the export envelope serializes `Ally` instances; import re-validates against `AllyCreate`.
"""

"""Pydantic schemas for character allies / stat blocks."""

from datetime import datetime

from pydantic import BaseModel, Field


class AllyCreate(BaseModel):
    """Inbound payload to add a new ally."""

    name: str = Field(..., min_length=1, max_length=120)
    # Free text — UI offers Contact/Companion/Pet/Wildshape/User Defined as
    # quick-pick chips but anything is allowed.
    ally_type: str = Field(..., min_length=1, max_length=40)
    body_md: str = Field(default="")


class AllyUpdate(BaseModel):
    """Inbound payload to edit an existing ally — all fields optional."""

    name: str | None = Field(None, min_length=1, max_length=120)
    ally_type: str | None = Field(None, min_length=1, max_length=40)
    body_md: str | None = None


class Ally(BaseModel):
    """Outbound representation of a CharacterAlly row."""

    id: str
    character_id: str
    name: str
    ally_type: str
    body_md: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
