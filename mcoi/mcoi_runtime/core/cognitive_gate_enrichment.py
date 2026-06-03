"""Safety-positive enrichment for live cognitive DECIDE verdicts.

Purpose: pure Stage-E helper that reads already-derived prior outcome counts and
returns a verdict that is never less restrictive than today's verdict.
Governance scope: pure decision enrichment only; no engine reads, no IO, no state.
Invariants:
  - Monotone safety: rank(enriched) >= rank(today) for all valid inputs.
  - Bad priors input degrades to today's verdict unchanged.
  - The initial rule set is intentionally small and auditable.
"""

from __future__ import annotations

from mcoi_runtime.core.cognitive_loop import DecisionVerdict
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

# Higher rank means more restrictive / more refusal.
VERDICT_RANK: dict[DecisionVerdict, int] = {
    DecisionVerdict.PROCEED: 0,
    DecisionVerdict.PROCEED_WITH_CAUTION: 1,
    DecisionVerdict.REPLAN: 2,
    DecisionVerdict.DEFER_TO_REVIEW: 3,
    DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT: 4,
}

_E2_MIN_SAMPLE = 3
_E2_BAD_SUCCESS_RATE = 0.5


def more_restrictive_verdict(
    left: DecisionVerdict,
    right: DecisionVerdict,
) -> DecisionVerdict:
    """Return the more restrictive of two verdicts.

    Pure / total / commutative. ``left`` is returned on ties so the function is
    deterministic for snapshot-style tests.
    """
    if not isinstance(left, DecisionVerdict):
        raise RuntimeCoreInvariantError("more_restrictive_verdict requires DecisionVerdict")
    if not isinstance(right, DecisionVerdict):
        raise RuntimeCoreInvariantError("more_restrictive_verdict requires DecisionVerdict")
    return left if VERDICT_RANK[left] >= VERDICT_RANK[right] else right


def enrich_verdict(
    today_verdict: DecisionVerdict,
    *,
    prior_outcomes_count: int,
    prior_success_count: int,
) -> DecisionVerdict:
    """Return a verdict at least as restrictive as ``today_verdict``.

    Rules:
      E1: PROCEED_WITH_CAUTION + zero prior outcomes -> DEFER_TO_REVIEW.
      E2: REPLAN + >=3 prior outcomes + success_rate < 0.5 -> DEFER_TO_REVIEW.

    Bad priors input returns today's verdict unchanged so malformed evidence cannot
    create a spurious refusal.
    """
    if not isinstance(today_verdict, DecisionVerdict):
        raise RuntimeCoreInvariantError("enrich_verdict requires a DecisionVerdict today")
    if not isinstance(prior_outcomes_count, int) or not isinstance(prior_success_count, int):
        return today_verdict
    if prior_outcomes_count < 0 or prior_success_count < 0:
        return today_verdict
    if prior_success_count > prior_outcomes_count:
        return today_verdict

    result = today_verdict
    if today_verdict is DecisionVerdict.PROCEED_WITH_CAUTION and prior_outcomes_count == 0:
        result = more_restrictive_verdict(result, DecisionVerdict.DEFER_TO_REVIEW)

    if today_verdict is DecisionVerdict.REPLAN and prior_outcomes_count >= _E2_MIN_SAMPLE:
        success_rate = prior_success_count / prior_outcomes_count
        if success_rate < _E2_BAD_SUCCESS_RATE:
            result = more_restrictive_verdict(result, DecisionVerdict.DEFER_TO_REVIEW)

    return result


__all__ = [
    "VERDICT_RANK",
    "enrich_verdict",
    "more_restrictive_verdict",
]
