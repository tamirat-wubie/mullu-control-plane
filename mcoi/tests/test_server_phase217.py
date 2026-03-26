"""Phase 217 — Server endpoint tests."""

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


class TestUsageEndpoint:
    def test_usage_report(self, client):
        resp = client.get("/api/v1/usage/test-tenant")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "test-tenant"
        assert "llm_calls" in data
        assert "total_cost" in data


class TestFinalIntegration:
    """Final v1.4.0+ integration verification."""

    def test_all_core_endpoints(self, client):
        endpoints = [
            ("GET", "/health"),
            ("GET", "/ready"),
            ("GET", "/api/v1/metrics"),
            ("GET", "/api/v1/dashboard"),
            ("GET", "/api/v1/health/deep"),
            ("GET", "/api/v1/health/score"),
            ("GET", "/api/v1/version"),
            ("GET", "/api/v1/release"),
            ("GET", "/api/v1/readiness"),
            ("GET", "/api/v1/snapshot"),
            ("GET", "/api/v1/agents"),
            ("GET", "/api/v1/models"),
            ("GET", "/api/v1/tools"),
            ("GET", "/api/v1/plugins"),
            ("GET", "/api/v1/schemas"),
            ("GET", "/api/v1/config"),
            ("GET", "/api/v1/guards"),
            ("GET", "/api/v1/capabilities"),
            ("GET", "/api/v1/circuit-breaker"),
            ("GET", "/api/v1/monitor"),
            ("GET", "/api/v1/queue/status"),
            ("GET", "/api/v1/memory/summary"),
        ]
        for method, path in endpoints:
            resp = client.get(path) if method == "GET" else client.post(path)
            assert resp.status_code == 200, f"{method} {path} failed with {resp.status_code}"

    def test_governed_workflow_chain(self, client):
        """Full governed flow: chat → workflow → trace → audit → health."""
        # Chat workflow
        resp = client.post("/api/v1/chat/workflow", json={
            "conversation_id": "final-test", "message": "Final integration test",
        })
        assert resp.json()["governed"] is True

        # Verify audit
        resp = client.get("/api/v1/audit/verify")
        assert resp.json()["valid"] is True

        # Health score
        resp = client.get("/api/v1/health/score")
        assert resp.json()["score"] > 0

        # Readiness
        resp = client.get("/api/v1/readiness")
        assert resp.json()["ready"] is True
