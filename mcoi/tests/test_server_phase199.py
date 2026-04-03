"""Phase 199 — Server endpoint tests.

Tests: LLM completion, budget, certification, ledger endpoints.
Uses FastAPI TestClient when available, falls back to structural tests.
"""

import pytest
import os
from types import SimpleNamespace

# Try to import FastAPI test client
try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.fixture
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    # Set dev environment
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "llm_invocations" in data
        assert "llm_total_cost" in data
        assert "certifications" in data
        assert "ledger_entries" in data

    def test_ready_endpoint(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True


class TestCompletionEndpoint:
    def test_basic_completion(self, client):
        resp = client.post("/api/v1/complete", json={
            "prompt": "What is 2+2?",
            "tenant_id": "test-tenant",
            "budget_id": "default",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert data["governed"] is True
        assert data["cost"] >= 0
        assert data["provider"] == "stub"

    def test_completion_with_system(self, client):
        resp = client.post("/api/v1/complete", json={
            "prompt": "hello",
            "system": "you are a math tutor",
            "tenant_id": "test-tenant",
        })
        assert resp.status_code == 200
        assert resp.json()["content"]

    def test_completion_with_custom_params(self, client):
        resp = client.post("/api/v1/complete", json={
            "prompt": "test",
            "model_name": "custom-model",
            "max_tokens": 512,
            "temperature": 0.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "custom-model"

    def test_completion_exception_is_sanitized(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        def boom(*args, **kwargs):
            raise RuntimeError("secret-provider-detail")

        monkeypatch.setattr(deps.llm_bridge, "complete", boom)
        resp = client.post("/api/v1/complete", json={
            "prompt": "boom",
            "tenant_id": "err-tenant",
            "actor_id": "err-actor",
        })
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error"] == "LLM service unavailable"
        assert data["error_code"] == "llm_service_unavailable"
        assert "secret-provider-detail" not in str(resp.json())
        entries = deps.audit_trail.query(
            tenant_id="err-tenant",
            action="llm.complete",
            outcome="error",
            limit=5,
        )
        assert any(e.detail["error_type"] == "RuntimeError" for e in entries)

    def test_completion_failure_result_is_structured(self, client, monkeypatch):
        from mcoi_runtime.app.routers.deps import deps

        monkeypatch.setattr(
            deps.llm_bridge,
            "complete",
            lambda *args, **kwargs: SimpleNamespace(
                succeeded=False,
                error="provider timeout (TimeoutError)",
            ),
        )
        resp = client.post("/api/v1/complete", json={"prompt": "fail"})
        assert resp.status_code == 503
        data = resp.json()["detail"]
        assert data["error_code"] == "llm_completion_failed"
        assert data["governed"] is True


class TestBudgetEndpoint:
    def test_budget_summary(self, client):
        resp = client.get("/api/v1/budget")
        assert resp.status_code == 200
        data = resp.json()
        assert "budgets" in data
        assert "total_spent" in data


class TestLLMHistoryEndpoint:
    def test_history_empty(self, client):
        resp = client.get("/api/v1/llm/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "invocations" in data

    def test_history_after_completion(self, client):
        client.post("/api/v1/complete", json={"prompt": "test"})
        resp = client.get("/api/v1/llm/history")
        data = resp.json()
        assert len(data["invocations"]) >= 1


class TestLedgerEndpoint:
    def test_ledger_returns_entries(self, client):
        resp = client.get("/api/v1/ledger")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert data["governed"] is True

    def test_ledger_after_completion(self, client):
        client.post("/api/v1/complete", json={"prompt": "test for ledger"})
        resp = client.get("/api/v1/ledger?tenant_id=system")
        data = resp.json()
        assert data["count"] >= 0


class TestCertificationEndpoint:
    def test_run_certification(self, client):
        resp = client.post("/api/v1/certify")
        assert resp.status_code == 200
        data = resp.json()
        assert "chain_id" in data
        assert "all_passed" in data
        assert "chain_hash" in data
        assert "steps" in data
        assert len(data["steps"]) == 5

    def test_certification_steps_have_names(self, client):
        resp = client.post("/api/v1/certify")
        data = resp.json()
        step_names = [s["name"] for s in data["steps"]]
        assert "api_boundary" in step_names
        assert "db_persistence" in step_names
        assert "llm_invocation" in step_names
        assert "ledger_integrity" in step_names
        assert "restart_proof" in step_names

    def test_certification_history(self, client):
        client.post("/api/v1/certify")
        resp = client.get("/api/v1/certify/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["certifications"]) >= 1


class TestSessionEndpoint:
    def test_create_session(self, client):
        resp = client.post("/api/v1/session?actor_id=test-actor&tenant_id=test-tenant")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["actor_id"] == "test-actor"
        assert data["tenant_id"] == "test-tenant"


class TestServerImport:
    """Structural tests that don't require FastAPI."""

    def test_server_module_importable(self):
        try:
            from mcoi_runtime.app import server
            assert hasattr(server, "app")
            assert hasattr(server, "llm_bridge")
            assert hasattr(server, "certifier")
            assert hasattr(server, "store")
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_completion_request_model(self):
        try:
            from mcoi_runtime.app.server import CompletionRequest
            req = CompletionRequest(prompt="test")
            assert req.prompt == "test"
            assert req.budget_id == "default"
            assert req.model_name == "claude-sonnet-4-20250514"
        except ImportError:
            pytest.skip("FastAPI not installed")
