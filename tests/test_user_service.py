"""
AI Helper Docstring
Purpose: Strictly maps the direct internal executions of fetching subsets of databases and generating service-level errors natively.
Interactions:
- Acts solely against `app.services.user_service.py`.
"""

"""Tests for app.services.user_service."""

import pytest

from app.models.user import UserRole
from app.schemas.user import ProfileUpdate, UserCreate, UserUpdate
from app.services.user_service import (
    UserServiceError,
    change_password,
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    list_users,
    reset_password,
    update_profile,
    update_user,
)


@pytest.mark.asyncio
class TestCreateUser:
    """Tests for admin user creation."""

    async def test_create_user_as_admin(self, db_session):
        data = UserCreate(username="newuser", email="new@test.com", password="Pass1234!")
        user = await create_user(db_session, data)
        assert user.username == "newuser"
        assert user.email == "new@test.com"

    async def test_create_user_with_role(self, db_session):
        data = UserCreate(
            username="adminuser", email="admin@test.com",
            password="Pass1234!", role=UserRole.ADMIN,
        )
        user = await create_user(db_session, data)
        assert user.role == UserRole.ADMIN

    async def test_create_duplicate_username_fails(self, db_session, create_test_user):
        await create_test_user(username="taken")
        data = UserCreate(username="taken", email="other@test.com", password="Pass1234!")
        with pytest.raises(UserServiceError, match="already taken"):
            await create_user(db_session, data)

    async def test_create_duplicate_email_fails(self, db_session, create_test_user):
        await create_test_user(email="taken@test.com")
        data = UserCreate(username="other", email="taken@test.com", password="Pass1234!")
        with pytest.raises(UserServiceError, match="already registered"):
            await create_user(db_session, data)


@pytest.mark.asyncio
class TestGetUser:
    """Tests for user retrieval."""

    async def test_get_user_by_id(self, db_session, create_test_user):
        user = await create_test_user()
        result = await get_user_by_id(db_session, user.id)
        assert result.id == user.id

    async def test_get_user_by_id_not_found(self, db_session):
        with pytest.raises(UserServiceError, match="not found"):
            await get_user_by_id(db_session, "nonexistent-id")

    async def test_get_user_by_email(self, db_session, create_test_user):
        user = await create_test_user(email="find@test.com")
        result = await get_user_by_email(db_session, "find@test.com")
        assert result.id == user.id

    async def test_get_user_by_email_not_found(self, db_session):
        with pytest.raises(UserServiceError, match="not found"):
            await get_user_by_email(db_session, "missing@test.com")


@pytest.mark.asyncio
class TestListUsers:
    """Tests for user listing."""

    async def test_list_users_paginated(self, db_session, create_test_user):
        for i in range(5):
            await create_test_user(username=f"user{i}", email=f"user{i}@test.com")

        users, total = await list_users(db_session, skip=0, limit=3)
        assert len(users) == 3
        assert total == 5


@pytest.mark.asyncio
class TestUpdateUser:
    """Tests for admin user update."""

    async def test_update_user_role(self, db_session, create_test_user):
        user = await create_test_user()
        data = UserUpdate(role=UserRole.PREMIUM)
        updated = await update_user(db_session, user.id, data)
        assert updated.role == UserRole.PREMIUM

    async def test_update_user_email(self, db_session, create_test_user):
        user = await create_test_user()
        data = UserUpdate(email="new@test.com")
        updated = await update_user(db_session, user.id, data)
        assert updated.email == "new@test.com"

    async def test_update_user_username(self, db_session, create_test_user):
        user = await create_test_user()
        data = UserUpdate(username="newname")
        updated = await update_user(db_session, user.id, data)
        assert updated.username == "newname"

    async def test_update_user_is_active(self, db_session, create_test_user):
        user = await create_test_user()
        data = UserUpdate(is_active=False)
        updated = await update_user(db_session, user.id, data)
        assert updated.is_active is False


@pytest.mark.asyncio
class TestDeleteUser:
    """Tests for soft-delete."""

    async def test_delete_user_soft_deletes(self, db_session, create_test_user):
        user = await create_test_user()
        assert user.is_active is True
        deleted = await delete_user(db_session, user.id)
        assert deleted.is_active is False


@pytest.mark.asyncio
class TestPasswordManagement:
    """Tests for password change and reset."""

    async def test_change_password_with_correct_current(self, db_session, create_test_user):
        user = await create_test_user(password="OldPass123!")
        await change_password(db_session, user, "OldPass123!", "NewPass456!")
        # Verify the new password works
        from app.security import verify_password
        assert verify_password("NewPass456!", user.hashed_password)

    async def test_change_password_with_wrong_current_fails(self, db_session, create_test_user):
        user = await create_test_user(password="OldPass123!")
        with pytest.raises(UserServiceError, match="incorrect"):
            await change_password(db_session, user, "WrongPass!", "NewPass456!")

    async def test_reset_password_sets_new_hash(self, db_session, create_test_user):
        user = await create_test_user(password="OldPass123!")
        old_hash = user.hashed_password
        await reset_password(db_session, user.id, "ResetPass789!")
        # Refresh to get updated hash
        updated = await get_user_by_id(db_session, user.id)
        assert updated.hashed_password != old_hash
        from app.security import verify_password
        assert verify_password("ResetPass789!", updated.hashed_password)


@pytest.mark.asyncio
class TestUpdateProfile:
    """Tests for self-service profile update."""

    async def test_update_profile_username(self, db_session, create_test_user):
        user = await create_test_user()
        data = ProfileUpdate(username="newprofilename")
        updated = await update_profile(db_session, user, data)
        assert updated.username == "newprofilename"

    async def test_update_profile_no_role_change(self, db_session, create_test_user):
        """ProfileUpdate schema has no role field — it's structurally impossible."""
        user = await create_test_user()
        data = ProfileUpdate(username="newname")
        updated = await update_profile(db_session, user, data)
        # Role should remain unchanged
        assert updated.role == UserRole.STANDARD
