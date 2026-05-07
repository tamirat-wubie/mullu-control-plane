"""Purpose: verify policy sandbox simulation engine and HTTP endpoints.
Governance scope: simulation tests only.
Dependencies: policy_sandbox module, FastAPI test client.
Invariants: simulations never modify real state; results are deterministic.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.governance.policy.sandbox import (
    PolicySandbox,
    SimulationRequest,
    SimulationScenario,
)


_CLOCK = "2026-03-30T00:00:00+00:00"


def _make_sandbox(**kwargs) -> PolicySandbox:
    return PolicySandbox(clock=lambda: _CLOCK, **kwargs)


# --- Core Engine Tests ---


def test_simulate_no_change() -> None:
    sb = _make_sandbox()
    result = sb.simulate(SimulationRequest(
        simulation_id="sim-1",
        scenario=SimulationScenario.POLICY_CHANGE,
        description="no blocked actions",
        parameters={},
        test_actions=(
            {"action_type": "file_read", "target": "/tmp/a"},
        ),
    ))
    assert result.actions_tested == 1
    assert result.actions_changed == 0
    assert result.newly_blocked == 0
    assert result.summary["impact"] == "none"


def test_simulate_policy_blocks_action() -> None:
    sb = _make_sandbox()
    result = sb.simulate(SimulationRequest(
        simulation_id="sim-2",
        scenario=SimulationScenario.POLICY_CHANGE,
        description="block shell_execute",
        parameters={"blocked_actions": ["shell_execute"]},
        test_actions=(
            {"action_type": "file_read", "target": "/tmp/a"},
            {"action_type": "shell_execute", "target": "rm -rf /"},
        ),
    ))
    assert result.actions_tested == 2
    assert result.newly_blocked == 1
    assert result.summary["impact"] == "high"


def test_simulate_provider_failure() -> None:
    sb = _make_sandbox()
    result = sb.simulate(SimulationRequest(
        simulation_id="sim-3",
        scenario=SimulationScenario.PROVIDER_FAILURE,
        description="all LLM actions fail",
        test_actions=(
            {"action_type": "llm.complete", "target": "model"},
            {"action_type": "file_read", "target": "/tmp/a"},
        ),
    ))
    assert result.newly_blocked == 1  # LLM action blocked
    assert result.actions_changed == 1


def test_simulate_budget_exhaustion() -> None:
    sb = _make_sandbox()
    result = sb.simulate(SimulationRequest(
        simulation_id="sim-4",
        scenario=SimulationScenario.BUDGET_CHANGE,
        description="reduce budget to zero",
        parameters={"new_max_cost": 0, "current_spent": 10},
        test_actions=(
            {"action_type": "llm.complete", "target": "model", "budget_id": "default"},
        ),
    ))
    assert result.newly_blocked == 1


def test_simulate_tenant_disable() -> None:
    sb = _make_sandbox()
    result = sb.simulate(SimulationRequest(
        simulation_id="sim-5",
        scenario=SimulationScenario.TENANT_DISABLE,
        description="disable tenant-1",
        parameters={"tenant_id": "tenant-1"},
        test_actions=(
            {"action_type": "read", "target": "data", "tenant_id": "tenant-1"},
            {"action_type": "read", "target": "data", "tenant_id": "tenant-2"},
        ),
    ))
    assert result.newly_blocked == 1  # Only tenant-1 blocked


def test_history_bounded() -> None:
    sb = _make_sandbox()
    for i in range(30):
        sb.simulate(SimulationRequest(
            simulation_id=f"sim-h{i}",
            scenario=SimulationScenario.CUSTOM,
            description=f"test-{i}",
        ))
    assert len(sb.recent_simulations(limit=10)) == 10


def test_summary() -> None:
    sb = _make_sandbox()
    sb.simulate(SimulationRequest(
        simulation_id="sum-1",
        scenario=SimulationScenario.POLICY_CHANGE,
        description="test",
    ))
    s = sb.summary()
    assert s["total_simulations"] == 1


# --- HTTP Endpoint Tests ---


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_simulate_endpoint(client) -> None:
    resp = client.post("/api/v1/simulate", json={
        "scenario": "policy_change",
        "description": "test simulation",
        "parameters": {"blocked_actions": ["dangerous"]},
        "test_actions": [
            {"action_type": "safe_read", "target": "file"},
            {"action_type": "dangerous", "target": "system"},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert data["newly_blocked"] == 1
    assert data["summary"]["impact"] == "high"


def test_simulation_history_endpoint(client) -> None:
    resp = client.get("/api/v1/simulate/history")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_simulation_summary_endpoint(client) -> None:
    resp = client.get("/api/v1/simulate/summary")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True
