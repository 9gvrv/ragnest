import asyncio
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.modules.documents.extraction import extract, safe_filename
from app.modules.documents.models import Document
from app.modules.workspaces.models import WorkspaceMember, WorkspaceRole


def can_manage(member: WorkspaceMember, document: Document) -> bool:
    return document.uploaded_by == member.user_id or member.role in (
        WorkspaceRole.CREATOR,
        WorkspaceRole.ADMIN,
    )


async def ingest(
    session: AsyncSession,
    workspace_id: UUID,
    uploaded_by: UUID,
    filename: str,
    data: bytes,
) -> Document:
    name = safe_filename(filename)
    extracted = await asyncio.to_thread(extract, name, data)

    document = Document(
        workspace_id=workspace_id,
        uploaded_by=uploaded_by,
        filename=name,
        content_type=extracted.content_type,
        size_bytes=extracted.size_bytes,
        page_count=extracted.page_count,
        char_count=extracted.char_count,
        extracted_text=extracted.text,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def list_documents(
    session: AsyncSession,
    workspace_id: UUID,
    mine: UUID | None = None,
) -> list[Document]:
    stmt = (
        select(Document)
        .options(
            load_only(
                Document.id,
                Document.workspace_id,
                Document.uploaded_by,
                Document.filename,
                Document.content_type,
                Document.size_bytes,
                Document.page_count,
                Document.char_count,
                Document.created_at,
            )
        )
        .where(Document.workspace_id == workspace_id)
    )
    if mine is not None:
        stmt = stmt.where(Document.uploaded_by == mine)
    stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_document(session: AsyncSession, workspace_id: UUID, document_id: UUID) -> Document:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


async def delete_document(
    session: AsyncSession,
    workspace_id: UUID,
    document_id: UUID,
    member: WorkspaceMember,
) -> None:
    document = await get_document(session, workspace_id, document_id)
    if not can_manage(member, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    await session.delete(document)
    await session.commit()
