import uuid
from datetime import timedelta

from app.modules.auth.security import create_access_token, decode_access_token


async def _signup_and_token(client, email="me@example.com"):
    resp = await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "supersecret"}
    )
    return resp.json()["access_token"]


async def test_me_without_token_returns_401(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_me_with_malformed_header_returns_401(client):
    resp = await client.get("/api/v1/users/me", headers={"Authorization": "Token abc123"})
    assert resp.status_code == 401


async def test_me_with_invalid_token_returns_401(client):
    resp = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


async def test_me_returns_current_user(client):
    token = await _signup_and_token(client)
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me@example.com"
    assert body["id"]
    assert "password_hash" not in body


async def test_me_rejects_token_with_non_uuid_subject(client):
    token = create_access_token("not-a-uuid")
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_me_rejects_token_with_unknown_user(client):
    token = create_access_token(str(uuid.uuid4()))
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_me_rejects_expired_token(client):
    token = await _signup_and_token(client)
    subject = decode_access_token(token)
    expired = create_access_token(subject, expires_delta=timedelta(seconds=-1))
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
