from uuid import UUID

from app.modules.documents.models import Document

from .conftest import insert_document, insert_workspace


def documents_url(workspace_id) -> str:
    return f"/api/v1/workspaces/{workspace_id}/documents"


async def upload(client, seed, uploader: str, filename="notes.txt", text=b"hello"):
    return await client.post(
        documents_url(seed["workspace_id"]),
        headers=seed["headers"][uploader],
        files={"file": (filename, text, "text/plain")},
    )


async def test_creator_deletes_another_members_document(client, seed):
    upload_resp = await upload(client, seed, "member")
    document_id = upload_resp.json()["id"]

    resp = await client.delete(
        f"{documents_url(seed['workspace_id'])}/{document_id}",
        headers=seed["headers"]["creator"],
    )

    assert resp.status_code == 204


async def test_admin_deletes_another_members_document(client, seed):
    upload_resp = await upload(client, seed, "member")
    document_id = upload_resp.json()["id"]

    resp = await client.delete(
        f"{documents_url(seed['workspace_id'])}/{document_id}",
        headers=seed["headers"]["admin"],
    )

    assert resp.status_code == 204


async def test_member_cannot_delete_another_members_document(client, seed, session_factory):
    upload_resp = await upload(client, seed, "admin")
    document_id = upload_resp.json()["id"]

    resp = await client.delete(
        f"{documents_url(seed['workspace_id'])}/{document_id}",
        headers=seed["headers"]["member"],
    )

    assert resp.status_code == 403

    async with session_factory() as session:
        assert await session.get(Document, UUID(document_id)) is not None


async def test_foreign_workspace_document_returns_404(client, seed, session_factory):
    other_workspace = await insert_workspace(session_factory, seed["users"]["outsider"])
    foreign = await insert_document(
        session_factory,
        other_workspace.id,
        seed["ids"]["outsider"],
        filename="foreign.txt",
    )
    url = f"{documents_url(seed['workspace_id'])}/{foreign.id}"

    detail = await client.get(url, headers=seed["headers"]["member"])
    delete = await client.delete(url, headers=seed["headers"]["member"])

    assert detail.status_code == 404
    assert detail.json() == {"detail": "Document not found"}
    assert delete.status_code == 404

    async with session_factory() as session:
        assert await session.get(Document, foreign.id) is not None
