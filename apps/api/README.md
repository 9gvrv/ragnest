# Ragnest API

Ragnest API is a FastAPI backend foundation built with Python 3.13, providing a clean, modular structure for future application features.

### Features

- **Configuration:** Environment-based settings with Pydantic Settings and Neon PostgreSQL URL normalization.
- **Database:** Asynchronous SQLAlchemy 2.0 integration with connection pooling and reusable session management.
- **Health Check:** Database-backed `GET /health` endpoint with connectivity status.
- **Migrations:** Alembic configured with an initial baseline migration.
- **Logging:** Centralized application logging configuration.
- **Testing:** Async API and database tests using pytest, HTTPX, and in-memory SQLite.
- **Code Quality:** Ruff linting and formatting.

### Tech Stack

Python 3.13 · FastAPI · Pydantic v2 · SQLAlchemy · asyncpg · PostgreSQL (Neon) · Alembic · pytest · uv

### Getting Started

```bash
cd apps/api
uv sync
cp .env.example .env
```

Configure `DATABASE_URL` in `.env`, then start the development server:

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

Tests use in-memory SQLite and do not connect to Neon.

**Scope:** This is an infrastructure-only foundation. Domain features, authentication, and application-specific database models will be added in subsequent development stages.
