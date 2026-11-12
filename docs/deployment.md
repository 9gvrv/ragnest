# Deploying Ragnest

**Status:** deployed. The API runs on Render's free web service, the web app on
Vercel, and data lives on the Neon production branch (schema verified and
stamped). What follows is the runbook: how it was set up, how to redeploy, how
to migrate, and what the CI gate on `main` now enforces (§9).

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
| `CORS_ORIGINS` | `https://ragnest.vercel.app` (see below) |
| `GOOGLE_CLIENT_ID` | The OAuth client ID (`...apps.googleusercontent.com`) |
| `GOOGLE_CLIENT_SECRET` | The OAuth client secret (`GOCSPX-...`) |
| `GOOGLE_REDIRECT_URI` | `https://ragnest.vercel.app/api/auth/google/callback` — the **web** callback, not this API |

Use the **pooled** URL at runtime: Neon recommends pooled connections for
non-JS platforms and web apps. `app/core/config.py` already converts the scheme
to `postgresql+asyncpg://`, strips libpq-only parameters, and disables asyncpg's
statement cache, which is what makes the pooler safe.

`CORS_ORIGINS` is a comma-separated browser-origin allowlist; empty (the
default) disables CORS middleware entirely. It only governs **browser** calls:
the web app proxies server-side, so changing it does not affect the app's own
traffic, and it does not stop `curl` or scripts. The API is protected by JWTs
and workspace membership, not by CORS. Set it to the Vercel origin anyway so a
future direct-from-browser call cannot be read by another site.

### Web (Vercel)

| Variable | Value | Scope |
| --- | --- | --- |
| `API_URL` | `https://<render-service>.onrender.com` | Production (add to Preview if used) |
| `GOOGLE_CLIENT_ID` | The same OAuth client ID | Production |
| `GOOGLE_REDIRECT_URI` | `https://ragnest.vercel.app/api/auth/google/callback` | Production |

No database URL and no secret belongs in Vercel. The web app is not a data
owner. The Google **client secret** is only ever in Render's env; the web reads
the client ID and the redirect URI, both of which are public in the OAuth
authorization request.

`GOOGLE_REDIRECT_URI` must be byte-identical on both hosts and registered in the
Google Cloud console, or Google refuses with `redirect_uri_mismatch` and the API
refuses the exchange with `400`. Leave all three API values (and both web
values) empty and Google sign-in stays off: the button is hidden and
`POST /api/v1/auth/google` answers `503`.

### Google Cloud console

1. **APIs & Services → OAuth consent screen**: External, app name `Ragnest`,
   support email, scopes `openid` and `email`. While the status is *Testing*,
   only the accounts under *Test users* can sign in; publish when you want
   anyone to.
2. **Credentials → Create credentials → OAuth client ID → Web application.**
3. **Authorized JavaScript origins**: not used by this flow (it is only for
   Google's browser SDK). Leaving it empty is fine.
4. **Authorized redirect URIs** — both, exactly, no trailing slash:
   `http://localhost:3000/api/auth/google/callback` and
   `https://ragnest.vercel.app/api/auth/google/callback`.
   The API's own origin is **never** a redirect URI.
5. Copy the client ID and secret into the env tables above, then redeploy both
   hosts. Vercel applies env changes only to new deployments.

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
# current revision (must print abba767e7170 (head) today)
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
9. Sign out, then sign in with **Continue with Google** → `/workspaces` loads.
   The same address signing in again reaches the same account, and the password
   still works for an account that was linked from email + password. Cancel on
   Google's consent screen → `/login?error=google_denied`.

---

## 8. Operations

- **Deploys:** Render and Vercel auto-deploy `main`. Use their dashboards for
  manual redeploys. Because `main` is gated by CI (§9), a deploy can only be of
  a commit whose pull request passed the `api` and `web` checks.
- **Rollback:** Render → Deploys → previous deploy → roll back. Vercel →
  Deployments → previous deployment → promote. Neon → restore/PITR within the
  plan window.
- **Secret rotation:** changing `SECRET_KEY` invalidates every session (expected).
- **Cost guardrails:** the real spend risk is Groq/Gemini usage, not hosting.
  Rate limits/quotas are the next milestone, not part of this deploy.
- **Free-tier gotchas:** cold starts; a mid-index sleep leaves a document
  non-ready (use Retry); Neon also autosuspends when idle.

---

## 9. Continuous integration (the merge gate)

`.github/workflows/ci.yml` runs on every pull request and every push to `main`.
That is what makes "tests before deploy" true: both hosts auto-deploy `main`,
so the guarantee comes from `main` only ever receiving merged, green commits —
not from the workflow running "before" Render or Vercel.

| Job | Steps | Typical time |
| --- | --- | --- |
| `api` | `uv sync --locked`, `ruff check app tests`, `ruff format --check app tests`, `ty check app`, `pytest -q` | ~20 s |
| `web` | `pnpm install --frozen-lockfile`, `pnpm lint`, `next typegen`, `tsc --noEmit`, `pnpm build` | ~30 s |

**No repository secrets are used.** `tests/conftest.py` sets dummy
`DATABASE_URL`, `SECRET_KEY`, `GEMINI_API`, and `LLM_API_KEY` before importing
any `app.*` module, and overrides `get_db` with in-memory SQLite. CI therefore
never reaches Neon, Gemini, or Groq.

### The branch ruleset (configure once)

GitHub → **Settings → Rules → Rulesets → New branch ruleset**:

- Target branch: `main`
- ✅ Require a pull request before merging — without this, a direct push skips
  the checks entirely
- ✅ Require status checks to pass → `api` and `web`
- ✅ Block force pushes
- Enforcement: **Active**

The check names come from each job's `name:` in the workflow. Renaming a job
silently blocks every merge until the ruleset is updated. The checks only appear
in the picker after the workflow has run at least once.

### Same checks locally

```bash
cd apps/api
uv run ruff check app tests
uv run ruff format --check app tests
uv run ty check app
uv run pytest -q

cd apps/web
pnpm lint && pnpm exec next typegen && pnpm exec tsc --noEmit && pnpm build
```

### Traps already paid for

- **`setup-uv` has no moving major tag above `v7`.** `astral-sh/setup-uv@v10`
  resolves to nothing and fails at "Set up job"; pin a full version
  (`@v10.3.3`).
- **The web type check needs `next typegen` first.** `PageProps`,
  `LayoutProps`, and `RouteContext` are generated into `.next/types`, which a
  clean checkout does not have — `tsc` alone reports 20+ `TS2304`. The workflow
  runs typegen before `tsc`; `pnpm build` regenerates them anyway.
- **`ty` is a dev dependency pinned by `uv.lock`.** Move it deliberately with
  `uv lock --upgrade-package ty`. Render installs with `--no-dev`, so it never
  ships to production.
- **CI does not run migrations.** The suite is SQLite-only and production is
  migrated manually (§6). Adding `alembic upgrade head` to CI would need a
  Postgres service container using the `pgvector/pgvector` image.
- **No `paths:` filters.** A workflow skipped by a path filter leaves its
  required check stuck at "pending", which blocks the merge. Both jobs always
  run; the whole gate costs under a minute.
