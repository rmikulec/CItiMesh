from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ENGINE = create_async_engine("sqlite+aiosqlite:///dev.db", pool_size=5)
SESSION_MAKER = async_sessionmaker(bind=ENGINE)


async def get_session_dependency() -> AsyncGenerator[AsyncSession]:
    """
    A FastAPI dependency to inject a Async SQLAlchemy session into a route
    """
    session = SESSION_MAKER()
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    """
    A async context manager to properly handle a Async SQLAlchemy session
    """
    session = SESSION_MAKER()
    try:
        yield session
    finally:
        await session.close()
