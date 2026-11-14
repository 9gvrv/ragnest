# Ragnest — RAG benchmark suite — Design

> **Status:** proposed. No harness code exists yet; the corpus and labels do
> (see `apps/api/bench/`).
>
> **Purpose:** produce numbers about retrieval and answer quality that are real,
> reproducible, and defensible in an interview. A number we cannot re-derive
> does not get published.

---

## 1. Why this exists

Ragnest has no live users. The usual resume metrics (MAU, QPS, uptime) are
unavailable and, on a free tier, dishonest. What *is* measurable is whether the
system retrieves the right document and answers only from it. That requires a
fixed corpus, fixed questions, fixed labels, and a script that anyone can run
again.

There is a second reason: we expect the measurement to find a defect. The chat
path retrieves `CHAT_TOP_K` chunks unconditionally and only refuses when zero
chunks come back, so an off-topic question will retrieve something irrelevant
and be answered confidently. Measuring that, then fixing it, is the point.

## 2. Intent

- A committed benchmark that a stranger can run with their own keys and get the
  same numbers, up to provider nondeterminism.
- Numbers that answer "is retrieval good?" and "is the answer grounded?" —
  separately, because they fail separately.
- One experiment that produces a *decision* (chunk size), not just a score.
- Zero changes to product code in v1.

## 3. Goals

1. Document-level retrieval quality on a constructed corpus: Recall@1, Recall@5,
   MRR@10.
2. A chunk-size ablation at 400 / 800 / 1200 characters, each in its own
   workspace, with the same questions.
3. Chat-side measurement: time-to-first-token, citation hit rate, abstention
   rate, and judge-scored groundedness.
4. Judge validity: agreement between the judge and 15 hand labels.
5. A results snapshot committed per run, with model names, versions, date, and
   machine.

## 4. Non-goals

- Throughput, concurrency, requests/sec, uptime. Nothing here is a load test.
- Cost per query. The LLM client does not request provider usage
  (`stream_options.include_usage`), so any cost figure would be an estimate
  dressed as a measurement. Adding usage is a separate product proposal.
- Production latency claims. All latency is laptop → provider.
- Comparing Gemini/Groq against other providers. One provider, one model.
- A web UI for results. JSON + Markdown is enough.

## 5. Anti-goals (the suite has failed if…)

- Any headline number cannot be reproduced by `uv run python -m bench.<x>` on a
  clean checkout with valid keys.
- A reported improvement has no before/after run, each with the same corpus and
  questions.
- The judge's score is reported without its agreement against human labels.
- The writeup implies live users, traffic, or production scale.

## 6. Constraints

- `apps/api/bench/` is a script package, not an app module and not a test. It is
  outside `testpaths = ["tests"]`, never runs in CI, and adds no dependency
  (uses `httpx`, `sqlalchemy`, and app modules already present).
- Bench code must stay ruff-clean (`uv run ruff check .` covers it).
- Real embeddings require the real `GEMINI_API` key and the real database
  (pgvector exists only in Postgres). Tests are unaffected: they never import
  `bench/`.
- Free-tier limits: pace embedding calls (batch size 16 already), and keep the
  suite under ~200 embedding calls and ~60 generations per run.
- No secret is printed, logged, or written to a results file.

## 7. Decisions

**D1 — Two execution modes, chosen per experiment.**
Retrieval and the ablation run **in-process**: build `Document` rows, call
`index_document`, call `service.search`. That is the only way to swap
`CHUNK_TARGET_CHARS` per run without a server restart, and it avoids HTTP noise
in the retrieval numbers. The chat experiment runs **over HTTP** against
`fastapi dev`, because the SSE contract and TTFT are what we want to measure
there. The difference is stated in every results file: `"mode": "in_process"` or
`"mode": "http"`.

**D2 — Ground truth is document-level.**
`questions.jsonl` already names `source_documents`. We rank chunks but score
documents: a hit counts when its `document_id` belongs to a gold document. This
avoids hand-labeling chunk offsets, which would add hours of work and a second
source of human error.

**D3 — Headline recall is "any gold document", with "all gold documents"
reported next to it.** Multi-fact questions name two documents; requiring both
is a stricter, more informative number, but it is not comparable to single-fact
questions. Both are printed so neither can be quoted alone.

**D4 — Documents are embedded, not uploaded, for retrieval runs.** Upload is
the product path and is already covered by `tests/modules/documents`. What the
benchmark needs is the chunk set, so it creates rows directly. `char_count` and
`extracted_text` are set the way `documents/service.py` sets them.

**D5 — The ablation scales overlap with the target.** Overlap stays at 15% of
the target (800 → 120, 400 → 60, 1200 → 180), and `MIN_CHUNK_CHARS` stays 120.
Scaling one parameter while the other is fixed would confound the result.

**D6 — The judge scores two things independently and they are never averaged.**
`correctness` is judged against the reference answer. `grounded` is judged
against the sources the system actually received. An answer can be correct and
ungrounded (right fact, wrong support), which is exactly the failure worth
seeing. The original prompt judged "hallucination" against the reference answer,
which flags *correct extra detail* as invention — fixed in
`rag_benchmark/judge_prompt.md`.

**D7 — The judge is validated, not trusted.** 15 system answers are hand-labeled
first, then compared. Judge–human agreement is reported beside every judged
number. If agreement is poor, the judged number is not published.

**D8 — No product change in v1.** If the abstention slice fails, the fix (a
relevance floor) is proposed separately with the measurements attached, then
re-measured. That proposal touches `chat/constants.py`, `chat/service.py`, and
tests.

**D9 — Bench data lives in disposable workspaces.** One workspace per
configuration, named `bench-<date>-<size>`, created in the existing dev
database and deleted by `bench/cleanup.py`. Nothing else in the database is
touched; every query is workspace-scoped.

## 8. The corpus as built

`apps/api/bench/` (human-authored, already committed):

- `facts.jsonl` — 20 planted facts (8 atomic, 7 descriptive, 5 relational), each
  naming exactly one owning document.
- `questions.jsonl` — 33 questions: 20 single-fact, 5 multi-fact, 8
  unanswerable. The abstain set is deliberately weighted toward questions whose
  topic *is* in the corpus but whose figure is not (free cash flow in dollars,
  FY2025 actual capex, total dividend, segment headcount, backlog value): those
  retrieve confidently and are the ones a relevance floor would have to catch. Each carries `reference_answer`, `source_documents`,
  `expected_behavior`, and `fact_ids`.
- `rag_benchmark/corpus/` — 17 Markdown documents: 12 fact documents and 5
  distractors, of which one (`fy2024_results_highlights.md`) is a deliberate
  near-miss whose figures differ from FY2025 by a single digit
  ($4,118.3M vs $4,187.3M, 11,208 vs 11,462 employees, $0.34 vs $0.37
  dividend, $600M vs $750M facility).
- `rag_benchmark/manifest.json` — file roles and fact ownership.
- `rag_benchmark/judge_prompt.md` — the judging rubric.

Validation already performed (to be re-run by `bench/validate.py`):

- Every fact's key value appears in its owning document and in no distractor.
- No question shares a run of six or more words with its source document
  (longest observed: 5, and it is a domain term).
- The eight unanswerable questions have no answering evidence anywhere in the corpus,
  including the near-miss document.
- Chunk counts at 800/120: 125 chunks over 17 documents (4–10 per document).
  At 400/60: 262. At 1200/180: 74.

**Known bias, recorded not hidden:** `doc_12_investor_day_faq.md` is written as
question-and-answer pairs, and two questions (q03, q06) target it. That document
is retrieval-easy by construction. It stays in the corpus; the writeup says so.

## 9. Metrics

All retrieval metrics are computed over the **25 answerable** questions.

| Metric | Definition |
| --- | --- |
| Recall@1 (any) | fraction where the top-1 chunk's document is a gold document |
| Recall@5 (any) | fraction where ≥1 of the top-5 chunks is from a gold document |
| Recall@5 (all) | fraction where every gold document appears in the top 5 |
| MRR@10 | mean of 1/rank of the first gold-document chunk, 0 if none in the top 10 |
| Support@k (any) | fraction where ≥1 of the top-k chunks contains the anchor value of one of the question's planted facts |
| Support@k (all) | fraction where *every* one of the question's facts has its anchor value inside the top-k chunks |
| Search p50/p95 | wall time of `embed_query` + `service.search` |

Document-level recall and chunk-level support answer different questions. Recall
asks "did the right document come back"; support asks "is the answer actually in
the text the model receives". Both are reported, document-level as a ceiling.

The anchor rule (`bench/support.py`) is the same one `bench/validate.py` uses to
prove a fact is not leaked into a distractor: the rarest value in the fact
statement that appears in its owning document, preferring numbers. One definition
of "this fact's value" serves validation and scoring, so a fact cannot pass
validation under one notion and be scored under another. The rule is a lower
bound: a fact whose value spans two chunks (arithmetic, for instance) needs both
chunks, and each fact contributes exactly one anchor.

`k` is counted in **chunks**, not documents, because k chunks is what the model
receives. Chat uses `DEFAULT_TOP_K = 5`, so `support@5` is the number that
describes production chat.

Chat metrics (25 answerable + 8 abstain):

| Metric | Definition |
| --- | --- |
| Citation hit | fraction where ≥1 cited source document is a gold document |
| Abstention rate | fraction of the 8 unanswerable questions where the system declines |
| Grounded | judge's `grounded` label, distribution over all answers |
| Judge agreement | agreement with 15 hand labels, per dimension |
| TTFT p50/p95 | time from request to first `token` event |
| Full-answer p50/p95 | time from request to `done` |

Latency is reported with the provider's model name, the date, and the label
"laptop → provider, single run, n=25". No confidence intervals on n=25 — we say
n=25.

## 10. Experiments

**E1 — Baseline.** Corpus at the current constants (800/120), 25 answerable
questions, retrieval metrics + chat metrics.

**E2 — Chunk ablation.** Same corpus and questions at 400/60 and 1200/180, each
in its own workspace. Only retrieval metrics; running chat three times triples
generation cost for no new information. Decision: which chunk size to keep.

**E3 — Abstention and the relevance floor.** Measure the 8 unanswerable
questions at baseline. If any is answered confidently, propose a score floor,
re-run E1's chat slice, and report the delta. This is the only experiment
allowed to touch product code, and only after its own proposal.

## 10a. E1 result (2026-11-14) and the assumption it broke

Measured on `bench-2026-11-14-800` (125 chunks, 800/120), 25 answerable
questions, `top_k=10`. Four full runs (`runs/2026-11-14-e1-a` … `-d`) produced
identical document metrics and identical rankings for 25/25 questions; the two
runs that record chunk support (`-c`, `-d`) also agree on every hit's `supports`
list.

Document-level metrics — a ceiling, because a hit only means a gold document
appeared:

| | R@1 any | R@5 any | R@5 all | MRR@10 |
| --- | --- | --- | --- | --- |
| overall (n=25) | 0.920 | 0.960 | 0.920 | 0.946 |
| single_fact (n=20) | 0.900 | 0.950 | 0.950 | 0.932 |
| multi_fact (n=5) | 1.000 | 1.000 | 0.800 | 1.000 |

Latency: embed p50 ≈ 0.5 s, search+DB total p50 2.07 s / p95 3.92 s.

**The break.** D2 assumed "a neighbour chunk usually carries the answer". It
does not. 44.8% of all 250 retrieved chunks are `chunk_index 0`, against a 13.6%
share of the index by construction — a 3.3× over-representation, because every
document opens with the same `# Tarnwick Industrial Group` banner. Those leading
chunks are often 276–680 characters of heading and dateline, so they match any
query about the company without containing the answer. 10 of 25 first gold hits
are `chunk_index 0`.

Re-scoring the same 25 runs against a stricter test — does a top-k chunk contain
a value from the question's planted fact — collapses the number:

| | Support@1 any | Support@1 all | Support@5 any | Support@5 all | Support@10 any | Support@10 all |
| --- | --- | --- | --- | --- | --- | --- |
| overall (n=25) | 0.400 | 0.320 | 0.680 | 0.640 | 0.800 | 0.680 |
| single_fact (n=20) | 0.400 | 0.400 | 0.700 | 0.700 | 0.750 | 0.750 |
| multi_fact (n=5) | 0.400 | 0.000 | 0.600 | 0.400 | 1.000 | 0.400 |

So 0.96 document-level recall@5 becomes **0.68 supporting-chunk recall@5** — the
k chat actually uses. At top_k=10 it is 0.80, which is why chat's k matters and
why the number is always quoted with its k. Seven document-level hits have no
support in the top 5: four are the stub chunk (q01, q02, q08, q09), one is a
paragraph the chunker split so the value sits in chunk 6 while chunk 5 was
retrieved (q15, first support at rank 8), and two are multi-document questions
(m04 at rank 8, m05 at rank 6). Raising k does not repair the two-document case:
`support@10_all` on multi_fact is still 0.40, because the second document's chunk
is outside the top 10 entirely.

Consequence: document-level recall stays as a *ceiling* number, but it is not
the headline. The supporting-chunk metric is now first class (`bench/support.py`,
`metrics.summarize_support`), and the stub chunk is a product finding (a
`_merge_short_head` counterpart to `_merge_short_tail` is the obvious candidate
fix). Both are proposals, not decisions taken here.

**Also noted:** the score band is narrow (0.69–0.80 across all hits, with the
q07 miss 0.0135 behind the top hit). A fixed cosine relevance floor for E3 will
therefore be brittle; pick it from measured distributions, not by feel.

## 11. Reproducibility package

```
apps/api/bench/
├── validate.py            # the four corpus checks above
├── support.py             # shared anchor rule: fact -> (owner, value)
├── seed.py                # create workspaces + document rows + index
├── retrieve.py            # E1 retrieval metrics
├── ablation.py            # E2
├── chat_eval.py           # E3 chat slice over HTTP
├── judge.py               # rubric runner
├── cleanup.py             # delete bench workspaces
├── human_labels.jsonl     # 15 hand labels (human-authored)
└── runs/YYYY-MM-DD-<git-sha>/
    ├── seed.json          # workspace ids, doc ids, chunk counts
    ├── retrieval.json     # metrics + per-question hits
    ├── chat.jsonl         # question, answer, citations, latency
    ├── judged.jsonl       # judge output per answer
    └── SUMMARY.md         # the table that goes in the writeup
```

Each results file records: git SHA, date, embedding model, LLM model, chunk
target/overlap, top_k, and `mode`. `runs/` is committed (it is small JSON).

## 12. What we will and will not claim

Will: "Built a 17-document constructed corpus with planted-fact labels and a
prior-year near-miss distractor; measured Recall@5 and MRR@10, ablated chunk
size, and validated an LLM judge against hand labels."

Will not: any accuracy percentage without its eval set, any throughput or scale
claim, any cost figure, any improvement without a before/after run.

## 13. Left to builder

- Exact CLI shape (`python -m bench.retrieve --run <dir>`) — builder's call.
- Whether `seed.py` reuses an existing workspace when the corpus hash matches —
  builder's call; hashing the corpus is a cheap way to skip re-embedding.
- Whether the judge uses the same model as generation. It currently would;
  that is a known self-preference risk, recorded in the judge output.
