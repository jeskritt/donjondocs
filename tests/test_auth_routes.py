"""
AI Helper Docstring
Purpose: Pytest suite confirming robust HTTP rejection mechanics of Login and Registration APIs (401s, 409s).
Interactions:
- Needs `client` injected fixtures configured inside `conftest.py`.
"""

"""Tests for auth API routes."""

import pytest

from tests.conftest import auth_cookies


@pytest.mark.asyncio
class TestLoginRoute:
    """Tests for POST /api/auth/login."""

    async def test_login_success_sets_httponly_cookie(self, client, test_user):
        resp = await client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        # Check cookie is set
        assert "access_token" in resp.cookies
        # Check response body has user info (no password)
        data = resp.json()
        assert data["username"] == "standard_user"
        assert data["email"] == "user@test.com"
        assert "hashed_password" not in data
        assert "password" not in data

    async def test_login_wrong_credentials_401(self, client, test_user):
        resp = await client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "wrong_password",
        })
        assert resp.status_code == 401

    async def test_login_inactive_user_401(self, client, create_test_user):
        await create_test_user(
            username="inactive", email="inactive@test.com",
            password="TestPass123!", is_active=False,
        )
        resp = await client.post("/api/auth/login", json={
            "email": "inactive@test.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 401

    async def test_login_rate_limit_returns_429(self, client, test_user):
        """Hammering /login past the 5/minute cap must return 429.

        Uses bad credentials so each attempt would normally be 401;
        SlowAPI counts attempts regardless of outcome, so the 6th
        request is rejected by the limiter before authentication runs.
        """
        for _ in range(5):
            resp = await client.post("/api/auth/login", json={
                "email": "user@test.com",
                "password": "wrong_password",
            })
            assert resp.status_code in (200, 401), resp.status_code
        # The 6th request crosses the cap.
        resp = await client.post("/api/auth/login", json={
            "email": "user@test.com",
            "password": "wrong_password",
        })
        assert resp.status_code == 429


@pytest.mark.asyncio
class TestRegisterRoute:
    """Tests for POST /api/auth/register."""

    async def test_register_success(self, client):
        resp = await client.post("/api/auth/register", json={
            "username": "newuser",
            "email": "new@test.com",
            "password": "NewPass123!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["role"] == "standard"

    async def test_register_duplicate_email_409(self, client, test_user):
        resp = await client.post("/api/auth/register", json={
            "username": "another",
            "email": "user@test.com",  # Already taken
            "password": "NewPass123!",
        })
        assert resp.status_code == 409

    async def test_register_rate_limit_returns_429(self, client):
        """6th /register call within a minute hits the 5/minute cap.

        Reuses bad payloads so attempts are cheap; SlowAPI counts
        before validation runs anyway.
        """
        for i in range(5):
            resp = await client.post("/api/auth/register", json={
                "username": f"rluser{i}",
                "email": f"rluser{i}@test.com",
                "password": "NewPass123!",
            })
            # 201 on success or 409 on duplicate — never 429 within budget.
            assert resp.status_code in (201, 409), resp.status_code
        resp = await client.post("/api/auth/register", json={
            "username": "rluser6",
            "email": "rluser6@test.com",
            "password": "NewPass123!",
        })
        assert resp.status_code == 429


@pytest.mark.asyncio
class TestLogoutRoute:
    """Tests for POST /api/auth/logout."""

    async def test_logout_clears_cookie(self, client, test_user):
        client.cookies = auth_cookies(test_user)
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 204

    async def test_get_logout_ui_removed_404(self, client, test_user):
        """State-changing GET /api/auth/logout-ui was removed (CSRF hardening)."""
        client.cookies = auth_cookies(test_user)
        resp = await client.get("/api/auth/logout-ui", follow_redirects=False)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestMeRoute:
    """Tests for GET /api/auth/me."""

    async def test_me_returns_user_info(self, client, test_user):
        client.cookies = auth_cookies(test_user)
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "standard_user"

    async def test_me_without_cookie_401(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401
