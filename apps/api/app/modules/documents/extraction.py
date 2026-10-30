import io
from dataclasses import dataclass
from pathlib import PurePosixPath

from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_TEXT_CHARS = 1_000_000
MAX_FILENAME_CHARS = 255

CONTENT_TYPE_BY_EXTENSION = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
}


class ExtractionError(Exception):
    """Base for every rejection raised by :func:`extract`."""

    status_code = 422

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class UnsupportedType(ExtractionError):
    status_code = 415


class TooLarge(ExtractionError):
    status_code = 413


class UnprocessableDocument(ExtractionError):
    status_code = 422


@dataclass(frozen=True)
class Extracted:
    text: str
    content_type: str
    size_bytes: int
    page_count: int | None
    char_count: int


def safe_filename(filename: str) -> str:
    """Return the basename of ``filename``, never a path."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not name:
        raise UnprocessableDocument("Invalid filename")
    if len(name) > MAX_FILENAME_CHARS:
        raise UnprocessableDocument("Filename is too long")
    return name


def extract(filename: str, data: bytes) -> Extracted:
    """Validate an upload and extract its text.

    Pure and synchronous: no database, no request object. Runs off the event
    loop via ``asyncio.to_thread`` in the service.
    """
    name = safe_filename(filename)
    extension = PurePosixPath(name).suffix.lower()
    content_type = CONTENT_TYPE_BY_EXTENSION.get(extension)
    if content_type is None:
        raise UnsupportedType(f"Unsupported file type: {extension or name}")

    if len(data) > MAX_UPLOAD_BYTES:
        raise TooLarge("File is larger than 5 MB")
    if not data:
        raise UnprocessableDocument("No text could be extracted")

    if extension == ".pdf":
        text, page_count = _extract_pdf(data)
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UnprocessableDocument("Text must be UTF-8") from exc
        page_count = None

    final_text = text[:MAX_TEXT_CHARS]
    if not final_text.strip():
        raise UnprocessableDocument("No text could be extracted")

    return Extracted(
        text=final_text,
        content_type=content_type,
        size_bytes=len(data),
        page_count=page_count,
        char_count=len(final_text),
    )


def _extract_pdf(data: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UnprocessableDocument("PDF is encrypted")

        page_count = len(reader.pages)
        if page_count > MAX_PDF_PAGES:
            raise UnprocessableDocument("PDF has too many pages")

        parts: list[str] = []
        accumulated = 0
        for page in reader.pages:
            page_text = (page.extract_text() or "").rstrip()
            if not page_text:
                continue
            parts.append(page_text)
            accumulated += len(page_text) + 2
            if accumulated >= MAX_TEXT_CHARS:
                break
    except PyPdfError as exc:
        raise UnprocessableDocument("Could not read PDF") from exc

    return "\n\n".join(parts), page_count
