import asyncio
import math
from typing import Any, Protocol

import httpx

from app.modules.retrieval.constants import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
    EMBEDDING_MAX_ATTEMPTS,
    EMBEDDING_MODEL,
    EMBEDDING_TIMEOUT_SECONDS,
)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


class EmbeddingProviderError(Exception):
    """Raised when the embedding provider cannot return valid vectors."""


class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class GeminiEmbeddingProvider:
    """Calls Gemini's ``batchEmbedContents`` endpoint.

    A client may be injected for tests; otherwise every public call owns and
    closes its own client.
    """

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        client, owns_client = self._acquire_client()
        try:
            vectors: list[list[float]] = []
            for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
                batch = texts[start : start + EMBEDDING_BATCH_SIZE]
                vectors.extend(await self._embed_batch(client, batch, "RETRIEVAL_DOCUMENT"))
            return vectors
        finally:
            if owns_client:
                await client.aclose()

    async def embed_query(self, text: str) -> list[float]:
        client, owns_client = self._acquire_client()
        try:
            vectors = await self._embed_batch(client, [text], "RETRIEVAL_QUERY")
            return vectors[0]
        finally:
            if owns_client:
                await client.aclose()

    def _acquire_client(self) -> tuple[httpx.AsyncClient, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT_SECONDS), True

    async def _embed_batch(
        self,
        client: httpx.AsyncClient,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        payload = {
            "requests": [
                {
                    "model": f"models/{EMBEDDING_MODEL}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": task_type,
                    "outputDimensionality": EMBEDDING_DIM,
                }
                for text in texts
            ]
        }
        url = f"{_API_ROOT}/{EMBEDDING_MODEL}:batchEmbedContents"
        response = await self._post_with_retry(client, url, payload)

        embeddings = response.json().get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise EmbeddingProviderError("Embedding response count mismatch")

        vectors: list[list[float]] = []
        for embedding in embeddings:
            values = embedding.get("values") if isinstance(embedding, dict) else None
            if not isinstance(values, list) or len(values) != EMBEDDING_DIM:
                raise EmbeddingProviderError("Embedding dimension mismatch")
            floats = [float(value) for value in values]
            if not all(math.isfinite(value) for value in floats):
                raise EmbeddingProviderError("Embedding contains non-finite values")
            vectors.append(_normalise(floats))
        return vectors

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(EMBEDDING_MAX_ATTEMPTS):
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"x-goog-api-key": self._api_key},
                )
            except httpx.TransportError as exc:
                last_error = exc
            else:
                if response.status_code < 400:
                    return response
                if response.status_code != 429 and response.status_code < 500:
                    raise EmbeddingProviderError(
                        f"Embedding provider returned {response.status_code}"
                    )
                last_error = EmbeddingProviderError(
                    f"Embedding provider returned {response.status_code}"
                )

            if attempt < EMBEDDING_MAX_ATTEMPTS - 1:
                await _sleep(2**attempt)

        raise EmbeddingProviderError("Embedding provider unavailable") from last_error


async def _sleep(seconds: float) -> None:
    # Indirection so tests can avoid real backoff sleeps.
    await asyncio.sleep(seconds)


def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]
