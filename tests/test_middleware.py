"""Tests for AuthMiddleware.

The middleware decodes the JWT carried in the `access_token` HttpOnly
cookie on every protected request, verifies the user against the
database, and attaches a `UserContext` to `request.state.user`. Any
failure clears session storage and redirects to `/login`.

Tests run against a minimal FastAPI app so the NiceGUI runtime (which
doesn't run under ASGI transports) stays out of the way. The real
DB-verification call (`get_user_from_token`) is patched per-test to
simulate each outcome.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.services.auth_service import AuthError
from app.user_context import UserContext
from app.user_roles import UserRole


class _FakeStorage:
    """Minimal stand-in for `nicegui.app.storage` exposing just `.user`."""

    def __init__(self, user_dict: dict):
        self.user = user_dict


def _install_storage(user_dict: dict) -> dict:
    """Replace the module-level `app.storage` that AuthMiddleware reads."""
    import app.ui.middleware as mw
    mw.app.storage = _FakeStorage(user_dict)
    return user_dict


def _build_app(user_dict: dict | None = None) -> FastAPI:
    import app.ui.middleware as mw

    app = FastAPI()
    app.add_middleware(mw.AuthMiddleware)

    @app.get("/sheet/new")
    async def _sheet_new(request: Request):
        ctx = getattr(request.state, "user", None)
        return {
            "ok": True,
            "user_id": ctx.id if ctx else None,
            "role": ctx.role.value if ctx else None,
        }

    @app.get("/character/{cid}")
    async def _char(request: Request, cid: str):
        return {"cid": cid}

    @app.get("/login")
    async def _login():
        return {"page": "login"}

    @app.get("/register")
    async def _register():
        return {"page": "register"}

    @app.get("/api/whatever")
    async def _api():
        return {"ok": True}

    @app.get("/_nicegui/client/abc")
    async def _internal():
        return {"internal": True}

    _install_storage(user_dict if user_dict is not None else {})
    return app


def _user_stub(
    user_id: str = "uid-1",
    username: str = "alice",
    email: str = "alice@example.com",
    role: UserRole = UserRole.STANDARD,
    is_active: bool = True,
):
    """Shape-compatible stand-in for the ORM User (only fields UserContext reads)."""
    u = MagicMock()
    u.id = user_id
    u.username = username
    u.email = email
    u.role = role
    u.is_active = is_active
    return u


@asynccontextmanager
async def _noop_session():
    yield object()


# ---------------------------------------------------------------------------
# Public paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_page_is_public():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/login", follow_redirects=False)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_register_page_is_public():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/register", follow_redirects=False)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_prefix_bypasses_middleware():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/whatever", follow_redirects=False)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_nicegui_internal_prefix_bypasses_middleware():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/_nicegui/client/abc", follow_redirects=False)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Unauthenticated / invalid token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_token_redirects_to_login():
    app = _build_app(user_dict={})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/sheet/new", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "/login" in resp.headers.get("location", "")


@pytest.mark.asyncio
async def test_invalid_token_clears_storage_and_redirects():
    # Storage stashed leftovers (e.g. from a prior session) must be wiped
    # on failure, even though the middleware no longer reads them for auth.
    storage = {"role": "admin", "id": "spoofed"}
    app = _build_app(user_dict=storage)
    transport = ASGITransport(app=app)

    with patch("app.ui.middleware.get_user_from_token",
               AsyncMock(side_effect=AuthError("Invalid or expired token"))):
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"access_token": "bogus"},
        ) as ac:
            resp = await ac.get("/character/c-1", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert "/login" in resp.headers.get("location", "")
    assert storage == {}


@pytest.mark.asyncio
async def test_deactivated_user_is_denied():
    storage = {"role": "admin"}
    app = _build_app(user_dict=storage)
    transport = ASGITransport(app=app)

    with patch("app.ui.middleware.get_user_from_token",
               AsyncMock(side_effect=AuthError("Account is deactivated"))):
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"access_token": "valid-but-deactivated"},
        ) as ac:
            resp = await ac.get("/sheet/new", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert storage == {}


# ---------------------------------------------------------------------------
# Authenticated happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_cookie_passes_through_with_request_state_user():
    app = _build_app(user_dict={})
    transport = ASGITransport(app=app)

    user = _user_stub(user_id="u-1", role=UserRole.STANDARD)
    with patch("app.ui.middleware.service_session", _noop_session), \
         patch("app.ui.middleware.get_user_from_token",
               AsyncMock(return_value=user)):
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"access_token": "valid"},
        ) as ac:
            resp = await ac.get("/sheet/new", follow_redirects=False)

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "u-1"
    assert body["role"] == "standard"


@pytest.mark.asyncio
async def test_request_state_user_reflects_current_db_role_not_storage_snapshot():
    """Forged storage role must be ignored; the DB lookup wins.

    This is the regression test for the MockUser BOLA finding: if someone
    pokes `role: admin` into `app.storage.user`, the middleware's DB lookup
    over the cookie must drive authorization.
    """
    storage = {"role": "admin", "id": "attacker-forged"}
    app = _build_app(user_dict=storage)
    transport = ASGITransport(app=app)

    user = _user_stub(user_id="real-id", role=UserRole.STANDARD)
    with patch("app.ui.middleware.service_session", _noop_session), \
         patch("app.ui.middleware.get_user_from_token",
               AsyncMock(return_value=user)):
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"access_token": "valid"},
        ) as ac:
            resp = await ac.get("/sheet/new", follow_redirects=False)

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "real-id"
    assert body["role"] == "standard"


@pytest.mark.asyncio
async def test_invalid_cookie_is_deleted_to_prevent_redirect_loop():
    """On auth failure, clear the bad access_token cookie via Set-Cookie.

    Without this, a user whose JWT is still in the browser but no longer
    valid (user deleted, token rotated, secret changed) gets stuck in a
    /login → / redirect loop because login.py's already-authenticated
    guard sees the stale cookie and bounces back.
    """
    app = _build_app(user_dict={})
    transport = ASGITransport(app=app)

    with patch("app.ui.middleware.get_user_from_token",
               AsyncMock(side_effect=AuthError("Invalid or expired token"))):
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"access_token": "stale"},
        ) as ac:
            resp = await ac.get("/sheet/new", follow_redirects=False)

    assert resp.status_code in (302, 307)
    set_cookie = resp.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    # A cookie deletion is an empty value + an expiry in the past.
    assert 'access_token=""' in set_cookie or "access_token=;" in set_cookie
    assert "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()


@pytest.mark.asyncio
async def test_storage_token_is_ignored_without_cookie():
    """A token sitting in storage without a cookie no longer authenticates."""
    app = _build_app(user_dict={"token": "legacy-storage-token"})
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/sheet/new", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert "/login" in resp.headers.get("location", "")


@pytest.mark.asyncio
async def test_request_state_user_is_a_UserContext():
    captured: dict = {}

    import app.ui.middleware as mw
    app_ = FastAPI()
    app_.add_middleware(mw.AuthMiddleware)

    @app_.get("/page")
    async def _page(request: Request):
        captured["ctx"] = request.state.user
        return {"ok": True}

    _install_storage({})

    user = _user_stub(user_id="u-1", role=UserRole.PREMIUM)
    with patch("app.ui.middleware.service_session", _noop_session), \
         patch("app.ui.middleware.get_user_from_token",
               AsyncMock(return_value=user)):
        transport = ASGITransport(app=app_)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"access_token": "valid"},
        ) as ac:
            await ac.get("/page", follow_redirects=False)

    assert isinstance(captured["ctx"], UserContext)
    assert captured["ctx"].role == UserRole.PREMIUM
