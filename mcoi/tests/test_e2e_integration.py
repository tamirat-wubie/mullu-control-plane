"""Phase 205B — End-to-end integration test.

Tests the full governed pipeline: API → agent workflow → LLM → audit → webhook → verify.
"""

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


class TestE2EIntegration:
    """Full end-to-end governed pipeline tests."""

    def test_full_lifecycle(self, client):
        """Test: health → session → budget → workflow → audit → verify."""
        # 1. Health check
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["governed"] is True

        # 2. Create tenant budget
        resp = client.post("/api/v1/tenant/budget", json={
            "tenant_id": "e2e-tenant", "max_cost": 50.0,
        })
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "e2e-tenant"

        # 3. Execute workflow
        resp = client.post("/api/v1/workflow/execute", json={
            "task_id": "e2e-task-1", "description": "Analyze test data",
            "capability": "llm.completion", "tenant_id": "e2e-tenant",
        })
        assert resp.status_code == 200
        wf = resp.json()
        assert wf["status"] == "completed"
        assert wf["agent_id"] == "llm-agent"
        assert wf["output"]["content"]

        # 4. Verify audit trail
        resp = client.get("/api/v1/audit", params={"tenant_id": "e2e-tenant"})
        assert resp.status_code == 200
        audit = resp.json()
        assert audit["count"] >= 1

        # 5. Verify audit chain integrity
        resp = client.get("/api/v1/audit/verify")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

        # 6. Check metrics reflect activity
        resp = client.get("/api/v1/metrics")
        assert resp.status_code == 200
        assert resp.json()["counters"]["requests_governed"] >= 3

    def test_workflow_then_certification(self, client):
        """Workflow execution followed by certification proves system integrity."""
        # Execute workflow
        resp = client.post("/api/v1/workflow/execute", json={
            "task_id": "cert-test-1", "description": "test",
            "capability": "llm.completion",
        })
        assert resp.json()["status"] == "completed"

        # Run certification
        resp = client.post("/api/v1/certify")
        assert resp.status_code == 200
        cert = resp.json()
        assert cert["all_passed"] is True

    def test_deep_health_after_operations(self, client):
        """Deep health shows all components healthy after operations."""
        # Do some work
        client.post("/api/v1/workflow/execute", json={
            "task_id": "health-test-1", "description": "test",
            "capability": "llm.completion",
        })

        # Deep health check
        resp = client.get("/api/v1/health/deep")
        assert resp.status_code == 200
        health = resp.json()
        assert health["overall"] == "healthy"
        assert len(health["components"]) >= 3

    def test_dashboard_aggregation(self, client):
        """Dashboard aggregates data from all subsystems."""
        # Execute some work to generate data
        client.post("/api/v1/workflow/execute", json={
            "task_id": "dash-1", "description": "test",
            "capability": "llm.completion",
        })

        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        dashboard = resp.json()
        assert "health" in dashboard
        assert "llm" in dashboard
        assert "agents" in dashboard
        assert "audit" in dashboard
        assert "workflows" in dashboard

    def test_webhook_flow(self, client):
        """Subscribe webhook → execute workflow → verify delivery."""
        # Subscribe
        resp = client.post("/api/v1/webhooks/subscribe", json={
            "subscription_id": "e2e-hook", "tenant_id": "t1",
            "url": "https://example.com/hook",
            "events": ["task.completed", "task.failed"],
        })
        assert resp.status_code == 200

        # Execute workflow (triggers webhook)
        resp = client.post("/api/v1/workflow/execute", json={
            "task_id": "hook-test-1", "description": "test",
            "capability": "llm.completion", "tenant_id": "t1",
        })
        assert resp.json()["status"] == "completed"

        # Check deliveries
        resp = client.get("/api/v1/webhooks/deliveries")
        deliveries = resp.json()["deliveries"]
        assert len(deliveries) >= 1
        assert any(d["event"] == "task.completed" for d in deliveries)

    def test_config_visibility(self, client):
        """Config endpoint shows runtime configuration."""
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data["config"]
        assert data["version"] >= 1

    def test_agents_visible(self, client):
        """Agent registry shows registered agents."""
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        assert any(a["id"] == "llm-agent" for a in agents)
        assert any(a["id"] == "code-agent" for a in agents)

    def test_multiple_workflows_tracked(self, client):
        """Multiple workflow executions are tracked in history."""
        for i in range(3):
            client.post("/api/v1/workflow/execute", json={
                "task_id": f"multi-{i}", "description": f"test {i}",
                "capability": "llm.completion",
            })

        resp = client.get("/api/v1/workflow/history")
        data = resp.json()
        assert data["summary"]["total"] >= 3
