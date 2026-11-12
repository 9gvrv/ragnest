import uuid

from sqlalchemy import select

from app.core.config import settings
from app.modules.auth.google import GoogleEmailUnverifiedError, GoogleOAuthError
from app.modules.users.models import User

REDIRECT_URI = "http://localhost:3000/api/auth/google/callback"


def _payload(**overrides):
    body = {
        "code": "the-code",
        "code_verifier": "v" * 64,
        "redirect_uri": REDIRECT_URI,
    }
    body.update(overrides)
    return body


async def _post(client, **overrides):
    return await client.post("/api/v1/auth/google", json=_payload(**overrides))


async def test_google_signin_returns_a_working_token(client, fake_google):
    resp = await _post(client)

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"

    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "person@example.com"


async def test_google_signin_passes_the_code_to_the_client(client, fake_google):
    await _post(client)

    assert fake_google.calls == [
        {"code": "the-code", "code_verifier": "v" * 64, "redirect_uri": REDIRECT_URI}
    ]


async def test_google_signin_twice_creates_one_user(client, fake_google, session_factory):
    await _post(client)
    await _post(client)

    async with session_factory() as session:
        users = list((await session.execute(select(User))).scalars())

    assert len(users) == 1
    assert users[0].password_hash is None


async def test_google_signin_refuses_a_different_redirect_uri(client, fake_google):
    resp = await _post(client, redirect_uri="https://evil.example/callback")

    assert resp.status_code == 400
    assert fake_google.calls == []


async def test_google_signin_maps_an_unverified_email_to_403(client, fake_google):
    fake_google.error = GoogleEmailUnverifiedError("not verified")

    resp = await _post(client)

    assert resp.status_code == 403


async def test_google_signin_maps_an_exchange_failure_to_400(client, fake_google):
    fake_google.error = GoogleOAuthError("bad code")

    resp = await _post(client)

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Google sign-in failed."


async def test_google_signin_maps_a_conflict_to_409(client, fake_google, session_factory):
    async with session_factory() as session:
        session.add(
            User(
                email="person@example.com",
                password_hash="not-used",
                google_sub="someone-elses-sub",
            )
        )
        await session.commit()

    resp = await _post(client)

    assert resp.status_code == 409


async def test_google_signin_is_503_when_unconfigured(client, fake_google, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")

    resp = await _post(client)

    assert resp.status_code == 503
    assert fake_google.calls == []


async def test_google_signin_rejects_a_malformed_body(client, fake_google):
    resp = await client.post("/api/v1/auth/google", json={"code": "only-a-code"})

    assert resp.status_code == 422
    assert fake_google.calls == []


async def test_google_signin_issues_a_token_for_the_linked_user(
    client, fake_google, session_factory
):
    existing_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(User(id=existing_id, email="person@example.com", password_hash="not-used"))
        await session.commit()

    resp = await _post(client)

    assert resp.status_code == 200
    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {resp.json()['access_token']}"},
    )
    assert me.json()["id"] == str(existing_id)
