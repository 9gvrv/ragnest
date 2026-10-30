from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from app.modules.documents.extraction import MAX_UPLOAD_BYTES
from app.modules.documents.middleware import MAX_REQUEST_BYTES
from app.modules.documents.models import Document

from .conftest import insert_document

FIXTURES = Path(__file__).parent / "fixtures"

SUMMARY_KEYS = {
    "id",
    "workspace_id",
    "uploaded_by",
    "filename",
    "content_type",
    "size_bytes",
    "page_count",
    "char_count",
    "created_at",
}
DETAIL_KEYS = SUMMARY_KEYS | {"extracted_text"}


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def documents_url(seed) -> str:
    return f"/api/v1/workspaces/{seed['workspace_id']}/documents"


async def document_count(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(Document))


async def test_upload_txt_returns_summary(client, seed):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == SUMMARY_KEYS
    assert body["filename"] == "notes.txt"
    assert body["content_type"] == "text/plain"
    assert body["size_bytes"] == len(b"hello world")
    assert body["page_count"] is None
    assert body["char_count"] == len("hello world")
    assert body["workspace_id"] == str(seed["workspace_id"])
    assert body["uploaded_by"] == str(seed["ids"]["member"])


async def test_upload_markdown_uses_markdown_content_type(client, seed):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("sample.md", fixture("sample.md"), "text/markdown")},
    )

    assert resp.status_code == 201
    assert resp.json()["content_type"] == "text/markdown"


async def test_upload_pdf_counts_pages(client, seed):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("two-page.pdf", fixture("two-page.pdf"), "application/pdf")},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["content_type"] == "application/pdf"
    assert body["page_count"] == 2
    assert body["char_count"] > 0


async def test_upload_reduces_filename_to_basename(client, seed):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("../../etc/passwd.txt", b"root", "text/plain")},
    )

    assert resp.status_code == 201
    assert resp.json()["filename"] == "passwd.txt"


async def test_upload_accepts_uppercase_extension(client, seed):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("A.PDF", fixture("two-page.pdf"), "application/octet-stream")},
    )

    assert resp.status_code == 201
    assert resp.json()["content_type"] == "application/pdf"


async def test_list_is_newest_first(client, seed, session_factory):
    older = await insert_document(
        session_factory,
        seed["workspace_id"],
        seed["ids"]["member"],
        filename="older.txt",
        created_at=datetime(2026, 1, 1, 12, 0),
    )
    newer = await insert_document(
        session_factory,
        seed["workspace_id"],
        seed["ids"]["member"],
        filename="newer.txt",
        created_at=datetime(2026, 1, 2, 12, 0),
    )

    resp = await client.get(documents_url(seed), headers=seed["headers"]["member"])

    assert resp.status_code == 200
    assert [d["id"] for d in resp.json()] == [str(newer.id), str(older.id)]


async def test_list_mine_excludes_other_uploaders(client, seed, session_factory):
    mine = await insert_document(
        session_factory, seed["workspace_id"], seed["ids"]["member"], filename="mine.txt"
    )
    await insert_document(
        session_factory, seed["workspace_id"], seed["ids"]["admin"], filename="theirs.txt"
    )

    resp = await client.get(documents_url(seed) + "?mine=true", headers=seed["headers"]["member"])

    assert resp.status_code == 200
    assert [d["id"] for d in resp.json()] == [str(mine.id)]


async def test_list_mine_with_no_uploads_returns_empty(client, seed):
    resp = await client.get(documents_url(seed) + "?mine=true", headers=seed["headers"]["member"])

    assert resp.status_code == 200
    assert resp.json() == []


async def test_detail_includes_extracted_text(client, seed):
    upload = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("notes.txt", b"hello detail", "text/plain")},
    )
    document_id = upload.json()["id"]

    resp = await client.get(
        f"{documents_url(seed)}/{document_id}", headers=seed["headers"]["member"]
    )

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == DETAIL_KEYS
    assert body["extracted_text"] == "hello detail"


async def test_delete_own_document_returns_204_and_removes_row(client, seed, session_factory):
    upload = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("notes.txt", b"hello delete", "text/plain")},
    )
    document_id = upload.json()["id"]

    resp = await client.delete(
        f"{documents_url(seed)}/{document_id}", headers=seed["headers"]["member"]
    )

    assert resp.status_code == 204
    assert resp.content == b""

    detail = await client.get(
        f"{documents_url(seed)}/{document_id}", headers=seed["headers"]["member"]
    )
    assert detail.status_code == 404

    assert await document_count(session_factory) == 0


async def test_unsupported_extension_returns_415(client, seed, session_factory):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("wrong.bin", fixture("wrong.bin"), "application/octet-stream")},
    )

    assert resp.status_code == 415
    assert await document_count(session_factory) == 0


async def test_declared_content_length_over_cap_returns_413(client, seed, session_factory):
    resp = await client.post(
        documents_url(seed),
        headers={
            **seed["headers"]["member"],
            "content-length": str(MAX_REQUEST_BYTES + 1),
        },
        files={"file": ("big.txt", b"small body", "text/plain")},
    )

    assert resp.status_code == 413
    assert await document_count(session_factory) == 0


async def test_actual_oversize_file_returns_413(client, seed, session_factory):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={
            "file": ("big.txt", b"a" * (MAX_UPLOAD_BYTES + 1), "text/plain"),
        },
    )

    assert resp.status_code == 413
    assert await document_count(session_factory) == 0


async def test_empty_file_returns_422(client, seed, session_factory):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert resp.status_code == 422
    assert await document_count(session_factory) == 0


async def test_bad_utf8_returns_422(client, seed, session_factory):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("latin1.txt", b"\xff\xfe\x00hello", "text/plain")},
    )

    assert resp.status_code == 422
    assert await document_count(session_factory) == 0


async def test_null_byte_text_returns_422(client, seed, session_factory):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("nul.txt", b"he\x00llo", "text/plain")},
    )

    assert resp.status_code == 422
    assert await document_count(session_factory) == 0


async def test_text_free_pdf_returns_422_and_writes_no_row(client, seed, session_factory):
    resp = await client.post(
        documents_url(seed),
        headers=seed["headers"]["member"],
        files={"file": ("scanned.pdf", fixture("scanned.pdf"), "application/pdf")},
    )

    assert resp.status_code == 422
    assert await document_count(session_factory) == 0


async def test_non_member_gets_403_on_every_route(client, seed):
    headers = seed["headers"]["outsider"]
    document_id = "00000000-0000-0000-0000-000000000000"

    upload = await client.post(
        documents_url(seed),
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    listing = await client.get(documents_url(seed), headers=headers)
    detail = await client.get(f"{documents_url(seed)}/{document_id}", headers=headers)
    delete = await client.delete(f"{documents_url(seed)}/{document_id}", headers=headers)

    assert upload.status_code == 403
    assert listing.status_code == 403
    assert detail.status_code == 403
    assert delete.status_code == 403
