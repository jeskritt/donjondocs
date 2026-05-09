"""
AI Helper Docstring
Purpose: The core FastAPI and NiceGUI entrypoint. Mounts all API routers, security middleware layers (CORS, SlowAPI limits), and registers NiceGUI UI routes.
Interactions: 
- `app.api.*`: Mounts REST routers.
- `app.ui.pages.*`: Registers the NiceGUI frontend routes implicitly.
- `app.ui.middleware.AuthMiddleware`: Protects non-public routes with JWT validation.
"""

"""DonjonDocs — Main application entry point.

Mounts API routers, security middleware, and NiceGUI pages.
Run with: python main.py
"""

from fastapi import Request
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from nicegui import app, ui

from app.config import get_settings
from app.api import auth_routes, user_routes, character_routes, character_addons_routes
from app.rate_limit import limiter
from app.security_headers import SecurityHeadersMiddleware
from app.services._errors import ServiceError, service_error_handler
from app.ui.middleware import AuthMiddleware

# Ensure all models are imported for table creation
from app.models import User, UserRole  # noqa: F401

settings = get_settings()

# ---------------------------------------------------------------------------
# Security Middleware Stack
# ---------------------------------------------------------------------------

# 1. Trusted Host (outermost — prevents Host header attacks).
# Hosts come from settings.ALLOWED_HOSTS so prod can lock this down via
# env without code changes. Refuse to boot in non-DEBUG mode if the list
# is empty or wildcarded — see security audit F-01.
_allowed_hosts = settings.allowed_hosts_list
if not settings.DEBUG and (not _allowed_hosts or _allowed_hosts == ["*"]):
    raise RuntimeError(
        "ALLOWED_HOSTS must list real hostnames when DEBUG=false "
        "(refusing to boot with a wildcard in production)."
    )
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=_allowed_hosts,
)

# 2. Rate Limiting (slowapi). Per-endpoint @limiter.limit decorators
# enforce the actual policy; this just wires up the middleware and the
# 429 handler. The shared limiter instance lives in app/rate_limit.py
# so router modules can import it without circular dependencies.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(ServiceError, service_error_handler)
app.add_middleware(SlowAPIMiddleware)

# 3. Auth Middleware (checks JWT cookie on non-public routes)
app.add_middleware(AuthMiddleware)

# 4. Security headers (outermost — runs last on the response so it
# stamps headers onto every response, including auth redirects and
# rate-limit 429s).
app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=settings.HSTS_ENABLED)

# ---------------------------------------------------------------------------
# Static assets — vendored CSS/fonts under app/static/. Mounted at /_static
# so it falls under AuthMiddleware.PUBLIC_PREFIXES without changes there.
# ---------------------------------------------------------------------------

app.add_static_files('/_static', 'app/static')

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(user_routes.router, prefix="/api/users", tags=["users"])
app.include_router(character_routes.router, prefix="/api/characters", tags=["characters"])
app.include_router(character_addons_routes.allies_router, prefix="/api/allies", tags=["allies"])
app.include_router(character_addons_routes.notes_router, prefix="/api/notes", tags=["notes"])

# ---------------------------------------------------------------------------
# UI Logout redirect (called from header menu)
# ---------------------------------------------------------------------------

@app.get("/api/auth/logout-ui")
async def logout_ui():
    """Logout via GET redirect (for UI navigation)."""
    app.storage.user.clear()
    response = RedirectResponse("/login")
    response.delete_cookie("access_token", path="/")
    return response


# ---------------------------------------------------------------------------
# Import NiceGUI pages (registering @ui.page routes)
# ---------------------------------------------------------------------------

from app.ui.pages import login, register, dashboard, profile, admin, character_sheet  # noqa: F401, E402


# ---------------------------------------------------------------------------
# Startup: auto-ingest seed data if global tables are empty
# ---------------------------------------------------------------------------

@app.on_startup
async def startup():
    """Auto-ingest the bundled `data/` CSVs if any of the global lookup
    tables are empty. Schema creation is owned by Alembic — run
    ``alembic upgrade head`` before first boot.
    """
    import os
    from sqlalchemy import select, func
    from app.database import async_session_factory
    from app.models.char_sheet import (
        GlobalClass, GlobalSkill, GlobalAttribute,
        GlobalWeapon, GlobalArmor, GlobalItem,
    )
    from app.cli.ingest import run_ingestion

    # If any of the global reference tables is empty, run ingest on `data/`.
    # This keeps the app working out-of-the-box for fresh sqlite DBs while
    # remaining idempotent via the upsert logic in `app.cli.ingest`.
    async with async_session_factory() as session:
        needs_ingest = False
        for ModelCls in (GlobalClass, GlobalSkill, GlobalAttribute,
                         GlobalWeapon, GlobalArmor, GlobalItem):
            count = (await session.execute(
                select(func.count()).select_from(ModelCls)
            )).scalar_one()
            if count == 0:
                needs_ingest = True
                break

    if needs_ingest:
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        if os.path.isdir(data_dir):
            print(f"[startup] Global reference tables empty — ingesting from {data_dir}")
            await run_ingestion(data_dir)
        else:
            print(f"[startup] WARNING: data dir not found at {data_dir}; skipping auto-ingest")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ in {"__main__", "__mp_main__"}:
    import os

    # PORT is a deploy-platform convention (Render, Heroku, Fly) — not
    # app config — so it's read directly from the environment rather
    # than going through Settings. Defaults to 8080 for local dev.
    ui.run(
        title=settings.APP_NAME,
        storage_secret=settings.STORAGE_SECRET,
        reload=False,  # temporarily disabled for stability
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
    )
