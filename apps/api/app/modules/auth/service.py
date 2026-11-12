from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.google import GoogleProfile
from app.modules.auth.security import hash_password, verify_password
from app.modules.users.models import User


class EmailAlreadyExistsError(Exception):
    """Raised when creating a user whose email is already taken."""


class GoogleAccountConflictError(Exception):
    """Raised when an email is already linked to a different Google account."""


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == _normalize_email(email)))
    return result.scalar_one_or_none()


async def get_user_by_google_sub(session: AsyncSession, google_sub: str) -> User | None:
    result = await session.execute(select(User).where(User.google_sub == google_sub))
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
    # A Google-only account has no password; never hand None to the verifier.
    if user.password_hash is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def authenticate_google(session: AsyncSession, profile: GoogleProfile) -> User:
    """Resolve a verified Google profile to exactly one user row."""
    email = _normalize_email(profile.email)
    try:
        return await _resolve_google_user(session, profile.sub, email)
    except IntegrityError:
        # Two first-time logins for the same person raced. The unique
        # constraints caught it; re-resolve against the row that won.
        await session.rollback()
        try:
            return await _resolve_google_user(session, profile.sub, email)
        except IntegrityError:
            await session.rollback()
            raise GoogleAccountConflictError from None


async def _resolve_google_user(session: AsyncSession, sub: str, email: str) -> User:
    user = await get_user_by_google_sub(session, sub)
    if user is not None:
        return user

    user = await get_user_by_email(session, email)
    if user is not None:
        if user.google_sub is not None:
            # Someone else's Google identity already owns this address.
            raise GoogleAccountConflictError
        user.google_sub = sub
        await session.commit()
        await session.refresh(user)
        return user

    user = User(email=email, password_hash=None, google_sub=sub)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
