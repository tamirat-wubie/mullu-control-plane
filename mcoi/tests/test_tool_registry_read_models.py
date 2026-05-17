"""Purpose: witness tool-registry read-model proof coverage anchors.

Governance scope: verifies that tool metadata and invocation history are exposed
as bounded read models while tool invocation remains on its action-proof surface.
Dependencies: FastAPI TestClient and the runtime tool registry.
Invariants: read models do not emit action proofs, category filters are bounded,
LLM schemas preserve required input contracts, and history limits are applied.
"""

from __future__ import annotations

import os

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
    from mcoi_runtime.app.server import app

    return TestClient(app)


def test_tool_registry_list_returns_registered_tools(client):
    response = client.get("/api/v1/tools")

    assert response.status_code == 200
    payload = response.json()
    tool_ids = {tool["id"] for tool in payload["tools"]}
    assert payload["count"] == len(payload["tools"])
    assert {"calculator", "get_time"}.issubset(tool_ids)
    assert "action_proof" not in payload
    assert all(
        set(tool) == {"id", "name", "description", "parameters", "category"}
        for tool in payload["tools"]
    )


def test_tool_registry_category_filter_bounded(client):
    utility_response = client.get("/api/v1/tools", params={"category": "utility"})
    missing_response = client.get("/api/v1/tools", params={"category": "not_registered"})

    assert utility_response.status_code == 200
    utility_payload = utility_response.json()
    assert utility_payload["count"] == len(utility_payload["tools"])
    assert {tool["id"] for tool in utility_payload["tools"]} >= {"calculator", "get_time"}
    assert all(tool["category"] == "utility" for tool in utility_payload["tools"])
    assert missing_response.status_code == 200
    assert missing_response.json() == {"tools": [], "count": 0}


def test_tool_llm_format_exports_input_schema(client):
    response = client.get("/api/v1/tools/llm-format")

    assert response.status_code == 200
    payload = response.json()
    calculator = next(tool for tool in payload["tools"] if tool["name"] == "calculator")
    schema = calculator["input_schema"]
    assert schema["type"] == "object"
    assert "expression" in schema["properties"]
    assert schema["properties"]["expression"]["type"] == "string"
    assert schema["required"] == ["expression"]
    assert "action_proof" not in payload


def test_tool_history_returns_bounded_summary(client):
    invoke_response = client.post(
        "/api/v1/tools/invoke",
        json={"tool_id": "get_time", "arguments": {}, "tenant_id": "tool-read-model"},
    )
    history_response = client.get("/api/v1/tools/history", params={"limit": 1})

    assert invoke_response.status_code == 200
    assert history_response.status_code == 200
    payload = history_response.json()
    assert len(payload["history"]) <= 1
    assert set(payload["summary"]) == {"tools", "invocations", "succeeded", "failed"}
    assert payload["summary"]["tools"] >= 2
    assert payload["summary"]["invocations"] >= len(payload["history"])
    assert "action_proof" not in payload


def test_tool_invocation_history_limit_applied(client):
    client.post(
        "/api/v1/tools/invoke",
        json={"tool_id": "calculator", "arguments": {"expression": "1+1"}},
    )
    latest_response = client.post(
        "/api/v1/tools/invoke",
        json={"tool_id": "calculator", "arguments": {"expression": "2+2"}},
    )
    history_response = client.get("/api/v1/tools/history", params={"limit": 1})

    assert latest_response.status_code == 200
    latest_invocation_id = latest_response.json()["invocation_id"]
    payload = history_response.json()
    assert history_response.status_code == 200
    assert len(payload["history"]) == 1
    assert payload["history"][0]["id"] == latest_invocation_id
    assert payload["history"][0]["tool"] == "calculator"
    assert payload["summary"]["invocations"] >= 2


def test_tool_invoke_separate_action_proof_surface(client):
    read_response = client.get("/api/v1/tools")
    history_response = client.get("/api/v1/tools/history", params={"limit": 1})
    invoke_response = client.post(
        "/api/v1/tools/invoke",
        json={"tool_id": "calculator", "arguments": {"expression": "2+3"}},
    )

    assert read_response.status_code == 200
    assert history_response.status_code == 200
    assert invoke_response.status_code == 200
    assert "action_proof" not in read_response.json()
    assert "action_proof" not in history_response.json()
    action_proof = invoke_response.json()["action_proof"]
    assert action_proof["endpoint"] == "/api/v1/tools/invoke"
    assert action_proof["proof_phase"] == "tool.invoke"
    assert action_proof["succeeded"] is True
