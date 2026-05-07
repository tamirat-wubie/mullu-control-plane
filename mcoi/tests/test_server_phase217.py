"""Phase 217 — Governed endpoint detail hardening for router error surfaces."""

import os

import pytest

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.fixture
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.server import app

    return TestClient(app)


class TestConnectorErrorContracts:
    def test_invalid_connector_type_is_bounded(self, client):
        resp = client.post(
            "/api/v1/connectors/register",
            json={"connector_id": "bad", "name": "Bad", "connector_type": "wild.invalid"},
        )
        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "invalid connector type"
        assert data["error_code"] == "invalid_connector_type"
        assert data["governed"] is True
        assert "wild.invalid" not in str(resp.json())


class TestMultiAgentErrorContracts:
    def test_invalid_resolution_status_is_bounded(self, client):
        resp = client.post(
            "/api/v1/multi-agent/delegate/resolve",
            json={"delegation_id": "del-1", "status": "not-a-status", "reason": "x"},
        )
        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "invalid status"
        assert data["error_code"] == "invalid_status"
        assert data["governed"] is True
        assert "not-a-status" not in str(resp.json())

    def test_missing_delegation_resolution_has_bounded_failure_class(self, client):
        resp = client.post(
            "/api/v1/multi-agent/delegate/resolve",
            json={
                "delegation_id": "secret-missing-delegation",
                "status": "accepted",
                "reason": "x",
            },
        )
        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "resolution failed"
        assert data["error_code"] == "resolution_error"
        assert data["failure_class"] == "RuntimeCoreInvariantError"
        assert data["governed"] is True
        assert "secret-missing-delegation" not in str(resp.json())

    def test_invalid_merge_outcome_is_bounded(self, client):
        resp = client.post(
            "/api/v1/multi-agent/merge",
            json={
                "merge_id": "mg-1",
                "goal_id": "goal-1",
                "source_ids": ["a", "b"],
                "outcome": "not-an-outcome",
                "reason": "x",
            },
        )
        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "invalid outcome"
        assert data["error_code"] == "invalid_outcome"
        assert data["governed"] is True
        assert "not-an-outcome" not in str(resp.json())

    def test_invalid_conflict_strategy_is_bounded(self, client):
        resp = client.post(
            "/api/v1/multi-agent/conflict",
            json={
                "conflict_id": "cf-1",
                "goal_id": "goal-1",
                "conflicting_ids": ["a", "b"],
                "strategy": "not-a-strategy",
            },
        )
        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "invalid strategy"
        assert data["error_code"] == "invalid_strategy"
        assert data["governed"] is True
        assert "not-a-strategy" not in str(resp.json())


class TestSchedulerErrorContracts:
    def test_invalid_schedule_type_is_bounded(self, client):
        resp = client.post(
            "/api/v1/scheduler/jobs",
            json={"job_id": "bad", "name": "Bad", "schedule_type": "wild.invalid"},
        )
        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "invalid schedule type"
        assert data["error_code"] == "invalid_schedule_type"
        assert data["governed"] is True
        assert "wild.invalid" not in str(resp.json())

    def test_missing_job_is_bounded(self, client):
        resp = client.post("/api/v1/scheduler/execute", json={"job_id": "job-missing-123"})
        assert resp.status_code == 404
        data = resp.json()["detail"]
        assert data["error"] == "job not found"
        assert data["error_code"] == "job_not_found"
        assert data["governed"] is True
        assert "job-missing-123" not in str(resp.json())


class TestCheckpointErrorContracts:
    def test_agent_restore_missing_checkpoint_is_bounded(self, client):
        resp = client.post("/api/v1/agent/restore", json={"checkpoint_id": "cp-missing-123"})
        assert resp.status_code == 404
        data = resp.json()["detail"]
        assert data["error"] == "checkpoint not found"
        assert data["error_code"] == "checkpoint_not_found"
        assert data["governed"] is True
        assert "cp-missing-123" not in str(resp.json())

    def test_coordination_restore_missing_checkpoint_is_bounded(self, client):
        resp = client.post("/api/v1/coordination/restore", json={"checkpoint_id": "cp-missing-456"})
        assert resp.status_code == 404
        data = resp.json()["detail"]
        assert data["error"] == "checkpoint not found"
        assert data["error_code"] == "checkpoint_not_found"
        assert data["governed"] is True
        assert "cp-missing-456" not in str(resp.json())
