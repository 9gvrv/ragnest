# Retrieval (Milestone 5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This project runs in mentor mode:** the human writes the code; the mentor explains, reviews, and only writes files when a step says so. Steps are still written as concrete, verifiable actions.

**Goal:** Turn each document's extracted text into workspace-scoped embedded chunks and expose a ranked similarity search endpoint, with no LLM answer generation.

**Architecture:** A new `app/modules/retrieval/` module owns chunking, the embedding provider, the `document_chunks` model, indexing, and search. Uploads schedule indexing as a FastAPI background task after the document row is committed; status lives on `documents`. Vectors are stored by pgvector in the same Postgres database, with a JSON variant so the SQLite test suite runs unchanged.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0 async, Alembic, pgvector, httpx, Gemini `gemini-embedding-001`, pytest + aiosqlite.

**Spec:** `docs/superpowers/specs/2026-11-02-retrieval-design.md`

## Global Constraints

- Python 3.13, `uv`, single top-level `app/` package — no `src/` layout.
- New module at `app/modules/retrieval/`; router registered in `app/api/router.py`; model imported in `app/db/models.py`.
- `gemini-embedding-001` at exactly **768** dimensions, `RETRIEVAL_DOCUMENT` for chunks and `RETRIEVAL_QUERY` for queries; L2-normalise every vector.
- Chunking: target **800** characters, overlap **120**, minimum tail **120**; chunks are exact substrings of `extracted_text`.
- `top_k` default **5**, maximum **20**; query length 1–**2,000** characters, blank rejected.
- `documents.embedding_status` ∈ `pending|indexing|ready|failed`, default `pending`; `indexed_at` nullable.
- pgvector in the existing database; `CREATE EXTENSION IF NOT EXISTS vector` in the migration.
- Only new secret: `GEMINI_API`. Model/dimension/chunk values are code constants, not env vars.
- Upload must return 201 even when embedding fails; the document becomes `failed` and reindex repairs it.
- Tests never touch Neon, the network, or a real Gemini key. In-memory SQLite only.
- Ruff: `line-length = 100`, `target-version = "py313"`; `uv run ruff check app tests` stays clean.
- Do not commit `.env`.

## Review Focus

1. **Cross-tenant search.** A query in workspace A must never return a chunk from workspace B, even when both contain identical text. Test with two workspaces.
2. **Provider outage on upload.** The upload must still return 201, the document must exist, status must be `failed`, and no half-written chunks may remain. Test with a failing fake provider.
3. **Offset integrity.** Every chunk's `content` must equal `extracted_text[char_start:char_end]`, including unicode and overlapping chunks. Test on a text with emoji and repeated paragraphs.
4. **Model/dimension mismatch.** A stored vector with a different `embedding_model` or wrong length must never be compared or accepted. Test the search filter and the provider's dimension validation.
5. **Reindex atomicity and permissions.** A failed reindex must not delete the old chunk set or the document; a member must not reindex someone else's document. Test both.

---

### Task 1: Config, constants, and the Gemini embedding provider

**Files:**
- Create: `app/modules/retrieval/__init__.py`
- Create: `app/modules/retrieval/constants.py`
- Create: `app/modules/retrieval/embeddings.py`
- Modify: `app/core/config.py` (add `GEMINI_API: str`)
- Modify: `tests/conftest.py` (set dummy `GEMINI_API`)
- Modify: `pyproject.toml` / `uv.lock` (add `httpx`, `pgvector`)
- Test: `tests/modules/retrieval/__init__.py`
- Test: `tests/modules/retrieval/test_embeddings.py`

**Interfaces:**
- Consumes: `app.core.config.settings`.
- Produces:
  - `EMBEDDING_MODEL = "gemini-embedding-001"`, `EMBEDDING_DIM = 768`, `EMBEDDING_BATCH_SIZE = 16`, `EMBEDDING_TIMEOUT_SECONDS = 30.0`, `EMBEDDING_MAX_ATTEMPTS = 3`
  - `class EmbeddingProviderError(Exception)`
  - `class EmbeddingProvider(Protocol)` with `async embed_documents(texts: list[str]) -> list[list[float]]` and `async embed_query(text: str) -> list[float]`
  - `class GeminiEmbeddingProvider(api_key: str, client: httpx.AsyncClient | None = None)`
  - Settings field `GEMINI_API: str`

- [ ] **Step 1: Add dependencies**

Run: `uv add httpx pgvector`
Expected: both in `[project].dependencies`; `uv.lock` updated.

- [ ] **Step 2: Write the failing tests**

`tests/modules/retrieval/test_embeddings.py` — use `httpx.MockTransport`, never the network:

```python
async def test_documents_use_retrieval_document_task_type_and_768_dims():
    # handler asserts body["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT",
    # body["requests"][0]["outputDimensionality"] == 768,
    # body["requests"][0]["model"] == "models/gemini-embedding-001",
    # header x-goog-api-key == "test-key"; returns one vector of 768 values
    # asserts len(vectors) == len(texts) and len(vectors[0]) == 768

async def test_query_uses_retrieval_query_task_type():
    # handler asserts "RETRIEVAL_QUERY"

async def test_batches_are_split_at_sixteen():
    # 17 texts -> exactly two HTTP requests; first has 16 requests, second 1

async def test_vectors_are_l2_normalised():
    # handler returns [3.0] + [0.0] * 767; assert norm == pytest.approx(1.0)

async def test_dimension_mismatch_raises():
    # handler returns 767 floats; pytest.raises(EmbeddingProviderError)

async def test_429_is_retried(monkeypatch):
    # first response 429, second 200; monkeypatch asyncio.sleep with AsyncMock
    # assert the call succeeds and exactly two requests were made

async def test_non_retryable_4xx_raises():
    # 400 -> EmbeddingProviderError, one request only
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/modules/retrieval/test_embeddings.py -v`
Expected: FAIL — module/classes not found.

- [ ] **Step 4: Implement constants, config, and provider**

`app/modules/retrieval/constants.py` holds the five embedding constants plus the chunk/search constants from Tasks 2 and 6.

`app/core/config.py` adds `GEMINI_API: str` next to `SECRET_KEY`.

`app/modules/retrieval/embeddings.py`:

```python
class GeminiEmbeddingProvider:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None): ...
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
```

`embed_documents` splits into batches of 16, calls `_embed_batch(batch, "RETRIEVAL_DOCUMENT")` sequentially and concatenates. `embed_query` calls `_embed_batch([text], "RETRIEVAL_QUERY")` and returns the single vector.

`_embed_batch` POSTs to `.../gemini-embedding-001:batchEmbedContents` with one request object per text; retries 429/5xx/transport errors up to 3 attempts with 1s then 2s sleeps; validates response count and every vector length; converts values to `list[float]`; L2-normalises.

If no client was injected, `embed_documents` and `embed_query` create and close one `httpx.AsyncClient` per call; an injected client (tests) is left open for the caller to close.

`tests/conftest.py` adds `os.environ.setdefault("GEMINI_API", "test-gemini-key")` above the `app.*` imports, and `.env.example` gains `GEMINI_API=your-gemini-api-key`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/modules/retrieval/test_embeddings.py tests/core/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/modules/retrieval/__init__.py app/modules/retrieval/constants.py \
        app/modules/retrieval/embeddings.py app/core/config.py tests/conftest.py \
        tests/modules/retrieval/__init__.py tests/modules/retrieval/test_embeddings.py \
        pyproject.toml uv.lock .env.example
git commit -m "feat(retrieval): add gemini embedding provider"
```

---

### Task 2: Chunking

**Files:**
- Create: `app/modules/retrieval/chunking.py`
- Test: `tests/modules/retrieval/test_chunking.py`

**Interfaces:**
- Consumes: `CHUNK_TARGET_CHARS`, `CHUNK_OVERLAP_CHARS`, `MIN_CHUNK_CHARS`.
- Produces:
  - `@dataclass(frozen=True) class TextChunk: content: str; char_start: int; char_end: int`
  - `def chunk_text(text: str) -> list[TextChunk]`

- [ ] **Step 1: Write the failing tests**

```python
def test_chunks_are_exact_slices():
    text = "Paragraph one.\n\nParagraph two is longer.\n\nParagraph three."
    for chunk in chunk_text(text):
        assert chunk.content == text[chunk.char_start:chunk.char_end]

def test_chunks_cover_the_document():
    chunks = chunk_text("A" * 5000)
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == 5000

def test_no_chunk_exceeds_the_bound():
    chunks = chunk_text("word " * 2000)
    assert all(len(c.content) <= CHUNK_TARGET_CHARS + MIN_CHUNK_CHARS for c in chunks)

def test_consecutive_chunks_overlap():
    chunks = chunk_text("word " * 2000)
    assert any(c2.char_start < c1.char_end for c1, c2 in zip(chunks, chunks[1:]))

def test_paragraphs_are_preferred_over_mid_word_cuts():
    text = "alpha " * 100 + "\n\n" + "beta " * 100
    chunks = chunk_text(text)
    assert any(c.content.lstrip().startswith("beta") for c in chunks)

def test_unicode_offsets_are_preserved():
    text = "héllo 👋\n\n" + "naïve café " * 200
    for chunk in chunk_text(text):
        assert chunk.content == text[chunk.char_start:chunk.char_end]

def test_whitespace_only_chunks_are_dropped():
    chunks = chunk_text("alpha\n\n\n\n\n\nbeta")
    assert all(c.content.strip() for c in chunks)

def test_blank_text_raises():
    with pytest.raises(ValueError):
        chunk_text("   \n\n  ")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/modules/retrieval/test_chunking.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `chunk_text`**

Recursive span splitting: `\n\n` → sentence end → newline → whitespace → hard cut. Greedily pack spans up to 800 characters. When a chunk closes, start the next one `120` characters before the previous end, but never before the span being added; guarantee `next_start > current_start`. If the last chunk is shorter than 120 characters and there is a previous chunk, extend the previous chunk's `char_end` to `len(text)` and drop the tail chunk. Skip whitespace-only chunks. `content` is always `text[start:end]`; no stripping or prefixes.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/modules/retrieval/test_chunking.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/retrieval/chunking.py tests/modules/retrieval/test_chunking.py
git commit -m "feat(retrieval): add offset-preserving chunking"
```

---

### Task 3: Model, status columns, migration

**Files:**
- Create: `app/modules/retrieval/types.py`
- Create: `app/modules/retrieval/models.py`
- Modify: `app/modules/documents/models.py`
- Modify: `app/db/models.py`
- Create: `alembic/versions/<rev>_add_retrieval_chunks.py` (hand-written)
- Test: `tests/modules/retrieval/test_model.py`

**Interfaces:**
- Consumes: `Base`, `TimestampMixin`, `EMBEDDING_DIM`.
- Produces:
  - `Vector768` — `Vector(768).with_variant(JSON(), "sqlite")`
  - `DocumentChunk` — `id, workspace_id, document_id, chunk_index, content, char_start, char_end, embedding, embedding_model, created_at, updated_at`
  - `Document.embedding_status: str`, `Document.indexed_at: datetime | None`

- [ ] **Step 1: Write the failing tests**

`tests/modules/retrieval/test_model.py`:

```python
async def test_chunk_round_trip_on_sqlite(session_factory):
    # seed user + workspace + document, then DocumentChunk(... embedding=[0.1] * 768)
    # assert fetched.embedding == [0.1] * 768, offsets and content survive

async def test_document_embedding_status_defaults_to_pending(session_factory):
    # insert a Document without embedding_status; assert fetched == "pending"
    # and indexed_at is None

async def test_deleting_document_cascades_chunks(session_factory):
    # delete document; assert session.get(DocumentChunk, chunk_id) is None

async def test_deleting_workspace_cascades_chunks(session_factory):
    # delete workspace; assert chunks and document are gone

async def test_chunk_index_is_unique_per_document(session_factory):
    # two chunks with document_id=X, chunk_index=0 -> IntegrityError
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/modules/retrieval/test_model.py -v`
Expected: FAIL — no table / attributes.

- [ ] **Step 3: Add types, models, and status columns**

`types.py`:

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON

Vector768 = Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite")
```

`DocumentChunk` uses `Uuid` PK, both foreign keys `ondelete="CASCADE"`, `Text` content, `Integer` offsets, `Mapped[list[float]]` embedding, `String(64)` model, `UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_id_chunk_index")`, and two indexes in `__table_args__`:

```python
Index("ix_document_chunks_workspace_id", "workspace_id"),
Index(
    "ix_document_chunks_embedding_hnsw",
    "embedding",
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
),
```

Declaring the HNSW index in the model keeps Alembic autogenerate from proposing to drop it later. SQLite ignores the Postgres index options and creates an ordinary index over the JSON column, which is harmless for the test database.

`documents/models.py` adds:

```python
embedding_status: Mapped[str] = mapped_column(
    String(16), default="pending", server_default="pending"
)
indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

`app/db/models.py` imports `DocumentChunk`.

- [ ] **Step 4: Write and apply the migration**

Run: `uv run alembic revision -m "add retrieval chunks"` (no `--autogenerate`).

In `upgrade()`:

```python
op.execute("CREATE EXTENSION IF NOT EXISTS vector")
op.add_column("documents", sa.Column("embedding_status", sa.String(16), nullable=False, server_default="pending"))
op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
op.create_table("document_chunks", ...)  # embedding uses pgvector Vector(768)
op.create_index("ix_document_chunks_workspace_id", "document_chunks", ["workspace_id"])
op.create_index(
    "ix_document_chunks_embedding_hnsw",
    "document_chunks",
    ["embedding"],
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
```

Import `from pgvector.sqlalchemy import Vector` in the migration. `downgrade()` drops the HNSW index, the table, and both columns; leave the extension in place.

Run: `uv run alembic upgrade head`
Expected: extension, columns, table, unique constraint, workspace index, and HNSW index exist on Neon.

- [ ] **Step 5: Run the tests and the full suite**

Run: `uv run pytest tests/modules/retrieval/test_model.py tests/modules/documents -q`
Expected: PASS — existing documents tests still pass with the added columns.

- [ ] **Step 6: Commit**

```bash
git add app/modules/retrieval/types.py app/modules/retrieval/models.py \
        app/modules/documents/models.py app/db/models.py \
        tests/modules/retrieval/test_model.py alembic/versions/
git commit -m "feat(retrieval): add chunk model, document status and pgvector migration"
```

---

### Task 4: Indexing service

**Files:**
- Create: `app/modules/retrieval/deps.py`
- Create: `app/modules/retrieval/service.py`
- Modify: `tests/conftest.py` (add `FakeEmbeddingProvider`, `FailingEmbeddingProvider`, and their fixtures)
- Test: `tests/modules/retrieval/test_service.py`

**Interfaces:**
- Consumes: `chunk_text`, `EmbeddingProvider`, `DocumentChunk`, `Document`, `EMBEDDING_MODEL`.
- Produces:
  - `get_session_factory() -> async_sessionmaker[AsyncSession]` (returns `SessionLocal`)
  - `get_embedding_provider() -> EmbeddingProvider` (returns `GeminiEmbeddingProvider(settings.GEMINI_API)`)
  - `async index_document(document_id: UUID, session_factory, embeddings: EmbeddingProvider) -> None`

- [ ] **Step 1: Write the failing tests**

Use the `fake_embeddings` / `failing_embeddings` fixtures added in Step 3; the first one records calls so the tests can prove the provider was reached.

```python
async def test_index_document_stores_chunks_and_marks_ready(session_factory, fake_embeddings):
    # insert user/workspace/document with text "alpha " * 400
    # await index_document(document.id, session_factory, fake_embeddings)
    # assert document.embedding_status == "ready"; indexed_at is not None
    # assert chunks exist, ordered by chunk_index, offsets slice the text exactly
    # assert every chunk.embedding_model == EMBEDDING_MODEL

async def test_index_document_failure_marks_failed_and_keeps_document(..., failing_embeddings):
    # provider raises EmbeddingProviderError
    # assert document still exists, status == "failed", indexed_at is None, zero chunks

async def test_reindex_replaces_previous_chunks(..., fake_embeddings):
    # index once, then replace text with new content and index again
    # assert old chunk ids are gone and new content is present

async def test_index_document_missing_document_returns_quietly(...):
    # random UUID; await index_document -> no exception, no chunks

async def test_index_document_deleted_mid_run_leaves_no_chunks(...):
    # provider deletes the document before returning embeddings
    # assert no chunks and no exception
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/modules/retrieval/test_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Add the test embedding fakes**

In `tests/conftest.py`, above the fixtures:

```python
class FakeEmbeddingProvider:
    # records document_calls/query_calls
    # vector: lowercase [a-z0-9]+ tokens hashed with sha256 into 768 buckets,
    # counts incremented, then L2-normalised; deterministic across processes
    # (used by service, upload, search, and backfill tests)

class FailingEmbeddingProvider:
    async def embed_documents(self, texts): raise EmbeddingProviderError("boom")
    async def embed_query(self, text): raise EmbeddingProviderError("boom")
```

Fixtures: `fake_embeddings` returns one `FakeEmbeddingProvider`; `failing_embeddings` returns `FailingEmbeddingProvider()`.

- [ ] **Step 4: Implement `index_document`**

Two sessions: read document and set `indexing` in the first; embed outside any session; then a write session re-checks existence, deletes existing chunks, `add_all`s new `DocumentChunk` rows with `chunk_index`, `workspace_id`, exact offsets, `embedding_model`, sets `ready` + `indexed_at = datetime.now(timezone.utc)`, and commits once.

On `Exception`: open a fresh session and set `embedding_status = "failed"` for the document ID if it still exists; log `document_id` and `type(exc).__name__` at WARNING. Never log text or the key.

`deps.py` returns `SessionLocal` and a new `GeminiEmbeddingProvider`; both are overridden in tests.

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/modules/retrieval/test_service.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/modules/retrieval/deps.py app/modules/retrieval/service.py \
        tests/conftest.py tests/modules/retrieval/test_service.py
git commit -m "feat(retrieval): index documents in the background"
```

---

### Task 5: Wire uploads and reindex

**Files:**
- Modify: `app/modules/documents/schemas.py` (add status fields and `ReindexResponse`)
- Modify: `app/modules/documents/service.py`
- Modify: `app/modules/documents/router.py`
- Modify: `tests/conftest.py` (app fixture and dependency overrides)
- Create: `tests/modules/retrieval/conftest.py` (users/workspace/member seed + auth headers)
- Test: `tests/modules/retrieval/test_upload.py`

**Interfaces:**
- Consumes: `index_document`, `get_session_factory`, `get_embedding_provider`, `can_manage`, `get_document`.
- Produces:
  - `DocumentSummary.embedding_status: str`, `DocumentSummary.indexed_at: datetime | None`
  - `ReindexResponse(embedding_status: str)` in `documents/schemas.py`
  - `POST /workspaces/{workspace_id}/documents/{document_id}/reindex` → 202 `ReindexResponse(embedding_status="pending")`

- [ ] **Step 1: Write the failing tests**

`tests/modules/retrieval/conftest.py` mirrors the documents seed: creator, admin, member, outsider; one workspace; auth headers from `create_access_token`. Add an `insert_workspace(session_factory, owner, name)` helper that creates a workspace plus an owner membership, for the cross-workspace search test.

`tests/modules/retrieval/test_upload.py`:

```python
async def test_upload_indexes_immediately_with_fake_provider(client, seed):
    # POST a .txt file; assert 201 and embedding_status == "ready"
    # assert document_chunks rows exist and slice the document text

async def test_upload_stays_201_when_provider_fails(client, seed, app):
    # override get_embedding_provider with a raising fake for this test
    # assert 201, document exists, status == "failed", zero chunks

async def test_list_and_detail_expose_embedding_status(client, seed):
    # upload; GET list and detail; both include embedding_status/indexed_at

async def test_reindex_requires_can_manage(client, seed):
    # member uploads; admin reindexes -> 202
    # member reindexes another member's document -> 403
    # outsider -> 403

async def test_reindex_foreign_document_is_404(client, seed):
    # document in workspace A requested through workspace B -> 404
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/modules/retrieval/test_upload.py -v`
Expected: FAIL — route missing / response field missing.

- [ ] **Step 3: Add the app fixture and dependency overrides**

In `tests/conftest.py`, add an `app` fixture that calls `create_app()`, make `client` depend on `app` and `fake_embeddings`, and register:

```python
app.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
app.dependency_overrides[get_session_factory] = lambda: session_factory
```

This makes background tasks use the in-memory database and never the network. Keep the fake provider itself from Task 4; do not duplicate it here.

- [ ] **Step 4: Implement schema, service, and routes**

- `DocumentSummary`: add `embedding_status: str` and `indexed_at: datetime | None`.
- `documents/schemas.py`: add `ReindexResponse(embedding_status: str)`.
- `documents/service.py` `load_only(...)`: add both new columns.
- `documents/router.py` upload: add `background_tasks: BackgroundTasks`, `session_factory`, `embeddings` dependencies; after `ingest`, call `background_tasks.add_task(index_document, document.id, session_factory, embeddings)`; return 201 unchanged.
- Add the reindex route:

```python
@router.post("/{document_id}/reindex", response_model=schemas.ReindexResponse, status_code=202)
async def reindex_document(...):
    document = await service.get_document(session, workspace_id, document_id)
    if not service.can_manage(member, document):
        raise HTTPException(403, "Insufficient permissions")
    document.embedding_status = "pending"
    await session.commit()
    background_tasks.add_task(index_document, document.id, session_factory, embeddings)
    return schemas.ReindexResponse(embedding_status="pending")
```

- [ ] **Step 5: Run to verify pass and the full documents suite**

Run: `uv run pytest tests/modules/retrieval/test_upload.py tests/modules/documents -q`
Expected: PASS. (FastAPI's `ASGITransport` awaits background tasks before the client call returns, so `ready` is visible in the test.)

- [ ] **Step 6: Commit**

```bash
git add app/modules/documents/schemas.py app/modules/documents/service.py \
        app/modules/documents/router.py \
        tests/conftest.py tests/modules/retrieval/conftest.py \
        tests/modules/retrieval/test_upload.py
git commit -m "feat(retrieval): schedule indexing on upload and expose reindex"
```

---

### Task 6: Search service and endpoint

**Files:**
- Create: `app/modules/retrieval/router.py`
- Modify: `app/modules/retrieval/schemas.py` (add `SearchRequest`, `SearchResult`)
- Modify: `app/modules/retrieval/service.py` (add `SearchHit`, `search`, `_cosine_similarity`)
- Modify: `app/api/router.py` (include the retrieval router)
- Test: `tests/modules/retrieval/test_search.py`

**Interfaces:**
- Consumes: `EmbeddingProvider.embed_query`, `DocumentChunk`, `Document`, `EMBEDDING_MODEL`.
- Produces:
  - `@dataclass(frozen=True) class SearchHit: chunk_id, document_id, filename, chunk_index, content, score, char_start, char_end`
  - `async search(session, workspace_id: UUID, query_vector: list[float], top_k: int) -> list[SearchHit]`
  - `POST /workspaces/{workspace_id}/search` → `list[SearchResult]`

- [ ] **Step 1: Write the failing tests**

```python
async def test_search_ranks_matching_chunk_first(client, seed):
    # upload "alpha alpha alpha" and "beta beta beta" to the same workspace
    # POST {"query": "alpha", "top_k": 5}; assert first content contains "alpha"

async def test_search_is_workspace_scoped(client, seed, session_factory):
    # create workspace B with the same owner via insert_workspace()
    # upload "alpha" to workspace A and "alpha" to workspace B
    # search A -> every result.document_id belongs to A; search B -> B only

async def test_search_respects_top_k(client, seed):
    # upload a long document; top_k=2 returns exactly 2 results

async def test_search_empty_workspace_returns_empty_list(client, seed):
    # POST search before any upload -> 200 []

async def test_search_rejects_blank_query_and_bad_top_k(client, seed):
    # "" -> 422; "   " -> 422; top_k=0 -> 422; top_k=21 -> 422

async def test_search_ignores_other_embedding_models(client, seed, session_factory):
    # insert a chunk with embedding_model="other-model"
    # assert it never appears in results

async def test_search_provider_failure_returns_503(client, seed, app):
    # override provider with a raising fake; assert 503

async def test_search_non_member_returns_403(client, seed):
    # outsider token -> 403
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/modules/retrieval/test_search.py -v`
Expected: FAIL — route not found.

- [ ] **Step 3: Implement search**

```python
async def search(session, workspace_id, query_vector, top_k):
    if session.get_bind().dialect.name == "postgresql":
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        stmt = (
            select(DocumentChunk, Document.filename, (1 - distance).label("score"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.workspace_id == workspace_id,
                DocumentChunk.embedding_model == EMBEDDING_MODEL,
            )
            .order_by(distance, DocumentChunk.document_id, DocumentChunk.chunk_index)
            .limit(top_k)
        )
        # map rows to SearchHit
    # SQLite: select chunks + filenames for the workspace/model, compute exact
    # cosine in Python, sort by (-score, str(document_id), chunk_index), slice top_k
```

`_cosine_similarity(a, b)` returns 0.0 if either norm is 0.

`schemas.py`:

```python
class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)

    @field_validator("query")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str: ...
```

`router.py` embeds the query, maps `EmbeddingProviderError` to 503 `"Embedding provider unavailable"`, calls `search`, and returns `SearchResult`s. Register in `app/api/router.py`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/modules/retrieval/test_search.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/modules/retrieval/router.py app/modules/retrieval/schemas.py \
        app/modules/retrieval/service.py app/api/router.py \
        tests/modules/retrieval/test_search.py
git commit -m "feat(retrieval): add workspace-scoped similarity search"
```

---

### Task 7: Backfill, documentation, end-to-end verification

**Files:**
- Create: `app/modules/retrieval/backfill.py`
- Test: `tests/modules/retrieval/test_backfill.py`
- Modify: `apps/api/AGENTS.md`, `apps/api/README.md`, `AGENTS.md` (root "next up")

**Interfaces:**
- Consumes: `index_document`, `Document`.
- Produces:
  - `async backfill(session_factory, embeddings) -> tuple[int, int]` (ready, failed counts)
  - `python -m app.modules.retrieval.backfill` entry point

- [ ] **Step 1: Write the failing tests**

```python
async def test_backfill_indexes_pending_and_skips_ready(session_factory, fake_embeddings):
    # three documents: pending, failed, ready
    # await backfill(...)
    # assert pending and failed became ready, ready was not re-embedded,
    # and the returned counts match

async def test_backfill_continues_after_one_failure(session_factory, fake_embeddings):
    # provider raises for the first text only; second document still becomes ready
    # assert counts reflect one ready and one failed
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/modules/retrieval/test_backfill.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement backfill**

Select document IDs where `embedding_status != "ready"`, close the session, call `index_document` sequentially, then re-read statuses to count `ready` and `failed`. `main()` uses `SessionLocal` and `GeminiEmbeddingProvider(settings.GEMINI_API)`; `if __name__ == "__main__": asyncio.run(main())`.

- [ ] **Step 4: Run the full suite and lint**

Run:

```bash
uv run pytest -q
uv run ruff check app tests
uv run ruff format --check app tests
```

Expected: all clean.

- [ ] **Step 5: Manual end-to-end check against Neon**

```bash
uv run alembic upgrade head
uv run python -m app.modules.retrieval.backfill
uv run fastapi dev app/main.py
```

Then, with a signed-in token and workspace:

```bash
curl -s -X POST "$API/api/v1/workspaces/$WS/documents" \
  -H "Authorization: Bearer $TOKEN" -F "file=@sample.md" | jq
curl -s "$API/api/v1/workspaces/$WS/documents/$DOC" \
  -H "Authorization: Bearer $TOKEN" | jq '.embedding_status'
curl -s -X POST "$API/api/v1/workspaces/$WS/search" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"what is this about?","top_k":3}' | jq
```

Expected: upload 201; status becomes `ready`; search returns chunks with `filename`, `chunk_index`, `score`, and offsets. Repeat the search with a second workspace and confirm it returns `[]` for text only in the first.

- [ ] **Step 6: Update documentation**

- `apps/api/AGENTS.md`: add `modules/retrieval/` and its tests to §3; add `GEMINI_API` to §6; record pgvector + the new migration in §7; add the fake provider/background-task notes to §8; mark Milestone 5 complete in §13; add the design/plan pointers in §14.
- `apps/api/README.md`: add retrieval to the feature list and mention `python -m app.modules.retrieval.backfill`.
- Root `AGENTS.md`: change "Next up: Milestone 5 (Retrieval)" to Milestone 6 (Chat/RAG) and add the retrieval spec/plan links.

- [ ] **Step 7: Commit**

```bash
git add app/modules/retrieval/backfill.py tests/modules/retrieval/test_backfill.py \
        apps/api/AGENTS.md apps/api/README.md AGENTS.md
git commit -m "docs(api): record milestone 5 retrieval"
```

---

## Done means

- `uv run pytest`, `uv run ruff check app tests`, and
  `uv run ruff format --check app tests` are clean.
- A real document uploads, reaches `ready`, and a search returns its chunks
  ranked with scores and exact character offsets.
- A second workspace cannot retrieve the first workspace's chunks.
- A provider failure leaves a `failed` document (not a lost upload) and reindex
  repairs it.
- Existing documents can be indexed with the backfill command.
- `AGENTS.md`, `README.md`, and `.env.example` describe the module as built.
