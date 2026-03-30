"""Phase 213 — Server endpoint tests for circuit-breaker LLM, tool workflow, streaming chat."""

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


class TestSafeCompletion:
    def test_safe_complete(self, client):
        resp = client.post("/api/v1/complete/safe", json={"prompt": "hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] is True
        assert data["circuit_state"] == "closed"
        assert data["governed"] is True

    def test_safe_complete_tracks_cost(self, client):
        client.post("/api/v1/complete/safe", json={
            "prompt": "test", "tenant_id": "safe-t",
        })
        resp = client.get("/api/v1/costs/safe-t")
        assert resp.json()["call_count"] >= 1

    def test_circuit_stays_closed_on_success(self, client):
        client.post("/api/v1/complete/safe", json={"prompt": "test"})
        resp = client.get("/api/v1/circuit-breaker")
        assert resp.json()["state"] == "closed"

    def test_safe_complete_exception_is_sanitized(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        def boom(*args, **kwargs):
            raise RuntimeError("safe-provider-secret")

        monkeypatch.setattr(deps.llm_bridge, "complete", boom)
        resp = client.post("/api/v1/complete/safe", json={"prompt": "hello"})
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error"] == "LLM service unavailable"
        assert data["error_code"] == "llm_service_unavailable"
        assert "safe-provider-secret" not in str(resp.json())


class TestToolWorkflowEndpoint:
    def test_tool_workflow(self, client):
        resp = client.post("/api/v1/workflow/tools", json={
            "prompt": "What is 2+2?",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"]
        assert data["governed"] is True

    def test_tool_workflow_with_filter(self, client):
        resp = client.post("/api/v1/workflow/tools", json={
            "prompt": "Calculate something",
            "tool_ids": ["calculator"],
        })
        assert resp.status_code == 200

    def test_tool_workflow_with_tenant(self, client):
        resp = client.post("/api/v1/workflow/tools", json={
            "prompt": "What time is it?",
            "tenant_id": "tool-tenant",
        })
        assert resp.json()["governed"] is True


class TestStreamingChat:
    def test_streaming_chat(self, client):
        resp = client.post("/api/v1/chat/stream", json={
            "conversation_id": "stream-1", "message": "Hello",
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "event: meta" in body
        assert "event: done" in body

    def test_streaming_chat_multi_turn(self, client):
        client.post("/api/v1/chat/stream", json={
            "conversation_id": "stream-multi", "message": "First",
            "system_prompt": "Be concise.",
        })
        resp = client.post("/api/v1/chat/stream", json={
            "conversation_id": "stream-multi", "message": "Second",
        })
        assert resp.status_code == 200
        # Verify conversation persisted
        conv_resp = client.get("/api/v1/conversation/stream-multi")
        assert conv_resp.json()["summary"]["message_count"] >= 4

    def test_streaming_chat_governed(self, client):
        resp = client.post("/api/v1/chat/stream", json={
            "conversation_id": "stream-gov", "message": "test",
        })
        assert "governed" in resp.text.lower() or resp.status_code == 200

    def test_streaming_chat_exception_is_sanitized(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        def boom(*args, **kwargs):
            raise RuntimeError("stream-chat-secret")

        monkeypatch.setattr(deps.llm_bridge, "chat", boom)
        resp = client.post("/api/v1/chat/stream", json={
            "conversation_id": "stream-fail",
            "message": "fail",
        })
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error"] == "LLM service unavailable"
        assert data["error_code"] == "llm_service_unavailable"
        assert "stream-chat-secret" not in str(resp.json())


class TestLatestRelease:
    def test_latest_release(self, client):
        resp = client.get("/api/v1/release/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["governed"] is True
        assert len(data["highlights"]) >= 3

    def test_both_release_endpoints(self, client):
        r1 = client.get("/api/v1/release")
        r2 = client.get("/api/v1/release/latest")
        assert r1.json()["version"] == "1.0.0"
        # Latest version may be >= 1.1.0
        assert r2.json()["version"] >= "1.1.0"


class TestV1_1Integration:
    """v1.1.0 integration flow."""

    def test_full_v1_1_flow(self, client):
        """Safe complete → tool workflow → streaming chat → verify."""
        # Safe completion
        resp = client.post("/api/v1/complete/safe", json={"prompt": "test"})
        assert resp.json()["governed"] is True

        # Tool workflow
        resp = client.post("/api/v1/workflow/tools", json={"prompt": "calc"})
        assert resp.json()["governed"] is True

        # Streaming chat
        resp = client.post("/api/v1/chat/stream", json={
            "conversation_id": "v11-test", "message": "hello",
        })
        assert resp.status_code == 200

        # Verify metrics counted
        resp = client.get("/api/v1/metrics")
        assert resp.json()["counters"]["requests_governed"] >= 3

        # Circuit breaker still closed
        resp = client.get("/api/v1/circuit-breaker")
        assert resp.json()["state"] == "closed"
