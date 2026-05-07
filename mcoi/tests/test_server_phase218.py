"""Phase 218 — Governed connector and scheduler execution error contracts."""

import os
from types import SimpleNamespace

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


def test_connector_invoke_guard_denial_is_bounded(client, monkeypatch):
    from mcoi_runtime.app.routers.deps import deps

    class GuardChain:
        def evaluate(self, ctx):
            return SimpleNamespace(allowed=False, reason="tenant t1 denied by confidential policy")

    deps.connector_framework._guard_chain = GuardChain()
    client.post(
        "/api/v1/connectors/register",
        json={"connector_id": "guarded-http", "name": "Guarded", "connector_type": "http_api"},
    )
    resp = client.post(
        "/api/v1/connectors/invoke",
        json={"connector_id": "guarded-http", "action": "fetch", "payload": {"x": 1}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "denied"
    assert data["error"] == "connector access denied"
    assert "tenant t1" not in str(data)
    assert "confidential policy" not in str(data)


def test_scheduler_execute_missing_handler_is_bounded(client):
    client.post(
        "/api/v1/scheduler/jobs",
        json={
            "job_id": "missing-handler-job",
            "name": "Missing Handler",
            "schedule_type": "once",
            "handler_name": "secret-handler",
        },
    )
    resp = client.post("/api/v1/scheduler/execute", json={"job_id": "missing-handler-job"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["error"] == "handler not found"
    assert "secret-handler" not in str(data)


def test_scheduler_execute_guard_denial_is_bounded(client):
    from mcoi_runtime.app.routers.deps import deps

    class GuardChain:
        def evaluate(self, ctx):
            return SimpleNamespace(allowed=False, reason="budget b1 denied for tenant t1")

    deps.scheduler._guard_chain = GuardChain()
    client.post(
        "/api/v1/scheduler/jobs",
        json={
            "job_id": "guarded-job",
            "name": "Guarded Job",
            "schedule_type": "once",
            "handler_name": "noop",
        },
    )
    resp = client.post("/api/v1/scheduler/execute", json={"job_id": "guarded-job"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["error"] == "job execution denied"
    assert "budget b1" not in str(data)
    assert "tenant t1" not in str(data)
