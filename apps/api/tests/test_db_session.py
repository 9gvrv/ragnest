from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import session as db_session


def test_engine_uses_asyncpg_driver():
    assert db_session.engine.url.drivername == "postgresql+asyncpg"


async def test_get_db_yields_and_closes_a_session(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(
        db_session, "SessionLocal", async_sessionmaker(engine, expire_on_commit=False)
    )

    yielded = None
    async for s in db_session.get_db():
        yielded = s
        assert isinstance(s, AsyncSession)
    # generator finished -> context manager exited -> session closed
    assert yielded is not None
    await engine.dispose()
