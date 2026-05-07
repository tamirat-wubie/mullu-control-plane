"""Tests for the engineering puzzle control-surface adapter.

Covers: JSON-like payload validation, governed candidate responses, goal
mutation responses, fail-closed missing fields, and event-spine emission.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.app.engineering_puzzle_control import (
    EngineeringPuzzleControlSurface,
    build_candidate_arrangement,
    build_engineering_puzzle,
)
from mcoi_runtime.contracts.engineering_puzzle import EngineeringVerdict, FILTER_STACK_LEVELS
from mcoi_runtime.core.event_spine import EventSpineEngine


def _observer_payload() -> dict[str, object]:
    return {
        "observer_id": "observer-architect-1",
        "invariants": ["observer inside puzzle"],
        "rules": ["propose only", "commit through Phi_gov"],
        "assumptions": ["fixture assumptions declared"],
        "known_unknowns": [],
        "risk_margins": [],
        "fragile_points": [],
        "interfaces": ["judgment-envelope"],
        "history_refs": [],
    }


def _witness_payload() -> dict[str, object]:
    return {
        "witness_id": "witness-1",
        "model_evidence": ["model-check:passed"],
        "observation_evidence": ["runtime-check:passed"],
        "prediction": "candidate preserves gateway invariants",
        "observation": "candidate preserved gateway invariants",
        "mismatch_margin": 0.0,
        "threshold": 0.1,
        "passed": True,
    }


def _puzzle_payload() -> dict[str, object]:
    goal = "build governed gateway"
    return {
        "invariants": [
            f"goal:{goal}",
            "history append only",
            "survival before optimization",
            "observer bound",
        ],
        "rules": ["Phi_gov commits", "L2 blocks L5", "dual witness required"],
        "state": {"gateway": "draft", "tenant_isolation": "unverified"},
        "interfaces": ["gateway-api", "audit-log"],
        "history": [],
        "goal": goal,
        "episode_model_hash": "episode-model-a",
        "observer": _observer_payload(),
    }


def _candidate_payload(**overrides: object) -> dict[str, object]:
    payload = {
        "candidate_id": "candidate-1",
        "state_delta": {"gateway": "verified", "tenant_isolation": "verified"},
        "filter_results": {level.value: True for level in FILTER_STACK_LEVELS},
        "confidence": 0.95,
        "authority_ref": "Phi_gov:approval-1",
        "governance_certified": True,
        "rollback_plan": "restore episode-model-a snapshot",
        "verification_plan": "run model lane and observation lane",
        "assumptions": ["tenant fixture is bounded"],
        "unknowns": [],
        "rejected_alternatives": ["commit without witness"],
        "fragile": False,
        "witness": _witness_payload(),
    }
    payload.update(overrides)
    return payload


def test_builders_create_contracts_from_plain_payloads() -> None:
    puzzle = build_engineering_puzzle(_puzzle_payload())
    candidate = build_candidate_arrangement(_candidate_payload())

    assert puzzle.goal == "build governed gateway"
    assert puzzle.observer.observer_id == "observer-architect-1"
    assert candidate.candidate_id == "candidate-1"
    assert candidate.witness.witness_id == "witness-1"
    assert candidate.filter_results["L2_survival"] is True


def test_control_surface_judges_candidate_as_json_safe_response() -> None:
    event_spine = EventSpineEngine()
    control = EngineeringPuzzleControlSurface(event_spine)

    response = control.judge_candidate(
        {
            "puzzle": _puzzle_payload(),
            "candidate": _candidate_payload(),
            "confidence_floor": 0.9,
        }
    )

    assert response["governed"] is True
    assert response["judgment"]["verdict"] == EngineeringVerdict.SOLVED_VERIFIED.value
    assert response["puzzle"]["state"]["gateway"] == "verified"
    assert response["event"]["payload"]["committed"] is True
    assert event_spine.event_count == 1


def test_control_surface_goal_mutation_returns_closed_and_active_puzzles() -> None:
    event_spine = EventSpineEngine()
    control = EngineeringPuzzleControlSurface(event_spine)

    response = control.decide_goal_delta(
        {
            "puzzle": _puzzle_payload(),
            "proposed_goal": "build full identity platform",
            "satisfaction_predicate_equivalent": False,
            "new_episode_model_hash": "episode-model-b",
            "fork_event_id": "fork-identity-platform",
        }
    )

    assert response["kind"] == "mutation"
    assert response["judgment"]["verdict"] == EngineeringVerdict.GOAL_MUTATED.value
    assert response["closed_puzzle"]["goal"] == "build governed gateway"
    assert response["active_puzzle"]["goal"] == "build full identity platform"
    assert response["event"]["payload"]["action"] == "engineering_goal_mutated"
    assert event_spine.event_count == 1


def test_missing_candidate_field_fails_closed_before_event_emit() -> None:
    event_spine = EventSpineEngine()
    control = EngineeringPuzzleControlSurface(event_spine)
    candidate = _candidate_payload()
    candidate.pop("rollback_plan")

    with pytest.raises(ValueError, match="rollback_plan is required"):
        control.judge_candidate(
            {
                "puzzle": _puzzle_payload(),
                "candidate": candidate,
                "confidence_floor": 0.9,
            }
        )

    assert event_spine.event_count == 0
    assert "rollback_plan" not in candidate
    assert _puzzle_payload()["goal"] == "build governed gateway"


def test_blocked_candidate_response_preserves_state() -> None:
    event_spine = EventSpineEngine()
    control = EngineeringPuzzleControlSurface(event_spine)

    response = control.judge_candidate(
        {
            "puzzle": _puzzle_payload(),
            "candidate": _candidate_payload(authority_ref="", governance_certified=False),
            "confidence_floor": 0.9,
        }
    )

    assert response["judgment"]["verdict"] == EngineeringVerdict.GOVERNANCE_BLOCKED.value
    assert response["puzzle"]["state"]["gateway"] == "draft"
    assert response["event"]["payload"]["committed"] is False
    assert response["event"]["payload"]["governance_certified"] is False
    assert event_spine.event_count == 1
