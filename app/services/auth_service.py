"""
AI Helper Docstring
Purpose: Core business logic function module validating Authentication pathways. Avoids tangling database actions strictly with HTTP endpoints.
Interactions:
- `app.security.py`: Imports token creation mechanics.
- `app.api.auth_routes.py`: Executed purely by router layers facing the public client mappings.
"""

"""Authentication service: login, register, token management."""

from datetime import datetime, timezone

from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest
from app.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.services._errors import ServiceError
from app.services.user_service import (
    find_user_by_email,
    find_user_by_id,
    find_user_by_username,
)


class AuthError(ServiceError):
    """Authentication error with a user-safe message."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message, status_code=status_code)


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Validate credentials and return the user.

    Raises:
        AuthError: If credentials are invalid or account is inactive.
    """
    user = await find_user_by_email(db, email)

    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password")

    if not user.is_active:
        raise AuthError("Account is deactivated")

    # Update last_login timestamp
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    return user


async def register_user(
    db: AsyncSession,
    data: RegisterRequest,
) -> User:
    """Register a new user account.

    Raises:
        AuthError: If registration is disabled or username/email already exists.
    """
    settings = get_settings()
    if not settings.ALLOW_REGISTRATION:
        raise AuthError("Registration is currently disabled", status_code=403)

    if await find_user_by_username(db, data.username) is not None:
        raise AuthError("Username already taken", status_code=409)

    if await find_user_by_email(db, data.email) is not None:
        raise AuthError("Email already registered", status_code=409)

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.STANDARD,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


def create_user_token(user: User) -> str:
    """Create a JWT access token for the given user."""
    return create_access_token(
        data={
            "sub": user.id,
            "role": user.role.value,
            "username": user.username,
        }
    )


async def get_user_from_token(
    db: AsyncSession,
    token: str,
) -> User:
    """Decode a JWT token and return the corresponding user.

    Raises:
        AuthError: If the token is invalid or the user doesn't exist.
    """
    try:
        payload = decode_token(token)
    except JWTError:
        raise AuthError("Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthError("Invalid token payload")

    user = await find_user_by_id(db, user_id)

    if user is None:
        raise AuthError("User not found")

    if not user.is_active:
        raise AuthError("Account is deactivated")

    return user
