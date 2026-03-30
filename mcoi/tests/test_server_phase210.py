"""Phase 210 — Server endpoint tests for chat workflow, health score, version, release."""

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


class TestChatWorkflowEndpoint:
    def test_chat_workflow(self, client):
        resp = client.post("/api/v1/chat/workflow", json={
            "conversation_id": "cw-1", "message": "Analyze this data",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["response"]
        assert data["trace_id"]
        assert data["governed"] is True

    def test_chat_workflow_multi_turn(self, client):
        client.post("/api/v1/chat/workflow", json={
            "conversation_id": "cw-multi", "message": "First",
            "system_prompt": "Be helpful.",
        })
        resp = client.post("/api/v1/chat/workflow", json={
            "conversation_id": "cw-multi", "message": "Second",
        })
        assert resp.json()["message_count"] >= 4

    def test_chat_workflow_history(self, client):
        client.post("/api/v1/chat/workflow", json={
            "conversation_id": "cw-h", "message": "test",
        })
        resp = client.get("/api/v1/chat/workflow/history")
        assert resp.status_code == 200
        assert resp.json()["summary"]["total"] >= 1

    def test_chat_workflow_bad_capability(self, client):
        resp = client.post("/api/v1/chat/workflow", json={
            "conversation_id": "cw-bad", "message": "test",
            "capability": "nonexistent",
        })
        assert resp.status_code == 400

    def test_chat_workflow_exception_is_sanitized(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        def boom(*args, **kwargs):
            raise RuntimeError("workflow-provider-secret")

        monkeypatch.setattr(deps.chat_workflow, "execute", boom)
        resp = client.post("/api/v1/chat/workflow", json={
            "conversation_id": "cw-fail",
            "message": "test",
            "tenant_id": "workflow-tenant",
            "actor_id": "workflow-actor",
        })
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error"] == "LLM service unavailable"
        assert data["error_code"] == "llm_service_unavailable"
        assert data["governed"] is True
        assert "workflow-provider-secret" not in str(resp.json())


class TestHealthScoreEndpoint:
    def test_health_score(self, client):
        resp = client.get("/api/v1/health/score")
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= data["score"] <= 1.0
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert len(data["components"]) >= 3


class TestVersionEndpoint:
    def test_version(self, client):
        resp = client.get("/api/v1/version")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "1.0.0"
        assert data["governed"] is True


class TestReleaseEndpoint:
    def test_release_info(self, client):
        resp = client.get("/api/v1/release")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "1.0.0"
        assert data["phase"] == 210
        assert "components" in data
        assert "llm" in data["components"]
        assert "agents" in data["components"]
        assert "governance" in data["components"]


class TestV1Integration:
    """Verify core v1.0.0 flows work end-to-end."""

    def test_full_governed_flow(self, client):
        """Health → Chat workflow → Audit → Health score."""
        # Health
        assert client.get("/health").status_code == 200

        # Chat workflow
        resp = client.post("/api/v1/chat/workflow", json={
            "conversation_id": "v1-test", "message": "test v1",
        })
        assert resp.json()["governed"] is True

        # Audit trail
        resp = client.get("/api/v1/audit/verify")
        assert resp.json()["valid"] is True

        # Health score
        resp = client.get("/api/v1/health/score")
        assert resp.json()["score"] > 0

        # Snapshot
        resp = client.get("/api/v1/snapshot")
        assert resp.status_code == 200

    def test_version_is_1_0_0(self, client):
        resp = client.get("/api/v1/version")
        assert resp.json()["version"] == "1.0.0"

        resp = client.get("/api/v1/release")
        assert resp.json()["version"] == "1.0.0"
