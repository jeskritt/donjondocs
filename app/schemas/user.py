"""
AI Helper Docstring
Purpose: Pydantic payload models (UserCreate, UserResponse). Ensures passwords aren't accidentally leaked out in HTTP responses.
Interactions:
- `app.services.user_service.py` receives and returns these instances safely over API websockets.
"""

"""User CRUD and profile management schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Admin: create a new user with any role."""

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.STANDARD


class UserUpdate(BaseModel):
    """Admin: update any user field (all optional)."""

    username: str | None = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    """Public user representation — never includes password hash."""

    id: str
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    """Self-service profile update — no role field allowed."""

    username: str | None = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    """Self-service password change — requires current password."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminResetPasswordRequest(BaseModel):
    """Admin: reset any user's password without knowing the current one."""

    new_password: str = Field(..., min_length=8, max_length=128)
