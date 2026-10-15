import uuid

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
