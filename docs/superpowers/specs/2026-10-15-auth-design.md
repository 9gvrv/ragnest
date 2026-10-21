# Ragnest API — Milestone 2: Users & Authentication — Design

**Date:** 2026-10-15
**Status:** Draft for review
**Milestone:** 2 of N

---

## 1. Why this exists

Milestone 1 delivered a bootable skeleton (config, async DB, `/health`, Alembic
baseline, tests). Milestone 2 adds the **first domain feature**: user accounts and
authentication.

Everything later — workspaces, documents, chat — hangs off "who is this user?".
This milestone answers that question and establishes the `app/modules/<feature>/`
pattern every future feature copies.

## 2. Intent

- Learn authentication properly: password hashing, JWTs, FastAPI dependencies.
- Establish the module structure the rest of the app grows into.
- Keep the scope minimal: accounts and auth. No tenancy objects yet.

## 3. Goals (this milestone)

- A `users` table and one Alembic migration.
- `POST /api/v1/auth/signup` — email + password → account (+ token).
- `POST /api/v1/auth/login` — email + password → access token.
- `GET /api/v1/users/me` — the authenticated user.
- A `get_current_user` dependency (Bearer token) other features will reuse.
- Password hashing with argon2; JWTs signed with HS256.
- Tests that run on in-memory SQLite and never touch Neon.

## 4. Non-goals (this milestone)

- Workspaces, membership, roles, invitations.
- Documents, chat, retrieval.
- Organization/team grouping (see §7).
- Password reset, email verification, refresh tokens, logout, OAuth/Google.

## 5. Anti-goals (this milestone is a failure if…)

- Passwords are stored reversibly, or a `password_hash` ever appears in a
  response or log.
- Tests touch Neon or depend on a local `.env`.
- The module layout has to be restructured to add the next feature.
- Hand-rolled crypto instead of a maintained library.
- Scope creep pulls workspaces into this milestone.

## 6. Constraints

- Python 3.13, `uv`, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic.
- Continue the locked structure: single `app/` package, no `src/`, features under
  `app/modules/<feature>/`.
- Reuse `app/db/base.py` (`Base` + naming convention + `TimestampMixin`).
- Must work identically on **SQLite (tests)** and **Postgres/Neon (dev)**.

## 7. Tenancy decision (organizations removed)

An earlier draft of this milestone had `users`, `organizations`, and
`memberships`, with an organization as the tenant. **We deliberately dropped
that.** Rationale:

- The product's core is RAG (upload documents, chat with them). A grouping layer
  above the place documents live buys nothing yet.
- Dropping it removed three unresolved questions: whether an organization was
  optional at signup, how to handle duplicate organization names, and how to
  manage personal/"default" organizations.

**Consequence for later milestones:** the **workspace** becomes the tenant.
Documents, chat, membership, roles, and invitations will all scope to a
workspace, not to an organization:

```
workspaces (future)         workspace_members (future)
──────────                  ─────────────────
id                         workspace_id  fk
name                       user_id       fk
created/updated            role  creator|admin|member
                           unique(workspace_id, user_id)
```

If a grouping layer above workspaces is ever needed (one company, many
workspaces, invite once), it is an *additive* migration then — not a rewrite now.

Default per-user experience: sign up → create your first workspace. There is no
"org-less state" to manage because there is no organization at all.

## 8. Data model (decided)

```
users
─────
id             Uuid  pk
email          str   unique (stored lowercase)
password_hash  str
created_at / updated_at  ts   (TimestampMixin)
```

Decisions and rationale:

- **UUID primary key**, so IDs are not guessable/enumerable and can be generated
  client-side later.
- **Email normalized to lowercase** before storing, with uniqueness on that
  normalized value. (A `citext` column is Postgres-only; lowercasing keeps SQLite
  and Postgres identical.)
- **`created_at`/`updated_at`** come from the existing `TimestampMixin`.
- **No other tables** this milestone. Roles live at the workspace level and
  arrive with workspaces.

## 9. Signup / login semantics (decided)

- `POST /api/v1/auth/signup` with `{ email, password }`:
  1. Normalize + validate the email; reject duplicates with **409**.
  2. Hash the password (argon2).
  3. Create the `User`.
  4. Return **201** with the user and an access token (signup auto-logs-in).
- `POST /api/v1/auth/login` with `{ email, password }`: verify credentials, return
  an access token. On failure, **401** with a generic message (never reveal
  whether the email exists).
- Password policy: minimum length 8 (validated by the request schema).

## 10. Authentication mechanics (decided)

- **Password hashing:** `pwdlib[argon2]`.
- **Tokens:** `PyJWT`, HS256.
  - `sub` = user id, `exp` = now + `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30),
    `iat` = now.
  - No refresh tokens this milestone.
- **Transport:** `Authorization: Bearer <token>`, via FastAPI's `HTTPBearer`
  security scheme (works with Swagger's Authorize button — paste the token).
- **`get_current_user`:** decode the token, load the `User`, raise **401** on
  missing/invalid/expired token or unknown user. Returns the ORM `User`.
- **Settings additions:** `SECRET_KEY` (required, no insecure default) and
  `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30). `SECRET_KEY` also goes into
  `.env.example` with a placeholder.
- **Email validation** via Pydantic `EmailStr` (adds an `email-validator`
  runtime dependency).

## 11. Module layout (decided)

```
app/modules/
├── users/
│   ├── __init__.py
│   ├── models.py        # User
│   ├── schemas.py       # UserRead
│   └── router.py        # GET /users/me
└── auth/
    ├── __init__.py
    ├── router.py        # POST /auth/signup, POST /auth/login
    ├── schemas.py       # SignupRequest, LoginRequest, TokenResponse
    ├── security.py      # hash/verify password, create/decode token
    ├── service.py       # create_user, authenticate
    └── deps.py          # get_current_user
```

- Models live with the module that owns the entity (`User` in `users`).
- Both routers are added to `app/api/router.py` (the aggregate) under a
  `/api/v1` prefix.
- **Model registration:** Alembic autogenerate and the test harness only see
  models that have been imported. A single place must import every module's
  `models.py` before `Base.metadata` is used. *(Exact mechanism left to the
  builder — see §14.)*

## 12. API surface (decided)

All under `/api/v1`.

| Method | Path | Auth | Body | Success | Errors |
|--------|------|------|------|---------|--------|
| POST | `/auth/signup` | no | `{email, password}` | `201 {access_token, token_type, user}` | `409` email exists, `422` invalid |
| POST | `/auth/login` | no | `{email, password}` | `200 {access_token, token_type}` | `401` bad credentials |
| GET | `/users/me` | Bearer | — | `200 {id, email, created_at}` (`UserRead`) | `401` |

- JSON request bodies (not the OAuth2 password form). `HTTPBearer` still gives a
  usable Swagger Authorize button.
- `password_hash` is **never** in a response schema.
- Error shape: FastAPI's default `{"detail": ...}` via `HTTPException`.

## 13. Testing strategy

- In-memory async SQLite via `aiosqlite`, tables created from `Base.metadata`,
  `get_db` overridden (extends the Milestone 1 harness).
- Tests (and Alembic) must set a dummy `SECRET_KEY` before importing `app.*`
  modules, exactly as `DATABASE_URL` is set today.
- New tests mirror the app tree: `tests/modules/auth/`, `tests/modules/users/`.
- Cases: signup creates a user and returns a token; duplicate email → 409; login
  success returns a token; wrong password → 401; unknown email → 401;
  `/users/me` without a token → 401; with a valid token returns the user;
  tampered/expired token → 401; no response ever contains `password_hash`.
- No test may reach Neon.

## 14. Left to the builder (not decided here)

- The exact model-registration mechanism (an `app/db/models.py` aggregator
  imported by `alembic/env.py` and the test harness, vs. explicit imports).
- Precise 401/409 `detail` strings.
- Whether password policy is a Pydantic `min_length` or a custom validator.
- Whether `GET /users/me` lives in `users/router.py` or `auth/router.py`
  (leaning: `users`).
- Token `sub` type handling (UUID ↔ string).

## 15. Where this goes next (context only)

- **Milestone 3 — Workspaces, roles & invitations:** create workspace (creator
  role), invite members (admin/member), accept invite. This is where the
  workspace-as-tenant model in §7 gets built.
- Then: documents, retrieval, chat.

The previous attempt's auth code remains in git history as reference. We are
**not** copying it; this design is written from scratch.
