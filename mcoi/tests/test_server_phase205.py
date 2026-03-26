"""Phase 205A — Server endpoint tests for workflow, agents, webhooks, health, config, dashboard, plugins."""

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
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.server import app
    return TestClient(app)


class TestWorkflowEndpoints:
    def test_execute_workflow(self, client):
        resp = client.post("/api/v1/workflow/execute", json={
            "task_id": "wf-test-1", "description": "test prompt",
            "capability": "llm.completion", "tenant_id": "t1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["agent_id"] == "llm-agent"
        assert len(data["steps"]) >= 4

    def test_execute_workflow_bad_capability(self, client):
        resp = client.post("/api/v1/workflow/execute", json={
            "task_id": "wf-bad", "description": "test",
            "capability": "nonexistent",
        })
        assert resp.status_code == 400

    def test_workflow_history(self, client):
        client.post("/api/v1/workflow/execute", json={
            "task_id": "wf-h1", "description": "a", "capability": "llm.completion",
        })
        resp = client.get("/api/v1/workflow/history")
        assert resp.status_code == 200
        assert resp.json()["summary"]["total"] >= 1


class TestAgentEndpoints:
    def test_list_agents(self, client):
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2
        assert any(a["id"] == "llm-agent" for a in data["agents"])

    def test_agent_tasks(self, client):
        resp = client.get("/api/v1/agents/llm-agent/tasks")
        assert resp.status_code == 200


class TestWebhookEndpoints:
    def test_subscribe(self, client):
        resp = client.post("/api/v1/webhooks/subscribe", json={
            "subscription_id": "sub-test", "tenant_id": "t1",
            "url": "https://example.com/hook", "events": ["task.completed"],
        })
        assert resp.status_code == 200
        assert resp.json()["subscription_id"] == "sub-test"

    def test_list_webhooks(self, client):
        client.post("/api/v1/webhooks/subscribe", json={
            "subscription_id": "sub-list", "tenant_id": "t1",
            "url": "http://x", "events": ["task.completed"],
        })
        resp = client.get("/api/v1/webhooks")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_webhook_deliveries(self, client):
        resp = client.get("/api/v1/webhooks/deliveries")
        assert resp.status_code == 200


class TestDeepHealthEndpoint:
    def test_deep_health(self, client):
        resp = client.get("/api/v1/health/deep")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall"] == "healthy"
        assert len(data["components"]) >= 3


class TestConfigEndpoints:
    def test_get_config(self, client):
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] >= 1
        assert "llm" in data["config"]

    def test_config_history(self, client):
        resp = client.get("/api/v1/config/history")
        assert resp.status_code == 200
        assert len(resp.json()["versions"]) >= 1


class TestDashboardEndpoint:
    def test_dashboard(self, client):
        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "health" in data
        assert "llm" in data
        assert "source_count" in data


class TestPluginEndpoints:
    def test_list_plugins(self, client):
        resp = client.get("/api/v1/plugins")
        assert resp.status_code == 200
        data = resp.json()
        assert "plugins" in data
        assert "summary" in data
