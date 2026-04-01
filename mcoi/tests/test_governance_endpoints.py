"""Governance HTTP Endpoint Tests.

Integration tests for all new governance endpoints using FastAPI TestClient:
- Tenant gating lifecycle (register, update status, get gate, list gates)
- Ops endpoints (benchmarks, imports, proof bridge)
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app
    return TestClient(app)


# ═══ Tenant Gating Endpoints ═══


class TestTenantRegister:
    def test_register_new_tenant(self, client):
        resp = client.post("/api/v1/tenant/register", json={
            "tenant_id": "test-reg-1",
            "status": "onboarding",
            "reason": "new signup",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "test-reg-1"
        assert data["status"] == "onboarding"
        assert data["governed"] is True

    def test_register_active_tenant(self, client):
        resp = client.post("/api/v1/tenant/register", json={
            "tenant_id": "test-reg-2",
            "status": "active",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_register_invalid_status(self, client):
        resp = client.post("/api/v1/tenant/register", json={
            "tenant_id": "test-reg-3",
            "status": "nonexistent",
        })
        assert resp.status_code == 422
        assert "invalid status" in resp.json()["detail"]["error"]

    def test_register_duplicate_tenant(self, client):
        client.post("/api/v1/tenant/register", json={
            "tenant_id": "test-dup",
            "status": "active",
        })
        resp = client.post("/api/v1/tenant/register", json={
            "tenant_id": "test-dup",
            "status": "active",
        })
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]["error"]


class TestTenantStatusUpdate:
    def test_suspend_tenant(self, client):
        client.post("/api/v1/tenant/register", json={
            "tenant_id": "test-suspend",
            "status": "active",
        })
        resp = client.patch("/api/v1/tenant/test-suspend/status", json={
            "status": "suspended",
            "reason": "payment overdue",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

    def test_reactivate_tenant(self, client):
        client.post("/api/v1/tenant/register", json={
            "tenant_id": "test-react",
            "status": "active",
        })
        client.patch("/api/v1/tenant/test-react/status", json={"status": "suspended"})
        resp = client.patch("/api/v1/tenant/test-react/status", json={
            "status": "active",
            "reason": "payment received",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_invalid_transition(self, client):
        client.post("/api/v1/tenant/register", json={
            "tenant_id": "test-invalid-trans",
            "status": "active",
        })
        resp = client.patch("/api/v1/tenant/test-invalid-trans/status", json={
            "status": "onboarding",
        })
        assert resp.status_code == 422
        assert "invalid transition" in resp.json()["detail"]["error"]

    def test_update_unknown_tenant(self, client):
        resp = client.patch("/api/v1/tenant/unknown-tenant-xyz/status", json={
            "status": "suspended",
        })
        assert resp.status_code == 422
        assert "not registered" in resp.json()["detail"]["error"]


class TestTenantGateGet:
    def test_get_existing_gate(self, client):
        client.post("/api/v1/tenant/register", json={
            "tenant_id": "test-gate-get",
            "status": "active",
        })
        resp = client.get("/api/v1/tenant/test-gate-get/gate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "test-gate-get"
        assert data["status"] == "active"
        assert data["governed"] is True

    def test_get_unknown_gate(self, client):
        resp = client.get("/api/v1/tenant/nonexistent-tenant/gate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "unknown"


class TestTenantGatesList:
    def test_list_gates(self, client):
        resp = client.get("/api/v1/tenant/gates")
        assert resp.status_code == 200
        data = resp.json()
        assert "gates" in data
        assert "summary" in data
        assert data["governed"] is True


# ═══ Ops Endpoints ═══


class TestOpsBenchmarks:
    def test_run_benchmarks(self, client):
        resp = client.post("/api/v1/ops/benchmarks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["governed"] is True
        assert data["suite"] == "governance"
        assert data["benchmarks"] >= 8
        assert len(data["results"]) >= 8

    def test_benchmark_results_have_metrics(self, client):
        resp = client.post("/api/v1/ops/benchmarks")
        data = resp.json()
        for result in data["results"]:
            assert "name" in result
            assert "mean_us" in result
            assert "ops_per_second" in result
            assert result["ops_per_second"] > 0


class TestOpsImports:
    def test_analyze_imports(self, client):
        resp = client.get("/api/v1/ops/imports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["governed"] is True
        assert data["module_count"] > 100
        assert data["has_cycles"] is False

    def test_imports_depth_distribution(self, client):
        resp = client.get("/api/v1/ops/imports")
        data = resp.json()
        assert "depth_distribution" in data
        assert "max_depth" in data


class TestOpsProofBridge:
    def test_proof_bridge_status(self, client):
        resp = client.get("/api/v1/ops/proof-bridge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["governed"] is True
        assert "receipt_count" in data
        assert "lineage_count" in data
        assert "last_receipt_hash" in data
