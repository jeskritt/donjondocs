import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role, get_current_user, get_db
from app.models.user import User, UserRole

@pytest.mark.asyncio
async def test_require_role_success():
    admin_user = User(username="admin", role=UserRole.ADMIN, hashed_password="hash")
    role_checker = require_role(UserRole.ADMIN)
    
    result = await role_checker(admin_user)
    assert result == admin_user

@pytest.mark.asyncio
async def test_require_role_forbidden():
    standard_user = User(username="standard", role=UserRole.STANDARD, hashed_password="hash")
    role_checker = require_role(UserRole.ADMIN)
    
    with pytest.raises(HTTPException) as excinfo:
        await role_checker(standard_user)
        
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Insufficient permissions"

@pytest.mark.asyncio
async def test_get_current_user_no_token():
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(db=None, access_token=None)
        
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Not authenticated"
