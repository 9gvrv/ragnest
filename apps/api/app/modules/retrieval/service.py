"""Indexing pipeline: chunk a document, embed its chunks, store them.

The document row is created before this runs, so a provider failure never loses
an upload. A failed run keeps any previous chunk set and records the failure on
the document row for ``reindex``/backfill to repair.
"""

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.documents.models import Document
from app.modules.retrieval.chunking import chunk_text
from app.modules.retrieval.constants import EMBEDDING_MODEL
from app.modules.retrieval.embeddings import EmbeddingProvider
from app.modules.retrieval.models import DocumentChunk

logger = logging.getLogger(__name__)


async def index_document(
    document_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: EmbeddingProvider,
) -> None:
    try:
        async with session_factory() as session:
            document = await session.get(Document, document_id)
            if document is None:
                return
            document.embedding_status = "indexing"
            workspace_id = document.workspace_id
            text = document.extracted_text
            await session.commit()

        chunks = chunk_text(text)
        vectors = await embeddings.embed_documents([chunk.content for chunk in chunks])

        async with session_factory() as session:
            document = await session.get(Document, document_id)
            if document is None:
                return
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            session.add_all(
                [
                    DocumentChunk(
                        workspace_id=workspace_id,
                        document_id=document_id,
                        chunk_index=index,
                        content=chunk.content,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        embedding=vector,
                        embedding_model=EMBEDDING_MODEL,
                    )
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
                ]
            )
            document.embedding_status = "ready"
            document.indexed_at = datetime.now(UTC)
            await session.commit()
    except Exception as exc:  # noqa: BLE001 - the task must never escape
        logger.warning("indexing failed for document %s: %s", document_id, type(exc).__name__)
        await _mark_failed(document_id, session_factory)


async def _mark_failed(
    document_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return
        document.embedding_status = "failed"
        await session.commit()


@dataclass(frozen=True)
class SearchHit:
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    score: float
    char_start: int
    char_end: int


async def search(
    session: AsyncSession,
    workspace_id: UUID,
    query_vector: list[float],
    top_k: int,
) -> list[SearchHit]:
    if session.get_bind().dialect.name == "postgresql":
        return await _search_postgres(session, workspace_id, query_vector, top_k)
    return await _search_python(session, workspace_id, query_vector, top_k)


async def _search_postgres(
    session: AsyncSession,
    workspace_id: UUID,
    query_vector: list[float],
    top_k: int,
) -> list[SearchHit]:
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    stmt = (
        select(DocumentChunk, Document.filename, (1 - distance).label("score"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.workspace_id == workspace_id,
            DocumentChunk.embedding_model == EMBEDDING_MODEL,
        )
        .order_by(distance, DocumentChunk.document_id, DocumentChunk.chunk_index)
        .limit(top_k)
    )
    rows = (await session.execute(stmt)).all()
    return [
        SearchHit(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=float(score),
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        )
        for chunk, filename, score in rows
    ]


async def _search_python(
    session: AsyncSession,
    workspace_id: UUID,
    query_vector: list[float],
    top_k: int,
) -> list[SearchHit]:
    stmt = (
        select(DocumentChunk, Document.filename)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.workspace_id == workspace_id,
            DocumentChunk.embedding_model == EMBEDDING_MODEL,
        )
    )
    rows = (await session.execute(stmt)).all()
    hits = [
        SearchHit(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=_cosine_similarity(chunk.embedding, query_vector),
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        )
        for chunk, filename in rows
    ]
    hits.sort(key=lambda hit: (-hit.score, str(hit.document_id), hit.chunk_index))
    return hits[:top_k]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
