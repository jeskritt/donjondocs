"""RBAC roles — dep-free leaf module.

Kept separate from app.models.user so non-ORM callers (UI pages, services,
schemas) can reference the enum without importing the SQLAlchemy model.
"""

import enum


class UserRole(str, enum.Enum):
    """User roles for RBAC."""

    ADMIN = "admin"
    STANDARD = "standard"
    PREMIUM = "premium"
