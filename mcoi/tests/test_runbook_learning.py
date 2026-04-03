"""Purpose: verify runbook learning engine and HTTP endpoints.
Governance scope: runbook learning tests only.
Dependencies: runbook_learning module, FastAPI test client.
Invariants: patterns from real data; promotion requires approval; versioned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from mcoi_runtime.core.runbook_learning import (
    PatternNotFoundError,
    RunbookLearningEngine,
    RunbookApprovalRequiredError,
    RunbookRetirementStateError,
    RunbookStatus,
)


_CLOCK = "2026-03-30T00:00:00+00:00"


@dataclass
class FakeAuditEntry:
    actor_id: str
    action: str
    outcome: str
    target: str = ""
    tenant_id: str = ""
    recorded_at: str = _CLOCK


def _make_engine() -> RunbookLearningEngine:
    return RunbookLearningEngine(clock=lambda: _CLOCK)


def _make_entries() -> list[FakeAuditEntry]:
    """Create repeated successful action sequences."""
    entries = []
    for _ in range(5):
        entries.append(FakeAuditEntry("agent-1", "file_read", "success", "/tmp/a", "t1"))
        entries.append(FakeAuditEntry("agent-1", "analyze", "success", "dataset", "t1"))
        entries.append(FakeAuditEntry("agent-1", "report", "success", "output", "t1"))
    return entries


# --- Core Engine Tests ---


def test_analyze_detects_patterns() -> None:
    engine = _make_engine()
    entries = _make_entries()
    patterns = engine.analyze(entries)
    assert len(patterns) > 0
    assert all(p.occurrence_count >= 3 for p in patterns)
    assert all(p.success_rate >= 0.8 for p in patterns)


def test_promote_creates_candidate() -> None:
    engine = _make_engine()
    patterns = engine.analyze(_make_entries())
    assert len(patterns) > 0
    runbook = engine.promote(patterns[0].pattern_id, "Read-Analyze-Report")
    assert runbook.status == RunbookStatus.CANDIDATE
    assert runbook.name == "Read-Analyze-Report"


def test_approve_requires_candidate() -> None:
    engine = _make_engine()
    patterns = engine.analyze(_make_entries())
    runbook = engine.promote(patterns[0].pattern_id, "Test")
    approved = engine.approve(runbook.runbook_id, "operator-1")
    assert approved.status == RunbookStatus.APPROVED
    assert approved.approved_by == "operator-1"


def test_activate_requires_approved() -> None:
    engine = _make_engine()
    patterns = engine.analyze(_make_entries())
    runbook = engine.promote(patterns[0].pattern_id, "Test")
    engine.approve(runbook.runbook_id, "op")
    activated = engine.activate(runbook.runbook_id)
    assert activated.status == RunbookStatus.ACTIVE


def test_cannot_activate_candidate() -> None:
    engine = _make_engine()
    patterns = engine.analyze(_make_entries())
    runbook = engine.promote(patterns[0].pattern_id, "Test")
    with pytest.raises(RunbookApprovalRequiredError) as excinfo:
        engine.activate(runbook.runbook_id)
    assert excinfo.value.runbook_id == runbook.runbook_id
    assert excinfo.value.current_status == RunbookStatus.CANDIDATE


def test_retire_runbook() -> None:
    engine = _make_engine()
    patterns = engine.analyze(_make_entries())
    runbook = engine.promote(patterns[0].pattern_id, "Test")
    engine.approve(runbook.runbook_id, "op")
    engine.activate(runbook.runbook_id)
    retired = engine.retire(runbook.runbook_id)
    assert retired.status == RunbookStatus.RETIRED


def test_cannot_retire_non_active_runbook() -> None:
    engine = _make_engine()
    patterns = engine.analyze(_make_entries())
    runbook = engine.promote(patterns[0].pattern_id, "Test")
    with pytest.raises(RunbookRetirementStateError) as excinfo:
        engine.retire(runbook.runbook_id)
    assert excinfo.value.runbook_id == runbook.runbook_id
    assert excinfo.value.current_status == RunbookStatus.CANDIDATE


def test_cannot_retire_already_retired_runbook() -> None:
    engine = _make_engine()
    patterns = engine.analyze(_make_entries())
    runbook = engine.promote(patterns[0].pattern_id, "Test")
    engine.approve(runbook.runbook_id, "op")
    engine.activate(runbook.runbook_id)
    engine.retire(runbook.runbook_id)
    with pytest.raises(RunbookRetirementStateError) as excinfo:
        engine.retire(runbook.runbook_id)
    assert excinfo.value.runbook_id == runbook.runbook_id
    assert excinfo.value.current_status == RunbookStatus.RETIRED


def test_promote_unknown_pattern_raises() -> None:
    engine = _make_engine()
    with pytest.raises(PatternNotFoundError) as excinfo:
        engine.promote("nonexistent", "Test")
    assert excinfo.value.pattern_id == "nonexistent"


def test_summary() -> None:
    engine = _make_engine()
    patterns = engine.analyze(_make_entries())
    engine.promote(patterns[0].pattern_id, "Test")
    s = engine.summary()
    assert s["patterns_detected"] > 0
    assert s["candidates"] == 1


# --- HTTP Endpoint Tests ---


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_analyze_endpoint(client) -> None:
    # Seed some audit data
    client.post("/api/v1/agent/register", json={"agent_name": "rb-agent"})
    resp = client.post("/api/v1/runbooks/analyze?limit=200")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_list_runbooks_endpoint(client) -> None:
    resp = client.get("/api/v1/runbooks")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_runbooks_summary_endpoint(client) -> None:
    resp = client.get("/api/v1/runbooks/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "patterns_detected" in data
    assert data["governed"] is True


def test_promote_endpoint_sanitizes_unknown_pattern(client) -> None:
    resp = client.post("/api/v1/runbooks/promote", json={
        "pattern_id": "pat-secret-do-not-echo",
        "name": "Secret Pattern",
    })
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "pattern not found"
    assert resp.json()["detail"]["error_code"] == "pattern_not_found"
    assert "pat-secret-do-not-echo" not in str(resp.json())


def test_approve_endpoint_sanitizes_unknown_runbook(client) -> None:
    resp = client.post("/api/v1/runbooks/approve", json={
        "runbook_id": "rb-secret-do-not-echo",
        "approved_by": "operator-1",
    })
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "runbook not found"
    assert resp.json()["detail"]["error_code"] == "runbook_not_found"
    assert "rb-secret-do-not-echo" not in str(resp.json())


def test_activate_endpoint_sanitizes_unknown_runbook(client) -> None:
    resp = client.post("/api/v1/runbooks/rb-secret-activate/activate")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "runbook not found"
    assert resp.json()["detail"]["error_code"] == "runbook_not_found"
    assert "rb-secret-activate" not in str(resp.json())


def test_list_runbooks_invalid_status_fails_closed(client) -> None:
    resp = client.get("/api/v1/runbooks?status=definitely-not-valid")
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid runbook status"
    assert resp.json()["detail"]["error_code"] == "invalid_status"


def test_retire_endpoint_rejects_non_active_runbook(client) -> None:
    from mcoi_runtime.app.routers.deps import deps

    pattern = deps.runbook_learning.analyze(_make_entries())[0]
    runbook = deps.runbook_learning.promote(pattern.pattern_id, "Retire Candidate")

    resp = client.post(f"/api/v1/runbooks/{runbook.runbook_id}/retire")

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "runbook must be active before retirement"
    assert resp.json()["detail"]["error_code"] == "invalid_runbook_state"
    assert runbook.runbook_id not in str(resp.json())
