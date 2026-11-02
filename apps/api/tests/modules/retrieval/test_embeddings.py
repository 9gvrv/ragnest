import json
import math
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.modules.retrieval.constants import EMBEDDING_DIM, EMBEDDING_MODEL
from app.modules.retrieval.embeddings import (
    EmbeddingProviderError,
    GeminiEmbeddingProvider,
)

ENDPOINT_PATH = f"/v1beta/models/{EMBEDDING_MODEL}:batchEmbedContents"


def _body(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content)


def _vector(value: float = 1.0) -> list[float]:
    return [value] + [0.0] * (EMBEDDING_DIM - 1)


def _response(batch_size: int, value: float = 1.0) -> httpx.Response:
    return httpx.Response(
        200,
        json={"embeddings": [{"values": _vector(value)} for _ in range(batch_size)]},
    )


def _provider(handler) -> GeminiEmbeddingProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return GeminiEmbeddingProvider("test-key", client=client)


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


async def test_documents_use_retrieval_document_task_type_and_768_dims():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(ENDPOINT_PATH)
        assert request.headers["x-goog-api-key"] == "test-key"
        body = _body(request)
        seen.update(body["requests"][0])
        return _response(len(body["requests"]))

    provider = _provider(handler)
    vectors = await provider.embed_documents(["alpha", "beta"])
    await provider._client.aclose()

    assert len(vectors) == 2
    assert len(vectors[0]) == EMBEDDING_DIM
    assert seen["model"] == f"models/{EMBEDDING_MODEL}"
    assert seen["taskType"] == "RETRIEVAL_DOCUMENT"
    assert seen["outputDimensionality"] == EMBEDDING_DIM


async def test_query_uses_retrieval_query_task_type():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = _body(request)
        assert len(body["requests"]) == 1
        seen.update(body["requests"][0])
        return _response(1)

    provider = _provider(handler)
    vector = await provider.embed_query("what is this?")
    await provider._client.aclose()

    assert len(vector) == EMBEDDING_DIM
    assert seen["taskType"] == "RETRIEVAL_QUERY"


async def test_batches_are_split_at_sixteen():
    sizes: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = _body(request)
        sizes.append(len(body["requests"]))
        return _response(len(body["requests"]))

    provider = _provider(handler)
    vectors = await provider.embed_documents([f"text {i}" for i in range(17)])
    await provider._client.aclose()

    assert sizes == [16, 1]
    assert len(vectors) == 17


async def test_vectors_are_l2_normalised():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = _body(request)
        return _response(len(body["requests"]), value=3.0)

    provider = _provider(handler)
    vectors = await provider.embed_documents(["alpha"])
    await provider._client.aclose()

    assert _norm(vectors[0]) == pytest.approx(1.0)


async def test_dimension_mismatch_raises():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [{"values": [0.1] * 767}]})

    provider = _provider(handler)
    with pytest.raises(EmbeddingProviderError):
        await provider.embed_documents(["alpha"])
    await provider._client.aclose()


async def test_response_count_mismatch_raises():
    async def handler(request: httpx.Request) -> httpx.Response:
        return _response(1)

    provider = _provider(handler)
    with pytest.raises(EmbeddingProviderError):
        await provider.embed_documents(["alpha", "beta"])
    await provider._client.aclose()


async def test_429_is_retried(monkeypatch: pytest.MonkeyPatch):
    calls: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        body = _body(request)
        return _response(len(body["requests"]))

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.modules.retrieval.embeddings._sleep", no_sleep)

    provider = _provider(handler)
    vectors = await provider.embed_documents(["alpha"])
    await provider._client.aclose()

    assert len(vectors) == 1
    assert len(calls) == 2


async def test_non_retryable_4xx_raises(monkeypatch: pytest.MonkeyPatch):
    calls: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": "bad request"})

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.modules.retrieval.embeddings._sleep", no_sleep)

    provider = _provider(handler)
    with pytest.raises(EmbeddingProviderError):
        await provider.embed_documents(["alpha"])
    await provider._client.aclose()

    assert len(calls) == 1


def test_env_example_documents_gemini_key():
    env_example = Path(__file__).parents[3] / ".env.example"
    assert "GEMINI_API=" in env_example.read_text()
