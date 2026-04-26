"""Direct tests for set_auth_cookie / clear_auth_cookie.

These helpers are exercised by /api/auth/login and /api/auth/register
integration tests, but those don't pin the flag combinations the
audit cares about (HttpOnly, SameSite=Lax, Secure-when-prod). Direct
tests catch a regression like "someone flips httponly off as a debug
hack and forgets to flip it back."
"""

from fastapi import FastAPI
from fastapi.responses import Response
from starlette.testclient import TestClient

from app.auth_cookie import clear_auth_cookie, set_auth_cookie
from app.config import get_settings


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/set")
    def _set(response: Response):
        set_auth_cookie(response, "dummy-jwt")
        return {"ok": True}

    @app.get("/clear")
    def _clear(response: Response):
        clear_auth_cookie(response)
        return {"ok": True}

    return app


def _parse_set_cookie(header: str) -> dict[str, str | bool]:
    """Walk a Set-Cookie header into a flag dict.

    Bare flags (HttpOnly, Secure) come back as True; key=value flags
    come back with their value. Names are lowercased so callers don't
    care about server casing.
    """
    parts = [p.strip() for p in header.split(";")]
    out: dict[str, str | bool] = {}
    for i, part in enumerate(parts):
        if i == 0:
            key, _, value = part.partition("=")
            out[key.lower()] = value
            continue
        if "=" in part:
            k, _, v = part.partition("=")
            out[k.lower()] = v
        else:
            out[part.lower()] = True
    return out


class TestSetAuthCookie:
    def test_sets_httponly_samesite_lax(self):
        client = TestClient(_build_app())
        resp = client.get("/set")
        cookie = _parse_set_cookie(resp.headers["set-cookie"])
        assert cookie["access_token"] == "dummy-jwt"
        assert cookie.get("httponly") is True
        assert cookie.get("samesite", "").lower() == "lax"
        assert cookie.get("path") == "/"

    def test_max_age_matches_token_expiry(self):
        client = TestClient(_build_app())
        resp = client.get("/set")
        cookie = _parse_set_cookie(resp.headers["set-cookie"])
        expected = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert int(cookie["max-age"]) == expected

    def test_secure_flag_off_in_debug(self, monkeypatch):
        """DEBUG=true (dev) drops Secure so http://localhost works."""
        from app import auth_cookie
        from app.config import Settings

        # Clear get_settings cache so we pick up the patched env.
        get_settings.cache_clear()
        monkeypatch.setattr(auth_cookie, "get_settings", lambda: Settings(
            SECRET_KEY="x" * 32, STORAGE_SECRET="y" * 32, DEBUG=True,
        ))

        client = TestClient(_build_app())
        resp = client.get("/set")
        cookie = _parse_set_cookie(resp.headers["set-cookie"])
        assert "secure" not in cookie

    def test_secure_flag_on_when_not_debug(self, monkeypatch):
        from app import auth_cookie
        from app.config import Settings

        get_settings.cache_clear()
        monkeypatch.setattr(auth_cookie, "get_settings", lambda: Settings(
            SECRET_KEY="x" * 32, STORAGE_SECRET="y" * 32, DEBUG=False,
        ))

        client = TestClient(_build_app())
        resp = client.get("/set")
        cookie = _parse_set_cookie(resp.headers["set-cookie"])
        assert cookie.get("secure") is True


class TestClearAuthCookie:
    def test_emits_expiry_in_the_past(self):
        client = TestClient(_build_app())
        resp = client.get("/clear")
        sc = resp.headers["set-cookie"]
        assert "access_token=" in sc
        # Starlette's delete_cookie sets Max-Age=0 + a 1970 expires.
        assert "Max-Age=0" in sc or "max-age=0" in sc.lower()
