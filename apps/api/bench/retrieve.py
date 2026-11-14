"""E1: retrieval quality for the seeded corpus.

Embeds each answerable question, runs the real ``service.search`` against the
bench workspace, and writes per-question ranks plus the aggregate metrics.

Run from ``apps/api``:

    uv run python -m bench.retrieve
    uv run python -m bench.retrieve --label 2026-11-14-e1-b   # determinism check
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal, dispose_engine
from app.modules.retrieval import service
from app.modules.retrieval.embeddings import EmbeddingProviderError, GeminiEmbeddingProvider
from bench import common, support
from bench import metrics as m

RETRIEVAL_TOP_K = 10  # deeper than chat's top_k so MRR@10 is meaningful
EMBED_ATTEMPTS = 4
BACKOFF_SECONDS = 5


def latest_seed() -> Path:
    seeds = sorted(common.RUNS.glob("*/seed.json"), key=lambda p: p.stat().st_mtime)
    if not seeds:
        raise SystemExit("no seed.json found - run `python -m bench.seed` first")
    return seeds[-1]


async def embed_with_retry(provider: GeminiEmbeddingProvider, text: str) -> list[float]:
    """Retry with backoff; free-tier 429s are expected, not exceptional."""
    for attempt in range(1, EMBED_ATTEMPTS + 1):
        try:
            return await provider.embed_query(text)
        except EmbeddingProviderError as exc:
            if attempt == EMBED_ATTEMPTS:
                raise
            delay = BACKOFF_SECONDS * 2 ** (attempt - 1)
            print(f"    embedding failed ({exc}); retry {attempt}/{EMBED_ATTEMPTS - 1} in {delay}s")
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def run_question(
    session: AsyncSession,
    provider: GeminiEmbeddingProvider,
    workspace_id: UUID,
    question: dict,
    top_k: int,
    gold_ids: set[str],
    anchors: dict[str, tuple[str, str]],
) -> dict:
    started = time.perf_counter()
    vector = await embed_with_retry(provider, question["question"])
    embedded = time.perf_counter()

    hits = await service.search(session, workspace_id, vector, top_k)
    finished = time.perf_counter()

    ranked_doc_ids = [str(hit.document_id) for hit in hits]

    return {
        "question_id": question["id"],
        "type": question["type"],
        "level": question["level"],
        "question": question["question"],
        "fact_ids": question["fact_ids"],
        "gold_doc_ids": sorted(gold_ids),
        "gold_documents": question["source_documents"],
        "ranked_doc_ids": ranked_doc_ids,
        "first_gold_rank": next(
            (rank for rank, doc_id in enumerate(ranked_doc_ids, start=1) if doc_id in gold_ids),
            None,
        ),
        "hits": [
            {
                "rank": rank,
                "chunk_id": str(hit.chunk_id),
                "document_id": str(hit.document_id),
                "filename": hit.filename,
                "chunk_index": hit.chunk_index,
                "char_start": hit.char_start,
                "char_end": hit.char_end,
                "score": round(hit.score, 6),
                # Derived from the planted fact, never from the ranking: a chunk
                # supports a question only if it contains that fact's anchor
                # value in its owning document.
                "supports": support.supported_facts(
                    anchors,
                    question["fact_ids"],
                    hit.filename,
                    hit.content,
                ),
            }
            for rank, hit in enumerate(hits, start=1)
        ],
        "returned": len(hits),
        "top_score": round(hits[0].score, 6) if hits else None,
        "embed_ms": round((embedded - started) * 1000, 1),
        "search_ms": round((finished - embedded) * 1000, 1),
        "total_ms": round((finished - started) * 1000, 1),
    }


async def main(label: str | None, seed_path: Path, top_k: int) -> None:
    seed = json.loads(seed_path.read_text())
    workspace_id = UUID(seed["workspace_id"])
    seeded_ids = {row["document_id"] for row in seed["documents"]}
    filename_of = {row["document_id"]: row["filename"] for row in seed["documents"]}
    # Gold sets are filenames in questions.jsonl; map them to the ids this
    # workspace actually holds. The full set matters: recall_all needs every
    # gold document, not just the ones that happened to be retrieved.
    gold_by_question = {
        question["id"]: {
            doc_id for doc_id, name in filename_of.items() if name in question["source_documents"]
        }
        for question in common.questions()
    }

    answerable = [q for q in common.questions() if q["expected_behavior"] == "answer"]
    provider = GeminiEmbeddingProvider(settings.GEMINI_API)
    docs = {path.name: path.read_text() for path in common.corpus_files()}
    anchors = support.anchors_by_fact(docs, common.facts())
    # A fact with no anchor cannot ever be "supported", which would quietly
    # depress the chunk-level numbers. Fail instead of shipping that.
    unscorable = {
        fid for question in answerable for fid in question["fact_ids"] if fid not in anchors
    }
    if unscorable:
        raise SystemExit(f"no anchor value found for facts: {sorted(unscorable)}")

    rows: list[dict] = []
    started = time.perf_counter()
    async with SessionLocal() as session:
        for index, question in enumerate(answerable, start=1):
            row = await run_question(
                session,
                provider,
                workspace_id,
                question,
                top_k,
                gold_by_question[question["id"]],
                anchors,
            )
            leaked = set(row["ranked_doc_ids"]) - seeded_ids
            if leaked:
                raise SystemExit(f"{question['id']}: hits outside the bench workspace: {leaked}")
            rows.append(row)
            rank = row["first_gold_rank"]
            support_rank = next(
                (hit["rank"] for hit in row["hits"] if hit["supports"]),
                None,
            )
            marker = "MISS" if rank is None or rank > 5 else "hit "
            print(
                f"[{index:2d}/{len(answerable)}] {marker} {question['id']:4s} "
                f"rank={rank!s:>4s}  support={support_rank!s:>4s}  "
                f"top={row['top_score']}  {row['embed_ms']:7.0f}ms"
            )
            await asyncio.sleep(1.0)  # free-tier pacing

    elapsed = round(time.perf_counter() - started, 1)
    summary = m.summarize(rows, ks=(1, 5), rr_k=10)
    support_summary = m.summarize_support(rows, ks=(1, 5))
    latency = {
        "embed_ms": {
            "p50": m.percentile([r["embed_ms"] for r in rows], 50),
            "p95": m.percentile([r["embed_ms"] for r in rows], 95),
        },
        "search_ms": {
            "p50": m.percentile([r["search_ms"] for r in rows], 50),
            "p95": m.percentile([r["search_ms"] for r in rows], 95),
        },
        "total_ms": {
            "p50": m.percentile([r["total_ms"] for r in rows], 50),
            "p95": m.percentile([r["total_ms"] for r in rows], 95),
        },
    }

    payload = {
        "mode": "in_process",
        "git_sha": common.git_sha(),
        "corpus_hash": seed["corpus_hash"],
        "workspace_id": str(workspace_id),
        "workspace_name": seed["workspace_name"],
        "embedding_model": seed["embedding_model"],
        "chunk_target": seed["chunk_target"],
        "chunk_overlap": seed["chunk_overlap"],
        "top_k": top_k,
        "seconds": elapsed,
        "metrics": summary,
        "support": support_summary,
        "latency_ms": latency,
        "questions": rows,
    }
    out = common.run_dir(label) / "retrieval.json"
    common.write_json(out, payload)

    print()
    print(f"workspace  {seed['workspace_name']}  chunks={seed['totals']['chunks']}")
    print(f"n          {len(rows)} answerable questions, top_k={top_k}")
    print("document   " + "  ".join(f"{k}={v:.3f}" for k, v in summary["overall"].items()))
    for question_type, block in summary["by_type"].items():
        print(f"  {question_type:12s} " + "  ".join(f"{k}={v:.3f}" for k, v in block.items()))
    print("chunk      " + "  ".join(f"{k}={v:.3f}" for k, v in support_summary["overall"].items()))
    for question_type, block in support_summary["by_type"].items():
        print(f"  {question_type:12s} " + "  ".join(f"{k}={v:.3f}" for k, v in block.items()))
    print(
        f"latency    p50={latency['total_ms']['p50']:.0f}ms  p95={latency['total_ms']['p95']:.0f}ms"
    )
    print(f"written    {out.relative_to(common.API_ROOT)}")
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default=None, help="run directory name")
    parser.add_argument("--seed", type=Path, default=None, help="path to a seed.json")
    parser.add_argument("--top-k", type=int, default=RETRIEVAL_TOP_K)
    args = parser.parse_args()
    if args.top_k < 10:
        raise SystemExit("--top-k must be >= 10 so MRR@10 is meaningful")
    asyncio.run(main(args.label, args.seed or latest_seed(), args.top_k))
