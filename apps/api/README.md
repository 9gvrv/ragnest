# Ragnest API

Ragnest API is a FastAPI backend foundation built with Python 3.13, providing a clean, modular structure for future application features.

### Features

- **Configuration:** Environment-based settings with Pydantic Settings and Neon PostgreSQL URL normalization; auth settings include `SECRET_KEY` and `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Database:** Asynchronous SQLAlchemy 2.0 integration with connection pooling, model registration via `app.db.models`, and reusable session management.
- **Health Check:** Database-backed `GET /health` endpoint with connectivity status.
- **Auth:** Passwords hashed with `pwdlib[argon2]`; access tokens signed with `PyJWT` (HS256). Endpoints: `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`, `GET /api/v1/users/me`. Token verification via `HTTPBearer` and the `get_current_user` dependency.
- **Migrations:** Alembic configured with initial baseline and the `users` table migration.
- **Logging:** Centralized application logging configuration.
- **Testing:** Async API and database tests using pytest, HTTPX, and in-memory SQLite with `StaticPool`.
- **Code Quality:** Ruff linting and formatting.

### Tech Stack

Python 3.13 · FastAPI · Pydantic v2 · SQLAlchemy · asyncpg · PostgreSQL (Neon) · Alembic · pytest · uv

### Getting Started

```bash
cd apps/api
uv sync
cp .env.example .env
```

Configure `DATABASE_URL`, `SECRET_KEY`, and optionally `ACCESS_TOKEN_EXPIRE_MINUTES` in `.env`. Generate `SECRET_KEY` with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`ACCESS_TOKEN_EXPIRE_MINUTES` defaults to `30`.

```bash
uv run fastapi dev app/main.py
```

### Development

```bash
# Run tests
uv run pytest

# Check linting
uv run ruff check app tests

# Check formatting
uv run ruff format --check app tests

# Apply database migrations
uv run alembic upgrade head
```

Tests use in-memory SQLite and do not connect to Neon. The SQLite engine uses `StaticPool` so the schema persists across test database sessions.

**Scope:** Infrastructure foundation plus users + auth. Workspaces/roles/invitations, documents, retrieval, and chat are planned for subsequent milestones.
