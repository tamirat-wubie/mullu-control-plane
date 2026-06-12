"""Purpose: verify explanation engine and HTTP endpoints.
Governance scope: explanation tests only.
Dependencies: explanation_engine module, FastAPI test client.
Invariants: explanations are deterministic; never modify state.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.core.explanation_engine import ExplanationEngine


_CLOCK = "2026-03-30T00:00:00+00:00"


def _make_engine(**kwargs) -> ExplanationEngine:
    return ExplanationEngine(clock=lambda: _CLOCK, **kwargs)


# --- Core Tests ---


def test_explain_action_no_guard_chain() -> None:
    engine = _make_engine()
    exp = engine.explain_action("file_read", "/tmp/a")
    assert exp.decision == "allowed"
    assert "No guard chain" in exp.reasons[0]


def test_explain_action_returns_explanation_id() -> None:
    engine = _make_engine()
    exp = engine.explain_action("shell", "ls")
    assert exp.explanation_id.startswith("exp-")


def test_explain_audit_entry_success() -> None:
    @dataclass
    class FakeEntry:
        action: str = "file_read"
        actor_id: str = "agent-1"
        target: str = "/tmp/a"
        outcome: str = "success"
        detail: dict = None
        recorded_at: str = _CLOCK
        def __post_init__(self):
            self.detail = self.detail or {}

    engine = _make_engine()
    exp = engine.explain_audit_entry(FakeEntry())
    assert exp.decision == "allowed"
    assert "successfully" in exp.reasons[0]


def test_explain_audit_entry_denied() -> None:
    @dataclass
    class FakeEntry:
        action: str = "dangerous"
        actor_id: str = "agent-1"
        target: str = "system"
        outcome: str = "denied"
        detail: dict = None
        recorded_at: str = _CLOCK
        def __post_init__(self):
            self.detail = self.detail or {"guard": "budget", "reason": "exhausted"}

    engine = _make_engine()
    exp = engine.explain_audit_entry(FakeEntry())
    assert exp.decision == "denied"
    assert "budget" in exp.reasons[0]


def test_explain_audit_entry_with_goal_hierarchy() -> None:
    @dataclass
    class FakeEntry:
        action: str = "analyze"
        actor_id: str = "agent-1"
        target: str = "data"
        outcome: str = "success"
        detail: dict = None
        recorded_at: str = _CLOCK
        def __post_init__(self):
            self.detail = self.detail or {"mission_id": "m-1", "goal_id": "g-1"}

    engine = _make_engine()
    exp = engine.explain_audit_entry(FakeEntry())
    assert "mission" in " ".join(exp.reasons).lower()
    assert exp.policy_context.get("mission_id") == "m-1"


def test_cache_bounded() -> None:
    engine = _make_engine()
    for i in range(100):
        engine.explain_action("test", f"target-{i}")
    assert engine.summary()["total_explanations"] == 100


def test_summary() -> None:
    engine = _make_engine()
    engine.explain_action("test", "a")
    s = engine.summary()
    assert s["total_explanations"] == 1
    assert s["cached"] == 1


# --- HTTP Tests ---


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_explain_action_endpoint(client) -> None:
    resp = client.post("/api/v1/explain/action", json={
        "action_type": "file_read",
        "target": "/tmp/test",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "decision" in data
    assert "reasons" in data
    assert "guard_chain_path" in data


def test_explain_audit_endpoint_governed_and_missing_entry(client) -> None:
    from mcoi_runtime.app.routers.deps import deps

    deps.audit_trail.record(
        action="explain.audit.test",
        actor_id="agent-explain-test",
        tenant_id="tenant-explain-test",
        target="audit-entry",
        outcome="success",
        detail={"mission_id": "mission-explain-test", "goal_id": "goal-explain-test"},
    )

    response = client.get("/api/v1/explain/audit/0")
    missing = client.get("/api/v1/explain/audit/499")
    body = response.json()
    missing_body = missing.json()

    assert response.status_code == 200
    assert body["governed"] is True
    assert body["decision"] == "allowed"
    assert body["action"]
    assert "policy_context" in body
    assert missing.status_code == 404
    assert missing_body["detail"]["governed"] is True


@pytest.mark.parametrize("entry_index", ["-1", "500", "999999", "not-an-index"])
def test_explain_audit_endpoint_invalid_index_returns_bounded_422(client, entry_index) -> None:
    resp = client.get(f"/api/v1/explain/audit/{entry_index}")
    detail = resp.json()["detail"]

    assert resp.status_code == 422
    assert detail["error"] == "invalid explain audit request"
    assert detail["error_code"] == "explain_audit_invalid_request"
    assert detail["governed"] is True


def test_explain_summary_endpoint(client) -> None:
    resp = client.get("/api/v1/explain/summary")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True
