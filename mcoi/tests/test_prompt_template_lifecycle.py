"""Purpose: witness prompt-template lifecycle proof coverage anchors.

Governance scope: verifies prompt template read models, deterministic rendering,
bounded validation failures, sanitized execution errors, and budgeted execution
receipts through the public prompt routes.
Dependencies: FastAPI TestClient and the runtime prompt/cost services.
Invariants: template metadata is bounded, missing variables fail closed,
provider failures are sanitized, and successful execution records cost evidence.
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


def test_prompt_template_list_bounded(client):
    response = client.get("/api/v1/prompts", params={"category": "analysis"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"templates", "summary"}
    assert payload["summary"]["total"] >= len(payload["templates"])
    assert payload["summary"]["by_category"]["analysis"] >= len(payload["templates"])
    assert {template["id"] for template in payload["templates"]} >= {"summarize", "analyze"}
    assert all(template["category"] == "analysis" for template in payload["templates"])
    assert all(
        set(template) == {"id", "name", "variables", "category", "version"}
        for template in payload["templates"]
    )


def test_prompt_render_variables_validated(client):
    rendered_response = client.post(
        "/api/v1/prompts/render",
        json={
            "template_id": "translate",
            "variables": {"text": "hello", "language": "Spanish", "unused": "ignored"},
        },
    )
    missing_variable_response = client.post(
        "/api/v1/prompts/render",
        json={"template_id": "translate", "variables": {"text": "hello"}},
    )

    assert rendered_response.status_code == 200
    rendered = rendered_response.json()
    assert rendered["template_id"] == "translate"
    assert "Spanish" in rendered["prompt"]
    assert "hello" in rendered["prompt"]
    assert rendered["system_prompt"] == "You are a professional translator."
    assert "llm_result" not in rendered
    assert missing_variable_response.status_code == 400
    assert missing_variable_response.json()["detail"] == {
        "error": "invalid request",
        "error_code": "validation_error",
        "governed": True,
    }


def test_prompt_execution_failure_sanitized(client, monkeypatch):
    from mcoi_runtime.app.routers.deps import deps

    def provider_failure(*_args, **_kwargs):
        raise RuntimeError("prompt-provider-secret")

    monkeypatch.setattr(deps.llm_bridge, "complete", provider_failure)

    response = client.post(
        "/api/v1/prompts/render",
        json={
            "template_id": "summarize",
            "variables": {"text": "sensitive source text"},
            "execute": True,
            "tenant_id": "prompt-failure-tenant",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "LLM service unavailable"
    assert detail["error_code"] == "llm_service_unavailable"
    assert detail["governed"] is True
    assert "prompt-provider-secret" not in str(response.json())


def test_prompt_execution_records_budgeted_result(client):
    tenant_id = "prompt-budget-tenant"
    response = client.post(
        "/api/v1/prompts/render",
        json={
            "template_id": "summarize",
            "variables": {"text": "budgeted execution witness"},
            "execute": True,
            "tenant_id": tenant_id,
            "budget_id": "default",
        },
    )
    cost_response = client.get(f"/api/v1/costs/{tenant_id}")

    assert response.status_code == 200
    payload = response.json()
    llm_result = payload["llm_result"]
    assert llm_result["succeeded"] is True
    assert llm_result["model"]
    assert llm_result["tokens"] >= 0
    assert llm_result["cost"] >= 0
    assert cost_response.status_code == 200
    cost_payload = cost_response.json()
    assert cost_payload["call_count"] >= 1
    assert cost_payload["total_cost"] >= llm_result["cost"]
