import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
JWKS_TTL_SECONDS = 3600
REQUEST_TIMEOUT_SECONDS = 10

# Google rotates signing keys rarely, so one fetch per process per hour is
# plenty. A token whose `kid` is unknown forces a single refetch.
_jwks_cache: tuple[float, dict[str, Any]] | None = None


class GoogleOAuthError(Exception):
    """Raised when Google's token or identity cannot be trusted."""


class GoogleEmailUnverifiedError(GoogleOAuthError):
    """Raised when Google has not verified the account's email address."""


@dataclass(frozen=True)
class GoogleProfile:
    sub: str
    email: str


class GoogleOAuthClient:
    """Exchanges an authorization code and returns the verified profile.

    A client may be injected for tests; otherwise each call owns and closes its
    own client, mirroring the Gemini provider.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = client

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> GoogleProfile:
        client, owns_client = self._acquire_client()
        try:
            claims = await self._exchange(
                client,
                code=code,
                code_verifier=code_verifier,
                redirect_uri=redirect_uri,
            )
        finally:
            if owns_client:
                await client.aclose()
        return _profile_from_claims(claims)

    def _acquire_client(self) -> tuple[httpx.AsyncClient, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS), True

    async def _exchange(
        self,
        client: httpx.AsyncClient,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
        except httpx.HTTPError as exc:
            raise GoogleOAuthError("Could not reach Google") from exc

        if response.status_code != 200:
            raise GoogleOAuthError(f"Google rejected the code ({response.status_code})")

        try:
            payload = response.json()
        except ValueError as exc:
            raise GoogleOAuthError("Google returned a non-JSON response") from exc

        id_token = payload.get("id_token") if isinstance(payload, dict) else None
        if not isinstance(id_token, str) or not id_token:
            raise GoogleOAuthError("Google did not return an ID token")

        jwks = await _fetch_jwks(client)
        try:
            return _verify_id_token(id_token, jwks, self._client_id)
        except KeyError:
            # The signing key rotated since we cached the set: refetch once.
            jwks = await _fetch_jwks(client, force=True)
            try:
                return _verify_id_token(id_token, jwks, self._client_id)
            except KeyError as exc:
                raise GoogleOAuthError("ID token signed by an unknown key") from exc


def _verify_id_token(token: str, jwks: dict[str, Any], audience: str) -> dict[str, Any]:
    """Verify signature, audience, expiry, and issuer. Raises on any doubt."""
    try:
        header = jwt.get_unverified_header(token)
        key_data = next(
            (key for key in jwks.get("keys", []) if key.get("kid") == header.get("kid")),
            None,
        )
        if key_data is None:
            raise KeyError(header.get("kid"))
        claims = jwt.decode(
            token,
            jwt.PyJWK(key_data).key,
            algorithms=["RS256"],
            audience=audience,
            options={"require": ["exp", "iat", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise GoogleOAuthError("Invalid ID token") from exc

    if claims.get("iss") not in ISSUERS:
        raise GoogleOAuthError("Unexpected ID token issuer")
    return claims


async def _fetch_jwks(client: httpx.AsyncClient, *, force: bool = False) -> dict[str, Any]:
    global _jwks_cache

    if not force:
        cached = _cached_jwks()
        if cached is not None:
            return cached

    try:
        response = await client.get(JWKS_URL)
    except httpx.HTTPError as exc:
        raise GoogleOAuthError("Could not fetch Google signing keys") from exc

    if response.status_code != 200:
        raise GoogleOAuthError("Could not fetch Google signing keys")

    try:
        payload = response.json()
    except ValueError as exc:
        raise GoogleOAuthError("Malformed Google signing keys") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        raise GoogleOAuthError("Malformed Google signing keys")

    _jwks_cache = (time.monotonic(), payload)
    return payload


def _cached_jwks() -> dict[str, Any] | None:
    if _jwks_cache is None:
        return None
    fetched_at, jwks = _jwks_cache
    if time.monotonic() - fetched_at >= JWKS_TTL_SECONDS:
        return None
    return jwks


def _profile_from_claims(claims: dict[str, Any]) -> GoogleProfile:
    sub = claims.get("sub")
    email = claims.get("email")
    verified = claims.get("email_verified")

    if not isinstance(sub, str) or not sub:
        raise GoogleOAuthError("ID token has no subject")
    if not isinstance(email, str) or not email:
        raise GoogleOAuthError("ID token has no email")
    if verified is not True and verified != "true":
        raise GoogleEmailUnverifiedError("Google has not verified that email address")

    return GoogleProfile(sub=sub, email=email)
