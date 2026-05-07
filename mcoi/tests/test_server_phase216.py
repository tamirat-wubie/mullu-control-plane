"""Phase 216 — Governed router error contract tests."""

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
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.server import app

    return TestClient(app)


class TestWorkflowErrorContracts:
    def test_execute_workflow_bad_capability_returns_governed_error(self, client):
        resp = client.post(
            "/api/v1/workflow/execute",
            json={"task_id": "wf-bad", "description": "test", "capability": "nonexistent.capability"},
        )
        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "invalid capability"
        assert data["error_code"] == "invalid_capability"
        assert data["governed"] is True
        assert "nonexistent.capability" not in str(resp.json())

    def test_traced_workflow_bad_capability_returns_governed_error(self, client):
        resp = client.post(
            "/api/v1/workflow/traced",
            json={"task_id": "wf-bad-traced", "description": "test", "capability": "nonexistent.capability"},
        )
        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "invalid capability"
        assert data["error_code"] == "invalid_capability"
        assert data["governed"] is True
        assert "nonexistent.capability" not in str(resp.json())


class TestDataErrorContracts:
    def test_create_wildcard_api_key_returns_governed_validation_error(self, client):
        from mcoi_runtime.app.routers.deps import deps
        from mcoi_runtime.governance.auth.api_key import APIKeyManager

        original_api_key_mgr = deps.get("api_key_mgr")
        deps.set(
            "api_key_mgr",
            APIKeyManager(
                clock=lambda: "2026-01-01T00:00:00Z",
                allow_wildcard_keys=False,
            ),
        )
        try:
            resp = client.post(
                "/api/v1/api-keys",
                json={
                    "tenant_id": "tenant-a",
                    "scopes": ["*"],
                    "description": "full access",
                },
            )
        finally:
            deps.set("api_key_mgr", original_api_key_mgr)

        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "wildcard api keys disabled"
        assert data["error_code"] == "wildcard_api_keys_disabled"
        assert data["governed"] is True
        assert "tenant-a" not in str(resp.json())

    def test_create_api_key_empty_scopes_returns_governed_validation_error(self, client):
        resp = client.post(
            "/api/v1/api-keys",
            json={
                "tenant_id": "tenant-a",
                "scopes": [],
                "description": "empty scopes",
            },
        )

        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "invalid api key request"
        assert data["error_code"] == "api_key_validation_error"
        assert data["governed"] is True
        assert "tenant-a" not in str(resp.json())

    def test_load_missing_state_returns_governed_not_found(self, client):
        resp = client.get("/api/v1/state/nonexistent_state")
        assert resp.status_code == 404
        data = resp.json()["detail"]
        assert data["error"] == "state not found"
        assert data["error_code"] == "state_not_found"
        assert data["governed"] is True
        assert "nonexistent_state" not in str(resp.json())

    def test_revoke_missing_api_key_returns_governed_not_found(self, client):
        resp = client.delete("/api/v1/api-keys/key-missing-123")
        assert resp.status_code == 404
        data = resp.json()["detail"]
        assert data["error"] == "api key not found"
        assert data["error_code"] == "api_key_not_found"
        assert data["governed"] is True
        assert "key-missing-123" not in str(resp.json())

    def test_export_invalid_format_returns_governed_validation_error(self, client):
        resp = client.post("/api/v1/export", json={"source": "audit", "format": "xml"})
        assert resp.status_code == 400
        data = resp.json()["detail"]
        assert data["error"] == "unsupported export format"
        assert data["error_code"] == "unsupported_export_format"
        assert data["governed"] is True
        assert "xml" not in str(resp.json())


class TestAgentErrorContracts:
    def test_missing_orchestration_plan_returns_governed_not_found(self, client):
        resp = client.get("/api/v1/orchestration/plans/plan-missing-123")
        assert resp.status_code == 404
        data = resp.json()["detail"]
        assert data["error"] == "plan not found"
        assert data["error_code"] == "plan_not_found"
        assert data["governed"] is True
        assert "plan-missing-123" not in str(resp.json())
