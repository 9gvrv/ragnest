from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.security import hash_password, verify_password
from app.modules.users.models import User


class EmailAlreadyExistsError(Exception):
    """Raised when creating a user whose email is already taken."""


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == _normalize_email(email)))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, email: str, password: str) -> User:
    user = User(email=_normalize_email(email), password_hash=hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise EmailAlreadyExistsError from exc
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
