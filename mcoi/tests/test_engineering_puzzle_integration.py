"""Integration tests for engineering puzzle kernel event-spine binding.

Covers: facade validation, goal decision event emission, candidate judgment
event emission, governed commit behavior, and blocked candidate preservation.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.engineering_puzzle import (
    CandidateArrangement,
    EngineeringPuzzle,
    EngineeringVerdict,
    FILTER_STACK_LEVELS,
    ObserverNode,
    VerificationWitness,
)
from mcoi_runtime.core.engineering_puzzle_integration import EngineeringPuzzleIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


class TickClock:
    """Deterministic ISO clock for event id stability without collisions."""

    def __init__(self) -> None:
        self._tick = 0

    def __call__(self) -> str:
        self._tick += 1
        return f"2026-05-07T12:00:0{self._tick}+00:00"


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


def _witness() -> VerificationWitness:
    return VerificationWitness(
        witness_id="witness-1",
        model_evidence=("model-check:passed",),
        observation_evidence=("runtime-check:passed",),
        prediction="candidate preserves gateway invariants",
        observation="candidate preserved gateway invariants",
        mismatch_margin=0.0,
        threshold=0.1,
        passed=True,
    )


def _candidate(**overrides: object) -> CandidateArrangement:
    fields = {
        "candidate_id": "candidate-1",
        "state_delta": {"gateway": "verified", "tenant_isolation": "verified"},
        "filter_results": {level: True for level in FILTER_STACK_LEVELS},
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


def _integration(event_spine: EventSpineEngine) -> EngineeringPuzzleIntegration:
    return EngineeringPuzzleIntegration(event_spine, clock=TickClock())


def test_constructor_rejects_invalid_event_spine() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
        EngineeringPuzzleIntegration("not-an-event-spine")

    assert EventSpineEngine().event_count == 0
    assert _puzzle().observer.observer_id == "observer-architect-1"
    assert _candidate().candidate_id == "candidate-1"


def test_goal_clarification_emits_append_only_event() -> None:
    event_spine = EventSpineEngine()
    integration = _integration(event_spine)

    result = integration.decide_goal_delta(
        _puzzle(),
        "build governed gateway with authorization boundary",
        satisfaction_predicate_equivalent=True,
    )
    event = result["event"]
    decision = result["decision"]

    assert event_spine.event_count == 1
    assert event.payload["action"] == "engineering_goal_clarified"
    assert event.payload["kind"] == "clarification"
    assert event.payload["verdict"] == EngineeringVerdict.SOLVED_UNVERIFIED.value
    assert decision.active_puzzle.goal == "build governed gateway"
    assert event.payload["active_history_depth"] == 1


def test_goal_mutation_emits_fork_event() -> None:
    event_spine = EventSpineEngine()
    integration = _integration(event_spine)

    result = integration.decide_goal_delta(
        _puzzle(),
        "build full identity platform",
        satisfaction_predicate_equivalent=False,
        new_episode_model_hash="episode-model-b",
        fork_event_id="fork-identity-platform",
    )
    event = result["event"]
    active_puzzle = result["active_puzzle"]
    closed_puzzle = result["closed_puzzle"]

    assert event_spine.event_count == 1
    assert event.payload["action"] == "engineering_goal_mutated"
    assert event.payload["verdict"] == EngineeringVerdict.GOAL_MUTATED.value
    assert active_puzzle.goal == "build full identity platform"
    assert closed_puzzle.goal == "build governed gateway"
    assert event.payload["closed_history_depth"] == 1


def test_candidate_judgment_event_records_commit() -> None:
    event_spine = EventSpineEngine()
    integration = _integration(event_spine)

    result = integration.judge_candidate(
        _puzzle(),
        _candidate(),
        confidence_floor=0.9,
    )
    event = result["event"]
    judgment = result["judgment"]
    next_puzzle = result["puzzle"]

    assert event_spine.event_count == 1
    assert event.payload["action"] == "engineering_candidate_judged"
    assert event.payload["committed"] is True
    assert event.payload["verdict"] == EngineeringVerdict.SOLVED_VERIFIED.value
    assert judgment.verdict == EngineeringVerdict.SOLVED_VERIFIED
    assert next_puzzle.state["gateway"] == "verified"


def test_candidate_block_event_preserves_state() -> None:
    event_spine = EventSpineEngine()
    integration = _integration(event_spine)
    blocked_candidate = _candidate(authority_ref="", governance_certified=False)
    puzzle = _puzzle()

    result = integration.judge_candidate(
        puzzle,
        blocked_candidate,
        confidence_floor=0.9,
    )
    event = result["event"]
    judgment = result["judgment"]
    next_puzzle = result["puzzle"]

    assert event_spine.event_count == 1
    assert event.payload["committed"] is False
    assert event.payload["verdict"] == EngineeringVerdict.GOVERNANCE_BLOCKED.value
    assert judgment.verdict == EngineeringVerdict.GOVERNANCE_BLOCKED
    assert next_puzzle.state == puzzle.state
    assert next_puzzle.history[-1]["event"] == "GovernanceBlocked"
