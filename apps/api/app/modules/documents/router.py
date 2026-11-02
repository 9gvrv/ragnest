from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_db
from app.modules.documents import schemas, service
from app.modules.documents.extraction import MAX_UPLOAD_BYTES, ExtractionError
from app.modules.retrieval.deps import get_embedding_provider, get_session_factory
from app.modules.retrieval.embeddings import EmbeddingProvider
from app.modules.retrieval.service import index_document
from app.modules.workspaces.deps import require_workspace_member
from app.modules.workspaces.models import WorkspaceMember

router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])


@router.post("", response_model=schemas.DocumentSummary, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: UUID,
    file: Annotated[UploadFile, File()],
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> schemas.DocumentSummary:
    # Read no more than the cap plus one byte, so a chunked upload without a
    # Content-Length cannot be loaded into memory in full.
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        document = await service.ingest(
            session, workspace_id, member.user_id, file.filename or "", data
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    background_tasks.add_task(index_document, document.id, session_factory, embeddings)
    return schemas.DocumentSummary.model_validate(document)


@router.get("", response_model=list[schemas.DocumentSummary])
async def list_documents(
    workspace_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
    mine: bool = False,
) -> list[schemas.DocumentSummary]:
    documents = await service.list_documents(
        session, workspace_id, mine=member.user_id if mine else None
    )
    return [schemas.DocumentSummary.model_validate(d) for d in documents]


@router.get("/{document_id}", response_model=schemas.DocumentDetail)
async def get_document(
    workspace_id: UUID,
    document_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.DocumentDetail:
    document = await service.get_document(session, workspace_id, document_id)
    return schemas.DocumentDetail.model_validate(document)


@router.post(
    "/{document_id}/reindex",
    response_model=schemas.ReindexResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reindex_document(
    workspace_id: UUID,
    document_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> schemas.ReindexResponse:
    document = await service.get_document(session, workspace_id, document_id)
    if not service.can_manage(member, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    document.embedding_status = "pending"
    await session.commit()
    background_tasks.add_task(index_document, document_id, session_factory, embeddings)
    return schemas.ReindexResponse(embedding_status="pending")


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    workspace_id: UUID,
    document_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await service.delete_document(session, workspace_id, document_id, member)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
