# AGENTS.md — Ragnest (monorepo)

Ragnest is a multi-tenant RAG SaaS: users sign up, create workspaces, upload
documents (txt/pdf/md), and chat with them; answers ground only in that
workspace's documents with citations. **The workspace is the tenant** — there
are no organizations. (The root `README.md` predates this decision and is
stale; trust this file and the app AGENTS.md files.)

## Read before touching code

- `apps/api/AGENTS.md` — API project law: locked structure, design decisions,
  Neon/Postgres traps, migration and testing rules.
- `apps/web/AGENTS.md` — web project law: route/proxy patterns, cookie + 401
  rules, design tokens, Next.js 16 quirks.

Both are mandatory reading for any session that edits code. The shared
`.opencode/opencode.jsonc` force-loads them for OpenCode sessions, but read
them outright in any other harness.

## How we work (applies to both apps)

- **The human writes the code.** The agent explains, reviews, and answers
  questions — a mentor, not a code generator. The agent writes a file only
  for pure boilerplate, saying so first, then explaining it line by line.
- **One small task at a time**; verify together, then move on. Small, frequent
  commits so history tells the story.
- **Design before code for every milestone**: a design doc and task-by-task
  plan in `docs/superpowers/specs/` and `docs/superpowers/plans/` before any
  implementation. **No unrequested refactors** — propose, agree, then move.
- If you are an agent: default to explaining and asking, not editing. When in
  doubt, stop and ask.

## Monorepo layout

Each app is its own project with its own manifest and `.env` — run all
commands from inside the app directory.

| Directory | Stack | Status |
| --- | --- | --- |
| `apps/api/` | FastAPI + async SQLAlchemy (uv, ruff, pytest, Alembic) | Milestones 1–3 done |
| `apps/web/` | Next.js 16 App Router + pnpm + Tailwind 4 | Auth + workspaces/invitations UI done |
| `docs/superpowers/` | Design specs & task plans per milestone | |
| `docs/progress.md` | Chronological work log (entries before 2026-10-14 describe a superseded `src/` layout) | |

**Next up: Milestone 4 (Documents).** Design of record:
`docs/superpowers/specs/2026-10-27-documents-design.md`, plan:
`docs/superpowers/plans/2026-10-27-documents.md`.

## Commands that matter

API (from `apps/api/`):

```bash
uv run pytest                     # tests — in-memory SQLite, never Neon
uv run ruff check app tests       # lint (also: ruff format / format --check)
uv run alembic upgrade head       # migrations — runs against REAL Neon
uv run fastapi dev app/main.py    # dev server on :8000
```

Web (from `apps/web/` — no test framework exists; this is the verification):

```bash
pnpm lint && pnpm exec tsc --noEmit && pnpm build   # must be clean at every commit
pnpm exec next typegen        # after adding routes (regenerates PageProps etc.)
```

- Web expects the API on `http://127.0.0.1:8000` (`API_URL`, default `:8000`).
  The browser never calls the API directly — reads go through server
  components, mutations through `app/api/**` route-handler proxies.
- Never commit or print `apps/api/.env` (real Neon + JWT secrets); never pass
  the raw `DATABASE_URL` to SQLAlchemy — see the Neon normalization traps in
  `apps/api/AGENTS.md` §5.
- Secrets/config: `.env` files are gitignored; the committed shape lives in
  `.env.example` in each app.
