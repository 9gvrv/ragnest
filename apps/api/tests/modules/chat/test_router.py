import json
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.chat import service
from app.modules.chat.constants import NO_CONTEXT_REPLY
from tests.modules.chat.conftest import (
    insert_conversation,
    insert_message,
    insert_workspace,
)

BASE = "/api/v1/workspaces/{workspace_id}/conversations"


def _url(workspace_id) -> str:
    return BASE.format(workspace_id=workspace_id)


async def test_create_and_list_conversations(client, seed):
    workspace_id = seed["workspace_id"]
    headers = seed["headers"]["creator"]

    first = await client.post(_url(workspace_id), json={}, headers=headers)
    second = await client.post(_url(workspace_id), json={"title": "  Billing  "}, headers=headers)

    assert first.status_code == 201
    assert first.json()["title"] == "New conversation"
    assert first.json()["created_by"] == str(seed["ids"]["creator"])
    assert second.status_code == 201
    assert second.json()["title"] == "Billing"

    listed = await client.get(_url(workspace_id), headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [
        second.json()["id"],
        first.json()["id"],
    ]


async def test_detail_returns_messages_in_order(client, seed, session_factory):
    workspace_id = seed["workspace_id"]
    conversation = await insert_conversation(session_factory, workspace_id, seed["ids"]["creator"])
    citation = {
        "n": 1,
        "document_id": str(uuid4()),
        "chunk_id": str(uuid4()),
        "filename": "notes.txt",
        "chunk_index": 0,
        "char_start": 0,
        "char_end": 11,
        "excerpt": "hello world",
        "score": 0.75,
    }

    await insert_message(session_factory, conversation.id, role="user", content="hello?")
    await insert_message(
        session_factory,
        conversation.id,
        role="assistant",
        content="answer [1]",
        citations=[citation],
        model="openai/gpt-oss-120b",
        finish_reason="stop",
    )

    response = await client.get(
        f"{_url(workspace_id)}/{conversation.id}", headers=seed["headers"]["creator"]
    )

    assert response.status_code == 200
    body = response.json()
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]
    assert body["messages"][1]["citations"][0]["filename"] == "notes.txt"
    assert body["messages"][1]["finish_reason"] == "stop"


async def test_delete_conversation(client, seed):
    workspace_id = seed["workspace_id"]
    headers = seed["headers"]["creator"]
    created = await client.post(_url(workspace_id), json={}, headers=headers)
    conversation_id = created.json()["id"]

    deleted = await client.delete(f"{_url(workspace_id)}/{conversation_id}", headers=headers)
    assert deleted.status_code == 204

    missing = await client.get(f"{_url(workspace_id)}/{conversation_id}", headers=headers)
    assert missing.status_code == 404


async def test_other_members_get_404(client, seed):
    workspace_id = seed["workspace_id"]
    created = await client.post(_url(workspace_id), json={}, headers=seed["headers"]["creator"])
    conversation_id = created.json()["id"]

    for role in ("member", "admin"):
        response = await client.get(
            f"{_url(workspace_id)}/{conversation_id}", headers=seed["headers"][role]
        )
        assert response.status_code == 404

    deleted = await client.delete(
        f"{_url(workspace_id)}/{conversation_id}", headers=seed["headers"]["member"]
    )
    assert deleted.status_code == 404


async def test_outsiders_get_403(client, seed):
    workspace_id = seed["workspace_id"]
    created = await client.post(_url(workspace_id), json={}, headers=seed["headers"]["creator"])
    conversation_id = created.json()["id"]

    response = await client.get(
        f"{_url(workspace_id)}/{conversation_id}", headers=seed["headers"]["outsider"]
    )

    assert response.status_code == 403


async def test_another_workspace_conversation_is_invisible(client, seed, session_factory):
    other = await insert_workspace(session_factory, seed["users"]["creator"])
    other_conversation = await insert_conversation(
        session_factory, other.id, seed["ids"]["creator"]
    )

    response = await client.get(
        f"{_url(seed['workspace_id'])}/{other_conversation.id}",
        headers=seed["headers"]["creator"],
    )

    assert response.status_code == 404


async def test_service_filters_by_author_and_workspace(session_factory, seed):
    async with session_factory() as session:
        conversation = await service.create_conversation(
            session, seed["workspace_id"], seed["ids"]["creator"]
        )
        assert conversation.title == "New conversation"

        listed = await service.list_conversations(
            session, seed["workspace_id"], seed["ids"]["member"]
        )
        assert listed == []

        with pytest.raises(HTTPException) as raised:
            await service.get_conversation(
                session, seed["workspace_id"], conversation.id, seed["ids"]["member"]
            )

    assert raised.value.status_code == 404


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        name = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        if name is not None and data is not None:
            events.append((name, data))
    return events


async def _upload(client, workspace_id, headers, text: str, filename: str) -> dict:
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        files={"file": (filename, text.encode(), "text/plain")},
    )
    assert response.status_code == 201
    return response.json()


async def _create(client, workspace_id, headers, title: str | None = None) -> dict:
    response = await client.post(
        _url(workspace_id), json={"title": title} if title else {}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def _ask(client, workspace_id, conversation_id, headers, content: str):
    return await client.post(
        f"{_url(workspace_id)}/{conversation_id}/messages",
        headers=headers,
        json={"content": content},
    )


async def test_streams_grounded_answer_and_persists(client, seed, fake_llm):
    headers = seed["headers"]["creator"]
    workspace_id = seed["workspace_id"]
    await _upload(client, workspace_id, headers, "alpha alpha alpha", "alpha.txt")
    conversation = await _create(client, workspace_id, headers)

    response = await _ask(client, workspace_id, conversation["id"], headers, "alpha")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    assert events[0][0] == "sources"
    assert events[-1][0] == "done"
    assert events[0][1]["no_context"] is False
    assert events[0][1]["sources"][0]["n"] == 1
    assert events[0][1]["sources"][0]["filename"] == "alpha.txt"
    tokens = "".join(data["delta"] for name, data in events if name == "token")
    assert tokens == "Grounded answer [1]"
    assert events[-1][1]["cited"] == [1]
    assert events[-1][1]["finish_reason"] == "stop"

    detail = await client.get(f"{_url(workspace_id)}/{conversation['id']}", headers=headers)
    messages = detail.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "alpha"
    assert messages[1]["content"] == "Grounded answer [1]"
    assert messages[1]["citations"][0]["filename"] == "alpha.txt"
    assert messages[1]["citations"][0]["excerpt"] == "alpha alpha alpha"
    assert messages[1]["finish_reason"] == "stop"
    assert messages[1]["model"] == "openai/gpt-oss-120b"
    assert fake_llm.calls


async def test_empty_workspace_refuses_without_calling_the_model(client, seed, fake_llm):
    headers = seed["headers"]["creator"]
    workspace_id = seed["workspace_id"]
    conversation = await _create(client, workspace_id, headers)

    response = await _ask(client, workspace_id, conversation["id"], headers, "anything")

    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert [name for name, _ in events] == ["sources", "token", "done"]
    assert events[0][1]["sources"] == []
    assert events[0][1]["no_context"] is True
    assert events[1][1]["delta"] == NO_CONTEXT_REPLY
    assert events[2][1]["finish_reason"] == "no_context"
    assert fake_llm.calls == []

    detail = await client.get(f"{_url(workspace_id)}/{conversation['id']}", headers=headers)
    messages = detail.json()["messages"]
    assert messages[1]["content"] == NO_CONTEXT_REPLY
    assert messages[1]["finish_reason"] == "no_context"
    assert messages[1]["citations"] == []


async def test_title_comes_from_the_first_question(client, seed):
    headers = seed["headers"]["creator"]
    workspace_id = seed["workspace_id"]
    conversation = await _create(client, workspace_id, headers)

    await _ask(
        client,
        workspace_id,
        conversation["id"],
        headers,
        "  How do I   retry?  ",
    )

    detail = await client.get(f"{_url(workspace_id)}/{conversation['id']}", headers=headers)
    assert detail.json()["title"] == "How do I retry?"


async def _messages(client, workspace_id, conversation_id, headers) -> list[dict]:
    detail = await client.get(f"{_url(workspace_id)}/{conversation_id}", headers=headers)
    assert detail.status_code == 200
    return detail.json()["messages"]


def _use_llm(app, provider) -> None:
    from app.modules.chat.deps import get_llm_provider

    app.dependency_overrides[get_llm_provider] = lambda: provider


async def test_rate_limited_provider_returns_429_and_keeps_the_question(
    client, seed, app, session_factory
):
    from tests.conftest import FailingLLMProvider

    headers = seed["headers"]["creator"]
    workspace_id = seed["workspace_id"]
    await _upload(client, workspace_id, headers, "alpha alpha", "alpha.txt")
    conversation = await _create(client, workspace_id, headers)
    _use_llm(app, FailingLLMProvider(status_code=429))

    response = await _ask(client, workspace_id, conversation["id"], headers, "alpha")

    assert response.status_code == 429
    assert response.json() == {"detail": "Answer model is rate limited"}
    messages = await _messages(client, workspace_id, conversation["id"], headers)
    assert [message["role"] for message in messages] == ["user"]
    assert messages[0]["content"] == "alpha"


async def test_provider_outage_returns_503_and_keeps_the_question(client, seed, app):
    from tests.conftest import FailingLLMProvider

    headers = seed["headers"]["creator"]
    workspace_id = seed["workspace_id"]
    await _upload(client, workspace_id, headers, "alpha alpha", "alpha.txt")
    conversation = await _create(client, workspace_id, headers)
    _use_llm(app, FailingLLMProvider(status_code=500))

    response = await _ask(client, workspace_id, conversation["id"], headers, "alpha")

    assert response.status_code == 503
    assert response.json() == {"detail": "Answer model unavailable"}
    messages = await _messages(client, workspace_id, conversation["id"], headers)
    assert [message["role"] for message in messages] == ["user"]


async def test_failure_after_first_token_ends_with_error_and_partial_row(client, seed, fake_llm):
    headers = seed["headers"]["creator"]
    workspace_id = seed["workspace_id"]
    await _upload(client, workspace_id, headers, "alpha alpha", "alpha.txt")
    conversation = await _create(client, workspace_id, headers)
    fake_llm.fail_after = 1

    response = await _ask(client, workspace_id, conversation["id"], headers, "alpha")

    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert [name for name, _ in events] == ["sources", "token", "error"]
    assert "".join(data["delta"] for name, data in events if name == "token") == "Grounded "
    assert events[-1][1] == {"detail": "Answer model failed"}

    messages = await _messages(client, workspace_id, conversation["id"], headers)
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "Grounded "
    assert messages[1]["finish_reason"] == "error"
    assert messages[1]["citations"][0]["filename"] == "alpha.txt"


async def test_empty_completion_is_503_not_a_blank_assistant(client, seed, fake_llm):
    headers = seed["headers"]["creator"]
    workspace_id = seed["workspace_id"]
    await _upload(client, workspace_id, headers, "alpha alpha", "alpha.txt")
    conversation = await _create(client, workspace_id, headers)
    fake_llm.deltas = []

    response = await _ask(client, workspace_id, conversation["id"], headers, "alpha")

    assert response.status_code == 503
    assert response.json() == {"detail": "Answer model unavailable"}
    messages = await _messages(client, workspace_id, conversation["id"], headers)
    assert [message["role"] for message in messages] == ["user"]


async def test_embedding_failure_persists_nothing(client, seed, app, failing_embeddings, fake_llm):
    from app.modules.retrieval.deps import get_embedding_provider

    headers = seed["headers"]["creator"]
    workspace_id = seed["workspace_id"]
    conversation = await _create(client, workspace_id, headers)
    app.dependency_overrides[get_embedding_provider] = lambda: failing_embeddings

    response = await _ask(client, workspace_id, conversation["id"], headers, "alpha")

    assert response.status_code == 503
    assert response.json() == {"detail": "Embedding provider unavailable"}
    assert fake_llm.calls == []
    assert await _messages(client, workspace_id, conversation["id"], headers) == []
