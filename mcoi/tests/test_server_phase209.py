"""Phase 209 — Server endpoint tests for chat, prompts, cost analytics."""

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


class TestChatEndpoint:
    def test_single_turn(self, client):
        resp = client.post("/api/v1/chat", json={
            "conversation_id": "chat-1", "message": "What is 2+2?",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] is True
        assert data["content"]
        assert data["governed"] is True
        assert data["message_count"] >= 2  # user + assistant

    def test_multi_turn(self, client):
        client.post("/api/v1/chat", json={
            "conversation_id": "multi-chat", "message": "Hello",
            "system_prompt": "You are helpful.",
        })
        resp = client.post("/api/v1/chat", json={
            "conversation_id": "multi-chat", "message": "What did I just say?",
        })
        data = resp.json()
        assert data["message_count"] >= 4  # system + user + assistant + user + assistant

    def test_chat_tracks_cost(self, client):
        client.post("/api/v1/chat", json={
            "conversation_id": "cost-chat", "message": "test", "tenant_id": "cost-t",
        })
        resp = client.get("/api/v1/costs/cost-t")
        assert resp.json()["call_count"] >= 1

    def test_conversation_persists(self, client):
        client.post("/api/v1/chat", json={
            "conversation_id": "persist-chat", "message": "hi",
        })
        resp = client.get("/api/v1/conversation/persist-chat")
        assert resp.status_code == 200
        assert len(resp.json()["messages"]) >= 2

    def test_chat_exception_is_sanitized(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        def boom(*args, **kwargs):
            raise RuntimeError("chat-provider-secret")

        monkeypatch.setattr(deps.llm_bridge, "chat", boom)
        resp = client.post("/api/v1/chat", json={
            "conversation_id": "chat-fail",
            "message": "fail",
            "tenant_id": "chat-tenant",
            "actor_id": "chat-actor",
        })
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error"] == "LLM service unavailable"
        assert data["error_code"] == "llm_service_unavailable"
        assert "chat-provider-secret" not in str(resp.json())


class TestPromptEndpoints:
    def test_list_templates(self, client):
        resp = client.get("/api/v1/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] >= 3
        ids = [t["id"] for t in data["templates"]]
        assert "summarize" in ids
        assert "translate" in ids

    def test_prompt_template_list_bounded(self, client):
        resp = client.get("/api/v1/prompts", params={"category": "analysis"})

        assert resp.status_code == 200
        data = resp.json()
        assert set(data) == {"templates", "summary"}
        assert data["summary"]["total"] >= len(data["templates"])
        assert all(set(template) == {"id", "name", "variables", "category", "version"} for template in data["templates"])
        assert all(template["category"] == "analysis" for template in data["templates"])

    def test_render_only(self, client):
        resp = client.post("/api/v1/prompts/render", json={
            "template_id": "summarize",
            "variables": {"text": "The quick brown fox"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "quick brown fox" in data["prompt"]
        assert "llm_result" not in data  # Not executed

    def test_prompt_render_variables_validated(self, client):
        valid_resp = client.post("/api/v1/prompts/render", json={
            "template_id": "summarize",
            "variables": {"text": "The quick brown fox"},
        })
        invalid_resp = client.post("/api/v1/prompts/render", json={
            "template_id": "translate",
            "variables": {"text": "hello"},
        })

        assert valid_resp.status_code == 200
        assert "quick brown fox" in valid_resp.json()["prompt"]
        assert invalid_resp.status_code == 400
        assert invalid_resp.json()["detail"]["error_code"] == "validation_error"
        assert invalid_resp.json()["detail"]["governed"] is True
        assert "language" not in str(invalid_resp.json())

    def test_render_and_execute(self, client):
        resp = client.post("/api/v1/prompts/render", json={
            "template_id": "summarize",
            "variables": {"text": "Some long text"},
            "execute": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_result" in data
        assert data["llm_result"]["succeeded"] is True

    def test_prompt_execution_records_budgeted_result(self, client):
        resp = client.post("/api/v1/prompts/render", json={
            "template_id": "summarize",
            "variables": {"text": "Budgeted prompt execution"},
            "execute": True,
            "budget_id": "default",
            "tenant_id": "prompt-budget-tenant",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["template_id"] == "summarize"
        assert "Budgeted prompt execution" in data["prompt"]
        assert set(data["llm_result"]) == {"content", "model", "tokens", "cost", "succeeded"}
        assert data["llm_result"]["succeeded"] is True
        assert data["llm_result"]["tokens"] >= 0
        assert data["llm_result"]["cost"] >= 0

    def test_render_missing_variable(self, client):
        resp = client.post("/api/v1/prompts/render", json={
            "template_id": "translate",
            "variables": {"text": "hello"},  # Missing "language"
        })
        assert resp.status_code == 400

    def test_render_unknown_template(self, client):
        resp = client.post("/api/v1/prompts/render", json={
            "template_id": "nonexistent", "variables": {},
        })
        assert resp.status_code == 400

    def test_filter_by_category(self, client):
        resp = client.get("/api/v1/prompts", params={"category": "analysis"})
        data = resp.json()
        assert all(t["category"] == "analysis" for t in data["templates"])

    def test_render_execute_exception_is_sanitized(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        def boom(*args, **kwargs):
            raise RuntimeError("prompt-provider-secret")

        monkeypatch.setattr(deps.llm_bridge, "complete", boom)
        resp = client.post("/api/v1/prompts/render", json={
            "template_id": "summarize",
            "variables": {"text": "Some long text"},
            "execute": True,
            "tenant_id": "prompt-tenant",
        })
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error"] == "LLM service unavailable"
        assert data["error_code"] == "llm_service_unavailable"
        assert data["governed"] is True
        assert "prompt-provider-secret" not in str(resp.json())

    def test_prompt_execution_failure_sanitized(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        def boom(*args, **kwargs):
            raise RuntimeError("prompt-provider-secret")

        monkeypatch.setattr(deps.llm_bridge, "complete", boom)
        resp = client.post("/api/v1/prompts/render", json={
            "template_id": "summarize",
            "variables": {"text": "Some long text"},
            "execute": True,
            "tenant_id": "prompt-tenant",
        })

        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error"] == "LLM service unavailable"
        assert data["error_code"] == "llm_service_unavailable"
        assert data["governed"] is True
        assert "prompt-provider-secret" not in str(resp.json())


class TestCostAnalyticsEndpoints:
    def test_cost_summary(self, client):
        resp = client.get("/api/v1/costs")
        assert resp.status_code == 200
        assert "total_entries" in resp.json()

    def test_tenant_costs(self, client):
        # Generate some cost data via chat
        client.post("/api/v1/chat", json={
            "conversation_id": "cost-test", "message": "test", "tenant_id": "analytics-t",
        })
        resp = client.get("/api/v1/costs/analytics-t")
        assert resp.status_code == 200
        assert resp.json()["call_count"] >= 1

    def test_tenant_costs_invalid_tenant_returns_bounded_422(self, client):
        resp = client.get("/api/v1/costs/%20%20%20")

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid cost analytics request"
        assert detail["error_code"] == "cost_analytics_invalid_request"
        assert detail["governed"] is True
        assert "tenant_id" not in str(resp.json())
        assert "%20" not in str(resp.json())

    def test_cost_projection(self, client):
        client.post("/api/v1/chat", json={
            "conversation_id": "proj-test", "message": "test", "tenant_id": "proj-t",
        })
        resp = client.get("/api/v1/costs/proj-t/projection", params={"budget": 10.0})
        assert resp.status_code == 200
        assert resp.json()["projected_monthly"] >= 0

    def test_top_spenders(self, client):
        resp = client.get("/api/v1/costs/top-spenders")
        assert resp.status_code == 200
        assert "spenders" in resp.json()

    def test_top_spenders_invalid_limit_returns_bounded_422(self, client):
        resp = client.get("/api/v1/costs/top-spenders", params={"limit": -1})

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid cost analytics request"
        assert detail["error_code"] == "cost_analytics_invalid_request"
        assert detail["governed"] is True
        assert "-1" not in str(resp.json())
        assert "finite non-negative integer" not in str(resp.json())

    def test_costs_by_model(self, client):
        resp = client.get("/api/v1/costs/by-model")
        assert resp.status_code == 200
        assert "models" in resp.json()

    @pytest.mark.parametrize(
        "params",
        [
            {"budget": -1.0},
            {"days_elapsed": 0.0},
            {"days_elapsed": -1.0},
        ],
    )
    def test_cost_projection_invalid_query_returns_bounded_422(self, client, params):
        resp = client.get("/api/v1/costs/proj-t/projection", params=params)

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid cost analytics request"
        assert detail["error_code"] == "cost_analytics_invalid_request"
        assert detail["governed"] is True
        assert str(next(iter(params.values()))) not in str(resp.json())
        assert next(iter(params)) not in str(resp.json())
