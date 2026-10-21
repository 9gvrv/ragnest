from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.deps import get_current_user
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


async def get_workspace(
    workspace_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Workspace:
    ws = await session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return ws


async def require_workspace_member(
    workspace_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkspaceMember:
    stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == current_user.id,
    )
    result = await session.execute(stmt)
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    return member


async def require_workspace_admin_or_creator(
    workspace_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkspaceMember:
    member = await require_workspace_member(workspace_id, session, current_user)
    if member.role not in (WorkspaceRole.ADMIN, WorkspaceRole.CREATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    return member


async def require_workspace_creator(
    workspace_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkspaceMember:
    member = await require_workspace_member(workspace_id, session, current_user)
    if member.role != WorkspaceRole.CREATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can perform this action"
        )
    return member
