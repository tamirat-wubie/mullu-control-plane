"""Purpose: verify agent adapter protocol HTTP endpoints.
Governance scope: adapter protocol integration tests only.
Dependencies: FastAPI test client, server app.
Invariants: agents register, actions are governed, audit trail records everything.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    return TestClient(app)


# --- Agent Registration ---


def test_register_agent(client: TestClient) -> None:
    resp = client.post("/api/v1/agent/register", json={
        "agent_name": "test-agent",
        "capabilities": ["file_read", "shell_execute"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "agent_id" in data
    assert data["agent_name"] == "test-agent"
    assert data["status"] == "registered"


# --- Heartbeat ---


def test_heartbeat_registered_agent(client: TestClient) -> None:
    reg = client.post("/api/v1/agent/register", json={"agent_name": "hb-agent"}).json()
    resp = client.post("/api/v1/agent/heartbeat", json={
        "agent_id": reg["agent_id"],
        "status": "healthy",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_heartbeat_unknown_agent_404(client: TestClient) -> None:
    resp = client.post("/api/v1/agent/heartbeat", json={
        "agent_id": "nonexistent",
        "status": "healthy",
    })
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_code"] == "agent_not_found"


# --- Action Request ---


def test_action_request_allowed(client: TestClient) -> None:
    reg = client.post("/api/v1/agent/register", json={"agent_name": "action-agent"}).json()
    resp = client.post("/api/v1/agent/action-request", json={
        "agent_id": reg["agent_id"],
        "action_type": "file_read",
        "target": "/tmp/safe.txt",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert data["decision"] == "allow"
    assert "action_id" in data


def test_action_request_unknown_agent_404(client: TestClient) -> None:
    resp = client.post("/api/v1/agent/action-request", json={
        "agent_id": "nonexistent",
        "action_type": "shell",
        "target": "ls",
    })
    assert resp.status_code == 404


# --- Action Result ---


def test_action_result_submitted(client: TestClient) -> None:
    reg = client.post("/api/v1/agent/register", json={"agent_name": "result-agent"}).json()
    action = client.post("/api/v1/agent/action-request", json={
        "agent_id": reg["agent_id"],
        "action_type": "file_read",
        "target": "/tmp/test.txt",
    }).json()

    resp = client.post("/api/v1/agent/action-result", json={
        "agent_id": reg["agent_id"],
        "action_id": action["action_id"],
        "outcome": "success",
        "result": {"content": "file contents"},
    })
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "success"


def test_action_result_unknown_action_404(client: TestClient) -> None:
    resp = client.post("/api/v1/agent/action-result", json={
        "agent_id": "any",
        "action_id": "nonexistent",
        "outcome": "success",
        "result": {},
    })
    assert resp.status_code == 404


# --- Adapter Summary ---


def test_adapter_summary(client: TestClient) -> None:
    resp = client.get("/api/v1/agent/adapter/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "registered_agents" in data
    assert "total_actions" in data
    assert data["governed"] is True


# --- Full Flow ---


def test_full_governed_flow(client: TestClient) -> None:
    """End-to-end: register → heartbeat → action-request → action-result."""
    # Register
    reg = client.post("/api/v1/agent/register", json={
        "agent_name": "e2e-agent",
        "capabilities": ["analyze"],
    }).json()
    agent_id = reg["agent_id"]

    # Heartbeat
    hb = client.post("/api/v1/agent/heartbeat", json={
        "agent_id": agent_id, "status": "healthy",
    }).json()
    assert hb["status"] == "healthy"

    # Request action
    action = client.post("/api/v1/agent/action-request", json={
        "agent_id": agent_id,
        "action_type": "analyze",
        "target": "dataset-1",
        "tenant_id": "tenant-1",
    }).json()
    assert action["decision"] == "allow"

    # Submit result
    result = client.post("/api/v1/agent/action-result", json={
        "agent_id": agent_id,
        "action_id": action["action_id"],
        "outcome": "success",
        "result": {"analysis": "complete"},
    }).json()
    assert result["outcome"] == "success"
    assert result["governed"] is True


# --- Goal Hierarchy ---


def test_action_request_propagates_goal_hierarchy(client: TestClient) -> None:
    """mission_id and goal_id propagate through action-request response and audit."""
    reg = client.post("/api/v1/agent/register", json={"agent_name": "goal-agent"}).json()
    resp = client.post("/api/v1/agent/action-request", json={
        "agent_id": reg["agent_id"],
        "action_type": "analyze",
        "target": "report-q4",
        "mission_id": "mission-001",
        "goal_id": "goal-042",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "allow"
    assert data["mission_id"] == "mission-001"
    assert data["goal_id"] == "goal-042"
