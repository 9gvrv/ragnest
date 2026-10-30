# Documents (Milestone 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.
>
> **This project runs in mentor mode:** the human writes the code; the mentor explains, reviews, and only writes files when a step says so. Steps are still written as concrete, verifiable actions.

**Goal:** Let a workspace member upload a `.txt`, `.md`, or `.pdf`; keep its extracted text in Postgres and discard the bytes.

**Architecture:** One new domain module, `app/modules/documents/`, following the established shape (models, schemas, extraction, service, router). Extraction is a pure, DB-free function called through `asyncio.to_thread`. All routes are workspace-scoped and sit behind the existing `require_workspace_member` dependency.

**Tech Stack:** Python 3.13, FastAPI (`UploadFile`, already backed by `python-multipart`), SQLAlchemy 2.0 async, Alembic, `pypdf`, pytest + aiosqlite.

**Spec:** `docs/superpowers/specs/2026-10-27-documents-design.md`

## Global Constraints

- Python 3.13, `uv`, single top-level `app/` package — **no `src/` layout**.
- New feature module at `app/modules/documents/`; router registered in `app/api/router.py`; model imported in `app/db/models.py`.
- Reuse `app/db/base.py` (`Base`, `TimestampMixin`) and `app/modules/workspaces/deps.py` (`require_workspace_member`).
- Generic SQLAlchemy types only (`Uuid`, `Text`, `Integer`, `String`, `DateTime(timezone=True)`) — SQLite and Postgres must behave identically.
- Limits, verbatim from the spec: 5 MB upload, 500 PDF pages, 1,000,000 stored characters, extensions `.txt`/`.md`/`.pdf`.
- Canonical `content_type` from extension: `.txt`→`text/plain`, `.md`→`text/markdown`, `.pdf`→`application/pdf`.
- Status codes: 415 unsupported type, 413 too large, 422 empty/bad-encoding/no-text/too-many-pages, 404 foreign or missing document, 403 not a member.
- No bytes retained: no `storage_key`, no file written by us, no URL in any schema.
- Tests never touch Neon, `.env`, or the network; in-memory SQLite only.
- Ruff: `line-length = 100`, `target-version = "py313"`; `uv run ruff check app tests` stays clean.
- Do not commit `.env`.

## Review Focus

1. **Foreign document ID.** A document in workspace A requested through workspace B must return 404 — never 403, never 200. Wrong guess here leaks existence across tenants.
2. **Delete authorisation.** A `member` deleting someone else's document must get 403; the uploader, and creators/admins, must get 204.
3. **Rejected uploads leave nothing.** Every 413/415/422 path must leave `documents` unchanged — especially the text-free PDF and the bad-UTF-8 file.
4. **Filenames.** `../../etc/passwd` is stored as `passwd`; `.PDF` is accepted as a PDF; whitespace-only text is rejected.
5. **`?mine=true`.** Must exclude other members' documents and return `[]` (not 404) when the caller has uploaded nothing.

---

### Task 1: Model, test-engine foreign keys, migration

**Files:**
- Create: `app/modules/documents/__init__.py`
- Create: `app/modules/documents/models.py`
- Modify: `app/db/models.py`
- Modify: `tests/conftest.py`
- Create: `tests/modules/documents/__init__.py`
- Test: `tests/modules/documents/test_model.py`

**Interfaces:**
- Consumes: `Base`, `TimestampMixin` from `app/db/base.py`; `Workspace`, `WorkspaceMember` from `app/modules/workspaces/models.py`; `User` from `app/modules/users/models.py`.
- Produces: `Document` — `id: UUID`, `workspace_id: UUID`, `uploaded_by: UUID`, `filename: str`, `content_type: str`, `size_bytes: int`, `page_count: int | None`, `char_count: int`, `extracted_text: str`, `created_at: datetime`, `updated_at: datetime`.

- [x] **Step 1: Write the failing tests**

`tests/modules/documents/test_model.py`:

```python
async def test_sqlite_foreign_keys_are_on(session_factory):
    async with session_factory() as session:
        result = await session.execute(text("PRAGMA foreign_keys"))
        assert result.scalar() == 1

async def test_document_round_trip(session_factory):
    # seed user + workspace, then Document(..., extracted_text="hello")
    # asserts created_at is set, page_count is None, char_count == 5

async def test_deleting_workspace_cascades_documents(session_factory):
    # seed workspace + document, session.delete(workspace), commit
    # assert await session.get(Document, document_id) is None
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/modules/documents/test_model.py -v`
Expected: FAIL — `ModuleNotFoundError` / `no such table: documents`; the pragma test returns `0`.

- [x] **Step 3: Enable SQLite foreign keys and create the model**

In `tests/conftest.py`, register a listener on the engine before `create_all`:

```python
from sqlalchemy import event

@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

`app/modules/documents/models.py` — `Document(Base, TimestampMixin)` with the columns above. `workspace_id` is `ForeignKey("workspaces.id", ondelete="CASCADE")`, `uploaded_by` is `ForeignKey("users.id", ondelete="RESTRICT")`, `extracted_text` is `Text`, `page_count` is nullable, and `__table_args__` declares `Index("ix_documents_workspace_created", "workspace_id", "created_at")` and `Index("ix_documents_workspace_uploaded_by", "workspace_id", "uploaded_by")`.

Add `from app.modules.documents.models import Document  # noqa: F401` to `app/db/models.py`.

- [x] **Step 4: Generate and apply the migration**

Run: `uv run alembic revision --autogenerate -m "add documents table"`
Run: `uv run alembic upgrade head`
Expected: one new revision creating `documents` plus both indexes.

- [x] **Step 5: Run the new tests and the full suite**

Run: `uv run pytest -q`
Expected: all pass — including M3 suites, which now run with real foreign keys.

- [x] **Step 6: Commit**

```bash
git add app/modules/documents/__init__.py app/modules/documents/models.py \
        app/db/models.py tests/conftest.py tests/modules/documents/__init__.py \
        tests/modules/documents/test_model.py alembic/versions/
git commit -m "feat(documents): add documents model and migration"
```

---

### Task 2: Extraction

**Files:**
- Create: `app/modules/documents/extraction.py`
- Test: `tests/modules/documents/test_extraction.py`
- Test data: `tests/modules/documents/fixtures/` (`sample.txt`, `sample.md`, `two-page.pdf`, `three-page.pdf`, `scanned.pdf`, `wrong.bin`)

**Interfaces:**
- Consumes: `pypdf` only.
- Produces:
  - `MAX_UPLOAD_BYTES = 5 * 1024 * 1024`, `MAX_TEXT_CHARS = 1_000_000`, `MAX_PDF_PAGES = 500`
  - `class ExtractionError(Exception)` with `status_code: int` and `detail: str`; subclasses `UnsupportedType(415)`, `TooLarge(413)`, `UnprocessableDocument(422)`
  - `@dataclass Extracted: text, content_type, size_bytes, page_count, char_count`
  - `safe_filename(filename: str) -> str`
  - `extract(filename: str, data: bytes) -> Extracted` — pure and synchronous

- [x] **Step 1: Add the dependency**

Run: `uv add pypdf`
Expected: `pyproject.toml` + `uv.lock` updated; no other dependency changes.

- [x] **Step 2: Write the failing tests**

`tests/modules/documents/test_extraction.py` — one test per rule:

```python
def test_txt_extracts_and_reports_plain_text()          # "text/plain", page_count None
def test_markdown_extracts_as_markdown()                # "text/markdown"
def test_pdf_extracts_pages_and_counts_them()           # page_count == 2, text from both
def test_uppercase_extension_is_accepted()              # "A.PDF" extracts
def test_path_in_filename_is_reduced_to_basename()      # "../../etc/passwd" -> "passwd"
def test_unsupported_extension_raises_415()
def test_oversize_bytes_raise_413()
def test_empty_file_raises_422()
def test_invalid_utf8_raises_422()
def test_whitespace_only_text_raises_422()
def test_text_free_pdf_raises_422()                     # scanned.pdf
def test_too_many_pages_raises_422(monkeypatch)         # MAX_PDF_PAGES -> 2, three-page.pdf
def test_long_text_is_truncated_to_cap(monkeypatch)     # MAX_TEXT_CHARS -> 10; char_count == 10
```

- [x] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/modules/documents/test_extraction.py -v`
Expected: FAIL — `ModuleNotFoundError: app.modules.documents.extraction`.

- [x] **Step 4: Implement extraction**

Rules the tests pin: lowercased extension drives everything; `safe_filename` replaces `\` with `/`, takes the basename, and rejects an empty result; size is checked on `len(data)`; `.txt`/`.md` decode with `utf-8-sig`; PDF uses `PdfReader`, rejects `is_encrypted`, rejects `len(reader.pages) > MAX_PDF_PAGES`, extracts pages until the accumulated text reaches `MAX_TEXT_CHARS`, joins non-empty pages with `"\n\n"`, and sets `page_count` to the full page count read from the reader; final text is `text[:MAX_TEXT_CHARS]`, and `char_count = len(final text)`; blank text raises `UnprocessableDocument`.

- [x] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/modules/documents/test_extraction.py -v`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add app/modules/documents/extraction.py tests/modules/documents/test_extraction.py \
        tests/modules/documents/fixtures/ pyproject.toml uv.lock
git commit -m "feat(documents): extract text from txt, md and pdf"
```

---

### Task 3: Schemas and service

**Files:**
- Create: `app/modules/documents/schemas.py`
- Create: `app/modules/documents/service.py`
- Test: `tests/modules/documents/test_service.py`

**Interfaces:**
- Consumes: `extract`, `Extracted`, `ExtractionError` from Task 2; `WorkspaceMember`, `WorkspaceRole`.
- Produces:
  - `DocumentSummary` (`from_attributes`): `id, workspace_id, uploaded_by, filename, content_type, size_bytes, page_count, char_count, created_at`
  - `DocumentDetail(DocumentSummary)`: adds `extracted_text`
  - `can_manage(member: WorkspaceMember, document: Document) -> bool`
  - `async ingest(session, workspace_id: UUID, uploaded_by: UUID, filename: str, data: bytes) -> Document`
  - `async list_documents(session, workspace_id: UUID, mine: UUID | None = None) -> list[Document]`
  - `async get_document(session, workspace_id: UUID, document_id: UUID) -> Document` (raises 404)
  - `async delete_document(session, workspace_id: UUID, document_id: UUID, member: WorkspaceMember) -> None` (raises 404/403)

- [x] **Step 1: Write the failing tests**

`tests/modules/documents/test_service.py`:
- `test_ingest_stores_extracted_text_and_counts` — calls `ingest()` with txt bytes, asserts row fields match `Extracted`
- `test_ingest_failure_writes_no_row` — unsupported bytes raise, `select(func.count()).select_from(Document)` is still 0
- `test_list_is_newest_first` — two rows with explicit `created_at` (2026-01-01, 2026-01-02)
- `test_list_mine_filters_by_uploader`
- `test_get_document_from_other_workspace_raises_404`
- `test_can_manage_uploader_true`, `test_can_manage_creator_true`, `test_can_manage_admin_true`, `test_can_manage_other_member_false`
- `test_delete_other_members_document_raises_403`

- [x] **Step 2: Run to verify failure**

Run: `uv run pytest tests/modules/documents/test_service.py -v`
Expected: FAIL — module not found.

- [x] **Step 3: Implement schemas and service**

Schemas are the two Pydantic models above. In the service: `ingest` calls `await asyncio.to_thread(extract, filename, data)`, then constructs `Document(...)` from the `Extracted` and commits. `get_document` selects by `id` **and** `workspace_id`, raising `HTTPException(404, "Document not found")`. `delete_document` loads via `get_document`, checks `can_manage`, then deletes and commits. `list_documents` filters by `workspace_id` (and `uploaded_by` when `mine` is set) ordered by `created_at.desc(), id.desc()`.

- [x] **Step 4: Run to verify pass**

Run: `uv run pytest tests/modules/documents/test_service.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add app/modules/documents/schemas.py app/modules/documents/service.py \
        tests/modules/documents/test_service.py
git commit -m "feat(documents): add schemas and document service"
```

---

### Task 4: Router, registration, API tests

**Files:**
- Create: `app/modules/documents/router.py`
- Modify: `app/api/router.py`
- Create: `tests/modules/documents/conftest.py`
- Test: `tests/modules/documents/test_router.py`, `tests/modules/documents/test_permissions.py`

**Interfaces:**
- Consumes: `ingest`, `list_documents`, `get_document`, `delete_document`, `can_manage`, `DocumentSummary`, `DocumentDetail`; `require_workspace_member`; `ExtractionError`.
- Produces: `router` — `APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])`.

- [x] **Step 1: Write the failing tests**

`tests/modules/documents/conftest.py` — a `seed` fixture creating three users, one workspace, membership rows (creator/admin/member), and returning `{"workspace_id", "headers": {user: auth header}, "ids": {...}}`, built with `create_access_token` and direct `session_factory` inserts (same style as `tests/modules/invitations/test_preview.py`).

`test_router.py` — upload txt/md/pdf (201 and correct summary fields), list newest-first, `?mine=true` excludes others and returns `[]` when empty, detail contains `extracted_text`, delete own returns 204 and the row is gone, unsupported extension 415, `Content-Length` over 5 MB 413, empty file 422, bad UTF-8 422, text-free PDF 422 with no row created, and 403 for a non-member on all four routes.

`test_permissions.py` — creator deletes another's 204; admin deletes another's 204; member deletes another's 403; foreign-workspace document ID → 404 on GET and DELETE.

- [x] **Step 2: Run to verify failure**

Run: `uv run pytest tests/modules/documents/test_router.py tests/modules/documents/test_permissions.py -v`
Expected: FAIL — 404 on every route (router not registered).

- [x] **Step 3: Implement the router**

Four handlers, each taking `member: Annotated[WorkspaceMember, Depends(require_workspace_member)]` and `session: Annotated[AsyncSession, Depends(get_db)]`:

- `POST` — reject when `content-length` exceeds `MAX_UPLOAD_BYTES` (413) before calling `file.read()`; then `data = await file.read()`, pass `member.user_id` as `uploaded_by` and `file.filename or ""` to `ingest`, return `DocumentSummary` with status 201. Catch `ExtractionError` and raise `HTTPException(e.status_code, e.detail)`.
- `GET` list — `mine: bool = False`; pass `member.user_id if mine else None`; return `list[DocumentSummary]`.
- `GET` detail — return `DocumentDetail`.
- `DELETE` — status 204, `Response(status_code=204)`.

Register in `app/api/router.py`: `api_v1.include_router(documents_router.router)`.

- [x] **Step 4: Run to verify pass**

Run: `uv run pytest tests/modules/documents -v`
Expected: PASS.

- [x] **Step 5: Lint**

Run: `uv run ruff check app tests && uv run ruff format --check app tests`
Expected: clean.

- [x] **Step 6: Commit**

```bash
git add app/modules/documents/router.py app/api/router.py \
        tests/modules/documents/conftest.py tests/modules/documents/test_router.py \
        tests/modules/documents/test_permissions.py
git commit -m "feat(documents): add workspace document endpoints"
```

---

### Task 5: Documentation and end-to-end verification

**Files:**
- Modify: `apps/api/AGENTS.md` (§3 tree, §7 migrations, §11 module list, §13 roadmap, §14 pointers)
- Modify: `apps/api/README.md` (feature + scope lines)

**Interfaces:**
- Consumes: the finished module from Tasks 1–4.
- Produces: docs that match the code.

- [x] **Step 1: Run the whole suite and lint**

Run: `uv run pytest -q && uv run ruff check app tests && uv run ruff format --check app tests`
Expected: all pass.

- [x] **Step 2: Manual end-to-end check against the dev API**

Run: `uv run fastapi dev app/main.py`, sign in, create a workspace, then:

```bash
curl -s -X POST "$API/api/v1/workspaces/$WS/documents" \
  -H "Authorization: Bearer $TOKEN" -F "file=@sample.pdf" | jq
curl -s "$API/api/v1/workspaces/$WS/documents?mine=true" \
  -H "Authorization: Bearer $TOKEN" | jq '.[].filename'
curl -s -X DELETE "$API/api/v1/workspaces/$WS/documents/$DOC" \
  -H "Authorization: Bearer $TOKEN" -o /dev/null -w '%{http_code}\n'
```

Expected: 201 with `page_count`/`char_count`; the list shows the file; DELETE prints `204`.

- [x] **Step 3: Update AGENTS.md**

- §3 tree: add `modules/documents/` (models, schemas, extraction, service, router) and its test dir.
- §7: `documents` is the newest domain table; note text-only storage and the M5 cascade requirement.
- §13: mark Milestone 4 complete; next is Milestone 5 (Retrieval).
- §14: point at this plan and the design doc.

- [x] **Step 4: Commit**

```bash
git add apps/api/AGENTS.md apps/api/README.md
git commit -m "docs(api): record milestone 4 documents"
```

---

## Done means

- `uv run pytest`, `uv run ruff check app tests`, `uv run ruff format --check app tests` all clean.
- A real PDF goes upload → list → detail → delete over HTTP.
- `documents` holds text and metadata only — no key, no URL, no file on disk.
- AGENTS.md and the README describe the module as built.
