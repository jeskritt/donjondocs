"""
AI Helper Docstring
Purpose: Encapsulated logic processing user registry, password validations, and global fetching (limit, totals). Sets up the `UserServiceError` pattern.
Interactions:
- `app.api.user_routes.py` relies exclusively on these handlers to orchestrate administrative mutations.
"""

"""User management service: CRUD, password management, profile updates."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    ProfileUpdate,
)
from app.security import hash_password, verify_password
from app.services._errors import ServiceError


class UserServiceError(ServiceError):
    """User service error with a user-safe message."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code=status_code)


async def find_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch a user by ID, or None if not found."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by email, or None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def find_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Fetch a user by username, or None if not found."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    """Fetch a user by ID.

    Raises:
        UserServiceError: If user not found.
    """
    user = await find_user_by_id(db, user_id)
    if user is None:
        raise UserServiceError("User not found", status_code=404)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User:
    """Fetch a user by email.

    Raises:
        UserServiceError: If user not found.
    """
    user = await find_user_by_email(db, email)
    if user is None:
        raise UserServiceError("User not found", status_code=404)
    return user


async def list_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[User], int]:
    """List users with pagination.

    Returns:
        Tuple of (users list, total count).
    """
    # Get total count
    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar() or 0

    # Get paginated results
    result = await db.execute(
        select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
    )
    users = list(result.scalars().all())

    return users, total


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """Admin: create a new user with any role.

    Raises:
        UserServiceError: If username or email already exists.
    """
    # Check uniqueness
    if await find_user_by_username(db, data.username) is not None:
        raise UserServiceError("Username already taken", status_code=409)

    if await find_user_by_email(db, data.email) is not None:
        raise UserServiceError("Email already registered", status_code=409)

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user_id: str,
    data: UserUpdate,
) -> User:
    """Admin: update any user field.

    Raises:
        UserServiceError: If user not found or uniqueness violation.
    """
    user = await get_user_by_id(db, user_id)

    if data.username is not None and data.username != user.username:
        if await find_user_by_username(db, data.username) is not None:
            raise UserServiceError("Username already taken", status_code=409)
        user.username = data.username

    if data.email is not None and data.email != user.email:
        if await find_user_by_email(db, data.email) is not None:
            raise UserServiceError("Email already registered", status_code=409)
        user.email = data.email

    if data.role is not None:
        user.role = data.role

    if data.is_active is not None:
        user.is_active = data.is_active

    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: str) -> User:
    """Admin: soft-delete (deactivate) a user.

    Raises:
        UserServiceError: If user not found.
    """
    user = await get_user_by_id(db, user_id)
    user.is_active = False
    await db.flush()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """Self-service: change own password.

    Raises:
        UserServiceError: If current password is wrong.
    """
    if not verify_password(current_password, user.hashed_password):
        raise UserServiceError("Current password is incorrect")
    user.hashed_password = hash_password(new_password)
    await db.flush()


async def reset_password(
    db: AsyncSession,
    user_id: str,
    new_password: str,
) -> None:
    """Admin: reset any user's password (no current password needed).

    Raises:
        UserServiceError: If user not found.
    """
    user = await get_user_by_id(db, user_id)
    user.hashed_password = hash_password(new_password)
    await db.flush()


async def update_profile(
    db: AsyncSession,
    user: User,
    data: ProfileUpdate,
) -> User:
    """Self-service: update own profile (no role change allowed).

    Raises:
        UserServiceError: If uniqueness violation.
    """
    if data.username is not None and data.username != user.username:
        if await find_user_by_username(db, data.username) is not None:
            raise UserServiceError("Username already taken", status_code=409)
        user.username = data.username

    if data.email is not None and data.email != user.email:
        if await find_user_by_email(db, data.email) is not None:
            raise UserServiceError("Email already registered", status_code=409)
        user.email = data.email

    await db.flush()
    await db.refresh(user)
    return user


async def get_user_count(db: AsyncSession) -> int:
    """Get total user count (for dashboard stats)."""
    result = await db.execute(select(func.count(User.id)))
    return result.scalar() or 0
