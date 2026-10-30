from pathlib import Path

import pytest

from app.modules.documents import extraction
from app.modules.documents.extraction import (
    MAX_UPLOAD_BYTES,
    Extracted,
    ExtractionError,
    TooLarge,
    UnprocessableDocument,
    UnsupportedType,
    extract,
    safe_filename,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_txt_extracts_and_reports_plain_text():
    data = fixture("sample.txt")

    result = extract("sample.txt", data)

    assert isinstance(result, Extracted)
    assert result.content_type == "text/plain"
    assert result.page_count is None
    assert result.text == data.decode("utf-8-sig")
    assert result.char_count == len(result.text)
    assert result.size_bytes == len(data)


def test_markdown_extracts_as_markdown():
    result = extract("sample.md", fixture("sample.md"))

    assert result.content_type == "text/markdown"
    assert result.page_count is None
    assert "Grounded answers." in result.text


def test_pdf_extracts_pages_and_counts_them():
    result = extract("two-page.pdf", fixture("two-page.pdf"))

    assert result.content_type == "application/pdf"
    assert result.page_count == 2
    assert "First page of the sample." in result.text
    assert "Second page of the sample." in result.text


def test_uppercase_extension_is_accepted():
    result = extract("A.PDF", fixture("two-page.pdf"))

    assert result.content_type == "application/pdf"
    assert result.page_count == 2


def test_path_in_filename_is_reduced_to_basename():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename(r"..\..\windows\system.ini") == "system.ini"


def test_unsupported_extension_raises_415():
    with pytest.raises(UnsupportedType) as excinfo:
        extract("wrong.bin", fixture("wrong.bin"))

    assert excinfo.value.status_code == 415


def test_oversize_bytes_raise_413():
    with pytest.raises(TooLarge) as excinfo:
        extract("big.txt", b"a" * (MAX_UPLOAD_BYTES + 1))

    assert excinfo.value.status_code == 413


def test_empty_file_raises_422():
    with pytest.raises(UnprocessableDocument) as excinfo:
        extract("empty.txt", b"")

    assert excinfo.value.status_code == 422


def test_invalid_utf8_raises_422():
    with pytest.raises(UnprocessableDocument) as excinfo:
        extract("latin1.txt", b"\xff\xfe\x00hello")

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == "Text must be UTF-8"


def test_whitespace_only_text_raises_422():
    with pytest.raises(UnprocessableDocument):
        extract("blank.txt", b" \n\t \r\n")


def test_text_free_pdf_raises_422():
    with pytest.raises(UnprocessableDocument) as excinfo:
        extract("scanned.pdf", fixture("scanned.pdf"))

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == "No text could be extracted"


def test_corrupt_pdf_raises_422():
    with pytest.raises(UnprocessableDocument) as excinfo:
        extract("corrupt.pdf", b"%PDF-1.4 not really a pdf")

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == "Could not read PDF"


def test_too_many_pages_raises_422(monkeypatch):
    monkeypatch.setattr(extraction, "MAX_PDF_PAGES", 2)

    with pytest.raises(UnprocessableDocument) as excinfo:
        extract("three-page.pdf", fixture("three-page.pdf"))

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == "PDF has too many pages"


def test_long_text_is_truncated_to_cap(monkeypatch):
    monkeypatch.setattr(extraction, "MAX_TEXT_CHARS", 10)

    result = extract("long.txt", b"abcdefghijklmno")

    assert result.text == "abcdefghij"
    assert result.char_count == 10


def test_extraction_error_is_the_shared_base():
    assert issubclass(UnsupportedType, ExtractionError)
    assert issubclass(TooLarge, ExtractionError)
    assert issubclass(UnprocessableDocument, ExtractionError)
