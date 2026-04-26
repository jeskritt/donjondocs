"""
AI Helper Docstring
Purpose: Pytest suite targeting standard Unit validation mechanisms to ensure internal Password mechanics perform seamlessly.
Interactions:
- Specifically runs independent hooks from `app.services.auth_service.py`.
"""

"""Tests for app.services.auth_service."""

import pytest
import pytest_asyncio

from app.models.user import User, UserRole
from app.security import hash_password
from app.services.auth_service import (
    AuthError,
    authenticate_user,
    create_user_token,
    get_user_from_token,
    register_user,
)
from app.schemas.auth import RegisterRequest


@pytest.mark.asyncio
class TestAuthenticateUser:
    """Tests for authenticate_user."""

    async def test_authenticate_valid_credentials(self, db_session, create_test_user):
        user = await create_test_user(password="correct_password")
        result = await authenticate_user(db_session, user.email, "correct_password")
        assert result.id == user.id

    async def test_authenticate_wrong_password(self, db_session, create_test_user):
        await create_test_user(password="correct_password")
        with pytest.raises(AuthError, match="Invalid email or password"):
            await authenticate_user(db_session, "test@example.com", "wrong_password")

    async def test_authenticate_nonexistent_user(self, db_session):
        with pytest.raises(AuthError, match="Invalid email or password"):
            await authenticate_user(db_session, "nobody@example.com", "password")

    async def test_authenticate_inactive_user(self, db_session, create_test_user):
        await create_test_user(password="password", is_active=False)
        with pytest.raises(AuthError, match="deactivated"):
            await authenticate_user(db_session, "test@example.com", "password")

    async def test_login_updates_last_login(self, db_session, create_test_user):
        user = await create_test_user(password="password")
        assert user.last_login is None
        result = await authenticate_user(db_session, user.email, "password")
        assert result.last_login is not None


@pytest.mark.asyncio
class TestRegisterUser:
    """Tests for register_user."""

    async def test_register_creates_user(self, db_session):
        data = RegisterRequest(username="newuser", email="new@test.com", password="Password123!")
        user = await register_user(db_session, data)
        assert user.username == "newuser"
        assert user.email == "new@test.com"
        assert user.id is not None

    async def test_register_hashes_password(self, db_session):
        data = RegisterRequest(username="newuser", email="new@test.com", password="Password123!")
        user = await register_user(db_session, data)
        assert user.hashed_password != "Password123!"
        assert user.hashed_password.startswith("$2b$")

    async def test_register_default_role_standard(self, db_session):
        data = RegisterRequest(username="newuser", email="new@test.com", password="Password123!")
        user = await register_user(db_session, data)
        assert user.role == UserRole.STANDARD

    async def test_register_duplicate_email_fails(self, db_session, create_test_user):
        await create_test_user(email="taken@test.com")
        data = RegisterRequest(username="other", email="taken@test.com", password="Password123!")
        with pytest.raises(AuthError, match="already registered"):
            await register_user(db_session, data)

    async def test_register_duplicate_username_fails(self, db_session, create_test_user):
        await create_test_user(username="taken")
        data = RegisterRequest(username="taken", email="other@test.com", password="Password123!")
        with pytest.raises(AuthError, match="already taken"):
            await register_user(db_session, data)

    async def test_register_blocked_when_disabled(self, db_session, monkeypatch):
        monkeypatch.setenv("ALLOW_REGISTRATION", "false")
        from app.config import get_settings
        get_settings.cache_clear()

        data = RegisterRequest(username="newuser", email="new@test.com", password="Password123!")
        with pytest.raises(AuthError, match="disabled"):
            await register_user(db_session, data)

        # Restore
        monkeypatch.setenv("ALLOW_REGISTRATION", "true")
        get_settings.cache_clear()


@pytest.mark.asyncio
class TestTokenFunctions:
    """Tests for token creation and validation."""

    async def test_create_user_token(self, create_test_user):
        user = await create_test_user()
        token = create_user_token(user)
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_get_user_from_valid_token(self, db_session, create_test_user):
        user = await create_test_user()
        token = create_user_token(user)
        result = await get_user_from_token(db_session, token)
        assert result.id == user.id

    async def test_get_user_from_invalid_token(self, db_session):
        with pytest.raises(AuthError, match="Invalid"):
            await get_user_from_token(db_session, "invalid-token")
