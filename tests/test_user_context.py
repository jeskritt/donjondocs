"""Tests for the UserContext auth-boundary DTO."""

import pytest

from app.user_context import UserContext
from app.user_roles import UserRole


@pytest.mark.asyncio
async def test_from_user_copies_required_fields(test_user):
    ctx = UserContext.from_user(test_user)

    assert ctx.id == test_user.id
    assert ctx.username == test_user.username
    assert ctx.email == test_user.email
    assert ctx.role == test_user.role
    assert ctx.is_active is True


@pytest.mark.asyncio
async def test_from_user_preserves_admin_role(test_admin):
    ctx = UserContext.from_user(test_admin)

    assert ctx.role == UserRole.ADMIN
    assert isinstance(ctx.role, UserRole)


@pytest.mark.asyncio
async def test_from_user_reflects_inactive_flag(create_test_user):
    user = await create_test_user(
        username="deactivated",
        email="deactivated@test.com",
        is_active=False,
    )
    ctx = UserContext.from_user(user)

    assert ctx.is_active is False


def test_user_context_is_frozen():
    ctx = UserContext(
        id="abc", role=UserRole.STANDARD, username="u", email="u@example.com", is_active=True,
    )
    with pytest.raises(Exception):
        ctx.role = UserRole.ADMIN  # type: ignore[misc]
