"""
The relevance gate.

This runs *before* the model does. It looks at how close the best retrieved
chunk actually is, and if nothing came back close enough it refuses the
question outright.

Why this exists as its own step, rather than just asking the model nicely to
admit when it doesn't know: if you only ask nicely, it will sometimes ignore
you and write something confident and wrong. Those answers are much harder to
catch than obvious errors. Deciding in your own code when there's nothing worth
answering from is more reliable than hoping.

You keep the polite instruction too — it's in generate.py — but as a second
layer. The gate catches the clear misses; the prompt catches the near ones.
"""

from dataclasses import dataclass

import config
from store import Result

REFUSAL = "I don't have enough information about that."


@dataclass
class GateDecision:
    passed: bool
    best_distance: float
    threshold: float

    @property
    def explanation(self) -> str:
        if self.passed:
            return (
                f"best distance {self.best_distance:.3f} "
                f"is under the {self.threshold} cutoff"
            )
        return (
            f"best distance {self.best_distance:.3f} "
            f"is over the {self.threshold} cutoff — refusing"
        )


def check(results: list[Result], threshold: float | None = None) -> GateDecision:
    """
    Decide whether the retrieved chunks are close enough to answer from.

    Remember: LOWER distance is better. A question passes when its best chunk
    is *under* the threshold.
    """
    threshold = config.THRESHOLD if threshold is None else threshold

    if not results:
        return GateDecision(passed=False, best_distance=1.0, threshold=threshold)

    best = min(r.distance for r in results)
    return GateDecision(passed=best < threshold, best_distance=best, threshold=threshold)


def keep_relevant(results: list[Result], threshold: float | None = None) -> list[Result]:
    """
    Drop retrieved chunks the gate would not have accepted as a best match.

    Unit 2 improvement. `check` above decides whether to answer at all by
    looking only at `min(distance)`, and `store.py::search` hands back a fixed
    count regardless of distance. Between them, the same distance gets treated
    two opposite ways depending on where it ranked:

        best chunk at 0.71  ->  refuse the question outright, too thin
        4th chunk at 0.736  ->  put it in the prompt as context

    Measured on my five test questions before this existed, 8 of the 20 chunks
    reaching a prompt were past 0.610 — the furthest distance unit 1 found on a
    question the corpus genuinely answers — and two were past the 0.70 cutoff
    itself. `housing_tamsin_court.txt#1` at 0.736 was context for a question
    about the housing lottery.

    Applying one number in both directions is the whole change. A chunk is
    worth reasoning from, or it isn't.

    This can never empty the list: `check` has already established that the
    best chunk is under the threshold, so that chunk always survives. The
    guard below is for callers that filter without gating first.
    """
    threshold = config.THRESHOLD if threshold is None else threshold

    kept = [r for r in results if r.distance < threshold]
    return kept or results[:1]
