"""Phase 206 — Server endpoint tests for event bus, pipeline, plugins, snapshot."""

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


class TestEventBusEndpoints:
    def test_publish_event(self, client):
        resp = client.post("/api/v1/events/publish", json={
            "event_type": "test.event", "tenant_id": "t1",
            "source": "test", "payload": {"key": "value"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "test.event"
        assert data["hash"]

    def test_list_events(self, client):
        client.post("/api/v1/events/publish", json={"event_type": "a"})
        client.post("/api/v1/events/publish", json={"event_type": "b"})
        resp = client.get("/api/v1/events")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 2

    def test_filter_events_by_type(self, client):
        client.post("/api/v1/events/publish", json={"event_type": "x.test"})
        client.post("/api/v1/events/publish", json={"event_type": "y.test"})
        resp = client.get("/api/v1/events", params={"event_type": "x.test"})
        data = resp.json()
        assert all(e["type"] == "x.test" for e in data["events"])

    def test_events_summary(self, client):
        client.post("/api/v1/events/publish", json={"event_type": "summary.test"})
        resp = client.get("/api/v1/events/summary")
        assert resp.status_code == 200
        assert "total_events" in resp.json()


class TestPipelineEndpoints:
    def test_execute_pipeline(self, client):
        resp = client.post("/api/v1/pipeline/execute", json={
            "steps": [
                {"step_id": "s1", "name": "Summarize", "prompt_template": "Summarize: {input}"},
                {"step_id": "s2", "name": "Refine", "prompt_template": "Refine: {input}"},
            ],
            "initial_input": "some text",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] is True
        assert len(data["steps"]) == 2
        assert data["final_output"]

    def test_single_step_pipeline(self, client):
        resp = client.post("/api/v1/pipeline/execute", json={
            "steps": [{"step_id": "s1", "name": "Test", "prompt_template": "Hello {input}"}],
            "initial_input": "world",
        })
        assert resp.json()["succeeded"] is True

    def test_pipeline_emits_event(self, client):
        client.post("/api/v1/pipeline/execute", json={
            "steps": [{"step_id": "s1", "name": "Test", "prompt_template": "test"}],
        })
        resp = client.get("/api/v1/events", params={"event_type": "pipeline.completed"})
        assert resp.json()["count"] >= 1

    def test_pipeline_history(self, client):
        client.post("/api/v1/pipeline/execute", json={
            "steps": [{"step_id": "s1", "name": "A", "prompt_template": "x"}],
        })
        resp = client.get("/api/v1/pipeline/history")
        assert resp.status_code == 200
        assert resp.json()["summary"]["total"] >= 1

    def test_empty_pipeline(self, client):
        resp = client.post("/api/v1/pipeline/execute", json={"steps": []})
        assert resp.json()["succeeded"] is True


class TestPluginEndpointsPhase206:
    def test_plugins_include_examples(self, client):
        resp = client.get("/api/v1/plugins")
        assert resp.status_code == 200
        plugins = resp.json()["plugins"]
        ids = [p["id"] for p in plugins]
        assert "logging" in ids
        assert "cost-alert" in ids

    def test_logging_plugin_active(self, client):
        resp = client.get("/api/v1/plugins")
        plugins = {p["id"]: p for p in resp.json()["plugins"]}
        assert plugins["logging"]["status"] == "active"
        assert plugins["cost-alert"]["status"] == "active"


class TestSystemSnapshot:
    def test_snapshot(self, client):
        resp = client.get("/api/v1/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.6.0"
        assert "store" in data
        assert "llm" in data
        assert "certification" in data
        assert "tenants" in data
        assert "agents" in data
        assert "workflows" in data
        assert "pipelines" in data
        assert "metrics" in data
        assert "audit" in data
        assert "events" in data
        assert "webhooks" in data
        assert "config" in data
        assert "plugins" in data
        assert "rate_limiter" in data
        assert "captured_at" in data

    def test_snapshot_after_operations(self, client):
        # Do some work
        client.post("/api/v1/workflow/execute", json={
            "task_id": "snap-wf", "description": "test",
            "capability": "llm.completion",
        })
        client.post("/api/v1/pipeline/execute", json={
            "steps": [{"step_id": "s1", "name": "A", "prompt_template": "x"}],
        })
        resp = client.get("/api/v1/snapshot")
        data = resp.json()
        assert data["workflows"]["total"] >= 1
        assert data["pipelines"]["total"] >= 1

    def test_deep_health_includes_event_bus(self, client):
        resp = client.get("/api/v1/health/deep")
        data = resp.json()
        component_names = [c["name"] for c in data["components"]]
        assert "event_bus" in component_names

    def test_dashboard_includes_event_bus_and_pipelines(self, client):
        resp = client.get("/api/v1/dashboard")
        data = resp.json()
        assert "event_bus" in data
        assert "pipelines" in data
