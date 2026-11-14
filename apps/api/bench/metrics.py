"""Scoring functions for the retrieval benchmark.

Plain data in, plain numbers out, so each definition can be checked by hand:

- ``ranked_doc_ids`` holds one document id per retrieved chunk, in score order.
  A document that contributes three chunks therefore appears three times.
- ``gold_doc_ids`` is the set of documents that actually contain the answer.
- ``k`` is counted in **chunks**, not documents, because k chunks is exactly
  what the model receives: the ``top_k`` rows of its context window.

So "a hit at k" means: among the first k retrieved chunks, at least one comes
from a gold document. That is generous to the retriever (a chunk is only part
of a document) and strict to the generator (it never sees more than k chunks).
Both facts belong in the writeup.

Two variants are reported because they answer different questions:

- ``recall_at`` — "did we surface the right document?" This is the number that
  matters for a chatbot, because a neighbour chunk usually carries the answer.
- ``recall_all_at`` — "did we surface *every* document the question needs?"
  This is the honest number for multi-document questions, and it is lower.
"""

import math
from collections.abc import Collection, Sequence


def _validate(k: int, gold_doc_ids: Collection[str]) -> frozenset[str]:
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    gold = frozenset(gold_doc_ids)
    if not gold:
        raise ValueError("gold_doc_ids is empty; abstain questions are not scored for recall")
    return gold


def _first_gold_rank(ranked_doc_ids: Sequence[str], gold: frozenset[str], k: int) -> int | None:
    """1-based rank of the first gold document within the top k, else None."""
    for rank, document_id in enumerate(ranked_doc_ids[:k], start=1):
        if document_id in gold:
            return rank
    return None


def recall_at(k: int, ranked_doc_ids: Sequence[str], gold_doc_ids: Collection[str]) -> float:
    """1.0 when at least one of the top k chunks comes from a gold document."""
    gold = _validate(k, gold_doc_ids)
    return 1.0 if _first_gold_rank(ranked_doc_ids, gold, k) is not None else 0.0


def recall_all_at(k: int, ranked_doc_ids: Sequence[str], gold_doc_ids: Collection[str]) -> float:
    """1.0 when every gold document appears in the top k chunks."""
    gold = _validate(k, gold_doc_ids)
    return 1.0 if gold <= set(ranked_doc_ids[:k]) else 0.0


def reciprocal_rank(k: int, ranked_doc_ids: Sequence[str], gold_doc_ids: Collection[str]) -> float:
    """1/rank of the first gold chunk within the top k, or 0.0 when there is none."""
    gold = _validate(k, gold_doc_ids)
    rank = _first_gold_rank(ranked_doc_ids, gold, k)
    return 0.0 if rank is None else 1.0 / rank


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean. Raises on an empty sequence rather than inventing 0.0."""
    if not values:
        raise ValueError("mean of an empty sequence")
    return sum(values) / len(values)


def summarize(
    rows: Sequence[dict],
    ks: Sequence[int] = (1, 5),
    rr_k: int = 10,
) -> dict:
    """Aggregate per-question rows overall and per question type.

    Each row needs ``ranked_doc_ids`` and ``gold_doc_ids``; ``type`` is
    optional and, when present, produces a per-type breakdown. Questions with
    an empty ``gold_doc_ids`` are skipped by design — abstain questions are
    scored by abstention rate, not by recall.
    """
    answerable = [row for row in rows if row.get("gold_doc_ids")]
    if not answerable:
        raise ValueError("no answerable rows to summarise")

    def block(subset: Sequence[dict]) -> dict:
        out: dict[str, float] = {}
        for k in ks:
            out[f"recall@{k}_any"] = mean(
                [recall_at(k, r["ranked_doc_ids"], r["gold_doc_ids"]) for r in subset]
            )
            out[f"recall@{k}_all"] = mean(
                [recall_all_at(k, r["ranked_doc_ids"], r["gold_doc_ids"]) for r in subset]
            )
        out[f"mrr@{rr_k}"] = mean(
            [reciprocal_rank(rr_k, r["ranked_doc_ids"], r["gold_doc_ids"]) for r in subset]
        )
        out["n"] = float(len(subset))
        return out

    by_type: dict[str, dict] = {}
    for question_type in sorted({row.get("type", "unknown") for row in answerable}):
        subset = [row for row in answerable if row.get("type", "unknown") == question_type]
        by_type[question_type] = block(subset)

    return {"overall": block(answerable), "by_type": by_type}


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile, with no interpolation.

    At n=25 a percentile is a description of the sample, not an estimate of a
    distribution, so we return an observed value instead of inventing one
    between two samples. p95 of 25 samples is therefore the slowest run: that
    is the honest reading, and the writeup says "n=25".
    """
    if not values:
        raise ValueError("percentile of an empty sequence")
    if not 0 < p <= 100:
        raise ValueError(f"p must be in (0, 100], got {p}")
    ordered = sorted(values)
    rank = math.ceil(p / 100 * len(ordered))
    return float(ordered[rank - 1])


def support_any_at(k: int, hits: Sequence[dict]) -> float:
    """1.0 when one of the top k chunks contains a value from the question's facts."""
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    return 1.0 if any(hit.get("supports") for hit in hits[:k]) else 0.0


def support_all_at(k: int, hits: Sequence[dict], fact_ids: Sequence[str]) -> float:
    """1.0 when *every* fact has its anchor value inside the top k chunks.

    This is the honest test for a multi-fact question: retrieving one half of a
    two-part answer leaves the model unable to answer, even though the ranked
    document list looks fine.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if not fact_ids:
        raise ValueError("support_all_at needs at least one fact id")
    found = {fact_id for hit in hits[:k] for fact_id in hit.get("supports", [])}
    return 1.0 if set(fact_ids) <= found else 0.0


def summarize_support(rows: Sequence[dict], ks: Sequence[int] = (1, 5)) -> dict:
    """Chunk-level support metrics, overall and per question type.

    A row needs ``hits`` (each with a ``supports`` list) and ``fact_ids``. Rows
    without facts - abstain questions - carry no support notion and are skipped.
    """
    answerable = [row for row in rows if row.get("fact_ids")]
    if not answerable:
        raise ValueError("no rows with fact_ids to summarise")

    def block(subset: Sequence[dict]) -> dict:
        out: dict[str, float] = {}
        for k in ks:
            out[f"support@{k}_any"] = mean([support_any_at(k, r["hits"]) for r in subset])
            out[f"support@{k}_all"] = mean(
                [support_all_at(k, r["hits"], r["fact_ids"]) for r in subset]
            )
        out["n"] = float(len(subset))
        return out

    by_type: dict[str, dict] = {}
    for question_type in sorted({row.get("type", "unknown") for row in answerable}):
        subset = [row for row in answerable if row.get("type", "unknown") == question_type]
        by_type[question_type] = block(subset)

    return {"overall": block(answerable), "by_type": by_type}
