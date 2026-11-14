# RAG benchmark suite — Implementation Plan

> **For agentic workers:** this suite produces publishable numbers, so the
> measurement logic is written by the human, not the mentor. Each task states
> who writes which file. Verification is a command and its output, never "looks
> right".
>
> **Spec:** `docs/superpowers/specs/2026-11-14-rag-benchmark-design.md`

**Goal:** A committed, rerunnable benchmark over the 17-document Tarnwick corpus
that yields retrieval quality, chunk-size decision, chat latency, citation
accuracy, abstention rate, and judge-scored groundedness.

**Tech Stack:** Python 3.13, `uv`, existing `httpx` + SQLAlchemy + app modules,
real Gemini embeddings and the Groq generation model. No new dependency.

## Global Constraints

- `apps/api/bench/` is a script package: add `bench/__init__.py`, run it as
  `uv run python -m bench.<name>` from `apps/api/`.
- It is not a test: outside `testpaths`, never imported by `tests/`, never in CI.
- `uv run ruff check .` and `uv run ruff format --check .` stay clean, including
  `bench/`.
- Never print or persist `DATABASE_URL`, `GEMINI_API`, `LLM_API_KEY`, or a JWT.
- Every results file records `git_sha`, `date`, `embedding_model`, `llm_model`,
  `top_k`, `chunk_target`, `chunk_overlap`, and `mode`.
- Bench workspaces are disposable and named `bench-<YYYY-MM-DD>-<size>`. Only
  `cleanup.py` deletes them, and it deletes by name prefix.
- Retrieval experiments run in-process; only the chat experiment uses HTTP.
- Free-tier pacing: `EMBEDDING_BATCH_SIZE=16` is already respected; sleep between
  queries if a 429 appears rather than retrying hot.

## Review Focus

1. **No workspace bleed.** A retrieval run must never see another workspace's
   chunks. Assert the hit set's `document_id` values are exactly the 17 seeded
   documents.
2. **No hidden nondeterminism in scoring.** Running `retrieve.py` twice on the
   same seeded workspace must produce identical metrics. If it does not, the
   metric code is wrong, not the model.
3. **Labels are read, never recomputed.** Metrics come from
   `questions.jsonl.source_documents`. A script that "fixes" labels from
   retrieval output is a bug.
4. **Judge separation.** `correctness` never reads sources; `grounded` never
   reads the reference answer. Check the rendered prompt shows both blocks.
5. **Honest latency labels.** Every latency file states `mode`, sample count,
   and that the path is laptop → provider.

---

### Task 1: Corpus validator — `bench/validate.py`

**Who:** mentor writes; human runs and reads.

Port the three checks already run ad hoc into a committed script:

- every fact's key value appears in its owning document and in no distractor;
- no question shares a verbatim word run of ≥6 with its source documents;
- the unanswerable questions have no evidence in any document, matched on word
  boundaries (the ad hoc version matched `trial` inside `industrial`).

Exit non-zero on any violation. Print one line per check with a count.

**Verification:** `uv run python -m bench.validate` prints three `PASS` lines and
exits 0 on the current corpus. Deliberately break one label locally and confirm
it exits 1.

---

### Task 2: Seed — `bench/seed.py`

**Who:** mentor writes; human runs.

1. Create or reuse a bench user (`bench@tarnwick.example`) directly through the
   session factory — `users.password_hash` is nullable, so no password is
   involved.
2. For each chunk configuration, create a workspace + creator membership named
   `bench-<date>-<size>`.
3. For each corpus file, insert a `Document` row with `extracted_text`, real
   `char_count`/`size_bytes`, `content_type="text/markdown"`, `page_count=None`,
   then call `index_document(...)` with the real `GeminiEmbeddingProvider`.
4. Write `runs/<run>/seed.json`: workspace ids, document ids by filename, chunk
   counts, total chunks, wall-clock indexing time.
5. Skip re-embedding when a run directory for today's corpus hash already exists
   and its workspace ids are still present.

**Verification:** `uv run python -m bench.seed` reports 17 documents and 125
chunks at 800/120; a second run reuses rather than re-embedding (it prints
"reused" and leaves `seed.json` untouched, so the first indexing time survives).

---

### Task 3: Retrieval metrics

**Who:** `bench/metrics.py` is written and its cases are checked by hand
(`recall_at`, `recall_all_at`, `reciprocal_rank`, `mean`, `summarize`,
`percentile`, `summarize_support`); mentor writes `bench/retrieve.py` (IO,
provider calls, result writing).

`bench/metrics.py` must expose pure functions over plain data:

```python
def recall_at(k, ranked_doc_ids, gold_doc_ids) -> float      # "any gold doc"
def recall_all_at(k, ranked_doc_ids, gold_doc_ids) -> float  # "all gold docs"
def reciprocal_rank(k, ranked_doc_ids, gold_doc_ids) -> float
def mean(values) -> float
```

`bench/retrieve.py` embeds each question with `RETRIEVAL_QUERY`, calls
`service.search(session, workspace_id, vector, top_k=10)`, records the ranked
`document_id` list, and writes per-question rows plus aggregates.

It also records chunk-level support, because document-level recall alone was
proven inflated (design §10a): each hit carries `supports`, the facts whose
anchor value appears in that chunk, and `metrics.summarize_support` turns that
into `support@k_any` / `support@k_all`. The anchor rule lives in
`bench/support.py` and is shared with `bench/validate.py`, so validation and
scoring cannot drift apart. A run with no anchor for a question's fact fails
loudly instead of scoring it as a silent miss.

**Verification:** `uv run python -m bench.retrieve` writes
`runs/<run>/retrieval.json`; run it twice and `diff` the two metric blocks —
identical, including the `support` block. The human reads the per-question table
and can point at any miss.

---

### Task 4: Ablation — `bench/ablation.py`

**Who:** mentor writes; human runs and interprets.

Runs Task 3 against the 400/60 and 1200/180 workspaces and prints one table:

| chunk target | chunks | Recall@1 | Recall@5 (any) | Recall@5 (all) | MRR@10 | Support@1 (any) | Support@5 (any) | Support@5 (all) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Both blocks are required. A chunk size can win on document recall and lose on
support — smaller chunks produce proportionally more stub-sized leading chunks —
so the decision is made on the support columns, with document recall as the
ceiling.

**Verification:** the table is written to `runs/<run>/ablation.json`; the
recommendation in `SUMMARY.md` names the winning row and the margin. If the
margins are within noise at n=25, say so — do not crown a winner.

---

### Task 5: Chat evaluation — `bench/chat_eval.py`

**Who:** mentor writes; human runs.

Against `fastapi dev app/main.py` on `:8000`:

1. Mint a JWT for the bench user in-process with `auth.security.create_access_token`.
2. Create one conversation per question, POST the message, parse SSE by
   splitting on blank lines (same approach as `tests/modules/chat/test_router.py`).
3. Record: question id, answer text, `sources` snapshot (filename, chunk index,
   score), cited numbers, TTFT, full time, error events.
4. Assert every retrieval question's `sources` came from the bench workspace.
5. Write `runs/<run>/chat.jsonl`.

**Verification:** 33 rows; no `error` events; the 8 unanswerable questions are
visibly classified (refused or answered — do not pre-judge). TTFT is non-zero
and smaller than full time for every row.

---

### Task 6: Judge and human labels

**Who:** human writes `bench/human_labels.jsonl`; mentor writes `bench/judge.py`.

1. Pick 15 answers spanning the three types (10 answerable, 5 unanswerable), read
   them, and label `correctness` and `grounded` yourself against
   `rag_benchmark/judge_prompt.md`.
2. `bench/judge.py` renders the prompt (reference + sources + answer), calls the
   same OpenAI-compatible endpoint at temperature 0, parses strictly, and writes
   `judged.jsonl`. A parse failure is recorded as `"parse_error"`, never silently
   coerced.
3. Compute agreement with the human labels per dimension and print it.

**Verification:** `uv run python -m bench.judge` prints the groundedness
distribution and agreement (e.g. `correctness 13/15`). Rerun once; the
distribution should be stable. If agreement is below ~80%, the judged numbers
are withheld from the writeup until the rubric is fixed.

---

### Task 7: Abstention finding and the relevance floor

**Who:** human decides; mentor writes the proposal.

1. Tabulate the 8 unanswerable questions: refused, or answered, and with what
   cited score.
2. If answered: write a short proposal — add a minimum score constant to
   `chat/constants.py`, filter retrieved hits in `chat/service.py`, add a test
   that an off-topic question with low scores refuses, and re-run Task 5.
3. Report before/after abstention and citation rates from two runs.

**Verification:** both runs exist under `runs/`; the delta in the writeup points
at the two files.

---

### Task 8: Summary and the claim

**Who:** mentor writes the table; human edits the wording until they can defend
every line.

`runs/<run>/SUMMARY.md` contains the corpus description (17 documents, 28
questions, planted-fact labels, prior-year near-miss), the metric table, the
ablation table, the judge agreement, the latency table with its caveat, and the
exact reproduce command. Then 3–5 resume bullets derived from it, each naming a
number from the table and nothing that is not in the table.

**Verification:** a fresh reader can clone, run three commands, and get the same
tables; every number in the bullets appears in `SUMMARY.md`.

## Done means

- `bench/validate.py`, `seed.py`, `retrieve.py`, `ablation.py`, `chat_eval.py`,
  `judge.py`, `cleanup.py` exist, ruff-clean, and run from `apps/api/`.
- `runs/<date>-<sha>/` holds seed, retrieval, ablation, chat, judged, SUMMARY.
- Retrieval metrics reproduce exactly across two runs.
- Judge agreement is reported next to every judged number.
- No product code changed in v1, or the change came through Task 7's proposal.
