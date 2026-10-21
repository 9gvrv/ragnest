# Ragnest API — Milestone 3: Workspaces, Roles & Invitations — Design

**Date:** 2026-10-19  
**Status:** Draft for review  
**Milestone:** 3 of N  
**Based on:** Milestone 2 (Users & Auth) — complete

---

## 1. Why this exists

Milestone 2 established user accounts and authentication (`users` table, signup/login, `get_current_user` dependency). Everything beyond auth needs tenancy — a boundary that scopes documents, chat, and membership.

Following the decision in Milestone 2 (§7), **the workspace is the tenant**. We are not introducing organizations. Workspaces are the container for future features (documents, retrieval, chat). This milestone adds workspaces, membership with roles, and invitations.

---

## 2. Intent

- Establish workspace-as-tenant model consistent with the existing module architecture.
- Enable users to create and manage their own workspaces.
- Support inviting others to collaborate with clear role boundaries.
- Keep the scope minimal while setting up the right primitives for future milestones.

---

## 3. Goals (this milestone)

- `workspaces` table with creator tracking.
- `workspace_members` table to model membership (user + workspace + role).
- `invitations` table to track pending invites by email with secure tokens.
- `POST /api/v1/workspaces` — create a workspace (creator becomes member with `creator` role).
- `GET /api/v1/workspaces` — list workspaces the current user belongs to.
- `GET /api/v1/workspaces/{workspace_id}` — get workspace details (if member).
- `DELETE /api/v1/workspaces/{workspace_id}` — delete workspace (only creator).
- `GET /api/v1/workspaces/{workspace_id}/members` — list members (members can view; creators/admins manage).
- `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}` — remove a member (permissions depend on role; cannot remove self in some cases; creator can remove others).
- `POST /api/v1/workspaces/{workspace_id}/invitations/check` — check if email belongs to existing user (lookup by email).
- `POST /api/v1/workspaces/{workspace_id}/invitations` — create/send invitation (if email exists, create pending invite; if not, return info to send invite via mail).
- `POST /api/v1/invitations/{token}/accept` — accept invitation (works whether user has account or needs to signup first).
- `POST /api/v1/invitations/{token}/decline` — decline invitation.
- `GET /api/v1/invitations/pending` — list pending invitations for current user (by email match).
- Role enum: `creator`, `admin`, `member`.
- Workspace-scoped permission checks via dependencies.
- Tests using in-memory SQLite (no Neon).

---

## 4. Non-goals (this milestone)

- Documents, chat, retrieval, embeddings, RAG.
- Organization/team grouping above workspaces.
- Email sending implementation (we return invite link/token; actual SMTP can be stubbed or added later).
- Password reset, email verification outside of invite acceptance flow.
- Refresh tokens, OAuth.
- Workspace settings beyond basic name.

---

## 5. Anti-goals (this milestone is a failure if…)

- Invitations allow privilege escalation (role is enforced at creation/acceptance).
- A non-member can access workspace data/endpoints.
- Creator can be removed from their own workspace.
- Email uniqueness logic for invites is case-sensitive or inconsistent.
- `password_hash` appears in any response or log.
- Tests touch Neon or depend on `.env`.
- We restructure existing `auth`/`users` modules unnecessarily.

---

## 6. Constraints

- Python 3.13, `uv`, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic.
- Follow locked structure: single `app/` package, features under `app/modules/<feature>/`.
- Reuse `app/db/base.py` (`Base` + `TimestampMixin`).
- Identical behavior on SQLite (tests) and Postgres/Neon (dev).
- Never raw `DATABASE_URL` — use `settings.database_url` + `settings.database_connect_args`.
- All endpoints under `/api/v1`.
- FastAPI dependency style: `Annotated[Type, Depends(...)]`.
- Hashing: `pwdlib[argon2]`. Tokens use `PyJWT` with `SECRET_KEY` (HS256).
- Ruff clean (`line-length = 100`, `target-version = "py313"`).
- Do not commit `.env`.

---

## 7. Tenancy model (workspace-as-tenant)

From Milestone 2: workspace becomes the tenant. All future resources (documents, chunks, conversations) will reference `workspace_id`.

Relationships:
- A `User` can belong to many `Workspaces` via `WorkspaceMember`.
- A `Workspace` has many `Members` (Users) via `WorkspaceMember`.
- A `Workspace` has one `Creator` (User) — stored as `created_by`.
- An `Invitation` belongs to a `Workspace` and is created by an `Inviter` (User).

Default flow: sign up → create first workspace (creator). No org-less state exists.

---

## 8. Data model (decided)

### Enums

```python
import enum

class WorkspaceRole(str, enum.Enum):
    CREATOR = "creator"
    ADMIN = "admin"
    MEMBER = "member"
```

### Tables

```python
# workspaces
# ──────────
# id             Uuid  pk
# name           str
# created_by     Uuid  fk users.id (ondelete RESTRICT or SET NULL? creator must exist; but we don't delete users in this milestone)
# created_at / updated_at  ts (TimestampMixin)

# workspace_members
# ─────────────────
# id             Uuid  pk (or composite; pk is fine for flexibility)
# workspace_id   Uuid  fk workspaces.id ondelete CASCADE
# user_id        Uuid  fk users.id ondelete CASCADE
# role           enum(str) values (creator|admin|member)
# joined_at      ts (default now)
# unique(workspace_id, user_id)

# invitations
# ───────────
# id             Uuid  pk
# workspace_id   Uuid  fk workspaces.id ondelete CASCADE
# inviter_id     Uuid  fk users.id ondelete SET NULL (nullable if inviter removed later)
# email          str   (lowercase, indexed)
# role           enum(str) values (admin|member) — creator cannot be invited
# token          str   unique (secure random token)
# status         enum(str) values (pending|accepted|declined|expired)
# expires_at     ts
# created_at     ts (TimestampMixin or explicit)
```

Decisions:
- **UUID primary keys** for all tables (consistency with `users`).
- **Email normalized to lowercase** on write (store `email.lower()`).
- **Creator role only via creation** — `invitations` should not allow inviting as `creator`. Only `admin` or `member`.
- **On delete**: deleting workspace cascades to members and invitations. Deleting user: cascade members? Or restrict? If user deleted, their memberships go away; inviter_id nullable on invitations.
- **Token**: cryptographically secure random token (e.g. `secrets.token_urlsafe(32)`) stored as string, unique index.
- **Expires at**: e.g. 7 days from creation (configurable default).
- **Status**: track state; invitations can only be accepted if `pending` and not expired.
- **joined_at** on membership (separate from `created_at` mixin if we want clarity; mixin gives `created_at/updated_at` — membership is a join record; `joined_at` = `created_at` is fine).
- **Index on invitations.email** for lookup by email when user checks pending invites.

---

## 9. Invite acceptance semantics (decided)

**Users can accept invites whether they have an account or not.** But they must be authenticated with an account whose email matches the invitation.

Flow:
1. User receives invite link containing token.
2. `POST /api/v1/invitations/{token}/accept` requires authentication (`get_current_user`).
3. The invitation’s `email` (lowercased) must equal `current_user.email` (lowercased). Otherwise 403.
4. If invitation is expired or not `pending` → 410/400.
5. On success: create `workspace_members` row (idempotent if already exists), set `invitations.status = "accepted"`, return 200 with `{workspace_id, role, workspace_name}`.

Also: when inviting, if email not found, we still create invitation record (or at least return token/link) so the invite can be shared via mail. The system doesn’t send email in this milestone (non-goal); we just provide the link/token.

---

## 10. Roles & permissions

Roles (in order of privilege): `CREATOR > ADMIN > MEMBER`

Permissions:
- **Creator**: full control of workspace. Can delete workspace. Can invite users (admin/member). Can remove members (excluding creator; cannot remove self). Can view all.
- **Admin**: can invite users (admin/member). Can remove members (excluding creator and other admins). Can view members and workspace.
- **Member**: can view workspace and members. Cannot invite, cannot remove others, cannot delete workspace.

Permission rules:
- Creating workspace: any authenticated user.
- Listing workspaces: only those you belong to.
- Viewing workspace: must be member.
- Deleting workspace: only creator.
- Listing members: must be member.
- Inviting: creator or admin (cannot invite as creator).
- Removing member: creator can remove anyone except creator; admin can remove members only (not admins, not creator). Cannot remove self.
- Accepting invite: must be authenticated with matching email.

---

## 11. Module layout

Create new modules: `workspaces` and `invitations`. Follow existing pattern.

```
app/modules/
├── users/        (existing)
├── auth/         (existing)
├── workspaces/
│   ├── __init__.py
│   ├── models.py      # Workspace, WorkspaceMember, WorkspaceRole
│   ├── schemas.py     # WorkspaceCreate, WorkspaceRead, MemberRead
│   ├── router.py      # workspace CRUD + members + invites check/create
│   ├── service.py     # business logic
│   └── deps.py        # workspace-scoped deps
└── invitations/
    ├── __init__.py
    ├── models.py      # Invitation, InvitationStatus
    ├── schemas.py     # schemas for invites
    ├── router.py      # accept/decline, pending list
    ├── service.py     # invite logic, token generation
    └── deps.py        # (optional)
```

Notes:
- `workspaces` router handles workspace CRUD, member listing/removal, and invitation creation/checking (scoped to workspace).
- `invitations` router handles accepting/declining via token and listing pending invites for current user (not workspace-scoped).
- Models registered via `app/db/models.py` aggregator (import new models).

---

## 12. API surface

All under `/api/v1`. Auth required unless stated.

| Method | Path | Auth | Body | Success | Errors |
|---|---|---|---|---|---|
| POST | `/workspaces` | Bearer | `{name}` | `201 {id, name, created_by, created_at}` | `401`, `422` |
| GET | `/workspaces` | Bearer | — | `200 [{id, name, created_by, created_at}]` | `401` |
| GET | `/workspaces/{workspace_id}` | Bearer | — | `200 {id, name, created_by, created_at}` | `401`, `403`, `404` |
| DELETE | `/workspaces/{workspace_id}` | Bearer | — | `204` | `401`, `403`, `404` |
| GET | `/workspaces/{workspace_id}/members` | Bearer | — | `200 [{user_id, email, role, joined_at}]` | `401`, `403`, `404` |
| DELETE | `/workspaces/{workspace_id}/members/{user_id}` | Bearer | — | `204` | `401`, `403`, `404`, `409` |
| POST | `/workspaces/{workspace_id}/invitations/check` | Bearer | `{email}` | `200 {exists: bool, user_id?: uuid}` | `401`, `403`, `422` |
| POST | `/workspaces/{workspace_id}/invitations` | Bearer | `{email, role}` | `201 {exists, invitation_id?, email, role, token?, expires_at?, link?, message?}` | `401`, `403`, `409`, `422` |
| GET | `/invitations/pending` | Bearer | — | `200 [{invitation_id, workspace_id, workspace_name, inviter_email?, email, role, expires_at, created_at}]` | `401` |
| POST | `/invitations/{token}/accept` | Bearer | — | `200 {workspace_id, role, workspace_name}` | `401`, `403`, `404`, `410`, `400` |
| POST | `/invitations/{token}/decline` | Bearer | — | `204` | `404`, `410`, `400` |

Notes:
- Emails are normalized to lowercase throughout.
- `invitations/create` creates invitation record regardless of whether user exists; response indicates `exists`. Return includes `token` and `link` (API path is fine).
- Cannot invite existing member (409). Cannot invite with pending invitation to same workspace (409). Cannot invite as `creator` (422).
- Accept is idempotent: if already member, still accept invitation and return membership info (200). Returns 403 if email mismatch, 404 if token not found, 410 if expired, 400 if not pending.
- Decline sets status to declined if pending; returns appropriate errors if expired/not pending.

---

## 13. Testing strategy

Extend test harness (in-memory async SQLite). Create test modules mirroring structure.

Cases to cover:
- **Workspace CRUD**: create workspace → creator is member with role `creator`. List workspaces includes it. Get workspace as member succeeds. Delete as creator succeeds (204). Delete as non-creator fails (403). Non-member cannot get workspace (403).
- **Membership**: member can list members. Creator can remove member (204). Admin can remove member (204). Cannot remove creator (403). Cannot remove self (409). Admin cannot remove admin/creator (403). Non-admin cannot remove others (403).
- **Invitations check**: existing email returns `exists: true, user_id`. Non-existing returns `exists: false`. Case-insensitive.
- **Invitations create**: invite existing user → 201 with token. Invite non-existing → 201 with token and `exists: false`. Cannot invite existing member (409). Cannot invite as creator (422). Cannot invite same email twice pending (409). Only admin/creator can create (403).
- **Accept invite**: authenticated user with matching email accepts → membership created, status accepted (200). Accept when already member → idempotent (200). Accept with wrong email → 403. Accept expired token → 410 (and status becomes expired). Accept already accepted → 400. Accept declined → 400. Token not found → 404.
- **Decline invite**: pending → 204. Expired pending → 410. Already declined/accepted → 400.
- **Pending invites**: user sees invites where email matches (case-insensitive). Shows workspace name and inviter email.
- **No password_hash leakage** in any response.
- **Cascade**: deleting workspace removes members and invitations.
- **Emails normalized to lowercase** throughout storage/comparisons.

---

## 14. Left to builder (not decided here)

- Exact permission implementation details (separate deps as specified).
- Whether to create invitation record even if user doesn’t exist (we do; response indicates).
- Token format (urlsafe `secrets.token_urlsafe(32)`) — fine.
- Expiration duration (default 7 days; constant is fine).
- Exact error detail strings (keep consistent and generic where appropriate).
- `joined_at` as explicit field (we have it) vs mixin created_at — explicit is clearer for membership.
- Link format returned (path like `/invitations/{token}/accept` is fine).
- Idempotent accept behavior when already member (return existing membership) — done.

---

## 15. Where this goes next

After Milestone 3: **Milestone 4 — Documents**. Upload txt/pdf/md, store metadata, extract text — all scoped to workspace (tenant). Membership/roles from this milestone gate access.