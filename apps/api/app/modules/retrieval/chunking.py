"""Offset-preserving recursive chunking.

Every chunk is an exact substring of the source text: ``content`` is always
``text[char_start:char_end]``. Splitting prefers paragraph boundaries, then
sentences, then newlines, then words, and only hard-cuts a single oversized
token.
"""

from dataclasses import dataclass

from app.modules.retrieval.constants import (
    CHUNK_OVERLAP_CHARS,
    CHUNK_TARGET_CHARS,
    MIN_CHUNK_CHARS,
)

# Tried in order. Each separator is kept at the end of the preceding span so
# that the spans tile the source text without gaps.
_SEPARATORS = ("\n\n", "\n", ". ", "! ", "? ", " ")


@dataclass(frozen=True)
class TextChunk:
    content: str
    char_start: int
    char_end: int


def chunk_text(text: str) -> list[TextChunk]:
    if not text.strip():
        raise ValueError("Cannot chunk empty text")

    spans = _split_spans(text, 0, len(text), 0)
    chunks = _pack_spans(spans)
    chunks = _merge_short_tail(chunks)

    return [
        TextChunk(content=text[start:end], char_start=start, char_end=end)
        for start, end in chunks
        if text[start:end].strip()
    ]


def _split_spans(text: str, start: int, end: int, separator_index: int) -> list[tuple[int, int]]:
    """Split ``[start, end)`` into spans no longer than the chunk target."""
    if end - start <= CHUNK_TARGET_CHARS:
        return [(start, end)]

    if separator_index >= len(_SEPARATORS):
        return [
            (cut, min(cut + CHUNK_TARGET_CHARS, end))
            for cut in range(start, end, CHUNK_TARGET_CHARS)
        ]

    separator = _SEPARATORS[separator_index]
    pieces = _split_on(text, start, end, separator)
    if len(pieces) <= 1:
        return _split_spans(text, start, end, separator_index + 1)

    spans: list[tuple[int, int]] = []
    for piece_start, piece_end in pieces:
        if piece_end - piece_start > CHUNK_TARGET_CHARS:
            spans.extend(_split_spans(text, piece_start, piece_end, separator_index + 1))
        else:
            spans.append((piece_start, piece_end))
    return spans


def _split_on(text: str, start: int, end: int, separator: str) -> list[tuple[int, int]]:
    """Split on ``separator`` keeping it attached to the preceding piece."""
    pieces: list[tuple[int, int]] = []
    position = start
    while position < end:
        found = text.find(separator, position, end)
        if found == -1:
            pieces.append((position, end))
            break
        pieces.append((position, found + len(separator)))
        position = found + len(separator)
    return pieces


def _pack_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    chunks: list[tuple[int, int]] = []
    index = 0
    total = len(spans)
    start = spans[0][0]

    while index < total:
        end = spans[index][1]
        next_index = index + 1

        while next_index < total and spans[next_index][1] - start <= CHUNK_TARGET_CHARS:
            end = spans[next_index][1]
            next_index += 1

        chunks.append((start, end))
        if next_index >= total:
            break

        # Start the next chunk at most CHUNK_OVERLAP_CHARS before the end, but
        # never so far back that it would have fit in the previous chunk.
        desired_start = end - CHUNK_OVERLAP_CHARS
        resume = index + 1
        while resume < next_index and spans[resume][1] <= desired_start:
            resume += 1
        start = max(spans[resume][0], desired_start)
        if start >= end:
            start = end - 1
        index = resume

    return chunks


def _merge_short_tail(chunks: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(chunks) > 1 and chunks[-1][1] - chunks[-1][0] < MIN_CHUNK_CHARS:
        previous_start, _ = chunks[-2]
        _, tail_end = chunks[-1]
        return [*chunks[:-2], (previous_start, tail_end)]
    return chunks
