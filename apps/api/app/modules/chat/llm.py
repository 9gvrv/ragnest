"""Generation provider: an OpenAI-compatible Chat Completions client.

Groq speaks the OpenAI wire format, so this is one small ``httpx`` client rather
than a provider SDK. It mirrors ``GeminiEmbeddingProvider``: an injected client
for tests, otherwise one client per call.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

from app.modules.chat.constants import CHAT_MAX_OUTPUT_TOKENS, CHAT_TEMPERATURE


class LLMProviderError(Exception):
    """Raised when generation cannot start or cannot be streamed."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class LLMMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMDelta:
    """One non-empty piece of visible answer text."""

    text: str


@dataclass(frozen=True)
class LLMFinish:
    """The provider's finish reason, sent exactly once at the end."""

    finish_reason: str


LLMEvent = LLMDelta | LLMFinish


class LLMProvider(Protocol):
    def stream(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = CHAT_MAX_OUTPUT_TOKENS,
    ) -> AsyncIterator[LLMEvent]: ...


class OpenAICompatibleLLMProvider:
    """Streams Chat Completions deltas from an OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str = "",
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._client = client
        self._timeout = httpx.Timeout(timeout, connect=10.0)

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int = CHAT_MAX_OUTPUT_TOKENS,
    ) -> AsyncIterator[LLMEvent]:
        payload = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "temperature": CHAT_TEMPERATURE,
            "max_completion_tokens": max_output_tokens,
            "stream": True,
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort

        client, owns_client = self._acquire_client()
        produced = False
        finish_reason = "stop"
        try:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as response:
                if response.status_code >= 400:
                    raise LLMProviderError(
                        f"LLM provider returned {response.status_code}",
                        status_code=response.status_code,
                    )

                async for line in response.aiter_lines():
                    data = _sse_data(line)
                    if data is None:
                        continue
                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise LLMProviderError("Malformed LLM stream chunk") from exc
                    if not isinstance(chunk, dict):
                        raise LLMProviderError("Malformed LLM stream chunk")
                    if chunk.get("error"):
                        raise LLMProviderError("LLM provider stream error")

                    choice = (chunk.get("choices") or [{}])[0]
                    if not isinstance(choice, dict):
                        continue

                    # ``delta.reasoning`` is deliberately ignored: chain of
                    # thought must never reach the user.
                    delta = choice.get("delta") or {}
                    text = delta.get("content")
                    if isinstance(text, str) and text:
                        produced = True
                        yield LLMDelta(text)

                    reason = choice.get("finish_reason")
                    if isinstance(reason, str) and reason:
                        finish_reason = reason
        except httpx.TransportError as exc:
            raise LLMProviderError("LLM provider unavailable") from exc
        finally:
            if owns_client:
                await client.aclose()

        if not produced:
            raise LLMProviderError("LLM provider returned no content")
        yield LLMFinish(finish_reason)

    def _acquire_client(self) -> tuple[httpx.AsyncClient, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.AsyncClient(timeout=self._timeout), True


def _sse_data(line: str) -> str | None:
    """Return the payload of one SSE ``data:`` line, or None to ignore it."""
    line = line.strip()
    if not line or line.startswith(":") or not line.startswith("data:"):
        return None
    return line[len("data:") :].strip()
