import os
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

from app.modules.documents.models import Document
from app.modules.retrieval.backfill import backfill
from app.modules.retrieval.constants import EMBEDDING_DIM
from app.modules.retrieval.embeddings import EmbeddingProviderError
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace


async def _seed(session_factory, statuses: list[str]) -> list[uuid.UUID]:
    async with session_factory() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", password_hash="not-used")
        session.add(user)
        await session.flush()

        workspace = Workspace(name="Acme", created_by=user.id)
        session.add(workspace)
        await session.flush()

        documents = []
        for index, status in enumerate(statuses):
            document = Document(
                workspace_id=workspace.id,
                uploaded_by=user.id,
                filename=f"doc-{index}.txt",
                content_type="text/plain",
                size_bytes=12,
                page_count=None,
                char_count=12,
                extracted_text="alpha alpha ",
                embedding_status=status,
            )
            documents.append(document)
        session.add_all(documents)
        await session.commit()
        return [document.id for document in documents]


async def _statuses(session_factory, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Document.id, Document.embedding_status).where(Document.id.in_(ids))
            )
        ).all()
    return dict(rows)


async def test_backfill_indexes_pending_and_skips_ready(session_factory, fake_embeddings):
    ids = await _seed(session_factory, ["pending", "failed", "ready"])

    ready, failed = await backfill(session_factory, fake_embeddings)

    assert (ready, failed) == (2, 0)
    assert await _statuses(session_factory, ids) == {
        ids[0]: "ready",
        ids[1]: "ready",
        ids[2]: "ready",
    }
    # The already-ready document was not embedded again.
    assert len(fake_embeddings.document_calls) == 2


class _FailOnceProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls == 1:
            raise EmbeddingProviderError("boom")
        return [[0.1] * EMBEDDING_DIM for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        raise AssertionError("not used")


async def test_backfill_continues_after_one_failure(session_factory):
    ids = await _seed(session_factory, ["pending", "pending"])
    provider = _FailOnceProvider()

    ready, failed = await backfill(session_factory, provider)

    assert (ready, failed) == (1, 1)
    assert await _statuses(session_factory, ids) == {
        ids[0]: "failed",
        ids[1]: "ready",
    }
    assert provider.calls == 2


def test_backfill_import_registers_every_model():
    """The CLI must load the aggregator or mapper configuration cannot resolve
    cross-module foreign keys (documents.uploaded_by -> users.id)."""
    api_root = Path(__file__).resolve().parents[3]
    code = (
        "from app.modules.retrieval import backfill;"
        "from sqlalchemy.orm import configure_mappers;"
        "configure_mappers()"
    )
    env = {
        **os.environ,
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/ragnest",
        "SECRET_KEY": "test-secret",
        "GEMINI_API": "test-key",
        "LLM_API_KEY": "test-key",
    }
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=api_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
