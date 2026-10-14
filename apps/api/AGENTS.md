# AGENTS.md — Ragnest API

> **Read this before touching code.** It records the decisions, structure, and
> traps we cannot afford to rediscover. It is not a tutorial and not a duplicate
> of `README.md`.
>
> **Last updated:** 2026-10-14 (Milestone 1 — foundation — complete)

---

## 1. What this project is

**Ragnest** is a multi-tenant RAG SaaS: an organization signs up, creates a
workspace, uploads documents (txt/pdf/md), and chats with them. Answers must be
grounded only in that workspace's documents, with citations to the source file.

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
  *before* anything moves.
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
  router, schemas, models, and service. New features copy the shape of an
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
│   │   └── session.py       # engine, SessionLocal, get_db, dispose_engine
│   └── api/
│       ├── __init__.py
│       ├── router.py        # api_router aggregate — includes every feature router
│       └── health.py        # GET /health
└── tests/                   # mirrors the app tree
    ├── conftest.py          # shared fixtures: client, session_factory
    ├── test_app.py
    ├── api/test_health.py
    ├── core/test_config.py, core/test_logging.py
    └── db/test_base.py, db/test_session.py
```

**`app/modules/` does not exist yet.** It is created with the first domain
feature (auth). That is *growth, not a restructure* — no existing file moves.

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
  `APP_NAME`, `LOG_LEVEL`, `DATABASE_URL`.
- Settings fields: `APP_NAME` (default `"Ragnest API"`), `LOG_LEVEL` (default
  `"INFO"`), `DATABASE_URL` (**required** — missing raises `ValidationError`).
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
- **Known wart:** there are currently **two empty baseline revisions**
  (`736e318369b1 -> a058018dc98a`; both `pass`). The design intended one. Neon is
  stamped at `a058018dc98a`. Squashing is cosmetic and optional.
- **No domain tables yet.** The first real table (users / organizations) arrives
  with the auth milestone.
- Apply migrations with `uv run alembic upgrade head`; inspect with
  `uv run alembic current` / `uv run alembic history`.

---

## 8. Testing

- Runner: **pytest** with `pytest-asyncio` in `asyncio_mode = "auto"` (async
  tests need no decorator). Config lives in `pyproject.toml`
  (`testpaths = ["tests"]`).
- **Tests never touch Neon.** `tests/conftest.py` sets a dummy `DATABASE_URL`
  *before* importing any `app.*` module, builds the app, and overrides `get_db`
  with an **in-memory async SQLite** (`aiosqlite`) session. Keep that import
  order — the `os.environ.setdefault(...)` must stay above the `app.*` imports.
- Fixtures live in the **root `tests/conftest.py`**: `client` (httpx
  `AsyncClient` bound via `ASGITransport`) and `session_factory` (async SQLite
  sessionmaker). A subdir may add its own `conftest.py` for local fixtures.
- **Test layout mirrors the app:** `tests/api/`, `tests/core/`, `tests/db/`, and
  later `tests/modules/<feature>/`. **Every test subdirectory needs an
  `__init__.py`** — otherwise pytest's default import mode breaks when two files
  share a basename.
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

## 11. Adding a feature module (the pattern, when auth arrives)

Do **not** invent a new shape. Copy this:

```
app/modules/<feature>/
├── __init__.py
├── router.py     # APIRouter(prefix="/<feature>", tags=["<feature>"])
├── schemas.py    # Pydantic request/response models
├── models.py     # SQLAlchemy models (inherit app.db.base.Base)
└── service.py    # business logic (routes stay thin)
```

Then register it in `app/api/router.py`:

```python
from app.modules.auth import router as auth_router
api_router.include_router(auth_router.router)
```

Tests go in `tests/modules/<feature>/` (with `__init__.py`).

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

---

## 13. Roadmap (each milestone gets its own design + plan)

1. ✅ **Foundation** (this milestone) — skeleton, config, db, `/health`,
   Alembic baseline, tests, README.
2. **Auth** — users + organizations, signup/login, JWT. First real models,
   migration, and the first `app/modules/` feature.
3. **Workspaces & membership** — create workspace, invite members.
4. **Documents** — upload txt/pdf/md, store, extract text.
5. **Retrieval** — chunk, embed, store vectors, search scoped to a workspace.
6. **Chat (RAG)** — ask questions, stream grounded answers with citations.

**Next up: Milestone 2 (auth + workspaces/orgs).** Design precedes code.

---

## 14. Pointers

- Design of record: `docs/superpowers/specs/2026-10-14-api-foundation-design.md`
- Task plan: `docs/superpowers/plans/2026-10-14-api-foundation.md`
- Human-facing setup/run notes: `apps/api/README.md`
