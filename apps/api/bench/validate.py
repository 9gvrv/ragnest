"""Corpus and label checks. Fails loudly when the benchmark stops being honest.

Run from ``apps/api``:  uv run python -m bench.validate
"""

import re
import sys

from bench import common
from bench.support import ranked_values


def check_facts(docs: dict[str, str], distractor_names: set[str]) -> list[str]:
    errors = []
    for fact in common.facts():
        owner = fact["document"]
        if owner not in docs:
            errors.append(f"{fact['id']}: owner {owner} does not exist")
            continue
        ranked = ranked_values(fact["statement"], docs, owner)
        if not ranked:
            errors.append(f"{fact['id']}: none of its values appear in its owning document {owner}")
            continue
        token = ranked[0][0]
        in_distractors = [n for n in distractor_names if token in docs[n]]
        if in_distractors:
            errors.append(
                f"{fact['id']}: value {token!r} also appears in distractor(s) "
                f"{in_distractors} - those documents can answer it"
            )
    return errors


def check_question_sources(docs: dict[str, str]) -> list[str]:
    """question.source_documents must match fact.document for every fact_id."""
    owner = {fact["id"]: fact["document"] for fact in common.facts()}
    errors = []
    for question in common.questions():
        expected = {owner[fid] for fid in question["fact_ids"] if fid in owner}
        missing_fact = [fid for fid in question["fact_ids"] if fid not in owner]
        if missing_fact:
            errors.append(f"{question['id']}: unknown fact_ids {missing_fact}")
        if expected != set(question["source_documents"]):
            errors.append(
                f"{question['id']}: source_documents {sorted(question['source_documents'])} "
                f"!= fact owners {sorted(expected)}"
            )
        for name in question["source_documents"]:
            if name not in docs:
                errors.append(f"{question['id']}: source {name} does not exist")
    return errors


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9$%.,]+", text.lower())


def longest_run(left: list[str], right: list[str]) -> tuple[int, str]:
    best, best_span = 0, ""
    for i in range(len(left)):
        for j in range(len(right)):
            k = 0
            while i + k < len(left) and j + k < len(right) and left[i + k] == right[j + k]:
                k += 1
            if k > best:
                best, best_span = k, " ".join(left[i : i + k])
    return best, best_span


def check_questions(docs: dict[str, str], threshold: int = 6) -> list[str]:
    errors = []
    for question in common.questions():
        sources = question["source_documents"] or list(docs)
        for name in sources:
            if name not in docs:
                errors.append(f"{question['id']}: source {name} does not exist")
                continue
            run, span = longest_run(words(question["question"]), words(docs[name]))
            if run >= threshold:
                errors.append(f"{question['id']}: {run}-word run with {name}: {span!r}")
    return errors


def check_unanswerable(docs: dict[str, str]) -> list[str]:
    """Each abstain question needs a regex that must match nowhere in the corpus.

    The probe targets the *shape of an answer* (a figure attached to the topic),
    not the topic itself: every one of these questions has relevant documents,
    which is exactly why they are good abstention tests.
    """
    probes = {
        "u01": r"operating cash flow|cash flow from operations|cash provided by operating",
        "u02": r"trial date|trial (?:is|was) (?:scheduled|expected|set)|hearing date",
        "u03": r"predecessor|former chief executive|previous chief executive",
        "u04": r"free cash flow (?:of|was|reached|total(?:l)?ed|amounted to) \$",
        "u05": r"capital expenditure (?:of|was|reached|total(?:l)?ed|amounted to) \$",
        "u06": r"total dividend (?:of|was|reached) \$|interim dividend of \$",
        "u07": r"Industrial Services[^.]{0,200}?\b\d[\d,]* (?:employees|people|staff)",
        "u08": r"backlog[^.]{0,120}?\$[\d,]",
    }
    known = {q["id"] for q in common.questions()}
    errors = [f"{qid}: no probe registered" for qid in known - probes.keys() if qid.startswith("u")]
    for qid, probe in probes.items():
        for name, body in docs.items():
            match = re.search(probe, body, re.IGNORECASE)
            if match:
                errors.append(f"{qid}: evidence found in {name}: {match.group(0)!r}")
    return errors


def main() -> int:
    docs = {path.name: path.read_text() for path in common.corpus_files()}
    roles = {entry["file"]: entry["role"] for entry in common.manifest()}
    distractors = {name for name, role in roles.items() if role != "fact_doc"}
    sections = [
        ("fact values live in their owning document only", check_facts(docs, distractors)),
        ("question sources match fact ownership", check_question_sources(docs)),
        ("no question echoes its source", check_questions(docs)),
        ("abstain questions have no evidence", check_unanswerable(docs)),
    ]
    failed = False
    for title, errors in sections:
        if errors:
            failed = True
            print(f"FAIL  {title}")
            for error in errors:
                print(f"      {error}")
        else:
            print(f"PASS  {title}")
    print()
    print(
        f"corpus: {len(docs)} documents  facts: {len(common.facts())}  "
        f"questions: {len(common.questions())}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
