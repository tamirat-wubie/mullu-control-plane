"""Purpose: verify multi-agent live runtime HTTP endpoints.
Governance scope: multi-agent coordination endpoint tests only.
Dependencies: FastAPI test client, server app, coordination engine.
Invariants: delegations tracked; handoffs preserve context; conflicts recorded.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    return TestClient(app)


def test_delegate_work(client: TestClient) -> None:
    resp = client.post("/api/v1/multi-agent/delegate", json={
        "delegation_id": "del-http-1",
        "delegator_id": "agent-a",
        "delegate_id": "agent-b",
        "goal_id": "goal-1",
        "action_scope": "analyze",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["delegation_id"] == "del-http-1"
    assert data["governed"] is True


def test_resolve_delegation(client: TestClient) -> None:
    client.post("/api/v1/multi-agent/delegate", json={
        "delegation_id": "del-resolve-1",
        "delegator_id": "agent-a",
        "delegate_id": "agent-b",
        "goal_id": "goal-1",
        "action_scope": "execute",
    })
    resp = client.post("/api/v1/multi-agent/delegate/resolve", json={
        "delegation_id": "del-resolve-1",
        "status": "accepted",
        "reason": "ready to proceed",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_record_handoff(client: TestClient) -> None:
    resp = client.post("/api/v1/multi-agent/handoff", json={
        "handoff_id": "ho-http-1",
        "from_party": "agent-a",
        "to_party": "agent-c",
        "goal_id": "goal-2",
        "context_ids": ["ctx-1", "ctx-2"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["handoff_id"] == "ho-http-1"
    assert data["governed"] is True


def test_record_merge(client: TestClient) -> None:
    resp = client.post("/api/v1/multi-agent/merge", json={
        "merge_id": "mg-http-1",
        "goal_id": "goal-3",
        "source_ids": ["src-1", "src-2"],
        "outcome": "merged",
        "reason": "results consistent",
    })
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "merged"


def test_record_conflict(client: TestClient) -> None:
    resp = client.post("/api/v1/multi-agent/conflict", json={
        "conflict_id": "cf-http-1",
        "goal_id": "goal-4",
        "conflicting_ids": ["a", "b"],
        "strategy": "escalate",
    })
    assert resp.status_code == 200
    assert resp.json()["strategy"] == "escalate"


def test_unresolved_conflicts(client: TestClient) -> None:
    resp = client.get("/api/v1/multi-agent/conflicts/unresolved")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_multi_agent_summary(client: TestClient) -> None:
    resp = client.get("/api/v1/multi-agent/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "delegations" in data
    assert "handoffs" in data
    assert data["governed"] is True


def test_full_cooperation_flow(client: TestClient) -> None:
    """End-to-end: delegate → resolve → handoff → merge."""
    # Delegate
    client.post("/api/v1/multi-agent/delegate", json={
        "delegation_id": "del-e2e",
        "delegator_id": "lead",
        "delegate_id": "worker",
        "goal_id": "goal-e2e",
        "action_scope": "full_analysis",
    })
    # Resolve
    client.post("/api/v1/multi-agent/delegate/resolve", json={
        "delegation_id": "del-e2e",
        "status": "accepted",
        "reason": "on it",
    })
    # Handoff
    client.post("/api/v1/multi-agent/handoff", json={
        "handoff_id": "ho-e2e",
        "from_party": "worker",
        "to_party": "reviewer",
        "goal_id": "goal-e2e",
        "context_ids": ["result-1"],
    })
    # Merge
    resp = client.post("/api/v1/multi-agent/merge", json={
        "merge_id": "mg-e2e",
        "goal_id": "goal-e2e",
        "source_ids": ["result-1", "result-2"],
        "outcome": "merged",
        "reason": "all good",
    })
    assert resp.status_code == 200
    assert resp.json()["governed"] is True
