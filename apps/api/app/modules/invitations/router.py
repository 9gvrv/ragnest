from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.deps import get_current_user
from app.modules.invitations import schemas, service
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get("/pending", response_model=list[schemas.InvitationPendingRead])
async def list_pending(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[schemas.InvitationPendingRead]:
    items = await service.list_pending_for_user(session, current_user)
    return [schemas.InvitationPendingRead.model_validate(i) for i in items]


@router.get("/{token}", response_model=schemas.InvitationPreviewRead)
async def preview_invitation(
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.InvitationPreviewRead:
    """Public: the token is the capability, so no session is required."""
    preview = await service.get_invitation_preview(session, token)
    if not preview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return schemas.InvitationPreviewRead.model_validate(preview)


@router.post("/{token}/accept", response_model=schemas.InvitationAcceptResponse)
async def accept_invitation(
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> schemas.InvitationAcceptResponse:
    inv = await service.get_invitation_by_token(session, token)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    member = await service.accept_invitation(session, inv, current_user)
    ws = await session.get(Workspace, inv.workspace_id)
    workspace_name = ws.name if ws else ""
    return schemas.InvitationAcceptResponse(
        workspace_id=inv.workspace_id,
        role=member.role,
        workspace_name=workspace_name,
    )


@router.post("/{token}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_invitation(
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    inv = await service.get_invitation_by_token(session, token)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    await service.decline_invitation(session, inv)
