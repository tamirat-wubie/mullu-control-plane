"""Phase 215 — Server endpoint tests for agent chains, monitoring, task queue."""

import pytest
import os

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
    from mcoi_runtime.app.server import app
    return TestClient(app)


class TestChainEndpoints:
    def test_execute_chain(self, client):
        resp = client.post("/api/v1/chain/execute", json={
            "steps": [
                {"step_id": "s1", "name": "A", "prompt_template": "Summarize: {{input}}"},
                {"step_id": "s2", "name": "B", "prompt_template": "Refine: {{prev}}"},
            ],
            "initial_input": "test data",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] is True
        assert len(data["steps"]) == 2
        assert data["governed"] is True

    def test_chain_history(self, client):
        client.post("/api/v1/chain/execute", json={
            "steps": [{"step_id": "s1", "name": "A", "prompt_template": "x"}],
        })
        resp = client.get("/api/v1/chain/history")
        assert resp.json()["summary"]["total"] >= 1


class TestMonitoringEndpoint:
    def test_monitor(self, client):
        resp = client.get("/api/v1/monitor")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "health_score" in data
        assert "circuit_breaker" in data
        assert data["health_score"] >= 0


class TestQueueEndpoints:
    def test_submit(self, client):
        resp = client.post("/api/v1/queue/submit", json={
            "task_id": "q1", "payload": {"data": "test"}, "priority": 5,
        })
        assert resp.status_code == 200
        assert resp.json()["task_id"] == "q1"

    def test_process(self, client):
        client.post("/api/v1/queue/submit", json={"task_id": "q-proc", "payload": {"x": 1}})
        resp = client.post("/api/v1/queue/process")
        assert resp.json()["processed"] is True

    def test_process_empty(self, client):
        # Process all existing tasks first
        while True:
            resp = client.post("/api/v1/queue/process")
            if not resp.json()["processed"]:
                break
        resp = client.post("/api/v1/queue/process")
        assert resp.json()["processed"] is False

    def test_queue_status(self, client):
        resp = client.get("/api/v1/queue/status")
        assert resp.status_code == 200
        assert "depth" in resp.json()

    def test_get_result(self, client):
        client.post("/api/v1/queue/submit", json={"task_id": "q-result", "payload": {}})
        client.post("/api/v1/queue/process")
        resp = client.get("/api/v1/queue/result/q-result")
        assert resp.status_code == 200
        assert resp.json()["succeeded"] is True

    def test_get_missing_result(self, client):
        resp = client.get("/api/v1/queue/result/nonexistent")
        assert resp.status_code == 404
