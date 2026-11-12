import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.users.models import User


async def test_user_can_be_persisted_and_read(session_factory):
    async with session_factory() as session:
        user = User(email="a@example.com", password_hash="not-a-real-hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

    async with session_factory() as session:
        fetched = await session.get(User, user.id)

    assert fetched is not None
    assert fetched.email == "a@example.com"
    assert isinstance(fetched.id, uuid.UUID)
    assert fetched.created_at is not None


async def test_google_only_user_has_no_password(session_factory):
    async with session_factory() as session:
        user = User(email="google@example.com", google_sub="google-sub-1")
        session.add(user)
        await session.commit()

    async with session_factory() as session:
        fetched = await session.get(User, user.id)

    assert fetched is not None
    assert fetched.password_hash is None
    assert fetched.google_sub == "google-sub-1"


async def test_google_sub_is_unique(session_factory):
    async with session_factory() as session:
        session.add(User(email="one@example.com", google_sub="same-sub"))
        session.add(User(email="two@example.com", google_sub="same-sub"))
        with pytest.raises(IntegrityError):
            await session.commit()
