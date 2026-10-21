from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


async def create_workspace(session: AsyncSession, name: str, creator: User) -> Workspace:
    workspace = Workspace(name=name, created_by=creator.id)
    session.add(workspace)
    await session.flush()  # get id
    member = WorkspaceMember(
        workspace_id=workspace.id, user_id=creator.id, role=WorkspaceRole.CREATOR
    )
    session.add(member)
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def list_workspaces_for_user(session: AsyncSession, user_id: UUID) -> list[Workspace]:
    stmt = (
        select(Workspace)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == user_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_members(session: AsyncSession, workspace_id: UUID) -> list[dict]:
    stmt = (
        select(
            WorkspaceMember.user_id,
            User.email,
            WorkspaceMember.role,
            WorkspaceMember.joined_at,
        )
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
    )
    result = await session.execute(stmt)
    return [dict(r) for r in result.mappings().all()]


async def remove_member(
    session: AsyncSession,
    workspace_id: UUID,
    target_user_id: UUID,
    actor_member: WorkspaceMember,
) -> None:
    # Load target member
    stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == target_user_id,
    )
    res = await session.execute(stmt)
    target = res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Cannot remove creator
    if target.role == WorkspaceRole.CREATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot remove creator")

    # Cannot remove self
    if target.user_id == actor_member.user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot remove yourself")

    # Actor rules
    if actor_member.role == WorkspaceRole.CREATOR:
        pass  # can remove others (not creator)
    elif actor_member.role == WorkspaceRole.ADMIN:
        if target.role in (WorkspaceRole.ADMIN, WorkspaceRole.CREATOR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    await session.delete(target)
    await session.commit()
