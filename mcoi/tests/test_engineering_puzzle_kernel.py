"""Tests for the engineering puzzle kernel closure.

Covers: immutable episode goals, observer binding, filter-stack precedence,
Phi_gov commitment gating, dual verification witness requirements, and
append-only lineage.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.engineering_puzzle import (
    CandidateArrangement,
    EngineeringPuzzle,
    EngineeringVerdict,
    FILTER_STACK_LEVELS,
    FilterLevel,
    GoalDeltaKind,
    ObserverNode,
    VerificationWitness,
)
from mcoi_runtime.core.engineering_puzzle_kernel import (
    evaluate_filter_stack,
    handle_goal_delta,
    solve_engineering_puzzle,
)


def _observer() -> ObserverNode:
    return ObserverNode(
        observer_id="observer-architect-1",
        invariants=("observer inside puzzle",),
        rules=("propose only", "commit through Phi_gov"),
        assumptions=("fixture assumptions declared",),
        known_unknowns=(),
        risk_margins=(),
        fragile_points=(),
        interfaces=("judgment-envelope",),
        history_refs=(),
    )


def _puzzle() -> EngineeringPuzzle:
    goal = "build governed gateway"
    return EngineeringPuzzle(
        invariants=(
            f"goal:{goal}",
            "history append only",
            "survival before optimization",
            "observer bound",
        ),
        rules=("Phi_gov commits", "L2 blocks L5", "dual witness required"),
        state={"gateway": "draft", "tenant_isolation": "unverified"},
        interfaces=("gateway-api", "audit-log"),
        history=(),
        goal=goal,
        episode_model_hash="episode-model-a",
        observer=_observer(),
        witness=None,
    )


def _witness(**overrides: object) -> VerificationWitness:
    fields = {
        "witness_id": "witness-1",
        "model_evidence": ("model-check:passed",),
        "observation_evidence": ("runtime-check:passed",),
        "prediction": "candidate preserves gateway invariants",
        "observation": "candidate preserved gateway invariants",
        "mismatch_margin": 0.0,
        "threshold": 0.1,
        "passed": True,
    }
    fields.update(overrides)
    return VerificationWitness(**fields)


def _filter_results(
    overrides: dict[FilterLevel, bool] | None = None,
) -> dict[FilterLevel, bool]:
    results = {level: True for level in FILTER_STACK_LEVELS}
    if overrides:
        results.update(overrides)
    return results


def _candidate(**overrides: object) -> CandidateArrangement:
    fields = {
        "candidate_id": "candidate-1",
        "state_delta": {"gateway": "verified", "tenant_isolation": "verified"},
        "filter_results": _filter_results(),
        "confidence": 0.95,
        "authority_ref": "Phi_gov:approval-1",
        "governance_certified": True,
        "rollback_plan": "restore episode-model-a snapshot",
        "verification_plan": "run model lane and observation lane",
        "assumptions": ("tenant fixture is bounded",),
        "unknowns": (),
        "rejected_alternatives": ("commit without witness",),
        "fragile": False,
        "witness": _witness(),
    }
    fields.update(overrides)
    return CandidateArrangement(**fields)


def test_filter_stack_blocks_optimization_when_survival_fails() -> None:
    candidate = _candidate(
        filter_results=_filter_results({FilterLevel.L2_SURVIVAL: False})
    )

    result = evaluate_filter_stack(candidate)

    assert result.passed is False
    assert result.failed_level == FilterLevel.L2_SURVIVAL
    assert result.evaluated_levels == (
        FilterLevel.L0_FEASIBILITY,
        FilterLevel.L1_IDENTITY,
        FilterLevel.L2_SURVIVAL,
    )
    assert FilterLevel.L5_OPTIMIZATION not in result.evaluated_levels


def test_candidate_without_governance_authority_is_blocked() -> None:
    puzzle = _puzzle()
    candidate = _candidate(authority_ref="", governance_certified=False)

    next_puzzle, judgment = solve_engineering_puzzle(
        puzzle,
        candidate,
        confidence_floor=0.9,
    )

    assert judgment.verdict == EngineeringVerdict.GOVERNANCE_BLOCKED
    assert len(puzzle.history) == 0
    assert len(next_puzzle.history) == 1
    assert next_puzzle.history[0]["event"] == "GovernanceBlocked"
    assert next_puzzle.state == puzzle.state


def test_missing_witness_keeps_candidate_uncommitted() -> None:
    puzzle = _puzzle()
    candidate = _candidate(witness=None)

    next_puzzle, judgment = solve_engineering_puzzle(
        puzzle,
        candidate,
        confidence_floor=0.9,
    )

    assert judgment.verdict == EngineeringVerdict.AWAITING_EVIDENCE
    assert next_puzzle.state == puzzle.state
    assert next_puzzle.witness is None
    assert next_puzzle.history[0]["reason"] == "missing dual verification witness"
    assert "commit without dual verification witness" in judgment.rejected_alternatives


def test_verified_candidate_commits_state_and_witness() -> None:
    puzzle = _puzzle()
    candidate = _candidate()

    committed, judgment = solve_engineering_puzzle(
        puzzle,
        candidate,
        confidence_floor=0.9,
    )

    assert judgment.verdict == EngineeringVerdict.SOLVED_VERIFIED
    assert judgment.margin == pytest.approx(0.05)
    assert committed.state["gateway"] == "verified"
    assert puzzle.state["gateway"] == "draft"
    assert committed.witness == candidate.witness
    assert committed.history[0]["event"] == "CandidateCommitted"


def test_model_invalidated_preserves_prior_state() -> None:
    puzzle = _puzzle()
    invalid_witness = _witness(
        witness_id="witness-invalid",
        mismatch_margin=0.4,
        threshold=0.1,
        passed=False,
    )
    candidate = _candidate(witness=invalid_witness)

    next_puzzle, judgment = solve_engineering_puzzle(
        puzzle,
        candidate,
        confidence_floor=0.9,
    )

    assert judgment.verdict == EngineeringVerdict.MODEL_INVALIDATED
    assert next_puzzle.state == puzzle.state
    assert next_puzzle.witness is None
    assert next_puzzle.history[0]["event"] == "ModelInvalidated"
    assert next_puzzle.history[0]["witness_id"] == "witness-invalid"


def test_goal_clarification_does_not_edit_episode_goal() -> None:
    puzzle = _puzzle()

    decision = handle_goal_delta(
        puzzle,
        "build governed gateway with explicit authorization boundary",
        satisfaction_predicate_equivalent=True,
    )

    assert decision.kind == GoalDeltaKind.CLARIFICATION
    assert decision.closed_puzzle is None
    assert decision.active_puzzle.goal == puzzle.goal
    assert decision.active_puzzle.history[0]["event"] == "GoalClarified"
    assert decision.judgment.verdict == EngineeringVerdict.SOLVED_UNVERIFIED


def test_goal_mutation_forks_new_episode() -> None:
    puzzle = _puzzle()

    decision = handle_goal_delta(
        puzzle,
        "build full identity platform",
        satisfaction_predicate_equivalent=False,
        new_episode_model_hash="episode-model-b",
        fork_event_id="fork-identity-platform",
    )

    assert decision.kind == GoalDeltaKind.MUTATION
    assert decision.closed_puzzle is not None
    assert decision.closed_puzzle.goal == "build governed gateway"
    assert decision.active_puzzle.goal == "build full identity platform"
    assert decision.active_puzzle.episode_model_hash == "episode-model-b"
    assert decision.active_puzzle.history[-2]["event"] == "GoalMutated"
    assert decision.active_puzzle.history[-1]["event"] == "EpisodeForked"
    assert "goal:build full identity platform" in decision.active_puzzle.invariants
    assert "goal:build governed gateway" not in decision.active_puzzle.invariants


def test_candidate_requires_explicit_result_for_every_filter_level() -> None:
    incomplete_results = {level: True for level in FILTER_STACK_LEVELS}
    incomplete_results.pop(FilterLevel.L6_LEARNING)

    with pytest.raises(ValueError, match="filter_results must declare every filter level"):
        _candidate(filter_results=incomplete_results)

    assert FilterLevel.L6_LEARNING not in incomplete_results
    assert len(incomplete_results) == len(FILTER_STACK_LEVELS) - 1
    assert _puzzle().goal == "build governed gateway"
