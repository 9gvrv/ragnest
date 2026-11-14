# RAG benchmark — Tarnwick corpus

A rerunnable evaluation of Ragnest's retrieval and chat pipeline. Every number
below came from the scripts in this directory, and every run is kept under
`runs/` as evidence.

This is not a test suite. It runs against the real database and the real
providers, sits outside `testpaths`, and never runs in CI.

## 1. Corpus and labels

A fictional company ("Tarnwick Industrial Group") so the answers cannot be
looked up. Written by hand, then audited by `validate.py`.

| | Count |
| --- | --- |
| Documents | 17 — 12 fact-bearing, 5 distractors |
| Planted facts | 20 (8 atomic, 7 descriptive, 5 relational) |
| Questions | 33 — 20 single-fact, 5 multi-fact, 8 unanswerable |
| Size | ~61k characters, 74–262 chunks depending on chunk size |

One distractor is a deliberate near-miss: an FY2024 results page where every
figure is one digit off the FY2025 value ($4,118.3M vs $4,187.3M, 11,208 vs
11,462 employees, $0.34 vs $0.37 dividend, $600M vs $750M facility).

`validate.py` enforces four things, all currently passing:

1. every fact's distinctive value appears in its owning document and in no
   distractor;
2. every question's `source_documents` matches its facts' owners;
3. no question echoes its source (longest verbatim run is 5 words, a domain
   term);
4. none of the 8 unanswerable questions has supporting evidence anywhere,
   including the near-miss document.

## 2. What is measured

`k` is counted in **chunks**, not documents, because k chunks is what the model
receives. Chat uses `top_k = 5`.

| Metric | Question it answers |
| --- | --- |
| Recall@k (any) | did a chunk from a gold document come back? |
| Recall@k (all) | did every gold document come back? |
| MRR@10 | how early did the first gold-document chunk appear? |
| Support@k (any) | does a retrieved chunk actually contain the answer? |
| Support@k (all) | is every part of the answer present? |

Document-level recall is a **ceiling**: a document can be retrieved without its
answer being in the chunk that was returned. Support is the honest test, and
both are always reported.

Anchors come from `support.py`, the same rule `validate.py` uses to prove a fact
is not leaked: the rarest value in the fact statement that appears in its owning
document, preferring numbers. Validation and scoring therefore cannot drift
apart.

## 3. Baseline results (800/120, 125 chunks)

25 answerable questions, `top_k = 10`, four full runs with identical rankings.

| | R@1 any | R@5 any | R@5 all | MRR@10 |
| --- | --- | --- | --- | --- |
| overall (n=25) | 0.920 | 0.960 | 0.920 | 0.946 |
| single_fact (n=20) | 0.900 | 0.950 | 0.950 | 0.932 |
| multi_fact (n=5) | 1.000 | 1.000 | 0.800 | 1.000 |

| | Support@1 any | Support@5 any | Support@5 all | Support@10 any |
| --- | --- | --- | --- | --- |
| overall (n=25) | 0.400 | **0.680** | 0.640 | 0.800 |
| single_fact (n=20) | 0.400 | 0.700 | 0.700 | 0.750 |
| multi_fact (n=5) | 0.400 | 0.600 | 0.400 | 1.000 |

Document recall says 0.96; support at the k chat actually uses says 0.68. The
gap is the finding, not noise: 44.8% of the 250 retrieved chunks were
`chunk_index 0`, against a 13.6% share of the index — every document opens with
the same `# Tarnwick Industrial Group` banner, so a stub chunk matches any
question about the company. 10 of 25 first gold hits were such stubs, and the
only document-level miss (q07, FY2026 capex plan, rank 7) had six of those
stubs ahead of it, the gold chunk 0.0135 behind.

Multi-fact questions cannot be rescued by a larger k: `support@10_all` is still
0.40, because the second document's chunk never enters the top 10.

Latency, laptop → Gemini → Neon, single run, n=25: query embedding p50 ≈ 0.53 s;
embed + search + DB p50 1.95–2.17 s across runs. The slowest query is 8.0–9.7 s
in every run — it is always the first query, a cold connection, not a claim
about steady state. No confidence intervals at n=25: the sample is the sample.

## 4. Reproducing

From `apps/api/`, with `.env` present (real Gemini key, real `DATABASE_URL`):

```bash
uv run python -m bench.validate                 # 4/4 corpus checks
uv run python -m bench.seed --size 800          # creates bench-<date>-800
uv run python -m bench.retrieve --label my-run  # writes runs/my-run/retrieval.json
```

- Workspaces are disposable and named `bench-<YYYY-MM-DD>-<size>`; seeding is
  idempotent and reuses an existing workspace without re-embedding.
- First index of 125 chunks takes ~200 s on the free tier (8 embedding batches);
  a reuse rerun takes ~19 s.
- Retrieval runs degrade gracefully: embed retries with exponential backoff,
  because free-tier 429s are expected.
- Determinism is a gate, not a hope: two runs of the same seeded workspace must
  produce identical metrics *and* identical rankings. They do, four for four.
- A run asserts every hit belongs to the seeded workspace, so another tenant's
  chunks can never leak into a score.

## 5. What this does not claim

- No throughput, scale, or cost number: this is 17 documents on one machine.
- No answer-quality result yet — chat evaluation and judge scoring are the next
  experiments, and the judge is validated against 15 hand labels.
- No improvement claim: nothing has been changed in the product yet. The
  stub-chunk finding suggests a `_merge_short_head` counterpart to the existing
  `_merge_short_tail`, and that is a separate proposal with before/after
  numbers.
- n=25 answerable questions, 17 documents. Small on purpose: hand-labelled and
  auditable beats large and unverifiable.

## 6. Files

| File | Purpose |
| --- | --- |
| `common.py` | paths, corpus loading, run directories, git SHA |
| `validate.py` | the four corpus/label checks |
| `support.py` | anchor rule shared by validation and scoring |
| `metrics.py` | pure metric functions over plain data |
| `seed.py` | create a bench workspace and index the corpus |
| `retrieve.py` | E1: retrieval metrics, document and chunk level |
| `facts.jsonl` | 20 planted facts with owning documents |
| `questions.jsonl` | 33 questions with gold documents and fact ids |
| `rag_benchmark/` | corpus, manifest, judge prompt |
| `runs/` | committed evidence: seed and retrieval results per run |

Status: E1 (retrieval baseline) complete. E2 (chunk-size ablation), E3 (chat,
citations, abstention, judge), `cleanup.py`, and `SUMMARY.md` are pending.
