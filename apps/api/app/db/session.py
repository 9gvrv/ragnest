# sets up the database connection, creates sessions for queries
# and transactions, and provides a way to clean up the connection pool.

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession, async_sessionmaker

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    connect_args=settings.database_connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()
