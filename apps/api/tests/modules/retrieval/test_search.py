from uuid import UUID

import pytest
from sqlalchemy import select

from app.modules.retrieval.constants import EMBEDDING_DIM, EMBEDDING_MODEL
from app.modules.retrieval.deps import get_embedding_provider
from app.modules.retrieval.models import DocumentChunk
from tests.modules.retrieval.conftest import insert_document, insert_workspace

RESULT_KEYS = {
    "chunk_id",
    "document_id",
    "filename",
    "chunk_index",
    "content",
    "score",
    "char_start",
    "char_end",
}


async def _upload(client, workspace_id, headers, text, filename):
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        files={"file": (filename, text.encode(), "text/plain")},
    )
    assert response.status_code == 201
    return response.json()


async def _search(client, workspace_id, headers, payload):
    return await client.post(
        f"/api/v1/workspaces/{workspace_id}/search",
        headers=headers,
        json=payload,
    )


async def test_search_ranks_matching_chunk_first(client, seed):
    headers = seed["headers"]["creator"]
    workspace_id = seed["workspace_id"]
    await _upload(client, workspace_id, headers, "beta beta beta", "beta.txt")
    alpha = await _upload(client, workspace_id, headers, "alpha alpha alpha", "alpha.txt")

    response = await _search(client, workspace_id, headers, {"query": "alpha", "top_k": 5})

    assert response.status_code == 200
    results = response.json()
    assert results
    assert set(results[0]) == RESULT_KEYS
    assert results[0]["document_id"] == alpha["id"]
    assert "alpha" in results[0]["content"]


async def test_search_is_workspace_scoped(client, seed, session_factory):
    headers = seed["headers"]["creator"]
    workspace_a = seed["workspace_id"]
    workspace_b = await insert_workspace(session_factory, seed["users"]["creator"], name="Beta")

    doc_a = await _upload(client, workspace_a, headers, "alpha alpha alpha", "a.txt")
    doc_b = await _upload(client, workspace_b.id, headers, "alpha alpha alpha", "b.txt")

    response_a = await _search(client, workspace_a, headers, {"query": "alpha"})
    response_b = await _search(client, workspace_b.id, headers, {"query": "alpha"})

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert {r["document_id"] for r in response_a.json()} == {doc_a["id"]}
    assert {r["document_id"] for r in response_b.json()} == {doc_b["id"]}


async def test_search_respects_top_k(client, seed):
    headers = seed["headers"]["creator"]
    await _upload(client, seed["workspace_id"], headers, "alpha " * 2000, "long.txt")

    response = await _search(client, seed["workspace_id"], headers, {"query": "alpha", "top_k": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_search_empty_workspace_returns_empty_list(client, seed):
    response = await _search(
        client, seed["workspace_id"], seed["headers"]["creator"], {"query": "alpha"}
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "   "},
        {"query": "alpha", "top_k": 0},
        {"query": "alpha", "top_k": 21},
        {"query": 123},
    ],
)
async def test_search_rejects_invalid_input(client, seed, payload):
    response = await _search(client, seed["workspace_id"], seed["headers"]["creator"], payload)

    assert response.status_code == 422


async def test_search_ignores_other_embedding_models(client, seed, session_factory):
    document = await insert_document(
        session_factory, seed["workspace_id"], seed["ids"]["creator"], text="alpha alpha"
    )
    async with session_factory() as session:
        session.add(
            DocumentChunk(
                workspace_id=seed["workspace_id"],
                document_id=document.id,
                chunk_index=0,
                content="alpha alpha",
                char_start=0,
                char_end=11,
                embedding=[1.0] + [0.0] * (EMBEDDING_DIM - 1),
                embedding_model="some-other-model",
            )
        )
        await session.commit()

    response = await _search(
        client, seed["workspace_id"], seed["headers"]["creator"], {"query": "alpha"}
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_search_provider_failure_returns_503(client, seed, app, failing_embeddings):
    app.dependency_overrides[get_embedding_provider] = lambda: failing_embeddings

    response = await _search(
        client, seed["workspace_id"], seed["headers"]["creator"], {"query": "alpha"}
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Embedding provider unavailable"}


async def test_search_non_member_returns_403(client, seed):
    response = await _search(
        client, seed["workspace_id"], seed["headers"]["outsider"], {"query": "alpha"}
    )

    assert response.status_code == 403


async def test_search_score_matches_cosine_similarity(client, seed, session_factory):
    headers = seed["headers"]["creator"]
    uploaded = await _upload(
        client, seed["workspace_id"], headers, "alpha alpha alpha", "alpha.txt"
    )

    response = await _search(client, seed["workspace_id"], headers, {"query": "alpha", "top_k": 20})

    results = response.json()
    assert results
    assert results[0]["document_id"] == uploaded["id"]
    assert results[0]["score"] == pytest.approx(1.0)
    assert results[0]["content"] == "alpha alpha alpha"
    assert (results[0]["char_start"], results[0]["char_end"]) == (0, 17)


async def test_search_ties_are_stable(client, seed, session_factory):
    headers = seed["headers"]["creator"]
    first = await insert_document(
        session_factory, seed["workspace_id"], seed["ids"]["creator"], text="alpha alpha"
    )
    second = await insert_document(
        session_factory, seed["workspace_id"], seed["ids"]["creator"], text="alpha alpha"
    )
    vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    async with session_factory() as session:
        session.add_all(
            [
                DocumentChunk(
                    workspace_id=seed["workspace_id"],
                    document_id=document_id,
                    chunk_index=0,
                    content="alpha alpha",
                    char_start=0,
                    char_end=11,
                    embedding=vector,
                    embedding_model=EMBEDDING_MODEL,
                )
                for document_id in (first.id, second.id)
            ]
        )
        await session.commit()

    response = await _search(client, seed["workspace_id"], headers, {"query": "alpha", "top_k": 20})

    results = response.json()
    assert [r["document_id"] for r in results] == sorted([str(first.id), str(second.id)])


class _FixedQueryProvider:
    def __init__(self, vector):
        self._vector = vector

    async def embed_documents(self, texts):
        raise AssertionError("not used")

    async def embed_query(self, text):
        return self._vector


async def test_search_chunks_are_ordered_by_score(client, seed, session_factory, app):
    # Two chunks with different similarities to a fixed query vector.
    document = await insert_document(
        session_factory, seed["workspace_id"], seed["ids"]["creator"], text="alpha beta"
    )
    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedQueryProvider(query_vector)
    async with session_factory() as session:
        session.add_all(
            [
                DocumentChunk(
                    workspace_id=seed["workspace_id"],
                    document_id=document.id,
                    chunk_index=0,
                    content="alpha",
                    char_start=0,
                    char_end=5,
                    embedding=[0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2),
                    embedding_model=EMBEDDING_MODEL,
                ),
                DocumentChunk(
                    workspace_id=seed["workspace_id"],
                    document_id=document.id,
                    chunk_index=1,
                    content="beta",
                    char_start=6,
                    char_end=10,
                    embedding=[1.0] + [0.0] * (EMBEDDING_DIM - 1),
                    embedding_model=EMBEDDING_MODEL,
                ),
            ]
        )
        await session.commit()

    results = (
        await _search(client, seed["workspace_id"], seed["headers"]["creator"], {"query": "alpha"})
    ).json()

    assert [r["chunk_index"] for r in results] == [1, 0]
    assert results[0]["score"] > results[1]["score"]
    assert UUID(results[0]["document_id"]) == document.id
    assert len(await _all_chunks(session_factory)) == 2


async def _all_chunks(session_factory):
    async with session_factory() as session:
        return list((await session.execute(select(DocumentChunk))).scalars().all())
