# Ragnest API — Foundation (Clean Skeleton) — Design

**Date:** 2026-10-14
**Status:** Draft for review
**Milestone:** 1 of N (foundation only)

---

## 1. Why this exists

Ragnest is a multi-tenant SaaS: an organization signs up, creates a workspace,
uploads documents (txt/pdf/md), and chats with them. Answers must be grounded
only in that workspace's documents, with citations back to the source file.

Building that end-to-end is a lot. An earlier attempt produced a working API
(JWT auth, users, organizations, migrations) but it went badly for two reasons:

1. **No settled structure.** Folders moved repeatedly; each refactor made the
   codebase harder to hold in your head.
2. **The agent ran ahead.** Large amounts of code appeared that you did not
   understand and could not maintain.

This milestone deliberately goes the other way: a small, stable foundation you
understand line by line and built yourself, with a mentor guiding rather than
typing on your behalf.

## 2. Intent

- **Learn FastAPI** by building a real backend, not a tutorial clone.
- Produce a **clean skeleton** that every later feature sits on, so we never
  have to restructure it.
- Keep the pace slow and the involvement yours.

## 3. Goals (this milestone)

A FastAPI app that:

- Boots and serves a `GET /health` endpoint.
- Loads configuration from the environment (Pydantic settings).
- Connects to Postgres asynchronously (SQLAlchemy 2 async + asyncpg).
- Proves the full vertical slice: config → engine → session → route → response,
  by having `/health` actually query the database (`SELECT 1`).
- Has Alembic wired up and verified (migrations run, `alembic_version` created),
  but **no domain tables yet**.
- Has structured logging configured at startup.
- Has a small automated test suite that runs without touching the real database.
- Has a README describing how to run, migrate, and test.

## 4. Non-goals (this milestone)

- Auth (signup/login), users, organizations, workspaces.
- Document upload or processing.
- Embeddings, vector search, retrieval, chat.
- Invites, roles/permissions beyond what exists today.
- Any domain table or migration beyond the Alembic baseline.

## 5. Anti-goals (this milestone is a failure if…)

- You end up with code you don't understand.
- The folder layout changes more than once.
- We build auth or RAG before the foundation is solid and tested.
- Tests are skipped "for now" and later discovered to be broken.
- The agent writes bulk code without explanation.

## 6. Constraints

- **Language/runtime:** Python `>=3.13`; dependencies managed with `uv`.
- **Framework:** FastAPI (`fastapi[standard]`), Pydantic v2, `pydantic-settings`.
- **Database:** SQLAlchemy 2.0 async + `asyncpg`; PostgreSQL (Neon) in dev.
- **Migrations:** Alembic.
- **Lint/format:** `ruff`.
- **Tests:** `pytest` + `pytest-asyncio` + `httpx` (ASGI client) + `aiosqlite`
  (isolated async test DB).
- **No `src/` layout.** Everything lives in one top-level `app/` package. (The
  previous `src/` layout caused recurring import-path pain — e.g. uvicorn
  needing `--app-dir src` — that we will not repeat.)
- **No throwaway schema.** We add no table we would have to delete later.

## 7. How we work (working agreement)

- **You write the code.** The mentor explains, reviews, and answers questions.
- **One small task at a time.** Finish, verify together, then move on.
- **The mentor writes a file only when** it is pure boilerplate with nothing to
  learn, or debugging it would cost more than it teaches — and always says so
  first, then explains the code line by line.
- **No unrequested refactors.** Structural changes are proposed and agreed
  before anything moves.
- **Small, frequent commits** so history tells the story.

## 8. Structure we are locking

The rules that keep this from becoming a mess:

> - `app/core` and `app/db` are shared infrastructure.
> - `app/api` is the HTTP layer: the aggregate router, shared HTTP dependencies,
>   and infrastructure routes (health).
> - **Domain features are modules** under `app/modules/<feature>/`, added when
>   the first one (auth) arrives. A module owns its router, schemas, models, and
>   service. New features copy the shape of an existing module.

`app/modules/` does not exist yet — there is no domain feature in this
milestone. It appears with the auth milestone. That is growth, not a
restructure: no existing file moves.

```
apps/api/
├── alembic.ini                 # Alembic config; script_location -> migrations
├── pyproject.toml              # deps + ruff + pytest config
├── uv.lock
├── .env                        # real secrets (gitignored)
├── .env.example                # documented, committed
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py                 # create_app() factory + lifespan
│   ├── core/                   # cross-cutting infrastructure
│   │   ├── __init__.py
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   └── logging.py          # configure_logging()
│   ├── db/                     # database infrastructure
│   │   ├── __init__.py
│   │   ├── base.py             # DeclarativeBase + naming convention + TimestampMixin
│   │   └── session.py          # engine, SessionLocal, get_db
│   └── api/                    # HTTP layer
│       ├── __init__.py         # empty package marker
│       ├── router.py           # api_router aggregate
│       └── health.py           # GET /health
├── migrations/                 # Alembic scripts
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
└── tests/
    ├── conftest.py
    └── test_health.py
```

## 9. Decisions (make now, hold steady)

These are the mentor's calls. Change any of them in review — but once this
document is approved, they stop moving.

1. **App factory.** `create_app() -> FastAPI` in `app/main.py`, with an
   `app = create_app()` module-level instance for ASGI servers. Routes are
   registered by an aggregate router at `app/api/router.py`, not decorated
   directly in `main.py`. `main.py` includes the aggregate. *Why:* makes
   configuration/logging/test setup explicit and keeps `main.py` small.
2. **No `src/` layout.** Single `app/` package at project root. *Why:* avoids
   the documented import-path pain from last time.
3. **HTTP layer vs domain modules.** `app/api` holds the aggregate router and
   infrastructure routes (health); domain features live in
   `app/modules/<feature>/`. *Why:* this is the structure the whole app scales
   into, so we never restructure. `app/modules/` is created with the first
   domain feature (auth).
4. **Config via `pydantic-settings`** reading from `.env`. `Settings` exposes a
   normalized `database_url` (scheme rewritten to `postgresql+asyncpg://`;
   libpq-only params like `sslmode`/`channel_binding` stripped) plus
   `database_connect_args` to pass SSL and `statement_cache_size=0`. *Why:*
   Neon's URL crashes asyncpg verbatim, and the pooled (`-pooler`) endpoint
   breaks asyncpg's prepared-statement cache — we hit both walls last time;
   fixing them now means they never surprise us again.
5. **Async SQLAlchemy.** One `AsyncEngine` + `async_sessionmaker`, created once
   in `db/session.py`. `get_db` is a FastAPI dependency yielding a session.
   Pool configured with `pool_pre_ping=True` and `pool_recycle=300`. Engine
   disposed in the app `lifespan`. *Why:* correct lifecycle, no leaked pools.
6. **Health is infrastructure, not a versioned API.** `GET /health` lives at
   the root; domain endpoints will live under `/api/v1`. *Why:* infra probes
   should not be versioned.
7. **Health semantics.** `GET /health` executes `SELECT 1`:
   - success → `200 {"status": "ok", "database": "connected"}`
   - DB failure → `503 {"status": "error", "database": "unreachable"}`
8. **No domain tables in this milestone.** Alembic is configured and verified
   (`upgrade head` works), but the first real table (users) arrives in the auth
   milestone. *Why:* avoids a throwaway schema and cleanup debt.
9. **Logging** via the standard library, configured once in `create_app()`.
10. **Tests are isolated.** `tests/conftest.py` builds the app against an
    in-memory/async SQLite database (`aiosqlite`) and overrides `get_db`, so the
    suite runs fast and never touches Neon.
11. **Lint/format with ruff**, enforced in CI-style commands
    (`ruff check`, `ruff format --check`).

## 10. Starting point / repo hygiene

The working tree is mid-revert: the previous implementation sits in git history
and staged renames, while the disk holds a partial tutorial scaffold
(`apps/api/main.py`, `apps/api/config.py`, an empty `apps/api/app/db/`) that does
**not** match the structure in §8.

The **first task of the plan** is therefore: delete the leftover scaffolding and
commit a clean, intentional starting point (just `pyproject.toml`, `.env`,
`.env.example`, `.python-version`, `README.md`, and an empty `app/`). No new code
is written in that commit. The old implementation stays recoverable in prior
commits. Every task after that creates files in the §8 layout.

## 11. Dev database state — verified

The connection string in `apps/api/.env` points at a **new, empty Neon
instance** (you deleted the old one). Verified directly: `public` schema has no
tables and no `alembic_version`. Nothing to reset. Migrations will start clean
against this instance; the plan needs no branching or cleanup step.

## 12. Where this goes next (context only — not specified here)

Each of these gets its own design + plan when we reach it:

2. **Auth** — users + organizations, signup/login, JWT. First real models and
   migration.
3. **Workspaces & membership** — create workspace, invite members.
4. **Documents** — upload txt/pdf/md, store, extract text.
5. **Retrieval** — chunk, embed, store vectors, search scoped to a workspace.
6. **Chat (RAG)** — ask questions, stream grounded answers with citations.

## 13. Left to the builder (not decided here)

- Exact wording/content of the README.
- Precise test function names and assertions (fixed in the plan).
- Whether to add an `AppError` + global exception handler now or wait for the
  first feature that needs it (leaning: wait).
- CI configuration (out of scope for this milestone; local commands only).
