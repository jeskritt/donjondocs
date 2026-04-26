"""
AI Helper Docstring
Purpose: Endpoint tests proving Admin profiles can successfully nuke Standard profiles globally, or users updating their specific accounts successfully.
Interactions:
- Leverages `app.api.user_routes.py` over an `httpx` AsyncClient proxy.
"""

"""Tests for user management API routes."""

import pytest

from tests.conftest import auth_cookies


@pytest.mark.asyncio
class TestAdminUserRoutes:
    """Tests for admin-only user management endpoints."""

    async def test_admin_list_users(self, client, test_admin):
        cookies = auth_cookies(test_admin)
        resp = await client.get("/api/users", cookies=cookies)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_admin_get_user(self, client, test_admin, test_user):
        cookies = auth_cookies(test_admin)
        resp = await client.get(f"/api/users/{test_user.id}", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["username"] == "standard_user"

    async def test_admin_create_user(self, client, test_admin):
        cookies = auth_cookies(test_admin)
        resp = await client.post("/api/users", cookies=cookies, json={
            "username": "created_by_admin",
            "email": "admin_created@test.com",
            "password": "Pass1234!",
            "role": "premium",
        })
        assert resp.status_code == 201
        assert resp.json()["role"] == "premium"

    async def test_admin_update_user(self, client, test_admin, test_user):
        cookies = auth_cookies(test_admin)
        resp = await client.put(f"/api/users/{test_user.id}", cookies=cookies, json={
            "role": "premium",
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == "premium"

    async def test_admin_delete_user(self, client, test_admin, test_user):
        cookies = auth_cookies(test_admin)
        resp = await client.delete(f"/api/users/{test_user.id}", cookies=cookies)
        assert resp.status_code == 204

    async def test_admin_reset_user_password(self, client, test_admin, test_user):
        cookies = auth_cookies(test_admin)
        resp = await client.post(
            f"/api/users/{test_user.id}/reset-password",
            cookies=cookies,
            json={"new_password": "ResetPass789!"},
        )
        assert resp.status_code == 204

    async def test_admin_reset_password_rate_limit_returns_429(
        self, client, test_admin, test_user
    ):
        """4th reset within a minute hits the 3/minute cap.

        Defence in depth — even an authenticated admin shouldn't be
        able to fire reset attempts at machine speed (cf. audit
        finding #6 — silent account takeover via admin reset).
        """
        cookies = auth_cookies(test_admin)
        for _ in range(3):
            resp = await client.post(
                f"/api/users/{test_user.id}/reset-password",
                cookies=cookies,
                json={"new_password": "ResetPass789!"},
            )
            assert resp.status_code == 204
        resp = await client.post(
            f"/api/users/{test_user.id}/reset-password",
            cookies=cookies,
            json={"new_password": "ResetPass789!"},
        )
        assert resp.status_code == 429


@pytest.mark.asyncio
class TestNonAdminRestrictions:
    """Tests that non-admin users can't access admin routes."""

    async def test_standard_user_cannot_list_users_403(self, client, test_user):
        cookies = auth_cookies(test_user)
        resp = await client.get("/api/users", cookies=cookies)
        assert resp.status_code == 403

    async def test_standard_user_cannot_create_user_403(self, client, test_user):
        cookies = auth_cookies(test_user)
        resp = await client.post("/api/users", cookies=cookies, json={
            "username": "hacker",
            "email": "hack@test.com",
            "password": "Pass1234!",
        })
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestSelfServiceRoutes:
    """Tests for self-service profile management."""

    async def test_self_update_profile(self, client, test_user):
        cookies = auth_cookies(test_user)
        resp = await client.put("/api/users/me", cookies=cookies, json={
            "username": "updated_name",
        })
        assert resp.status_code == 200
        assert resp.json()["username"] == "updated_name"

    async def test_self_update_cannot_change_role(self, client, test_user):
        """ProfileUpdate schema has no 'role' field, so it's ignored."""
        cookies = auth_cookies(test_user)
        resp = await client.put("/api/users/me", cookies=cookies, json={
            "username": "sneaky",
            "role": "admin",  # This field is not in ProfileUpdate schema
        })
        # Should succeed but role should NOT change
        assert resp.status_code == 200
        assert resp.json()["role"] == "standard"  # Unchanged

    async def test_self_change_password(self, client, test_user):
        cookies = auth_cookies(test_user)
        resp = await client.post("/api/users/me/change-password", cookies=cookies, json={
            "current_password": "TestPass123!",
            "new_password": "NewTestPass456!",
        })
        assert resp.status_code == 204

    async def test_self_change_password_wrong_current_400(self, client, test_user):
        cookies = auth_cookies(test_user)
        resp = await client.post("/api/users/me/change-password", cookies=cookies, json={
            "current_password": "WrongPass!",
            "new_password": "NewTestPass456!",
        })
        assert resp.status_code == 400
