import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    # NULL for accounts that only ever sign in with Google.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Google's stable subject id; NULL until that person uses Google sign-in.
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
