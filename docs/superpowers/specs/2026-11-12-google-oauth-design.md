# Ragnest — Milestone 7: Google Sign-in — Design

**Date:** 2026-11-12
**Status:** proposed
**Scope:** `apps/api/` + `apps/web/` + `docs/deployment.md`

---

## 1. Intent

Today an account is an email plus a password. Many people would rather not
invent one more password, and a "Continue with Google" button on `/login` and
`/signup` is the shortest path from "I want to try this" to a workspace.

The result must be the **same account model** we already have: one `users` row,
one JWT, the same 30-minute `ragnest_session` cookie, the same workspace
membership rules. Google is only a second way to prove who you are. Nothing
downstream — workspaces, documents, retrieval, chat — changes at all.

---

## 2. Goals

1. A person can sign up and sign in with Google from `/login` and `/signup`.
2. An existing email/password account can also use Google, and keeps its
   workspaces, documents, and conversations.
3. The browser never sees the Google client secret, and no session token ever
   appears in a URL, history entry, or referrer.
4. The flow works in local dev (`localhost:3000` → `127.0.0.1:8000`) and in
   production (Vercel → Render) with only environment variables differing.
5. The API tests never touch Google. The whole flow is exercised against a fake
   provider, like `fake_llm` and `fake_embeddings` today.
6. Deployments that have not configured Google keep working: the button is
   hidden, the endpoint answers `503`, email/password is untouched.

## 3. Non-goals

- Any provider other than Google. The design leaves room for one, but nothing
  is generalised now.
- Email verification at signup (see §7 for why this matters).
- Refresh tokens, offline access, or reading Google Drive.
- Profile data: no name, no avatar, no Google ID shown anywhere. We store the
  stable subject id and the email, nothing else.
- "Link/unlink Google" from `/account`, and showing which providers an account
  has. Deferred; the data model already supports it.
- Account deletion, session revocation, or a logout-everywhere button.

## 4. Anti-goals

- A JWT in a redirect URL (`?token=…`), in `localStorage`, or in client JS.
- The Google client secret reaching the browser or the web server.
- Trusting an email from a request body instead of a verified ID token.
- Creating a second account for someone who already has one under that email.
- A CSRF hole: an attacker's `code` being swapped into a victim's callback.
- Breaking password login for existing accounts.

---

## 5. Constraints

- **The web app holds no secrets today.** `apps/web` reads only `API_URL`; it
  forwards the session cookie and renders. This milestone keeps that true.
- **The API is the only token issuer.** The web must not be able to mint a
  session for an arbitrary user id.
- **No new UI dependencies.** The Google mark is inline SVG.
- **Existing patterns are law:** `app/modules/<feature>/`, provider protocol +
  FastAPI dependency + fake in `tests/conftest.py`, `httpx` with
  `MockTransport` for client tests, SQLite in tests, `camel`-free env names.
- **`users.email` stays unique and lowercase-normalised.**

---

## 6. Decisions at a glance

| Decision | Choice | Why |
| --- | --- | --- |
| Who runs the OAuth dance | Web starts and ends it; **API performs the code exchange** | Keeps the client secret on the API; keeps the session token out of URLs |
| CSRF protection | `state` in a short-lived httpOnly cookie | No server-side session store, no extra table, works on one Render instance |
| Code interception | PKCE `S256` | Google recommends it; the verifier rides in the same cookie |
| Session handoff | Web calls `POST /api/v1/auth/google`, gets a JWT, sets its own cookie | Identical to the existing login route handler |
| Identity key | Google `sub`, plus verified `email` | `sub` is stable if the email changes |
| Account linking | Match `google_sub`, then verified `email`, else create | One account per person; no dead end |
| Conflicting `google_sub` | `409`, no silent relink | Two identities claiming one email is a real conflict |
| Password storage | `password_hash` becomes nullable | A Google-only account has no password |
| Provider config | Three API env vars, default `""` | Unconfigured deployments must not break |
| ID token verification | Google's JWKS over `httpx` + `PyJWT` (`RS256`) | Same shape as the Gemini/Groq clients; no SDK, no `requests` |
| Post-login default | `/workspaces` | `/` is the marketing page; `AuthForm` already defaults here |

---

## 7. Account linking (the one sharp edge)

Order of lookup in `authenticate_google`:

1. **By `google_sub`.** The same Google account always lands in the same row,
   even if its email changed.
2. **By normalised email, when that row has no `google_sub`.** The account
   exists but has never used Google, so we attach `google_sub` to it. Password
   login keeps working afterwards.
3. **By normalised email, when that row has a *different* `google_sub`.** This
   means two Google identities now claim one email — possible when a Google
   account's address changed. We refuse with `409` and change nothing: silently
   overwriting the stored `sub` would move a stranger into someone's account,
   and creating a row would violate the unique email. The message is generic
   ("That email is already linked to a different sign-in method.") and the
   web maps it to `google_conflict`.
4. **Create** a new row with `password_hash = NULL`.

Google only returns an email it considers verified; we additionally require the
`email_verified` claim to be true and refuse otherwise (`403`). That is the
normal industry behaviour and it is what makes step 2 safe enough.

**Residual risk, stated plainly:** signup does not verify email ownership. An
attacker could register `victim@gmail.com` with a password before the victim
arrives; when the victim later clicks "Continue with Google", they are linked
into that attacker-controlled account. This is the known *account pre-hijacking*
pattern. The real fix is email verification at signup (or refusing to link when
`password_hash` is set), both of which are out of scope here. We accept the risk
and record it rather than hide it.

Google-only accounts can never log in with a password: `authenticate_user`
returns `None` when `password_hash IS NULL` instead of calling the verifier with
`None`.

---

## 8. The flow, step by step

```
Browser                 Web (Vercel)                     API (Render)          Google
   |  click "Continue      |                                 |                    |
   |  with Google"         |                                 |                    |
   |---------------------->| GET /api/auth/google/start      |                    |
   |                       |  state, verifier, next, origin  |                    |
   |                       |  -> httpOnly cookie (10 min)    |                    |
   |<----------------------| 302 to accounts.google.com      |                    |
   |------------------------------------------------------------------------------>|
   |                       |                                 |                    |
   |<------------------------------------------------------------------------------|
   |  GET /api/auth/google/callback?code&state                 |                    |
   |---------------------->| cookie.state == query.state ?   |                    |
   |                       |------------------------------- >| POST /api/v1/auth/google
   |                       |                                 |  code, verifier,   |
   |                       |                                 |  redirect_uri      |
   |                       |                                 |-------> token exchange
   |                       |                                 |<------- id_token   |
   |                       |                                 | verify (JWKS, aud) |
   |                       |                                 | upsert user        |
   |                       |<------------------------------- | {access_token}     |
   |                       | set ragnext_session, clear oauth cookie              |
   |<----------------------| 302 to next (or /login?error=…) |                    |
```

### 8.1 Web: start (`GET /api/auth/google/start`)

- `next` is filtered through `safeNextPath()` before it is stored, and defaults
  to `/workspaces` — the place a signed-in person wants to be. (The existing
  login route handler defaults to `/`; that is left alone.)
- Generates `state` and `code_verifier` with `crypto.randomBytes`, and
  `code_challenge = base64url(sha256(verifier))`.
- Stores `{state, verifier, next}` in the `ragnest_google` cookie:
  `httpOnly`, `sameSite=lax`, `secure` in production, `path=/api/auth/google`,
  `maxAge=600`. `lax` is required: Google's callback is a cross-site top-level
  GET, and `strict` would drop the cookie.
- Redirects to
  `https://accounts.google.com/o/oauth2/v2/auth` with
  `client_id`, `redirect_uri`, `response_type=code`, `scope=openid email`,
  `state`, `code_challenge`, `code_challenge_method=S256`,
  `access_type=online`, `prompt=select_account`.
- If `GOOGLE_CLIENT_ID`/`GOOGLE_REDIRECT_URI` are unset, redirects to
  `/login?error=google_unconfigured` instead. The button is hidden in that case,
  so this is a belt-and-braces path.

### 8.2 Web: callback (`GET /api/auth/google/callback`)

- Reads and immediately clears the cookie.
- Rejects a missing cookie, a missing `code`, or a `state` mismatch with
  `/login?error=google_state`.
- Calls `exchangeGoogleCode(code, verifier, GOOGLE_REDIRECT_URI)`.
- On success: `setSessionToken()`, redirect to the stored `next` (re-validated
  with `safeNextPath`, falling back to `/workspaces`).
- On failure the person always lands on `/login?error=…`: `google_unverified`
  for a 403, `google_conflict` for a 409, `google_denied` when Google returned
  `error=access_denied`, `google_failed` otherwise. Always `/login` — no
  page-of-origin is stored, so no query value ever chooses a redirect target
  and there is no open-redirect surface. `/login` already links to `/signup`.
- `/login` and `/signup` both render the alert, so whichever page the person
  returns to is consistent.

### 8.3 API: `POST /api/v1/auth/google`

Request `{code, code_verifier, redirect_uri}` → `200 {access_token, token_type}`.

- `503` when `google_oauth_enabled` is false.
- `400` when `redirect_uri` is not exactly `settings.GOOGLE_REDIRECT_URI` — the
  API refuses to exchange a code issued for another callback.
- Posts to `https://oauth2.googleapis.com/token` with the client id, secret,
  code, verifier, redirect URI, and `grant_type=authorization_code` over
  `httpx`.
- Verifies `id_token` locally: fetch Google's JWKS
  (`https://www.googleapis.com/oauth2/v3/certs`) with `httpx`, pick the key by
  the token header's `kid`, and `jwt.decode` it with `PyJWT` (`RS256`,
  `audience=GOOGLE_CLIENT_ID`), then check the issuer is `accounts.google.com`
  or `https://accounts.google.com`. The JWKS is cached in-process for an hour;
  an unknown `kid` triggers one refetch (key rotation), and a second miss is a
  failure. No SDK, no `requests`, and the HTTP call is mockable with
  `MockTransport` exactly like the Gemini and Groq clients.
- Requires `sub` (str), `email` (str), `email_verified == true`.
- `400 Google sign-in failed.` for any exchange or verification failure — the
  response never explains which check failed.
- `403 Google has not verified that email address.` for an unverified email.
- `409 That email is already linked to a different sign-in method.` for the
  conflicting-`sub` case in §7.

The endpoint is unauthenticated by nature (it is a callback); PKCE plus the
client secret are what make a stolen `code` useless.

---

## 9. Data model

`users` gains one column and loses one `NOT NULL`:

| Column | Before | After |
| --- | --- | --- |
| `email` | `varchar(255) NOT NULL UNIQUE` | unchanged |
| `password_hash` | `varchar(255) NOT NULL` | `varchar(255) NULL` |
| `google_sub` | — | `varchar(255) NULL UNIQUE` (`uq_users_google_sub`) |

`google_sub` is Google's stable subject identifier. It is nullable so every
existing row is valid, and unique so one Google account cannot map to two users.
The model mirrors it with `Mapped[str | None]`.

Migration `down_revision = "7c1e4a9b2d3f"`. Downgrade restores `NOT NULL`,
which fails if Google-only users exist; that is documented in the migration.

---

## 10. Configuration

**API** (`apps/api/.env`, `.env.example`):

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
```

All three default to `""`. `Settings.google_oauth_enabled` is true only when all
three are non-empty. Existing deployments therefore start unchanged.

**Web** (`apps/web/.env`, `.env.example`):

```
GOOGLE_CLIENT_ID=
GOOGLE_REDIRECT_URI=
```

Server-only, read inside route handlers and server components. `GOOGLE_REDIRECT_URI`
must be **identical** on both services and must be registered in the Google
Cloud console; it is the web callback, e.g.
`http://localhost:3000/api/auth/google/callback` in dev and
`https://<vercel-host>/api/auth/google/callback` in production.

**Dependency:** `pyjwt[crypto]` replaces `pyjwt` in `apps/api` (it pulls in
`cryptography`, which `RS256` needs). The code exchange and the JWKS fetch both
use `httpx`, already present, so both are mockable with `MockTransport`.

---

## 11. UI

- `components/google-sign-in.tsx` (server component): a bordered, surface-coloured
  `h-10` link with an inline 16px Google mark and the label "Continue with
  Google", then an `or` rule. It renders nothing when Google is unconfigured.
- `/login` and `/signup` place it above `AuthForm`, inside `AuthShell`.
- `/login` and `/signup` read `?error=` and render one inline `text-danger` alert
  above the form. Messages: `google_state` → "That sign-in link expired. Try
  again.", `google_unverified` → "Google hasn't verified that email address.",
  `google_conflict` → "That email is already linked to another sign-in method.",
  `google_denied` → "Google sign-in was cancelled.", anything else → "Google
  sign-in didn't work. Try again, or use your email and password."
- No change to `AuthForm`, no new client state. The button is a plain `<a>`, so
  it is a full navigation — consistent with the "no router.push across a
  cookie change" rule.

---

## 12. Testing

API (`tests/modules/auth/`):

- `conftest.py` (new, local): a `FakeGoogleClient` with a settable profile and
  error, plus the `get_google_client` dependency override.
- `test_google.py`: exchange success creates a user with `password_hash IS NULL`;
  second sign-in reuses the row; existing email/password account gets
  `google_sub` attached and keeps its password login; a second Google identity
  on an already-linked email → 409 and no mutation; unverified email → 403;
  exchange failure → 400; `redirect_uri` mismatch → 400; unconfigured → 503.
- `test_google_client.py`: `MockTransport` for the token endpoint (success, 400,
  missing `id_token`) and for the JWKS endpoint (known `kid`, unknown `kid`
  triggers exactly one refetch, bad signature / wrong audience / wrong issuer /
  expired token are all rejected).
- `test_login.py`: a passwordless user gets `401`, not a crash.

Web: no test framework. Verification is
`pnpm lint && pnpm exec next typegen && pnpm exec tsc --noEmit && pnpm build`,
plus `curl` checks that the start route 302s to `accounts.google.com` with the
expected parameters and that a wrong `state` lands on `/login?error=google_state`.
The full round trip needs real credentials; §13 covers the manual pass.

---

## 13. Operational steps (human)

1. Google Cloud console → *APIs & Services* → *OAuth consent screen* (External,
   app name "Ragnest", support email, scopes `openid`, `email`).
2. *Credentials* → *Create credentials* → *OAuth client ID* → *Web application*.
   Authorised redirect URIs: the local and production web callbacks. Add
   `http://localhost:3000/api/auth/google/callback` and
   `https://<vercel-host>/api/auth/google/callback`.
3. Copy the client id/secret into the API host's env and the id/redirect URI
   into Vercel's; redeploy both (Vercel only applies env changes to new
   deployments).
4. While the consent screen is in *Testing*, only listed test users can sign in.

---

## 14. What the builder decides

- Exact module split inside `auth/` (`google.py` for the client, `deps.py` for
  the dependency, `service.py` for the upsert) — follow the existing module.
- Whether `GoogleOAuthClient` creates its own `httpx.AsyncClient` or accepts
  one for tests; match `embeddings.py`/`llm.py`.
- Cookie encoding (plain JSON is fine; it is httpOnly and small).
- Whether the error alert lives in the page or in a tiny shared component.
