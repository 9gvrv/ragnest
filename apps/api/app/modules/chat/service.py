from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.constants import DEFAULT_TITLE
from app.modules.chat.models import Conversation, Message


async def create_conversation(
    session: AsyncSession,
    workspace_id: UUID,
    created_by: UUID,
    title: str | None = None,
) -> Conversation:
    now = datetime.now(UTC)
    conversation = Conversation(
        workspace_id=workspace_id,
        created_by=created_by,
        title=title or DEFAULT_TITLE,
        created_at=now,
        updated_at=now,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations(
    session: AsyncSession,
    workspace_id: UUID,
    created_by: UUID,
) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_by == created_by,
        )
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_conversation(
    session: AsyncSession,
    workspace_id: UUID,
    conversation_id: UUID,
    created_by: UUID,
) -> Conversation:
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.workspace_id == workspace_id,
        Conversation.created_by == created_by,
    )
    conversation = (await session.execute(stmt)).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


async def delete_conversation(
    session: AsyncSession,
    workspace_id: UUID,
    conversation_id: UUID,
    created_by: UUID,
) -> None:
    conversation = await get_conversation(session, workspace_id, conversation_id, created_by)
    await session.delete(conversation)
    await session.commit()


async def list_messages(session: AsyncSession, conversation_id: UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
