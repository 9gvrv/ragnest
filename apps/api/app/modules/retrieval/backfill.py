"""Index every document that is not yet ``ready``.

Run from ``apps/api``::

    uv run python -m app.modules.retrieval.backfill

Useful after deploying the retrieval migration (existing documents start as
``pending``) and as a repair path for ``failed`` or stuck documents.
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.documents.models import Document
from app.modules.retrieval.embeddings import EmbeddingProvider, GeminiEmbeddingProvider
from app.modules.retrieval.service import index_document

logger = logging.getLogger(__name__)


async def backfill(
    session_factory: async_sessionmaker[AsyncSession],
    embeddings: EmbeddingProvider,
) -> tuple[int, int]:
    async with session_factory() as session:
        document_ids = list(
            (await session.execute(select(Document.id).where(Document.embedding_status != "ready")))
            .scalars()
            .all()
        )

    for document_id in document_ids:
        await index_document(document_id, session_factory, embeddings)

    return await _count_statuses(session_factory, document_ids)


async def _count_statuses(
    session_factory: async_sessionmaker[AsyncSession],
    document_ids: list[UUID],
) -> tuple[int, int]:
    if not document_ids:
        return 0, 0

    async with session_factory() as session:
        statuses = list(
            (
                await session.execute(
                    select(Document.embedding_status).where(Document.id.in_(document_ids))
                )
            )
            .scalars()
            .all()
        )

    return statuses.count("ready"), statuses.count("failed")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ready, failed = await backfill(SessionLocal, GeminiEmbeddingProvider(settings.GEMINI_API))
    logger.info("backfill finished: %d ready, %d failed", ready, failed)


if __name__ == "__main__":
    asyncio.run(main())
