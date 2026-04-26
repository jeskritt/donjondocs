"""
AI Helper Docstring
Purpose: Async SQLAlchemy Engine and Session maker. Configures `aiosqlite` connections and sets up the declarative `Base` class.
Interactions:
- `app.config.py`: Retrieves `DATABASE_URL` runtime settings.
- `app.models.*`: Acts as the parent declarative class `Base`.
- `app.api.deps.py`: Vends the `get_db` generator.
"""

"""Async SQLAlchemy database setup.

Loose coupling: switch DATABASE_URL from sqlite+aiosqlite:// to
postgresql+asyncpg:// for production without changing any other code.
"""

from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import MetaData, DateTime
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from app.config import get_settings

# Naming convention for consistent constraint names across SQLite and PostgreSQL
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base with naming conventions for Alembic compatibility."""

    metadata = MetaData(naming_convention=convention)


class TimestampMixin:
    """Mixin that adds auto-managed created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


def _create_engine():
    """Create the async engine from settings."""
    settings = get_settings()
    connect_args = {}
    pool_kwargs = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif "asyncpg" in settings.DATABASE_URL:
        # Supabase uses PgBouncer (port 6543) in transaction mode, which
        # does not support prepared statements.  Disable asyncpg's
        # statement cache to avoid DuplicatePreparedStatementError.
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
        pool_kwargs["pool_pre_ping"] = True
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args=connect_args,
        **pool_kwargs,
    )


engine = _create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
