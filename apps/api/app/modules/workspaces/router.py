from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.deps import get_current_user
from app.modules.invitations import schemas as inv_schemas
from app.modules.invitations import service as inv_service
from app.modules.users.models import User
from app.modules.workspaces import schemas, service
from app.modules.workspaces.deps import (
    require_workspace_admin_or_creator,
    require_workspace_creator,
    require_workspace_member,
)
from app.modules.workspaces.models import WorkspaceMember

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=schemas.WorkspaceRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=schemas.WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: schemas.WorkspaceCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> schemas.WorkspaceRead:
    ws = await service.create_workspace(session, data.name, current_user)
    return schemas.WorkspaceRead.model_validate(ws)


@router.get("", response_model=list[schemas.WorkspaceRead])
@router.get("/", response_model=list[schemas.WorkspaceRead])
async def list_workspaces(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[schemas.WorkspaceRead]:
    wss = await service.list_workspaces_for_user(session, current_user.id)
    return [schemas.WorkspaceRead.model_validate(w) for w in wss]


@router.get("/{workspace_id}", response_model=schemas.WorkspaceRead)
async def get_workspace(
    workspace_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.WorkspaceRead:
    from app.modules.workspaces.models import Workspace

    ws = await session.get(Workspace, workspace_id)
    return schemas.WorkspaceRead.model_validate(
        ws
    )  # ws exists if member valid context; but just fetch


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    creator_member: Annotated[WorkspaceMember, Depends(require_workspace_creator)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    from app.modules.workspaces.models import Workspace

    ws = await session.get(Workspace, workspace_id)
    if ws:
        await session.delete(ws)
        await session.commit()


@router.get("/{workspace_id}/members", response_model=list[schemas.MemberRead])
async def list_members(
    workspace_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[schemas.MemberRead]:
    members = await service.list_members(session, workspace_id)
    return [schemas.MemberRead.model_validate(m) for m in members]


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: UUID,
    user_id: UUID,
    actor_member: Annotated[WorkspaceMember, Depends(require_workspace_admin_or_creator)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.remove_member(session, workspace_id, user_id, actor_member)


@router.post(
    "/{workspace_id}/invitations/check", response_model=inv_schemas.InvitationCheckResponse
)
async def check_invitation(
    workspace_id: UUID,
    data: inv_schemas.InvitationCheckRequest,
    actor_member: Annotated[WorkspaceMember, Depends(require_workspace_admin_or_creator)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> inv_schemas.InvitationCheckResponse:
    user = await inv_service.check_user_exists(session, data.email)
    if user:
        return inv_schemas.InvitationCheckResponse(exists=True, user_id=user.id)
    return inv_schemas.InvitationCheckResponse(exists=False, user_id=None)


@router.post("/{workspace_id}/invitations", status_code=status.HTTP_201_CREATED)
async def create_invitation(
    workspace_id: UUID,
    data: inv_schemas.InvitationCreateRequest,
    actor_member: Annotated[WorkspaceMember, Depends(require_workspace_admin_or_creator)],
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> inv_schemas.InvitationCreateResponse:
    user = await inv_service.check_user_exists(session, data.email)
    inv = await inv_service.create_invitation(
        session, workspace_id, current_user.id, data.email, data.role
    )
    link = f"/invitations/{inv.token}/accept"
    return inv_schemas.InvitationCreateResponse(
        exists=user is not None,
        invitation_id=inv.id,
        email=inv.email,
        role=inv.role,
        token=inv.token,
        expires_at=inv.expires_at,
        link=link,
    )
