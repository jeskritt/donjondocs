"""
AI Helper Docstring
Purpose: SQLAlchemy ORM rows hung off a `CharacterRecord` that are too big or too dynamic for the JSON blob — currently allies/stat-blocks and free-form notes. Each addon row is independently CRUD-able and cascades on character delete.
Interactions:
- `app.models.character.CharacterRecord`: parent. The FK has `ondelete=CASCADE` so deleting a character takes its allies and notes with it.
- `app.services.ally_service`, `app.services.note_service`: only writers.
- `app.services.character_io`: per-character export envelope packs allies/notes alongside `character_data`.
- `app.services.backup_service`: includes both tables in the global backup envelope.
"""

"""Per-character relational addons: allies (stat blocks) and notes.

These tables exist instead of new fields on `character_data` because they
are independently sortable, edited one-at-a-time, and benefit from
DB-side timestamps. Their bodies hold Markdown text that the UI renders
via `ui.markdown`.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


def _uuid() -> str:
    return str(uuid.uuid4())


class CharacterAlly(TimestampMixin, Base):
    """A named NPC, companion, pet, or stat block tied to a character."""

    __tablename__ = "character_allies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    character_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Free text. UI offers Contact / Companion / Pet / Wildshape / User Defined
    # as quick-pick chips but accepts anything.
    ally_type: Mapped[str] = mapped_column(String(40), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False, default="")

    character: Mapped["CharacterRecord"] = relationship(
        "CharacterRecord", back_populates="allies"
    )

    def __repr__(self) -> str:
        return f"<CharacterAlly {self.name!r} ({self.ally_type})>"


class CharacterNote(TimestampMixin, Base):
    """A free-form Markdown note tied to a character (session log, plot hook, etc.)."""

    __tablename__ = "character_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    character_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False, default="")

    character: Mapped["CharacterRecord"] = relationship(
        "CharacterRecord", back_populates="notes"
    )

    def __repr__(self) -> str:
        return f"<CharacterNote {self.title!r}>"
