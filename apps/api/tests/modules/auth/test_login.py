async def _signup(client, email="user@example.com", password="supersecret"):
    return await client.post("/api/v1/auth/signup", json={"email": email, "password": password})


async def test_login_returns_token(client):
    await _signup(client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "supersecret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_is_case_insensitive_on_email(client):
    await _signup(client, email="Mixed@Example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "mixed@example.com", "password": "supersecret"},
    )
    assert resp.status_code == 200


async def test_login_wrong_password_returns_401(client):
    await _signup(client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "supersecret"},
    )
    assert resp.status_code == 401


async def test_login_failures_do_not_reveal_whether_email_exists(client):
    await _signup(client)
    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "wrongpassword"},
    )
    unknown_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "supersecret"},
    )
    assert wrong_password.json() == unknown_email.json()
