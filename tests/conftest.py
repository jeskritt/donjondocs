"""
AI Helper Docstring
Purpose: Global testing fixture setup via `pytest`. Generates and mocks the async in-memory SQLite instances to run integration checks quickly.
Interactions:
- Impacts EVERY test file executing in `/tests`. Overrides internal dependency mechanisms heavily (`get_db`).
"""

"""Shared test fixtures for the DonjonDocs test suite.

Provides:
- In-memory async SQLite database
- Test DB session with rollback
- Test client (httpx.AsyncClient) with auth helpers
- Factory fixtures for creating test users
"""

import asyncio
import os
from typing import AsyncGenerator

# Set test environment variables BEFORE importing anything from `app.*`,
# because app.database imports trigger Settings() at module load time.
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("STORAGE_SECRET", "test-storage-secret-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("ALLOW_REGISTRATION", "true")
os.environ.setdefault("DEBUG", "false")
# httpx ASGITransport sends Host: test; TestClient sends Host: testserver.
os.environ.setdefault("ALLOWED_HOSTS", "test,testserver,localhost,127.0.0.1")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import User, UserRole  # noqa: F401
from app.security import hash_password, create_access_token
from app.api.deps import get_db

# Clear settings cache so test env vars are picked up
from app.config import get_settings
get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory async SQLite engine for tests."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a test database session with rollback."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# App / Client fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def app_instance(db_engine):
    """Get the FastAPI/NiceGUI app with test DB override."""
    from main import app  # noqa: E402
    from app.rate_limit import limiter

    # Create a test session factory bound to the test engine
    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )

    async def override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    # SlowAPI uses in-memory storage by default; clear it per test so
    # bucket state doesn't leak between cases that hammer the same
    # endpoint.
    limiter.reset()
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app_instance) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient configured to talk to the test app."""
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Factory fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def create_test_user(db_session: AsyncSession):
    """Factory fixture to create test users."""
    created_users = []

    async def _factory(
        username: str = "testuser",
        email: str = "test@example.com",
        password: str = "TestPass123!",
        role: UserRole = UserRole.STANDARD,
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        created_users.append(user)
        return user

    return _factory


@pytest_asyncio.fixture
async def test_admin(create_test_user) -> User:
    """Create an admin test user."""
    return await create_test_user(
        username="admin",
        email="admin@test.com",
        role=UserRole.ADMIN,
    )


@pytest_asyncio.fixture
async def test_user(create_test_user) -> User:
    """Create a standard test user."""
    return await create_test_user(
        username="standard_user",
        email="user@test.com",
        role=UserRole.STANDARD,
    )


@pytest_asyncio.fixture
async def test_premium(create_test_user) -> User:
    """Create a premium test user."""
    return await create_test_user(
        username="premium_user",
        email="premium@test.com",
        role=UserRole.PREMIUM,
    )


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def auth_cookies(user: User) -> dict[str, str]:
    """Generate an auth cookie dict for a test user."""
    token = create_access_token(
        data={"sub": user.id, "role": user.role.value, "username": user.username}
    )
    return {"access_token": token}
