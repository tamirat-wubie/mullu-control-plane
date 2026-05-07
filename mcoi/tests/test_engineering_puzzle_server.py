"""Server-level tests for engineering puzzle route wiring.

Covers: server dependency registration, included FastAPI route, governed
candidate response, and route-ready JSON envelope shape.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.contracts.engineering_puzzle import EngineeringVerdict, FILTER_STACK_LEVELS


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


def _candidate_payload() -> dict[str, object]:
    return {
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


@pytest.fixture
def client() -> TestClient:
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app

    return TestClient(app)


def test_engineering_puzzle_control_registered(client: TestClient) -> None:
    control = deps.get("engineering_puzzle_control")
    event_spine = deps.get("engineering_puzzle_event_spine")

    assert control is not None
    assert event_spine.event_count >= 0
    assert client is not None
    assert hasattr(control, "judge_candidate")


def test_engineering_puzzle_candidate_route_wired(client: TestClient) -> None:
    response = client.post(
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
    assert body["event"]["payload"]["action"] == "engineering_candidate_judged"
