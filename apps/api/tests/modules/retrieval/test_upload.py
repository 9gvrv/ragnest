from uuid import UUID

from sqlalchemy import select

from app.modules.retrieval.deps import get_embedding_provider
from app.modules.retrieval.models import DocumentChunk
from tests.modules.retrieval.conftest import insert_workspace


async def _upload(client, workspace_id, headers, text="alpha " * 400, filename="notes.txt"):
    return await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        files={"file": (filename, text.encode(), "text/plain")},
    )


async def _chunks(session_factory, document_id):
    async with session_factory() as session:
        return list(
            (
                await session.execute(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.chunk_index)
                )
            )
            .scalars()
            .all()
        )


async def test_upload_indexes_immediately_with_fake_provider(client, seed, session_factory):
    response = await _upload(client, seed["workspace_id"], seed["headers"]["creator"])

    assert response.status_code == 201
    body = response.json()
    # The 201 body is built before the background task runs.
    assert body["embedding_status"] == "pending"

    chunks = await _chunks(session_factory, UUID(body["id"]))
    assert chunks
    detail = await client.get(
        f"/api/v1/workspaces/{seed['workspace_id']}/documents/{body['id']}",
        headers=seed["headers"]["creator"],
    )
    assert detail.json()["embedding_status"] == "ready"
    assert detail.json()["indexed_at"] is not None
    text = detail.json()["extracted_text"]
    for chunk in chunks:
        assert chunk.content == text[chunk.char_start : chunk.char_end]


async def test_upload_stays_201_when_provider_fails(
    client, seed, session_factory, app, failing_embeddings
):
    app.dependency_overrides[get_embedding_provider] = lambda: failing_embeddings

    response = await _upload(client, seed["workspace_id"], seed["headers"]["creator"])

    assert response.status_code == 201
    body = response.json()
    assert body["embedding_status"] == "pending"

    detail = await client.get(
        f"/api/v1/workspaces/{seed['workspace_id']}/documents/{body['id']}",
        headers=seed["headers"]["creator"],
    )
    assert detail.json()["embedding_status"] == "failed"
    assert detail.json()["indexed_at"] is None
    assert await _chunks(session_factory, UUID(body["id"])) == []


async def test_list_and_detail_expose_embedding_status(client, seed):
    upload = await _upload(client, seed["workspace_id"], seed["headers"]["creator"])
    document_id = upload.json()["id"]

    listing = await client.get(
        f"/api/v1/workspaces/{seed['workspace_id']}/documents",
        headers=seed["headers"]["creator"],
    )
    assert listing.status_code == 200
    assert listing.json()[0]["embedding_status"] == "ready"
    assert "indexed_at" in listing.json()[0]

    detail = await client.get(
        f"/api/v1/workspaces/{seed['workspace_id']}/documents/{document_id}",
        headers=seed["headers"]["creator"],
    )
    assert detail.status_code == 200
    assert detail.json()["embedding_status"] == "ready"


async def test_reindex_requires_can_manage(client, seed):
    member_upload = await _upload(
        client, seed["workspace_id"], seed["headers"]["member"], filename="member.txt"
    )
    member_document_id = member_upload.json()["id"]

    admin_reindex = await client.post(
        f"/api/v1/workspaces/{seed['workspace_id']}/documents/{member_document_id}/reindex",
        headers=seed["headers"]["admin"],
    )
    assert admin_reindex.status_code == 202
    assert admin_reindex.json() == {"embedding_status": "pending"}

    creator_upload = await _upload(
        client, seed["workspace_id"], seed["headers"]["creator"], filename="creator.txt"
    )
    creator_document_id = creator_upload.json()["id"]

    member_reindex = await client.post(
        f"/api/v1/workspaces/{seed['workspace_id']}/documents/{creator_document_id}/reindex",
        headers=seed["headers"]["member"],
    )
    assert member_reindex.status_code == 403

    outsider_reindex = await client.post(
        f"/api/v1/workspaces/{seed['workspace_id']}/documents/{member_document_id}/reindex",
        headers=seed["headers"]["outsider"],
    )
    assert outsider_reindex.status_code == 403


async def test_reindex_foreign_document_is_404(client, seed, session_factory):
    upload = await _upload(client, seed["workspace_id"], seed["headers"]["creator"])
    document_id = upload.json()["id"]
    other = await insert_workspace(session_factory, seed["users"]["creator"], name="Other")

    response = await client.post(
        f"/api/v1/workspaces/{other.id}/documents/{document_id}/reindex",
        headers=seed["headers"]["creator"],
    )

    assert response.status_code == 404
