from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

ENGINE = create_async_engine("sqlite+aiosqlite:///dev.db", pool_size=5)
SESSION_MAKER = async_sessionmaker(bind=ENGINE)


async def get_session_dependency():
    session = SESSION_MAKER()
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_session():
    session = SESSION_MAKER()
    try:
        yield session
    finally:
        await session.close()
