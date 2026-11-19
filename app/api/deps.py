"""
AI Helper Docstring
Purpose: FastAPI Dependency Injection orchestrator. Resolves database sessions and active JWT tokens to provide Request context.
Interactions:
- `app.database.py`: Yields the `async_session_factory` instances for route usage.
- `app.api.*_routes.py`: Endpoints aggressively inject `get_current_user` and `get_admin_user`.
"""

"""FastAPI dependency injection functions."""

from typing import Annotated, Callable

from fastapi import Cookie, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.user import User, UserRole
from app.services.auth_service import AuthError, get_user_from_token


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Yield an async database session with auto-commit/rollback."""
    async with async_session_factory() as session:
        try:
            yield session  # type: ignore[misc]
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    """Extract and validate the current user from the JWT cookie.

    Raises:
        HTTPException 401: If no token, invalid token, or inactive user.
    """
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        user = await get_user_from_token(db, access_token)
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
        )
    return user


def require_role(*roles: UserRole) -> Callable:
    """Factory that creates a dependency requiring specific user roles.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_endpoint(): ...
    """
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


# Convenience shortcuts
require_admin = require_role(UserRole.ADMIN)
require_premium_or_admin = require_role(UserRole.PREMIUM, UserRole.ADMIN)


async def read_json_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Validate a `.json` upload and return its raw bytes up to `max_bytes`.

    Shared between the character and creature import routes so both enforce
    identical extension checks and two-layer size limits (Content-Length
    pre-check plus streaming accumulator against lying headers / chunked bodies).
    """
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are accepted.")

    if file.size is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Import file exceeds {max_bytes} bytes.",
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Import file exceeds {max_bytes} bytes.",
            )
        chunks.append(chunk)
    return b"".join(chunks)
