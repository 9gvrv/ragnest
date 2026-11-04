# conftest.py

import hashlib
import math
import os
import re
from collections.abc import AsyncIterator

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ragnest"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-bytes-long")
os.environ.setdefault("GEMINI_API", "test-gemini-key")
os.environ.setdefault("LLM_API_KEY", "test-llm-key")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db.models
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.modules.chat.deps import get_llm_provider
from app.modules.chat.llm import (
    LLMDelta,
    LLMEvent,
    LLMFinish,
    LLMMessage,
    LLMProviderError,
)
from app.modules.retrieval.constants import EMBEDDING_DIM
from app.modules.retrieval.deps import get_embedding_provider, get_session_factory
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


class FakeLLMProvider:
    """Deterministic generator; records prompts and can fail mid-stream."""

    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.deltas = ["Grounded ", "answer ", "[1]"]
        self.fail_after: int | None = None

    def stream(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = 1024,
    ) -> AsyncIterator[LLMEvent]:
        self.calls.append(list(messages))
        return self._events()

    async def _events(self) -> AsyncIterator[LLMEvent]:
        for index, text in enumerate(self.deltas):
            if self.fail_after is not None and index >= self.fail_after:
                raise LLMProviderError("provider failed mid-stream")
            yield LLMDelta(text)
        yield LLMFinish("stop")


class FailingLLMProvider:
    def __init__(self, status_code: int | None = None) -> None:
        self.status_code = status_code

    def stream(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = 1024,
    ) -> AsyncIterator[LLMEvent]:
        return self._events()

    async def _events(self) -> AsyncIterator[LLMEvent]:
        raise LLMProviderError("provider unavailable", status_code=self.status_code)
        yield LLMFinish("stop")  # pragma: no cover - makes this a generator


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


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def failing_llm() -> FailingLLMProvider:
    return FailingLLMProvider()


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
async def app(session_factory, fake_embeddings, fake_llm):
    application = create_app()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
    application.dependency_overrides[get_session_factory] = lambda: session_factory
    application.dependency_overrides[get_llm_provider] = lambda: fake_llm
    return application


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
