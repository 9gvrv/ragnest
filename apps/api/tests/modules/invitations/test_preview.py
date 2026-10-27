from app.modules.auth.security import create_access_token
from app.modules.invitations.service import create_invitation
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole

PREVIEW_KEYS = {
    "invitation_id",
    "workspace_id",
    "workspace_name",
    "inviter_email",
    "email",
    "role",
    "status",
    "expires_at",
    "created_at",
}


async def seed_invitation(session_factory, invited_email="bob@example.com") -> dict:
    async with session_factory() as session:
        inviter = User(email="alice@example.com", password_hash="not-used")
        invited = User(email=invited_email, password_hash="not-used")
        session.add_all([inviter, invited])
        await session.flush()

        workspace = Workspace(name="Acme", created_by=inviter.id)
        session.add(workspace)
        await session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=inviter.id,
                role=WorkspaceRole.CREATOR,
            )
        )
        await session.commit()

        invitation = await create_invitation(
            session, workspace.id, inviter.id, invited_email, WorkspaceRole.MEMBER
        )
        return {
            "token": invitation.token,
            "invitation_id": str(invitation.id),
            "workspace_id": str(workspace.id),
            "invited_id": str(invited.id),
        }


async def test_preview_returns_invitation_details(client, session_factory):
    seed = await seed_invitation(session_factory)

    resp = await client.get(f"/api/v1/invitations/{seed['token']}")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == PREVIEW_KEYS
    assert body["invitation_id"] == seed["invitation_id"]
    assert body["workspace_id"] == seed["workspace_id"]
    assert body["workspace_name"] == "Acme"
    assert body["inviter_email"] == "alice@example.com"
    assert body["email"] == "bob@example.com"
    assert body["role"] == "member"
    assert body["status"] == "pending"


async def test_preview_unknown_token_returns_404(client):
    resp = await client.get("/api/v1/invitations/not-a-real-token")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Invitation not found"}


async def test_pending_list_includes_token(client, session_factory):
    seed = await seed_invitation(session_factory)
    headers = {"Authorization": f"Bearer {create_access_token(seed['invited_id'])}"}

    resp = await client.get("/api/v1/invitations/pending", headers=headers)

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["token"] == seed["token"]
