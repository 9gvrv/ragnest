# AGENTS.md — Ragnest Web

> **Read this before touching code.** It records the decisions, structure, and
> traps we cannot afford to rediscover. It is not a tutorial and not a duplicate
> of `README.md`.
>
> **Last updated:** 2026-11-12 (Google sign-in on login and signup). The CI
> gate and the agent-writes agreement landed 2026-11-08.

---

## 1. What this project is

**Ragnest** is a multi-tenant RAG SaaS: a user signs up, creates a workspace,
uploads documents (txt/pdf/md), and chats with them. Answers must be grounded
only in that workspace's documents, with citations to the source file. The
**workspace is the tenant** — there are no organizations.

`apps/web/` is the **Next.js 16 App Router frontend**. It is one part of a
monorepo; the API it talks to lives in `apps/api/` and is its own project. The
web app never reads a database and never holds a secret: it forwards the
session cookie to the API and renders what comes back.

---

## 2. How we work (working agreement — do not violate)

- **The agent writes the code; the human decides.** The human owns scope, the
  trade-offs, and approvals; the agent implements and explains each non-obvious
  decision as it goes. This is a learning project — code the human cannot
  explain is not finished.
- **One small task at a time.** Finish, verify together, then move on.
- **Propose before deciding.** New dependencies, route/structure changes, and
  anything irreversible get a short options-plus-recommendation first.
  Mechanical work proceeds without a round trip.
- **No unrequested refactors.** Structural changes are proposed and agreed
  _before_ anything moves.
- **Small, frequent commits**, so history tells the story. The agent may make
  them; the human decides what merges.
- **Design before code for every new milestone.** New features get a short design
  doc and a task-by-task plan before implementation.
- **Verify before claiming done.** `pnpm lint && pnpm exec next typegen &&
  pnpm exec tsc --noEmit && pnpm build` clean, plus a scripted browser/curl
  check when behaviour is involved. "Should pass" is not a result.

If you are an agent: ask when a decision is genuinely ambiguous, then act and
report what changed and why.

---

## 3. Locked structure (do not reorganize)

```
apps/web/
├── app/
│   ├── layout.tsx                 # fonts + document shell
│   ├── globals.css                # Tailwind 4 theme tokens
│   ├── page.tsx                   # public landing (/)
│   ├── login/page.tsx             # public sign-in
│   ├── signup/page.tsx            # public sign-up
│   ├── invite/[token]/page.tsx    # public invite accept page
│   ├── (protected)/
│   │   ├── layout.tsx             # cookie-presence guard
│   │   ├── workspaces/page.tsx    # workspaces home (/workspaces)
│   │   ├── account/page.tsx       # /account
│   │   ├── invitations/page.tsx   # /invitations
│   │   ├── workspaces/[id]/(shell)/page.tsx          # documents + chat
│   │   └── workspaces/[id]/documents/[documentId]/page.tsx
│   └── api/                       # route handlers (mutation proxies)
│       ├── auth/{login,signup,logout,me}/route.ts
│       ├── auth/google/{start,callback}/route.ts
│       ├── workspaces/route.ts
│       ├── workspaces/[id]/route.ts
│       ├── workspaces/[id]/members/[userId]/route.ts
│       ├── workspaces/[id]/invitations/route.ts
│       ├── workspaces/[id]/invitations/check/route.ts
│       ├── workspaces/[id]/documents/route.ts
│       ├── workspaces/[id]/documents/[documentId]/route.ts
│       ├── workspaces/[id]/documents/[documentId]/reindex/route.ts
│       ├── workspaces/[id]/conversations/route.ts
│       ├── workspaces/[id]/conversations/[conversationId]/route.ts
│       ├── workspaces/[id]/conversations/[conversationId]/messages/route.ts
│       └── invitations/[token]/{accept,decline}/route.ts
├── components/                    # shared UI + workspace shell and chat components
└── lib/                           # api.ts, session.ts, dates.ts, chat-stream.ts, ...
```

- Pages under `app/(protected)/` are wrapped by `app/(protected)/layout.tsx`,
  which redirects when the cookie is absent. The page itself still calls the
  API, which is the only real authority.
- `app/invite/[token]/` sits **outside** the group: it is public and handles its
  own sign-in resume.
- `app/api/**` route handlers exist only to proxy mutations; there are no server
  actions in this milestone.

---

## 4. Patterns of record

1. **Auth storage.** The JWT lives only in the `ragnest_session` httpOnly cookie
   (`lib/session.ts`, 30-minute maxAge mirroring the API expiry). Client JS
   never reads it.
2. **Server data reads.** Server components take the cookie with
   `getSessionToken()` and call `lib/api.ts` (`request<T>(path, { token })`)
   directly. Every such page exports `export const instant = false;` — it cannot
   be prerendered.
3. **Mutations.** Client components `fetch()` route handlers under `app/api/**`.
   The handler reads the cookie, calls `lib/api.ts`, and forwards the API's
   `{detail, fields}` body with the API's status via `apiErrorResponse()`
   (status 0 — unreachable — becomes 502). Auth handlers keep their own inline
   error shape; new handlers use the shared helper.
4. **401 handling.** During render it means the session ended →
   `redirect("/login")` (add `?next=` when the person should resume here).
   During a mutation it is forwarded; the client sends the person to
   `/login?next=<current path>` rather than showing a dead error.
5. **Full navigation after session or membership changes.** `window.location.assign(...)`,
   never `router.push`, so prefetched router payloads from the old state are
   discarded. This applies after sign-in/out, creating/deleting a workspace,
   removing a member, accepting/declining an invite.
6. **Errors.** `ApiError` carries `status` + optional `field_errors`; FastAPI 422
   bodies are unwrapped into per-field messages by `toError()`. Render those on
   the `Field` and show everything else inline as an alert.
7. **Dates.** API timestamps carry no zone suffix; always render through
   `parseApiDate()` (`lib/dates.ts`).
8. **Next.js 16 (vendored docs).** Trained-data assumptions may not apply:
   consult `node_modules/next/dist/docs/` first. Dynamic pages use
   `PageProps<'/path/[seg]'>` + `await params`; route handlers use
   `RouteContext<'/api/.../[seg]'>` + `await context.params`.
9. **Chat reads live in the server page.** `/workspaces/[id]` fetches the
   author's conversations plus the `?chat=<id>` detail (messages in order).
   `?chat` is a query parameter, not a nested route; a stale/deleted id
   redirects to the bare workspace page. Conversations are private to their
   author, so another member's id is a 404 there.
10. **The messages proxy streams.** `app/api/.../messages/route.ts` calls
    `streamConversationMessage()` and returns `new Response(upstream.body, ...)`
    with `text/event-stream`, `no-cache, no-transform`, and
    `X-Accel-Buffering: no`. It never reads the body. Non-OK upstream responses
    are ordinary JSON and keep the API's status (`429`/`503` map to alerts).
11. **Chat state is client-owned.** `ChatArea` (keyed by
    `activeChatId ?? "new"`) seeds from server messages, adds optimistic
    messages, creates the conversation on first send, and streams through
    `lib/chat-stream.ts`. The URL changes with `router.replace(...?chat=<id>)`
    only after the stream settles. Stop aborts the fetch; the API persists the
    partial answer as `finish_reason: "cancelled"`.
12. **Citations are rendered from the answer text.** Split on
    `/(\[\d+\]|【\d+】)/`; a marker becomes a button only when its `n` matches
    a citation, and clicking scrolls and highlights that source card. `sources`
    snapshots come from the API; `done.cited` is informational.
13. **Indexing feedback.** Non-`ready` documents show `Queued`/`Indexing…`/
    `Failed` and (for uploader/creator/admin) a retry that POSTs the reindex
    proxy. `IndexingWatcher` polls `router.refresh()` every 2.5s while any
    document is non-ready, paused when the tab is hidden, capped at 40 ticks.
    The chat gate is **at least one `ready` document**, not document count.
14. **Google sign-in is a server-side code flow, not Google's JS SDK.**
    `/api/auth/google/start` mints `state` and a PKCE verifier, stores them in
    the ten-minute httpOnly `ragnest_google` cookie (`path=/`, because
    `cookies().delete()` cannot target a narrower path), and redirects to
    `accounts.google.com`. `/api/auth/google/callback` compares `state`, clears
    the cookie, calls the API's `POST /api/v1/auth/google`, sets
    `ragnest_session`, and redirects to the stored `next` (re-validated with
    `safeNextPath`). Failures always land on `/login?error=<code>`, rendered by
    `AuthAlert`; no query value ever chooses a redirect target. The web holds
    only `GOOGLE_CLIENT_ID` and `GOOGLE_REDIRECT_URI` — never the secret, and
    no token ever appears in a URL. The button is a plain `<a>`, so it is a
    full navigation. Do not add `export const dynamic` to these routes:
    `cacheComponents: true` rejects it, and reading `cookies()` already makes
    them dynamic.

---

## 5. Routes and who sees what

| Route | Access | Purpose |
| --- | --- | --- |
| `/` | public | Landing page: hero, product preview. Static; does not read the cookie |
| `/workspaces` | signed in | Workspaces home: pending-invite banner, workspace list, create form |
| `/account` | signed in | Email, account id, member since, token expiry |
| `/workspaces/[id]` | member | Documents, members, and the author's chats; `?chat=<id>` opens one conversation, `?mine=true` filters documents |
| `/invitations` | signed in | Pending invitations with accept/decline |
| `/invite/[token]` | public | Preview + accept; sign-in resume via `?next=` |
| `/login`, `/signup` | public | Auth, honour `?next=` |

Role-gated controls (presentation only — the API is the authority):

| Action | Control visible to |
| --- | --- |
| Invite | creator, admin |
| Remove member | creator → admin/member; admin → member only; never self; never creator |
| Delete workspace | creator |

The viewer's own role comes from the members list, matched by
`getMe().id`. A 403 from the workspace/members fetch renders the explicit
"not a member" state; 404/422 render `notFound()`.

---

## 6. `?next=` and invite links (decisions)

- **`?next=` resumption.** Login/signup accept `next` in the request body. The
  value must survive `safeNextPath()` (`lib/next-path.ts`): a leading `/`, no
  backslash or control characters, and a parsed origin equal to this site
  (`/\evil.com` and `//evil.com` both fall back to the default
  `/workspaces`). `AuthForm` reads
  `redirect` and does a full navigation. The auth pages pass `next` through to
  the form and to the link that switches between login and signup, and only
  bounce a cookie-holding visitor when `getMe()` confirms the session is live
  (a stale cookie must not loop between `/` and `/login`).
- **Invite links are web links.** The shareable address is always
  `${origin}/invite/{token}`. The API's `link` field
  (`/invitations/{token}/accept`) is internal plumbing and is never rendered.
- **No email delivery.** Creating an invite produces a copyable link (the only
  "send" mechanism in this milestone).
- **Accept is never automatic.** The public page only previews; consuming an
  invite always requires an explicit button press, so a link preview cannot
  burn it.

---

## 7. Design language

Neutral Vercel/Geist minimalism. Semantic Tailwind 4 tokens live in
`app/globals.css`: `background`, `surface`, `border`, `control`, `foreground`,
`muted`, `accent`, `danger`, with automatic dark values via
`prefers-color-scheme` (there is no theme toggle). Geist Sans is the UI face;
Geist Mono is for IDs and citation refs. There is no serif or display face. The
scale is 12/14/16/20/24/32/48, headings at weight 600 with tight tracking.
Structure comes from 1px borders, never shadows; radii are 6px for controls and
8px for panels. Exactly one accent (blue) is used for links, focus rings, and
state highlights; primary buttons are solid `foreground` with inverse text.
Motion is limited to 150ms color/border transitions and is disabled under
`prefers-reduced-motion`. The app container is `max-w-3xl mx-auto px-6`; the
header is a plain `Ragnest` wordmark followed by an `h1`. Reuse `Button` and
`Field`. No new dependencies.

**Dark surface.** `/`, `/login`, `/signup`, and `/workspaces` share
`SiteShell` (`site-nav`, `site-footer`) or the `dark-surface` wrapper and are
deliberately dark in both OS themes: the `dark-surface` class in `globals.css`
re-declares the semantic tokens on the wrapper (background `#08090a`, surface
`#0e0f11`, elevated `#15161a`, foreground `#f7f8f8`, muted `#8b9099`, accent
`#7c9cff`, borders `rgba(255,255,255,.08)`), so nothing outside that subtree
changes. One soft radial glow at the top is the only decoration; there is no
second typeface, no grid, and no gradient text. Marketing pages align to the
shared `Container` (`max-w-7xl`, `px-6 lg:px-8`), use tight `-0.04em` tracking
on large headings, and a white pill for the primary CTA. The preview image path
and the footer's GitHub link live in `lib/site.ts`.

---

## 8. Commands (run from `apps/web`)

```bash
pnpm dev                  # dev server on :3000 (API expected on :8000)
pnpm lint
pnpm exec next typegen    # writes PageProps/RouteContext/LayoutProps to .next/types
pnpm exec tsc --noEmit    # requires typegen first in a clean checkout
pnpm build                # must be clean at every commit
```

There is **no web test framework** in this repo. Verification is
`pnpm lint && pnpm exec next typegen && pnpm exec tsc --noEmit && pnpm build`
plus a scripted manual browser/curl check. `API_URL` (default
`http://127.0.0.1:8000`) points at the API. CI runs the same sequence (see
`docs/deployment.md` §9).

Deployment: Vercel with **Root Directory** `apps/web` and the server-only
`API_URL` set to the API's HTTPS origin. `NODE_ENV=production` makes
`ragnest_session` a `Secure` cookie, so the app must be served over HTTPS (Vercel
always is). `lib/api.ts` trims `API_URL` and strips trailing slashes — without
that, a base ending in `/` yields `//api/v1/...`, which the API answers with 404.
Vercel applies environment-variable changes **only to new deployments**, so edit
the value and redeploy; the running deployment keeps its old value. Full runbook:
`docs/deployment.md`.

---

## 9. Do not

- Do **not** read or write the JWT from client JS, or store it anywhere but the
  httpOnly cookie.
- Do **not** call the API from client components; mutations go through
  `app/api/**`, reads through server components + `lib/api.ts`.
- Do **not** use `router.push` across a cookie/membership change; use
  `window.location.assign`.
- Do **not** render the API's invite `link` field.
- Do **not** re-implement date parsing; use `parseApiDate`.
- Do **not** add dependencies or restructure routes without a design first.

---

## 10. Roadmap (web)

1. ✅ Auth pages — login, signup, account.
2. ✅ Workspaces, members & invitations — home, detail, invite links, pending
   list, public accept, `?next=` resume.
3. ✅ Documents & chat — upload/list/delete/reindex, indexing status, streaming
   answers, clickable citations, conversation list.
4. ✅ Google sign-in — "Continue with Google" on `/login` and `/signup`, the
   start/callback route handlers, and `/login?error=<code>` alerts.

## 11. Pointers

- Google sign-in design:
  `docs/superpowers/specs/2026-11-12-google-oauth-design.md`
- Google sign-in plan:
  `docs/superpowers/plans/2026-11-12-google-oauth.md`
- Web documents + chat design:
  `docs/superpowers/specs/2026-11-06-web-documents-chat-design.md`
- Web documents + chat plan:
  `docs/superpowers/plans/2026-11-06-web-documents-chat.md`
- Web design of record: `docs/superpowers/specs/2026-10-27-workspaces-invitations-web-design.md`
- Web task plan: `docs/superpowers/plans/2026-10-27-workspaces-invitations-web.md`
- API design of record: `docs/superpowers/specs/2026-10-19-workspaces-roles-invitations-design.md`
- API project notes: `apps/api/AGENTS.md`

---

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

<!-- BEGIN:nextjs-agent-feedback -->

## Report Next.js feedback

The project owner enabled `experimental.agentFeedback`, authorizing this feedback pass. When enabled, `next dev` writes this block and restores it if removed. Commit `AGENTS.md` with your work to keep the tree clean.

During the current user request, retain anonymized facts as feedback candidates for meaningful or recurring Next.js issues:

- Crashes, hangs, OOMs, or unexpected slowness
- Incorrect behavior, output, errors, or diagnostics
- Missing, unclear, or conflicting documentation
- Unexpected CLI, codemod, Skill, or upgrade behavior and non-obvious workarounds

Continue the current user request without reporting immediately. Routine debugging is not feedback. Verify changes before retaining them as feedback candidates. Never retain code, logs, paths, URLs, secrets, personal information, or project-specific data.

Retain qualifying friction even if it is later fixed or worked around; record the final outcome during the reporting pass.

Before the final response, run one reporting pass. If candidates remain, from this file's directory run `npx --no-install next internal agent-feedback-instructions` once without piping or truncating its output. Follow its output or error guidance. If a network sandbox blocks it, retry with network access; if it still returns no output, continue normally.

<!-- END:nextjs-agent-feedback -->
