# Ragnest Web

The browser client for **Ragnest**: a multi-tenant RAG service where you sign up,
create a workspace, upload documents, and ask questions that are answered only
from that workspace's own files — every answer citing the source it came from.

A **workspace is the tenant**. There are no organizations. People join a
workspace through an invitation and hold one role there: `creator`, `admin`, or
`member`. Documents, members and answers never cross that boundary.

This package is the Next.js 16 (App Router) front end for the FastAPI service in
[`apps/api`](../api). It owns no data and no secrets. The session JWT lives only
in an httpOnly cookie, and every read or write is forwarded to the API, which
remains the sole authority on identity and access.

---

## Progress

| # | Milestone | Status | What it delivered |
| --- | --- | --- | --- |
| 1 | Accounts | ✅ Done | Sign up, sign in, sign out, and `/account` showing email, account id, join date and session expiry |
| 2 | Workspaces, members & invitations | ✅ Done | Workspace list and creation, workspace detail with a members table, role-gated invite / remove / delete, pending invitations with accept & decline, public invite links, sign-in resume via `?next=` |
| 3 | Documents | Next | Upload and list a workspace's txt / pdf / md files — waiting on API milestone 4, so no UI exists yet |
| 4 | Retrieval & chat | Planned | Ask a question, stream a grounded answer, render citations to the source sentence |

The API side of milestones 1–2 is complete as well. Everything described below
is implemented, type-checked and built; nothing here is a mock.

---

## What you can do today

**Accounts**

- Create an account with an email and password, then sign in. Invalid input is
  reported on the field that caused it (FastAPI's 422 bodies are unwrapped);
  anything else is shown inline as an alert.
- Stay signed in for the life of the 30-minute token. The cookie is `httpOnly`,
  `SameSite=Lax`, and `Secure` in production — client JavaScript never reads it.
- Open `/account` to see who you are signed in as and when the session ends.
- Sign out, which clears the cookie and returns you to the login page.

**Workspaces**

- See every workspace you belong to, plus a banner when invitations are waiting.
- Create a new workspace; you become its `creator`.
- Open a workspace to see its members, their roles and when they joined.

**Members and invitations**

- Invite someone by email as `member` or `admin`. Before creating the invite,
  the form checks whether that address already has a Ragnest account and says so
  if they will need to sign up first.
- Each invite produces a copyable link (`https://<this site>/invite/<token>`).
  There is no email delivery in this milestone — the link is the delivery.
- Review pending invitations on `/invitations` and accept or decline them.
- Public invite pages preview the workspace, inviter, role and expiry without
  consuming anything; accepting is always an explicit button press. Signed-out
  visitors are sent to sign in and returned to the invite afterwards; a visitor
  signed in as the wrong account is offered "Sign out and sign in as …".

Role-gated controls are presentation only — the API enforces the same matrix:

| Action | Who sees the control |
| --- | --- |
| Invite someone | creator, admin |
| Remove a member | creator → admin or member; admin → member only; never yourself; never the creator |
| Delete the workspace | creator |

**Resuming where you were**

- Any redirect into `/login` or `/signup` can carry `?next=/some/path`. Only
  same-origin paths are honoured (`lib/next-path.ts`), so a crafted link cannot
  bounce you to another site.

---

## Routes

| Route | Access | Purpose |
| --- | --- | --- |
| `/` | signed in | Workspaces home: pending invitations banner, workspace list, create form |
| `/account` | signed in | Email, account id, member since, session expiry |
| `/workspaces/[id]` | member | Members table; invite form for admin/creator; remove and delete per the matrix above |
| `/invitations` | signed in | Pending invitations with accept and decline |
| `/invite/[token]` | public | Invite preview and accept, with sign-in resume |
| `/login`, `/signup` | public | Authentication, honouring `?next=` |

Routes under `app/(protected)/` sit behind a cookie-presence guard; the page
itself still asks the API, which decides whether the session is real. A stale
cookie therefore lands on `/login` instead of looping.

---

## How it is put together

- **Reads happen on the server.** Server components take the cookie with
  `getSessionToken()` and call `lib/api.ts` directly. Any page that reads the
  cookie or the API exports `instant = false`, so it is never prerendered.
- **Mutations go through route handlers.** Client components `fetch()`
  `app/api/**`; those handlers read the cookie, call `lib/api.ts`, and forward
  the API's `{detail, fields}` body and status (`apiErrorResponse()` turns an
  unreachable API into a 502). Client components never call the API themselves.
- **401 means the session ended.** During render it redirects to `/login`
  (with `?next=` when there is somewhere to return to); during a mutation the
  client sends you to `/login?next=<current path>` rather than showing a dead
  error.
- **Session and membership changes use full navigation.**
  `window.location.assign(...)`, not `router.push`, so prefetched payloads from
  the old state are discarded after sign-in, sign-out, workspace changes or
  invite accept/decline.
- **Dates are parsed through `parseApiDate()`.** API timestamps are UTC without
  a zone suffix; reading them raw would shift them by your offset.
- **Design tokens, not ad-hoc styles.** Ink-on-paper palette and Archivo /
  Newsreader typography defined in `app/globals.css`. Reusable `Button` and
  `Field` primitives; saffron is reserved for the pending-invite signal.

---

## Running it locally

Prerequisites: Node 20.9+ (or 22+), pnpm 11, and a running API (`apps/api`)
with its migrations applied.

```bash
# terminal 1 — the API
cd apps/api
uv run alembic upgrade head
uv run fastapi dev app/main.py        # http://127.0.0.1:8000

# terminal 2 — this app
cd apps/web
pnpm install
pnpm dev                              # http://localhost:3000
```

Configuration is a single variable, read only by server code (route handlers and
server components):

| Variable | Default | Meaning |
| --- | --- | --- |
| `API_URL` | `http://127.0.0.1:8000` | Where the FastAPI backend listens |

Copy `.env.example` to `.env.local` if you need to point somewhere else. There
is no API key or database URL here — this app never holds a secret.

---

## Checks before committing

There is no web test framework in this repository; correctness is verified by
the type checker, the linter, the production build, and a scripted manual pass
(HTTP with `curl`, then the browser).

```bash
pnpm lint                  # eslint
pnpm exec tsc --noEmit     # types
pnpm build                 # production build, must be clean at every commit
```

After adding or renaming a route, refresh the generated route types before
type-checking:

```bash
pnpm exec next typegen
```

---

## Project layout

```text
apps/web/
├── app/
│   ├── layout.tsx               # fonts + document shell
│   ├── globals.css              # Tailwind 4 theme tokens
│   ├── login/, signup/          # public auth pages
│   ├── invite/[token]/          # public invite preview + accept
│   ├── (protected)/             # cookie-guarded pages
│   │   ├── page.tsx             # workspaces home (/)
│   │   ├── account/
│   │   ├── invitations/
│   │   └── workspaces/[id]/
│   └── api/                     # route handlers: mutation proxies
├── components/                  # Button, Field, forms, actions
└── lib/                         # api client, session cookie, dates, safe ?next=
```

---

## Further reading

- [`AGENTS.md`](./AGENTS.md) — decisions, structural rules and traps for anyone
  changing this code.
- [Web design of record](../../docs/superpowers/specs/2026-10-27-workspaces-invitations-web-design.md)
- [Task plan](../../docs/superpowers/plans/2026-10-27-workspaces-invitations-web.md)
- [API notes](../api/AGENTS.md) and
  [API design of record](../../docs/superpowers/specs/2026-10-19-workspaces-roles-invitations-design.md)
