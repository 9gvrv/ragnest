import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.modules.workspaces.models import WorkspaceRole


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class Invitation(Base, TimestampMixin):
    __tablename__ = "invitations"
    __table_args__ = (Index("ix_invitations_email", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    inviter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255))
    role: Mapped[WorkspaceRole] = mapped_column(
        SAEnum(WorkspaceRole, values_callable=lambda e: [x.value for x in e])
    )
    token: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[InvitationStatus] = mapped_column(
        SAEnum(InvitationStatus, values_callable=lambda e: [x.value for x in e])
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
