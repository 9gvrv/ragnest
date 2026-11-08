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

Both are mandatory reading for any session that edits code. The repo-root
`opencode.jsonc` force-loads them for OpenCode sessions, but read them
outright in any other harness.

## How we work (applies to both apps)

- **The agent writes the code; the human makes the decisions.** The human owns
  scope, trade-offs, and approvals. This is a learning project for AI-assisted
  development: the agent implements, the human learns by reviewing real code
  instead of typing it.
- **Explain while writing, not after.** Each non-obvious choice gets a sentence
  or two of "why" as it is made. No silent bulk edits, no unexplained
  abstractions. If the human cannot explain a line, the work is not finished.
- **Propose before deciding; proceed when it is mechanical.** New dependencies,
  structural moves, schema changes, and anything irreversible get a short
  options-plus-recommendation first. Clear work is simply executed.
- **One small task at a time**; verify together, then move on. Small, frequent
  commits so history tells the story. The agent may make commits; the human
  decides what merges.
- **Design before code for every milestone**: a design doc and task-by-task
  plan in `docs/superpowers/specs/` and `docs/superpowers/plans/` before any
  implementation. **No unrequested refactors** — propose, agree, then move.
- **Verify before claiming done.** Run the real command and report its output —
  tests, lint, types, build. "Should pass" is not a result.
- If you are an agent: ask when a decision is genuinely ambiguous, then act and
  report what changed and why.

## Monorepo layout

Each app is its own project with its own manifest and `.env` — run all
commands from inside the app directory.

| Directory | Stack | Status |
| --- | --- | --- |
| `apps/api/` | FastAPI + async SQLAlchemy (uv, ruff, pytest, Alembic) | Milestones 1–6 done |
| `apps/web/` | Next.js 16 App Router + pnpm + Tailwind 4 | Auth + workspaces/invitations + documents/chat UI done |
| `docs/superpowers/` | Design specs & task plans per milestone | |
| `docs/progress.md` | Chronological work log (entries before 2026-10-14 describe a superseded `src/` layout) | |

**Deployed.** The web app runs on Vercel, the API on Render's free web service,
and data lives on the Neon production branch (schema verified and stamped). The
runbook — env matrix, build/start commands, manual migration command, smoke
test, and the CI gate — is `docs/deployment.md`. `main` is gated: a branch
ruleset requires the `api` and `web` checks from `.github/workflows/ci.yml`
before a merge, and both hosts auto-deploy `main`, so a deploy only ever
carries tested code.

No milestone is scheduled. The API is complete through Milestone 6
(chat/RAG) and the web app covers auth, workspaces/invitations, documents, and
chat. Propose the next milestone with a design doc and plan before
implementation. Web documents + chat design:
`docs/superpowers/specs/2026-11-06-web-documents-chat-design.md`; plan:
`docs/superpowers/plans/2026-11-06-web-documents-chat.md`.

## Commands that matter

API (from `apps/api/`):

```bash
uv run pytest                     # tests — in-memory SQLite, never Neon
uv run ruff check app tests       # lint (also: ruff format / format --check)
uv run ty check app               # type check — app/ only
uv run alembic upgrade head       # migrations — runs against REAL Neon
uv run fastapi dev app/main.py    # dev server on :8000
```

Web (from `apps/web/` — no test framework exists; this is the verification, and
it must be clean at every commit):

```bash
pnpm lint && pnpm exec next typegen && pnpm exec tsc --noEmit && pnpm build
```

`next typegen` must run before `tsc` in a clean checkout: it writes
`PageProps`/`RouteContext`/`LayoutProps` into `.next/types`.

- Web expects the API on `http://127.0.0.1:8000` (`API_URL`, default `:8000`).
  The browser never calls the API directly — reads go through server
  components, mutations through `app/api/**` route-handler proxies.
- Never commit or print `apps/api/.env` (real Neon + JWT secrets); never pass
  the raw `DATABASE_URL` to SQLAlchemy — see the Neon normalization traps in
  `apps/api/AGENTS.md` §5.
- Secrets/config: `.env` files are gitignored; the committed shape lives in
  `.env.example` in each app.
