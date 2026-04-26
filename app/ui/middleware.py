"""Authentication middleware for NiceGUI pages.

On every HTTP request for a protected page, decode the JWT carried in
the `access_token` HttpOnly cookie, look the user up in the database,
and attach a `UserContext` to `request.state.user`. Pages read that
context via `app.ui.auth.current_user_context()` instead of forging
their own session object.

Any verification failure (no token, bad token, deactivated or missing
user) clears the session storage and redirects to `/login`. That is
what closes the `MockUser` RBAC-bypass: pages can no longer trust a
stale session-storage snapshot of `role`/`id` — every request hits the
DB.

API routes (`/api/*`) are exempt: they enforce auth via the
`get_current_user` FastAPI dependency which does its own DB verify.
"""

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from nicegui import app

from app.services.auth_service import AuthError, get_user_from_token
from app.services.session import service_session
from app.user_context import UserContext

PUBLIC_PATHS = {"/login", "/register"}
PUBLIC_PREFIXES = ("/_nicegui", "/api/", "/_static")


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES)


def _redirect_to_login(path: str) -> RedirectResponse:
    try:
        app.storage.user.clear()
    except Exception:
        pass
    response = RedirectResponse(f"/login?redirect_to={path}")
    # Ensure a stale/invalid cookie does not trigger a redirect loop when
    # login.py's "already authenticated" guard fires on the next hop.
    response.delete_cookie("access_token", path="/")
    return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Verify identity against the DB on every protected page request."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if _is_public(path):
            return await call_next(request)

        token = request.cookies.get("access_token")
        if not token:
            return _redirect_to_login(path)

        try:
            async with service_session() as session:
                user = await get_user_from_token(session, token)
        except AuthError:
            return _redirect_to_login(path)

        request.state.user = UserContext.from_user(user)
        return await call_next(request)
