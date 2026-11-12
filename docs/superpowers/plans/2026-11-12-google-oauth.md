# Google Sign-in Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a person sign up and sign in with Google from `/login` and `/signup`, landing in the same account model, JWT, and workspace rules as email/password.

**Architecture:** The web starts and finishes the browser dance (`state` + PKCE in a short-lived httpOnly cookie); the API holds the Google client secret, exchanges the code, verifies the ID token against Google's JWKS, upserts the user, and returns the usual access token. No token ever appears in a URL and the web never holds a secret.

**Tech Stack:** FastAPI, async SQLAlchemy (Postgres/Neon in prod, SQLite in tests), `httpx`, `PyJWT` (`RS256`), Alembic, pytest; Next.js 16 App Router route handlers, `cookies()`, `node:crypto`.

**Spec:** `docs/superpowers/specs/2026-11-12-google-oauth-design.md`

## Global Constraints

- The Google client secret lives **only** on the API. The web holds
  `GOOGLE_CLIENT_ID` and `GOOGLE_REDIRECT_URI`, nothing secret.
- No session token in a URL, query string, cookie readable by JS, or client
  component.
- Tests never touch Google. Fakes in `tests/conftest.py`, `MockTransport` for
  the client.
- All three Google settings default to `""`; unconfigured deployments keep
  working and the endpoint answers `503`.
- Migration `down_revision = "7c1e4a9b2d3f"`.
- `ruff` line length 100; `uv run ruff check app tests` and
  `uv run ruff format --check app tests` must pass.
- Never log or commit a secret, an ID token, or a code.
- Existing email/password behaviour must not change except: a passwordless
  account gets `401` instead of a crash.

## Review Focus

- Passwordless row: `POST /auth/login` → `401`, never a `TypeError`.
- Existing password account + Google on the same verified email → linked, and
  password login still works.
- A *different* Google `sub` on an already-linked email → `409`, nothing
  mutated.
- `email_verified: false` → `403`; missing `email`/`sub` → `400`.
- Wrong `state` / expired cookie → `/login?error=google_state`, no session.
- Wrong `redirect_uri` → `400`, no token exchange attempted.
- JWKS: unknown `kid` refetches once; bad signature / audience / issuer /
  expiry are all rejected.
- Google unconfigured → button hidden, start route redirects to
  `/login?error=google_unconfigured`, endpoint `503`.

---

## Task 1: API config and the `cryptography` dependency

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/.env.example`
- Modify: `apps/api/tests/core/test_config.py`

**Steps:**

- [ ] `uv add "pyjwt[crypto]"` from `apps/api`. This keeps one dependency line
      and adds `cryptography`, which `RS256` needs. Confirm `uv run python -c
      "import cryptography"` succeeds.
- [ ] Add to `Settings`, all defaulting to `""` so nothing breaks:

```python
GOOGLE_CLIENT_ID: str = ""
GOOGLE_CLIENT_SECRET: str = ""
GOOGLE_REDIRECT_URI: str = ""

@property
def google_oauth_enabled(self) -> bool:
    return bool(
        self.GOOGLE_CLIENT_ID.strip()
        and self.GOOGLE_CLIENT_SECRET.strip()
        and self.GOOGLE_REDIRECT_URI.strip()
    )
```

- [ ] Document the three vars in `.env.example` with a comment that the
      redirect URI is the **web** callback and must match Vercel's value.
- [ ] Test in `tests/core/test_config.py`: empty → disabled; all three set →
      enabled; whitespace-only → disabled.

**Verify:** `uv run pytest tests/core/test_config.py -q`

---

## Task 2: `users` schema — nullable password, `google_sub`

**Files:**
- Modify: `apps/api/app/modules/users/models.py`
- Create: `apps/api/alembic/versions/<rev>_add_google_sub_to_users.py`
- Modify: `apps/api/tests/modules/users/test_model.py`

**Steps:**

- [ ] Model:

```python
password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
```

- [ ] `uv run alembic revision -m "add google_sub to users"`, set
      `down_revision = "7c1e4a9b2d3f"`, and write:

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.create_unique_constraint(op.f("uq_users_google_sub"), "users", ["google_sub"])
    op.alter_column(
        "users", "password_hash", existing_type=sa.String(length=255), nullable=True
    )

def downgrade() -> None:
    # Fails if any Google-only account exists: there is no password to restore.
    op.alter_column(
        "users", "password_hash", existing_type=sa.String(length=255), nullable=False
    )
    op.drop_constraint(op.f("uq_users_google_sub"), "users", type_="unique")
    op.drop_column("users", "google_sub")
```

- [ ] Test: a `User` with `password_hash=None` and a `google_sub` persists; two
      users cannot share a `google_sub` (expect `IntegrityError`).

**Verify:** `uv run pytest tests/modules/users -q` (SQLite creates the schema
from the model, so this proves the model, not the migration; the migration is
checked by reading it and by the production run in Task 11).

---

## Task 3: The Google client

**Files:**
- Create: `apps/api/app/modules/auth/google.py`
- Modify: `apps/api/app/modules/auth/deps.py`
- Create: `apps/api/tests/modules/auth/test_google_client.py`

**Steps:**

- [ ] `google.py` holds the whole Google conversation. Shape:

```python
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

class GoogleOAuthError(Exception): ...
class GoogleEmailUnverifiedError(GoogleOAuthError): ...

@dataclass(frozen=True)
class GoogleProfile:
    sub: str
    email: str

class GoogleOAuthClient:
    def __init__(self, http: httpx.AsyncClient | None = None) -> None: ...
    async def exchange_code(self, *, code, code_verifier, redirect_uri) -> GoogleProfile: ...
```

- [ ] `exchange_code` POSTs the form body (`grant_type=authorization_code`,
      `code`, `code_verifier`, `redirect_uri`, `client_id`, `client_secret`),
      treats anything but `200` or a missing `id_token` as `GoogleOAuthError`,
      then verifies the token.
- [ ] Verification helper (module-level so it is unit-testable):

```python
def _verify_id_token(token: str, jwks: dict, audience: str) -> dict:
    header = jwt.get_unverified_header(token)
    key_data = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if key_data is None:
        raise KeyError(header.get("kid"))   # caller refetches once
    claims = jwt.decode(
        token,
        jwt.PyJWK(key_data).key,
        algorithms=["RS256"],
        audience=audience,
        options={"require": ["exp", "iat", "aud", "iss"]},
    )
    if claims.get("iss") not in ISSUERS:
        raise GoogleOAuthError("unexpected issuer")
    return claims
```

- [ ] JWKS cache: module-level `(fetched_at, jwks)` with a 3600 s TTL. On a
      missing `kid`, refetch once and retry; a second miss is an error. Cache
      only successful fetches.
- [ ] Claim handling: `sub` and `email` must be non-empty strings; `email_verified`
      must be true (`True` or `"true"`); otherwise
      `GoogleEmailUnverifiedError`.
- [ ] `deps.py`: `def get_google_client() -> GoogleOAuthClient: return GoogleOAuthClient()`.
- [ ] Tests with `httpx.MockTransport`:
      - success: token endpoint returns a JWT signed with a locally generated
        RSA key (`jwt.algorithms.RSAAlgorithm.generate_key()`), JWKS returns
        that key via `RSAAlgorithm.to_jwk(public_key, as_dict=True)` with
        `kid="k1"`.
      - token endpoint `400` → `GoogleOAuthError`.
      - response without `id_token` → `GoogleOAuthError`.
      - `email_verified: false` → `GoogleEmailUnverifiedError`.
      - missing `email` → `GoogleOAuthError`.
      - wrong `aud` → error; wrong `iss` → error; expired → error.
      - unknown `kid` → exactly one JWKS refetch, then success (count calls);
        unknown twice → error.

**Verify:** `uv run pytest tests/modules/auth/test_google_client.py -q`

---

## Task 4: Upsert and the passwordless login guard

**Files:**
- Modify: `apps/api/app/modules/auth/service.py`
- Create: `apps/api/tests/modules/auth/test_google.py`
- Modify: `apps/api/tests/modules/auth/test_login.py`

**Steps:**

- [ ] `authenticate_user`: `if user is None or user.password_hash is None: return None`
      before calling `verify_password`. Add a test that a Google-only row gets
      `401` from `POST /api/v1/auth/login`.
- [ ] `get_user_by_google_sub(session, sub)` mirroring `get_user_by_email`.
- [ ] `class GoogleAccountConflictError(Exception)`.
- [ ] `authenticate_google(session, profile)` implements §7 exactly:

```
by sub          -> return
by email, no sub-> attach sub, commit, return
by email, other -> raise GoogleAccountConflictError
otherwise       -> create with password_hash=None, google_sub=sub
```

      Wrap the create/link commit in `try/except IntegrityError` → rollback and
      re-resolve by `sub`, then by email; if still unresolved, raise
      `GoogleAccountConflictError`. (Two concurrent first logins must not 500.)

- [ ] Service tests in `test_google.py` cover all four branches plus the
      IntegrityError retry.

**Verify:** `uv run pytest tests/modules/auth -q`

---

## Task 5: The endpoint and the test fakes

**Files:**
- Modify: `apps/api/app/modules/auth/schemas.py`
- Modify: `apps/api/app/modules/auth/router.py`
- Modify: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/modules/auth/conftest.py`
- Create: `apps/api/tests/modules/auth/test_google_router.py`

**Steps:**

- [ ] `GoogleExchangeRequest(BaseModel)`: `code: str`, `code_verifier: str`,
      `redirect_uri: str`.
- [ ] Router:

```python
@router.post("/google", response_model=TokenResponse)
async def google_login(payload, session, google=Depends(get_google_client)):
    # 503 unconfigured; 400 redirect_uri mismatch; exchange; 403/409/400 mapping
```

      Status map: `GoogleEmailUnverifiedError` → `403`, exchange/verification
      failure → `400 "Google sign-in failed."`,
      `GoogleAccountConflictError` → `409 "That email is already linked to a
      different sign-in method."`
- [ ] `tests/conftest.py`: add `os.environ.setdefault` for the three Google
      vars (so `google_oauth_enabled` is true), a `FakeGoogleClient` with a
      `profile` and an optional `error`, and override `get_google_client` in the
      `app` fixture exactly like `get_llm_provider`.
- [ ] Router tests: success creates a row with `password_hash IS NULL`; second
      call reuses the id; `email_verified` refusal; `409`; `400`; `503` via
      `monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")`; returned token
      works on `GET /api/v1/users/me`.

**Verify:** `uv run pytest tests/modules/auth -q && uv run ruff check app tests && uv run ty check app`

---

## Task 6: Web helpers

**Files:**
- Create: `apps/web/lib/google-oauth.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/.env.example`

**Steps:**

- [ ] `lib/google-oauth.ts`:
      - `GOOGLE_COOKIE = "ragnest_google"`, `AUTHORIZE_URL`.
      - `googleOAuthConfigured()` → both `GOOGLE_CLIENT_ID` and
        `GOOGLE_REDIRECT_URI` are non-empty.
      - `randomToken(bytes)` and `codeChallengeFor(verifier)` using
        `node:crypto` (`randomBytes`, `createHash`), base64url without padding.
      - `setGoogleCookie(payload)` / `readGoogleCookie()` / `clearGoogleCookie()`
        via `cookies()`; `httpOnly`, `sameSite: "lax"`, `secure` in production,
        `path: "/api/auth/google"`, `maxAge: 600`.
      - `buildAuthorizeUrl({ state, codeChallenge })` with the parameters in the
        spec (§8.1).
- [ ] `lib/api.ts`: `exchangeGoogleCode(code, codeVerifier, redirectUri)` →
      `POST /api/v1/auth/google`, returning `{ access_token, token_type }`.
- [ ] `apps/web/.env.example`: document `GOOGLE_CLIENT_ID` and
      `GOOGLE_REDIRECT_URI` as server-only.

**Verify:** `pnpm exec tsc --noEmit` (after `pnpm exec next typegen`).

---

## Task 7: Start route

**Files:**
- Create: `apps/web/app/api/auth/google/start/route.ts`

**Steps:**

- [ ] `GET`: unconfigured → `NextResponse.redirect(new URL("/login?error=google_unconfigured", request.url))`.
- [ ] `next = safeNextPath(searchParams.get("next")) ?? "/workspaces"`.
- [ ] Generate state + verifier, set the cookie, redirect to the authorize URL
      (302).
- [ ] Confirm the `Set-Cookie` header is actually on the 302 (see Task 11); if
      `cookies()` does not apply to a returned `NextResponse.redirect`, set the
      cookie on the response object instead and note it in
      `apps/web/AGENTS.md`.

---

## Task 8: Callback route

**Files:**
- Create: `apps/web/app/api/auth/google/callback/route.ts`

**Steps:**

- [ ] `GET`: read + clear the cookie first. Missing cookie / missing `code` /
      `state` mismatch → `/login?error=google_state`.
- [ ] `searchParams.get("error") === "access_denied"` → `/login?error=google_denied`.
- [ ] `exchangeGoogleCode(...)`; on success `setSessionToken` and redirect to
      `safeNextPath(stored.next) ?? "/workspaces"`.
- [ ] `ApiError.status === 403` → `google_unverified`; `409` → `google_conflict`;
      everything else (including unreachable API) → `google_failed`.

---

## Task 9: The button and the alert

**Files:**
- Create: `apps/web/components/google-sign-in.tsx`
- Create: `apps/web/components/auth-alert.tsx` (tiny, server-safe)
- Modify: `apps/web/app/login/page.tsx`
- Modify: `apps/web/app/signup/page.tsx`

**Steps:**

- [ ] `GoogleSignIn` (no `"use client"`): returns `null` when
      `googleOAuthConfigured()` is false. Otherwise an `<a>` to
      `/api/auth/google/start?next=<encoded>`, styled as an `h-10` bordered
      surface control with an inline 16 px Google mark, followed by an `or`
      rule. No new dependency, no image file.
- [ ] `AuthAlert({ code })`: maps the error codes in spec §11 to one sentence and
      renders `role="alert"` + `text-sm text-danger`; renders nothing when there
      is no code.
- [ ] Both pages: read `params.error`, render `AuthAlert` above the form, and
      `GoogleSignIn` above that.
- [ ] Keep `AuthForm` untouched.

---

## Task 10: Docs

**Files:**
- Modify: `docs/deployment.md`
- Modify: `apps/api/AGENTS.md`
- Modify: `apps/web/AGENTS.md`
- Modify: `docs/progress.md`

**Steps:**

- [ ] `deployment.md` §3: add the three API vars and the two web vars, with the
      "must match, must be registered in Google Cloud" note; add the console
      steps from spec §13 and the "redeploy after env changes" reminder.
- [ ] `apps/api/AGENTS.md`: §6 config list, §7 migration note, §13 roadmap item
      (Milestone 7), and the account-linking decision + residual risk.
- [ ] `apps/web/AGENTS.md`: route table rows for the two `auth/google` handlers,
      a pattern note (state+PKCE cookie, no token in URLs), roadmap item.
- [ ] `docs/progress.md`: a dated entry at the end.

---

## Task 11: Verification

- [ ] API: `uv run pytest`, `uv run ruff check app tests`,
      `uv run ruff format --check app tests`, `uv run ty check app`.
- [ ] Web: `pnpm lint && pnpm exec next typegen && pnpm exec tsc --noEmit && pnpm build`.
- [ ] Start route (web dev running with fake-but-well-formed env values):

```bash
curl -sSI 'http://localhost:3000/api/auth/google/start?next=/workspaces' | grep -i -E 'HTTP/|location:|set-cookie:'
```

      Expect `302`, a `location:` on `accounts.google.com` carrying
      `client_id`, `redirect_uri`, `scope=openid email`, `state`,
      `code_challenge_method=S256`, and a `ragnest_google` `Set-Cookie` with
      `HttpOnly` and `Path=/api/auth/google`.
- [ ] Callback with no cookie:

```bash
curl -sSI 'http://localhost:3000/api/auth/google/callback?code=x&state=y' | grep -i -E 'HTTP/|location:'
```

      Expect `307/302` to `/login?error=google_state`.
- [ ] Manual round trip with real credentials (human, spec §13): sign in with
      Google as a new address → account created, `/workspaces` loads; sign out,
      sign in again → same account; sign in with Google using the email of an
      existing password account → same account, and password login still works;
      cancel on the consent screen → `/login?error=google_denied`.
- [ ] Migration: `uv run alembic upgrade head` against a scratch branch (never
      the production branch without the runbook), then `uv run alembic current`.
