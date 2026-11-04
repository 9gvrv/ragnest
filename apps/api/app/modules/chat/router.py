from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.chat import schemas, service
from app.modules.workspaces.deps import require_workspace_member
from app.modules.workspaces.models import WorkspaceMember

router = APIRouter(
    prefix="/workspaces/{workspace_id}/conversations",
    tags=["chat"],
)


@router.post("", response_model=schemas.ConversationSummary, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    workspace_id: UUID,
    body: schemas.ConversationCreate,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.ConversationSummary:
    conversation = await service.create_conversation(
        session, workspace_id, member.user_id, body.title
    )
    return schemas.ConversationSummary.model_validate(conversation)


@router.get("", response_model=list[schemas.ConversationSummary])
async def list_conversations(
    workspace_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[schemas.ConversationSummary]:
    conversations = await service.list_conversations(session, workspace_id, member.user_id)
    return [schemas.ConversationSummary.model_validate(item) for item in conversations]


@router.get("/{conversation_id}", response_model=schemas.ConversationDetail)
async def get_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.ConversationDetail:
    conversation = await service.get_conversation(
        session, workspace_id, conversation_id, member.user_id
    )
    messages = await service.list_messages(session, conversation.id)
    summary = schemas.ConversationSummary.model_validate(conversation)
    return schemas.ConversationDetail(
        **summary.model_dump(),
        messages=[schemas.MessageOut.model_validate(message) for message in messages],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.delete_conversation(session, workspace_id, conversation_id, member.user_id)
