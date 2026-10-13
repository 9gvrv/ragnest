# Ragnest API — Foundation (Clean Skeleton) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This project runs in mentor mode:** the human writes the code; the mentor explains, reviews, and only writes files when a step says so. Steps are still written as concrete, verifiable actions.

**Goal:** Stand up a small, well-understood FastAPI foundation — config, app factory, logging, async database wiring, a DB-backed `/health`, Alembic, and tests — with no domain features.

**Architecture:** One `app/` package. `app/core` and `app/db` are shared infrastructure; `app/api` is the HTTP layer (aggregate router + infrastructure routes). An app factory (`create_app()`) wires logging, lifespan, and routers. Postgres is reached through a single async SQLAlchemy engine, with Neon's URL and pooler quirks normalized in settings.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0 async + asyncpg, Alembic, pytest + pytest-asyncio + httpx + aiosqlite, ruff, uv.

**Spec:** `docs/superpowers/specs/2026-10-14-api-foundation-design.md`

## Global Constraints

- Python `>=3.13`; all dependencies managed with `uv` (run from `apps/api`).
- **No `src/` layout.** One top-level `app/` package at `apps/api/app/`.
- Shared infra lives in `app/core` and `app/db`; the HTTP layer lives in `app/api`. `app/modules/` does **not** exist yet (arrives with auth).
- No domain tables and no domain migrations in this milestone. Alembic is wired and gets one empty baseline revision only.
- `GET /health` lives at the root (unversioned). Domain routes (later) go under `/api/v1`.
- Neon URL handling: rewrite scheme to `postgresql+asyncpg://`, strip `sslmode`/`channel_binding`/`sslnegotiation`, pass SSL + `statement_cache_size=0` via connect args.
- Tests must not touch Neon; they run against in-memory async SQLite.
- Every task ends with `ruff check app tests` + `ruff format --check app tests` clean and a commit.

## Review Focus

Failure modes the spec implies but that no task fully pins down in tests, most likely to bite first:

1. **DB unreachable at request time** — `/health` should return `503 {"status":"error","database":"unreachable"}`, not a 500 or a hung request. (Test in Task 7.)
2. **Missing/malformed `DATABASE_URL`** — the app should fail fast with a clear validation error, not an obscure `KeyError` at import. (Test in Task 3.)
3. **Local (non-Neon) URL without `sslmode`** — must connect without demanding SSL. (Test in Task 3.)
4. **Neon pooled endpoint** — asyncpg's prepared-statement cache must be disabled, or `SELECT 1` and migrations fail against PgBouncer. (Test in Task 3 for the args; live check in Task 8.)
5. **Two clients hitting the app at once** — a shared engine/session factory must be safe; per-request sessions must be isolated and closed. (Partly covered by Task 5's `get_db` test; concurrency is left to the live smoke test.)

---

### Task 1: Reset to a clean baseline

**Files:**
- Delete: `apps/api/main.py`, `apps/api/config.py`, `apps/api/app/` (the leftover tutorial scaffold)
- Keep: `apps/api/pyproject.toml`, `apps/api/uv.lock`, `apps/api/.env`, `apps/api/.env.example`, `apps/api/.python-version`, `apps/api/README.md`

**Interfaces:**
- Consumes: nothing
- Produces: a clean working tree on `main`; no `app/` package yet.

- [x] **Step 1: Confirm what is on disk**

Run: `find apps/api -not -path '*/.venv/*' -not -path '*/__pycache__/*' | sort`
Expected: shows `apps/api/main.py`, `apps/api/config.py`, and an `apps/api/app/` tree with no real code.

- [x] **Step 2: Remove the leftover scaffold**

```bash
rm -rf apps/api/app apps/api/main.py apps/api/config.py
```

- [x] **Step 3: Stage and review the full change**

```bash
git add -A
git status
```
Expected: the old `src/`, `migrations/`, `tests/`, `alembic.ini` are recorded as deleted; the scaffold is gone. `.env` is *not* listed (it is gitignored).

- [x] **Step 4: Commit**

```bash
git commit -m "chore(api): reset to a clean baseline for a rebuild"
```

- [x] **Step 5: Verify**

Run: `git status`
Expected: `nothing to commit, working tree clean`.

---

### Task 2: Project setup — dependencies, tooling, env example

**Files:**
- Modify: `apps/api/pyproject.toml` (dev deps, ruff config, pytest config)
- Modify: `apps/api/.env.example`
- Create: `apps/api/app/__init__.py`, `apps/api/tests/__init__.py`

**Interfaces:**
- Consumes: Task 1's clean tree
- Produces: `uv run pytest`, `uv run ruff`, and `uv run fastapi` all work; `pyproject.toml` has `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`) and `[tool.ruff]` (`line-length = 100`, `target-version = "py313"`, `exclude = ["migrations/versions"]`).

- [x] **Step 1: Add dev dependencies**

Run (from `apps/api`): `uv add --dev pytest pytest-asyncio httpx aiosqlite ruff`
Expected: `pyproject.toml` gains a `[dependency-groups]` (or `[tool.uv]` dev group) and `uv.lock` updates.

- [x] **Step 2: Add tool configuration to `apps/api/pyproject.toml`**

Add (as my/mentor's call — pure config, nothing to learn):

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py313"
exclude = ["migrations/versions"]
```

- [x] **Step 3: Write `apps/api/.env.example`**

```
APP_NAME="Ragnest API"
LOG_LEVEL=INFO
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

- [x] **Step 4: Create the package markers**

```bash
mkdir -p apps/api/app apps/api/tests
touch apps/api/app/__init__.py apps/api/tests/__init__.py
```

- [x] **Step 5: Verify the toolchain runs**

```bash
uv run ruff check app tests
uv run pytest
```
Expected: ruff reports no issues; pytest reports `no tests ran` (exit code 5 is fine here).

- [x] **Step 6: Commit**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/.env.example apps/api/app/__init__.py apps/api/tests/__init__.py
git commit -m "chore(api): add dev dependencies and tooling config"
```

---

### Task 3: Settings

**Files:**
- Create: `apps/api/app/core/__init__.py`, `apps/api/app/core/config.py`
- Test: `apps/api/tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Settings` (pydantic-settings, reads `apps/api/.env` resolved from the file location) with fields `APP_NAME: str = "Ragnest API"`, `LOG_LEVEL: str = "INFO"`, `DATABASE_URL: str`, and properties `database_url -> str` and `database_connect_args -> dict`; a module-level `settings = Settings()`.

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError
from urllib.parse import parse_qs, urlparse

from app.core.config import Settings

NEON = (
    "postgresql://u:p@host/db"
    "?sslmode=require&channel_binding=require&application_name=ragnest"
)


def test_rewrites_scheme_and_strips_libpq_only_params():
    s = Settings(DATABASE_URL=NEON)
    parsed = urlparse(s.database_url)
    assert parsed.scheme == "postgresql+asyncpg"
    params = parse_qs(parsed.query)
    assert "sslmode" not in params
    assert "channel_binding" not in params
    assert params.get("application_name") == ["ragnest"]


def test_connect_args_enable_ssl_and_disable_statement_cache():
    s = Settings(DATABASE_URL=NEON)
    assert s.database_connect_args == {"statement_cache_size": 0, "ssl": True}


def test_local_url_does_not_force_ssl():
    s = Settings(DATABASE_URL="postgresql://u:p@localhost:5432/ragnest")
    assert urlparse(s.database_url).scheme == "postgresql+asyncpg"
    assert "ssl" not in s.database_connect_args
    assert s.database_connect_args["statement_cache_size"] == 0


def test_missing_database_url_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.config'`.

- [ ] **Step 3: Implement `apps/api/app/core/config.py`**

Signature:

```python
class Settings(BaseSettings):
    APP_NAME: str = "Ragnest API"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )

    @property
    def database_url(self) -> str: ...

    @property
    def database_connect_args(self) -> dict: ...

settings = Settings()
```

Approach: parse `DATABASE_URL` with `urllib.parse`; in `database_url`, replace the scheme with `postgresql+asyncpg`, drop `sslmode`/`channel_binding`/`sslnegotiation`, and keep everything else. In `database_connect_args`, always include `statement_cache_size=0`, and add `ssl=True` when the original `sslmode` was `require`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check app tests && uv run ruff format --check app tests
git add apps/api/app/core apps/api/tests/test_config.py
git commit -m "feat(api): add settings with Neon URL normalization"
```

---

### Task 4: Logging

**Files:**
- Create: `apps/api/app/core/logging.py`
- Test: `apps/api/tests/test_logging.py`

**Interfaces:**
- Consumes: `settings.LOG_LEVEL` (Task 3)
- Produces: `configure_logging(level: str = "INFO") -> None` that configures the root logger once (idempotent).

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_logging.py`:

```python
import logging

from app.core.logging import configure_logging


def test_configure_logging_sets_root_level():
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_is_idempotent():
    configure_logging("INFO")
    configure_logging("INFO")  # must not raise or duplicate handlers
    assert logging.getLogger().level == logging.INFO
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_logging.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.logging'`.

- [ ] **Step 3: Implement `apps/api/app/core/logging.py`**

Signature: `def configure_logging(level: str = "INFO") -> None: ...`
Approach: `logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True)`. `force=True` resets handlers on each call, which makes it idempotent.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_logging.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check app tests && uv run ruff format --check app tests
git add apps/api/app/core/logging.py apps/api/tests/test_logging.py
git commit -m "feat(api): add logging setup"
```

---

### Task 5: Database core

**Files:**
- Create: `apps/api/app/db/__init__.py`, `apps/api/app/db/base.py`, `apps/api/app/db/session.py`
- Test: `apps/api/tests/test_db_base.py`, `apps/api/tests/test_db_session.py`

**Interfaces:**
- Consumes: `settings.database_url`, `settings.database_connect_args` (Task 3)
- Produces:
  - `app.db.base.Base` — `DeclarativeBase` with a constraint naming convention; `TimestampMixin` with `created_at`/`updated_at` (`Mapped[datetime]`, non-null, server default `now()`).
  - `app.db.session.engine` (`AsyncEngine`, `pool_pre_ping=True`, `pool_recycle=300`), `SessionLocal` (`async_sessionmaker`, `expire_on_commit=False`), `get_db() -> AsyncIterator[AsyncSession]`, `dispose_engine() -> None`.

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/test_db_base.py`:

```python
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Parent(Base):
    __tablename__ = "parent"
    id: Mapped[int] = mapped_column(primary_key=True)


class Child(Base, TimestampMixin):
    __tablename__ = "child"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parent.id"))
    name: Mapped[str] = mapped_column(index=True)
    __table_args__ = (UniqueConstraint("parent_id", "name"),)


def test_timestamp_mixin_columns_exist():
    cols = Base.metadata.tables["child"].columns
    assert "created_at" in cols and not cols["created_at"].nullable
    assert "updated_at" in cols and not cols["updated_at"].nullable


def test_constraint_naming_convention_is_applied():
    table = Base.metadata.tables["child"]
    assert any(c.name.startswith("fk_") for c in table.foreign_key_constraints)
    assert any(c.name.startswith("uq_") for c in table.constraints)
    assert any(i.name.startswith("ix_") for i in table.indexes)
```

`apps/api/tests/test_db_session.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import session as db_session


def test_engine_uses_asyncpg_driver():
    assert db_session.engine.url.drivername == "postgresql+asyncpg"


async def test_get_db_yields_and_closes_a_session(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db_session, "SessionLocal", async_sessionmaker(engine, expire_on_commit=False))

    yielded = None
    async for s in db_session.get_db():
        yielded = s
        assert isinstance(s, AsyncSession)
    # generator finished -> context manager exited -> session closed
    assert yielded is not None
    await engine.dispose()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_db_base.py tests/test_db_session.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Implement `apps/api/app/db/base.py`**

```python
class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: Implement `apps/api/app/db/session.py`**

```python
engine = create_async_engine(
    settings.database_url,
    connect_args=settings.database_connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session

async def dispose_engine() -> None:
    await engine.dispose()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_db_base.py tests/test_db_session.py -v`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check app tests && uv run ruff format --check app tests
git add apps/api/app/db apps/api/tests/test_db_base.py apps/api/tests/test_db_session.py
git commit -m "feat(api): add async database core (base + session)"
```

---

### Task 6: App factory and test harness

**Files:**
- Create: `apps/api/app/api/__init__.py`, `apps/api/app/api/router.py`, `apps/api/app/main.py`
- Create: `apps/api/tests/conftest.py`
- Test: `apps/api/tests/test_app.py`

**Interfaces:**
- Consumes: `configure_logging` (Task 4), `dispose_engine` (Task 5), `settings` (Task 3)
- Produces:
  - `app.api.router.api_router` (`APIRouter`, currently empty; health is added in Task 7).
  - `app.main.create_app() -> FastAPI` — sets title from `settings.APP_NAME`, configures logging, wires a lifespan that disposes the engine on shutdown, and mounts `api_router`; plus `app = create_app()`.
  - `tests/conftest.py` fixture `client` (async `httpx.AsyncClient` bound to the app via `ASGITransport`), and fixture `session_factory` (async SQLite sessionmaker).

- [ ] **Step 1: Write `apps/api/tests/conftest.py`**

```python
import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ragnest"
)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import create_app


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

- [ ] **Step 2: Write the failing test**

`apps/api/tests/test_app.py`:

```python
async def test_app_boots_and_serves_openapi(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    assert "openapi" in resp.json()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 4: Implement the HTTP layer and factory**

`apps/api/app/api/__init__.py`: empty.

`apps/api/app/api/router.py`:

```python
from fastapi import APIRouter

api_router = APIRouter()
```

`apps/api/app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine


def create_app() -> FastAPI:
    configure_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await dispose_engine()

    app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
    app.include_router(api_router)
    return app


app = create_app()
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check app tests && uv run ruff format --check app tests
git add apps/api/app/api apps/api/app/main.py apps/api/tests/conftest.py apps/api/tests/test_app.py
git commit -m "feat(api): add app factory, HTTP layer, and test harness"
```

---

### Task 7: Health endpoint (DB-backed)

**Files:**
- Create: `apps/api/app/api/health.py`
- Modify: `apps/api/app/api/router.py`
- Modify: `apps/api/tests/conftest.py` (override `get_db` in the `client` fixture)
- Test: `apps/api/tests/test_health.py`

**Interfaces:**
- Consumes: `get_db` (Task 5), `api_router` (Task 6)
- Produces: `app.api.health.router` exposing `GET /health` →
  - `200 {"status": "ok", "database": "connected"}` on success,
  - `503 {"status": "error", "database": "unreachable"}` if the query fails.

- [ ] **Step 1: Extend the `client` fixture to override `get_db` with SQLite**

In `apps/api/tests/conftest.py`, import `get_db` and change `client` to accept `session_factory`:

```python
from app.db.session import get_db


@pytest_asyncio.fixture
async def client(session_factory):
    app = create_app()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

- [ ] **Step 2: Write the failing tests**

`apps/api/tests/test_health.py`:

```python
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import create_app


async def test_health_reports_connected(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "connected"}


async def test_health_reports_503_when_database_fails():
    class BrokenSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("database is down")

    app = create_app()

    async def broken_get_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/health")

    assert resp.status_code == 503
    assert resp.json() == {"status": "error", "database": "unreachable"}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_health.py -v`
Expected: FAIL — `GET /health` returns 404.

- [ ] **Step 4: Implement `apps/api/app/api/health.py` and register it**

`apps/api/app/api/health.py`:

```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_db)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unreachable"},
        )
    return {"status": "ok", "database": "connected"}
```

In `apps/api/app/api/router.py`:

```python
from fastapi import APIRouter

from app.api import health

api_router = APIRouter()
api_router.include_router(health.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest -v`
Expected: PASS (all tests across the suite).

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check app tests && uv run ruff format --check app tests
git add apps/api/app/api/health.py apps/api/app/api/router.py apps/api/tests/conftest.py apps/api/tests/test_health.py
git commit -m "feat(api): add DB-backed health endpoint"
```

---

### Task 8: Alembic wiring and baseline migration

**Files:**
- Create: `apps/api/alembic.ini`, `apps/api/migrations/env.py`, `apps/api/migrations/script.py.mako`, `apps/api/migrations/versions/` (dir with `.gitkeep`)
- Generated: `apps/api/migrations/versions/<hash>_baseline.py`

**Interfaces:**
- Consumes: `settings.database_url`, `settings.database_connect_args` (Task 3), `Base.metadata` (Task 5)
- Produces: `uv run alembic upgrade head` creates `alembic_version` and stamps the empty baseline revision; `uv run alembic check` reports `No new upgrade operations detected`.

- [ ] **Step 1: Create `apps/api/alembic.ini`**

```ini
[alembic]
script_location = %(here)s/migrations
prepend_sys_path = .
# sqlalchemy.url is set programmatically in migrations/env.py from app settings

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create `apps/api/migrations/env.py`**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=settings.database_connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Create `apps/api/migrations/script.py.mako` and the versions dir**

Use the standard Alembic template (as my/mentor's call — generated boilerplate):

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

```bash
mkdir -p apps/api/migrations/versions
touch apps/api/migrations/versions/.gitkeep
```

- [ ] **Step 4: Generate the empty baseline revision**

Run (from `apps/api`): `uv run alembic revision -m "baseline"`
Expected: creates `migrations/versions/<hash>_baseline.py` with empty `upgrade()`/`downgrade()` bodies. Do **not** pass `--autogenerate`.

- [ ] **Step 5: Apply it to Neon and verify**

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```
Expected: `upgrade` creates `alembic_version`; `current` shows the baseline hash; `check` prints `No new upgrade operations detected`.

- [ ] **Step 6: Confirm in the database**

```bash
.venv/bin/python - <<'PY'
import asyncio, urllib.parse, asyncpg
dsn = None
for line in open(".env"):
    if line.startswith("DATABASE_URL="):
        dsn = line.strip().split("=", 1)[1]
u = urllib.parse.urlparse(dsn)
q = urllib.parse.parse_qs(u.query)
for k in ("sslmode", "channel_binding", "sslnegotiation"):
    q.pop(k, None)
clean = urllib.parse.urlunparse(u._replace(query=urllib.parse.urlencode(q, doseq=True)))
async def main():
    c = await asyncpg.connect(clean, ssl=True)
    print("tables:", [r["tablename"] for r in await c.fetch(
        "select tablename from pg_tables where schemaname='public' order by tablename")])
    print("version:", [r["version_num"] for r in await c.fetch("select version_num from alembic_version")])
    await c.close()
asyncio.run(main())
PY
```
Expected: `tables: ['alembic_version']`, `version:` one hash.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check app tests && uv run ruff format --check app tests
git add apps/api/alembic.ini apps/api/migrations
git commit -m "feat(api): wire Alembic with an empty baseline revision"
```

---

### Task 9: README

**Files:**
- Modify: `apps/api/README.md`

**Interfaces:**
- Consumes: everything above
- Produces: documentation for setup, running, migrating, testing, and linting.

- [ ] **Step 1: Write `apps/api/README.md`**

Include: purpose; prerequisites (Python 3.13, uv); setup (`uv sync`, copy `.env.example` → `.env`, fill `DATABASE_URL`); run (`uv run fastapi dev app/main.py`); migrate (`uv run alembic upgrade head`); test (`uv run pytest`); lint (`uv run ruff check app tests`, `uv run ruff format --check app tests`); and a note that tests use in-memory SQLite and never touch Neon.

- [ ] **Step 2: Verify each documented command**

```bash
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest
uv run alembic current
```
Expected: all succeed; `pytest` green; `alembic current` shows the baseline.

- [ ] **Step 3: Commit**

```bash
git add apps/api/README.md
git commit -m "docs(api): document setup, run, migrate, and test"
```

---

## Final verification

- [ ] `uv run pytest` — all tests pass.
- [ ] `uv run ruff check app tests && uv run ruff format --check app tests` — clean.
- [ ] `uv run fastapi dev app/main.py` boots; `GET /health` returns `{"status":"ok","database":"connected"}` against Neon.
- [ ] `uv run alembic current` shows the baseline; `uv run alembic check` is clean.
- [ ] `git status` is clean; the log reads as small, self-explanatory commits.
