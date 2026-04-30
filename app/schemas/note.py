"""
AI Helper Docstring
Purpose: Pydantic models for the per-character `CharacterNote` rows — Create / Update payloads (used by services + API) and Read response.
Interactions:
- `app.services.note_service`: input/output of every CRUD function.
- `app.api.character_routes`: validates inbound JSON and shapes outbound JSON.
- `app.services.character_io` (export/import): the export envelope serializes `Note` instances; import re-validates against `NoteCreate`.
"""

"""Pydantic schemas for character notes."""

from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    """Inbound payload to add a new note."""

    title: str = Field(..., min_length=1, max_length=200)
    body_md: str = Field(default="")


class NoteUpdate(BaseModel):
    """Inbound payload to edit an existing note — all fields optional."""

    title: str | None = Field(None, min_length=1, max_length=200)
    body_md: str | None = None


class Note(BaseModel):
    """Outbound representation of a CharacterNote row."""

    id: str
    character_id: str
    title: str
    body_md: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
