from datetime import datetime

import pytest_asyncio

from app.modules.auth.security import create_access_token
from app.modules.documents.models import Document
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


async def insert_document(
    session_factory,
    workspace_id,
    uploaded_by,
    filename="doc.txt",
    text="document text",
    created_at: datetime | None = None,
) -> Document:
    async with session_factory() as session:
        document = Document(
            workspace_id=workspace_id,
            uploaded_by=uploaded_by,
            filename=filename,
            content_type="text/plain",
            size_bytes=len(text),
            page_count=None,
            char_count=len(text),
            extracted_text=text,
        )
        if created_at is not None:
            document.created_at = created_at
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document


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
