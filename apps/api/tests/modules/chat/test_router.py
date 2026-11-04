from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.chat import service
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
