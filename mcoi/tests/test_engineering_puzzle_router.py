"""Tests for standalone engineering puzzle FastAPI router.

Covers: dependency wiring, route-level payload validation, governed candidate
judgment, goal mutation, and fail-closed missing control-surface behavior.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.engineering_puzzle_control import EngineeringPuzzleControlSurface
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.engineering_puzzle import router
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


@pytest.fixture
def isolated_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(deps, "_store", {}, raising=False)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_missing_control_surface_returns_503(isolated_client: TestClient) -> None:
    response = isolated_client.post(
        "/api/v1/engineering-puzzle/candidates/judge",
        json={
            "puzzle": _puzzle_payload(),
            "candidate": _candidate_payload(),
            "confidence_floor": 0.9,
        },
    )

    assert response.status_code == 503
    assert "engineering_puzzle_control" in response.json()["detail"]
    assert response.request.method == "POST"
    assert response.request.url.path.endswith("/candidates/judge")


def test_engineering_candidate_judgment_governed(
    isolated_client: TestClient,
) -> None:
    event_spine = EventSpineEngine()
    deps.set("engineering_puzzle_control", EngineeringPuzzleControlSurface(event_spine))

    response = isolated_client.post(
        "/api/v1/engineering-puzzle/candidates/judge",
        json={
            "puzzle": _puzzle_payload(),
            "candidate": _candidate_payload(),
            "confidence_floor": 0.9,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["governed"] is True
    assert body["judgment"]["verdict"] == EngineeringVerdict.SOLVED_VERIFIED.value
    assert body["puzzle"]["state"]["gateway"] == "verified"
    assert body["event"]["payload"]["committed"] is True
    assert event_spine.event_count == 1


def test_engineering_goal_delta_classified(
    isolated_client: TestClient,
) -> None:
    event_spine = EventSpineEngine()
    deps.set("engineering_puzzle_control", EngineeringPuzzleControlSurface(event_spine))

    response = isolated_client.post(
        "/api/v1/engineering-puzzle/goal-delta",
        json={
            "puzzle": _puzzle_payload(),
            "proposed_goal": "build full identity platform",
            "satisfaction_predicate_equivalent": False,
            "new_episode_model_hash": "episode-model-b",
            "fork_event_id": "fork-identity-platform",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "mutation"
    assert body["active_puzzle"]["goal"] == "build full identity platform"
    assert body["closed_puzzle"]["goal"] == "build governed gateway"
    assert body["event"]["payload"]["action"] == "engineering_goal_mutated"
    assert event_spine.event_count == 1


def test_route_validation_error_returns_400_without_event_emit(
    isolated_client: TestClient,
) -> None:
    event_spine = EventSpineEngine()
    deps.set("engineering_puzzle_control", EngineeringPuzzleControlSurface(event_spine))
    candidate = _candidate_payload()
    candidate.pop("rollback_plan")

    response = isolated_client.post(
        "/api/v1/engineering-puzzle/candidates/judge",
        json={
            "puzzle": _puzzle_payload(),
            "candidate": candidate,
            "confidence_floor": 0.9,
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "invalid engineering puzzle candidate judgment"
    assert detail["error_code"] == "invalid_candidate_judgment"
    assert detail["governed"] is True
    assert event_spine.event_count == 0
    assert "rollback_plan" not in candidate


def test_engineering_puzzle_errors_sanitized(
    isolated_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    control = EngineeringPuzzleControlSurface(EventSpineEngine())

    def fail_with_sensitive_detail(payload: dict[str, object]) -> dict[str, object]:
        raise ValueError("secret-token-from-kernel")

    monkeypatch.setattr(control, "judge_candidate", fail_with_sensitive_detail)
    deps.set("engineering_puzzle_control", control)

    response = isolated_client.post(
        "/api/v1/engineering-puzzle/candidates/judge",
        json={
            "puzzle": _puzzle_payload(),
            "candidate": _candidate_payload(),
            "confidence_floor": 0.9,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "invalid_candidate_judgment"
    assert response.json()["detail"]["governed"] is True
    assert "secret-token-from-kernel" not in response.text


def test_invalid_control_surface_type_returns_500(
    isolated_client: TestClient,
) -> None:
    deps.set("engineering_puzzle_control", object())

    response = isolated_client.post(
        "/api/v1/engineering-puzzle/candidates/judge",
        json={
            "puzzle": _puzzle_payload(),
            "candidate": _candidate_payload(),
            "confidence_floor": 0.9,
        },
    )

    assert response.status_code == 500
    assert "invalid type" in response.json()["detail"]
    assert response.json()["detail"].startswith("Dependency")
