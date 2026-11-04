import json

import httpx
import pytest

from app.modules.chat.llm import (
    LLMDelta,
    LLMFinish,
    LLMMessage,
    LLMProviderError,
    OpenAICompatibleLLMProvider,
)

BASE_URL = "https://groq.test/openai/v1"


def _sse(chunks: list[dict] | None = None, *, done: bool = True) -> bytes:
    body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks or [])
    if done:
        body += "data: [DONE]\n\n"
    return body.encode()


def _provider(client: httpx.AsyncClient, **overrides) -> OpenAICompatibleLLMProvider:
    options = {
        "api_key": "test-key",
        "base_url": BASE_URL,
        "model": "openai/gpt-oss-120b",
        "reasoning_effort": "low",
    }
    options.update(overrides)
    return OpenAICompatibleLLMProvider(client=client, **options)


async def _collect(
    provider: OpenAICompatibleLLMProvider,
    *,
    max_output_tokens: int = 64,
) -> list[object]:
    messages = [LLMMessage("user", "hello")]
    return [event async for event in provider.stream(messages, max_output_tokens=max_output_tokens)]


async def test_request_shape_and_stream_events():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=_sse(
                [
                    {"choices": [{"delta": {"content": "Hello"}}]},
                    {"choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}]},
                ]
            ),
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        events = await _collect(_provider(client), max_output_tokens=32)

    assert seen["url"] == f"{BASE_URL}/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    body = seen["body"]
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["stream"] is True
    assert body["temperature"] == 0.2
    assert body["max_completion_tokens"] == 32
    assert body["reasoning_effort"] == "low"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert [event.text for event in events if isinstance(event, LLMDelta)] == ["Hello", " world"]
    assert events[-1] == LLMFinish("stop")


async def test_reasoning_and_null_content_are_ignored():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse(
                [
                    {"choices": [{"delta": {"reasoning": "thinking"}}]},
                    {"choices": [{"delta": {"content": None}}]},
                    {"choices": [{"delta": {"content": "answer"}}]},
                ]
            ),
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        events = await _collect(_provider(client))

    assert [event.text for event in events if isinstance(event, LLMDelta)] == ["answer"]


async def test_sse_comments_and_split_lines_are_handled():
    def handler(_request: httpx.Request) -> httpx.Response:
        body = (
            ": keep-alive\r\n"
            "\r\n"
            'data: {"choices":[{"delta":{"content":"one"}}]}\r\n'
            "\r\n"
            'data: {"choices":[{"delta":{"content":"two"},"finish_reason":"length"}]}\r\n'
            "\r\n"
            "data: [DONE]\r\n\r\n"
        )
        return httpx.Response(
            200,
            content=body.encode(),
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        events = await _collect(_provider(client))

    assert [event.text for event in events if isinstance(event, LLMDelta)] == ["one", "two"]
    assert events[-1] == LLMFinish("length")


async def test_blank_reasoning_effort_is_omitted():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=_sse([{"choices": [{"delta": {"content": "ok"}}]}]),
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await _collect(_provider(client, reasoning_effort=""))

    assert "reasoning_effort" not in seen["body"]


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_http_errors_carry_the_status(status: int):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "nope"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMProviderError) as raised:
            await _collect(_provider(client))

    assert raised.value.status_code == status


async def test_transport_error_becomes_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMProviderError):
            await _collect(_provider(client))


async def test_malformed_chunk_is_an_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"data: {not json}\n\n",
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMProviderError):
            await _collect(_provider(client))


async def test_empty_completion_is_an_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse([]),
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMProviderError):
            await _collect(_provider(client))
