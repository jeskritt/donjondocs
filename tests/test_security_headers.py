"""Tests for SecurityHeadersMiddleware (audit finding #5).

Verifies the middleware emits the expected defensive headers on
responses and respects the HSTS flag (which gates emission to HTTPS
deployments only).
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.security_headers import SecurityHeadersMiddleware


def _build_app(*, hsts_enabled: bool) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=hsts_enabled)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_default_security_headers_present():
    app = _build_app(hsts_enabled=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ping")
    assert resp.status_code == 200
    h = resp.headers
    # Hard-required defensive headers.
    assert "Content-Security-Policy" in h
    assert "default-src 'self'" in h["Content-Security-Policy"]
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in h


@pytest.mark.asyncio
async def test_hsts_omitted_when_disabled():
    """HSTS must NOT appear on http://localhost — would sticky-cache and
    break dev sessions if it ever leaked."""
    app = _build_app(hsts_enabled=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ping")
    assert "Strict-Transport-Security" not in resp.headers


@pytest.mark.asyncio
async def test_hsts_emitted_when_enabled():
    app = _build_app(hsts_enabled=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ping")
    sts = resp.headers.get("Strict-Transport-Security", "")
    assert "max-age=" in sts
    assert "includeSubDomains" in sts


@pytest.mark.asyncio
async def test_csp_allows_nicegui_inline_assets():
    """NiceGUI ships inline Vue templates and Tailwind runtime styles.

    A strict CSP would crater the UI; this test pins the policy to the
    relaxed-but-still-useful shape we ship so a future tightening
    doesn't accidentally break NiceGUI rendering.
    """
    app = _build_app(hsts_enabled=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ping")
    csp = resp.headers["Content-Security-Policy"]
    assert "'unsafe-inline'" in csp
    assert "'unsafe-eval'" in csp
    assert "frame-ancestors 'none'" in csp
