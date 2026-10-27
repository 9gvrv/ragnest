# Workspaces & Invitations — Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This project runs in mentor mode:** the human writes the code; the mentor explains, reviews, and only writes files when a step says so. Steps are still written as concrete, verifiable actions.

**Goal:** Build the web UI for the Milestone 3 API: workspace home with creation, workspace detail with role-gated member management and invites, a copyable invite link (no email), a pending-invitations page, and a public token-based accept page.

**Architecture:** Follows the web app's established patterns — server components read the httpOnly session cookie and fetch the API directly via `lib/api.ts`; all mutations go through `app/api/**` route handlers proxied from client components (the auth pattern). One small API addition (invitation preview endpoint) enables a meaningful public accept page. Spec drives everything; this plan argues from it.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Tailwind 4, pnpm — no new dependencies. API addition: FastAPI + pytest (existing stack).

**Spec:** `docs/superpowers/specs/2026-10-27-workspaces-invitations-web-design.md`

## Global Constraints

(from the spec §3, §10 — every task inherits these)

- Consult `apps/web/node_modules/next/dist/docs/` before unfamiliar Next APIs; dynamic segments use `PageProps<'/path/[seg]'>` with `await params` (vendored `dynamic-routes.md`, `adopting-partial-prefetching.md`).
- JWT lives only in the `ragnest_session` httpOnly cookie (`lib/session.ts`); client JS never reads it.
- Server GETs: `getSessionToken()` + `lib/api.ts` `request(..., { token })`, page sets `export const instant = false;` with the established comment about cookies/prerender.
- Mutations: client `fetch()` → route handler → reads cookie → `lib/api.ts` → forward `{detail, fields}` with the API's status (0 → 502).
- After sign-in/out/certain mutations: `window.location.assign(...)` full navigation (router-cache trap), never `router.push` across cookie changes.
- 401 during render = expired session → `redirect("/login")` (with `?next=` where resumption matters); 401 during a mutation is forwarded for the client to act on.
- All dates rendered via `parseApiDate()` (`lib/dates.ts`).
- Styling: existing tokens only — `text-action`, `text-muted`, `text-danger`, `bg-paper`, `border-rule`, `font-serif`, `max-w-136 mx-auto px-6` container, `Button`/`Field` primitives; no new deps.
- Verification per web task: `cd apps/web && pnpm lint && pnpm exec tsc --noEmit && pnpm build` all clean; manual browser check per task; API task verifies with pytest + ruff.
- Servers for manual checks: API `cd apps/api && uv run fastapi dev app/main.py` (port 8000), web `cd apps/web && pnpm dev` (port 3000).
- Never render the API's `link` field (`/invitations/{token}/accept`) as user-facing; the web link is always `${origin}/invite/{token}` (spec D6).
- Do not restructure auth pages beyond the `?next=` change (Task 3).

## Review Focus

Failure modes the spec calls out; each is pinned to its owning task's verification steps:

1. **Token expiry mid-use** — a 30-minute-old session that 401s on a mutation should offer "sign in and resume," not a dead error. Pinned: Task 3 manual check (login with `?next=` resumes), Task 8 manual check (accept-page 401 recovery).
2. **Dead or mismatched invites** — unknown (404), non-pending (400), expired (410, after `expires_at`), wrong email (403) must each render explicit copy and never a stack trace or a blank page. Pinned: Task 1 (pytest: unknown 404; wrong-token shape), Task 8 manual checks (all four states).
3. **Role gating (presentation vs authority)** — plain member sees no invite form, no remove buttons, no delete; API error text still surfaces when rules collide stale UI. Pinned: Task 6 manual checks (member vs creator views).
4. **Bad identifiers** — `/workspaces/[id]` with a non-UUID or stranger's workspace renders not-found / no-access states (API 422/404/403 → `notFound()` or explicit state). Pinned: Task 6 manual checks.
5. **Stale prefetched pages** — after creating a workspace, accepting, or deleting, navigation is a full `window.location.assign`, matching the sign-in/out trap. Pinned: Tasks 5–8 steps say which navigation rule applies after which response.

---

### Task 1: API — `GET /api/v1/invitations/{token}` (preview)

**Files:**
- Modify: `apps/api/app/modules/invitations/router.py` (add GET `/{token}` route **after** the existing `GET /pending` — registration order keeps `/pending` unshadowed)
- Modify: `apps/api/app/modules/invitations/schemas.py` (add `InvitationPreviewRead`)
- Modify: `apps/api/app/modules/invitations/service.py` (add `get_invitation_preview`)
- Create: `apps/api/tests/modules/invitations/test_preview.py`, `apps/api/tests/modules/invitations/__init__.py` (dir exists; only add `__init__.py` if absent)

**Interfaces:**
- Consumes: existing `get_invitation_by_token`, the pending-list join pattern in `list_pending_for_user` (Invite → Workspace → inviter User).
- Produces — three things later tasks use by exact name:
  1. `service.get_invitation_preview(session, token) -> dict | None` returning `{invitation_id, workspace_id, workspace_name, inviter_email, email, role, status, expires_at, created_at}`; router route `GET /{token}` → `200 InvitationPreviewRead` or `404` `{"detail": "Invitation not found"}`. **No auth required** (token is the capability; spec §7).
  2. `service.list_pending_for_user` select and `InvitationPendingRead` schema each gain `token` (spec §7 addition #2) — the pending page's accept/decline actions (Task 7) call token-addressed routes.

- [ ] **Step 1: Write the failing test** — `test_preview.py`: (a) creates a workspace + invitation directly via the service/models, then via `client` asserts `GET /api/v1/invitations/{token}` returns 200 with exactly `{invitation_id, workspace_id, workspace_name, inviter_email, email, role, status, expires_at, created_at}` and `status == "pending"`; (b) 404 for a bogus token; (c) `GET /api/v1/invitations/pending` for the invited email includes `token` in each row.
- [ ] **Step 2: Run it** — `cd apps/api && uv run pytest tests/modules/invitations/test_preview.py -v` → expect FAIL (404 on preview; missing `token` key).
- [ ] **Step 3: Implement** — `InvitationPreviewRead` (fields per Interface); `get_invitation_preview` (clone the pending-list select: drop the email/pending filters, add `Invitation.status`); router route `GET /{token}` registered *after* `GET /pending`; `InvitationPendingRead` + select gain `token`.
- [ ] **Step 4: Run it** — same command → PASS.
- [ ] **Step 5: Full suite + lint** — `uv run pytest` (all green), `uv run ruff check app tests`.
- [ ] **Step 6: Commit** — `git add apps/api/app/modules/invitations apps/api/tests/modules/invitations && git commit -m "feat(api): invitation preview endpoint and pending-list token"`

---

### Task 2: `lib/api.ts` — types + functions + shared error response

**Files:**
- Modify: `apps/web/lib/api.ts` (append types and functions; add exported helper)

**Interfaces:** (single source for every later task — exact names)

```ts
export type ApiRole = "creator" | "admin" | "member";
export type ApiWorkspace = { id: string; name: string; created_by: string; created_at: string };
export type ApiMember = { user_id: string; email: string; role: ApiRole; joined_at: string };
export type ApiPendingInvitation = { invitation_id: string; workspace_id: string; workspace_name: string; inviter_email: string | null; email: string; role: ApiRole; token: string; expires_at: string; created_at: string };
export type ApiInvitationPreview = ApiPendingInvitation & { status: "pending" | "accepted" | "declined" | "expired" };
export type ApiInvitationCreated = { exists: boolean; invitation_id: string | null; email: string; role: ApiRole; token: string | null; expires_at: string | null; link: string | null; message?: string | null };
export type ApiAcceptedInvitation = { workspace_id: string; role: ApiRole; workspace_name: string };
```

(The `token` field on pending rows exists because Task 1 adds it to the API's pending list — spec §7 addition #2.)

Functions (all thin wrappers over `request`; `token` param is the session JWT named `token` to match existing `getMe`):

- `listWorkspaces(token: string): Promise<ApiWorkspace[]>` — GET `/api/v1/workspaces`
- `createWorkspace(token: string, name: string): Promise<ApiWorkspace>` — POST
- `getWorkspace(token: string, workspaceId: string): Promise<ApiWorkspace>` — GET `/{id}`
- `deleteWorkspace(token: string, workspaceId: string): Promise<void>` — DELETE `/{id}`
- `listMembers(token: string, workspaceId: string): Promise<ApiMember[]>`
- `removeMember(token: string, workspaceId: string, userId: string): Promise<void>`
- `checkInvitationEmail(token: string, workspaceId: string, email: string): Promise<{ exists: boolean; user_id: string | null }>`
- `createInvitation(token: string, workspaceId: string, email: string, role: "admin" | "member"): Promise<ApiInvitationCreated>`
- `getInvitationPreview(invitationToken: string): Promise<ApiInvitationPreview>` — GET `/api/v1/invitations/{invitationToken}`, **no** session token
- `listPendingInvitations(token: string): Promise<ApiPendingInvitation[]>`
- `acceptInvitation(token: string, invitationToken: string): Promise<ApiAcceptedInvitation>`
- `declineInvitation(token: string, invitationToken: string): Promise<void>`
- `export function apiErrorResponse(error: unknown): Response` — catches nothing itself; takes a caught error and returns the same `Response.json({detail, fields}, {status})` shape the auth route handlers build by hand (ApiError → its status, 0 → 502; anything else → 500 fallback). Existing auth route handlers stay untouched.

- [ ] **Step 1: Add types + functions + `apiErrorResponse`** to `lib/api.ts`, matching signatures above and the file's existing comment style.
- [ ] **Step 2: Verify** — `pnpm exec tsc --noEmit && pnpm lint && pnpm build` all clean.
- [ ] **Step 3: Commit** — `git add apps/web/lib/api.ts && git commit -m "feat(web): add workspace and invitation API client"`

---

### Task 3: `?next=` resumption after sign-in / sign-up

**Files:**
- Modify: `apps/web/app/api/auth/login/route.ts`, `apps/web/app/api/auth/signup/route.ts` (honor `next`)
- Modify: `apps/web/components/auth-form.tsx` (accept + carry `nextPath`)
- Modify: `apps/web/app/login/page.tsx`, `apps/web/app/signup/page.tsx` (read `next` from search params, pass down)

**Interfaces:**
- Consumes: nothing new.
- Produces: `AuthForm` prop `nextPath?: string` (default `"/"`); route-handler behavior — read `body.next`, accept only if it starts with `"/"` and not `"//"` (open-redirect guard), else `"/"`; respond `{ ok: true, redirect: next }`; `AuthForm` on `response.ok` does `window.location.assign(result.redirect)`.

- [ ] **Step 1: Route handlers** — validate + echo `redirect` per Interface (both files, same three lines).
- [ ] **Step 2: Pages** — server pages extract `next` from async search params (vendored convention: `PageProps<'/login'>` + `await searchParams`, string filter), pass `<AuthForm mode=… nextPath={next} />`.
- [ ] **Step 3: AuthForm** — add prop, read `redirect` from the success body, `window.location.assign(redirect ?? "/")` (keep the eslint comment about router cache).
- [ ] **Step 4: Verify** — `pnpm lint && pnpm exec tsc --noEmit && pnpm build`; then manual: visit `/login?next=/invitations` (page may 404 yet — the *redirect target* may not exist until Task 7; use `next=/account` in Task 5+, or assert only that you land on the `next` path), sign in → lands on `next` path; also `open-redirect` check: `/login?next=//evil.com` → lands on `/`.
- [ ] **Step 5: Commit** — `git add apps/web/app/api/auth apps/web/components/auth-form.tsx apps/web/app/login apps/web/app/signup && git commit -m "feat(web): support next redirects after auth"`

---

### Task 4: Mutation route handlers (`app/api/**`)

**Files (all Create):**
- `apps/web/app/api/workspaces/route.ts` — POST → `createWorkspace`
- `apps/web/app/api/workspaces/[id]/route.ts` — DELETE → `deleteWorkspace`
- `apps/web/app/api/workspaces/[id]/members/[userId]/route.ts` — DELETE → `removeMember`
- `apps/web/app/api/workspaces/[id]/invitations/check/route.ts` — POST → `checkInvitationEmail`
- `apps/web/app/api/workspaces/[id]/invitations/route.ts` — POST → `createInvitation`
- `apps/web/app/api/invitations/[token]/accept/route.ts` — POST → `acceptInvitation`
- `apps/web/app/api/invitations/[token]/decline/route.ts` — POST → `declineInvitation`

**Interfaces:**
- Consumes: Task 2 functions + `apiErrorResponse`; `getSessionToken()`; async `params` per vendored docs (`{ params }: PageProps<'/x/[seg]'>` shape → `const { id } = await params`).
- Produces (client contract, used in Tasks 5–8): every handler forwards the API's status and body `{detail, fields}`. One catch-all catch: `catch (error) { return apiErrorResponse(error); }` (500 fallback built into the helper). Unauthenticated call → forwarded 401. Body parsing follows the auth-handlers' defensive-typeof pattern; `createInvitation` forwards the API's 422 untouched when role is not `admin`/`member`.

- [ ] **Step 1: Write all seven handlers** — each is the auth-login handler's skeleton with its Task 2 function; cookie provides the bearer token.
- [ ] **Step 2: Verify** — `pnpm lint && pnpm exec tsc --noEmit && pnpm build`; then with both servers running, curl the web layer using the JWT from `curl -s -X POST localhost:8000/api/v1/auth/login …` as the cookie: `curl -s -X POST localhost:3000/api/workspaces -b "ragnest_session=$TOKEN" -H 'Content-Type: application/json' -d '{"name":"Acme"}'` → the API's 201 workspace body; same call without `-b` → 401 with `{detail: "Not authenticated"}`.
- [ ] **Step 3: Commit** — `git add apps/web/app/api && git commit -m "feat(web): add workspace and invitation mutation routes"`

---

### Task 5: `/account` extraction + Workspaces home on `/`

**Files:**
- Create: `apps/web/app/(protected)/account/page.tsx` — the current `app/page.tsx` content moved verbatim (metadata `"Your account — Ragnest"`, `instant = false`, account dl, SignOut) plus a link back to `/`.
- Modify: `apps/web/app/page.tsx` — rewritten as the Workspaces home.
- Create: `apps/web/components/create-workspace-form.tsx` — client component.

**Interfaces:**
- Consumes: `listWorkspaces`, `listPendingInvitations`, `createWorkspace`; `CreateWorkspaceForm` posts `JSON.stringify({ name })` to `/api/workspaces`, maps `fields` 422 errors onto its `Field`, on success `window.location.assign(`/workspaces/${workspace.id}`)`, surfaces `detail` otherwise.
- Produces (Task 9 E2E): `/` shows — pending banner when `listPendingInvitations().length > 0` (copy: "You have {n} pending invitation(s)" → link `"/invitations"`), workspace list as links to `/workspaces/{id}`, empty state (`"No workspaces yet. Create one to get started."`), header block per existing motif, footer: `SignOut` + link to `/account`.

- [ ] **Step 1: Create `/account`** (move; add the back-link line; keep `SignOut`).
- [ ] **Step 2: Rewrite `/`** — server component, `instant = false`, cookie → 401 → `redirect("/login")`; fetch workspaces + pending invitations via Task 2 functions; render per Interface; metadata `"Workspaces — Ragnest"`.
- [ ] **Step 3: `CreateWorkspaceForm`** — client component per Interface; `Field` for name, `Button` with `pending`.
- [ ] **Step 4: Verify** — lint/tsc/build; manual: signed-in user with no workspaces sees empty state → create "Acme" → lands on `/workspaces/{id}` (page 404s until Task 6 — acceptable interim, note it); `/account` shows the old dl content; old `/` content gone.
- [ ] **Step 5: Commit** — `git add apps/web/app apps/web/components/create-workspace-form.tsx && git commit -m "feat(web): workspaces home page and account split"`

---

### Task 6: `/workspaces/[id]` — detail, members, invite, remove, delete

**Files:**
- Create: `apps/web/app/(protected)/workspaces/[id]/page.tsx` — server page.
- Create: `apps/web/components/invite-form.tsx`, `apps/web/components/remove-member-button.tsx`, `apps/web/components/delete-workspace-button.tsx` — client components.

**Interfaces:**
- Consumes: `getWorkspace` + `listMembers` + `getMe` (Task 2 functions, exact signatures); client posts to Task 4 route paths.
- Produces (visibility matrix from spec §5 — exact gating):
  - My role = the row in `listMembers` where `member.user_id === user.id` (`getMe` supplies `user.id`); 403 from either fetch (`ApiError.status === 403`) → render "You're not a member of this workspace."; 404/422 → `notFound()` (spec Review Focus 4); 401 → `redirect("/login?next=/workspaces/{id}")`.
  - Members table: email, role chip (plain text `creator`/`admin`/`member`), joined date via `parseApiDate`.
  - `InviteForm` rendered when my role ∈ {creator, admin}: email `Field` + role select (`admin` | `member`) → `checkInvitationEmail` on submit → hint under the form when `exists === false` (`"No Ragnest account yet — they'll need to sign up with this email."`) → `createInvitation` → success block shows the full shareable URL `window.location.origin + "/invite/" + token` with a "Copy link" button (`navigator.clipboard.writeText`, shows "Copied" for 2s) — **the only "send" mechanism (spec D5)**; API `detail`s (409s, 422) render inline as alerts.
  - `RemoveMemberButton` per row where the matrix allows (see spec §5): posts DELETE `/api/workspaces/{id}/members/{user_id}`; on success `window.location.assign(`/workspaces/{id}`)`; any forwarded API detail renders inline (creator-self-remove is hidden anyway: matrix never shows it).
  - `DeleteWorkspaceButton` when my role `=== "creator"`: `confirm()` by name, POST not needed — DELETE `/api/workspaces/{id}` → on 204 `window.location.assign("/")`.
- Title: `"Acme — Ragnest"` pattern (workspace name + suffix).

- [ ] **Step 1: Server page** — renders name, created date, members table, role-derived sections; error mapping per Interface.
- [ ] **Step 2: `InviteForm`** — check → hint → invite → copyable link block; only admin/creator see it.
- [ ] **Step 3: `RemoveMemberButton` / `DeleteWorkspaceButton`** — per matrix; inline API-error rendering.
- [ ] **Step 4: Verify** — lint/tsc/build; manual, as creator: invite bob (member), copy link; as bob later add self via Task 8; creator sees Remove on bob's row, no self-remove, no Remove on creator row; member-created URL `/workspaces/{id}` visited by a non-member → not-found/no-access state; bad UUID → not-found.
- [ ] **Step 5: Commit** — `git add apps/web/app apps/web/components && git commit -m "feat(web): workspace detail with members, invites and role gates"`

---

### Task 7: `/invitations` — pending list, accept/decline

**Files:**
- Create: `apps/web/app/(protected)/invitations/page.tsx` — server page.
- Create: `apps/web/components/invitation-actions.tsx` — client component.

**Interfaces:**
- Consumes: `listPendingInvitations` (server, with `token` from Task 1) ; client posts to Task 4 routes `/api/invitations/{token}/accept` and `/api/invitations/{token}/decline`.
- Produces (what later tasks rely on):
  - `InvitationActions` client component per row, props `{ token: string }`: **Accept** → POST accept → on success `window.location.assign(`/workspaces/${body.workspace_id}`)`; **Decline** → POST decline → on 204 `window.location.assign("/invitations")`; any forwarded API `detail` (410 expired, 403 mismatch) renders inline next to the row.
  - Page rows: workspace name, `inviter_email ?? "someone"`, role chip, expiry via `parseApiDate`; empty state `"No pending invitations."`; metadata `"Invitations — Ragnest"`. Task 8's accepted-state link targets this same workspace URL pattern.

- [ ] **Step 1: Server page** per Interface.
- [ ] **Step 2: `InvitationActions`** per Interface (accept→workspace redirect, decline→list refresh, inline errors).
- [ ] **Step 3: Verify** — lint/tsc/build; manual: as bob with a live invite, `/invitations` shows the row; Decline → row disappears; invite again, Accept → lands in the workspace; late-accept of an expired invite shows the API's 410 text inline.
- [ ] **Step 4: Commit** — `git add apps/web && git commit -m "feat(web): pending invitations page with accept and decline"`

---

### Task 8: `/invite/[token]` — public accept flow

**Files:**
- Create: `apps/web/app/invite/[token]/page.tsx` — public server page (outside `(protected)`).
- Create: `apps/web/components/accept-invitation-button.tsx` — client component.

**Interfaces:**
- Consumes: `getInvitationPreview(token)` (no cookie needed); `getSessionToken()` only to decide whether the viewer has a session; Task 4 route `/api/invitations/{token}/accept`.
- Produces (states per spec §6 flow 4 — exact copy intent):
  - `status === "pending"` + no session → summary block ({workspace_name}, role, inviter_email) + copy "Sign in to accept this invitation." + two links: `/login?next=/invite/{token}` and `/signup?next=/invite/{token}` (Task 3 completes the resume).
  - `pending` + session → summary + `AcceptInvitationButton`: POST accept → success `{workspace_id}` → `window.location.assign(`/workspaces/${workspace_id}`)`; forwarded errors inline — **403** → "This invitation was sent to {preview.email} — sign in with that account." (link to `/login?next=/invite/{token}`); 400/410 → dead-state copy; network → generic.
  - `expired` → "This invitation expired on {parse date}."; `accepted` → "You're already a member of {workspace_name}." + link `/workspaces/{workspace_id}`; `declined` → "This invitation was declined."
  - 404 preview → "This invitation link isn't valid." (no stack trace).
  - The page never mutates on render (spec: reveal links must not consume invites).
  - Metadata `"Invitation — Ragnest"`.

- [ ] **Step 1: Server page** per Interface (await params; preview fetch; state branches).
- [ ] **Step 2: `AcceptInvitationButton`** per Interface.
- [ ] **Step 3: Verify** — lint/tsc/build; manual Review-Focus-2 pass, all four dead/mismatch cases plus the happy path: signed-out open → sign in via link → resumption lands back → accept → inside workspace; wrong account session → 403 copy with the target email.
- [ ] **Step 4: Commit** — `git add apps/web && git commit -m "feat(web): public invite accept flow with resume-after-auth"`

---

### Task 9: Full verification + docs + E2E walkthrough

**Files:**
- Modify: `apps/web/AGENTS.md` — Last updated + new route structure + the `?next=` and invite-link decisions.
- Modify: `apps/api/AGENTS.md` — roadmap note: web milestone for M3 done; `§14` pointers.
- Modify: `apps/api/README.md` / `apps/web/README.md` — only if a run step changed (none expected).

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Machine gates** — `cd apps/web && pnpm lint && pnpm exec tsc --noEmit && pnpm build` clean; `cd apps/api && uv run pytest && uv run ruff check app tests` clean.
- [ ] **Step 2: E2E manual script** (both servers running, two browser profiles or a fresh incognito): alice signs up → `/` empty state → creates "Acme" → workspace page → invites `bob@example.com` as member → copy link; incognito: opens `/invite/{token}` signed out → sign-up resumes via `?next=` → accept → lands in workspace → members shows both rows with roles; alice: invite existing bob again → 409 copy; bob (member) opens same workspace → no invite form/remove/delete controls (Review Focus 3); alice removes bob → 204, bob's next view 403s into not-access state; alice deletes workspace → home.
- [ ] **Step 3: Docs** — edits per Files above (small, factual).
- [ ] **Step 4: Commit** — `git add apps/web/AGENTS.md apps/api/AGENTS.md && git commit -m "docs: record web milestone for workspaces and invitations"`
