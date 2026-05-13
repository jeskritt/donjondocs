"""
AI Helper Docstring
Purpose: SQLAlchemy ORM row for the Creature Catalog — a per-user-owned monster/NPC stat block with optional `is_public` flag making it readable by all authenticated peers. Authored as PHB-flavoured Markdown in `body_md`, with denormalised search metadata (size, type, CR, habitat) kept in dedicated columns so the catalog list query stays fast.
Interactions:
- `app.services.creature_service`: the only writer / authorised reader.
- `app.services.creature_io`: per-creature export envelope.
- `app.services.creature_parser`: best-effort extraction of metadata from `body_md`.
- `app.api.creature_routes`: thin REST surface that delegates to the service layer.
- `app.ui.pages.creatures`: NiceGUI catalog page; cards are styled via the `.phb` class, optionally with `.phb-cols-2` driven by the `columns` column.
"""

"""Creature catalog ORM model.

Mirrors the `CharacterAlly` shape but the parent is `users` (not
`characters`) and we add an `is_public` flag so a creator can share a
creature with other logged-in users without giving up ownership. The
visibility predicate is the same one `global_items_service` uses for
catalog vs user-owned globals: `(is_public == True) OR (owner_id == me)`.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


def _uuid() -> str:
    return str(uuid.uuid4())


class Creature(TimestampMixin, Base):
    """A user-authored creature stat block, optionally shared (is_public)."""

    __tablename__ = "creatures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Owner is required; copies always re-assign ownership to the copier. If
    # the user is deleted, their creatures go with them (cascade).
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # PHB-flavoured Markdown stat block. Seeded with the shared template on
    # create when the client doesn't supply a body.
    body_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Comma-separated free-text. UI multi-select validates against
    # CREATURE_TYPES; the column tolerates anything so an import from a
    # different schema doesn't lose data.
    creature_type: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # Single value from CREATURE_SIZES; column is permissive for the same reason.
    size: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    # String, not int — admits "1/8", "1/4", "1/2", "0".."30".
    challenge_rating: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    habitat: Mapped[str] = mapped_column(String(200), nullable=False, default="Any")
    # When True, every authenticated user can read; only owner/admin can edit.
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    # 1 or 2; drives the `.phb-cols-2` class on the rendered markdown.
    columns: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def __repr__(self) -> str:
        return f"<Creature {self.name!r} owner={self.owner_id} public={self.is_public}>"
