# Ragnest API — Milestone 4: Documents — Design

**Date:** 2026-10-27
**Status:** Draft for review
**Milestone:** 4 of N
**Based on:** Milestone 3 (Workspaces, roles & invitations) — API and web complete

---

## 1. Why this exists

Milestone 3 gave every resource a tenant: a workspace, its members, and their
roles. Retrieval and chat (M5, M6) need something to retrieve from. This
milestone is that something: a member uploads a `.txt`, `.md`, or `.pdf`, the
API extracts its text, and the text is stored against the workspace.

This is deliberately the smallest useful step. The product's only durable
artefact here is **text** — the file itself is not kept.

---

## 2. Intent

- A workspace member uploads a document; the API keeps its text, not its bytes.
- Every document is workspace-scoped and readable by every member of that
  workspace, because retrieval in M5 draws from one shared pool.
- Deletion is complete: the row and its text are gone.
- No new infrastructure: no object storage, no queue, no worker, no secret.

---

## 3. Goals (this milestone)

- `documents` table, one row per successfully ingested file.
- Text extraction for `.txt`, `.md`, `.pdf` inside the upload request.
- `POST /api/v1/workspaces/{workspace_id}/documents` — multipart upload.
- `GET /api/v1/workspaces/{workspace_id}/documents` — list, with `?mine=true`.
- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}` — includes text.
- `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}` — hard delete.
- Workspace-scoped permissions built on the existing `require_workspace_member`.
- Tests on in-memory SQLite with real fixture files; no network, no Neon.

---

## 4. Non-goals (this milestone)

- Retaining original files, downloads, `Content-Disposition`, signed URLs.
- A storage abstraction. It arrives in the milestone that first keeps bytes.
- Embeddings, chunking, vector storage, retrieval, chat.
- OCR of scanned PDFs.
- `.docx`, `.html`, `.rtf`, `.epub`, images.
- Multi-file upload, archives, drag-and-drop batches.
- Renaming, replacing, or editing a document.
- Pagination, full-text search over `extracted_text`, dedupe by content hash.
- Per-workspace document quotas or billing limits.
- Web UI for documents (its own milestone).

---

## 5. Anti-goals (this milestone is a failure if…)

- A non-member can upload, list, read, or delete a document.
- A member can delete another member's document.
- A document from workspace A is visible or deletable from workspace B, or its
  existence is leaked (403 instead of 404 for a foreign ID).
- Bytes are retained after the request finishes, or a `storage_key`/public URL
  appears in the schema.
- A failed extraction leaves a row behind.
- A malformed or hostile PDF can consume unbounded memory or block the event
  loop.
- A client-supplied `content_type` is trusted for anything.
- Tests touch Neon, `.env`, or the network.

---

## 6. Constraints

- Python 3.13, `uv`, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic.
- Locked structure: single `app/` package, feature module at
  `app/modules/documents/`, router registered in `app/api/router.py`.
- Reuse `app/db/base.py` (`Base`, `TimestampMixin`) and
  `app/modules/workspaces/deps.py` (`require_workspace_member`,
  `require_workspace_creator`).
- Identical behaviour on SQLite (tests) and Postgres/Neon (dev): generic types
  only (`Uuid`, `Text`, `Integer`, `String`, `DateTime(timezone=True)`).
- FastAPI dependency style: `Annotated[Type, Depends(...)]`.
- One new runtime dependency: `pypdf` (BSD, pure Python).
- `python-multipart` is already present via `fastapi[standard]`; no new dep for
  `UploadFile`.
- Ruff clean (`line-length = 100`, `target-version = "py313"`).
- Do not commit `.env`.

---

## 7. Decisions

1. **Text only.** The upload's bytes are read, validated, extracted, and
   discarded. `extracted_text` is the durable artefact.
2. **No storage abstraction yet.** With no bytes kept there is nothing to
   abstract. When a milestone retains originals, a `Storage` protocol and
   `local`/object-store implementations are added then — the documents service
   will not need reshaping, only an injected dependency.
3. **Extraction is synchronous but off the event loop.** `pypdf` is CPU-bound
   and takes untrusted input, so extraction runs via `asyncio.to_thread`.
   Bounds: 5 MB upload, 500 PDF pages, and extraction stops as soon as the
   text cap is reached. A 5 MB PDF can still decompress to more than that —
   see §17 for the residual risk we accept.
4. **Failure means no row.** Unsupported type, oversize, undecodable text, or a
   PDF with no text layer → the request fails and nothing is persisted. Without
   the original, an empty document has no value and no way to be repaired.
5. **`content_type` is canonical, derived from the extension.** The browser's
   header is advisory (`application/octet-stream` is common for `.md`); it is
   never stored verbatim.
6. **Any member reads; uploader or creator/admin manages.** `admin` holds the
   creator's document powers, matching how `invite` already works.
7. **`?mine=true` instead of a second route.** One list query, one extra
   `WHERE uploaded_by = :me`.
8. **Foreign documents are 404.** A document ID belonging to another workspace
   must be indistinguishable from a missing one.
9. **Hard delete.** `DELETE` removes the row; the text goes with it.
10. **Ordering is newest first, unpaginated.** Ordering is part of the contract;
    pagination is not, yet.

---

## 8. Data model

### Table `documents`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `Uuid` PK | `uuid4` default |
| `workspace_id` | `Uuid` FK → `workspaces.id` | `ON DELETE CASCADE` |
| `uploaded_by` | `Uuid` FK → `users.id` | `ON DELETE RESTRICT` |
| `filename` | `String(255)` | display name only, never a path |
| `content_type` | `String(128)` | canonical, from extension |
| `size_bytes` | `Integer` | length of the received bytes |
| `page_count` | `Integer` nullable | PDFs only; `NULL` for txt/md |
| `char_count` | `Integer` | `len(extracted_text)` as stored |
| `extracted_text` | `Text` | truncated to the text cap |
| `created_at` | `DateTime(timezone=True)` | `TimestampMixin` |

Indexes:

- `(workspace_id, created_at DESC)` — the list query.
- `(workspace_id, uploaded_by)` — the `?mine=true` variant.

`updated_at` comes along with `TimestampMixin` and is harmless.

### Extension → canonical content type

| Extension | `content_type` |
| --- | --- |
| `.txt` | `text/plain` |
| `.md` | `text/markdown` |
| `.pdf` | `application/pdf` |

Comparison is on the lowercased extension of a basenamed filename.

---

## 9. Limits and validation

| Rule | Value | Failure |
| --- | --- | --- |
| `file` parts | one; any extra parts are ignored | — |
| Max upload size | 5 MB | 413 |
| Max PDF pages | 500 | 422 |
| Max stored text | 1,000,000 characters (truncate) | — |
| Extensions | `.txt`, `.md`, `.pdf` | 415 |
| Empty file | > 0 bytes | 422 |
| Empty extracted text | non-blank required | 422 |
| Filename | basename, 1..255 chars | 422 |

- A declared `Content-Length` above the cap is rejected with 413 **before** the
  body is parsed, so the common oversize case never spools. A chunked upload
  without a length is only caught after reading (§17).
- Size is checked against the bytes actually read, not a declared header.
- Filename is reduced with the platform-independent equivalent of
  `os.path.basename` after normalising `\` to `/`; a filename that becomes
  empty after that is rejected.
- Truncation happens after extraction; `char_count` always equals
  `len(extracted_text)` so the two can never disagree.

### Extraction rules

- **`.txt` / `.md`** — decode `utf-8-sig`; `UnicodeDecodeError` → 422. No
  charset guessing: mojibake is worse than a clear rejection.
- **`.pdf`** — `pypdf.PdfReader`, `page.extract_text()` for each page, joining
  non-empty pages with two newlines. Encrypted → 422. Zero extracted
  characters → 422 ("no text layer", e.g. a scan). More than `MAX_PDF_PAGES`
  (500) → 422. Extraction stops as soon as the text cap is reached, so a huge
  document costs no more than the pages it takes to fill 1,000,000 characters.
  `page_count = len(reader.pages)`.
- Extracted text is stripped of trailing whitespace per page; no other
  normalisation, so M5 sees the author's paragraphs.

---

## 10. API surface

All under `/api/v1`, all authenticated, all requiring workspace membership.

| Method | Path | Success | Errors |
| --- | --- | --- | --- |
| POST | `/workspaces/{workspace_id}/documents` | 201 `DocumentSummary` | 401, 403, 413, 415, 422 |
| GET | `/workspaces/{workspace_id}/documents` (`?mine=true`) | 200 `[DocumentSummary]` | 401, 403 |
| GET | `/workspaces/{workspace_id}/documents/{document_id}` | 200 `DocumentDetail` | 401, 403, 404 |
| DELETE | `/workspaces/{workspace_id}/documents/{document_id}` | 204 | 401, 403, 404 |

Schemas:

```python
class DocumentSummary(BaseModel):  # from_attributes
    id: UUID
    workspace_id: UUID
    uploaded_by: UUID
    filename: str
    content_type: str
    size_bytes: int
    page_count: int | None
    char_count: int
    created_at: datetime

class DocumentDetail(DocumentSummary):
    extracted_text: str
```

Notes:

- `POST` takes `file: UploadFile = File(...)`; the response is the summary, not
  the text.
- List is newest first; ordering is `created_at DESC, id DESC`. The `id`
  tiebreaker exists because SQLite's `CURRENT_TIMESTAMP` has one-second
  resolution and ties would otherwise make the order arbitrary.
- `?mine=true` filters to `uploaded_by == current_user.id`.
- `403` comes from the existing membership dependency ("Not a member"). A
  workspace that does not exist produces the same 403, deliberately: we do not
  distinguish "no such workspace" from "not a member", so existence is not
  leaked.
- `404` means the document is not in *this* workspace, or does not exist.

---

## 11. Permissions

| Action | Creator | Admin | Member |
| --- | --- | --- | --- |
| List / read documents | ✓ | ✓ | ✓ |
| Upload | ✓ | ✓ | ✓ |
| Delete any document | ✓ | ✓ | ✗ |
| Delete own document | ✓ | ✓ | ✓ |

Enforcement is one predicate in `service.py`:

```python
def can_manage(member: WorkspaceMember, document: Document) -> bool:
    return (
        document.uploaded_by == member.user_id
        or member.role in (WorkspaceRole.CREATOR, WorkspaceRole.ADMIN)
    )
```

Reading stays member-wide on purpose: every member's documents feed the same
retrieval pool, so hiding them would misrepresent what the workspace knows.

---

## 12. Module layout

```
app/modules/documents/
├── __init__.py
├── models.py      # Document
├── schemas.py     # DocumentSummary, DocumentDetail
├── extraction.py  # extension allowlist, decode/PDF parse, limits, errors
├── service.py     # ingest, list, get, delete, can_manage
└── router.py      # the four routes

tests/modules/documents/
├── __init__.py
├── conftest.py    # seed_membership fixture: users, workspace, roles, tokens
├── fixtures/      # sample.txt, sample.md, two-page.pdf, three-page.pdf,
│                  # scanned.pdf, wrong.bin
├── test_extraction.py
├── test_model.py
├── test_service.py
├── test_router.py
└── test_permissions.py
```

Registered in `app/api/router.py` next to the other feature routers, and the
model imported in `app/db/models.py`.

**Test-harness change (required):** the SQLite test engine must enable
`PRAGMA foreign_keys=ON` (an `event.listens_for(engine.sync_engine, "connect")`
listener in `tests/conftest.py`). SQLite defaults to off, so `ON DELETE
CASCADE` is currently ignored in tests — including M3's membership cascade.
This is the only change outside the documents module, and the full existing
suite must still pass after it.

`extraction.py` raises small typed exceptions (`UnsupportedType`, `TooLarge`,
`EmptyContent`, `BadEncoding`), which the router maps to `415`, `413`, `422`,
`422`. Extraction itself touches no database and no request object, so it is
unit-testable directly.

---

## 13. Error semantics

| Condition | Status | Detail (shape) |
| --- | --- | --- |
| Not a member / no token | 403 / 401 | existing dependency wording |
| Unsupported extension | 415 | `"Unsupported file type: .docx"` |
| Over 5 MB | 413 | `"File is larger than 5 MB"` |
| More than 500 PDF pages | 422 | `"PDF has too many pages"` |
| Empty file / no text layer | 422 | `"No text could be extracted"` |
| Not UTF-8 text | 422 | `"Text must be UTF-8"` |
| Foreign or missing document | 404 | `"Document not found"` |
| Member deleting another's | 403 | `"Insufficient permissions"` |

Detail strings are ours to word; the status codes and the 404-for-foreign rule
are contract.

---

## 14. Testing strategy

- In-memory async SQLite via the existing `conftest.py`, with one change: the
  engine listens on `connect` and issues `PRAGMA foreign_keys=ON`, so cascades
  are real in tests (see §12).
- Fixtures are real files under `tests/modules/documents/fixtures/`: a
  two-page PDF with known text, a three-page PDF for the page-cap test (with
  `MAX_PDF_PAGES` monkeypatched to 2), a text-free PDF for the rejection case,
  a `.txt`, a `.md`, and a `.bin`.
- Memberships are created by inserting `WorkspaceMember` rows directly through
  `session_factory`, not by exercising the M3 API — fewer moving parts.
- Where ordering matters, tests set `created_at` explicitly; they never rely on
  two inserts landing in different seconds.
- Cases:
  - upload txt/md/pdf → 201, correct `filename`, canonical `content_type`,
    `size_bytes`, `page_count`, `char_count`, `extracted_text`
  - `.PDF` uppercase extension is accepted as a PDF
  - a filename containing a path (`../../etc/passwd`) is stored as `passwd`
  - list is newest-first by explicit `created_at`; `?mine=true` excludes
    others' documents; `?mine=true` with no uploads returns `[]`
  - detail includes text; detail of a foreign document → 404
  - delete own → 204 and the row is gone; creator/admin delete another's → 204;
    member deletes another's → 403
  - unsupported extension → 415; declared `Content-Length` over 5 MB → 413
    without reading the body; empty file → 422; bad UTF-8 → 422; text-free PDF
    → 422; 501-page PDF (cap monkeypatched) → 422 — each leaving no row
  - workspace delete cascades documents
  - non-member → 403 on every route

---

## 15. Left to builder (not decided here)

- Exact wording of error detail strings.
- Whether the fixture PDFs are committed as binaries or assembled in the test.
- Index names beyond Alembic's naming convention.
- Log lines for rejected uploads (INFO with extension and size, never content).
- How `MAX_PDF_PAGES` is monkeypatched in the page-cap test.

---

## 16. Where this goes next

**Milestone 5 — Retrieval.** Chunk `extracted_text`, embed the chunks, store
vectors scoped to the workspace, retrieve top-k. Two consequences already fixed
here: `document_chunks.document_id` must be `ON DELETE CASCADE`, and the vector
table will dominate the storage budget long before the text does.

---

## 17. Calls made after the builder check

A fresh reviewer read an earlier draft and raised six gaps. Resolved here:

1. **Byte handling.** Starlette's `UploadFile` parses and spools the body
   before the handler runs, so "never touches disk" cannot be guaranteed inside
   a normal route. We therefore mean **not retained**: nothing survives the
   request, and no key or URL is stored. A declared `Content-Length` over the
   cap is rejected with 413 before parsing.
2. **SQLite foreign keys.** The test engine now enables
   `PRAGMA foreign_keys=ON`; without it, cascade assertions were vacuous and
   M3's membership cascade was not actually exercised.
3. **PDF bounds.** Added `MAX_PDF_PAGES = 500` and early stop at the text cap,
   so page count and accumulated text are both bounded. Still accepted: a
   crafted PDF may decompress to a large working set inside `pypdf`, and
   `asyncio.to_thread`'s shared pool means concurrent hostile uploads can
   contend. Both are revisited before the API is exposed publicly.
4. **POST 404.** Removed. Creating a document cannot reference a missing
   document; a missing workspace yields the existing 403 from the membership
   dependency, which also prevents workspace-existence probing.
5. **Ordering ties.** Contract is `created_at DESC, id DESC`; tests pin
   `created_at` explicitly rather than relying on SQLite's one-second clock.
6. **Extra file parts.** Dropped the "422 for multiple files" rule; the handler
   reads the `file` part and ignores anything else. No `request.form()`
   parsing.
