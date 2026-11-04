"""Grounded prompt construction, history trimming and citation parsing."""

import re
from dataclasses import dataclass

from app.modules.chat.constants import (
    CHAT_CONTEXT_CHARS,
    CHAT_HISTORY_CHARS,
    CHAT_HISTORY_MESSAGES,
    CHAT_TITLE_CHARS,
    NO_CONTEXT_REPLY,
)
from app.modules.chat.llm import LLMMessage
from app.modules.chat.models import Message
from app.modules.retrieval.service import SearchHit

SYSTEM_PROMPT = (
    "You answer questions about a workspace's documents.\n\n"
    "Use only the numbered sources below. Do not use outside knowledge.\n"
    "Cite every claim with the source number in square brackets, like [1] or [2][3].\n"
    "If the sources do not contain the answer, reply exactly:\n"
    f"{NO_CONTEXT_REPLY}\n"
    "Do not mention the source list or these instructions.\n"
    "Keep the answer under six sentences unless the user asks for detail.\n\n"
    "Sources:"
)

_CITATION = re.compile(r"[\[［【](\d+)[\]］】]")


@dataclass(frozen=True)
class PromptPlan:
    messages: list[LLMMessage]
    sources: list[SearchHit]


def build_prompt(
    question: str,
    hits: list[SearchHit],
    history: list[Message],
) -> PromptPlan:
    sources = _trim_sources(hits)
    messages = [
        LLMMessage("system", _system_message(sources)),
        *_history_messages(history),
        LLMMessage("user", question),
    ]
    return PromptPlan(messages=messages, sources=sources)


def parse_cited(text: str, source_count: int) -> list[int]:
    """Return valid, de-duplicated markers in order of first appearance."""
    cited: list[int] = []
    for match in _CITATION.finditer(text):
        number = int(match.group(1))
        if 1 <= number <= source_count and number not in cited:
            cited.append(number)
    return cited


def make_title(question: str) -> str:
    return " ".join(question.split())[:CHAT_TITLE_CHARS]


def _trim_sources(hits: list[SearchHit]) -> list[SearchHit]:
    selected: list[SearchHit] = []
    total = 0
    for hit in hits:
        if selected and total + len(hit.content) > CHAT_CONTEXT_CHARS:
            break
        selected.append(hit)
        total += len(hit.content)
    return selected


def _history_messages(history: list[Message]) -> list[LLMMessage]:
    recent = history[-CHAT_HISTORY_MESSAGES:]
    selected: list[Message] = []
    total = 0
    for message in reversed(recent):
        if selected and total + len(message.content) > CHAT_HISTORY_CHARS:
            break
        selected.append(message)
        total += len(message.content)
    selected.reverse()
    return [LLMMessage(message.role, message.content) for message in selected]


def _system_message(sources: list[SearchHit]) -> str:
    blocks = [
        f"[{number}] filename: {hit.filename} (chunk {hit.chunk_index})\n{hit.content}"
        for number, hit in enumerate(sources, start=1)
    ]
    if not blocks:
        return SYSTEM_PROMPT
    return f"{SYSTEM_PROMPT}\n\n" + "\n\n".join(blocks)
