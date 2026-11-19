"""
AI Helper Docstring
Purpose: Strongly-typed Pydantic settings management. Parses `.env` variables or system environment variables to configure App globally.
Interactions:
- Most core structures (`main.py`, `app.database.py`, `app.security.py`) use `get_settings()`.
"""

"""Application configuration via Pydantic Settings.

All secrets are loaded from environment variables (or .env file for local dev).
Never hardcode secrets in source code.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Security ---
    SECRET_KEY: str  # Required — no default, must be set in environment
    # Independent secret for NiceGUI session storage. Required so a JWT
    # SECRET_KEY rotation does not also nuke every active UI session, and
    # so a leak of one secret does not compromise the other.
    STORAGE_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./donjondocs.db"

    # --- Auth ---
    ALLOW_REGISTRATION: bool = True

    # --- App ---
    APP_NAME: str = "DonjonDocs"
    DEBUG: bool = False

    # --- Security headers ---
    # When true, add Strict-Transport-Security to responses. Only enable
    # behind HTTPS — HSTS on plain http://localhost gets sticky-cached by
    # browsers and breaks future dev sessions. Off by default; flip to
    # true in production .env where the deploy serves HTTPS.
    HSTS_ENABLED: bool = False

    # --- Trusted hosts ---
    # Comma-separated list of hostnames the app accepts in the Host
    # header. The default is dev-safe; production must override with the
    # real hostname(s). main.py refuses to boot if DEBUG=False and this
    # is empty or wildcarded.
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"

    # --- Reverse proxy ---
    # When true (e.g. deployed behind Render/Nginx/Caddy), SlowAPI reads the
    # rightmost entry of X-Forwarded-For (appended by the trusted edge proxy)
    # so users don't collapse onto a single shared rate-limit bucket. Leave
    # false for direct connections so clients cannot spoof X-Forwarded-For.
    TRUST_PROXY_HEADERS: bool = False

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()  # type: ignore[call-arg]
