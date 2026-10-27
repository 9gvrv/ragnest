# Ragnest Web — Workspaces, Memberships & Invitations — Design

**Date:** 2026-10-27
**Status:** Proposed

---

## 1. What this is

The frontend for Milestone 3's API (`apps/api` workspaces, memberships with
roles, and invitations). The API work is done and tested manually (39 tests
green, DB migrated to `c435432cb50d`); the web app currently has auth only —
this milestone gives people something to do after they sign in: create
workspaces, see members, invite others, and accept invites.

This document and its implementation plan follow the established convention:
`specs/` records design decisions, `plans/` records task-by-task execution.

---

## 2. Scope

**In:**

- Workspace home — list my workspaces, create one.
- Workspace detail — members with roles; role-gated actions (remove member,
  invite, delete workspace).
- Invitation creation UI — email-check + invite, then a **copyable link**
  (this is the "send" step; see §8 D6, no email delivery).
- My pending invitations page — accept or decline.
- Public invite-accept page for a token — the pre-signup entry point.
- A small **API addition**: `GET /api/v1/invitations/{token}` (§7) — required
  so the public page can render meaningful state before accepting.
- `?next=` redirect support in login/signup so an invite link resumes after
  signing in.

**Out (non-goals):**

- Email delivery of invites (its own future milestone; Everest for later).
- Workspace settings/rename (no API endpoint exists).
- Listing the invitations already sent for a workspace (no API endpoint; a
  future API micro-feature — the workspace page shows only what the API can).
- A web test framework (none exists in this repo; verification is
  lint + tsc + build + scripted manual browser checks, see §9 D8).
- Any new web dependency.

---

## 3. How the web app works today (patterns of record)

All verbatim truths the plan builds on:

- **Auth storage.** The JWT lives only in the `ragnest_session` httpOnly
  cookie (`lib/session.ts`, 30-minute maxAge mirroring the API expiry).
  Client JS never sees the token.
- **Server data reads.** Server components read the cookie via
  `getSessionToken()` and call the API directly through `lib/api.ts`
  (`request<T>(path, { token })`), never via a self-HTTP hop. Pages doing
  this set `export const instant = false;` (cannot be prerendered).
- **Mutations.** Client components `fetch()` route handlers under
  `app/api/...` (the auth pattern: handler reads the cookie, calls the API,
  forwards `{detail, fields}` errors with the API's status code).
- **After sign-in/out.** `window.location.assign(...)` full navigation to
  discard prefetched router payloads built for the old session
  (documented trap in `auth-form.tsx`).
- **401 during render** = normal session end → `redirect("/login")`.
- **Errors.** `ApiError` carries `status` + optional `field_errors`; FastAPI
  422 bodies are unwrapped into per-field messages by `toError()`.
- **Dates.** API timestamps have no zone suffix; always render through
  `parseApiDate()` (`lib/dates.ts`).
- **Design language.** Ink-and-paper Tailwind 4 tokens: `text-action`,
  `text-muted`, `text-danger`, `bg-paper`, `text-paper`, `border-rule`,
  `border-control`, `font-serif`, container `max-w-136 mx-auto px-6` with the
  existing header block (`text-[13px] tracking-[0.08em] text-action`
  + serif `<h1>`). Reuse `Button`, `Field` primitives.
- **Next.js 16 (vendored docs).** Trained-data assumptions may not apply:
  consult `apps/web/node_modules/next/dist/docs/` before using unfamiliar
  APIs. Dynamic segments use the typed global helpers with async params:
  `export default async function Page({ params }: PageProps<'/x/[seg]'>)`
  and `const { seg } = await params;`.

---

## 4. Information architecture (routes)

| Route | Type | Purpose |
| --- | --- | --- |
| `/` | protected, server | **Workspaces home** (rewritten from account page): workspace list, create form, pending-invitations banner, sign out, link to account |
| `/account` | protected, server | The existing account page content (email, id, member since, signed-in until) moved here |
| `/workspaces/[id]` | protected, server | Workspace detail: info, members, role-gated invite/remove/delete |
| `/invitations` | protected, server | My pending invitations: accept or decline each |
| `/invite/[token]` | **public**, server | Accept flow for a shared link: preview → resume auth → accept |
| `app/api/workspaces/**`, `app/api/invitations/**` | route handlers | Mutation proxies (create/delete/remove/invite/check/accept/decline) |

The `(protected)` route group keeps guarding `/`, `/account`,
`/invitations`, `/workspaces/[id]`. `/invite/[token]` sits outside the group
(public) and handles its own auth resume (§6 flow 4).

---

## 5. Role-gated UI matrix

Derived from `workspaces/deps.py` and `service.remove_member` (as built):

| Action | Who sees the control | API enforces anyway |
| --- | --- | --- |
| Create workspace | every signed-in user | `get_current_user` |
| View members | every member | `require_workspace_member` → 403 |
| Invite (after check) | admin or creator | `require_workspace_admin_or_creator` |
| Remove member | admin → member targets only; creator → admin/member targets only; **never** self (409), **never** creator (403) | same, server side |
| Delete workspace | creator only | `require_workspace_creator` |

Client-side hiding is presentation, not security — the API is the authority,
and API error text is always the fallback when a stale page sends a forbidden
action. The member's own role comes from the members list (find my row by
`user_id` — the workspace fetch itself does not return a role).

---

## 6. User flows

**Flow 1 — Home & create.** Sign in → `/` shows workspaces (or an empty
state: "No workspaces yet"). Create form posts to the route handler, refreshes
to the new workspace page. A pending-invitations banner appears above the
list when `GET /api/v1/invitations/pending` is non-empty.

**Flow 2 — Workspace detail & invite.** Open a workspace → members table
(email, role chip, joined date) + role-gated controls. Invite form: email +
role (`admin`|`member`) → `POST .../invitations/check` (hint: "No Ragnest
account yet — they'll need to sign up with this email" when `exists=false`)
→ `POST .../invitations` → success block with the shareable link
`${origin}/invite/{token}` (the API's `/invitations/{token}/accept` path is
API-internal; the web link is `§8 D6`). Copy button. 409s surface the API's
message ("Pending invitation already exists" / "User already a member").

**Flow 3 — Pending invitations.** `/invitations` lists each row (workspace
name, inviter email, role, expiry via `parseApiDate`). Accept →
API accept → full navigation to `/workspaces/{workspace_id}`. Decline →
204 → refresh the list.

**Flow 4 — Public accept (`/invite/[token]`).** Server component fetches
`GET /api/v1/invitations/{token}` (no auth) and renders:

- `pending` + viewer has session → summary + Accept button. Accept errors
  render in place: **403** = "This invitation was sent to `email` — sign in
  with that account."; **400/410/404** = dead-state copy.
- `pending` + no session → sign-in prompt with links to
  `/login?next=/invite/{token}` and `/signup?next=/invite/{token}`; after
  auth, `?next=` resumes this page (§8 D4).
- `expired` → "This invitation expired on {date}." `accepted` → "You're
  already a member — open workspace." `declined` → "This invitation was
  declined."

The page never mutates on render; accept is always an explicit button so
preview links (email previews, accidental clicks) can't consume an invite.

---

## 7. API surface consumed (+ one addition)

Existing endpoints drive everything: `POST/GET /api/v1/workspaces`,
`GET/DELETE /api/v1/workspaces/{id}`, `GET .../members`,
`DELETE .../members/{user_id}`, `POST .../invitations/check`,
`POST .../invitations`, `GET /api/v1/invitations/pending`,
`POST /api/v1/invitations/{token}/accept|decline`.

**Addition: `GET /api/v1/invitations/{token}`** (no auth) →
`200 {invitation_id, workspace_id, workspace_name, inviter_email, email,
role, status, expires_at}`; `404` for unknown tokens. Rationale: without it,
the public page cannot render any pre-accept state ("who is inviting me,
what role") without blindly calling accept, which could consume the
invitation. Decision: **no auth required** — the token itself is a
capability string; the endpoint reveals only what a link holder already
holds (workspace name, role, status, target email). Server-side
implementation reuses the pending-list join plus `status`; tested with
pytest like all API code.

**Second, smaller addition (same task): the pending list returns `token`.**
`InvitationPendingRead` and the `list_pending_for_user` select gain a
`token` field. Without it, the pending-invitations page cannot call
accept/decline (both are token-addressed) — the pending list is already
email-gated to the signed-in user, so the token reaches exactly the
audience the accept endpoint permits anyway.

---

## 8. Decisions

- **D1 — IA (locked).** Routes per §4. Account content moves from `/` to
  `/account`; `/` becomes the workspaces home. No restructure of auth pages.
- **D2 — Data & mutations.** GETs: server components + `lib/api.ts` +
  cookie token. Mutations: `app/api/**` route handlers following the auth
  proxy pattern. No server actions this milestone (the repo's proven
  pattern is route handlers; switching conventions is out of scope).
- **D3 — API addition.** One new read-only endpoint (§7) lands first in the
  plan; tested; keeps every web page render-able from real data.
- **D4 — `?next=` resumption.** Login/signup accept a `next` body value,
  validated as starting with `/` and not `//` (open-redirect guard,
  default `/`); the route handler echoes `{ok, redirect}` and `AuthForm`
  does `window.location.assign(redirect)`. No cookies-of-intent needed.
- **D5 — "Send" = copy-link (recorded).** No email in this milestone. The
  invite success block renders the full `/invite/{token}` URL with a copy
  button; pending-list discovery covers already-registered emails.
- **D6 — Link plumbing.** UI builds `origin/invite/{token}`; the API's
  `link` field (`/invitations/{token}/accept`) is treated as internal and
  never rendered as-is.
- **D7 — Roles & copy.** Role chips render as text
  (`creator`/`admin`/`member`); the matrix in §5 is the single source for
  control visibility.
- **D8 — Verification.** No web test framework exists (repo truth). Every
  task verifies with `pnpm lint`, `pnpm exec tsc --noEmit`, `pnpm build`,
  and a scripted manual browser check; the one API task uses pytest. The
  plan's final task runs the full two-user manual flow end to end.
- **D9 — Style.** Existing primitives and tokens only; no new dependencies;
  serif/muted/action classes as in §3; metadata titles per page
  (`"Workspaces — Ragnest"`, etc.).

---

## 9. Edge cases to nail (each maps to a Review Focus line in the plan)

1. **30-minute token expiry mid-use** → any 401 during a mutation is
   forwarded as the auth routes do; the client turns 401 into
   "sign in → resume this page" (`?next=`), not a dead error.
2. **Dead/mismatched invites** on `/invite/[token]` — 404 unknown,
   400 non-pending, 410 expired, 403 wrong email all have explicit copy
   (§6 flow 4); a clicked-dead link never 500s.
3. **Role gating** — a plain member sees no invite form, no remove buttons,
   no delete; direct API calls still govern (server rules are the boundary).
4. **Bad identifiers** — a non-UUID or unknown `[id]` in
   `/workspaces/[id]` renders a not-found state (API 422/404 → `notFound()`),
   never a stack trace.
5. **Lazy re-render safety** — the `window.location.assign` pattern after
   cookie changes, and after mutations that change membership on pages
   where prefetched payloads could be stale.

---

## 10. Constraints

- Next.js 16 App Router, React 19, TypeScript strict, Tailwind 4, pnpm.
- Vendored docs `apps/web/node_modules/next/dist/docs/` are the API truth.
- JWT stays in the httpOnly cookie; client JS never reads it.
- API calls always go through `lib/api.ts` `request()` (one error ontology).
- `pnpm lint` clean; `pnpm build` must succeed at every commit.
- Do not touch `apps/web/node_modules`, do not add dependencies.
- Do not restructure auth pages beyond the `?next=` addition (§8 D4).

---

## 11. Pointers

- API of record: `docs/superpowers/specs/2026-10-19-workspaces-roles-invitations-design.md`
- API plan: `docs/superpowers/plans/2026-10-19-workspaces-roles-invitations.md`
- API reality check (endpoints as built, with bodies): this session's test
  walkthrough; the API source in `apps/api/app/modules/`.
- Web structure of record: `apps/web/AGENTS.md` (Next 16 vendored docs).
- Implementation plan: `docs/superpowers/plans/2026-10-27-workspaces-invitations-web.md`
