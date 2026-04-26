"""Shared helpers for managing the `access_token` HttpOnly cookie.

Extracted so both the API routes and future UI call sites can set the
cookie consistently without duplicating the flag list.
"""

from fastapi import Response

from app.config import get_settings


def set_auth_cookie(response: Response, token: str) -> None:
    """Set the JWT access token as an HttpOnly cookie."""
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the JWT access token cookie."""
    response.delete_cookie(key="access_token", path="/")
