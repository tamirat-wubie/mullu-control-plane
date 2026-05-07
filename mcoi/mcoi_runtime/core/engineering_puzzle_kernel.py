"""Purpose: reference kernel for engineering-as-governed-arrangement-search.
Governance scope: episode goal handling, filter-stack evaluation, witness
checks, append-only lineage, and governed candidate commitment.
Dependencies: engineering puzzle contracts only.
Invariants:
  - History is never overwritten; every transition returns a new puzzle value.
  - Goal mutation closes the current episode and forks a new episode snapshot.
  - L2 survival is evaluated before L5 optimization.
  - Candidate state commits require authority, Phi_gov certification, and witness.
  - Model/observation mismatch restores the prior puzzle state.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from mcoi_runtime.contracts.engineering_puzzle import (
    CandidateArrangement,
    EngineeringPuzzle,
    EngineeringVerdict,
    FILTER_STACK_LEVELS,
    FilterEvaluation,
    FilterLevel,
    GoalDeltaDecision,
    GoalDeltaKind,
    JudgmentEnvelope,
)


def _require_bool(value: bool, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_event(event: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(event, Mapping):
        raise ValueError("event must be a mapping")
    event_name = event.get("event")
    if not isinstance(event_name, str) or not event_name.strip():
        raise ValueError("event must include non-empty event")
    return event


def append_history(
    puzzle: EngineeringPuzzle,
    event: Mapping[str, Any],
) -> EngineeringPuzzle:
    """Return a new puzzle with one event appended to immutable lineage."""

    _require_event(event)
    return replace(puzzle, history=puzzle.history + (dict(event),))


def classify_goal_delta(
    current_goal: str,
    proposed_goal: str,
    *,
    satisfaction_predicate_equivalent: bool,
) -> GoalDeltaKind:
    """Classify whether proposed goal text preserves the satisfaction predicate."""

    if not isinstance(current_goal, str) or not current_goal.strip():
        raise ValueError("current_goal must be a non-empty string")
    if not isinstance(proposed_goal, str) or not proposed_goal.strip():
        raise ValueError("proposed_goal must be a non-empty string")
    _require_bool(satisfaction_predicate_equivalent, "satisfaction_predicate_equivalent")
    if satisfaction_predicate_equivalent:
        return GoalDeltaKind.CLARIFICATION
    return GoalDeltaKind.MUTATION


def _replace_goal_invariant(
    invariants: tuple[str, ...],
    old_goal: str,
    new_goal: str,
) -> tuple[str, ...]:
    old_invariant = f"goal:{old_goal}"
    new_invariant = f"goal:{new_goal}"
    retained = tuple(item for item in invariants if item != old_invariant)
    return retained + (new_invariant,)


def handle_goal_delta(
    puzzle: EngineeringPuzzle,
    proposed_goal: str,
    *,
    satisfaction_predicate_equivalent: bool,
    new_episode_model_hash: str = "",
    fork_event_id: str = "",
) -> GoalDeltaDecision:
    """Apply goal-delta governance without silently editing episode intent."""

    kind = classify_goal_delta(
        puzzle.goal,
        proposed_goal,
        satisfaction_predicate_equivalent=satisfaction_predicate_equivalent,
    )

    if kind == GoalDeltaKind.CLARIFICATION:
        active_puzzle = append_history(
            puzzle,
            {
                "event": "GoalClarified",
                "goal": puzzle.goal,
                "proposed_goal": proposed_goal,
            },
        )
        return GoalDeltaDecision(
            kind=kind,
            active_puzzle=active_puzzle,
            judgment=JudgmentEnvelope(
                verdict=EngineeringVerdict.SOLVED_UNVERIFIED,
                confidence=1.0,
                margin=0.0,
                fragile=False,
                assumptions=("satisfaction predicate equivalence supplied",),
                unknowns=(),
                rejected_alternatives=(),
            ),
            closed_puzzle=None,
        )

    if not new_episode_model_hash.strip():
        raise ValueError("new_episode_model_hash is required for goal mutation")

    closed_puzzle = append_history(
        puzzle,
        {
            "event": "GoalMutated",
            "old_goal": puzzle.goal,
            "new_goal": proposed_goal,
            "verdict": EngineeringVerdict.AWAITING_NEW_EPISODE.value,
        },
    )
    fork_id = fork_event_id.strip() or f"fork:{puzzle.episode_model_hash}:{new_episode_model_hash}"
    new_puzzle = EngineeringPuzzle(
        invariants=_replace_goal_invariant(puzzle.invariants, puzzle.goal, proposed_goal),
        rules=puzzle.rules,
        state=puzzle.state,
        interfaces=puzzle.interfaces,
        history=closed_puzzle.history
        + (
            {
                "event": "EpisodeForked",
                "fork_event_id": fork_id,
                "old_goal": puzzle.goal,
                "new_goal": proposed_goal,
                "old_episode_model_hash": puzzle.episode_model_hash,
                "new_episode_model_hash": new_episode_model_hash,
            },
        ),
        goal=proposed_goal,
        episode_model_hash=new_episode_model_hash,
        observer=puzzle.observer,
        witness=None,
    )
    return GoalDeltaDecision(
        kind=kind,
        active_puzzle=new_puzzle,
        closed_puzzle=closed_puzzle,
        judgment=JudgmentEnvelope(
            verdict=EngineeringVerdict.GOAL_MUTATED,
            confidence=1.0,
            margin=0.0,
            fragile=True,
            assumptions=("satisfaction predicate changed",),
            unknowns=(),
            rejected_alternatives=("silent goal edit",),
        ),
    )


def evaluate_filter_stack(candidate: CandidateArrangement) -> FilterEvaluation:
    """Evaluate candidate filters in kernel order, stopping on first failure."""

    evaluated: list[FilterLevel] = []
    for level in FILTER_STACK_LEVELS:
        evaluated.append(level)
        if candidate.filter_results[level.value] is not True:
            return FilterEvaluation(
                passed=False,
                evaluated_levels=tuple(evaluated),
                failed_level=level,
            )
    return FilterEvaluation(
        passed=True,
        evaluated_levels=tuple(evaluated),
        failed_level=None,
    )


def _judgment_from_candidate(
    candidate: CandidateArrangement,
    *,
    verdict: EngineeringVerdict,
    confidence: float | None = None,
    margin: float | None = None,
    fragile: bool | None = None,
    rejected_alternatives: tuple[str, ...] | None = None,
) -> JudgmentEnvelope:
    return JudgmentEnvelope(
        verdict=verdict,
        confidence=candidate.confidence if confidence is None else confidence,
        margin=margin,
        fragile=candidate.fragile if fragile is None else fragile,
        assumptions=candidate.assumptions,
        unknowns=candidate.unknowns,
        rejected_alternatives=(
            candidate.rejected_alternatives
            if rejected_alternatives is None
            else rejected_alternatives
        ),
    )


def solve_engineering_puzzle(
    puzzle: EngineeringPuzzle,
    candidate: CandidateArrangement,
    *,
    confidence_floor: float,
) -> tuple[EngineeringPuzzle, JudgmentEnvelope]:
    """Judge and possibly commit a candidate arrangement through the kernel.

    The function is pure: accepted and rejected paths return new puzzle values
    with appended lineage while preserving the caller's original puzzle object.
    """

    if not isinstance(confidence_floor, (int, float)) or isinstance(confidence_floor, bool):
        raise ValueError("confidence_floor must be a number")
    if not (0.0 <= float(confidence_floor) <= 1.0):
        raise ValueError("confidence_floor must be between 0.0 and 1.0")
    confidence_floor = float(confidence_floor)

    if not candidate.authority_ref or not candidate.governance_certified:
        blocked = append_history(
            puzzle,
            {
                "event": "GovernanceBlocked",
                "candidate_id": candidate.candidate_id,
                "authority_ref": candidate.authority_ref,
                "governance_certified": candidate.governance_certified,
            },
        )
        return blocked, _judgment_from_candidate(
            candidate,
            verdict=EngineeringVerdict.GOVERNANCE_BLOCKED,
            confidence=1.0,
            margin=None,
            fragile=False,
            rejected_alternatives=("missing Phi_gov commitment authority",),
        )

    filter_evaluation = evaluate_filter_stack(candidate)
    if not filter_evaluation.passed:
        rejected = append_history(
            puzzle,
            {
                "event": "CandidateRejected",
                "candidate_id": candidate.candidate_id,
                "failed_level": filter_evaluation.failed_level.value,
            },
        )
        return rejected, _judgment_from_candidate(
            candidate,
            verdict=EngineeringVerdict.SAFE_HALT,
            margin=None,
            fragile=True,
            rejected_alternatives=(
                f"candidate failed {filter_evaluation.failed_level.value}",
            ),
        )

    confidence_margin = candidate.confidence - confidence_floor
    if candidate.confidence < confidence_floor:
        awaiting = append_history(
            puzzle,
            {
                "event": "AwaitingEvidence",
                "candidate_id": candidate.candidate_id,
                "reason": "confidence below floor",
                "confidence": candidate.confidence,
                "confidence_floor": confidence_floor,
            },
        )
        return awaiting, _judgment_from_candidate(
            candidate,
            verdict=EngineeringVerdict.AWAITING_EVIDENCE,
            margin=confidence_margin,
            fragile=True,
        )

    if candidate.witness is None:
        awaiting = append_history(
            puzzle,
            {
                "event": "AwaitingEvidence",
                "candidate_id": candidate.candidate_id,
                "reason": "missing dual verification witness",
            },
        )
        return awaiting, _judgment_from_candidate(
            candidate,
            verdict=EngineeringVerdict.AWAITING_EVIDENCE,
            margin=confidence_margin,
            fragile=True,
            rejected_alternatives=("commit without dual verification witness",),
        )

    if (
        not candidate.witness.passed
        or candidate.witness.mismatch_margin > candidate.witness.threshold
    ):
        invalidated = append_history(
            puzzle,
            {
                "event": "ModelInvalidated",
                "candidate_id": candidate.candidate_id,
                "witness_id": candidate.witness.witness_id,
                "mismatch_margin": candidate.witness.mismatch_margin,
                "threshold": candidate.witness.threshold,
                "rollback_plan": candidate.rollback_plan,
            },
        )
        return invalidated, _judgment_from_candidate(
            candidate,
            verdict=EngineeringVerdict.MODEL_INVALIDATED,
            margin=candidate.witness.threshold - candidate.witness.mismatch_margin,
            fragile=True,
            rejected_alternatives=("model prediction diverged from observation",),
        )

    new_state = dict(puzzle.state)
    new_state.update(dict(candidate.state_delta))
    committed = EngineeringPuzzle(
        invariants=puzzle.invariants,
        rules=puzzle.rules,
        state=new_state,
        interfaces=puzzle.interfaces,
        history=puzzle.history
        + (
            {
                "event": "CandidateCommitted",
                "candidate_id": candidate.candidate_id,
                "authority_ref": candidate.authority_ref,
                "witness_id": candidate.witness.witness_id,
            },
        ),
        goal=puzzle.goal,
        episode_model_hash=puzzle.episode_model_hash,
        observer=puzzle.observer,
        witness=candidate.witness,
    )
    return committed, _judgment_from_candidate(
        candidate,
        verdict=EngineeringVerdict.SOLVED_VERIFIED,
        margin=confidence_margin,
        fragile=candidate.fragile,
    )
