import time
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.modules.auth import google
from app.modules.auth.google import (
    GoogleEmailUnverifiedError,
    GoogleOAuthClient,
    GoogleOAuthError,
    GoogleProfile,
)

AUDIENCE = "test-client-id.apps.googleusercontent.com"
KID = "test-key"


@pytest.fixture(autouse=True)
def _clear_jwks_cache():
    # The JWKS cache is process-wide; every test starts from a cold cache.
    google._jwks_cache = None
    yield
    google._jwks_cache = None


@pytest.fixture(scope="module")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def jwks(private_key):
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    return {"keys": [dict(jwk, kid=KID, alg="RS256", use="sig")]}


def _claims(**overrides):
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": AUDIENCE,
        "sub": "google-sub-1",
        "email": "person@example.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return claims


class _Google:
    """A stand-in for Google's token and JWKS endpoints."""

    def __init__(self, private_key, jwks):
        self.private_key = private_key
        self.jwks_queue = [jwks]
        self.claims = _claims()
        self.token_status = 200
        self.include_id_token = True
        self.jwks_calls = 0
        self.token_requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) == google.TOKEN_URL:
            self.token_requests.append(request)
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_grant"})
            body = {"access_token": "access-token"}
            if self.include_id_token:
                body["id_token"] = jwt.encode(
                    self.claims,
                    self.private_key,
                    algorithm="RS256",
                    headers={"kid": KID},
                )
            return httpx.Response(200, json=body)

        if str(request.url) == google.JWKS_URL:
            self.jwks_calls += 1
            # Serve the next response once, then keep repeating the last one.
            current = self.jwks_queue.pop(0) if len(self.jwks_queue) > 1 else self.jwks_queue[0]
            return httpx.Response(200, json=current)

        raise AssertionError(f"unexpected request to {request.url}")

    def client(self) -> GoogleOAuthClient:
        transport = httpx.MockTransport(self.handler)
        return GoogleOAuthClient(
            client_id=AUDIENCE,
            client_secret="test-secret",
            client=httpx.AsyncClient(transport=transport),
        )


async def _exchange(server: _Google) -> GoogleProfile:
    return await server.client().exchange_code(
        code="the-code",
        code_verifier="the-verifier",
        redirect_uri="http://localhost:3000/api/auth/google/callback",
    )


async def test_exchange_returns_profile_from_signed_id_token(private_key, jwks):
    server = _Google(private_key, jwks)

    profile = await _exchange(server)

    assert profile == GoogleProfile(sub="google-sub-1", email="person@example.com")
    assert len(server.token_requests) == 1


async def test_exchange_posts_the_authorization_code_grant(private_key, jwks):
    server = _Google(private_key, jwks)

    await _exchange(server)

    form = parse_qs(server.token_requests[0].content.decode())
    assert form["grant_type"] == ["authorization_code"]
    assert form["code"] == ["the-code"]
    assert form["code_verifier"] == ["the-verifier"]
    assert form["client_id"] == [AUDIENCE]
    assert form["client_secret"] == ["test-secret"]
    assert form["redirect_uri"] == ["http://localhost:3000/api/auth/google/callback"]


async def test_token_endpoint_failure_is_refused(private_key, jwks):
    server = _Google(private_key, jwks)
    server.token_status = 400

    with pytest.raises(GoogleOAuthError):
        await _exchange(server)


async def test_response_without_id_token_is_refused(private_key, jwks):
    server = _Google(private_key, jwks)
    server.include_id_token = False

    with pytest.raises(GoogleOAuthError):
        await _exchange(server)


async def test_unverified_email_is_refused(private_key, jwks):
    server = _Google(private_key, jwks)
    server.claims = _claims(email_verified=False)

    with pytest.raises(GoogleEmailUnverifiedError):
        await _exchange(server)


async def test_missing_email_is_refused(private_key, jwks):
    server = _Google(private_key, jwks)
    server.claims = _claims(email=None)

    with pytest.raises(GoogleOAuthError):
        await _exchange(server)


async def test_wrong_audience_is_refused(private_key, jwks):
    server = _Google(private_key, jwks)
    server.claims = _claims(aud="someone-else.apps.googleusercontent.com")

    with pytest.raises(GoogleOAuthError):
        await _exchange(server)


async def test_wrong_issuer_is_refused(private_key, jwks):
    server = _Google(private_key, jwks)
    server.claims = _claims(iss="https://evil.example")

    with pytest.raises(GoogleOAuthError):
        await _exchange(server)


async def test_expired_token_is_refused(private_key, jwks):
    server = _Google(private_key, jwks)
    now = int(time.time())
    server.claims = _claims(iat=now - 600, exp=now - 300)

    with pytest.raises(GoogleOAuthError):
        await _exchange(server)


async def test_unknown_kid_refetches_jwks_once(private_key, jwks):
    server = _Google(private_key, jwks)
    server.jwks_queue = [{"keys": []}, jwks]

    profile = await _exchange(server)

    assert profile.email == "person@example.com"
    assert server.jwks_calls == 2


async def test_unknown_kid_twice_is_refused(private_key, jwks):
    server = _Google(private_key, jwks)
    server.jwks_queue = [{"keys": []}, {"keys": []}]

    with pytest.raises(GoogleOAuthError):
        await _exchange(server)

    assert server.jwks_calls == 2


async def test_jwks_is_cached_between_exchanges(private_key, jwks):
    server = _Google(private_key, jwks)

    await _exchange(server)
    await _exchange(server)

    assert server.jwks_calls == 1


async def test_malformed_jwks_body_is_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == google.JWKS_URL:
            return httpx.Response(200, text="<html>not json</html>")
        return httpx.Response(200, json={"id_token": "irrelevant"})

    client = GoogleOAuthClient(
        client_id=AUDIENCE,
        client_secret="test-secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(GoogleOAuthError):
        await client.exchange_code(code="c", code_verifier="v", redirect_uri="r")
