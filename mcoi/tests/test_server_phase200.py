"""Phase 200 — Server endpoint tests for streaming, daemon, bootstrap."""

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
    os.environ["MULLU_CERT_ENABLED"] = "true"
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.server import app
    return TestClient(app)


class TestStreamingEndpoint:
    def test_stream_returns_sse(self, client):
        resp = client.post("/api/v1/stream", json={"prompt": "test streaming"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "event: meta" in body
        assert "event: token" in body
        assert "event: done" in body

    def test_stream_contains_content(self, client):
        resp = client.post("/api/v1/stream", json={"prompt": "hello"})
        body = resp.text
        assert "event: done" in body
        assert '"governed": true' in body

    def test_stream_with_system(self, client):
        resp = client.post("/api/v1/stream", json={
            "prompt": "hello", "system": "you are helpful"
        })
        assert resp.status_code == 200
        assert "event: done" in resp.text

    def test_stream_exception_is_sanitized(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        def boom(*args, **kwargs):
            raise RuntimeError("stream-backend-secret")

        monkeypatch.setattr(deps.llm_bridge, "complete", boom)
        resp = client.post("/api/v1/stream", json={"prompt": "explode"})
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error"] == "LLM service unavailable"
        assert data["error_code"] == "llm_service_unavailable"
        assert "stream-backend-secret" not in str(resp.json())


class TestDaemonEndpoints:
    def test_daemon_status(self, client):
        resp = client.get("/api/v1/daemon/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "health_score" in data
        assert "is_healthy" in data
        assert "total_runs" in data

    def test_daemon_tick(self, client):
        resp = client.post("/api/v1/daemon/tick")
        assert resp.status_code == 200
        data = resp.json()
        assert "ran" in data
        if data["ran"]:
            assert "chain_id" in data
            assert "all_passed" in data

    def test_daemon_force(self, client):
        resp = client.post("/api/v1/daemon/force")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ran"] is True
        assert data["all_passed"] is True
        assert "chain_hash" in data

    def test_daemon_status_after_run(self, client):
        client.post("/api/v1/daemon/force")
        resp = client.get("/api/v1/daemon/status")
        data = resp.json()
        assert data["total_runs"] >= 1
        assert data["last_status"] == "passed"


class TestBootstrapEndpoint:
    def test_bootstrap_info(self, client):
        resp = client.get("/api/v1/bootstrap")
        assert resp.status_code == 200
        data = resp.json()
        assert "default_backend" in data
        assert "available_backends" in data
        assert "stub" in data["available_backends"]
        assert "config" in data
        assert data["config"]["default_model"]

    def test_bootstrap_has_stub(self, client):
        resp = client.get("/api/v1/bootstrap")
        data = resp.json()
        assert "stub" in data["available_backends"]


class TestDockerCompose:
    def test_compose_file_exists(self):
        # Check relative to various locations
        paths = [
            "docker-compose.yml",
            "../docker-compose.yml",
            "../../docker-compose.yml",
        ]
        found = any(os.path.exists(p) for p in paths)
        assert found, "docker-compose.yml not found"
