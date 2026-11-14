"""Shared paths, corpus loading, and run bookkeeping for the benchmark."""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BENCH = Path(__file__).resolve().parent
API_ROOT = BENCH.parent
CORPUS = BENCH / "rag_benchmark" / "corpus"
RUNS = BENCH / "runs"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def facts() -> list[dict[str, Any]]:
    return load_jsonl(BENCH / "facts.jsonl")


def manifest() -> list[dict[str, Any]]:
    return json.loads((BENCH / "rag_benchmark" / "manifest.json").read_text())


def questions() -> list[dict[str, Any]]:
    return load_jsonl(BENCH / "questions.jsonl")


def corpus_files() -> list[Path]:
    return sorted(CORPUS.glob("*.md"))


def corpus_hash() -> str:
    digest = hashlib.sha256()
    for path in corpus_files():
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=API_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_dir(label: str | None = None) -> Path:
    name = label or f"{datetime.now(UTC):%Y-%m-%d}-{git_sha()}"
    path = RUNS / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
