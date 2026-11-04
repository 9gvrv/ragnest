from datetime import datetime
from uuid import UUID

import pytest_asyncio

from app.modules.auth.security import create_access_token
from app.modules.chat.constants import DEFAULT_TITLE
from app.modules.chat.models import Conversation, Message
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


async def insert_workspace(session_factory, owner: User, name: str = "Other") -> Workspace:
    async with session_factory() as session:
        workspace = Workspace(name=name, created_by=owner.id)
        session.add(workspace)
        await session.flush()
        session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role=WorkspaceRole.CREATOR)
        )
        await session.commit()
        await session.refresh(workspace)
        return workspace


async def insert_conversation(
    session_factory,
    workspace_id: UUID,
    created_by: UUID,
    title: str = DEFAULT_TITLE,
    updated_at: datetime | None = None,
) -> Conversation:
    async with session_factory() as session:
        conversation = Conversation(
            workspace_id=workspace_id,
            created_by=created_by,
            title=title,
        )
        if updated_at is not None:
            conversation.updated_at = updated_at
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation


async def insert_message(
    session_factory,
    conversation_id: UUID,
    role: str = "user",
    content: str = "hello",
    citations: list[dict] | None = None,
    model: str | None = None,
    finish_reason: str | None = None,
    created_at: datetime | None = None,
) -> Message:
    async with session_factory() as session:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations or [],
            model=model,
            finish_reason=finish_reason,
        )
        if created_at is not None:
            message.created_at = created_at
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message


@pytest_asyncio.fixture
async def seed(session_factory):
    async with session_factory() as session:
        creator = User(email="creator@example.com", password_hash="not-used")
        admin = User(email="admin@example.com", password_hash="not-used")
        member = User(email="member@example.com", password_hash="not-used")
        outsider = User(email="outsider@example.com", password_hash="not-used")
        session.add_all([creator, admin, member, outsider])
        await session.flush()

        workspace = Workspace(name="Acme", created_by=creator.id)
        session.add(workspace)
        await session.flush()

        session.add_all(
            [
                WorkspaceMember(
                    workspace_id=workspace.id, user_id=creator.id, role=WorkspaceRole.CREATOR
                ),
                WorkspaceMember(
                    workspace_id=workspace.id, user_id=admin.id, role=WorkspaceRole.ADMIN
                ),
                WorkspaceMember(
                    workspace_id=workspace.id, user_id=member.id, role=WorkspaceRole.MEMBER
                ),
            ]
        )
        await session.commit()
        workspace_id = workspace.id

    users = {
        "creator": creator,
        "admin": admin,
        "member": member,
        "outsider": outsider,
    }
    return {
        "workspace_id": workspace_id,
        "users": users,
        "headers": {role: auth_header(user) for role, user in users.items()},
        "ids": {role: user.id for role, user in users.items()},
    }
