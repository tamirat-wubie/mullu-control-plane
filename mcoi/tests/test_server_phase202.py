"""Phase 202 — Server endpoint tests for tenant API, metrics, rate limit, audit."""

import pytest
import os
import re

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


class TestTenantBudgetEndpoints:
    def test_create_tenant_budget(self, client):
        resp = client.post("/api/v1/tenant/budget", json={
            "tenant_id": "test-tenant", "max_cost": 50.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "test-tenant"
        assert data["max_cost"] == 50.0

    def test_get_tenant_budget(self, client):
        client.post("/api/v1/tenant/budget", json={"tenant_id": "t1"})
        resp = client.get("/api/v1/tenant/t1/budget")
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "t1"

    def test_get_tenant_ledger(self, client):
        resp = client.get("/api/v1/tenant/t1/ledger")
        assert resp.status_code == 200
        assert "entries" in resp.json()

    def test_get_tenant_ledger_zero_limit_returns_no_entries(self, client):
        resp = client.get("/api/v1/tenant/t1/ledger", params={"limit": "0"})

        assert resp.status_code == 200
        assert resp.json()["entries"] == []
        assert resp.json()["count"] == 0

    @pytest.mark.parametrize("limit", ["-1", "not-a-limit", "501"])
    def test_get_tenant_ledger_invalid_limit_returns_bounded_422(self, client, limit):
        resp = client.get("/api/v1/tenant/t1/ledger", params={"limit": limit})

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid tenant ledger request"
        assert detail["error_code"] == "tenant_ledger_invalid_request"
        assert detail["governed"] is True

    def test_get_tenant_summary(self, client):
        resp = client.get("/api/v1/tenant/t1/summary")
        assert resp.status_code == 200
        assert "total_entries" in resp.json()

    def test_list_tenants(self, client):
        resp = client.get("/api/v1/tenants")
        assert resp.status_code == 200
        assert "tenants" in resp.json()


class TestTenantUsageAnalyticsEndpoints:
    def test_tenant_usage_invalid_tenant_returns_bounded_422(self, client):
        resp = client.get("/api/v1/usage/%20%20%20")

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid tenant analytics request"
        assert detail["error_code"] == "tenant_analytics_invalid_request"
        assert detail["governed"] is True
        assert "tenant_id" not in str(resp.json())
        assert "%20" not in str(resp.json())

    def test_tenant_analytics_invalid_tenant_returns_bounded_422(self, client):
        resp = client.get("/api/v1/analytics/%20%20%20")

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid tenant analytics request"
        assert detail["error_code"] == "tenant_analytics_invalid_request"
        assert detail["governed"] is True
        assert "tenant_id" not in str(resp.json())
        assert "%20" not in str(resp.json())


class TestMetricsEndpoint:
    def test_get_metrics(self, client):
        resp = client.get("/api/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "counters" in data
        assert "gauges" in data

    def test_metrics_track_requests(self, client):
        # Make some requests that increment counters
        client.get("/api/v1/tenant/t1/budget")
        client.get("/api/v1/tenant/t1/budget")
        resp = client.get("/api/v1/metrics")
        data = resp.json()
        assert data["counters"]["requests_governed"] >= 2

    def test_prometheus_metrics_project_dashboard_families(self, client):
        client.post("/api/v1/tenant/budget", json={"tenant_id": "prometheus-tenant"})
        client.get("/api/v1/tenant/prometheus-tenant/budget")

        resp = client.get("/metrics")
        text = resp.text

        governed = re.search(r"^mullu_requests_governed_total\s+([0-9.]+)$", text, re.MULTILINE)
        tenants = re.search(r"^mullu_active_tenants\s+([0-9.]+)$", text, re.MULTILINE)

        assert resp.status_code == 200
        assert "# TYPE mullu_health_score gauge" in text
        assert "# TYPE mullu_chain_success_rate gauge" in text
        assert "# TYPE mullu_llm_budget_utilization_ratio gauge" in text
        assert governed is not None and float(governed.group(1)) >= 1.0
        assert tenants is not None and float(tenants.group(1)) >= 1.0


class TestRateLimitEndpoint:
    def test_rate_limit_status(self, client):
        resp = client.get("/api/v1/rate-limit/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_allowed" in data
        assert "active_buckets" in data


class TestAuditEndpoints:
    def test_get_audit_trail(self, client):
        resp = client.get("/api/v1/audit")
        assert resp.status_code == 200
        assert "entries" in resp.json()

    @pytest.mark.parametrize("limit", ["-1", "not-a-limit", "501"])
    def test_audit_invalid_limit_returns_bounded_422(self, client, limit):
        resp = client.get("/api/v1/audit", params={"limit": limit})

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid audit/event read request"
        assert detail["error_code"] == "audit_event_read_invalid_request"
        assert detail["governed"] is True

    def test_audit_zero_limit_is_empty_read(self, client):
        client.post("/api/v1/tenant/budget", json={"tenant_id": "zero-limit-audit"})

        resp = client.get("/api/v1/audit", params={"limit": "0"})

        assert resp.status_code == 200
        assert resp.json()["entries"] == []
        assert resp.json()["count"] == 0

    def test_audit_after_budget_create(self, client):
        client.post("/api/v1/tenant/budget", json={"tenant_id": "audit-test"})
        resp = client.get("/api/v1/audit")
        data = resp.json()
        assert data["count"] >= 1

    def test_audit_verify(self, client):
        client.post("/api/v1/tenant/budget", json={"tenant_id": "verify-test"})
        resp = client.get("/api/v1/audit/verify")
        data = resp.json()
        assert data["valid"] is True
        assert data["entries_checked"] >= 1

    def test_audit_summary(self, client):
        resp = client.get("/api/v1/audit/summary")
        assert resp.status_code == 200
        assert "entry_count" in resp.json()
        assert "chain_valid" in resp.json()

    def test_audit_filter_by_tenant(self, client):
        client.post("/api/v1/tenant/budget", json={"tenant_id": "filter-t1"})
        client.post("/api/v1/tenant/budget", json={"tenant_id": "filter-t2"})
        resp = client.get("/api/v1/audit", params={"tenant_id": "filter-t1"})
        data = resp.json()
        assert all(e["tenant"] == "filter-t1" for e in data["entries"])
