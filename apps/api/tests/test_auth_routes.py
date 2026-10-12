import uuid

import jwt
from sqlalchemy import select

from src.core.security import decode_access_token
from src.models import Organization, User

SIGNUP = {"email": "ada@example.com", "password": "hunter2secure"}


async def test_signup_creates_user_without_org(client, session):
    res = await client.post("/auth/signup", json=SIGNUP)

    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "ada@example.com"
    assert data["is_active"] is True
    assert data["org_id"] is None
    assert data["role"] is None

    user = await session.get(User, uuid.UUID(data["id"]))
    assert user is not None
    assert user.password_hash != "hunter2secure"


async def test_signup_with_org_makes_user_owner(client, session):
    res = await client.post(
        "/auth/signup",
        json={**SIGNUP, "organization_name": "Acme"},
    )

    assert res.status_code == 201
    data = res.json()
    assert data["org_id"] is not None
    assert data["role"] == "owner"

    org = await session.get(Organization, uuid.UUID(data["org_id"]))
    assert org is not None
    assert org.name == "Acme"

    user = await session.get(User, uuid.UUID(data["id"]))
    assert user.role == "owner"


async def test_signup_rejects_duplicate_email(client, session):
    await client.post("/auth/signup", json=SIGNUP)

    res = await client.post("/auth/signup", json=SIGNUP)

    assert res.status_code == 409


async def test_signup_validates_email_and_password(client, session):
    res = await client.post(
        "/auth/signup", json={"email": "not-an-email", "password": "hunter2secure"}
    )
    assert res.status_code == 422

    res = await client.post(
        "/auth/signup", json={"email": "ada@example.com", "password": "short"}
    )
    assert res.status_code == 422


async def test_login_returns_access_token(client, session):
    await client.post("/auth/signup", json=SIGNUP)

    res = await client.post(
        "/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}
    )

    assert res.status_code == 200
    data = res.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]

    user = await session.scalar(select(User).where(User.email == SIGNUP["email"]))
    payload = decode_access_token(data["access_token"])
    assert payload["sub"] == str(user.id)


async def test_login_rejects_wrong_password(client, session):
    await client.post("/auth/signup", json=SIGNUP)

    res = await client.post(
        "/auth/login", json={"email": SIGNUP["email"], "password": "wrong-password"}
    )

    assert res.status_code == 401


async def test_login_rejects_unknown_email(client, session):
    res = await client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": "hunter2secure"}
    )

    assert res.status_code == 401


async def test_me_requires_token(client, session):
    res = await client.get("/auth/me")

    assert res.status_code == 401


async def test_me_returns_current_user(client, session):
    await client.post("/auth/signup", json=SIGNUP)
    login = await client.post(
        "/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}
    )
    token = login.json()["access_token"]

    res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.json()["email"] == SIGNUP["email"]


async def test_me_rejects_invalid_token(client, session):
    res = await client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert res.status_code == 401


async def test_me_rejects_token_for_missing_user(client, session):
    token = jwt.encode(
        {"sub": str(uuid.uuid4())},
        "a-dummy-secret-key-that-is-longer-than-32-bytes",
        algorithm="HS256",
    )

    res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 401


async def test_logout_returns_204_for_authenticated_user(client, session):
    await client.post("/auth/signup", json=SIGNUP)
    login = await client.post(
        "/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}
    )
    token = login.json()["access_token"]

    res = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 204


async def test_logout_requires_authentication(client, session):
    res = await client.post("/auth/logout")

    assert res.status_code == 401
