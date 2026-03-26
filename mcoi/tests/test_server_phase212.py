"""Phase 212 — Server endpoint tests for tools, state, output, circuit breaker."""

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


class TestToolEndpoints:
    def test_list_tools(self, client):
        resp = client.get("/api/v1/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2
        ids = [t["id"] for t in data["tools"]]
        assert "calculator" in ids
        assert "get_time" in ids

    def test_invoke_tool(self, client):
        resp = client.post("/api/v1/tools/invoke", json={
            "tool_id": "calculator", "arguments": {"expression": "2+3"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] is True
        assert data["output"]["result"] == "5"

    def test_invoke_unknown_tool(self, client):
        resp = client.post("/api/v1/tools/invoke", json={
            "tool_id": "nonexistent", "arguments": {},
        })
        data = resp.json()
        assert data["succeeded"] is False

    def test_invoke_get_time(self, client):
        resp = client.post("/api/v1/tools/invoke", json={
            "tool_id": "get_time", "arguments": {},
        })
        assert resp.json()["succeeded"] is True
        assert resp.json()["output"]["time"]

    def test_llm_format(self, client):
        resp = client.get("/api/v1/tools/llm-format")
        assert resp.status_code == 200
        tools = resp.json()["tools"]
        assert len(tools) >= 2
        assert all("input_schema" in t for t in tools)

    def test_tool_history(self, client):
        client.post("/api/v1/tools/invoke", json={"tool_id": "get_time", "arguments": {}})
        resp = client.get("/api/v1/tools/history")
        assert resp.json()["summary"]["invocations"] >= 1


class TestStateEndpoints:
    def test_save_and_load(self, client):
        client.post("/api/v1/state/save", json={
            "state_type": "test_config", "data": {"key": "value"},
        })
        resp = client.get("/api/v1/state/test_config")
        assert resp.status_code == 200
        assert resp.json()["data"]["key"] == "value"

    def test_load_missing(self, client):
        resp = client.get("/api/v1/state/nonexistent_state")
        assert resp.status_code == 404

    def test_list_states(self, client):
        client.post("/api/v1/state/save", json={
            "state_type": "list_test", "data": {},
        })
        resp = client.get("/api/v1/state")
        assert resp.status_code == 200


class TestStructuredOutputEndpoints:
    def test_parse_valid(self, client):
        resp = client.post("/api/v1/output/parse", json={
            "schema_id": "analysis",
            "text": '{"summary": "test summary", "key_points": ["a", "b"]}',
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_parse_invalid(self, client):
        resp = client.post("/api/v1/output/parse", json={
            "schema_id": "analysis", "text": "not json",
        })
        assert resp.json()["valid"] is False

    def test_list_output_schemas(self, client):
        resp = client.get("/api/v1/output/schemas")
        assert resp.status_code == 200
        assert len(resp.json()["schemas"]) >= 1


class TestCircuitBreakerEndpoint:
    def test_circuit_breaker_status(self, client):
        resp = client.get("/api/v1/circuit-breaker")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "closed"
        assert "failure_count" in data
