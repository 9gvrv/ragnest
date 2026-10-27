import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.invitations.models import Invitation, InvitationStatus
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


async def check_user_exists(session: AsyncSession, email: str) -> User | None:
    email_norm = email.lower().strip()
    stmt = select(User).where(User.email == email_norm)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_invitation(
    session: AsyncSession,
    workspace_id,
    inviter_id,
    email: str,
    role: WorkspaceRole,
    expires_days: int = 7,
) -> Invitation:
    if role == WorkspaceRole.CREATOR:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot invite as creator"
        )

    email_norm = email.lower().strip()
    # Check not already member
    stmt = (
        select(WorkspaceMember)
        .join(User)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            User.email == email_norm,
        )
    )
    res = await session.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already a member")

    # Check pending invite exists
    stmt = select(Invitation).where(
        Invitation.workspace_id == workspace_id,
        Invitation.email == email_norm,
        Invitation.status == InvitationStatus.PENDING,
    )
    res = await session.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Pending invitation already exists"
        )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=expires_days)
    inv = Invitation(
        workspace_id=workspace_id,
        inviter_id=inviter_id,
        email=email_norm,
        role=role,
        token=token,
        status=InvitationStatus.PENDING,
        expires_at=expires_at,
    )
    session.add(inv)
    await session.commit()
    await session.refresh(inv)
    return inv


async def get_invitation_by_token(session: AsyncSession, token: str) -> Invitation | None:
    stmt = select(Invitation).where(Invitation.token == token)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def accept_invitation(
    session: AsyncSession, invitation: Invitation, user: User
) -> WorkspaceMember:
    now = datetime.now(UTC)
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation not pending"
        )
    if invitation.expires_at < now:
        invitation.status = InvitationStatus.EXPIRED
        await session.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation expired")

    if invitation.email.lower() != user.email.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email mismatch")

    # Check if already member
    stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == invitation.workspace_id,
        WorkspaceMember.user_id == user.id,
    )
    res = await session.execute(stmt)
    member = res.scalar_one_or_none()
    if member:
        invitation.status = InvitationStatus.ACCEPTED
        await session.commit()
        return member

    member = WorkspaceMember(
        workspace_id=invitation.workspace_id,
        user_id=user.id,
        role=invitation.role,
    )
    session.add(member)
    invitation.status = InvitationStatus.ACCEPTED
    await session.commit()
    await session.refresh(member)
    return member


async def decline_invitation(session: AsyncSession, invitation: Invitation) -> None:
    now = datetime.now(UTC)
    if invitation.expires_at < now and invitation.status == InvitationStatus.PENDING:
        invitation.status = InvitationStatus.EXPIRED
        await session.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation expired")
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation not pending"
        )
    invitation.status = InvitationStatus.DECLINED
    await session.commit()


async def list_pending_for_user(session: AsyncSession, user: User) -> list[dict]:
    email_norm = user.email.lower()
    stmt = (
        select(
            Invitation.id.label("invitation_id"),
            Invitation.workspace_id,
            Workspace.name.label("workspace_name"),
            User.email.label("inviter_email"),
            Invitation.email,
            Invitation.role,
            Invitation.token,
            Invitation.expires_at,
            Invitation.created_at,
        )
        .join(Workspace, Workspace.id == Invitation.workspace_id)
        .join(User, User.id == Invitation.inviter_id, isouter=True)
        .where(Invitation.email == email_norm, Invitation.status == InvitationStatus.PENDING)
    )
    res = await session.execute(stmt)
    return [dict(r) for r in res.mappings().all()]


async def get_invitation_preview(session: AsyncSession, token: str) -> dict | None:
    stmt = (
        select(
            Invitation.id.label("invitation_id"),
            Invitation.workspace_id,
            Workspace.name.label("workspace_name"),
            User.email.label("inviter_email"),
            Invitation.email,
            Invitation.role,
            Invitation.status,
            Invitation.expires_at,
            Invitation.created_at,
        )
        .join(Workspace, Workspace.id == Invitation.workspace_id)
        .join(User, User.id == Invitation.inviter_id, isouter=True)
        .where(Invitation.token == token)
    )
    res = await session.execute(stmt)
    row = res.mappings().one_or_none()
    return dict(row) if row else None
