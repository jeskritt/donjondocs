"""Authenticated-user context — the auth-boundary DTO.

A frozen snapshot of the fields services need to make authorization
decisions, built from a DB-verified `User` at the request boundary.
Decoupling services from the ORM model keeps the trust model explicit:
anything accepting a `UserContext` was produced by code that verified
identity, not forged client-side.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.user_roles import UserRole

if TYPE_CHECKING:
    from app.models.user import User


@dataclass(frozen=True)
class UserContext:
    """DB-verified identity for authorization decisions."""

    id: str
    role: UserRole
    username: str
    email: str
    is_active: bool

    @classmethod
    def from_user(cls, user: "User") -> "UserContext":
        return cls(
            id=user.id,
            role=user.role,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
        )
