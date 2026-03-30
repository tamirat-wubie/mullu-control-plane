"""Purpose: verify operator console dashboard endpoints.
Governance scope: console view tests only.
Dependencies: FastAPI test client, server app.
Invariants: all views return governed responses with structured data.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    return TestClient(app)


def test_console_home(client: TestClient) -> None:
    resp = client.get("/api/v1/console/home")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "active_runs" in data
    assert "blocked_runs" in data
    assert "failed_runs" in data
    assert "llm_invocations" in data
    assert "health_score" in data
    assert "scheduler" in data


def test_console_runs(client: TestClient) -> None:
    resp = client.get("/api/v1/console/runs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "runs" in data
    assert "count" in data
    assert isinstance(data["runs"], list)


def test_console_runs_filtered(client: TestClient) -> None:
    resp = client.get("/api/v1/console/runs?outcome=success&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["filters"]["outcome"] == "success"


def test_console_audit(client: TestClient) -> None:
    resp = client.get("/api/v1/console/audit?limit=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "entries" in data
    assert "aggregations" in data
    assert "by_action" in data["aggregations"]
    assert "by_outcome" in data["aggregations"]
    assert "by_actor" in data["aggregations"]
    assert "chain_intact" in data


def test_console_checkpoints(client: TestClient) -> None:
    resp = client.get("/api/v1/console/checkpoints")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "engine_state" in data
    assert "persisted_checkpoints" in data
    assert "checkpoint_count" in data


def test_console_providers(client: TestClient) -> None:
    resp = client.get("/api/v1/console/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "providers" in data
    assert "circuit_breaker" in data["providers"]
    assert "tenant_count" in data


def test_console_scheduler(client: TestClient) -> None:
    resp = client.get("/api/v1/console/scheduler")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "summary" in data
    assert "jobs" in data
    assert "recent_executions" in data


def test_full_console(client: TestClient) -> None:
    resp = client.get("/api/v1/console")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "home" in data
    assert "checkpoints" in data
    assert "providers" in data
    assert "scheduler" in data
