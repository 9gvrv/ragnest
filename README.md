# Ragnest

Ragnest is a multi-tenant RAG SaaS. A user signs up, creates a workspace,
uploads documents (txt, md, pdf), and asks questions about them. Answers are
grounded only in that workspace's documents, cite the source file, and never
cross workspace boundaries. **The workspace is the tenant** — there are no
organizations.

Live: <https://ragnest.vercel.app>

## How it works

1. **Ingest.** Uploading a document extracts its text into Postgres (the bytes
   are discarded). A background job splits the text into overlapping chunks,
   embeds them with Gemini, and stores the vectors in pgvector.
2. **Retrieve.** A question is embedded with the same model and matched against
   the workspace's chunks by cosine similarity.
3. **Answer.** The top chunks go into a grounded prompt sent to Groq. The answer
   streams to the browser over SSE and is stored with a snapshot of its
   citations.
4. **Isolate.** Every domain read and write is scoped to workspace membership,
   and conversations are private to their author. The browser never calls the
   API directly: Next.js server components read, route handlers proxy
   mutations, and the JWT lives only in an httpOnly cookie.

## Implemented

- Accounts — signup, login, and `/account`; Argon2 passwords and HS256 JWT.
- Workspaces — roles (creator/admin/member), invitations, and member management.
- Documents — upload, list, and delete txt/md/pdf; text extraction and limits.
- Retrieval — chunking, Gemini embeddings, pgvector search, indexing status,
  and reindex.
- Chat — streamed answers with clickable citations, conversation list, and
  private history.
- Deployment — Vercel for the web app, Render for the API, Neon for the database.

## Tech

| Area | Main tools |
| --- | --- |
| API | Python 3.13, FastAPI, async SQLAlchemy 2, Alembic, pytest, ruff, uv |
| Data | Neon Postgres, pgvector |
| AI | Gemini `gemini-embedding-001` (768-d), Groq chat completions |
| Web | Next.js 16 App Router, React 19, TypeScript, Tailwind 4, pnpm |
| Hosting | Vercel, Render |

## Layout

```text
apps/
  api/    FastAPI backend and tests
  web/    Next.js frontend
docs/
  deployment.md      deploy runbook (Vercel + Render + Neon)
  progress.md        chronological work log
  superpowers/       design specs and task plans per milestone
```

## Run locally

API, from `apps/api/`:

```bash
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py     # http://127.0.0.1:8000
```

Web, from `apps/web/`:

```bash
pnpm install
pnpm dev                           # http://localhost:3000
```

Copy each app's `.env.example` to `.env` and fill in the values. The web app
expects the API at `http://127.0.0.1:8000` (override with `API_URL`).

## Docs

- Deploy and operate: `docs/deployment.md`
- API structure and traps: `apps/api/AGENTS.md`
- Web structure and traps: `apps/web/AGENTS.md`
- Design specs and plans: `docs/superpowers/`
