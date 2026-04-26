"""Service-layer session helper.

Thin wrapper around `async_session_factory` so UI pages and other
non-FastAPI callers open sessions through one documented entry point
instead of reaching into `app.database`.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory


@asynccontextmanager
async def service_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
