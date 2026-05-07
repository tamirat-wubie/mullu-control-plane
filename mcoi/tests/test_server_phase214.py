"""Phase 214 — Server endpoint tests for model routing, correlation, shutdown, readiness."""

import pytest
import os
from types import SimpleNamespace

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


class TestAutoRoutedCompletion:
    def test_auto_complete(self, client):
        resp = client.post("/api/v1/complete/auto", json={"prompt": "What is 2+2?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] is True
        assert "routing" in data
        assert data["routing"]["complexity"] in ("simple", "moderate", "complex")
        assert data["governed"] is True

    def test_auto_complex(self, client):
        resp = client.post("/api/v1/complete/auto", json={
            "prompt": "Implement a recursive tree traversal and debug it step by step",
        })
        data = resp.json()
        assert data["routing"]["complexity"] == "complex"

    def test_force_model(self, client):
        resp = client.post("/api/v1/complete/auto", json={
            "prompt": "hello", "force_model": "claude-opus-4-6",
        })
        data = resp.json()
        assert data["model"] == "claude-opus-4-6"

    def test_list_models(self, client):
        resp = client.get("/api/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["models"] >= 4
        ids = [m["id"] for m in data["models"]]
        assert "claude-haiku-4-5" in ids
        assert "claude-opus-4-6" in ids
        assert "gpt-4.1-nano" in ids
        assert "gemini-2.0-flash-lite" in ids
        assert "deepseek-v4-flash" in ids

    def test_auto_complete_exception_is_sanitized(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        def boom(*args, **kwargs):
            raise RuntimeError("auto-route-secret")

        monkeypatch.setattr(deps.llm_bridge, "complete", boom)
        resp = client.post("/api/v1/complete/auto", json={"prompt": "hello"})
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error"] == "LLM service unavailable"
        assert data["error_code"] == "llm_service_unavailable"
        assert "auto-route-secret" not in str(resp.json())

    def test_no_routable_model_returns_structured_error(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        monkeypatch.setattr(deps.model_router, "route", lambda *args, **kwargs: SimpleNamespace(model_id=""))
        resp = client.post("/api/v1/complete/auto", json={"prompt": "hello"})
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error_code"] == "no_routable_model"
        assert data["governed"] is True


class TestCorrelationEndpoint:
    def test_active_correlations(self, client):
        resp = client.get("/api/v1/correlation/active")
        assert resp.status_code == 200
        assert "active" in resp.json()


class TestShutdownEndpoint:
    def test_shutdown_info(self, client):
        resp = client.get("/api/v1/shutdown/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hooks"] >= 3
        assert "save_state" in data["hook_names"]


class TestProductionReadiness:
    def test_readiness(self, client):
        resp = client.get("/api/v1/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["subsystems"] >= 12
        assert data["governed"] is True
        assert all(data["checks"].values())

    def test_readiness_version(self, client):
        resp = client.get("/api/v1/readiness")
        assert resp.json()["version"] >= "1.2.0"


class TestV1_2Integration:
    def test_full_v1_2_flow(self, client):
        """Auto-route → readiness → models → health score."""
        # Auto-routed completion
        resp = client.post("/api/v1/complete/auto", json={"prompt": "test"})
        assert resp.json()["governed"] is True

        # Readiness
        resp = client.get("/api/v1/readiness")
        assert resp.json()["ready"] is True

        # Models
        resp = client.get("/api/v1/models")
        assert resp.json()["summary"]["models"] >= 4

        # Health
        resp = client.get("/api/v1/health/score")
        assert resp.json()["score"] > 0
