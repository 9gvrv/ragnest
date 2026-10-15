async def test_signup_creates_user_and_returns_token(client):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": "a@example.com", "password": "supersecret"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "a@example.com"
    assert body["user"]["id"]
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


async def test_signup_duplicate_email_returns_409(client):
    payload = {"email": "dup@example.com", "password": "supersecret"}
    first = await client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409


async def test_signup_duplicate_email_is_case_insensitive(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "Case@Example.com", "password": "supersecret"},
    )
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": "CASE@EXAMPLE.COM", "password": "supersecret"},
    )
    assert resp.status_code == 409


async def test_signup_rejects_short_password(client):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": "b@example.com", "password": "short"},
    )
    assert resp.status_code == 422


async def test_signup_rejects_invalid_email(client):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": "not-an-email", "password": "supersecret"},
    )
    assert resp.status_code == 422
