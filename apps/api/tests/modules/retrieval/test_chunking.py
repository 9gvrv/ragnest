import itertools

import pytest

from app.modules.retrieval.chunking import chunk_text
from app.modules.retrieval.constants import CHUNK_TARGET_CHARS, MIN_CHUNK_CHARS


def test_chunks_are_exact_slices():
    text = "Paragraph one.\n\nParagraph two is longer.\n\nParagraph three."
    for chunk in chunk_text(text):
        assert chunk.content == text[chunk.char_start : chunk.char_end]


def test_chunks_cover_the_document():
    chunks = chunk_text("A" * 5000)
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == 5000


def test_no_chunk_exceeds_the_bound():
    chunks = chunk_text("word " * 2000)
    assert all(len(c.content) <= CHUNK_TARGET_CHARS + MIN_CHUNK_CHARS for c in chunks)


def test_consecutive_chunks_overlap():
    chunks = chunk_text("word " * 2000)
    assert any(c2.char_start < c1.char_end for c1, c2 in itertools.pairwise(chunks))


def test_paragraphs_are_preferred_over_mid_word_cuts():
    text = "alpha " * 100 + "\n\n" + "beta " * 100
    chunks = chunk_text(text)
    assert any(c.content.lstrip().startswith("beta") for c in chunks)


def test_unicode_offsets_are_preserved():
    text = "héllo 👋\n\n" + "naïve café " * 200
    for chunk in chunk_text(text):
        assert chunk.content == text[chunk.char_start : chunk.char_end]


def test_whitespace_only_chunks_are_dropped():
    chunks = chunk_text("alpha\n\n\n\n\n\nbeta")
    assert all(c.content.strip() for c in chunks)


def test_blank_text_raises():
    with pytest.raises(ValueError):
        chunk_text("   \n\n  ")
