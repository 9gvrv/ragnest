from uuid import uuid4

from app.modules.chat.constants import (
    CHAT_CONTEXT_CHARS,
    CHAT_HISTORY_CHARS,
    CHAT_TITLE_CHARS,
    NO_CONTEXT_REPLY,
)
from app.modules.chat.llm import LLMMessage
from app.modules.chat.models import Message
from app.modules.chat.prompts import build_prompt, make_title, parse_cited
from app.modules.retrieval.service import SearchHit


def _hit(index: int, content: str, filename: str = "notes.txt") -> SearchHit:
    return SearchHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        filename=filename,
        chunk_index=index,
        content=content,
        score=0.9,
        char_start=0,
        char_end=len(content),
    )


def _message(role: str, content: str) -> Message:
    return Message(conversation_id=uuid4(), role=role, content=content, citations=[])


def test_sources_are_numbered_and_question_is_last():
    hits = [_hit(0, "alpha"), _hit(1, "beta", "other.md")]

    plan = build_prompt("what?", hits, [])

    assert plan.sources == hits
    system = plan.messages[0]
    assert system.role == "system"
    assert "[1] filename: notes.txt (chunk 0)\nalpha" in system.content
    assert "[2] filename: other.md (chunk 1)\nbeta" in system.content
    assert plan.messages[-1] == LLMMessage("user", "what?")


def test_system_prompt_contains_the_refusal():
    plan = build_prompt("what?", [], [])

    assert NO_CONTEXT_REPLY in plan.messages[0].content


def test_context_trim_drops_the_tail():
    first = _hit(0, "a" * (CHAT_CONTEXT_CHARS - 10))
    second = _hit(1, "b" * 100)

    plan = build_prompt("q", [first, second], [])

    assert plan.sources == [first]
    assert "[1] filename:" in plan.messages[0].content
    assert "[2] filename:" not in plan.messages[0].content


def test_an_oversized_first_source_is_kept():
    oversized = _hit(0, "x" * (CHAT_CONTEXT_CHARS + 1))

    plan = build_prompt("q", [oversized], [])

    assert plan.sources == [oversized]


def test_history_keeps_the_last_six():
    history = [_message("user", f"m{index}") for index in range(8)]

    plan = build_prompt("q", [], history)

    body = plan.messages[1:-1]
    assert [message.content for message in body] == [f"m{index}" for index in range(2, 8)]


def test_history_char_cap_drops_the_oldest():
    half = CHAT_HISTORY_CHARS // 2
    history = [
        _message("user", "a" * half),
        _message("assistant", "b" * half),
        _message("user", "c"),
    ]

    plan = build_prompt("q", [], history)

    body = plan.messages[1:-1]
    assert [message.content for message in body] == ["b" * half, "c"]


def test_parse_cited_keeps_valid_unique_markers():
    assert parse_cited("a [1] b [2] [1] [99] [0]", 2) == [1, 2]
    assert parse_cited("no markers", 3) == []


def test_parse_cited_accepts_full_width_brackets():
    assert parse_cited("a 【1】 b ［2］ c [3]", 3) == [1, 2, 3]


def test_make_title_collapses_and_truncates():
    assert make_title("  hello \n world  ") == "hello world"
    assert len(make_title("x" * 200)) == CHAT_TITLE_CHARS
