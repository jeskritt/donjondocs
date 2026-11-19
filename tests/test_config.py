"""
AI Helper Docstring
Purpose: Verifies the App defaults don't immediately crash under malformed Environment mappings or variables.
Interactions:
- Evaluates constraints located directly on `app.config.py`.
"""

"""Tests for app.config module."""

import os

import pytest

from app.config import Settings


class TestConfig:
    """Tests for application configuration."""

    def test_settings_loads_defaults(self):
        settings = Settings(SECRET_KEY="test-key", STORAGE_SECRET="test-storage")
        assert settings.APP_NAME == "DonjonDocs"
        assert settings.DEBUG is False
        assert settings.ALLOW_REGISTRATION is True
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert "sqlite" in settings.DATABASE_URL

    def test_settings_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "env-secret")
        monkeypatch.setenv("APP_NAME", "TestApp")
        monkeypatch.setenv("DEBUG", "true")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.SECRET_KEY == "env-secret"
        assert settings.APP_NAME == "TestApp"
        assert settings.DEBUG is True

    def test_secret_key_required(self):
        """SECRET_KEY must be set — no default."""
        # Remove it from env to force failure
        env_backup = os.environ.pop("SECRET_KEY", None)
        try:
            with pytest.raises(Exception):
                Settings(_env_file=None)  # type: ignore[call-arg]
        finally:
            if env_backup:
                os.environ["SECRET_KEY"] = env_backup

    def test_allow_registration_toggle(self):
        settings = Settings(SECRET_KEY="test-key", STORAGE_SECRET="test-storage", ALLOW_REGISTRATION=False)
        assert settings.ALLOW_REGISTRATION is False

        settings = Settings(SECRET_KEY="test-key", STORAGE_SECRET="test-storage", ALLOW_REGISTRATION=True)
        assert settings.ALLOW_REGISTRATION is True

    def test_trust_proxy_headers_defaults_false(self):
        settings = Settings(SECRET_KEY="test-key", STORAGE_SECRET="test-storage")
        assert settings.TRUST_PROXY_HEADERS is False


class TestRateLimitClientIP:
    """Verify proxy-aware client IP resolution for SlowAPI."""

    @staticmethod
    def _make_request(peer_host: str, xff: str | None = None):
        from starlette.requests import Request

        headers = []
        if xff is not None:
            headers.append((b"x-forwarded-for", xff.encode("latin-1")))
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": headers,
            "client": (peer_host, 12345),
        }
        return Request(scope)

    def test_ignores_forwarded_for_when_proxy_untrusted(self, monkeypatch):
        from app.rate_limit import get_client_ip

        monkeypatch.setattr(
            "app.rate_limit.get_settings",
            lambda: Settings(SECRET_KEY="k", STORAGE_SECRET="s", TRUST_PROXY_HEADERS=False),
        )
        req = self._make_request("10.0.0.5", xff="1.2.3.4, 5.6.7.8")
        assert get_client_ip(req) == "10.0.0.5"

    def test_uses_rightmost_forwarded_for_when_proxy_trusted(self, monkeypatch):
        from app.rate_limit import get_client_ip

        monkeypatch.setattr(
            "app.rate_limit.get_settings",
            lambda: Settings(SECRET_KEY="k", STORAGE_SECRET="s", TRUST_PROXY_HEADERS=True),
        )
        # Attacker prepends 1.2.3.4; Render proxy appends the true client IP 203.0.113.9.
        req = self._make_request("10.0.0.5", xff="1.2.3.4, 203.0.113.9")
        assert get_client_ip(req) == "203.0.113.9"

    def test_falls_back_to_peer_when_header_missing(self, monkeypatch):
        from app.rate_limit import get_client_ip

        monkeypatch.setattr(
            "app.rate_limit.get_settings",
            lambda: Settings(SECRET_KEY="k", STORAGE_SECRET="s", TRUST_PROXY_HEADERS=True),
        )
        req = self._make_request("10.0.0.5")
        assert get_client_ip(req) == "10.0.0.5"
