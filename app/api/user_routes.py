"""
AI Helper Docstring
Purpose: REST router handling User account lifecycles (Profile checks, updates, Admin capabilities).
Interactions:
- `app.api.deps.py`: Extremely reliant on `.get_admin_user` and `.get_current_active_user`.
- `app.services.user_service.py`: Triggers service functions to modify roles or update hashed passwords.
"""

"""User management API routes.

Admin routes:
    GET    /api/users              — list all users
    GET    /api/users/{id}         — get user detail
    POST   /api/users              — create user with any role
    PUT    /api/users/{id}         — update user (role, email, etc.)
    DELETE /api/users/{id}         — soft-delete (deactivate) user
    POST   /api/users/{id}/reset-password — reset user's password

Self-service routes:
    PUT    /api/users/me                  — update own profile
    POST   /api/users/me/change-password  — change own password
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.user import (
    AdminResetPasswordRequest,
    ChangePasswordRequest,
    ProfileUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import (
    change_password,
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    reset_password,
    update_profile,
    update_user,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Self-service routes (must be defined BEFORE /{user_id} to avoid conflicts)
# ---------------------------------------------------------------------------

@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    data: ProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update own profile (username, email). Cannot change role."""
    return await update_profile(db, current_user, data)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    data: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Change own password. Requires current password."""
    await change_password(db, current_user, data.current_password, data.new_password)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[UserResponse])
async def admin_list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Admin: list all users with pagination."""
    users, _total = await list_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def admin_get_user(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
):
    """Admin: get a single user by ID."""
    return await get_user_by_id(db, user_id)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
):
    """Admin: create a new user with any role."""
    return await create_user(db, data)


@router.put("/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: str,
    data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
):
    """Admin: update any user field (role, email, username, is_active)."""
    return await update_user(db, user_id, data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
):
    """Admin: soft-delete (deactivate) a user."""
    await delete_user(db, user_id)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
async def admin_reset_password(
    request: Request,
    user_id: str,
    data: AdminResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
):
    """Admin: reset any user's password (no current password needed)."""
    await reset_password(db, user_id, data.new_password)
