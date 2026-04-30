"""
AI Helper Docstring
Purpose: Alembic migration environment configuration. Bootstraps the database connection for auto-generating and applying schema migrations.
Interactions:
- `app.database.Base`: Imports the declarative base to inspect metadata.
- `app.models.*`: Imports all standard tables so Alembic detects their structures.
"""

"""Alembic environment configuration for async SQLAlchemy.

Reads DATABASE_URL from app settings and uses async engine for migrations.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.database import Base

# Import every model module so its tables register on Base.metadata
# before autogenerate inspects it. Importing the modules (not symbols)
# is sufficient — the side effect is what matters.
from app.models import user, character, character_addons, char_sheet  # noqa: F401

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata for autogenerate
target_metadata = Base.metadata

# Read the database URL from app settings. Do NOT route this through
# config.set_main_option / alembic.ini — configparser treats '%' as
# interpolation syntax and rejects URL-encoded password chars (%40, %3F,
# %25, ...). Inject the URL into the engine config dict instead.
settings = get_settings()
DATABASE_URL = settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without requiring a live database connection.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    # Mirror app/database.py: Supabase's pgbouncer pooler (port 6543) is
    # in transaction mode and does not support prepared statements.
    connect_args: dict = {}
    if "asyncpg" in DATABASE_URL:
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0

    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
