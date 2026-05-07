"""Purpose: verify finance approval packet HTTP endpoints.
Governance scope: create/list/get/approval/proof routes and default router
mounting for the M1 finance approval packet pilot.
Dependencies: FastAPI TestClient and finance approval router.
Invariants:
  - Created packets are policy-evaluated before read-model exposure.
  - Blocked packets export review proof without effects.
  - Approval actions create explicit approval/effect/closure state.
  - Default router mounting includes the finance approval API.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.finance_approval import (
    reset_finance_approval_packets_for_tests,
    router,
)
from mcoi_runtime.app.server_http import include_default_routers
from mcoi_runtime.persistence.finance_approval_store import FinanceApprovalPacketStore


class MetricsStub:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value


class FixedClock:
    def __call__(self) -> str:
        return "2026-05-05T12:00:00+00:00"


def _client() -> TestClient:
    reset_finance_approval_packets_for_tests()
    deps.set("clock", FixedClock())
    deps.set("metrics", MetricsStub())
    deps.set("finance_approval_store", FinanceApprovalPacketStore())
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _blocked_request() -> dict[str, object]:
    return {
        "case_id": "case-blocked-001",
        "tenant_id": "tenant-demo",
        "actor_id": "user-requester",
        "vendor_id": "vendor-acme",
        "invoice_id": "INV-BLOCKED-001",
        "minor_units": 1_200_000,
        "source_evidence_ref": "evidence:invoice:blocked",
        "risk": "high",
        "actor_limit_minor_units": 500_000,
        "tenant_limit_minor_units": 5_000_000,
        "vendor_evidence_status": "stale",
        "approval_status": "absent",
    }


def _success_request() -> dict[str, object]:
    return {
        "case_id": "case-success-001",
        "tenant_id": "tenant-demo",
        "actor_id": "user-requester",
        "vendor_id": "vendor-acme",
        "invoice_id": "INV-OK-001",
        "minor_units": 120_000,
        "source_evidence_ref": "evidence:invoice:success",
        "risk": "medium",
        "actor_limit_minor_units": 500_000,
        "tenant_limit_minor_units": 5_000_000,
        "vendor_evidence_status": "fresh",
        "approval_status": "granted",
    }


def test_create_list_get_and_proof_blocked_packet() -> None:
    client = _client()

    created = client.post("/api/v1/finance/approval-packets", json=_blocked_request())
    listed = client.get("/api/v1/finance/approval-packets", params={"tenant_id": "tenant-demo"})
    fetched = client.get("/api/v1/finance/approval-packets/case-blocked-001")
    proof = client.get("/api/v1/finance/approval-packets/case-blocked-001/proof")

    assert created.status_code == 200
    assert created.json()["packet"]["state"] == "requires_review"
    assert "budget_exceeded_actor_limit" in created.json()["policy_decision"]["reasons"]
    assert listed.json()["count"] == 1
    assert fetched.json()["packet"]["effect_refs"] == []
    assert proof.status_code == 200
    assert proof.json()["proof"]["final_state"] == "requires_review"
    assert proof.json()["proof"]["effect_refs"] == []


def test_approval_creates_effect_and_closed_proof() -> None:
    client = _client()
    client.post("/api/v1/finance/approval-packets", json=_success_request())

    approved = client.post(
        "/api/v1/finance/approval-packets/case-success-001/approval",
        json={
            "approver_id": "finance-admin",
            "approver_role": "finance_admin",
            "status": "granted",
            "create_email_handoff": True,
        },
    )
    proof = client.get("/api/v1/finance/approval-packets/case-success-001/proof")

    assert approved.status_code == 200
    assert approved.json()["packet"]["state"] == "closed_sent"
    assert len(approved.json()["packet"]["approval_refs"]) == 1
    assert len(approved.json()["packet"]["effect_refs"]) == 1
    assert proof.status_code == 200
    assert proof.json()["proof"]["closure_certificate_id"] == "closure:case-success-001:sent"
    assert proof.json()["proof"]["final_state"] == "closed_sent"


def test_operator_read_model_summarizes_blocked_and_closed_packets() -> None:
    client = _client()
    client.post("/api/v1/finance/approval-packets", json=_blocked_request())
    client.post("/api/v1/finance/approval-packets", json=_success_request())
    client.post(
        "/api/v1/finance/approval-packets/case-success-001/approval",
        json={"approver_id": "finance-admin", "status": "granted"},
    )

    read_model = client.get("/api/v1/finance/approval-packets/operator/read-model", params={"tenant_id": "tenant-demo"})
    body = read_model.json()

    assert read_model.status_code == 200
    assert body["visible_count"] == 2
    assert body["blocked_count"] == 1
    assert body["proof_ready_count"] == 2
    assert body["summary"]["case_count"] == 2
    assert body["packets"][0]["case_id"] == "case-blocked-001"
    assert "budget_exceeded_actor_limit" in body["packets"][0]["latest_policy_reasons"]
    assert body["packets"][1]["case_id"] == "case-success-001"
    assert body["packets"][1]["effect_ref_count"] == 1
    assert body["packets"][1]["proof_exportable"] is True


def test_invalid_state_and_missing_packet_fail_closed() -> None:
    client = _client()

    invalid = client.get("/api/v1/finance/approval-packets", params={"state": "unknown"})
    missing = client.get("/api/v1/finance/approval-packets/missing/proof")
    invalid_limit = client.get("/api/v1/finance/approval-packets/operator/read-model", params={"limit": 0})

    assert invalid.status_code == 400
    assert invalid.json()["detail"]["error_code"] == "invalid_state"
    assert missing.status_code == 404
    assert missing.json()["detail"]["error_code"] == "packet_not_found"
    assert invalid_limit.status_code == 400
    assert invalid_limit.json()["detail"]["error_code"] == "invalid_limit"


def test_default_routers_include_finance_approval_paths() -> None:
    reset_finance_approval_packets_for_tests()
    deps.set("clock", FixedClock())
    deps.set("metrics", MetricsStub())
    deps.set("finance_approval_store", FinanceApprovalPacketStore())
    app = FastAPI()
    include_default_routers(app)
    paths = {route.path for route in app.routes}

    assert "/api/v1/finance/approval-packets" in paths
    assert "/api/v1/finance/approval-packets/operator/read-model" in paths
    assert "/api/v1/finance/approval-packets/{case_id}" in paths
    assert "/api/v1/finance/approval-packets/{case_id}/proof" in paths
