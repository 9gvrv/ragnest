import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.documents.models import Document
from app.modules.retrieval.constants import EMBEDDING_DIM, EMBEDDING_MODEL
from app.modules.retrieval.models import DocumentChunk
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace


async def _seed_document(session) -> tuple[User, Workspace, Document]:
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
        size_bytes=11,
        page_count=None,
        char_count=11,
        extracted_text="hello world",
    )
    session.add(document)
    await session.flush()
    return user, workspace, document


def _chunk(document: Document, index: int = 0) -> DocumentChunk:
    return DocumentChunk(
        workspace_id=document.workspace_id,
        document_id=document.id,
        chunk_index=index,
        content="hello world",
        char_start=0,
        char_end=11,
        embedding=[0.1] * EMBEDDING_DIM,
        embedding_model=EMBEDDING_MODEL,
    )


async def test_chunk_round_trip_on_sqlite(session_factory):
    async with session_factory() as session:
        _, _, document = await _seed_document(session)
        session.add(_chunk(document))
        await session.commit()
        chunk_id = (await session.execute(_select_chunk_id())).scalar_one()

    async with session_factory() as session:
        fetched = await session.get(DocumentChunk, chunk_id)

    assert fetched is not None
    assert fetched.embedding == pytest.approx([0.1] * EMBEDDING_DIM)
    assert (fetched.char_start, fetched.char_end) == (0, 11)
    assert fetched.content == "hello world"
    assert fetched.embedding_model == EMBEDDING_MODEL


async def test_document_embedding_status_defaults_to_pending(session_factory):
    async with session_factory() as session:
        _, _, document = await _seed_document(session)
        await session.commit()
        document_id = document.id

    async with session_factory() as session:
        fetched = await session.get(Document, document_id)

    assert fetched.embedding_status == "pending"
    assert fetched.indexed_at is None


async def test_deleting_document_cascades_chunks(session_factory):
    async with session_factory() as session:
        _, _, document = await _seed_document(session)
        session.add(_chunk(document))
        await session.commit()
        document_id = document.id
        chunk_id = (await session.execute(_select_chunk_id())).scalar_one()

    async with session_factory() as session:
        document = await session.get(Document, document_id)
        await session.delete(document)
        await session.commit()

    async with session_factory() as session:
        assert await session.get(DocumentChunk, chunk_id) is None


async def test_deleting_workspace_cascades_chunks(session_factory):
    async with session_factory() as session:
        _, workspace, document = await _seed_document(session)
        session.add(_chunk(document))
        await session.commit()
        workspace_id = workspace.id
        document_id = document.id
        chunk_id = (await session.execute(_select_chunk_id())).scalar_one()

    async with session_factory() as session:
        workspace = await session.get(Workspace, workspace_id)
        await session.delete(workspace)
        await session.commit()

    async with session_factory() as session:
        assert await session.get(Document, document_id) is None
        assert await session.get(DocumentChunk, chunk_id) is None


async def test_chunk_index_is_unique_per_document(session_factory):
    async with session_factory() as session:
        _, _, document = await _seed_document(session)
        session.add(_chunk(document, index=0))
        await session.flush()
        session.add(_chunk(document, index=0))
        with pytest.raises(IntegrityError):
            await session.flush()


def _select_chunk_id():
    from sqlalchemy import select

    return select(DocumentChunk.id)
