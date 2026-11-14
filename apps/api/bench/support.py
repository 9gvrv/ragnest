"""Which retrieved chunks actually carry the answer?

Document-level recall only asks whether some chunk of the right document came
back. That is too weak for this corpus: every document opens with the same
``Tarnwick Industrial Group`` banner, so a leading chunk scores as a hit while
containing none of the answer. E1 showed 44.8% of retrieved chunks were
``chunk_index 0``, against a 13.6% share of the index.

So we derive, from the planted facts, the value that identifies each fact in its
owning document, and later ask whether a retrieved chunk's text contains it.
This is a lower bound on "the answer is reachable": a question whose value is
spread over two chunks (arithmetic, for instance) needs both, and each fact
contributes only one anchor value.

The anchor rule is deliberately conservative: the rarest value in the fact
statement that appears in the owning document, preferring numbers, because a
number is far less likely to be incidental prose than a name. The same rule
backs ``bench.validate``, so a fact cannot pass validation and then be scored
against a different notion of "its value".
"""

import re

MONEY_OR_PCT = re.compile(r"\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion))?|\d+(?:\.\d+)?%")
NUMBER = re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b")
CAPITALISED = re.compile(r"\b[A-Z][\w'-]{3,}\b")

# Words that carry no discriminating meaning for "is this the fact's value".
GENERIC = {
    "tarnwick",
    "industrial",
    "group",
    "company",
    "fiscal",
    "million",
    "billion",
    "chief",
    "financial",
    "officer",
    "committee",
    "board",
}


def candidates(statement: str) -> list[str]:
    """Every token in a fact statement that could identify it in a document."""
    found = MONEY_OR_PCT.findall(statement) + NUMBER.findall(statement)
    found += [word for word in CAPITALISED.findall(statement) if word.lower() not in GENERIC]
    return found


def ranked_values(statement: str, docs: dict[str, str], owner: str) -> list[tuple[str, int]]:
    """Candidate values ordered by rarity across the corpus.

    Only candidates that appear in the owning document count: the question is
    which value identifies the fact, not how the statement was worded. Numeric
    values win ties.
    """
    scored = []
    for token in set(candidates(statement)):
        if token not in docs[owner]:
            continue
        seen_in = sum(token in body for body in docs.values())
        scored.append((seen_in, 0 if token[0].isdigit() or token[0] == "$" else 1, token))
    scored.sort()
    return [(token, seen_in) for seen_in, _, token in scored]


def anchors_by_fact(docs: dict[str, str], facts: list[dict]) -> dict[str, tuple[str, str]]:
    """Map each fact id to ``(owning filename, anchor value)``.

    Facts with no usable value are omitted, so callers must handle a missing
    entry by treating that question as not chunk-scorable rather than as a miss.
    """
    anchors: dict[str, tuple[str, str]] = {}
    for fact in facts:
        owner = fact["document"]
        ranked = ranked_values(fact["statement"], docs, owner)
        if ranked:
            anchors[fact["id"]] = (owner, ranked[0][0])
    return anchors


def supported_facts(
    anchors: dict[str, tuple[str, str]],
    fact_ids: list[str],
    filename: str,
    content: str,
) -> list[str]:
    """Facts whose anchor value appears in this chunk, from this document."""
    return [
        fact_id
        for fact_id in fact_ids
        if fact_id in anchors and anchors[fact_id][0] == filename and anchors[fact_id][1] in content
    ]
