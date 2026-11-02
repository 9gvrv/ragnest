# Ragnest API — Milestone 5: Retrieval — Design

**Date:** 2026-11-02
**Status:** Draft for review
**Milestone:** 5 of N
**Based on:** Milestone 4 (Documents) — API complete

---

## 1. Why this exists

Milestone 4 stores each document's extracted text but nothing can search it. This
milestone turns that text into a searchable index: split it into chunks, embed
the chunks, store the vectors in Postgres, and answer "which chunks match this
question?" with ranked results. There is no generated answer — that is Milestone
6.

This is the retrieval half of RAG, delivered as API plumbing. The user-facing
surface changes only in that a workspace's documents become queryable.

---

## 2. Intent

- Uploading a document automatically chunks and indexes it after the response is
  sent; a slow or failing embedding provider never blocks the upload.
- Every chunk is tenant-scoped: search in workspace A can never return a chunk
  from workspace B.
- One embedding model, one dimension, one distance metric. No per-workspace
  configuration.
- The API exposes search directly, so the pipeline is provable before chat
  exists.
- No new infrastructure: same Postgres (Neon), no queue, no worker, no vector
  service.

---

## 3. Goals (this milestone)

- `document_chunks` table with text, offsets, vector, and model metadata.
- `documents.embedding_status` and `documents.indexed_at`.
- Deterministic, offset-preserving chunking of `extracted_text`.
- Gemini `gemini-embedding-001` at 768 dimensions, via `batchEmbedContents`.
- Background indexing on upload, a reindex endpoint, and a backfill command for
  documents that existed before this milestone.
- `POST /api/v1/workspaces/{workspace_id}/search` returning ranked chunks.
- Tests on in-memory SQLite with a fake embedding provider; no network, no Neon,
  no key required in CI.

---

## 4. Non-goals (this milestone)

- Chat, answer generation, streaming, citations UI (Milestone 6).
- Hybrid search, BM25/full-text, reranking, query rewriting.
- Metadata filters, date filters, pagination of search results.
- Multiple embedding models, per-workspace model choice, dimension changes.
- Re-embedding when the model changes (the schema records the model so the
  mismatch is detectable; the migration is a future milestone).
- Page-level citations. M4 joined PDF pages without storing boundaries, so page
  numbers cannot be reconstructed reliably.
- A durable job queue, Celery/arq/RQ, retries across process restarts.
- Web UI changes. Retrieval is API-only until Milestone 6.
- Chunk editing, chunk deletion endpoints, document re-upload.

---

## 5. Anti-goals (this milestone is a failure if…)

- A search in one workspace returns a chunk from another workspace.
- An embedding-provider outage makes upload fail or loses the document.
- A failed indexing run leaves a half-written chunk set that search treats as
  complete.
- Deleting a document or workspace leaves orphan chunks.
- A chunk's `content` is not exactly `extracted_text[char_start:char_end]`.
- A vector of the wrong model or dimension is stored or compared silently.
- The API key appears in logs, responses, or tests.
- The pytest suite makes a network call or requires a real Gemini key.
- Search returns chunks from a different embedding model than the query's.

---

## 6. Constraints

- Python 3.13, `uv`, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic.
- Locked structure: `app/modules/retrieval/`, router registered in
  `app/api/router.py`, model imported in `app/db/models.py`.
- Reuse `app/db/base.py` (`Base`, `TimestampMixin`) and
  `app/modules/workspaces/deps.py` (`require_workspace_member`).
- Reuse `app/modules/documents/service.py` (`get_document`, `can_manage`).
- Two new runtime dependencies: `httpx` (Gemini REST calls) and `pgvector`
  (SQLAlchemy vector type and distance operator).
- `GEMINI_API` is the only new secret. It is required by `Settings`, documented
  in `.env.example`, and must never be logged.
- Model, dimension, chunk sizes, batch size, and `top_k` bounds are code
  constants, not environment variables. Changing them is a code change plus a
  migration, not a config tweak.
- SQLite (tests) and Postgres/Neon (dev) must behave identically at the service
  boundary. The vector column is `vector(768)` on Postgres and JSON on SQLite.
- Neon supports pgvector on every plan; the extension is created by the
  migration.
- Ruff clean (`line-length = 100`, `target-version = "py313"`).

---

## 7. Decisions

1. **Chunks live in a new table; `documents.extracted_text` stays.** The text is
   the canonical artefact. It is needed to re-chunk with a different strategy,
   and `GET /documents/{id}` already returns it. Chunk text duplicates the
   document text (slightly more because of overlap); that is accepted.
2. **pgvector in the existing database, not Qdrant.** Same transaction, same
   backup, same `ON DELETE CASCADE`, one connection pool, one secret. A second
   store would require dual writes and orphan-vector cleanup.
3. **`gemini-embedding-001`, 768 output dimensions.** Text-only, stable,
   supports `task_type` directly, and its 2,048-token input limit comfortably
   fits an 800-character chunk. `gemini-embedding-2` is multimodal (unused) and
   expects task instructions in the prompt instead of `task_type`; it buys
   nothing for this milestone. Vectors at 768 dimensions must be L2-normalised
   manually with `gemini-embedding-001`; the provider does it.
4. **Task types are asymmetric.** Chunks use `RETRIEVAL_DOCUMENT`; queries use
   `RETRIEVAL_QUERY`. Mixing these up silently degrades results, so the provider
   exposes `embed_documents` and `embed_query` as separate methods and tests pin
   the payloads.
5. **Indexing runs after the upload response.** FastAPI `BackgroundTasks` is
   enough; no queue and no worker. The document row is created first, so an
   embedding failure never loses the upload. A lost task (process restart) leaves
   the document in a non-ready status and can be repaired with reindex.
6. **Status is explicit.** `documents.embedding_status` is one of `pending`,
   `indexing`, `ready`, `failed`, defaulting to `pending`. `indexed_at` is set
   when a run succeeds. The document list/detail expose both.
7. **Search is `POST`.** A query is user text that may be long, may contain
   punctuation, and should not sit in URLs or access logs. Body:
   `{"query": "...", "top_k": 5}`.
8. **Chunks are exact substrings.** No synthetic title or heading prefix is
   added to `content`; `char_start`/`char_end` always slice the original text.
   This keeps highlighting and future citation verification honest.
9. **Cosine distance.** Chunks and queries are L2-normalised; Postgres orders by
   `embedding <=> :query`, and the API reports `score = 1 - distance` (higher is
   better). SQLite computes exact cosine in Python for tests.
10. **Search filters on `embedding_model`.** If a future model change leaves
    old vectors behind, they are ignored rather than compared against a
    different embedding space.
11. **Failures do not delete the previous chunk set.** A failed reindex leaves
    the old chunks in place (same model in M5, still valid). The status is
    `failed`, and reindex can be retried.
12. **The provider is an injectable protocol.** Production uses Gemini;
    tests use a deterministic fake. Background tasks receive the provider and a
    session factory from dependencies, never a hard-coded `SessionLocal`.

---

## 8. Data model

### Additions to `documents`

| Column | Type | Notes |
| --- | --- | --- |
| `embedding_status` | `String(16)` | `pending` / `indexing` / `ready` / `failed`; `NOT NULL`, default `pending` |
| `indexed_at` | `DateTime(timezone=True)` nullable | set when a run reaches `ready` |

`server_default="pending"` makes the migration safe for existing rows.

### Table `document_chunks`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `Uuid` PK | `uuid4` default |
| `workspace_id` | `Uuid` FK → `workspaces.id` | `ON DELETE CASCADE`; denormalised for scoped search |
| `document_id` | `Uuid` FK → `documents.id` | `ON DELETE CASCADE`; a hard-deleted document takes its chunks |
| `chunk_index` | `Integer` | 0-based ordinal within the document |
| `content` | `Text` | exact substring of `documents.extracted_text` |
| `char_start` | `Integer` | inclusive start offset |
| `char_end` | `Integer` | exclusive end offset |
| `embedding` | `vector(768)` on Postgres, `JSON` on SQLite | `NOT NULL` |
| `embedding_model` | `String(64)` | `gemini-embedding-001` |
| `created_at` | `DateTime(timezone=True)` | `TimestampMixin` |
| `updated_at` | `DateTime(timezone=True)` | `TimestampMixin` |

Constraints and indexes:

- `UNIQUE (document_id, chunk_index)` — one chunk per ordinal per document.
- `INDEX (workspace_id)` — every search filters on it.
- `INDEX USING hnsw (embedding vector_cosine_ops)` — approximate cosine search.
  It is declared on the model with `postgresql_using="hnsw"` so Alembic
  autogenerate does not propose dropping it, and created by the migration.
- Cascade paths: workspace → documents → chunks, and workspace → chunks
  directly. Both foreign keys are `ON DELETE CASCADE`.

`pgvector`'s `Vector(768)` is used directly in the model with
`.with_variant(JSON(), "sqlite")`. This compiles to `VECTOR(768)` on Postgres
and `JSON` on SQLite, and keeps the `cosine_distance` comparator available.

### Storage budget

768 dimensions × 4 bytes ≈ 3 KB per vector. A maximum-size document (1,000,000
characters, ~1,470 chunks at 800 characters with 120 overlap) costs roughly
5 MB including chunk text. Vectors dominate, as Milestone 4 predicted. This is
acceptable on Neon's free tier for a development corpus; quotas are future
work.

---

## 9. Chunking

Constants:

```python
CHUNK_TARGET_CHARS = 800
CHUNK_OVERLAP_CHARS = 120
MIN_CHUNK_CHARS = 120
```

Algorithm — recursive, paragraph first, character-based:

1. Split the text into spans on `\n\n` (paragraphs).
2. If a paragraph is longer than the target, split it on sentence ends
   (`.`, `!`, `?` followed by whitespace), then on newlines, then on whitespace,
   then hard-cut a single oversized token.
3. Greedily pack spans into a chunk until adding the next span would exceed
   `CHUNK_TARGET_CHARS`.
4. Start the next chunk `CHUNK_OVERLAP_CHARS` before the end of the previous one,
   never before the start of the span being added, so progress is guaranteed.
5. If the final chunk is shorter than `MIN_CHUNK_CHARS` and a previous chunk
   exists, extend the previous chunk to the end of the text instead of emitting
   a tiny chunk.
6. Drop chunks whose content is whitespace-only.

Invariants, pinned by tests:

- `content == text[char_start:char_end]` for every chunk.
- The first chunk starts at 0, the last ends at `len(text)`.
- Consecutive chunks overlap by at most `CHUNK_OVERLAP_CHARS` and by at least
  one character when the document is long enough.
- No chunk exceeds `CHUNK_TARGET_CHARS + MIN_CHUNK_CHARS` characters.
- Blank documents raise `ValueError` (M4 guarantees a non-empty text, so this is
  a programming error, not a user error).

No tokenizer is used. At 800 characters an English chunk is roughly 200–300
tokens, well below the model's 2,048-token limit. Character-based chunking is
language-agnostic and dependency-free.

---

## 10. Embedding provider

Model and endpoint:

```text
model: gemini-embedding-001
dimension: 768
endpoint: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents
auth: x-goog-api-key: <GEMINI_API>
```

Request body is one `EmbedContentRequest` per chunk:

```json
{
  "requests": [
    {
      "model": "models/gemini-embedding-001",
      "content": {"parts": [{"text": "..."}]},
      "taskType": "RETRIEVAL_DOCUMENT",
      "outputDimensionality": 768
    }
  ]
}
```

Response: `{"embeddings": [{"values": [ ... 768 floats ... ]}, ...]}`.

Behaviour:

- Batches of `EMBEDDING_BATCH_SIZE = 16`, sequential, to stay under free-tier
  request/token limits.
- `httpx.AsyncClient` with a 30-second timeout, one client per
  `embed_documents`/`embed_query` call.
- Retries: 3 attempts total on `429`, `5xx`, and transport errors; exponential
  backoff starting at 1 second. Non-retryable 4xx raises immediately.
- Validates that the response count equals the request count and that every
  vector has exactly 768 finite floats. A mismatch raises
  `EmbeddingProviderError`.
- L2-normalises each vector before returning it (`gemini-embedding-001` requires
  manual normalisation below 3,072 dimensions).
- `embed_documents(texts)` uses `RETRIEVAL_DOCUMENT`;
  `embed_query(text)` uses `RETRIEVAL_QUERY`.
- `EmbeddingProvider` is a `Protocol` with those two methods. Tests implement a
  deterministic fake; no test calls Gemini.

Configuration:

- `Settings.GEMINI_API: str` (required). Add `GEMINI_API=...` to `.env.example`.
- The model, dimension, batch size, timeout, and retry count are constants in
  `app/modules/retrieval/constants.py`, not settings.

---

## 11. Indexing lifecycle

```text
upload ──► documents row (pending) ──► 201 ──► background task
                                                    │
                                            indexing │
                                         ┌──────────┴──────────┐
                                         ▼                     ▼
                                      ready                failed
                                    (chunks)          (old chunks kept)
```

### Upload

`POST /workspaces/{id}/documents` keeps its current behaviour and response, plus
the new `embedding_status`/`indexed_at` fields. After the row is committed, the
route schedules `index_document(document_id, session_factory, provider)` via
`BackgroundTasks` and returns 201 immediately.

### `index_document`

1. Open a session from the injected factory and load the document. If it no
   longer exists, return quietly.
2. Set `embedding_status = "indexing"` and commit.
3. Chunk the text.
4. Embed all chunks through the provider (network; no database connection is
   held).
5. Open a new session. Re-check the document still exists; delete its existing
   chunks; insert the new chunks; set `embedding_status = "ready"` and
   `indexed_at = now`; commit. Delete and insert happen in one transaction, so
   search never sees a half-written set.
6. On any exception: roll back, log the document ID and error class (never the
   text or key), then set `embedding_status = "failed"` in a fresh session. A
   document deleted meanwhile is ignored.

The task never raises into the response; the response has already been sent.

### Reindex

`POST /workspaces/{workspace_id}/documents/{document_id}/reindex` — uploader,
admin, or creator. Sets status to `pending`, commits, schedules the same task,
and returns 202. It is the repair path for `failed`/stuck `indexing` documents.

### Backfill

`python -m app.modules.retrieval.backfill` iterates every document whose status
is not `ready` and indexes them sequentially. It uses the real provider and a
real session factory. Existing documents get `pending` from the migration's
server default, so the first run after deploy indexes the whole corpus.

### Concurrency

Two indexing runs for the same document can race. The write step is
delete-then-insert in one transaction, and the last commit wins; both write the
same chunks because the model and chunker are deterministic. No locking is added
in this milestone.

A maximum-size document (~1,470 chunks) can keep a background task busy for
several minutes and may hit free-tier token-per-minute limits. Retries absorb
short 429 bursts; a daily quota failure leaves the document `failed` and can be
retried later with reindex or backfill. This is accepted for M5 and is the main
argument for a real worker in a later milestone.

---

## 12. API surface

All routes are under `/api/v1` and authenticated.

### Search

```http
POST /api/v1/workspaces/{workspace_id}/search
Authorization: Bearer <token>
Content-Type: application/json

{"query": "how do I deploy?", "top_k": 5}
```

Response `200`:

```json
[
  {
    "chunk_id": "…",
    "document_id": "…",
    "filename": "deploy.md",
    "chunk_index": 3,
    "content": "…",
    "score": 0.83,
    "char_start": 2410,
    "char_end": 3210
  }
]
```

Validation:

- `query`: 1–2,000 characters, stripped, blank rejected (422).
- `top_k`: integer 1–20, default 5 (422 outside the range).
- Results ordered by score descending, ties by `document_id`, then
  `chunk_index`.
- Only chunks whose `embedding_model` equals the current model are considered.
- An empty workspace returns `[]`.

### Reindex

```http
POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/reindex
```

`202` → `{"embedding_status": "pending"}`. `404` for a foreign/missing document,
`403` for a member who neither uploaded it nor is admin/creator.

### Schemas

```python
class SearchRequest(BaseModel):
    query: str  # 1..2000, stripped, non-blank
    top_k: int = 5  # 1..20

class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    score: float
    char_start: int
    char_end: int
```

`ReindexResponse(embedding_status: str)` lives in
`app/modules/documents/schemas.py` because it is a document response.

`DocumentSummary` gains `embedding_status: str` and
`indexed_at: datetime | None`. `DocumentDetail` inherits them.

---

## 13. Permissions

| Action | Creator | Admin | Member | Outsider |
| --- | --- | --- | --- | --- |
| Search | ✓ | ✓ | ✓ | ✗ (403) |
| Reindex own document | ✓ | ✓ | ✓ | ✗ |
| Reindex another's document | ✓ | ✓ | ✗ (403) | ✗ |

Search is member-wide for the same reason document reads are: every member's
documents feed one workspace pool. Reindex follows `can_manage` from the
documents service: uploader, admin, or creator.

A missing or foreign document on reindex is `404`; workspace membership failures
remain `403` with the existing dependency wording.

---

## 14. Module layout

```text
app/modules/retrieval/
├── __init__.py
├── constants.py     # model, dimension, chunk sizes, limits
├── embeddings.py    # EmbeddingProvider protocol, GeminiEmbeddingProvider, errors
├── chunking.py      # chunk_text() and TextChunk
├── types.py         # the vector column type (vector on PG, JSON on SQLite)
├── models.py        # DocumentChunk
├── schemas.py       # SearchRequest, SearchResult
├── deps.py          # get_embedding_provider, get_session_factory
├── service.py       # index_document, search
├── backfill.py      # python -m app.modules.retrieval.backfill
└── router.py        # POST /workspaces/{id}/search
```

Changed outside the module:

- `app/core/config.py` — `GEMINI_API`.
- `app/modules/documents/models.py` — status columns.
- `app/modules/documents/schemas.py` — status fields and `ReindexResponse`.
- `app/modules/documents/service.py` — include new columns in `load_only`.
- `app/modules/documents/router.py` — schedule indexing, add reindex route.
- `app/db/models.py` — import `DocumentChunk`.
- `app/api/router.py` — include the retrieval router.
- `tests/conftest.py` — fake provider, session-factory override, dummy
  `GEMINI_API`.
- `alembic/versions/` — one hand-written migration.
- `.env.example`, `apps/api/AGENTS.md`, `apps/api/README.md`.

---

## 15. Error semantics

| Condition | Status | Detail |
| --- | --- | --- |
| Not a member / no token | 403 / 401 | existing dependency wording |
| Blank query / bad `top_k` | 422 | Pydantic validation body |
| Provider unavailable during search | 503 | `"Embedding provider unavailable"` |
| Provider fails during indexing | — (upload stays 201) | document becomes `failed` |
| Reindex foreign/missing document | 404 | `"Document not found"` |
| Reindex another member's document | 403 | `"Insufficient permissions"` |
| Missing `GEMINI_API` at startup | — | Settings validation error |

Indexing failures are logged at WARNING with the document ID and exception
class. Document text and the API key are never logged.

---

## 16. Testing strategy

- In-memory async SQLite through the existing root `conftest.py`, with SQLite
  foreign keys enabled.
- `tests/conftest.py` sets `GEMINI_API=test-gemini-key` before importing `app.*`
  and overrides `get_embedding_provider` with a deterministic fake for the
  `client` fixture. The fake maps tokens to fixed vector dimensions via
  `hashlib`, so "alpha" queries rank "alpha" chunks above unrelated text.
- `tests/conftest.py` also overrides `get_session_factory` so background tasks
  use the same in-memory database as the request.
- The real `GeminiEmbeddingProvider` is tested with `httpx.MockTransport`:
  request payload shape (model, task type, output dimensionality, batch split),
  response parsing, dimension validation, normalisation, and retry on 429.
- Chunking is tested directly: exact slices, coverage, overlap bounds, long
  paragraphs, unicode, whitespace.
- Model tests: round-trip a chunk on SQLite, cascade from document and
  workspace, unique `(document_id, chunk_index)`, status default.
- Service tests: success sets `ready` and `indexed_at`; provider failure sets
  `failed` and keeps the document; reindex replaces chunks atomically; a
  document deleted mid-run leaves no chunks.
- Router tests: upload schedules indexing; reindex permission matrix; search
  ranking, `top_k`, empty workspace, query validation, cross-workspace
  isolation, model filter, provider failure 503, non-member 403.
- The Postgres-only search path and the HNSW index are verified manually
  against Neon (upload → status ready → search → second workspace returns
  nothing). They are not in CI because tests must not touch Neon.

---

## 17. Left to builder (not decided here)

- Exact retry/backoff implementation details and log wording.
- Whether to add a separate `embedding_error` column (not planned in v1).
- HNSW build parameters (`m`, `ef_construction`); defaults are acceptable.
- Whether backfill logs per-document progress or only a final count.
- Exact `EXPLAIN` expectations on Neon; the planner may choose a sequential scan
  for a tiny table, which is still correct.
- How to display `pending`/`failed` in the future web UI (Milestone 6).

---

## 18. Where this goes next

**Milestone 6 — Chat (RAG).** The search service returns ranked chunks and
character spans; chat will embed the user's question, retrieve top-k chunks,
build a grounded prompt with file names and chunk ordinals, stream the answer,
and render citations that point back at `document_id` + `char_start`/`char_end`.
If page-level citations become a requirement, M4 must start storing page
boundaries — that is a document-extraction change, not a retrieval one.
