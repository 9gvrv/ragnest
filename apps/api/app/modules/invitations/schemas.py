from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.modules.invitations.models import InvitationStatus
from app.modules.workspaces.models import WorkspaceRole


class InvitationCheckRequest(BaseModel):
    email: EmailStr


class InvitationCheckResponse(BaseModel):
    exists: bool
    user_id: UUID | None = None


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: WorkspaceRole

    @field_validator("role")
    @classmethod
    def role_must_not_be_creator(cls, v: WorkspaceRole) -> WorkspaceRole:
        if v == WorkspaceRole.CREATOR:
            raise ValueError("cannot invite as creator")
        return v


class InvitationCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exists: bool = True
    invitation_id: UUID | None = None
    email: str
    role: WorkspaceRole
    token: str | None = None
    expires_at: datetime | None = None
    link: str | None = None
    message: str | None = None


class InvitationPendingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invitation_id: UUID
    workspace_id: UUID
    workspace_name: str
    inviter_email: str | None = None
    email: str
    role: WorkspaceRole
    token: str
    expires_at: datetime
    created_at: datetime


class InvitationPreviewRead(BaseModel):
    """What a link holder may see before accepting."""

    model_config = ConfigDict(from_attributes=True)

    invitation_id: UUID
    workspace_id: UUID
    workspace_name: str
    inviter_email: str | None = None
    email: str
    role: WorkspaceRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


class InvitationAcceptResponse(BaseModel):
    workspace_id: UUID
    role: WorkspaceRole
    workspace_name: str
