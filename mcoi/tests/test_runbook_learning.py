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
    RunbookLearningEngine,
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
    with pytest.raises(ValueError, match="approved"):
        engine.activate(runbook.runbook_id)


def test_retire_runbook() -> None:
    engine = _make_engine()
    patterns = engine.analyze(_make_entries())
    runbook = engine.promote(patterns[0].pattern_id, "Test")
    engine.approve(runbook.runbook_id, "op")
    engine.activate(runbook.runbook_id)
    retired = engine.retire(runbook.runbook_id)
    assert retired.status == RunbookStatus.RETIRED


def test_promote_unknown_pattern_raises() -> None:
    engine = _make_engine()
    with pytest.raises(ValueError, match="pattern not found"):
        engine.promote("nonexistent", "Test")


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
