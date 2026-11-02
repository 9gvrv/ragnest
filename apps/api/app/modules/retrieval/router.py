from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.retrieval import schemas, service
from app.modules.retrieval.deps import get_embedding_provider
from app.modules.retrieval.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.modules.workspaces.deps import require_workspace_member
from app.modules.workspaces.models import WorkspaceMember

router = APIRouter(prefix="/workspaces/{workspace_id}/search", tags=["retrieval"])


@router.post("", response_model=list[schemas.SearchResult])
async def search_chunks(
    workspace_id: UUID,
    body: schemas.SearchRequest,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> list[schemas.SearchResult]:
    try:
        query_vector = await embeddings.embed_query(body.query)
    except EmbeddingProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider unavailable",
        ) from exc

    hits = await service.search(session, workspace_id, query_vector, body.top_k)
    return [schemas.SearchResult.model_validate(hit) for hit in hits]
