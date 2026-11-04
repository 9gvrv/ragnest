from uuid import uuid4

from app.modules.chat import service
from app.modules.chat.constants import CHAT_EXCERPT_CHARS, NO_CONTEXT_REPLY
from app.modules.retrieval.service import SearchHit
from tests.modules.chat.conftest import insert_conversation


def _hit(index: int = 0, content: str = "alpha", filename: str = "notes.txt") -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        filename=filename,
        chunk_index=index,
        content=content,
        score=0.8,
        char_start=0,
        char_end=len(content),
    )


def test_citations_are_numbered_and_truncated():
    long_text = "a" * (CHAT_EXCERPT_CHARS + 10)

    citations = service.citations_from_hits([_hit(0, long_text), _hit(1, "short", "other.txt")])

    assert [citation["n"] for citation in citations] == [1, 2]
    assert citations[0]["excerpt"] == f"{'a' * CHAT_EXCERPT_CHARS}…"
    assert citations[1]["excerpt"] == "short"
    assert citations[1]["filename"] == "other.txt"


async def test_persist_assistant_writes_the_snapshot(session_factory, seed):
    conversation = await insert_conversation(
        session_factory, seed["workspace_id"], seed["ids"]["creator"]
    )
    assistant_id = uuid4()

    await service.persist_assistant(
        session_factory,
        assistant_id,
        conversation.id,
        content="answer [1]",
        sources=[_hit()],
        finish_reason="stop",
        model="openai/gpt-oss-120b",
    )

    async with session_factory() as session:
        messages = await service.list_messages(session, conversation.id)

    assert len(messages) == 1
    assert messages[0].id == assistant_id
    assert messages[0].content == "answer [1]"
    assert messages[0].citations[0]["filename"] == "notes.txt"
    assert messages[0].finish_reason == "stop"
    assert messages[0].model == "openai/gpt-oss-120b"


async def test_prepare_exchange_no_context_persists_both_rows(
    session_factory, seed, fake_embeddings
):
    async with session_factory() as session:
        conversation = await service.create_conversation(
            session, seed["workspace_id"], seed["ids"]["creator"]
        )

        exchange = await service.prepare_exchange(
            session,
            seed["workspace_id"],
            conversation,
            "  what is this?  ",
            fake_embeddings,
        )

        assert exchange.no_context is True
        assert exchange.plan is None
        assert exchange.sources == []
        assert conversation.title == "what is this?"

    async with session_factory() as session:
        messages = await service.list_messages(session, conversation.id)

    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "  what is this?  "
    assert messages[1].id == exchange.assistant_message_id
    assert messages[1].content == NO_CONTEXT_REPLY
    assert messages[1].finish_reason == "no_context"
