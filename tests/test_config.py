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
