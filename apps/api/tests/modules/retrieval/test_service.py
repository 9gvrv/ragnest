import uuid

import pytest
from sqlalchemy import select

from app.modules.documents.models import Document
from app.modules.retrieval.constants import EMBEDDING_DIM, EMBEDDING_MODEL
from app.modules.retrieval.models import DocumentChunk
from app.modules.retrieval.service import index_document
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace


async def _seed_document(session, text: str) -> Document:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="not-used")
    session.add(user)
    await session.flush()

    workspace = Workspace(name="Acme", created_by=user.id)
    session.add(workspace)
    await session.flush()

    document = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        filename="notes.txt",
        content_type="text/plain",
        size_bytes=len(text),
        page_count=None,
        char_count=len(text),
        extracted_text=text,
    )
    session.add(document)
    await session.commit()
    return document


async def _chunks(session_factory) -> list[DocumentChunk]:
    async with session_factory() as session:
        return list(
            (await session.execute(select(DocumentChunk).order_by(DocumentChunk.chunk_index)))
            .scalars()
            .all()
        )


async def test_index_document_stores_chunks_and_marks_ready(session_factory, fake_embeddings):
    text = "alpha " * 400
    async with session_factory() as session:
        document = await _seed_document(session, text)
        document_id = document.id

    await index_document(document_id, session_factory, fake_embeddings)

    async with session_factory() as session:
        stored = await session.get(Document, document_id)

    assert stored.embedding_status == "ready"
    assert stored.indexed_at is not None

    chunks = await _chunks(session_factory)
    assert chunks
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk.content == text[chunk.char_start : chunk.char_end]
        assert chunk.embedding_model == EMBEDDING_MODEL
        assert len(chunk.embedding) == EMBEDDING_DIM
    assert fake_embeddings.document_calls


async def test_index_document_failure_marks_failed_and_keeps_document(
    session_factory, failing_embeddings
):
    async with session_factory() as session:
        document = await _seed_document(session, "alpha " * 400)
        document_id = document.id

    await index_document(document_id, session_factory, failing_embeddings)

    async with session_factory() as session:
        stored = await session.get(Document, document_id)

    assert stored is not None
    assert stored.embedding_status == "failed"
    assert stored.indexed_at is None
    assert await _chunks(session_factory) == []


async def test_reindex_replaces_previous_chunks(session_factory, fake_embeddings):
    async with session_factory() as session:
        document = await _seed_document(session, "alpha " * 400)
        document_id = document.id

    await index_document(document_id, session_factory, fake_embeddings)
    old_ids = {chunk.id for chunk in await _chunks(session_factory)}

    async with session_factory() as session:
        document = await session.get(Document, document_id)
        document.extracted_text = "beta " * 400
        await session.commit()

    await index_document(document_id, session_factory, fake_embeddings)

    new_chunks = await _chunks(session_factory)
    assert new_chunks
    assert {chunk.id for chunk in new_chunks}.isdisjoint(old_ids)
    assert all("beta" in chunk.content for chunk in new_chunks)


async def test_index_document_missing_document_returns_quietly(session_factory, fake_embeddings):
    await index_document(uuid.uuid4(), session_factory, fake_embeddings)
    assert await _chunks(session_factory) == []


class _DeletingProvider:
    def __init__(self, session_factory, document_id):
        self._session_factory = session_factory
        self._document_id = document_id

    async def embed_documents(self, texts):
        async with self._session_factory() as session:
            document = await session.get(Document, self._document_id)
            await session.delete(document)
            await session.commit()
        return [[0.1] * EMBEDDING_DIM for _ in texts]

    async def embed_query(self, text):
        raise AssertionError("not used")


async def test_index_document_deleted_mid_run_leaves_no_chunks(session_factory):
    async with session_factory() as session:
        document = await _seed_document(session, "alpha " * 400)
        document_id = document.id

    provider = _DeletingProvider(session_factory, document_id)
    await index_document(document_id, session_factory, provider)

    assert await _chunks(session_factory) == []


@pytest.mark.parametrize("status", ["pending", "indexing", "failed"])
async def test_index_document_recovers_from_non_ready_status(
    session_factory, fake_embeddings, status
):
    async with session_factory() as session:
        document = await _seed_document(session, "alpha " * 400)
        document.embedding_status = status
        await session.commit()
        document_id = document.id

    await index_document(document_id, session_factory, fake_embeddings)

    async with session_factory() as session:
        stored = await session.get(Document, document_id)

    assert stored.embedding_status == "ready"
