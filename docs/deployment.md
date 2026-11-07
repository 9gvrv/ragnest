# Deploying Ragnest

**Status:** prepared, not yet executed. The repository is merged and pushed; the
production database is verified and stamped. Everything below is the part that
happens in the Vercel, Render, and Neon dashboards.

Topology:

```
Browser ── HTTPS ──> Vercel (Next.js, apps/web)
                         │  server-side fetch only; the JWT stays in an httpOnly cookie
                         ▼
                    Render (FastAPI, apps/api)  ── pooled TCP ──> Neon production branch
```

The browser never calls the API directly. That is why the API needs no CORS
configuration and why `API_URL` is a server-side-only environment variable.

---

## 1. What is already true

- `main` contains the finished web documents + chat milestone (PR-ready commit
  `ebf2f57`), and it is pushed to GitHub.
- The Neon **production branch** was copied from the dev branch with **schema
  only** and holds **zero rows** in every table.
- Its schema matches `Base.metadata` exactly (checked with Alembic's
  `compare_metadata`): 9 tables, `vector 0.8.6`, and the HNSW index
  `ix_document_chunks_embedding_hnsw`.
- `alembic_version` was **empty** after the schema copy. It is now stamped to
  `7c1e4a9b2d3f (head)`, so **no migration is pending** and none was run.
- No Dockerfile or deploy config is committed. The settings below are enough for
  Render's native Python runtime.

> **Trap for the next schema-only branch copy:** Neon copies tables, extensions,
> and indexes, but not the `alembic_version` row. Verify the schema, then
> `alembic stamp head`. Do **not** run `alembic upgrade head` against a schema
> that is already current — it will try to recreate existing tables.

---

## 2. Recommended free API host: Render

**Why Render:** it is the least fiddly free option for a Python/FastAPI
container-style process, supports `uv` natively when `uv.lock` is present, and
keeps a long-lived process (SSE and 10–30 s generations behave better than on
scale-to-zero serverless). It is enough for a demo or a private beta.

**Free-tier facts to accept (Render documents these):**

- Web service spins down after **15 minutes** without traffic; the next request
  takes roughly **1 minute** to wake it.
- **0.1 CPU / 512 MB**, one instance, 750 instance-hours per month.
- Ephemeral filesystem (irrelevant here: documents live in Postgres).
- **No pre-deploy command on free services** — migrations are manual.
- Render explicitly says free instances are **not for production applications**.

Things that are fine on Render: streaming responses, outbound HTTPS to Groq and
Gemini, and Neon over TCP. Things to warn users about: the first request after
idle is slow, and an in-process indexing background task can be cut off if the
service sleeps or restarts mid-job. The document then stays `pending`; the
reindex button in the UI repairs it.

When this stops being a demo, Render Starter is $7/month and unlocks pre-deploy
commands (automatic migrations). Cloud Run is the alternative if you want a real
free tier and are willing to add a billing account and configure a container.

---

## 3. Environment variables

### API (Render)

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Production branch **pooled** connection string (`-pooler` host, `sslmode=require`) |
| `SECRET_KEY` | **New** random value for production (generate with `python -c "import secrets;print(secrets.token_urlsafe(48))"`) |
| `GEMINI_API` | Gemini key (ideally separate from dev, for quota isolation) |
| `LLM_API_KEY` | Groq key (ideally separate from dev) |
| `PYTHON_VERSION` | `3.13.13` (matches local; Render defaults to 3.14) |
| `APP_NAME` | `Ragnest API` (optional) |
| `LOG_LEVEL` | `INFO` (optional) |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` (optional, default) |
| `LLM_MODEL` | `openai/gpt-oss-120b` (optional, default) |
| `LLM_REASONING_EFFORT` | `low` (optional, default) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` (optional, default) |

Use the **pooled** URL at runtime: Neon recommends pooled connections for
non-JS platforms and web apps. `app/core/config.py` already converts the scheme
to `postgresql+asyncpg://`, strips libpq-only parameters, and disables asyncpg's
statement cache, which is what makes the pooler safe.

### Web (Vercel)

| Variable | Value | Scope |
| --- | --- | --- |
| `API_URL` | `https://<render-service>.onrender.com` | Production (add to Preview if used) |

No database URL and no secret belongs in Vercel. The web app is not a data
owner.

---

## 4. Deploy the API on Render

1. **New → Web Service**, connect the `9gvrv/ragnest` repository.
2. Settings:
   - **Branch:** `main`
   - **Root Directory:** `apps/api`
   - **Language:** Python 3
   - **Region:** the same continent as the Neon branch (e.g. Ohio for
     `aws-us-east-2`, Frankfurt for `aws-eu-central-1`) to keep queries quick.
   - **Instance Type:** Free
   - **Build Command:** `uv sync --frozen --no-dev`
   - **Start Command:** `uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/health`
3. Add the environment variables from §3.
4. **Create Web Service** and wait for the first deploy.

Why those commands:

- `uv sync --frozen --no-dev` installs exactly `uv.lock` and skips pytest/ruff.
  Render adds `uv` automatically because `apps/api/uv.lock` exists.
- `--no-sync` stops `uv run` from re-resolving and re-installing at boot; the
  build already produced `.venv`.
- `--port $PORT` is required: Render assigns the port.
- `/health` runs `SELECT 1`, so a green health check also proves Neon is
  reachable with the production URL.

Check it:

```bash
curl -sS https://<render-service>.onrender.com/health
# {"status":"ok","database":"connected"}
```

The first call after 15 idle minutes can take about a minute.

---

## 5. Deploy the web app on Vercel

1. **Add New → Project**, import `9gvrv/ragnest`.
2. **Root Directory:** `apps/web`. Framework preset: Next.js (detected).
3. Add `API_URL` from §3 for **Production** (and Preview if you use it).
4. Deploy.

Notes:

- Vercel installs with pnpm because `package.json` pins `pnpm@11.25.0`.
- `NODE_ENV=production` makes `ragnest_session` a `Secure` cookie, so the site
  must be served over HTTPS. Vercel always is; this is exactly the intended
  setup.
- Vercel Hobby functions default to a 300 s maximum duration, so the SSE proxy
  (`app/api/.../messages/route.ts`) has plenty of headroom. It streams the
  upstream body without buffering.

---

## 6. Migrations (manual on free Render)

Render's pre-deploy command is paid-only, so run migrations from your machine
**before** merging a change that needs one.

In Neon Console → **Connect**, toggle **Connection pooling OFF**, copy the
**direct** URL, and store it in `apps/api/.env` as `DATABASE_URL_PROD_DIRECT`
(local only; gitignored). Keep `DATABASE_URL_PROD` as the pooled URL the host
uses.

Then, from `apps/api`:

```bash
# current revision (must print 7c1e4a9b2d3f (head) today)
DATABASE_URL="$(uv run python -c "from dotenv import dotenv_values;print(dotenv_values('.env')['DATABASE_URL_PROD_DIRECT'])")" \
  uv run alembic current

# apply anything new
DATABASE_URL="$(uv run python -c "from dotenv import dotenv_values;print(dotenv_values('.env')['DATABASE_URL_PROD_DIRECT'])")" \
  uv run alembic upgrade head
```

Why this shape: the environment variable overrides `.env`, so `Settings()` never
sees the dev URL, and the URL is read straight from the gitignored file instead
of being pasted into shell history or a process listing.

Rules:

- **Direct URL for DDL**, pooled URL for the running app. Neon's guidance.
- Migrations must be backward compatible: the old API instance keeps serving
  while Render builds the new one.
- Order: migrate the database → merge/push to `main` → Render auto-deploys.
- Never run migrations against the dev branch by accident. The command above
  only reads `DATABASE_URL_PROD_DIRECT`.

---

## 7. Smoke test after the first deploy

1. `GET https://<api>/health` → `200`, `"database":"connected"`.
2. Open the Vercel URL over HTTPS and **sign up** (new production user, not a
   dev account).
3. Create a workspace, upload a small `.txt` containing one unique fact.
4. Wait until the document shows `ready` (Gemini indexing).
5. Ask a question about that fact. Confirm the answer streams token by token and
   shows a clickable `[1]` citation to the file.
6. Reload the page: the conversation is in the sidebar and the answer is still
   there.
7. Delete the document and confirm the conversation still renders its citation
   snapshot (by design, citations survive deletion).
8. Check DevTools → Cookies: `ragnest_session` is `HttpOnly` and `Secure`.

---

## 8. Operations

- **Deploys:** Render and Vercel auto-deploy `main`. Use their dashboards for
  manual redeploys.
- **Rollback:** Render → Deploys → previous deploy → roll back. Vercel →
  Deployments → previous deployment → promote. Neon → restore/PITR within the
  plan window.
- **Secret rotation:** changing `SECRET_KEY` invalidates every session (expected).
- **Cost guardrails:** the real spend risk is Groq/Gemini usage, not hosting.
  Rate limits/quotas are the next milestone, not part of this deploy.
- **Free-tier gotchas:** cold starts; a mid-index sleep leaves a document
  non-ready (use Retry); Neon also autosuspends when idle.
