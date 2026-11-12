import pytest
from sqlalchemy import select

from app.modules.auth import service
from app.modules.auth.google import GoogleProfile
from app.modules.users.models import User

PROFILE = GoogleProfile(sub="google-sub-1", email="person@example.com")


async def _users(session_factory) -> list[User]:
    async with session_factory() as session:
        return list((await session.execute(select(User))).scalars())


async def test_google_signup_creates_a_passwordless_user(session_factory):
    async with session_factory() as session:
        user = await service.authenticate_google(session, PROFILE)

    assert user.email == "person@example.com"
    assert user.google_sub == "google-sub-1"
    assert user.password_hash is None


async def test_google_signup_normalizes_the_email(session_factory):
    profile = GoogleProfile(sub="google-sub-1", email="Person@Example.COM")

    async with session_factory() as session:
        user = await service.authenticate_google(session, profile)

    assert user.email == "person@example.com"


async def test_second_google_signin_reuses_the_row_by_sub(session_factory):
    async with session_factory() as session:
        first = await service.authenticate_google(session, PROFILE)

    # Google can change the address; the subject is what identifies the person.
    renamed = GoogleProfile(sub="google-sub-1", email="renamed@example.com")
    async with session_factory() as session:
        second = await service.authenticate_google(session, renamed)

    assert second.id == first.id
    assert len(await _users(session_factory)) == 1


async def test_existing_password_account_is_linked(session_factory):
    async with session_factory() as session:
        password_user = await service.create_user(session, "person@example.com", "supersecret")

    async with session_factory() as session:
        linked = await service.authenticate_google(session, PROFILE)

    assert linked.id == password_user.id
    assert linked.google_sub == "google-sub-1"
    assert linked.password_hash is not None

    # Password login keeps working after the link.
    async with session_factory() as session:
        assert await service.authenticate_user(session, "person@example.com", "supersecret")


async def test_a_different_google_identity_on_a_linked_email_is_refused(session_factory):
    async with session_factory() as session:
        await service.authenticate_google(session, PROFILE)

    other_identity = GoogleProfile(sub="google-sub-2", email="person@example.com")
    async with session_factory() as session:
        with pytest.raises(service.GoogleAccountConflictError):
            await service.authenticate_google(session, other_identity)

    users = await _users(session_factory)
    assert len(users) == 1
    assert users[0].google_sub == "google-sub-1"


async def test_concurrent_first_login_recovers_from_the_unique_constraint(
    session_factory, monkeypatch
):
    async with session_factory() as session:
        first = await service.authenticate_google(session, PROFILE)

    # Simulate the race: this request's lookups see nothing, but the row exists.
    calls = {"sub": 0, "email": 0}
    real_by_sub = service.get_user_by_google_sub
    real_by_email = service.get_user_by_email

    async def stale_by_sub(session, sub):
        calls["sub"] += 1
        return None if calls["sub"] == 1 else await real_by_sub(session, sub)

    async def stale_by_email(session, email):
        calls["email"] += 1
        return None if calls["email"] == 1 else await real_by_email(session, email)

    monkeypatch.setattr(service, "get_user_by_google_sub", stale_by_sub)
    monkeypatch.setattr(service, "get_user_by_email", stale_by_email)

    async with session_factory() as session:
        second = await service.authenticate_google(session, PROFILE)

    assert second.id == first.id
    assert len(await _users(session_factory)) == 1
