# AGENTS.md — Ragnest API

> **Read this before touching code.** It records the decisions, structure, and
> traps we cannot afford to rediscover. It is not a tutorial and not a duplicate
> of `README.md`.
>
> **Last updated:** 2026-11-07 (deployment runbook; Neon production branch verified and stamped)

---

## 1. What this project is

**Ragnest** is a multi-tenant RAG SaaS: a user signs up, creates a workspace,
uploads documents (txt/pdf/md), and chats with them. Answers must be grounded
only in that workspace's documents, with citations to the source file. The
**workspace is the tenant** — there are no organizations (see §13).

`apps/api/` is the **FastAPI backend**. It is one part of a monorepo; treat it as
its own project (its own `pyproject.toml`, its own `.env`).

An earlier attempt produced a working API (JWT auth, users, orgs, migrations) but
failed for two reasons we are deliberately correcting:

1. **No settled structure** — folders moved repeatedly and became hard to hold in
   your head.
2. **The agent ran ahead** — large amounts of unexplained code appeared.

Milestone 1 therefore rebuilt only a small, stable foundation, understood line by
line.

---

## 2. How we work (working agreement — do not violate)

- **The human writes the code.** The agent explains, reviews, and answers
  questions. It acts as a mentor, not a code generator.
- **One small task at a time.** Finish, verify together, then move on.
- **The agent writes a file only when** it is pure boilerplate with nothing to
  learn, or debugging it would cost more than it teaches — and must **say so
  first**, then explain the code line by line.
- **No unrequested refactors.** Structural changes are proposed and agreed
  _before_ anything moves.
- **Small, frequent commits**, so history tells the story.
- **Design before code for every new milestone.** New features get a short design
  doc and a task-by-task plan before implementation.

If you are an agent: default to explaining and asking, not editing. When in
doubt, stop and ask.

---

## 3. Locked structure (do not reorganize)

Rules that keep this from becoming a mess:

- `app/core/` and `app/db/` are **shared infrastructure**.
- `app/api/` is the **HTTP layer**: the aggregate router, shared HTTP
  dependencies, and infrastructure routes (health).
- **Domain features are modules** under `app/modules/<feature>/`, each owning its
  router, schemas, models, service, and (where applicable) deps. New features copy the shape of an
  existing module.

```
apps/api/
├── alembic.ini              # script_location -> %(here)s/alembic
├── pyproject.toml           # deps + [dependency-groups] dev + ruff + pytest config
├── uv.lock
├── .env                     # REAL secrets — gitignored, never commit
├── .env.example             # documented, committed
├── AGENTS.md                # this file
├── README.md
├── alembic/                 # migration scripts (see §7 for naming note)
│   ├── env.py               # async env.py, reads Settings
│   ├── script.py.mako
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py              # create_app() factory + lifespan
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Settings (pydantic-settings) + Neon URL normalization
│   │   └── logging.py       # configure_logging()
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py          # Base (DeclarativeBase + naming convention) + TimestampMixin
│   │   ├── models.py        # import-only aggregator registering all models
│   │   └── session.py       # engine, SessionLocal, get_db, dispose_engine
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py        # api_router aggregate — includes every feature router
│   │   └── health.py        # GET /health
│   └── modules/             # domain feature modules
│       ├── __init__.py
│       ├── chat/
│       │   ├── __init__.py
│       │   ├── constants.py   # budgets, refusal text, default title
│       │   ├── deps.py        # get_llm_provider
│       │   ├── llm.py         # LLMProvider protocol + Groq client
│       │   ├── models.py      # Conversation, Message
│       │   ├── prompts.py     # grounded prompt, trimming, citation parse
│       │   ├── router.py      # conversation CRUD + SSE messages
│       │   ├── schemas.py     # Citation, conversation/message models
│       │   ├── service.py     # CRUD, prepare_exchange, persist_assistant
│       │   └── types.py       # JSONB on PG, JSON on SQLite
│       ├── documents/
│       │   ├── __init__.py
│       │   ├── models.py     # Document (text only; no bytes, no key)
│       │   ├── schemas.py    # DocumentSummary, DocumentDetail
│       │   ├── extraction.py # extension allowlist, decode/PDF parse, limits
│       │   ├── middleware.py # 413 from Content-Length before multipart spool
│       │   ├── service.py    # ingest, list, get, delete, can_manage
│       │   └── router.py     # /workspaces/{id}/documents
│       ├── invitations/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── router.py
│       │   ├── schemas.py
│       │   └── service.py
│       ├── retrieval/
│       │   ├── __init__.py
│       │   ├── backfill.py    # python -m app.modules.retrieval.backfill
│       │   ├── chunking.py    # offset-preserving recursive chunker
│       │   ├── constants.py   # model, dimension, chunk and search limits
│       │   ├── deps.py        # get_embedding_provider, get_session_factory
│       │   ├── embeddings.py  # EmbeddingProvider protocol + Gemini client
│       │   ├── models.py      # DocumentChunk
│       │   ├── router.py      # POST /workspaces/{id}/search
│       │   ├── schemas.py     # SearchRequest, SearchResult
│       │   ├── service.py     # index_document, search
│       │   └── types.py       # vector(768) on PG, JSON on SQLite
│       ├── users/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── router.py
│       │   └── schemas.py
│       ├── workspaces/
│       │   ├── __init__.py
│       │   ├── deps.py       # require_workspace_member/admin/creator
│       │   ├── models.py     # Workspace, WorkspaceMember, WorkspaceRole
│       │   ├── router.py
│       │   ├── schemas.py
│       │   └── service.py
│       └── auth/
│           ├── __init__.py
│           ├── deps.py
│           ├── router.py
│           ├── schemas.py
│           ├── security.py
│           └── service.py
└── tests/                   # mirrors the app tree
    ├── conftest.py          # shared fixtures: client, session_factory
    ├── test_app.py
    ├── api/test_health.py
    ├── core/test_config.py, core/test_logging.py
    ├── db/test_base.py, db/test_session.py
    └── modules/             # domain feature tests
        ├── auth/
        │   ├── __init__.py
        │   ├── test_login.py
        │   └── test_signup.py
        ├── chat/
        │   ├── __init__.py
        │   ├── conftest.py       # seed fixture (creator/admin/member/outsider)
        │   ├── test_llm.py
        │   ├── test_model.py
        │   ├── test_prompts.py
        │   ├── test_router.py
        │   └── test_service.py
        ├── documents/
        │   ├── __init__.py
        │   ├── conftest.py       # seed fixture: users, workspace, roles, tokens
        │   ├── fixtures/         # sample txt/md, PDFs, wrong.bin
        │   ├── test_extraction.py
        │   ├── test_model.py
        │   ├── test_service.py
        │   ├── test_router.py
        │   └── test_permissions.py
        ├── invitations/
        │   ├── __init__.py
        │   └── test_preview.py
        ├── retrieval/
        │   ├── __init__.py
        │   ├── conftest.py       # seed fixture (creator/admin/member/outsider)
        │   ├── test_backfill.py
        │   ├── test_chunking.py
        │   ├── test_embeddings.py
        │   ├── test_model.py
        │   ├── test_search.py
        │   ├── test_service.py
        │   └── test_upload.py
        └── users/
            ├── __init__.py
            ├── test_me.py
            └── test_model.py
```

**`app/modules/` holds every domain feature** (`auth`, `users`, `workspaces`,
`invitations`, `documents`, `retrieval`, `chat`). Modules were added over time;
no existing file moved.

### Hard structural rules

- **No `src/` layout.** Single top-level `app/` package. (The old `src/` layout
  caused recurring import pain, e.g. uvicorn needing `--app-dir src`.)
- **`app/api/router.py` is the aggregate router, not a route file.** It imports
  each feature's router and includes it. `main.py` includes only `api_router`
  once. Adding endpoints = add a router file, then one line in `router.py`.
- Infrastructure routes (health, later root/meta) stay in `app/api/`. Domain
  routes live in `app/modules/<feature>/router.py`.

---

## 4. Architecture decisions (make once, hold steady)

1. **App factory.** `create_app() -> FastAPI` in `app/main.py`, plus a
   module-level `app = create_app()` for ASGI servers (uvicorn/fastapi CLI).
   Routes are registered via the aggregate router, never decorated in `main.py`.
2. **Config via `pydantic-settings`**, reading `apps/api/.env` (path resolved
   from `config.py`, not CWD). `extra="ignore"`.
3. **Async SQLAlchemy 2.0.** One `AsyncEngine` + `async_sessionmaker` created
   once in `app/db/session.py`. `get_db` is a FastAPI dependency yielding a
   session. Engine uses `pool_pre_ping=True`, `pool_recycle=300`, and is disposed
   in the app `lifespan` (`dispose_engine`).
4. **Health is infrastructure, not a versioned API.** `GET /health` lives at the
   root. Domain endpoints will live under `/api/v1`.
5. **Health semantics.** `SELECT 1` against the DB:
   - success → `200 {"status": "ok", "database": "connected"}`
   - DB failure → `503 {"status": "error", "database": "unreachable"}`
   - The broad `except Exception` is **intentional** (a health check must never
     raise); it is marked `# noqa: BLE001` with a comment. Do not "fix" it
     without updating `tests/api/test_health.py`.
6. **Dependency style.** Use `Annotated[AsyncSession, Depends(get_db)]`, not
   `session: AsyncSession = Depends(get_db)` (avoids ruff `B008`, and is current
   FastAPI idiom).
7. **Logging** via the stdlib, configured once in `create_app()`.
8. **Chat streams Server-Sent Events.** One endpoint,
   `POST /api/v1/workspaces/{workspace_id}/conversations/{id}/messages`, emits
   `sources` → `token`* → `done`. `error` is terminal (never followed by
   `done`). The first provider event is awaited **before** returning
   `StreamingResponse`, so pre-token failures are ordinary JSON errors
   (429/503). Conversations are private to their author: other members get 404,
   non-members get 403 at the workspace gate. Zero retrieved chunks skip the
   model entirely and persist a fixed refusal with `finish_reason="no_context"`.
   Generation never retries and never exposes `delta.reasoning` (no
   chain-of-thought). See §6 for keys and §7 for the timestamp trap.

---

## 5. Neon / Postgres traps (we hit these before — do not relearn)

The `DATABASE_URL` Neon hands you is a **libpq** URL, e.g.:

```
postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/db?sslmode=require&channel_binding=require
```

Two things break if used verbatim:

1. **`asyncpg` rejects libpq-only params** like `sslmode`, `channel_binding`,
   `sslnegotiation`.
2. **Neon's `-pooler` endpoint (PgBouncer)** breaks asyncpg's prepared-statement
   cache.

`app/core/config.py` (`Settings`) solves both, and **everything must consume it
rather than the raw env var**:

- `settings.DATABASE_URL` — raw value (do not pass to SQLAlchemy directly).
- `settings.database_url` — scheme rewritten to `postgresql+asyncpg://`, with
  `sslmode` / `channel_binding` / `sslnegotiation` stripped. **Use this for
  SQLAlchemy.**
- `settings.database_connect_args` — `{"statement_cache_size": 0}`, plus
  `{"ssl": True}` when the original URL had `sslmode=require`. **Pass this too.**

If you add another DB engine (e.g. in Alembic), pass
`connect_args=settings.database_connect_args` exactly as `app/db/session.py` and
`alembic/env.py` do.

---

## 6. Config & secrets

- `.env` is **gitignored** and holds the real credentials. Never commit it, never
  print it, never paste it into logs.
- `.env.example` is committed and documents the shape:
  `APP_NAME`, `LOG_LEVEL`, `DATABASE_URL`, `SECRET_KEY`, `GEMINI_API`,
  `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_REASONING_EFFORT`,
  `ACCESS_TOKEN_EXPIRE_MINUTES`. It also carries an empty
  `DATABASE_URL_PROD` placeholder, which is a **local convenience only** — the
  app never reads it. Point `DATABASE_URL` at the production branch to run
  migrations there (use the **direct**, non-pooler URL for DDL).
- Settings fields: `APP_NAME` (default `"Ragnest API"`), `LOG_LEVEL` (default
  `"INFO"`), `DATABASE_URL` (**required**), `SECRET_KEY` (**required**),
  `GEMINI_API` (**required**, Gemini embeddings), `LLM_API_KEY` (**required**,
  Groq generation), `LLM_BASE_URL` (default
  `https://api.groq.com/openai/v1`), `LLM_MODEL` (default
  `openai/gpt-oss-120b`), `LLM_REASONING_EFFORT` (default `"low"`; blank omits
  the field), `ACCESS_TOKEN_EXPIRE_MINUTES` (default `30`).
- **Blank LLM keys fall back to defaults.** A `key=` line in `.env` arrives as
  `""`, not "unset"; a model validator restores the base URL and model and
  strips `LLM_REASONING_EFFORT`, so an empty placeholder cannot silently break
  generation. `LLM_API_KEY` has no default and must be real.
- `SECRET_KEY` is used for HS256 JWTs; tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES`.
- The project uses `pwdlib[argon2]` for password hashing and `PyJWT` for token signing; `EmailStr` validation is provided by `email-validator`.
- A module-level `settings = Settings()` exists; `Settings()` is instantiated at
  import time. Keep that in mind if you touch import order in tests.

---

## 7. Database & migrations

- Migrations use **Alembic**, folder named **`alembic/`** (the Alembic default).
  **Naming note:** the design doc §8 shows `migrations/`; the real, as-built
  folder is `alembic/`. Trust `alembic/`. `alembic.ini` has
  `script_location = %(here)s/alembic`.
- `alembic/env.py` is **async**: it reads `settings.database_url`, sets
  `sqlalchemy.url`, uses `async_engine_from_config` with
  `connect_args=settings.database_connect_args`, and targets `Base.metadata`.
- The first real domain table is **`users`** (T1 of Milestone 2); Milestone 3
  adds **`workspaces`**, **`workspace_members`** and **`invitations`**;
  Milestone 4 adds **`documents`** (`25d91090dee5`); Milestone 5 adds
  **`document_chunks`** plus `documents.embedding_status`/`indexed_at`
  (`299585b2a1a6`); Milestone 6 adds **`conversations`** and **`messages`**
  (`7c1e4a9b2d3f`). The two empty baseline revisions
  (`736e318369b1 -> a058018dc98a`) remain a cosmetic wart; squashing is
  optional.
- **Milestone 5 uses pgvector in the same database.** The migration runs
  `CREATE EXTENSION IF NOT EXISTS vector` and creates an HNSW cosine index
  (`ix_document_chunks_embedding_hnsw`). No second database or vector service
  exists. `app/modules/retrieval/types.py` declares `Vector(768)` with a JSON
  SQLite variant, so tests need no Postgres. `document_chunks.document_id` and
  `.workspace_id` are both `ON DELETE CASCADE`.
- **`documents` stores text only.** There is no `storage_key`, no URL, and no
  file on disk: `extracted_text` is the durable artefact, `char_count` always
  equals its length, and `page_count` is `NULL` for txt/md. `document_chunks`
  cascades from the hard-deleted document (and from the workspace).
- **Chat tables.** `conversations` (`id`, `workspace_id`, `created_by`, `title`,
  `created_at`, `updated_at`) and `messages` (`id`, `conversation_id`, `role`,
  `content`, `citations`, `model`, `finish_reason`, `created_at`) both cascade
  from their parents; deleting a workspace removes its conversations and their
  messages. `citations` is `JSONB` on Postgres with a JSON SQLite variant
  (`chat/types.py`) and stores the citation snapshot, so citations survive
  document deletion. Conversation listing is filtered by `workspace_id` **and**
  `created_by` — the author is part of the query, not just the API check.
- **Conversation timestamps are naive UTC; message timestamps are aware.** The
  `TimestampMixin` columns are `TIMESTAMP WITHOUT TIME ZONE`; asyncpg rejects
  an aware `datetime` bound to them (`can't subtract offset-naive and
  offset-aware datetimes`). `chat/service.py` therefore uses
  `_utcnow_naive()` for `conversations.created_at`/`updated_at`, while
  `messages.created_at` is a `timestamptz` column and keeps
  `datetime.now(UTC)`. SQLite accepts both, so only a Postgres smoke test
  catches a regression here.
- Apply migrations with `uv run alembic upgrade head`; inspect with
  `uv run alembic current` / `uv run alembic history`.
- **A schema-only Neon branch copy loses the `alembic_version` row.** Tables,
  the `vector` extension, and the HNSW index copy across; the version row does
  not. The production branch therefore showed an empty `alembic_version` even
  though its schema already matched head. Verify with `compare_metadata` (or a
  careful manual diff), then `alembic stamp head`; never run `upgrade head`
  against a schema that is already current. Use the **direct** (non-pooler) URL
  for migrations and the **pooled** URL for the running API. Full runbook:
  `docs/deployment.md`.

---

## 8. Testing

- Runner: **pytest** with `pytest-asyncio` in `asyncio_mode = "auto"` (async
  tests need no decorator). Config lives in `pyproject.toml`
  (`testpaths = ["tests"]`).
- **Tests never touch Neon.** `tests/conftest.py` sets a dummy `DATABASE_URL`
  _before_ importing any `app.*` module, builds the app, and overrides `get_db`
  with an **in-memory async SQLite** (`aiosqlite`) session. Keep that import
  order — the `os.environ.setdefault(...)` must stay above the `app.*` imports. The
  session factory uses `StaticPool` so the in-memory schema (created via
  `Base.metadata.create_all`) persists for all database-dependent tests.
- **SQLite foreign keys are ON.** The engine registers a `connect` listener
  that executes `PRAGMA foreign_keys=ON`; without it SQLite silently ignores
  every `ON DELETE CASCADE` and FK constraint. Keep the listener when touching
  the fixture, and do not assume a cascade test proves anything unless the
  pragma test (`tests/modules/documents/test_model.py`) passes.
- Fixtures live in the **root `tests/conftest.py`**: `client` (httpx
  `AsyncClient` bound via `ASGITransport`), `app` (the FastAPI app with
  dependency overrides), `session_factory` (async SQLite sessionmaker),
  `fake_embeddings`, `failing_embeddings`, `fake_llm`, and `failing_llm`. A
  subdir may add its own `conftest.py` for local fixtures.
- **Embeddings never hit the network in tests.** `fake_embeddings` is a
  deterministic bag-of-tokens vector; `tests/conftest.py` overrides
  `get_embedding_provider` and `get_session_factory`, so upload background
  tasks use the same in-memory SQLite and the fake provider. The real Gemini
  client is tested with `httpx.MockTransport` in
  `tests/modules/retrieval/test_embeddings.py`.
- **Background tasks run inside the test request.** Starlette executes
  `BackgroundTasks` before `AsyncClient.post` returns, so a document reaches
  `ready`/`failed` by the time the test reads it back — but the 201 response
  body was serialized earlier and therefore says `pending`. Assert the settled
  status through `GET /documents/{id}`.
- **Generation never hits the network in tests.** `fake_llm` records prompts and
  streams `["Grounded ", "answer ", "[1]"]` then `LLMFinish("stop")`;
  `fail_after=N` raises mid-stream, `deltas=[]` simulates an empty completion,
  and `failing_llm` fails before the first token (pass `status_code=429` for the
  rate-limit mapping). `tests/conftest.py` overrides `get_llm_provider`. The
  real client is tested with `httpx.MockTransport` in
  `tests/modules/chat/test_llm.py`.
- **SSE tests parse the raw body.** `AsyncClient.post` buffers the whole
  `text/event-stream`; `tests/modules/chat/test_router.py` splits on blank lines
  and asserts event names, token order, `done.cited`, and the persisted row.
  Because the endpoint pre-flights the first event, pre-token failures are
  ordinary JSON responses (429/503) while post-token failures end with
  `event: error` and no `done`.
- **Test layout mirrors the app:** `tests/api/`, `tests/core/`, `tests/db/`, and
  `tests/modules/<feature>/` for domain code (`tests/modules/auth/`,
  `tests/modules/users/`, `tests/modules/documents/`,
  `tests/modules/retrieval/`, `tests/modules/chat/`). **Every test subdirectory
  needs an `__init__.py`** — otherwise pytest's default import mode breaks when
  two files share a basename.
- Test names/fixtures use plain absolute imports (`from app.core.config import
Settings`); moving test files does not change imports.

---

## 9. Dev commands (run from `apps/api`)

```bash
uv sync                                  # install deps (incl. dev group)
uv run pytest                            # run tests
uv run ruff check app tests              # lint
uv run ruff format app tests             # format
uv run ruff format --check app tests     # format check
uv run fastapi dev app/main.py           # dev server (auto-detects `app` in main.py)
uv run alembic upgrade head              # apply migrations
```

`app/main.py` exposes `app = create_app()`, which the `fastapi` CLI auto-detects
from the given file path.

## 10. Tooling config

- **ruff:** `line-length = 100`, `target-version = "py313"`,
  `exclude = ["alembic/versions"]`. Run `ruff check .` (whole project) — it
  passes; the exclude keeps generated migrations out of lint.
- **Dependencies:** runtime in `[project].dependencies`; dev tools
  (pytest, pytest-asyncio, httpx, aiosqlite, ruff) in
  `[dependency-groups].dev`. Add via `uv add` / `uv add --dev`.

---

## 11. Adding a feature module (pattern)

Do **not** invent a new shape. Copy the `users` or `auth` module as a template. New
modules follow:
```text
app/modules/<feature>/
├── __init__.py
├── router.py     # APIRouter(prefix="/<feature>", tags=["<feature>"])
├── schemas.py    # Pydantic request/response models
├── models.py     # SQLAlchemy models (inherit app.db.base.Base)
├── service.py    # business logic (routes stay thin)
└── deps.py       # FastAPI dependencies (optional)
```

Then register it in `app/api/router.py` and add tests under `tests/modules/<feature>/` (with `__init__.py`).

---

## 12. Do not

- Do **not** add a `src/` layout or move the `app/` package.
- Do **not** restructure folders without an agreed design first.
- Do **not** commit `.env` or any real credential.
- Do **not** point tests at Neon; tests use SQLite.
- Do **not** pass raw `DATABASE_URL` to SQLAlchemy; use the normalized
  `settings.database_url` + `settings.database_connect_args`.
- Do **not** add domain tables before the milestone that owns them.
- Do **not** write bulk code without explaining it first.
- Do **not** persist or stream `delta.reasoning` (chain-of-thought); only
  `delta.content` is user-visible.
- Do **not** bind aware datetimes to `TimestampMixin` columns — they are
  `TIMESTAMP WITHOUT TIME ZONE` on Postgres (see §7).

---

## 13. Roadmap (each milestone gets its own design + plan)

1. ✅ **Foundation** (this milestone) — skeleton, config, db, `/health`,
   Alembic baseline, tests, README.
2. ✅ **Users + Auth** — users model + migration, password hashing (argon2),
   JWT (HS256), `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`,
   `GET /api/v1/users/me`, dependency injection, module layout. **Organizations were
   deliberately removed; the workspace is the tenant.**
3. ✅ **Workspaces, roles & invitations** — create workspace, membership, roles,
   invitations. The web UI (home, workspace detail, invite links, pending list,
   public accept) followed in a separate milestone plan. The API also gained the
   public `GET /api/v1/invitations/{token}` preview and a `token` field on the
   pending list so the web pages could render real state; preview and pending
   list both treat a past-`expires_at` invitation as expired.
4. ✅ **Documents** — `POST`/`GET`/`DELETE` under
   `/api/v1/workspaces/{workspace_id}/documents`, multipart txt/md/pdf upload,
   text extraction stored in Postgres (bytes discarded), `?mine=true`, and
   workspace-scoped permissions (`require_workspace_member`; uploader or
   creator/admin may delete). Limits: 5 MB, 500 PDF pages, 1,000,000 stored
   characters. No web UI yet. The 5 MB declared-length cap is enforced in
   `documents/middleware.py` before multipart parsing; the handler reads at
   most cap+1 bytes so a chunked body cannot be loaded into memory in full.
5. ✅ **Retrieval** — offset-preserving chunking, Gemini
   `gemini-embedding-001` at 768 dimensions (`RETRIEVAL_DOCUMENT` for chunks,
   `RETRIEVAL_QUERY` for queries, manual L2 normalisation), pgvector storage in
   the same Neon database, background indexing on upload with
   `pending|indexing|ready|failed` status, `POST .../documents/{id}/reindex`,
   `POST /api/v1/workspaces/{workspace_id}/search`, and
   `python -m app.modules.retrieval.backfill` for pre-existing documents. No
   chat/answer generation and no web UI yet.
6. ✅ **Chat (RAG)** — `POST /api/v1/workspaces/{workspace_id}/conversations`
   (create), `GET` (author's list, newest first), `GET/DELETE /{id}`, and
   `POST /{id}/messages` streaming SSE (`sources` → `token`* → `done`). Groq's
   OpenAI-compatible Chat Completions API over `httpx` (no SDK, no new
   dependency), retrieval reused from Milestone 5, grounded system prompt with
   `[n]` citations, fixed refusal when the workspace has no chunks, and
   citation snapshots on the assistant row. Failures: 429/503 before the first
   token, terminal `error` plus partial persistence afterwards. No web UI yet.

**Next up: web documents + chat.** Upload/list documents, then a workspace chat
page that consumes this SSE contract, renders `sources`, and makes `[n]` markers
clickable. That milestone owns the web streaming proxy and the chat route; the
API side is complete.

---

## 14. Pointers

- Design of record: `docs/superpowers/specs/2026-10-14-api-foundation-design.md`
- Task plan: `docs/superpowers/plans/2026-10-14-api-foundation.md`
- Milestone 3 API design:
  `docs/superpowers/specs/2026-10-19-workspaces-roles-invitations-design.md`
- Milestone 3 web design:
  `docs/superpowers/specs/2026-10-27-workspaces-invitations-web-design.md`
- Milestone 3 web plan:
  `docs/superpowers/plans/2026-10-27-workspaces-invitations-web.md`
- Milestone 4 documents design:
  `docs/superpowers/specs/2026-10-27-documents-design.md`
- Milestone 4 documents plan:
  `docs/superpowers/plans/2026-10-27-documents.md`
- Milestone 5 retrieval design:
  `docs/superpowers/specs/2026-11-02-retrieval-design.md`
- Milestone 5 retrieval plan:
  `docs/superpowers/plans/2026-11-02-retrieval.md`
- Milestone 6 chat design:
  `docs/superpowers/specs/2026-11-04-chat-rag-design.md`
- Milestone 6 chat plan:
  `docs/superpowers/plans/2026-11-04-chat-rag.md`
- Web project notes: `apps/web/AGENTS.md`
- Human-facing setup/run notes: `apps/api/README.md`
- Deployment runbook (Render + Vercel + Neon production branch):
  `docs/deployment.md`
