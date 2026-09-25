#!/usr/bin/env python3
"""
Deciding what counts as correct.

`run_eval.py` looks for this file and calls `judge` if it finds it, which turns
the Run columns in results/ from blanks into verdicts. That is the only hook it
uses, and one boolean per run cannot carry five criteria — so the rest of this
file measures the criteria that never reach the model at all:

    python scorer.py        criteria 1 and 4, no API calls, deterministic

⚠️ This is test tooling, not the system. Nothing in here is imported by
ingest → chunker → store → gate → generate. The unit-2 rule that the only
change to the system is the improvement is about that pipeline; measuring it
more honestly is not a change to it.

What each criterion is measured by, and why here rather than by hand:

  1. Retrieved chunks contain the answer   `retrieval_contains_answer`
     Retrieval is a fixed query against a fixed index, so this is the same in
     every run. Measuring it costs nothing — no generation happens.

  2. Every answer names a source           `names_a_source`
     Has to read the generated answer, so it is scored per run, from the
     transcript run_eval.py writes.

  3. Gate stops out-of-corpus questions    run_eval.py::check_out_of_scope
     Already measured there. Not repeated here.

  4. Chunks keep answers whole             `chunk_check`
     A property of chunker.py output, not of any run. Never touches retrieval.

  5. Answers are right and grounded        `judge`  ← run_eval.py's hook
     The objective half of it, anyway. See that function's docstring for the
     half a script cannot do.
"""

import re
import sys

# ─── Matching facts in text ──────────────────────────────────────────────────

_WS = re.compile(r"\s+")
_DASHES = re.compile(r"[‐-―]")


def normalize(text: str) -> str:
    """Collapse whitespace and unify dash characters, preserving case.

    Case survives because `expects` can be a single letter — criterion 4's
    question 4 expects a "W" on the transcript, and a case-insensitive search
    for "w" matches every other word in the corpus.
    """
    return _WS.sub(" ", _DASHES.sub("-", text)).strip()


def _fact_pattern(expects: str) -> re.Pattern:
    """A regex that matches `expects` allowing for how people write numbers.

    "20 to 25 minutes" is written that way in the document and may come back
    from the model as "20-25 minutes". Runs of whitespace are flexible for the
    same reason. Everything else is matched literally, between word boundaries,
    so "W" matches the transcript mark and not the "w" in "window".
    """
    tokens = normalize(expects).split(" ")
    parts = []
    for token in tokens:
        if token == "to" and parts:
            # "20 to 25" / "20-25" / "20 - 25"
            parts.append(r"(?:to|-)")
        else:
            parts.append(re.escape(token))

    body = r"\s*".join(parts) if len(parts) > 1 else parts[0]
    # Single uppercase letters stay case-sensitive; real phrases don't need to.
    flags = 0 if len(expects.strip()) <= 2 else re.IGNORECASE
    return re.compile(rf"\b{body}\b", flags)


def contains_fact(text: str, expects: str) -> bool:
    """Does `text` state the fact that `expects` names?"""
    if not expects.strip():
        return False
    return bool(_fact_pattern(expects).search(normalize(text)))


# ─── Criterion 1: retrieved chunks contain the answer ────────────────────────


def retrieval_contains_answer(results, expects: str) -> bool:
    """
    criteria.md 1 — "the retrieved chunks include one that contains the answer."

    Read literally: one of the chunks handed back has the answer in it. The
    `expects` phrase written in questions.py *before* any results existed is
    what stands in for "the answer", which is the whole reason it was written
    then rather than now.
    """
    return any(contains_fact(r.text, expects) for r in results)


# ─── Criterion 2: every answer names a source ────────────────────────────────

_FILENAME = re.compile(r"\b([A-Za-z0-9_\-]+\.txt)\b")


def names_a_source(answer: str, results=None) -> str | None:
    """
    criteria.md 2 — "names at least one source document."

    Returns the filename it named, or None. When `results` is given the name
    also has to be one of the files actually retrieved: a filename the model
    invented is not a source, it is a second thing to check.

    This reads the answer text only. app.py prints a "Sources retrieved:" line
    of its own underneath, and counting that would score the retriever rather
    than the answer — every answer would pass for free.
    """
    named = _FILENAME.findall(answer or "")
    if not named:
        return None
    if results is None:
        return named[0]

    retrieved = {r.source for r in results}
    for name in named:
        if name in retrieved:
            return name
    return None


def is_refusal(answer: str) -> bool:
    """Did the system decline to answer, at either layer?

    gate.REFUSAL is the fixed string; GROUNDING_INSTRUCTION produces the
    free-form variants, which is why this matches on the phrase rather than
    on equality.
    """
    text = normalize(answer or "").lower()
    return bool(re.search(r"do(?:n'|\sno)t have enough information", text))


# ─── Criterion 5: right, and grounded ────────────────────────────────────────


def judge(question: str, expects: str, answer: str, results) -> bool:
    """
    criteria.md 5 — the hook run_eval.py calls. One run of one question.

    The criterion has two halves:

      "produces an answer that directly addresses the question"   ← checked
      "whose factual claims are all supported by the documents"   ← partly

    What this checks: the answer is not a refusal, it states the fact the
    question was written to elicit, and it names a document that was really
    retrieved. Those three are decidable and they are decided the same way
    every time, which a person reading thirty answers is not.

    What it cannot check is the rest of the sentence. An answer can carry the
    right fact and an invented one beside it, and this returns True. So every
    answer still gets read for unsupported claims, and where reading disagrees
    with this function the README says so and the reading wins. Writing a
    scorer that pretended otherwise would be the easier thing to do and would
    make criterion 5 meaningless.
    """
    if is_refusal(answer):
        return False
    if not contains_fact(answer, expects):
        return False
    return names_a_source(answer, results) is not None


# ─── Criterion 4: chunks keep answers whole ──────────────────────────────────

# criteria.md 4: "at least one produced chunk must contain both the relevant
# topic identifier and the complete answer-bearing sentence, including any
# condition or exception in that sentence."
#
# So each of the five posts a test question was written from needs, in ONE
# chunk: the topic marker, and the answer sentence entire. The sentences below
# are quoted from the documents, and `_verify_spec` re-reads the corpus at
# import to prove they still are — a typo here would otherwise quietly fail a
# post that is fine, or pass one that isn't.
ANSWER_SENTENCES = [
    {
        "question": 1,
        "source": "admin_parking_permits.txt",
        "topic": "parking permits",
        "sentence": "Student permits for the west lots go on sale in August and sell out in about three days.",
        "why": "'three days' is meaningless without 'west lots' — the east lot never sells out.",
    },
    {
        "question": 2,
        "source": "admin_housing_lottery.txt",
        "topic": "housing lottery",
        "sentence": "Rising sophomores get a number drawn at random, but juniors and seniors are ordered by accumulated credit hours first, and only tie-break randomly.",
        "why": "The exception ('only tie-break randomly') is what separates juniors and seniors from sophomores. Split it off and the answer inverts.",
    },
    {
        "question": 3,
        "source": "advising_registration.txt",
        "topic": "adviser",
        "sentence": "Book two weeks out.",
        "why": "Four words. Without the title anchoring it to advisers, 'two weeks out' could be any deadline in the corpus.",
    },
    {
        "question": 4,
        "source": "admin_add_drop_deadline.txt",
        "topic": "add/drop",
        "sentence": "Dropping is a longer window - through the end of week six - but a drop after week two shows as a W on your transcript.",
        "why": "The condition 'after week two' and the consequence 'a W' are one sentence. Separated, this document is indistinguishable from admin_withdrawal_deadline.txt, which also mentions a W and week six.",
    },
    {
        "question": 5,
        "source": "dining_kestrel_commons.txt",
        "topic": "Kestrel Commons",
        "sentence": "Wait times: 20 to 25 minutes between 12:15 and 1:00, under 5 minutes before 11:45.",
        "why": "The window '12:15 and 1:00' is the condition — the same sentence says under 5 minutes before 11:45.",
    },
]


def _verify_spec(documents) -> list[str]:
    """Check every sentence above is really in the document it claims.

    Returns the problems. This is here because the spec is hand-quoted, and a
    hand-quoted string that has drifted from the corpus turns criterion 4 into
    a check on my typing.
    """
    by_source = {d.source: normalize(d.text) for d in documents}
    problems = []
    for spec in ANSWER_SENTENCES:
        text = by_source.get(spec["source"])
        if text is None:
            problems.append(f"{spec['source']} is not in the corpus")
        elif normalize(spec["sentence"]) not in text:
            problems.append(
                f"{spec['source']}: the quoted sentence is not in the document"
            )
    return problems


def chunk_check(chunks=None, documents=None) -> list[dict]:
    """
    criteria.md 4, measured against chunker.py output directly.

    Deliberately does not go through retrieval. The criterion exists to say
    something about the chunks themselves — "independently of whether retrieval
    finds them" — so that when retrieval fails there is already evidence about
    which stage to look at.
    """
    from ingest import load_documents
    from chunker import split_documents

    if documents is None:
        documents = load_documents()
    if chunks is None:
        chunks = split_documents(documents)

    problems = _verify_spec(documents)
    if problems:
        raise RuntimeError(
            "scorer.py's quoted sentences no longer match the corpus:\n  "
            + "\n  ".join(problems)
        )

    rows = []
    for spec in ANSWER_SENTENCES:
        sentence = normalize(spec["sentence"])
        topic = normalize(spec["topic"]).lower()

        mine = [c for c in chunks if c.source == spec["source"]]
        holder = None
        has_sentence = False
        for chunk in mine:
            text = normalize(chunk.text)
            if sentence in text:
                has_sentence = True
                if topic in text.lower():
                    holder = chunk
                    break

        rows.append(
            {
                **spec,
                "chunks_from_post": len(mine),
                "sentence_intact": has_sentence,
                "chunk": holder,
                "passed": holder is not None,
            }
        )
    return rows


# ─── Printing the deterministic criteria ─────────────────────────────────────


def _report() -> int:
    from ingest import load_documents
    from chunker import split_documents, describe
    from store import search
    import config
    import questions as qs

    documents = load_documents()
    chunks = split_documents(documents)

    print("Produced by `scorer.py::_report`. No model calls: criteria 1 and 4")
    print("are fixed by the index and the chunker, not by the run.\n")
    print(describe(chunks))

    print("\n" + "=" * 72)
    print("CRITERION 4 — chunks keep the answer sentence whole, with its topic")
    print("=" * 72)
    print("Measured by `scorer.py::chunk_check` on `chunker.py::split_documents`.\n")

    rows = chunk_check(chunks, documents)
    for row in rows:
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"  Q{row['question']}  {mark}  {row['source']} "
              f"({row['chunks_from_post']} chunk(s))")
        if not row["passed"]:
            print(f"        sentence survived intact: {row['sentence_intact']}")
            print(f"        (needs topic '{row['topic']}' in the same chunk)")
        else:
            print(f"        in {row['chunk'].label}")
    passed_4 = sum(r["passed"] for r in rows)
    print(f"\n  -> {passed_4} of {len(rows)} posts pass. Target: 5 of 5.")

    print("\n" + "=" * 72)
    print("CRITERION 1 — a retrieved chunk contains the answer")
    print("=" * 72)
    print(f"Measured by `scorer.py::retrieval_contains_answer` over "
          f"`store.py::search`,\ntop-k {config.TOP_K}. Retrieval is deterministic, "
          f"so this is the same in every run.\n")

    passed_1 = 0
    for i, item in enumerate(qs.answered(), 1):
        results = search(item["question"], top_k=config.TOP_K)
        ok = retrieval_contains_answer(results, item["expects"])
        passed_1 += ok
        best = min((r.distance for r in results), default=1.0)
        print(f"  Q{i}  {'PASS' if ok else 'FAIL'}  expects {item['expects']!r}  "
              f"(best distance {best:.3f})")
        for rank, r in enumerate(results, 1):
            hit = "<-- has the answer" if contains_fact(r.text, item["expects"]) else ""
            print(f"        {rank}. {r.label:<42} {r.distance:.3f}  {hit}")
    print(f"\n  -> {passed_1} of {len(qs.answered())} questions. Target: 4 of 5.")

    return 0 if (passed_4 == len(rows) and passed_1 >= 4) else 1


if __name__ == "__main__":
    sys.exit(_report())
