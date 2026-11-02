# conftest.py

import hashlib
import math
import os
import re

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ragnest"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-bytes-long")
os.environ.setdefault("GEMINI_API", "test-gemini-key")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401  (register all models on Base.metadata)
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.modules.retrieval.constants import EMBEDDING_DIM
from app.modules.retrieval.embeddings import EmbeddingProviderError


class FakeEmbeddingProvider:
    """Deterministic bag-of-tokens embedding; no network, stable across runs."""

    def __init__(self) -> None:
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [_embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return _embed(text)


class FailingEmbeddingProvider:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingProviderError("provider unavailable")

    async def embed_query(self, text: str) -> list[float]:
        raise EmbeddingProviderError("provider unavailable")


def _embed(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(digest[:4], "big") % EMBEDDING_DIM] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


@pytest.fixture
def fake_embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def failing_embeddings() -> FailingEmbeddingProvider:
    return FailingEmbeddingProvider()


@pytest_asyncio.fixture
async def session_factory():
    # StaticPool keeps ONE connection, so the in-memory DB (and its tables)
    # persist across sessions within a test.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        # SQLite ships with foreign keys OFF; without this ON DELETE CASCADE
        # and FK constraints are silently ignored in every test.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    app = create_app()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
