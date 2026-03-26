"""Phase 208 — Server endpoint tests for middleware, traced workflow, conversations, schemas."""

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


class TestGovernanceMiddleware:
    def test_health_bypasses_guards(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_governed_endpoint_passes(self, client):
        resp = client.get("/api/v1/metrics")
        assert resp.status_code == 200


class TestTracedWorkflowEndpoint:
    def test_traced_workflow(self, client):
        resp = client.post("/api/v1/workflow/traced", json={
            "task_id": "traced-1", "description": "test traced",
            "capability": "llm.completion",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["trace_id"] is not None
        assert data["trace_frames"] >= 3

    def test_traced_workflow_bad_capability(self, client):
        resp = client.post("/api/v1/workflow/traced", json={
            "task_id": "bad", "description": "test",
            "capability": "nonexistent",
        })
        assert resp.status_code == 400

    def test_traces_in_replay_list(self, client):
        client.post("/api/v1/workflow/traced", json={
            "task_id": "replay-1", "description": "test",
            "capability": "llm.completion",
        })
        resp = client.get("/api/v1/replay/traces")
        data = resp.json()
        assert data["count"] >= 1
        assert data["summary"]["completed"] >= 1


class TestConversationEndpoints:
    def test_add_message(self, client):
        resp = client.post("/api/v1/conversation/message", json={
            "conversation_id": "conv-1", "role": "user", "content": "hello",
        })
        assert resp.status_code == 200
        assert resp.json()["message_count"] == 1

    def test_get_conversation(self, client):
        client.post("/api/v1/conversation/message", json={
            "conversation_id": "conv-get", "role": "user", "content": "hi",
        })
        resp = client.get("/api/v1/conversation/conv-get")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 1

    def test_get_missing_conversation(self, client):
        resp = client.get("/api/v1/conversation/nonexistent")
        assert resp.status_code == 404

    def test_multi_turn(self, client):
        client.post("/api/v1/conversation/message", json={
            "conversation_id": "multi", "role": "user", "content": "What is 2+2?",
        })
        client.post("/api/v1/conversation/message", json={
            "conversation_id": "multi", "role": "assistant", "content": "4",
        })
        resp = client.get("/api/v1/conversation/multi")
        assert len(resp.json()["messages"]) == 2

    def test_list_conversations(self, client):
        client.post("/api/v1/conversation/message", json={
            "conversation_id": "list-1", "content": "a",
        })
        resp = client.get("/api/v1/conversations")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1


class TestSchemaEndpoints:
    def test_list_schemas(self, client):
        resp = client.get("/api/v1/schemas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["schemas"] >= 2

    def test_validate_valid(self, client):
        resp = client.post("/api/v1/schemas/validate", json={
            "schema_id": "workflow_request",
            "data": {"task_id": "t1", "description": "test", "capability": "llm.completion"},
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_invalid(self, client):
        resp = client.post("/api/v1/schemas/validate", json={
            "schema_id": "workflow_request",
            "data": {"task_id": "", "description": ""},
        })
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) >= 1

    def test_validate_unknown_schema(self, client):
        resp = client.post("/api/v1/schemas/validate", json={
            "schema_id": "nonexistent", "data": {},
        })
        assert resp.json()["valid"] is False
