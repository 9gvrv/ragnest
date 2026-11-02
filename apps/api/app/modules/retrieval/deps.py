from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.retrieval.embeddings import EmbeddingProvider, GeminiEmbeddingProvider


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return SessionLocal


def get_embedding_provider() -> EmbeddingProvider:
    return GeminiEmbeddingProvider(settings.GEMINI_API)
