# Ragnest

Ragnest is a multi-tenant RAG SaaS. A user signs up, creates a workspace,
uploads documents (txt/pdf/md), and chats with them. Answers are grounded only
in that workspace's documents and cite the source file, and every workspace's
data is fully isolated from every other one's. **The workspace is the tenant**;
there are no organizations.

## Monorepo layout

The repo is split into two independent apps, each with its own manifest,
environment, and tooling:

| Path | What | Stack |
| --- | --- | --- |
| `apps/api/` | FastAPI backend: auth, users, workspaces, invitations | FastAPI, async SQLAlchemy 2.0, Alembic, Neon (Postgres), uv |
| `apps/web/` | Next.js frontend: browser for the API | Next.js 16 App Router, React 19, Tailwind 4, pnpm |
| `docs/superpowers/` | Design specs and task plans, one pair per milestone | |
| `docs/progress.md` | Chronological work log (entries older than 2026-10-14 describe a superseded `src/` layout) | |

## Status and roadmap

| # | Milestone | Status |
| --- | --- | --- |
| 1 | API foundation — app factory, config, `/health`, Alembic baseline, tests | Done |
| 2 | Users and auth — signup/login (Argon2 + HS256 JWT), `/users/me` | Done |
| 3 | Workspaces, roles and invitations — API plus the web UI (home, member management, invite links, public accept) | Done |
| 4 | Documents — upload txt/pdf/md, store, extract text | Designed, not built |
| 5 | Retrieval — chunk, embed, workspace-scoped vector search | Planned |
| 6 | Chat (RAG) — streaming answers with citations | Planned |

Design of record for milestone 4:
`docs/superpowers/specs/2026-10-27-documents-design.md` with plan
`docs/superpowers/plans/2026-10-27-documents.md`.

## Running the API

All commands run from `apps/api/`.

```bash
uv sync                            # install dependencies
uv run alembic upgrade head        # apply migrations to the configured database
uv run fastapi dev app/main.py     # dev server on http://127.0.0.1:8000
uv run pytest                      # tests — use in-memory SQLite, never Neon
uv run ruff check app tests        # lint (ruff format to format)
```

Configuration lives in `apps/api/.env` (gitignored):
`DATABASE_URL` (Neon Postgres), `SECRET_KEY` (JWT signing),
`ACCESS_TOKEN_EXPIRE_MINUTES`. See `apps/api/.env.example` for the shape.

## Running the web app

All commands run from `apps/web/`.

```bash
pnpm install
pnpm dev                           # dev server on http://localhost:3000
pnpm lint && pnpm exec tsc --noEmit && pnpm build
```

There is no web test framework; lint, types, and a clean build are the
verification. The API is expected on port 8000 (override with `API_URL`).
The browser never calls the API directly — the Next.js server forwards the
httpOnly session cookie, and mutations go through `apps/web/app/api/**`
route handlers.

## Conventions and docs

- Anyone editing code should read `apps/api/AGENTS.md` and
  `apps/web/AGENTS.md` first — they record the project's structure, design
  decisions, and traps, and a root `AGENTS.md` gives the monorepo overview.
- Workflow: one small task at a time, design doc and task plan before each
  new milestone, small frequent commits.
- Never commit real credentials; `.env` files are gitignored per app.
