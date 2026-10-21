# Workspaces, Roles & Invitations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This project runs in mentor mode:** the human writes the code; the mentor explains, reviews, and only writes files when a step says so. Steps are still written as concrete, verifiable actions.

**Goal:** Add workspaces, membership with roles, and invitations to the Ragnest API. Workspaces are the tenant (no organizations). Users can create workspaces, invite others, and accept invites whether they have an account or not.

**Architecture:** Three new domain entities — `Workspace`, `WorkspaceMember`, `WorkspaceRole` (enum), `Invitation`, `InvitationStatus` (enum). Modules: `app/modules/workspaces/` and `app/modules/invitations/`, each following the established pattern (models, schemas, router, service, deps where needed). Both routers mounted under `/api/v1`.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2 (+ `email-validator`), SQLAlchemy 2.0 async, Alembic, `PyJWT`, `secrets` for tokens, pytest + httpx/aiosqlite.

**Spec:** `docs/superpowers/specs/2026-10-19-workspaces-roles-invitations-design.md`

## Global Constraints

- Python 3.13, `uv`, single top-level `app/` package — **no `src/` layout**.
- Domain features in `app/modules/<feature>/`; each owns its router, schemas, models, service.
- Reuse `app/db/base.py` — `Base` (naming convention) and `TimestampMixin` (`created_at`, `updated_at`).
- Identical behavior on **SQLite (tests)** and **Postgres/Neon (dev)** — use SQLAlchemy generic types (`Uuid`, string-backed enums), never Postgres-only types.
- Any DB engine uses `settings.database_url` + `settings.database_connect_args` — never raw `DATABASE_URL`.
- Tests never touch Neon; use in-memory async SQLite.
- `password_hash` must never appear in a response or log.
- All endpoints under `/api/v1`; `GET /health` stays at root.
- FastAPI dependency style: `Annotated[Type, Depends(...)]`.
- Ruff: `line-length = 100`, `target-version = "py313"`; `uv run ruff check .` must stay clean.
- Do not commit `.env`.

## Review Focus

Key behaviors to get right:

1. **Email normalization.** All emails stored and compared in lowercase. Invite `Alice@Example.com`, check `alice@example.com`, accept as `ALICE@EXAMPLE.COM` must work.
2. **Role boundaries.** Only `admin`/`member` can be invited (creator never). Creator cannot be removed. Admin cannot remove creator or other admins? (per spec: Admin can remove members; not admins, not creator).
3. **Invite semantics.** Accept requires authenticated user with matching email. Unauthenticated cannot accept directly.
4. **Idempotency.** Accepting when already a member doesn’t create duplicate or error.
5. **Expiration.** Expired tokens return 410. Non-pending statuses return 400/410 appropriately.
6. **Case-insensitive uniqueness.** Creating invites/memberships must not create duplicates due to case.
7. **Cascades.** Deleting workspace cascades to members and invitations.

## Task 1: Models for workspaces, members, invitations

Create models and enums. Register them via `app/db/models.py` aggregator.

**Files:**

- Create: `app/modules/workspaces/__init__.py`
- Create: `app/modules/workspaces/models.py`
- Create: `app/modules/invitations/__init__.py`
- Create: `app/modules/invitations/models.py`
- Modify: `app/db/models.py` (import new models)
- Test: `tests/modules/workspaces/__init__.py`, `tests/modules/workspaces/test_models.py`

**Interfaces:**

`app/modules/workspaces/models.py`:

- `WorkspaceRole` enum (str, Enum): `CREATOR="creator"`, `ADMIN="admin"`, `MEMBER="member"`
- `Workspace` (Base, TimestampMixin): `id` uuid pk default uuid4, `name` str, `created_by` uuid FK to `users.id` (RESTRICT on delete), `created_at/updated_at`
- `WorkspaceMember` (Base): `id` uuid pk default uuid4, `workspace_id` uuid FK to `workspaces.id` (CASCADE), `user_id` uuid FK to `users.id` (CASCADE), `role` WorkspaceRole, `joined_at` datetime (server default now), unique `(workspace_id, user_id)`

`app/modules/invitations/models.py`:

- `InvitationStatus` enum (str, Enum): `PENDING="pending"`, `ACCEPTED="accepted"`, `DECLINED="declined"`, `EXPIRED="expired"`
- `Invitation` (Base, TimestampMixin): `id` uuid pk, `workspace_id` FK CASCADE, `inviter_id` FK to `users.id` (SET NULL, nullable), `email` str (lowercase), `role` WorkspaceRole (admin/member only conceptually), `token` str unique indexed, `status` InvitationStatus, `expires_at` datetime, index on email.

- [ ] **Step 1: Write failing tests for models**
- [ ] **Step 2: Create models**
- [ ] **Step 3: Update aggregator**
- [ ] **Step 4: Generate and apply migration**
- [ ] **Step 5: Verify tests pass**

---

## Task 2: Workspace schemas

Create Pydantic schemas for workspaces and members.

**Files:**

- Create: `app/modules/workspaces/schemas.py`
- Test: `tests/modules/workspaces/test_schemas.py`

**Schemas:**

- `WorkspaceCreate`: `name` (str, min_length 1, max 255)
- `WorkspaceRead`: `id` uuid, `name` str, `created_by` uuid, `created_at` datetime
- `MemberRead`: `user_id` uuid, `email` str, `role` WorkspaceRole, `joined_at` datetime

- [ ] **Step 1: Create schemas**
- [ ] **Step 2: Add schema tests**

---

## Task 3: Invitation schemas

**Files:**

- Create: `app/modules/invitations/schemas.py`
- Test: `tests/modules/invitations/test_schemas.py`

**Schemas:**

- `InvitationCheckRequest`: `email` EmailStr
- `InvitationCheckResponse`: `exists` bool, `user_id` UUID | None
- `InvitationCreateRequest`: `email` EmailStr, `role` WorkspaceRole (validate not CREATOR)
- `InvitationCreateResponse`: includes `exists`, `invitation_id`, `email`, `role`, `token`, `expires_at`, `link`, `message`
- `InvitationPendingRead`: fields as in API
- `InvitationAcceptResponse`: `workspace_id, role, workspace_name`

- [ ] **Step 1: Create schemas with validation**
- [ ] **Step 2: Add tests**

---

## Task 4: Workspace dependencies (permissions)

Create deps for workspace-scoped access control.

**Files:**

- Create: `app/modules/workspaces/deps.py`

**Deps:**

- `get_workspace(workspace_id, session) -> Workspace`
- `require_workspace_member(workspace_id, session, current_user) -> WorkspaceMember`
- `require_workspace_admin_or_creator(...) -> WorkspaceMember`
- `require_workspace_creator(...) -> WorkspaceMember`

- [ ] **Step 1: Implement deps**

---

## Task 5: Workspace service

Business logic for workspace operations.

**Files:**

- Create: `app/modules/workspaces/service.py`

**Functions:**

- `create_workspace(session, name, creator_user) -> Workspace`
- `list_workspaces_for_user(session, user_id) -> list[Workspace]`
- `list_members(session, workspace_id) -> list[dict]`
- `remove_member(session, workspace_id, target_user_id, actor_member) -> None`

- [ ] **Step 1: Implement service with permission rules (cannot remove creator, cannot remove self, role checks)**
- [ ] **Step 2: Add service tests**

---

## Task 6: Invitations service

Implement business logic for invitations.

**Files:**

- Create: `app/modules/invitations/service.py`

**Functions:**

- `check_user_exists(session, email) -> User | None`
- `create_invitation(session, workspace_id, inviter_id, email, role, expires_days=7) -> Invitation`
- `get_invitation_by_token(session, token) -> Invitation | None`
- `accept_invitation(session, invitation, user) -> WorkspaceMember`
- `decline_invitation(session, invitation) -> None`
- `list_pending_for_user(session, user) -> list[dict]`

- [ ] **Step 1: Implement service (normalize emails, token generation, expiration checks, idempotency, prevent duplicates)**
- [ ] **Step 2: Add service tests**

---

## Task 7: Workspace router

Create CRUD, members, and invitation endpoints scoped to workspace.

**Files:**

- Create: `app/modules/workspaces/router.py`

**Routes:**

- `POST /workspaces` (create), `GET /workspaces` (list), `GET /workspaces/{id}` (get), `DELETE /workspaces/{id}` (delete)
- `GET /workspaces/{id}/members` (list), `DELETE /workspaces/{id}/members/{user_id}` (remove)
- `POST /workspaces/{id}/invitations/check`, `POST /workspaces/{id}/invitations` (create)

- [ ] **Step 1: Implement router using deps and services**

## Task 8: Invitations router

Create endpoints for accepting/declining and listing pending invites.

**Files:**

- Create: `app/modules/invitations/router.py`

**Routes (under /api/v1/invitations):**

- `GET /pending` → list pending invitations for current user (by email). Requires auth. Returns list of `InvitationPendingRead`.
- `POST /{token}/accept` → accept invitation. Requires auth. Returns `InvitationAcceptResponse`. Enforces email match.
- `POST /{token}/decline` → decline invitation. Requires no auth? Or auth? Better require auth - user should be logged in to act on their invite. But invite is tied to email; if not logged in, they can’t match. Require auth. Returns 204.

Use `get_current_user`, `get_db`.

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.deps import get_current_user
from app.modules.invitations import schemas, service
from app.modules.users.models import User

router = APIRouter(prefix="/invitations", tags=["invitations"])
```

- [ ] **Step 1: Implement router**

Routes:

- `@router.get("/pending", response_model=list[schemas.InvitationPendingRead])`
- `@router.post("/{token}/accept", response_model=schemas.InvitationAcceptResponse)`
- `@router.post("/{token}/decline", status_code=status.HTTP_204_NO_CONTENT)`

For accept: load invitation by token (404 if not found). Call service.accept_invitation. Return workspace info - need to load workspace name.

---

## Task 9: Wire routers into API

Register the new routers in the aggregate router.

**Files:**

- Modify: `app/api/router.py`

Add imports and includes for `workspaces.router` and `invitations.router`. Both mounted under `/api/v1` (prefix already applied at aggregate level? The aggregate adds `/api/v1` in main or router - check existing pattern. Looking at how it's structured: in Milestone 2, both routers added to api_router; main.py includes api_router. The prefix `/api/v1` is applied when including - see main or how done. But in the codebase as-is, auth router has prefix `/auth` in its own router; api_router includes them. The full path becomes `/api/v1/auth/...` if api_router is included with prefix? Or just included. Check: `app/api/router.py` likely creates `api_router = APIRouter()` and includes feature routers; then in `main.py`, `app.include_router(api_router, prefix="/api/v1")`. That’s the pattern.)

So in `app/api/router.py`:

```python
from app.api.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.workspaces.router import router as workspaces_router
from app.modules.invitations.router import router as invitations_router

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(workspaces_router)
api_router.include_router(invitations_router)
```

Also ensure health stays at root (not under /api/v1) - health router is included as-is.

- [ ] **Step 1: Update router.py**

---

## Task 10: Model registration & migration check

Ensure all models are imported in `app/db/models.py`. We did this in Task 1 - verify completeness (Workspace, WorkspaceMember, Invitation). Also ensure Invitation imports WorkspaceRole or uses string enum properly.

Also regenerate migration if needed? We created one in Task 1. That’s fine.

---

## Task 11: Integration tests - workspaces CRUD

Create comprehensive tests following existing test patterns.

**Files:**

- Create: `tests/modules/workspaces/test_workspaces.py`
- Create: `tests/modules/invitations/test_invitations.py`

Test cases as per testing strategy in spec.

### Workspaces tests

- Create workspace: returns 201, creator becomes member
- List workspaces: shows only member workspaces
- Get workspace: member can access, non-member gets 403
- Delete workspace: creator can delete (204), non-creator gets 403
- Members list: member can view
- Remove member: creator removes member (204), cannot remove creator (403), admin rules

### Invitations tests

- Check existing email returns exists true with user_id
- Check non-existing returns exists false
- Create invite for existing user → 201 with token
- Create invite for non-existing → still creates/returns token (per our design)
- Cannot invite existing member → 409
- Cannot invite as creator → 422
- Cannot create duplicate pending invite → 409
- Accept invite as matching authenticated user → 200, membership created
- Accept with wrong email → 403
- Accept expired → 410
- Accept when already member → idempotent (200)
- Decline → 204
- Pending list shows invites for user’s email
- Case-insensitive handling throughout

Also verify no `password_hash` appears in any response.

- [ ] **Step 1: Write workspace CRUD tests**

- [ ] **Step 2: Write invitations flow tests**

- [ ] **Step 3: All new tests pass**

---

## Task 12: Verification

Run full test suite, lint, format, type check basics.

**Commands:**

```bash
cd /home/gvrv/ragnest/apps/api
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest -v
uv run alembic current
```

All tests must pass (existing + new). No ruff violations.

- [ ] **Step 1: Lint and format**

- [ ] **Step 2: Run all tests**

- [ ] **Step 3: Verify migrations**

---

## Notes

- `joined_at` uses server default in model (datetime.now(timezone.utc)); works on both SQLite and Postgres.
- Token is `secrets.token_urlsafe(32)` — URL-safe, sufficient entropy.
- Email normalization: always `.lower().strip()` on write and comparisons.
- Idempotent accept: if already member, we still mark invitation accepted (if it was pending) — reasonable.
- For the “send invite via mail” case when email doesn’t exist: we return token and link; actual email sending is non-goal. That matches requirement.
- Cascade deletes: workspace deletion cascades to members and invitations (FK with CASCADE). User deletion affects memberships (CASCADE) and invitations (SET NULL for inviter_id).
- Creator cannot be removed — enforced in remove_member. Also cannot invite as creator.

## Acceptance Criteria

- All new tables exist and migrations apply cleanly.
- All API endpoints behave as specified.
- Permissions correctly enforced (403/404 as appropriate).
- Email case-insensitive throughout.
- No `password_hash` leakage in any response.
- Full test suite passes; ruff clean; format clean.
