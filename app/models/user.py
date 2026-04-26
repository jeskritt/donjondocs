"""
AI Helper Docstring
Purpose: The primary SQLAlchemy ORM User entity defining Auth rules, Email, Roles (Premium, Admin, Standard).
Interactions:
- One-to-many to `CharacterRecord` via `User.characters` / `CharacterRecord.owner` (cascade delete).
- Audit fields `created_at` / `updated_at` are inherited from `TimestampMixin`.
- Soft-delete via `is_active=False`; the user row is never removed.
"""

"""User model with role-based access control."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin
from app.user_roles import UserRole  # noqa: F401  (re-export for legacy importers)


class User(TimestampMixin, Base):
    """User account model.

    Audit fields (created_at, updated_at) are auto-managed by TimestampMixin.
    Soft-delete is implemented via is_active=False.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.STANDARD, nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None,
    )

    # Relationships
    characters: Mapped[list["CharacterRecord"]] = relationship(
        "CharacterRecord", back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"
