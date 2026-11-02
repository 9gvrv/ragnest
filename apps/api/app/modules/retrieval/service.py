"""Indexing pipeline: chunk a document, embed its chunks, store them.

The document row is created before this runs, so a provider failure never loses
an upload. A failed run keeps any previous chunk set and records the failure on
the document row for ``reindex``/backfill to repair.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete
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
