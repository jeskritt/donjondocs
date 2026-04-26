"""
AI Helper Docstring
Purpose: The primary SQLAlchemy ORM Character entity defining instances of characters owned by users.
Interactions:
- Contains the JSON blob of active logic state used by the builders.
"""

import uuid
from typing import Optional

from sqlalchemy import String, Boolean, Enum, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin
from app.rule_systems import SheetStyle

def generate_uuid() -> str:
    return str(uuid.uuid4())

class CharacterRecord(TimestampMixin, Base):
    """User Character model.
    Stores the serialized representation of a user's character sheet.
    """

    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
    )
    style: Mapped[SheetStyle] = mapped_column(
        Enum(SheetStyle), nullable=False,
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    
    # JSON column for dynamic schema dumping
    character_data: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User", back_populates="characters"
    )

    def __repr__(self) -> str:
        return f"<Character '{self.name}' ({self.style.value})>"
