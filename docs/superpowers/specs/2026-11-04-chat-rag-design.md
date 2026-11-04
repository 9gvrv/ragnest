# Ragnest API — Milestone 6: Chat (RAG) — Design

**Date:** 2026-11-04
**Status:** proposed
**Scope:** `apps/api/` only. The web chat UI is a separate milestone.

---

## 1. Intent

Milestone 5 can answer "which chunks are closest to this text?" This milestone
turns that into the thing a person actually wants: ask a question in a
workspace, watch an answer stream back, and see exactly which documents and
character spans it came from.

The workspace remains the only tenant. Retrieval already refuses to cross
workspace boundaries; chat inherits that and adds a stricter rule — the model
is told to answer **only** from the chunks retrieved for this workspace and to
say so when they do not contain the answer.

---

## 2. Goals

1. A workspace member can create a conversation, ask a question, and receive a
   streamed answer grounded in that workspace's indexed chunks.
2. Every answer carries citation metadata (`document_id`, filename, chunk
   ordinal, `char_start`/`char_end`, excerpt, score) that outlives the source
   document.
3. Conversations and messages are persisted per user, with the same cascade
   behaviour as documents.
4. The pipeline is testable without network access and without a real key.
5. Free-tier quotas are respected deliberately: bounded prompt, bounded answer,
   no hidden retries, no extra model calls.

## 3. Non-goals

- Query rewriting or follow-up question resolution. Retrieval uses the literal
  question; a follow-up like "and the second one?" may retrieve poorly.
- Reranking, hybrid/BM25 search, neighbour-chunk expansion, deduplication.
- Page-level citations (M4 does not store page boundaries).
- Regenerate, edit message, stop button, message feedback, sharing, export.
- Team-shared conversations. Conversations are private to their author; the
  filter is one line if that changes.
- An LLM-generated title. The title is the first question, truncated.
- Web UI, document upload UI, streaming proxy.
- Token accounting dashboards. Usage may be logged, not stored in v1.
- Serialising concurrent sends to one conversation. Two in-flight requests can
  interleave their prompts and rows; order is still deterministic by
  `created_at`. No lock, no 409 in v1.

## 4. Anti-goals

- An answer that is not grounded in the retrieved sources.
- A citation that points at a chunk in another workspace.
- Holding a database connection open for the lifetime of a stream.
- Leaking chain-of-thought deltas into the answer text.
- Retrying a generation that has already streamed tokens and duplicating text.
- Committing or logging the Groq or Gemini key.

---

## 5. Constraints

- **Embeddings are fixed.** `document_chunks.embedding` is `vector(768)` and
  `embedding_model = 'gemini-embedding-001'`. Changing the embedding model is a
  migration plus re-embedding every document. The Gemini key stays on
  embeddings only.
- **Generation uses Groq free tier** through its OpenAI-compatible API. One
  question costs one embedding call (small) and one completion (large).
- **Existing patterns are law.** Provider protocols, `httpx` clients with
  `MockTransport` tests, `app/modules/<feature>/`, async SQLAlchemy, SQLite
  tests, and the aggregate router all carry over unchanged.
- **The web app has no documents UI.** A chat UI on the web would have nothing
  to chat about yet, so this milestone proves the pipeline with curl and tests.

---

## 6. Decisions at a glance

| Question | Decision |
| --- | --- |
| Generation provider | Groq, via the OpenAI-compatible HTTP API |
| HTTP client | Raw `httpx` (no `groq` package), behind an `LLMProvider` protocol |
| Default model | `openai/gpt-oss-120b`, `reasoning_effort="low"`, overridable by env |
| Transport | Server-Sent Events (`text/event-stream`) from the messages endpoint |
| Persistence | `conversations` + `messages`, both workspace-scoped |
| Conversation visibility | Author only; members-not-author 404, non-members 403 at the workspace gate |
| Citations | JSON snapshot on the assistant message |
| Empty retrieval | Fixed refusal, persisted, **no** LLM call |
| Score threshold | None in v1; the prompt and citations carry the grounding burden |
| History | Last 6 messages, char-capped |
| Retrieval | `top_k = 8`, reusing `retrieval.service.search` |
| Retries | None for generation; one request, explicit error mapping |

---

## 7. Data model

### `conversations`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | `uuid4` |
| `workspace_id` | UUID FK → `workspaces.id` | `ON DELETE CASCADE`, not null |
| `created_by` | UUID FK → `users.id` | `ON DELETE CASCADE`, not null |
| `title` | `String(120)` | not null, default `"New conversation"` |
| `created_at` | timestamp | `TimestampMixin` |
| `updated_at` | timestamp | `TimestampMixin`, touched on every message |

Index: `ix_conversations_workspace_author_updated`
(`workspace_id`, `created_by`, `updated_at`) for the list query.

### `messages`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | `uuid4`, generated before streaming starts |
| `conversation_id` | UUID FK → `conversations.id` | `ON DELETE CASCADE`, not null |
| `role` | `String(16)` | `"user"` or `"assistant"`, not null |
| `content` | `Text` | not null |
| `citations` | JSONB (PG) / JSON (SQLite) | not null, default `[]` |
| `model` | `String(64)` | nullable; assistant rows only |
| `finish_reason` | `String(32)` | nullable; `stop`, `length`, `no_context`, `error`, `cancelled` |
| `created_at` | timestamp | set explicitly with `datetime.now(UTC)` |

Index: `ix_messages_conversation_created` (`conversation_id`, `created_at`).

`created_at` is set in Python rather than by `server_default=func.now()` so
that a question and its answer cannot tie in ordering. Read messages ordered by
`(created_at, id)`.

The JSONB/JSON variant lives in `app/modules/chat/types.py`, copying the
`Vector768.with_variant(...)` pattern from retrieval:

```python
CitationsJSON = JSONB().with_variant(JSON(), "sqlite")
```

### Citation object

```json
{
  "n": 1,
  "document_id": "8b1d...",
  "chunk_id": "f40a...",
  "filename": "billing.md",
  "chunk_index": 3,
  "char_start": 210,
  "char_end": 980,
  "excerpt": "Billing retries are handled by ...",
  "score": 0.71
}
```

`excerpt` is the first 320 characters of the chunk (plus `…` when truncated),
so the snapshot stays useful after the document is hard-deleted. `n` matches
the `[n]` markers in the answer. The full chunk text is **not** stored in the
citation; it is in the prompt only.

### Cascades

- delete workspace → conversations → messages → citations (JSON in the row)
- delete conversation → messages
- delete user → conversations (and their messages)
- delete document → chunks, but **not** historical citations; the UI checks
  whether the document still exists before linking.

---

## 8. API surface

Base: `/api/v1/workspaces/{workspace_id}/conversations`

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| POST | `` | `{title?: str}` | `201 ConversationSummary` |
| GET | `` | — | `200 list[ConversationSummary]` |
| GET | `/{conversation_id}` | — | `200 ConversationDetail` |
| DELETE | `/{conversation_id}` | — | `204` |
| POST | `/{conversation_id}/messages` | `{content: str}` | `200 text/event-stream` |

`ConversationSummary`: `id`, `workspace_id`, `created_by`, `title`,
`created_at`, `updated_at`.

`ConversationDetail`: summary + `messages: list[MessageOut]`.

`MessageOut`: `id`, `role`, `content`, `citations: list[Citation]`, `model`,
`finish_reason`, `created_at`.

`MessageCreate`: `content` stripped, 1–2000 characters (reuse
`MAX_QUERY_CHARS`), blank rejected with 422.

List is newest-first by `updated_at`, filtered to `created_by = current_user`.
Detail and delete load by `(id, workspace_id, created_by)`. Because
`require_workspace_member` runs first, an outsider gets 403 without the
conversation being looked up; a member who is not the author gets **404**, so
ownership is what stays secret.

Title: on the first user message, if the title is still `"New conversation"`,
set it to `" ".join(question.split())[:80]`. No extra model call.

No pagination in v1. Detail returns all messages; a workspace conversation is
unlikely to exceed a few hundred in this milestone.

---

## 9. Streaming protocol

Headers:

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

Events, in order:

```
event: sources
data: {"user_message_id":"...","assistant_message_id":"...","sources":[Citation,...],"no_context":false}

event: token
data: {"delta":"Billing retries are"}

event: token
data: {"delta":" handled by ... [1]"}

event: done
data: {"assistant_message_id":"...","finish_reason":"stop","cited":[1]}
```

- `sources` is always first, before the model is asked for anything the client
  has not already been told. It lets the UI render the source list immediately.
- `token` deltas are plain text, already stripped of reasoning deltas.
- `done.cited` is the de-duplicated, in-range list of markers found in the
  answer, in order of first appearance.
- `event: error` (`{"detail": "..."}`) is used **only after** the 200 headers
  have been sent. It is **terminal**: no `done` follows it. A successful stream
  ends with exactly one `done`; a failed one ends with exactly one `error`.
  Errors before the stream starts are normal JSON responses with a non-2xx
  status (see §15).
- On the no-context path the stream is `sources` (empty), one `token` with the
  refusal, then `done` with `finish_reason = "no_context"` — the same value
  stored on the row.

The web layer will later proxy this stream; it must forward the body without
buffering. Not built here.

### Pre-flight

The endpoint does the cheap work before returning `StreamingResponse`:

1. Validate membership + conversation ownership.
2. `embed_query(question)` → retrieval. Failure here returns JSON 503 and
   **nothing is persisted**.
3. Persist the user message (id generated up front).
4. Build the prompt.
5. Open the provider stream and await the **first `LLMDelta`**.

If step 5 fails (429, 5xx, timeout, bad key, or an `LLMFinish` before any
text), the response is a normal JSON error. The user message stays persisted,
so history shows the question and the client can retry. If it succeeds, the
first delta is handed to the streaming generator, which emits `sources`, then
that delta and the rest.

Once tokens have been sent, failures become `event: error`; the partial answer
is persisted with `finish_reason = "error"` (an empty partial is not persisted).
On client disconnect, the partial answer is persisted best-effort with
`finish_reason = "cancelled"`, using a fresh session and `asyncio.shield`; if
that fails, it is logged and ignored.

---

## 10. RAG pipeline

1. **Load.** `conversations` row must match `(id, workspace_id, created_by)`.
2. **Embed.** `EmbeddingProvider.embed_query(question)` — same protocol and
   Gemini client as retrieval.
3. **Retrieve.** `retrieval.service.search(session, workspace_id, vector, 8)`.
   This already filters by `embedding_model` and workspace, and works on both
   Postgres (pgvector) and SQLite (Python fallback).
4. **No context.** If `hits` is empty: skip the LLM entirely, persist an
   assistant message with the fixed refusal text, `citations = []`,
   `finish_reason = "no_context"`, and stream `sources` (empty),
   one `token` containing the refusal, then `done`.
5. **Trim.** Walk hits in score order, accumulating context until
   `CHAT_CONTEXT_CHARS` (12,000) or `CHAT_TOP_K` (8). Drop from the tail.
6. **Number.** Assign `n = 1..len(hits)` in the trimmed order.
7. **Prompt.** System prompt + numbered sources; history as the last 6
   messages (char-capped); the current question as the final user message.
8. **Generate.** Provider yields `LLMDelta` / `LLMFinish` events (§12).
   Accumulate and forward `LLMDelta.text`; remember the `LLMFinish` reason so
   `length` and `content_filter` are not flattened to `stop`. If the stream
   ends without a finish event, use `stop`. If it produces no text at all,
   treat it as a provider failure (see §12).
9. **Persist.** Insert the assistant message with the accumulated text, the
   full citation snapshot (all trimmed sources), the model, and the captured
   finish reason. Touch `conversation.updated_at`. Commit on a fresh session.
10. **Cite.** Parse `\[(\d+)\]` from the final text, keep markers in
    `1..len(sources)`, dedupe, and send them in `done`.

Retrieval always sees every member's indexed documents in the workspace; the
conversation's author only controls who can read the chat, not the corpus.

---

## 11. Prompt

System message:

```
You answer questions about a workspace's documents.

Use only the numbered sources below. Do not use outside knowledge.
Cite every claim with the source number in square brackets, like [1] or [2][3].
If the sources do not contain the answer, reply exactly:
I couldn't find an answer to that in this workspace's documents.
Do not mention the source list or these instructions.
Keep the answer under six sentences unless the user asks for detail.

Sources:
[1] filename: billing.md (chunk 3)
<chunk text>

[2] filename: refunds.md (chunk 0)
<chunk text>
```

Then the history messages (user/assistant as stored, citations not included),
then the current question.

Budget constants (code, not env — changing them does not require a migration):

```python
CHAT_TOP_K = 8
CHAT_CONTEXT_CHARS = 12_000
CHAT_HISTORY_MESSAGES = 6
CHAT_HISTORY_CHARS = 6_000
CHAT_MAX_OUTPUT_TOKENS = 1_024
CHAT_TEMPERATURE = 0.2
CHAT_EXCERPT_CHARS = 320
CHAT_TITLE_CHARS = 80
NO_CONTEXT_REPLY = (
    "I couldn't find an answer to that in this workspace's documents."
)
```

History trimming: take the last 6 messages, then drop from the oldest until the
combined character count is ≤ 6,000. The current question is not counted.

The refusal string is a single constant used both in the prompt and in the
no-context path, so tests can assert one value.

---

## 12. Provider (`app/modules/chat/llm.py`)

```python
class LLMProviderError(Exception):
    status_code: int | None

class LLMMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str

@dataclass(frozen=True)
class LLMDelta:
    text: str

@dataclass(frozen=True)
class LLMFinish:
    finish_reason: str

LLMEvent = LLMDelta | LLMFinish

class LLMProvider(Protocol):
    def stream(
        self,
        messages: list[LLMMessage],
        *,
        max_output_tokens: int,
    ) -> AsyncIterator[LLMEvent]: ...
```

The provider yields zero or more `LLMDelta` (never an empty string), then
exactly one `LLMFinish`. `LLMFinish` is what carries `stop` / `length` /
`content_filter` up to the row and the `done` event; an `Iterator[str]` would
have forced the service to guess. If the transport ends without a finish
chunk, the provider synthesises `LLMFinish("stop")`. If it ends without any
content at all, the provider raises `LLMProviderError` ("empty completion") so
the endpoint returns a normal error rather than persisting a blank answer.

`OpenAICompatibleLLMProvider(api_key, base_url, model, reasoning_effort, client=None)`

- `POST {base_url}/chat/completions`
- Headers: `Authorization: Bearer <key>`, `Content-Type: application/json`
- Body:

```json
{
  "model": "openai/gpt-oss-120b",
  "messages": [...],
  "temperature": 0.2,
  "max_completion_tokens": 1024,
  "reasoning_effort": "low",
  "stream": true
}
```

- `reasoning_effort` is omitted when the setting is blank, so a non-reasoning
  model can be swapped in without a code change.
- Reads `text/event-stream` with `client.stream(...)` + `aiter_lines()`:
  ignore blank lines, `:` comments, and `event:` lines; parse `data: {...}`;
  stop at `data: [DONE]`.
- Yields `choices[0].delta.content` when it is a non-empty string. Ignores
  `delta.reasoning` — chain-of-thought must never reach the user.
- A chunk containing `{"error": ...}` raises `LLMProviderError`.
- HTTP status → `LLMProviderError(status_code=...)`; no retries. This differs
  deliberately from `GeminiEmbeddingProvider`, which retries because indexing
  is not user-facing and has no streaming state to protect.
- Timeout: `httpx.Timeout(120.0, connect=10.0)`.
- Client ownership mirrors embeddings: use an injected client if given, else
  create and close one per call.
- `stream()` is an async generator; the router calls `anext()` once to
  pre-flight, then closes it in `finally`. An `LLMDelta` becomes the first
  streamed token; any exception (or an `LLMFinish` before the first delta)
  becomes a normal JSON error before the SSE headers are sent.

An adapter for another OpenAI-compatible vendor (OpenAI, Gemini's compat
endpoint, a local server) is a config change, not a new class, as long as the
wire format stays Chat Completions.

---

## 13. Config

| Setting | Default | Notes |
| --- | --- | --- |
| `LLM_API_KEY` | — (required) | Groq key; never logged |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | no `.env` entry needed |
| `LLM_MODEL` | `openai/gpt-oss-120b` | from `/openai/v1/models` |
| `LLM_REASONING_EFFORT` | `low` | blank omits the field |

`.env.example` documents the three optional values and the required key.
`tests/conftest.py` sets `LLM_API_KEY=test-llm-key` before importing `app.*`,
alongside the existing dummy values.

Fallback if free-tier limits bite: `LLM_MODEL=openai/gpt-oss-20b`. The design
does not change.

---

## 14. Permissions

| Action | Rule |
| --- | --- |
| Create conversation | `require_workspace_member` |
| List conversations | own only (`created_by = current_user`) |
| Read conversation | author only, else 404 |
| Send message | author only, else 404 |
| Delete conversation | author only, else 404 |
| Retrieval corpus | every document in the workspace, regardless of uploader |

Every conversation route runs `require_workspace_member` **first**. A
non-member (or an author later removed from the workspace) gets 403 at that
gate; the conversation's existence is never confirmed. A *member* who is not
the author gets 404. Workspace membership is not secret; conversation
ownership is.

Admins do **not** get access to other people's conversations in v1. That is a
deliberate privacy call; the workspace is shared, the chat history is not.

---

## 15. Failure modes

| Condition | Response |
| --- | --- |
| Not authenticated | 401 |
| Not a workspace member | 403 `Not a member` (checked before conversation lookup) |
| Member, but not the conversation author | 404 `Conversation not found` |
| Blank / >2000-char question | 422 |
| Embedding provider fails | 503 `Embedding provider unavailable`; nothing persisted |
| Zero retrieved chunks | 200 SSE; refusal persisted; LLM not called |
| Groq 429 before first token | 429 `Answer model is rate limited` + `Retry-After` if present |
| Groq 401/403 | 503 `Answer model unavailable` (do not leak provider auth detail) |
| Groq 5xx / connect timeout before first token | 503 `Answer model unavailable` |
| Groq fails after tokens started | 200 SSE, terminal `event: error` (no `done`); partial persisted as `error` |
| Client disconnects mid-answer | best-effort partial persisted as `cancelled` |
| Document deleted later | citations still render; link omitted if the document is gone |

---

## 16. Free-tier budget

Per question, approximately:

- Gemini: one `embed_query` (~20 tokens). Unchanged from retrieval.
- Groq: prompt ~2–3k tokens (8 chunks × ≤800 chars + history + system) and
  ≤1k output tokens.

That means single-digit questions per minute on Groq's free tier is the
realistic ceiling. Manual verification should use two or three questions, not a
load test. Automated tests never touch either provider.

No query-rewrite call, no title-generation call, no summarisation call, no
retries. The only optional second call anyone might add later is a follow-up
rewrite — explicitly out of scope.

---

## 17. Testing

### Fixtures (root `tests/conftest.py`)

- `fake_llm`: deterministic `LLMProvider` that yields
  `LLMDelta("Grounded ")`, `LLMDelta("answer ")`, `LLMDelta("[1]")`,
  `LLMFinish("stop")`; records the messages it was given; can be told to fail
  immediately or after N deltas.
- `failing_llm`: raises `LLMProviderError` before yielding.
- Override `get_llm_provider` in the `app` fixture, exactly as
  `get_embedding_provider` and `get_session_factory` are overridden today.
- `tests/modules/chat/conftest.py` seeds the same creator/admin/member/outsider
  shape as retrieval.

### Provider tests (`test_llm.py`)

`httpx.MockTransport`:

- request URL, auth header, model, temperature, `max_completion_tokens`,
  `stream: true`
- SSE split across lines/chunks; `[DONE]`; comments ignored
- `delta.content` null and `delta.reasoning` ignored
- HTTP 429 → `LLMProviderError` with `status_code == 429`
- HTTP 500, connect error, malformed JSON
- `reasoning_effort` omitted when blank

### Prompt tests (`test_prompts.py`)

- source numbering and ordering
- context trim at the char cap; tail dropped
- history cap (last 6, then char trim)
- refusal constant used verbatim

### Service tests (`test_service.py`)

- user + assistant messages persisted in order; `updated_at` touched
- citation snapshot has the right `n`, document, span, excerpt
- citation parsing: `[1]`, `[1][2]`, duplicates, `[99]` dropped
- no-context path: fake LLM not called, refusal persisted
- provider failure after N deltas: partial persisted with `error`
- conversation in another workspace is invisible

### Router tests (`test_router.py`)

- create/list/detail/delete happy paths
- another member gets 404; an outsider gets 403 at the workspace gate; a
  removed author gets 403
- blank and over-long question 422
- SSE event order: `sources` → `token`* → `done`
- `done.cited` matches markers
- no-context: `done.finish_reason == "no_context"`, refusal streamed
- empty workspace streams the refusal and never calls the fake LLM
- failing LLM before first token returns 503 JSON; user message persists
- mid-stream failure ends with `error` and no `done`, partial row persisted
- conversation list is newest-first

### Model tests (`test_model.py`)

- round-trip citations on SQLite
- cascade: delete workspace → conversations and messages gone
- cascade: delete conversation → messages gone
- `conversation_id` index/order behaviour

### Not in CI

- Real Groq call, real Gemini embedding, pgvector search, and HNSW behaviour.
  These are manual checks against Neon + the real keys.

---

## 18. Migration

One revision, `down_revision = "299585b2a1a6"` (retrieval).

Upgrade:

1. `CREATE TABLE conversations` with FKs and the list index.
2. `CREATE TABLE messages` with `citations JSONB NOT NULL DEFAULT '[]'::jsonb`,
   the conversation FK, and the ordering index.
3. Downgrade drops `messages`, then `conversations`.

Tests use `Base.metadata.create_all` on SQLite, so the migration itself is
verified manually with `uv run alembic upgrade head` against Neon.

---

## 19. Module layout

```
app/modules/chat/
├── __init__.py
├── constants.py    # budgets, top_k, refusal text
├── deps.py         # get_llm_provider
├── llm.py          # protocol, OpenAI-compatible provider, errors
├── models.py       # Conversation, Message, MessageRole
├── prompts.py      # prompt builder, history/context trimming, citation parsing
├── router.py       # conversation CRUD + SSE messages endpoint
├── schemas.py      # API models + Citation
├── service.py      # load/create/list/delete, persist, stream orchestration
└── types.py        # CitationsJSON variant

tests/modules/chat/
├── __init__.py
├── conftest.py
├── test_llm.py
├── test_model.py
├── test_prompts.py
├── test_router.py
└── test_service.py
```

Registration: `app/db/models.py` imports both models; `app/api/router.py`
includes `chat_router.router`.

`chat/deps.py` reuses `retrieval.deps.get_session_factory` for the
post-stream writes — the same override the test harness already installs — and
adds `get_llm_provider`.

---

## 20. Manual verification (Neon + real keys)

1. `uv run alembic upgrade head`; `uv run alembic current`.
2. Start the API; upload a `.md` file; wait for `embedding_status = ready`.
3. Create a conversation; POST a question with `curl -N`; confirm `sources`,
   token deltas, and `done`.
4. Ask something absent from the document; confirm the refusal and
   `no_context`.
5. Delete the document; reload the conversation; citations still render with
   filenames and excerpts.
6. Sign in as a second member; confirm the first user's conversation is 404.
7. Check Groq usage in its console after two or three questions.

---

## 21. Left to builder

- Exact wording/order of the system prompt, as long as the citation and refusal
  rules survive.
- Whether to log Groq `usage` (the final chunk may include it) or ignore it.
- Whether to send an SSE heartbeat before the first token; not planned.
- Whether `excerpt` cuts at a word boundary.
- Exact `Retry-After` parsing from Groq.
- Whether `GET /conversations/{id}` should cap message count; not planned in
  v1.
- How the future web UI renders markers and deleted-document citations.

---

## 22. Next milestone

**Web: documents + chat.** Upload/list documents, then a workspace chat page
that consumes this SSE contract, renders `sources`, and makes `[n]` markers
clickable. That milestone owns the streaming proxy under `app/api/**` and the
`/workspaces/[id]/chat` route. It is deliberately not bundled here because the
web app currently cannot upload a document at all.
