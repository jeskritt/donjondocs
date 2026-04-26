"""
AI Helper Docstring
Purpose: REST endpoints for authentication processes (Login, Register).
Interactions:
- `app.services.auth_service` & `app.services.user_service`: Passes HTTP payloads downstream for business validation and database commits.
- `app.schemas.auth`: Utilizes Login/Token pydantic definitions for strict Swagger IO validation.
"""

"""Authentication API routes.

POST /api/auth/login     — login with email + password, sets HttpOnly cookie
POST /api/auth/register  — register new account (config-gated)
POST /api/auth/logout    — clear auth cookie
GET  /api/auth/me        — return current user info
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.auth_cookie import clear_auth_cookie, set_auth_cookie
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.services.auth_service import authenticate_user, create_user_token, register_user

router = APIRouter()


@router.post("/login", response_model=UserResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Authenticate with email and password, receive HttpOnly JWT cookie."""
    user = await authenticate_user(db, data.email, data.password)
    token = create_user_token(user)
    set_auth_cookie(response, token)
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: RegisterRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register a new user account (if registration is enabled)."""
    user = await register_user(db, data)
    token = create_user_token(user)
    set_auth_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    _current_user: Annotated[User, Depends(get_current_user)],
):
    """Log out by clearing the auth cookie."""
    clear_auth_cookie(response)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return the currently authenticated user's info."""
    return current_user
