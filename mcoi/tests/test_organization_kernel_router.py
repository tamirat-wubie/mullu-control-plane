"""Purpose: verify Organization Kernel HTTP routes.
Governance scope: organization bootstrap, pilot case plan, evidence, approvals,
gate decisions, terminal closure, learning admission, and default router mounting.
Dependencies: FastAPI TestClient, router deps, OrganizationKernel, and file store.
Invariants:
  - API writes pass through OrganizationKernel methods.
  - Case events are kernel-emitted and visible in read models.
  - Configured persistence receives each mutation snapshot.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.organization_kernel import (
    reset_organization_kernel_for_tests,
    router,
)
from mcoi_runtime.app.server_http import include_default_routers
from mcoi_runtime.contracts.organization_kernel import (
    PlanStepWorkerDispatchReceipt,
    PlanStepWorkerLeaseReceipt,
)
from mcoi_runtime.core.organization_kernel import OrganizationKernel
from mcoi_runtime.persistence.organization_kernel_store import FileOrganizationKernelStore


FIXED_CLOCK = "2026-05-27T12:00:00+00:00"


class MetricsStub:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value


class FixedClock:
    def __init__(self) -> None:
        self._base = datetime.fromisoformat(FIXED_CLOCK)
        self._counter = 0

    def __call__(self) -> str:
        value = self._base + timedelta(seconds=self._counter)
        self._counter += 1
        return value.isoformat()


class StubHttpResponse:
    """Context-managed urllib response fixture."""

    def __init__(self, *, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def _client(tmp_path: Path) -> tuple[TestClient, FileOrganizationKernelStore]:
    reset_organization_kernel_for_tests()
    clock = FixedClock()
    store = FileOrganizationKernelStore(tmp_path / "organization-kernel.json")
    deps.set("clock", clock)
    deps.set("metrics", MetricsStub())
    deps.set("organization_kernel", OrganizationKernel(clock=clock))
    deps.set("organization_kernel_store", store)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), store


def _bootstrap_and_open_pilot(client: TestClient) -> None:
    bootstrap = client.post(
        "/api/v1/orgs/org-mullu/bootstrap-minimum",
        json={"tenant_id": "tenant-mullu", "name": "Mullu"},
    )
    pilot = client.post(
        "/api/v1/cases/launch-gateway-pilot",
        json={"org_id": "org-mullu", "case_id": "case.launch_gateway_pilot"},
    )

    assert bootstrap.status_code == 200
    assert bootstrap.json()["department_count"] == 5
    assert pilot.status_code == 200
    assert pilot.json()["case"]["status"] == "planned"


def _signed_runtime_witness(*, secret: str) -> dict[str, Any]:
    payload = {
        "witness_id": "runtime-witness-test",
        "environment": "pilot",
        "runtime_status": "healthy",
        "gateway_status": "healthy",
        "responsibility_debt_clear": True,
        "latest_command_event_hash": "event-hash",
        "latest_anchor_id": "anchor-1",
        "latest_terminal_certificate_id": "terminal-1",
        "open_case_count": 0,
        "active_accepted_risk_count": 0,
        "unresolved_reconciliation_count": 0,
        "last_change_certificate_id": None,
        "signed_at": "2026-05-27T12:00:00+00:00",
        "signature_key_id": "runtime-witness-test",
    }
    return {**payload, "signature": _signature(secret, payload)}


def _signed_conformance_certificate(*, secret: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "certificate_id": "conf-0123456789abcdef",
        "environment": "pilot",
        "issued_at": "2026-05-27T12:00:00+00:00",
        "expires_at": "2026-05-27T12:30:00+00:00",
        "gateway_witness_valid": True,
        "runtime_witness_valid": True,
        "latest_anchor_valid": True,
        "command_closure_canary_passed": True,
        "capability_admission_canary_passed": True,
        "dangerous_capability_isolation_canary_passed": True,
        "streaming_budget_canary_passed": True,
        "lineage_query_canary_passed": True,
        "authority_obligation_canary_passed": True,
        "authority_responsibility_debt_clear": True,
        "authority_pending_approval_chain_count": 0,
        "authority_overdue_approval_chain_count": 0,
        "authority_open_obligation_count": 0,
        "authority_overdue_obligation_count": 0,
        "authority_escalated_obligation_count": 0,
        "authority_unowned_high_risk_capability_count": 0,
        "authority_directory_sync_receipt_valid": True,
        "mcp_capability_manifest_configured": True,
        "mcp_capability_manifest_valid": True,
        "mcp_capability_manifest_capability_count": 1,
        "capability_plan_bundle_canary_passed": True,
        "capability_plan_bundle_count": 1,
        "physical_worker_canary_passed": True,
        "physical_worker_canary_id": "physical-worker-canary-0123456789abcdef",
        "physical_worker_canary_artifact_hash": "1" * 64,
        "physical_worker_canary_evidence_count": 3,
        "capsule_registry_certified": True,
        "proof_coverage_matrix_current": True,
        "proof_coverage_declared_routes_classified": True,
        "proof_coverage_declared_route_count": 303,
        "proof_coverage_unclassified_route_count": 0,
        "known_limitations_aligned": False,
        "security_model_aligned": False,
        "terminal_status": "conformant_with_gaps",
        "open_conformance_gaps": ["known_limitations_documentation_drift"],
        "evidence_refs": ["gateway_witness:test"],
        "checks": [
            {
                "check_id": "gateway_witness_valid",
                "passed": True,
                "evidence_ref": "gateway_witness:test",
                "detail": "verified",
            }
        ],
        "signature_key_id": "runtime-conformance-test",
    }
    return {**payload, "signature": _signature(secret, payload)}


def _signature(secret: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature_payload = hashlib.sha256(canonical).hexdigest()
    signature = hmac.new(
        secret.encode("utf-8"),
        signature_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"hmac-sha256:{signature}"


def _admit_all_pilot_evidence(client: TestClient) -> None:
    requirements = (
        "executive_objective",
        "product_launch_boundary",
        "engineering_health_endpoint",
        "engineering_gateway_witness",
        "engineering_runtime_conformance",
        "security_public_claim_boundary",
        "security_approval",
        "finance_budget_check",
        "terminal_closure_certificate",
        "learning_admission_decision",
    )
    for requirement_id in requirements:
        evidence_ref = f"evidence:{requirement_id}"
        if requirement_id == "terminal_closure_certificate":
            evidence_ref = "terminal:gateway-pilot"
        response = client.post(
            "/api/v1/cases/case.launch_gateway_pilot/evidence",
            json={
                "evidence_ref": evidence_ref,
                "requirement_id": requirement_id,
                "submitted_by": "operator",
            },
        )
        assert response.status_code == 200
        assert response.json()["evidence"]["requirement_id"] == requirement_id


def _allow_all_plan_steps(client: TestClient) -> None:
    preconditions = {
        "executive_objective_freeze": ["objective_received"],
        "product_launch_boundary": ["objective_frozen"],
        "engineering_runtime_witness": ["launch_boundary_defined"],
        "security_claim_boundary": ["runtime_witness_collected"],
        "finance_budget_check": ["runtime_witness_collected"],
    }
    for step_id, checked in preconditions.items():
        response = client.post(
            f"/api/v1/cases/case.launch_gateway_pilot/plan-steps/{step_id}/gate",
            json={"checked_preconditions": checked},
        )
        assert response.status_code == 200
        assert response.json()["decision"]["status"] == "allowed"


def _closure_gate_evidence_refs() -> list[str]:
    return [
        "evidence:executive_objective",
        "evidence:product_launch_boundary",
        "evidence:engineering_health_endpoint",
        "evidence:engineering_gateway_witness",
        "evidence:engineering_runtime_conformance",
        "evidence:security_public_claim_boundary",
        "evidence:security_approval",
        "evidence:finance_budget_check",
    ]


def _terminal_closure_evidence_refs() -> list[str]:
    return [*_closure_gate_evidence_refs(), "terminal:gateway-pilot"]


def _record_engineering_dispatch_receipt_for_route(client: TestClient, requirement_id: str) -> tuple[str, str, str]:
    evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:product_launch_boundary",
            "requirement_id": "product_launch_boundary",
            "submitted_by": "operator",
        },
    )
    assert evidence.status_code == 200
    kernel = deps.get("organization_kernel")
    assert isinstance(kernel, OrganizationKernel)
    lease_id = f"lease.eng.gateway.{requirement_id}"
    dispatch_request_id = f"req.{requirement_id}"
    dispatch_receipt_id = f"receipt.{requirement_id}"
    lease = kernel.create_worker_lease_receipt(
        PlanStepWorkerLeaseReceipt(
            lease_id=lease_id,
            case_id="case.launch_gateway_pilot",
            step_id="engineering_runtime_witness",
            capability_id="engineering.gateway_runtime.verify",
            responsible_role_id="engineering.owner",
            requested_by_role_id="engineering.owner",
            dispatch_lease_preview_id=f"dispatch-lease-preview.{requirement_id}",
            queued_action="bind_worker_receipt",
            capability_action="verify_gateway_runtime",
            expected_effect="gateway_runtime_witnessed",
            evidence_refs=("evidence:product_launch_boundary",),
            timeout_seconds=900,
            budget_ref="budget:gateway-pilot",
            created_at=FIXED_CLOCK,
        )
    )
    kernel.record_worker_dispatch_receipt(
        PlanStepWorkerDispatchReceipt(
            dispatch_receipt_id=dispatch_receipt_id,
            dispatch_request_id=dispatch_request_id,
            case_id="case.launch_gateway_pilot",
            step_id="engineering_runtime_witness",
            worker_lease_id=lease.lease_id,
            capability_id="engineering.gateway_runtime.verify",
            responsible_role_id="engineering.owner",
            requested_by_role_id="engineering.owner",
            worker_id="worker:gateway-runtime",
            dispatch_intent="request_gateway_runtime_verification",
            expected_effect=lease.expected_effect,
            evidence_refs=lease.evidence_refs,
            lease_created_at=lease.created_at,
            dispatched_at=FIXED_CLOCK,
        )
    )
    return lease_id, dispatch_request_id, dispatch_receipt_id


def _readiness_closure_payload() -> dict[str, Any]:
    return {
        "submitted_by": "operator",
        "executive_objective": {
            "evidence_ref": "evidence:readiness:executive-objective",
            "metadata": {"objective_ref": "objective:gateway-pilot"},
        },
        "product_launch_boundary": {
            "evidence_ref": "evidence:readiness:product-launch-boundary",
            "metadata": {"launch_boundary_ref": "launch-boundary:pilot"},
        },
        "security_public_claim_boundary": {
            "evidence_ref": "evidence:readiness:security-public-claim",
            "metadata": {"claim_boundary_ref": "security:public-claim-boundary"},
        },
        "security_approval": {
            "evidence_ref": "evidence:readiness:security-approval",
            "metadata": {"approval_receipt_ref": "approval:security-dual-control"},
        },
        "finance_budget_check": {
            "evidence_ref": "evidence:readiness:finance-budget",
            "metadata": {"budget_ref": "budget:gateway-pilot"},
        },
        "approval_id": "approval:security-dual-control",
        "approved_by": "human-executive",
        "expected_effect": "gateway_pilot_ready",
        "observed_effect": "gateway_pilot_ready",
        "closure_evidence_refs": ["evidence:closure:gateway-pilot-readiness"],
        "terminal_certificate_id": "terminal:gateway-pilot-readiness",
    }


def _bind_verified_deployment_witness(
    client: TestClient,
    monkeypatch,
    *,
    auto_gate_engineering_step: bool = True,
) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_WITNESS_SECRET", "runtime-secret")
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    witness_payload = _signed_runtime_witness(secret="runtime-secret")
    conformance_payload = _signed_conformance_certificate(secret="conformance-secret")

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/deployment-witness",
        json={
            "gateway_url": "https://gateway.example",
            "expected_environment": "pilot",
            "auto_gate_engineering_step": auto_gate_engineering_step,
            "metadata": {"operator_action": "collect_gateway_pilot_evidence"},
        },
    )

    assert response.status_code == 200
    if auto_gate_engineering_step:
        assert response.json()["gate_decision"]["status"] == "allowed"
    else:
        assert response.json()["gate_decision"] is None


def test_bootstrap_open_pilot_read_model_and_persistence(tmp_path: Path) -> None:
    client, store = _client(tmp_path)

    _bootstrap_and_open_pilot(client)
    departments = client.get("/api/v1/orgs/org-mullu/departments")
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")
    events = client.get("/api/v1/cases/case.launch_gateway_pilot/events")
    restored = OrganizationKernel(clock=FixedClock())
    store.restore_kernel(restored)

    assert departments.status_code == 200
    assert departments.json()["count"] == 5
    assert fetched.status_code == 200
    assert fetched.json()["case"]["plan_id"] == "plan.launch_gateway_pilot.v1"
    assert fetched.json()["plan"]["steps"][0]["step_id"] == "executive_objective_freeze"
    assert events.status_code == 200
    assert events.json()["count"] == 2
    assert store.exists() is True
    assert restored.get_case("case.launch_gateway_pilot") is not None


def test_case_proof_timeline_reports_open_case_without_closure(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)

    response = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-timeline")
    payload = response.json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["summary"]["case_status"] == "planned"
    assert payload["summary"]["has_plan"] is True
    assert payload["summary"]["has_terminal_closure"] is False
    assert payload["summary"]["all_plan_steps_allowed"] is False
    assert payload["closure_certificate"] is None
    assert len(payload["plan_step_proof"]) == 5
    assert {step["gate_status"] for step in payload["plan_step_proof"]} == {"not_evaluated"}
    assert {item["kind"] for item in payload["proof_timeline"]} == {"case_event"}


def test_case_proof_explorer_reports_open_case_attention_without_mutation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-explorer")
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["read_only"] is True
    assert payload["terminal_status"] == "blocked_by_plan_gate"
    assert payload["source_timeline"]["case_id"] == "case.launch_gateway_pilot"
    assert len(payload["department_lanes"]) == 5
    assert {item["kind"] for item in payload["attention_items"]} == {
        "blocked_plan_step",
        "missing_evidence",
        "missing_terminal_closure",
    }
    assert all(item["present"] is False for item in payload["evidence_matrix"])
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_case_proof_explorer_html_view_is_read_only_and_escaped(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    created = client.post(
        "/api/v1/cases",
        json={
            "case_id": "case.html_escape",
            "org_id": "org-mullu",
            "department_id": "executive",
            "case_type": "launch_gateway_pilot",
            "goal": "<script>alert('proof')</script>",
            "risk": "low",
            "owner_role_id": "executive.owner",
            "assigned_department_ids": ["executive"],
        },
    )
    before = client.get("/api/v1/cases/case.html_escape").json()

    response = client.get("/api/v1/cases/case.html_escape/proof-explorer/view")
    after = client.get("/api/v1/cases/case.html_escape").json()

    assert created.status_code == 200
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Mullu OrgOS Proof Explorer" in response.text
    assert "json explorer" in response.text
    assert "proof timeline" in response.text
    assert "No records" in response.text
    assert "<script>alert('proof')</script>" not in response.text
    assert "&lt;script&gt;alert(&#x27;proof&#x27;)&lt;/script&gt;" in response.text
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_case_audit_explorer_reports_open_case_without_mutation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.get("/api/v1/cases/case.launch_gateway_pilot/audit-explorer")
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["read_only"] is True
    assert payload["terminal_status"] == "blocked_by_plan_gate"
    assert payload["summary"]["timeline_count"] == 2
    assert payload["summary"]["case_event_count"] == 2
    assert payload["summary"]["blocker_count"] == 8
    assert payload["summary"]["review_count"] == 6
    assert [item["sequence"] for item in payload["audit_timeline"]] == [1, 2]
    assert {item["layer"] for item in payload["audit_timeline"]} == {"case"}
    assert {item["kind"] for item in payload["attention_items"]} == {
        "blocked_plan_step",
        "missing_evidence",
        "missing_terminal_closure",
    }
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_case_audit_explorer_view_is_read_only_and_escaped(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    created = client.post(
        "/api/v1/cases",
        json={
            "case_id": "case.audit_escape",
            "org_id": "org-mullu",
            "department_id": "executive",
            "case_type": "launch_gateway_pilot",
            "goal": "<script>alert('audit')</script>",
            "risk": "low",
            "owner_role_id": "executive.owner",
            "assigned_department_ids": ["executive"],
        },
    )
    before = client.get("/api/v1/cases/case.audit_escape").json()

    audit = client.get("/api/v1/cases/case.audit_escape/audit-explorer")
    view = client.get("/api/v1/cases/case.audit_escape/audit-explorer/view")
    after = client.get("/api/v1/cases/case.audit_escape").json()

    assert created.status_code == 200
    assert audit.status_code == 200
    assert audit.json()["audit_id"] == "case-audit:case.audit_escape"
    assert audit.json()["summary"]["timeline_count"] == 1
    assert view.status_code == 200
    assert "text/html" in view.headers["content-type"]
    assert "Mullu OrgOS Case Audit Explorer" in view.text
    assert "json audit" in view.text
    assert "case bundle" in view.text
    assert "proof timeline" in view.text
    assert "proof explorer" in view.text
    assert "closure certificate" in view.text
    assert "<script>alert('audit')</script>" not in view.text
    assert "&lt;script&gt;alert(&#x27;audit&#x27;)&lt;/script&gt;" in view.text
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_case_step_handoffs_report_worker_receipt_binding_without_mutation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    lease_id, dispatch_request_id, dispatch_receipt_id = _record_engineering_dispatch_receipt_for_route(
        client,
        "engineering_health_endpoint",
    )
    bound = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/worker-receipt",
        json={
            "binding_id": "binding.eng.health",
            "requirement_id": "engineering_health_endpoint",
            "worker_lease_id": lease_id,
            "dispatch_request_id": dispatch_request_id,
            "dispatch_receipt_id": dispatch_receipt_id,
            "worker_output_hash": "hash-health",
            "receipt_evidence_refs": ["worker-evidence:/health"],
            "admitted_evidence_ref": "evidence:engineering_health_endpoint",
        },
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.get("/api/v1/cases/case.launch_gateway_pilot/step-handoffs")
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    handoffs = {
        item["step_id"]: item
        for item in payload["handoffs"]
    }
    engineering = handoffs["engineering_runtime_witness"]

    assert bound.status_code == 200
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["read_only"] is True
    assert payload["summary"]["step_count"] == 5
    assert payload["summary"]["dispatch_authority_granted"] is False
    assert payload["summary"]["receipt_bound_awaiting_evidence_count"] == 1
    assert payload["summary"]["awaiting_evidence_count"] == 3
    assert payload["summary"]["awaiting_gate_count"] == 1
    assert engineering["handoff_status"] == "receipt_bound_awaiting_evidence"
    assert engineering["next_action"] == "collect_required_evidence"
    assert engineering["dispatch_authority"] is False
    assert engineering["worker_dispatch_receipt_count"] == 1
    assert engineering["worker_receipt_count"] == 1
    assert engineering["evidence_refs"] == ["evidence:engineering_health_endpoint"]
    assert engineering["missing_evidence"] == [
        "engineering_gateway_witness",
        "engineering_runtime_conformance",
    ]
    assert all(item["dispatch_authority"] is False for item in payload["handoffs"])
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"]


def test_case_step_handoffs_view_is_read_only_and_escaped(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    created = client.post(
        "/api/v1/cases",
        json={
            "case_id": "case.handoff_escape",
            "org_id": "org-mullu",
            "department_id": "executive",
            "case_type": "launch_gateway_pilot",
            "goal": "<script>alert('handoff')</script>",
            "risk": "low",
            "owner_role_id": "executive.owner",
            "assigned_department_ids": ["executive"],
        },
    )
    before = client.get("/api/v1/cases/case.handoff_escape").json()

    handoffs = client.get("/api/v1/cases/case.handoff_escape/step-handoffs")
    view = client.get("/api/v1/cases/case.handoff_escape/step-handoffs/view")
    after = client.get("/api/v1/cases/case.handoff_escape").json()

    assert created.status_code == 200
    assert handoffs.status_code == 200
    assert handoffs.json()["summary"]["step_count"] == 0
    assert handoffs.json()["summary"]["dispatch_authority_granted"] is False
    assert handoffs.json()["attention_items"] == [
        {
            "kind": "missing_plan",
            "severity": "review",
            "ref": "case.handoff_escape",
            "message": "case has no governed plan",
        }
    ]
    assert view.status_code == 200
    assert "text/html" in view.headers["content-type"]
    assert "Mullu OrgOS Step Handoffs" in view.text
    assert "json handoffs" in view.text
    assert "proof timeline" in view.text
    assert "case audit" in view.text
    assert "No records" in view.text
    assert "<script>alert('handoff')</script>" not in view.text
    assert "&lt;script&gt;alert(&#x27;handoff&#x27;)&lt;/script&gt;" in view.text
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_case_plan_step_admission_preview_defers_missing_evidence_without_mutation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/admission-preview",
        json={
            "checked_preconditions": ["launch_boundary_defined"],
            "proposed_action": "bind_worker_receipt",
            "requested_by_role_id": "engineering.owner",
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["read_only"] is True
    assert payload["decision"] == "defer"
    assert payload["reason_code"] == "evidence_missing"
    assert payload["decision_set"] == ["allow", "block", "defer", "escalate", "simulate"]
    assert payload["execution_authority_granted"] is False
    assert payload["dispatch_authority_granted"] is False
    assert payload["receipt_binding_authority_granted"] is False
    assert payload["gate_preview"]["status"] == "blocked"
    assert payload["gate_preview"]["reason"] == "evidence_missing"
    assert payload["handoff"]["handoff_status"] == "awaiting_evidence"
    assert payload["causal_decision_trace"]["decision"] == "defer"
    assert payload["causal_decision_trace"]["guard_verdicts"]["evidence_sufficient"] == "Fail(evidence_missing)"
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_case_plan_step_admission_preview_allows_receipt_binding_without_dispatch(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert gate.status_code == 200
    assert gate.json()["decision"]["status"] == "allowed"
    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/admission-preview",
        json={
            "checked_preconditions": ["launch_boundary_defined"],
            "proposed_action": "bind_worker_receipt",
            "requested_by_role_id": "engineering.owner",
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["decision"] == "allow"
    assert payload["reason_code"] == "plan_step_gate_allowed"
    assert payload["execution_authority_granted"] is False
    assert payload["dispatch_authority_granted"] is False
    assert payload["receipt_binding_authority_granted"] is True
    assert payload["gate_preview"]["status"] == "allowed"
    assert payload["gate_preview"]["reason"] == "allowed"
    assert payload["handoff"]["handoff_status"] == "ready_for_worker_receipt"
    assert payload["causal_decision_trace"]["decision"] == "allow"
    assert payload["causal_decision_trace"]["guard_verdicts"]["authority_valid"] == "Pass"
    assert payload["causal_decision_trace"]["guard_verdicts"]["capability_certified"] == "Pass"
    assert payload["causal_decision_trace"]["guard_verdicts"]["receipt_emittable"] == "Pass"
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"]
    assert len(after["gate_decisions"]) == 1


def test_organization_action_queue_reports_deferred_handoff_actions_without_mutation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.get("/api/v1/orgs/org-mullu/action-queue")
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["read_only"] is True
    assert payload["summary"]["open_case_count"] == 1
    assert payload["summary"]["action_count"] == 5
    assert payload["summary"]["ready_action_count"] == 0
    assert payload["summary"]["review_action_count"] == 5
    assert payload["summary"]["defer_count"] == 5
    assert payload["summary"]["execution_authority_granted"] is False
    assert payload["summary"]["dispatch_authority_granted"] is False
    assert {item["next_action"] for item in payload["actions"]} == {"collect_required_evidence"}
    assert {item["admission_decision"] for item in payload["actions"]} == {"defer"}
    assert all(item["dispatch_authority_granted"] is False for item in payload["actions"])
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_organization_action_queue_reports_receipt_ready_step_without_dispatch(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.get("/api/v1/orgs/org-mullu/action-queue")
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    engineering = next(
        item for item in payload["actions"]
        if item["step_id"] == "engineering_runtime_witness"
    )

    assert gate.status_code == 200
    assert response.status_code == 200
    assert engineering["next_action"] == "bind_worker_receipt"
    assert engineering["handoff_status"] == "ready_for_worker_receipt"
    assert engineering["admission_decision"] == "allow"
    assert engineering["queue_severity"] == "ready"
    assert engineering["receipt_binding_authority_granted"] is True
    assert engineering["execution_authority_granted"] is False
    assert engineering["dispatch_authority_granted"] is False
    assert payload["summary"]["ready_action_count"] >= 1
    assert payload["summary"]["allow_count"] >= 1
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"]


def test_organization_action_queue_filters_ready_receipt_actions_without_mutation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?decision=allow&severity=ready&department_id=engineering"
        "&responsible_role_id=engineering.owner&next_action=bind_worker_receipt"
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert gate.status_code == 200
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["read_only"] is True
    assert payload["filters"] == {
        "decision": "allow",
        "severity": "ready",
        "department_id": "engineering",
        "responsible_role_id": "engineering.owner",
        "next_action": "bind_worker_receipt",
    }
    assert payload["summary"]["total_action_count"] == 5
    assert payload["summary"]["action_count"] == 1
    assert payload["summary"]["filter_count"] == 5
    assert payload["summary"]["ready_action_count"] == 1
    assert payload["summary"]["allow_count"] == 1
    assert payload["summary"]["execution_authority_granted"] is False
    assert payload["summary"]["dispatch_authority_granted"] is False
    assert payload["attention_items"] == []
    assert len(payload["actions"]) == 1
    assert payload["actions"][0]["department_id"] == "engineering"
    assert payload["actions"][0]["responsible_role_id"] == "engineering.owner"
    assert payload["actions"][0]["next_action"] == "bind_worker_receipt"
    assert payload["actions"][0]["admission_decision"] == "allow"
    assert payload["actions"][0]["execution_authority_granted"] is False
    assert payload["actions"][0]["dispatch_authority_granted"] is False
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"]


def test_organization_action_queue_selection_preview_simulates_visible_filtered_action_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=engineering&next_action=collect_required_evidence"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/selection-preview",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "engineering",
                "next_action": "collect_required_evidence",
            },
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["read_only"] is True
    assert payload["action_id"] == action_id
    assert payload["filters"] == {
        "department_id": "engineering",
        "next_action": "collect_required_evidence",
    }
    assert payload["queue_context"]["action_count"] == 1
    assert payload["queue_context"]["total_action_count"] == 5
    assert payload["selected_action"]["department_id"] == "engineering"
    assert payload["selected_action"]["next_action"] == "collect_required_evidence"
    assert payload["admission_preview"]["decision"] == "simulate"
    assert payload["admission_preview"]["reason_code"] == "evidence_missing_simulation_available"
    assert payload["selection_decision"] == "simulate"
    assert payload["simulation_available"] is True
    assert payload["workflow_projection"]["acyclic"] is True
    assert payload["workflow_projection"]["stage_count"] == 3
    assert payload["execution_authority_granted"] is False
    assert payload["dispatch_authority_granted"] is False
    assert payload["receipt_binding_authority_granted"] is False
    assert payload["receipt_ref"] is None
    assert "worker_dispatch" in payload["forbidden_effects"]
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_organization_action_queue_selection_preview_rejects_filtered_out_action_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    queue = client.get("/api/v1/orgs/org-mullu/action-queue").json()
    finance_action = next(
        item for item in queue["actions"]
        if item["department_id"] == "finance"
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/selection-preview",
        json={
            "action_id": finance_action["action_id"],
            "filters": {"department_id": "engineering"},
        },
    )
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "action_queue_selection_preview_rejected"
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_organization_action_queue_approval_packet_preview_defers_missing_evidence_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=security_compliance&next_action=collect_required_evidence"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/approval-packet-preview",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "security_compliance",
                "next_action": "collect_required_evidence",
            },
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["read_only"] is True
    assert payload["action_id"] == action_id
    assert payload["approval_packet_decision"] == "awaiting_evidence_before_approval"
    assert payload["required_approvals"] == ["security_approval"]
    assert payload["approval_count"] == 1
    assert payload["approval_roles"][0]["approval_scope"] == "security_approval"
    assert payload["approval_roles"][0]["self_approval_forbidden"] is True
    assert payload["evidence_ready"] is False
    assert "security_public_claim_boundary" in payload["missing_evidence"]
    assert "security_approval" in payload["missing_evidence"]
    assert payload["selection_preview"]["selection_decision"] == "simulate"
    assert payload["workflow_projection"]["acyclic"] is True
    assert payload["workflow_projection"]["stage_count"] == 3
    assert payload["approval_creation_authority_granted"] is False
    assert payload["dispatch_authority_granted"] is False
    assert payload["receipt_binding_authority_granted"] is False
    assert "approval_creation" in payload["forbidden_effects"]
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_organization_action_queue_approval_packet_preview_requires_approval_after_evidence_ready(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=security_compliance&next_action=evaluate_plan_step_gate"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/approval-packet-preview",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "security_compliance",
                "next_action": "evaluate_plan_step_gate",
            },
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["approval_packet_decision"] == "approval_required"
    assert payload["required_approvals"] == ["security_approval"]
    assert payload["evidence_ready"] is True
    assert payload["missing_evidence"] == []
    assert payload["selection_preview"]["selection_decision"] == "escalate"
    assert payload["selection_preview"]["reason_code"] == "approval_missing"
    assert payload["separation_of_duty"]["required"] is True
    assert payload["separation_of_duty"]["requesting_role_id"] == "security_compliance.owner"
    assert payload["separation_of_duty"]["self_approval_forbidden"] is True
    assert payload["operator_next_step"] == "open_explicit_approval_request_after_evidence_is_complete"
    assert payload["approval_creation_authority_granted"] is False
    assert payload["execution_authority_granted"] is False
    assert payload["dispatch_authority_granted"] is False
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"]


def test_organization_action_queue_approval_packet_preview_rejects_filtered_out_action_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    queue = client.get("/api/v1/orgs/org-mullu/action-queue").json()
    security_action = next(
        item for item in queue["actions"]
        if item["department_id"] == "security_compliance"
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/approval-packet-preview",
        json={
            "action_id": security_action["action_id"],
            "filters": {"department_id": "engineering"},
        },
    )
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "action_queue_approval_packet_preview_rejected"
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_organization_action_queue_dispatch_lease_preview_reports_ready_lease_without_dispatch(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=engineering&next_action=bind_worker_receipt"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/dispatch-lease-preview",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "engineering",
                "next_action": "bind_worker_receipt",
            },
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert gate.status_code == 200
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["read_only"] is True
    assert payload["lease_decision"] == "lease_request_ready"
    assert payload["lease_blockers"] == []
    assert payload["lease_blocker_count"] == 0
    assert payload["lease_scope"]["capability_id"] == "engineering.gateway_runtime.verify"
    assert payload["lease_scope"]["sandbox_required"] is True
    assert payload["lease_scope"]["receipt_required"] is True
    assert payload["operator_next_step"] == "open_bounded_worker_lease_request"
    assert payload["worker_lease_authority_granted"] is False
    assert payload["dispatch_authority_granted"] is False
    assert payload["receipt_binding_authority_granted"] is False
    assert "worker_lease_creation" in payload["forbidden_effects"]
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"]


def test_organization_action_queue_dispatch_lease_preview_simulates_missing_evidence_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=security_compliance&next_action=collect_required_evidence"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/dispatch-lease-preview",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "security_compliance",
                "next_action": "collect_required_evidence",
            },
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["lease_decision"] == "simulation_only"
    assert payload["selection_preview"]["selection_decision"] == "simulate"
    assert payload["lease_blockers"][0]["kind"] == "missing_evidence"
    assert "security_public_claim_boundary" in payload["lease_blockers"][0]["refs"]
    assert payload["missing_evidence"]
    assert payload["worker_lease_authority_granted"] is False
    assert payload["dispatch_authority_granted"] is False
    assert payload["workflow_projection"]["terminal_closure_condition"] == "preview_only_no_worker_lease"
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_organization_action_queue_dispatch_lease_preview_blocks_until_approval_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=security_compliance&next_action=evaluate_plan_step_gate"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/dispatch-lease-preview",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "security_compliance",
                "next_action": "evaluate_plan_step_gate",
            },
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 200
    assert payload["lease_decision"] == "awaiting_approval"
    assert payload["required_approvals"] == ["security_approval"]
    assert payload["lease_blockers"] == [
        {"kind": "approval_required", "refs": ["security_approval"]}
    ]
    assert payload["selection_preview"]["reason_code"] == "approval_missing"
    assert payload["operator_next_step"] == "complete_required_approval_before_lease"
    assert payload["worker_lease_authority_granted"] is False
    assert payload["dispatch_authority_granted"] is False
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"]


def test_organization_action_queue_dispatch_lease_preview_rejects_filtered_out_action_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    queue = client.get("/api/v1/orgs/org-mullu/action-queue").json()
    finance_action = next(
        item for item in queue["actions"]
        if item["department_id"] == "finance"
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/dispatch-lease-preview",
        json={
            "action_id": finance_action["action_id"],
            "filters": {"department_id": "engineering"},
        },
    )
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "action_queue_dispatch_lease_preview_rejected"
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_organization_action_queue_worker_lease_creates_receipt_without_dispatch(
    tmp_path: Path,
) -> None:
    client, store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=engineering&next_action=bind_worker_receipt"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/worker-lease",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "engineering",
                "next_action": "bind_worker_receipt",
            },
            "lease_id": "lease:engineering-runtime-witness",
            "requested_by_role_id": "engineering.owner",
            "timeout_seconds": 900,
            "budget_ref": "budget:gateway-pilot",
            "evidence_refs": [
                "evidence:engineering_health_endpoint",
                "evidence:engineering_gateway_witness",
                "evidence:engineering_runtime_conformance",
            ],
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    persisted = store.load_state()

    assert gate.status_code == 200
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["lease_created"] is True
    assert payload["worker_dispatch_started"] is False
    assert payload["receipt_binding_created"] is False
    assert payload["approval_created"] is False
    assert payload["terminal_closure_created"] is False
    assert payload["dispatch_lease_preview"]["lease_decision"] == "lease_request_ready"
    assert payload["worker_lease"]["lease_id"] == "lease:engineering-runtime-witness"
    assert payload["worker_lease"]["capability_id"] == "engineering.gateway_runtime.verify"
    assert payload["worker_lease"]["queued_action"] == "bind_worker_receipt"
    assert payload["worker_lease"]["capability_action"] == "verify_gateway_runtime"
    assert payload["worker_lease"]["metadata"]["worker_dispatch_started"] is False
    assert len(after["worker_leases"]) == 1
    assert after["worker_leases"][0]["lease_id"] == "lease:engineering-runtime-witness"
    assert len(persisted.worker_lease_receipts) == 1
    assert persisted.worker_lease_receipts[0].lease_id == "lease:engineering-runtime-witness"
    assert before["case"]["status"] == after["case"]["status"] == "planned"
    assert before["evidence"] == after["evidence"]
    assert before["approvals"] == after["approvals"]
    assert before["gate_decisions"] == after["gate_decisions"]
    assert after["events"][-1]["event_type"] == "plan_step_worker_lease_created"


def test_organization_action_queue_worker_lease_rejects_not_ready_selection_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=security_compliance&next_action=collect_required_evidence"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/worker-lease",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "security_compliance",
                "next_action": "collect_required_evidence",
            },
            "lease_id": "lease:security-missing-evidence",
            "requested_by_role_id": "security.owner",
            "timeout_seconds": 900,
            "budget_ref": "budget:gateway-pilot",
            "evidence_refs": ["evidence:security_public_claim_boundary"],
        },
    )
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "action_queue_worker_lease_rejected"
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []
    assert after["worker_leases"] == []


def test_organization_action_queue_worker_lease_rejects_duplicate_lease_without_extra_event(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=engineering&next_action=bind_worker_receipt"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    request_body = {
        "action_id": action_id,
        "filters": {
            "department_id": "engineering",
            "next_action": "bind_worker_receipt",
        },
        "lease_id": "lease:engineering-runtime-witness",
        "requested_by_role_id": "engineering.owner",
        "timeout_seconds": 900,
        "budget_ref": "budget:gateway-pilot",
        "evidence_refs": [
            "evidence:engineering_health_endpoint",
            "evidence:engineering_gateway_witness",
            "evidence:engineering_runtime_conformance",
        ],
    }

    first = client.post("/api/v1/orgs/org-mullu/action-queue/worker-lease", json=request_body)
    before_duplicate = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    duplicate = client.post("/api/v1/orgs/org-mullu/action-queue/worker-lease", json=request_body)
    after_duplicate = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    lease_events = [
        event for event in after_duplicate["events"]
        if event["event_type"] == "plan_step_worker_lease_created"
    ]

    assert first.status_code == 200
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"]["error_code"] == "action_queue_worker_lease_rejected"
    assert len(after_duplicate["worker_leases"]) == 1
    assert before_duplicate["events"] == after_duplicate["events"]
    assert len(lease_events) == 1
    assert lease_events[0]["payload"]["lease_id"] == "lease:engineering-runtime-witness"


def test_organization_action_queue_worker_dispatch_receipt_records_envelope_without_output_binding(
    tmp_path: Path,
) -> None:
    client, store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=engineering&next_action=bind_worker_receipt"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    lease_body = {
        "action_id": action_id,
        "filters": {
            "department_id": "engineering",
            "next_action": "bind_worker_receipt",
        },
        "lease_id": "lease:engineering-runtime-witness",
        "requested_by_role_id": "engineering.owner",
        "timeout_seconds": 900,
        "budget_ref": "budget:gateway-pilot",
        "evidence_refs": [
            "evidence:engineering_health_endpoint",
            "evidence:engineering_gateway_witness",
            "evidence:engineering_runtime_conformance",
        ],
    }
    lease = client.post("/api/v1/orgs/org-mullu/action-queue/worker-lease", json=lease_body)
    before_dispatch = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/worker-dispatch-receipt",
        json={
            "action_id": action_id,
            "filters": lease_body["filters"],
            "worker_lease_id": "lease:engineering-runtime-witness",
            "dispatch_request_id": "dispatch-request:engineering-runtime-witness",
            "dispatch_receipt_id": "dispatch-receipt:engineering-runtime-witness",
            "requested_by_role_id": "engineering.owner",
            "worker_id": "worker:gateway-runtime",
            "dispatch_intent": "request_gateway_runtime_verification",
            "evidence_refs": lease_body["evidence_refs"],
        },
    )
    payload = response.json()
    after_dispatch = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    persisted = store.load_state()
    dispatch_events = [
        event for event in after_dispatch["events"]
        if event["event_type"] == "plan_step_worker_dispatch_recorded"
    ]

    assert lease.status_code == 200
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["dispatch_envelope_created"] is True
    assert payload["worker_execution_started"] is False
    assert payload["worker_output_bound"] is False
    assert payload["evidence_admitted"] is False
    assert payload["receipt_binding_created"] is False
    assert payload["approval_created"] is False
    assert payload["terminal_closure_created"] is False
    assert payload["dispatch_authority_granted"] is False
    assert payload["dispatch_lease_preview"]["lease_decision"] == "lease_request_ready"
    assert payload["worker_dispatch_receipt"]["worker_lease_id"] == "lease:engineering-runtime-witness"
    assert payload["worker_dispatch_receipt"]["worker_id"] == "worker:gateway-runtime"
    assert payload["worker_dispatch_receipt"]["metadata"]["worker_execution_started"] is False
    assert len(after_dispatch["worker_dispatch_receipts"]) == 1
    assert len(persisted.worker_dispatch_receipts) == 1
    assert before_dispatch["case"]["status"] == after_dispatch["case"]["status"] == "planned"
    assert before_dispatch["evidence"] == after_dispatch["evidence"]
    assert before_dispatch["approvals"] == after_dispatch["approvals"]
    assert before_dispatch["gate_decisions"] == after_dispatch["gate_decisions"]
    assert len(dispatch_events) == 1
    assert dispatch_events[0]["payload"]["dispatch_receipt_id"] == "dispatch-receipt:engineering-runtime-witness"


def test_organization_action_queue_worker_dispatch_receipt_rejects_missing_lease_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=engineering&next_action=bind_worker_receipt"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/worker-dispatch-receipt",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "engineering",
                "next_action": "bind_worker_receipt",
            },
            "worker_lease_id": "lease:missing",
            "dispatch_request_id": "dispatch-request:missing",
            "dispatch_receipt_id": "dispatch-receipt:missing",
            "requested_by_role_id": "engineering.owner",
            "worker_id": "worker:gateway-runtime",
            "evidence_refs": [
                "evidence:engineering_health_endpoint",
                "evidence:engineering_gateway_witness",
                "evidence:engineering_runtime_conformance",
            ],
        },
    )
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "action_queue_worker_dispatch_receipt_rejected"
    assert before["events"] == after["events"]
    assert after["worker_dispatch_receipts"] == []
    assert before["evidence"] == after["evidence"]


def test_organization_action_queue_worker_dispatch_receipt_rejects_duplicate_dispatch_without_extra_event(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=engineering&next_action=bind_worker_receipt"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    evidence_refs = [
        "evidence:engineering_health_endpoint",
        "evidence:engineering_gateway_witness",
        "evidence:engineering_runtime_conformance",
    ]
    client.post(
        "/api/v1/orgs/org-mullu/action-queue/worker-lease",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "engineering",
                "next_action": "bind_worker_receipt",
            },
            "lease_id": "lease:engineering-runtime-witness",
            "requested_by_role_id": "engineering.owner",
            "timeout_seconds": 900,
            "budget_ref": "budget:gateway-pilot",
            "evidence_refs": evidence_refs,
        },
    )
    request_body = {
        "action_id": action_id,
        "filters": {
            "department_id": "engineering",
            "next_action": "bind_worker_receipt",
        },
        "worker_lease_id": "lease:engineering-runtime-witness",
        "dispatch_request_id": "dispatch-request:engineering-runtime-witness",
        "dispatch_receipt_id": "dispatch-receipt:engineering-runtime-witness",
        "requested_by_role_id": "engineering.owner",
        "worker_id": "worker:gateway-runtime",
        "evidence_refs": evidence_refs,
    }

    first = client.post("/api/v1/orgs/org-mullu/action-queue/worker-dispatch-receipt", json=request_body)
    before_duplicate = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    duplicate = client.post("/api/v1/orgs/org-mullu/action-queue/worker-dispatch-receipt", json=request_body)
    after_duplicate = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    dispatch_events = [
        event for event in after_duplicate["events"]
        if event["event_type"] == "plan_step_worker_dispatch_recorded"
    ]

    assert first.status_code == 200
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"]["error_code"] == "action_queue_worker_dispatch_receipt_rejected"
    assert len(after_duplicate["worker_dispatch_receipts"]) == 1
    assert before_duplicate["events"] == after_duplicate["events"]
    assert len(dispatch_events) == 1


def test_organization_action_queue_worker_dispatch_receipt_rejects_not_ready_selection_without_mutation(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    queue = client.get(
        "/api/v1/orgs/org-mullu/action-queue"
        "?department_id=security_compliance&next_action=collect_required_evidence"
    ).json()
    action_id = queue["actions"][0]["action_id"]
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/orgs/org-mullu/action-queue/worker-dispatch-receipt",
        json={
            "action_id": action_id,
            "filters": {
                "department_id": "security_compliance",
                "next_action": "collect_required_evidence",
            },
            "worker_lease_id": "lease:security-missing-evidence",
            "dispatch_request_id": "dispatch-request:security-missing-evidence",
            "dispatch_receipt_id": "dispatch-receipt:security-missing-evidence",
            "requested_by_role_id": "security.owner",
            "worker_id": "worker:security-review",
            "evidence_refs": ["evidence:security_public_claim_boundary"],
        },
    )
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "action_queue_worker_dispatch_receipt_rejected"
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []
    assert after["worker_dispatch_receipts"] == []


def test_organization_action_queue_view_is_read_only_and_escaped(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    bootstrap = client.post(
        "/api/v1/orgs/org-mullu/bootstrap-minimum",
        json={"tenant_id": "tenant-mullu", "name": "<script>alert('queue')</script>"},
    )
    pilot = client.post(
        "/api/v1/cases/launch-gateway-pilot",
        json={"org_id": "org-mullu", "case_id": "case.launch_gateway_pilot"},
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    queue = client.get("/api/v1/orgs/org-mullu/action-queue")
    view = client.get("/api/v1/orgs/org-mullu/action-queue/view")
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert bootstrap.status_code == 200
    assert pilot.status_code == 200
    assert queue.status_code == 200
    assert view.status_code == 200
    assert "text/html" in view.headers["content-type"]
    assert "Mullu OrgOS Action Queue" in view.text
    assert "json queue" in view.text
    assert "case portfolio" in view.text
    assert "authority map" in view.text
    assert "collect_required_evidence" in view.text
    assert "<script>alert('queue')</script>" not in view.text
    assert "&lt;script&gt;alert(&#x27;queue&#x27;)&lt;/script&gt;" in view.text
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_case_private_pilot_live_rehearsal_binds_preview_receipts_without_mutation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/private-pilot/rehearsal",
        json={
            "checked_preconditions": ["launch_boundary_defined"],
            "proposed_action": "bind_worker_receipt",
            "requested_by_role_id": "engineering.owner",
            "allow_simulation_when_blocked": True,
        },
    )
    payload = response.json()
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    branches = {
        branch["branch_id"]: branch
        for branch in payload["story"]["uao_branches"]
    }

    assert response.status_code == 200
    assert payload["operation"] == "private_pilot_live_rehearsal"
    assert payload["read_only"] is True
    assert payload["governed"] is True
    assert payload["execution_authority_granted"] is False
    assert payload["dispatch_authority_granted"] is False
    assert payload["admission_preview"]["decision"] == "simulate"
    assert payload["admission_preview"]["gate_preview"]["reason"] == "evidence_missing"
    assert payload["rehearsal_uao"]["decision"]["status"] == "simulate"
    assert payload["rehearsal_uao"]["effect_bearing"] is False
    assert payload["receipt_ref"] == payload["rehearsal_uao"]["closure"]["closure_receipt_ref"]
    assert payload["story"]["request"]["tenant_id"] == "tenant-mullu"
    assert payload["story"]["request"]["org_id"] == "org-mullu"
    assert payload["story"]["request"]["case_id"] == "case.launch_gateway_pilot"
    assert payload["story"]["authority_boundary"]["execution_authority_granted"] is False
    assert branches["rehearsal"]["source_ref"] == "action://orgos-private-pilot-live-rehearsal"
    assert branches["rehearsal"]["receipt_refs"]
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_organization_action_queue_view_preserves_filters(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    view = client.get(
        "/api/v1/orgs/org-mullu/action-queue/view"
        "?department_id=engineering&next_action=collect_required_evidence"
    )
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert view.status_code == 200
    assert "text/html" in view.headers["content-type"]
    assert "Mullu OrgOS Action Queue" in view.text
    assert "Filters" in view.text
    assert "department_id" in view.text
    assert "engineering" in view.text
    assert "next_action" in view.text
    assert "collect_required_evidence" in view.text
    assert "json queue" in view.text
    assert "department_id=engineering&amp;next_action=collect_required_evidence" in view.text
    assert "total_action_count" in view.text
    assert "filter_count" in view.text
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_department_registry_view_is_read_only_and_escaped(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    organization = client.post(
        "/api/v1/orgs",
        json={"org_id": "org-dept", "tenant_id": "tenant-dept", "name": "Department Test"},
    )
    created = client.post(
        "/api/v1/departments",
        json={
            "department_id": "research_ops",
            "org_id": "org-dept",
            "name": "<script>alert('dept')</script>",
            "mission": "Control research case intake and proof boundaries.",
            "owns": ["research_cases"],
            "allowed_case_types": ["launch_gateway_pilot"],
            "allowed_capabilities": ["research.case.review"],
            "required_evidence": ["research_case_receipt"],
            "escalation_departments": ["executive"],
            "metrics": ["unreviewed_case_count"],
            "failure_modes": ["unbounded_research_claim"],
        },
    )
    before = client.get("/api/v1/orgs/org-dept/departments").json()

    registry = client.get("/api/v1/orgs/org-dept/department-registry")
    view = client.get("/api/v1/orgs/org-dept/department-registry/view")
    after = client.get("/api/v1/orgs/org-dept/departments").json()

    assert organization.status_code == 200
    assert created.status_code == 200
    assert registry.status_code == 200
    assert registry.json()["summary"]["department_count"] == 1
    assert registry.json()["summary"]["review_department_count"] == 1
    assert registry.json()["departments"][0]["readiness"] == "needs_review"
    assert registry.json()["departments"][0]["readiness_gaps"] == [
        "missing_owner_role",
        "missing_capability:research.case.review",
        "missing_evidence_rule:research_case_receipt",
    ]
    assert view.status_code == 200
    assert "text/html" in view.headers["content-type"]
    assert "Mullu OrgOS Department Registry" in view.text
    assert "json registry" in view.text
    assert "department list" in view.text
    assert "<script>alert('dept')</script>" not in view.text
    assert "&lt;script&gt;alert(&#x27;dept&#x27;)&lt;/script&gt;" in view.text
    assert before == after


def test_authority_map_view_is_read_only_escaped_and_chained(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    bootstrap = client.post(
        "/api/v1/orgs/org-map/bootstrap-minimum",
        json={"tenant_id": "tenant-map", "name": "<script>alert('map')</script>"},
    )
    before = client.get("/api/v1/orgs/org-map/departments").json()

    authority_map = client.get("/api/v1/orgs/org-map/authority-map")
    view = client.get("/api/v1/orgs/org-map/authority-map/view")
    after = client.get("/api/v1/orgs/org-map/departments").json()
    payload = authority_map.json()
    departments = {
        item["department"]["department_id"]: item
        for item in payload["departments"]
    }
    executive_chain = departments["executive"]["role_authority_chains"][0]
    executive_authority = executive_chain["authority_chain"][0]

    assert bootstrap.status_code == 200
    assert authority_map.status_code == 200
    assert payload["read_only"] is True
    assert payload["summary"]["department_count"] == 5
    assert payload["summary"]["mapped_department_count"] == 5
    assert payload["summary"]["map_gap_count"] == 0
    assert departments["executive"]["map_status"] == "mapped"
    assert executive_chain["role"]["role_id"] == "executive.owner"
    assert executive_authority["authority_rule"]["rule_id"] == "authority.executive.objective.freeze"
    assert executive_authority["capability_ids"] == ["executive.objective.freeze"]
    assert executive_authority["evidence_requirement_ids"] == [
        "executive_objective",
        "learning_admission_decision",
        "terminal_closure_certificate",
    ]
    assert executive_authority["escalation_path"][0]["department_id"] == "security_compliance"
    assert view.status_code == 200
    assert "text/html" in view.headers["content-type"]
    assert "Mullu OrgOS Authority Map" in view.text
    assert "json authority map" in view.text
    assert "department registry" in view.text
    assert "<script>alert('map')</script>" not in view.text
    assert "&lt;script&gt;alert(&#x27;map&#x27;)&lt;/script&gt;" in view.text
    assert before == after


def test_authority_map_reports_unresolved_department_bindings(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    organization = client.post(
        "/api/v1/orgs",
        json={"org_id": "org-map-gap", "tenant_id": "tenant-map-gap", "name": "Gap Map"},
    )
    department = client.post(
        "/api/v1/departments",
        json={
            "department_id": "research_ops",
            "org_id": "org-map-gap",
            "name": "Research Ops",
            "mission": "Control research case intake and proof boundaries.",
            "owns": ["research_cases"],
            "allowed_case_types": ["launch_gateway_pilot"],
            "allowed_capabilities": ["research.case.review"],
            "required_evidence": ["research_case_receipt"],
            "escalation_departments": ["missing_escalation"],
            "metrics": ["unreviewed_case_count"],
            "failure_modes": ["unbounded_research_claim"],
        },
    )
    before = client.get("/api/v1/orgs/org-map-gap/departments").json()

    authority_map = client.get("/api/v1/orgs/org-map-gap/authority-map")
    after = client.get("/api/v1/orgs/org-map-gap/departments").json()
    payload = authority_map.json()
    row = payload["departments"][0]

    assert organization.status_code == 200
    assert department.status_code == 200
    assert authority_map.status_code == 200
    assert payload["summary"]["department_count"] == 1
    assert payload["summary"]["mapped_department_count"] == 0
    assert payload["summary"]["review_department_count"] == 1
    assert payload["summary"]["map_gap_count"] == 4
    assert row["map_status"] == "needs_review"
    assert row["gaps"] == [
        "missing_capability:research.case.review",
        "missing_evidence_rule:research_case_receipt",
        "missing_owner_role",
        "unknown_escalation_department:missing_escalation",
    ]
    assert row["escalation_path"] == [
        {"department_id": "missing_escalation", "name": None, "known": False}
    ]
    assert payload["attention_items"] == [
        {
            "kind": "authority_map_gap",
            "severity": "review",
            "ref": "research_ops",
            "message": "department authority map has unresolved bindings",
            "gaps": row["gaps"],
        }
    ]
    assert before == after


def test_case_portfolio_view_is_read_only_escaped_and_grouped(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    created = client.post(
        "/api/v1/cases",
        json={
            "case_id": "case.portfolio_escape",
            "org_id": "org-mullu",
            "department_id": "executive",
            "case_type": "launch_gateway_pilot",
            "goal": "<script>alert('portfolio')</script>",
            "risk": "low",
            "owner_role_id": "executive.owner",
            "assigned_department_ids": ["executive"],
        },
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    portfolio = client.get("/api/v1/orgs/org-mullu/case-portfolio")
    view = client.get("/api/v1/orgs/org-mullu/case-portfolio/view")
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    payload = portfolio.json()
    cases = {
        item["case"]["case_id"]: item
        for item in payload["cases"]
    }
    departments = {
        item["department_id"]: item
        for item in payload["department_lanes"]
    }

    assert created.status_code == 200
    assert portfolio.status_code == 200
    assert payload["read_only"] is True
    assert payload["summary"]["case_count"] == 2
    assert payload["summary"]["open_case_count"] == 2
    assert payload["summary"]["closed_case_count"] == 0
    assert payload["summary"]["blocked_case_count"] == 1
    assert payload["summary"]["review_case_count"] == 2
    assert payload["summary"]["attention_count"] == 4
    assert cases["case.launch_gateway_pilot"]["terminal_status"] == "blocked_by_plan_gate"
    assert cases["case.launch_gateway_pilot"]["blocked_step_count"] == 5
    assert cases["case.portfolio_escape"]["terminal_status"] == "awaiting_plan"
    assert departments["executive"]["primary_case_count"] == 2
    assert departments["executive"]["assigned_case_count"] == 2
    assert view.status_code == 200
    assert "text/html" in view.headers["content-type"]
    assert "Mullu OrgOS Case Portfolio" in view.text
    assert "json portfolio" in view.text
    assert "department registry" in view.text
    assert "authority map" in view.text
    assert "<script>alert('portfolio')</script>" not in view.text
    assert "&lt;script&gt;alert(&#x27;portfolio&#x27;)&lt;/script&gt;" in view.text
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"]


def test_case_portfolio_reports_closed_verified_case(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": ["evidence:learning_admission_decision"],
        },
    )

    response = client.get("/api/v1/orgs/org-mullu/case-portfolio")
    payload = response.json()

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert learning.status_code == 200
    assert response.status_code == 200
    assert payload["summary"]["case_count"] == 1
    assert payload["summary"]["open_case_count"] == 0
    assert payload["summary"]["closed_case_count"] == 1
    assert payload["summary"]["blocked_case_count"] == 0
    assert payload["summary"]["review_case_count"] == 0
    assert payload["summary"]["terminal_closure_count"] == 1
    assert payload["summary"]["learning_admitted_count"] == 1
    assert payload["attention_items"] == []
    assert payload["cases"][0]["terminal_status"] == "closed_verified"
    assert payload["cases"][0]["has_terminal_closure"] is True
    assert payload["cases"][0]["effect_reconciled"] is True
    assert payload["cases"][0]["learning_admitted"] is True


def test_closure_certificate_reports_required_gate_evidence_before_closure(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)

    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    view = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate/view")
    explorer = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-explorer")
    portfolio = client.get("/api/v1/orgs/org-mullu/case-portfolio")
    readiness = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness")

    assert approval.status_code == 200
    assert certificate.status_code == 200
    assert certificate.json()["terminal_status"] == "awaiting_closure"
    assert certificate.json()["closure_gate_evidence"]["required_gate_evidence_refs"] == _closure_gate_evidence_refs()
    assert certificate.json()["closure_gate_evidence"]["admitted_gate_evidence_refs"] == _closure_gate_evidence_refs()
    assert certificate.json()["closure_gate_evidence"]["unavailable_gate_evidence_refs"] == []
    assert certificate.json()["closure_gate_evidence"]["omitted_gate_evidence_refs"] == []
    assert {item["kind"] for item in certificate.json()["attention_items"]} == {
        "missing_terminal_closure",
        "closure_gate_evidence_required",
    }
    assert view.status_code == 200
    assert "Gate Evidence" in view.text
    assert "evidence:engineering_gateway_witness" in view.text
    assert "closure_gate_evidence_required" in {item["kind"] for item in explorer.json()["attention_items"]}
    assert "closure_gate_evidence_required" in {item["kind"] for item in portfolio.json()["attention_items"]}
    assert readiness.json()["ready_to_close"] is True
    assert readiness.json()["required_closure_evidence_refs"] == _closure_gate_evidence_refs()


def test_case_close_rejects_unadmitted_terminal_certificate_evidence(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": [*_closure_gate_evidence_refs(), "terminal:unadmitted"],
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:unadmitted",
        },
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")

    assert approval.status_code == 200
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "case_closure_rejected"
    assert fetched.json()["case"]["status"] == "planned"
    assert fetched.json()["closure"] is None


def test_closure_certificate_reports_stale_gate_after_newer_evidence(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    newer_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )

    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    view = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate/view")
    explorer = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-explorer")
    portfolio = client.get("/api/v1/orgs/org-mullu/case-portfolio")
    readiness = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness")

    assert approval.status_code == 200
    assert newer_evidence.status_code == 200
    assert certificate.status_code == 200
    assert certificate.json()["closure_gate_evidence"]["gate_decisions_fresh"] is False
    assert certificate.json()["closure_gate_evidence"]["stale_gate_step_ids"] == ["engineering_runtime_witness"]
    assert certificate.json()["closure_gate_evidence"]["newer_gate_evidence_refs"] == [
        "evidence:engineering_health_endpoint:v2",
    ]
    assert certificate.json()["closure_gate_evidence"]["ready_for_closure_packet"] is False
    assert "closure_gate_decision_stale" in {item["kind"] for item in certificate.json()["attention_items"]}
    assert view.status_code == 200
    assert "Gate Freshness" in view.text
    assert "evidence:engineering_health_endpoint:v2" in view.text
    assert explorer.json()["terminal_status"] == "awaiting_gate_refresh"
    assert "closure_gate_decision_stale" in {item["kind"] for item in explorer.json()["attention_items"]}
    assert "closure_gate_decision_stale" in {item["kind"] for item in portfolio.json()["attention_items"]}
    assert portfolio.json()["cases"][0]["terminal_status"] == "awaiting_gate_refresh"
    assert readiness.json()["ready_to_close"] is False
    assert readiness.json()["preview_ready_to_close"] is True
    assert readiness.json()["terminal_status"] == "awaiting_gate_refresh"
    assert readiness.json()["stale_gate_step_ids"] == ["engineering_runtime_witness"]

    refreshed_gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    refreshed_certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    refreshed_readiness = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness")

    assert refreshed_gate.status_code == 200
    assert "evidence:engineering_health_endpoint:v2" in refreshed_gate.json()["decision"]["evidence_refs"]
    assert refreshed_certificate.json()["closure_gate_evidence"]["gate_decisions_fresh"] is True
    assert refreshed_certificate.json()["closure_gate_evidence"]["stale_gate_decisions"] == []
    assert "closure_gate_decision_stale" not in {
        item["kind"] for item in refreshed_certificate.json()["attention_items"]
    }
    assert refreshed_readiness.json()["ready_to_close"] is True


def test_gateway_pilot_can_close_and_bind_learning(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": ["evidence:learning_admission_decision"],
        },
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")

    assert approval.status_code == 200
    assert approval.json()["approval"]["role_id"] == "executive.owner"
    assert closure.status_code == 200
    assert closure.json()["closure"]["terminal_disposition"] == "committed"
    assert learning.status_code == 200
    assert learning.json()["learning_admission"]["admitted"] is True
    assert fetched.json()["case"]["status"] == "closed"
    assert fetched.json()["closure"]["terminal_certificate_id"] == "terminal:gateway-pilot"


def test_learning_binding_requires_admission_evidence_refs(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": [],
        },
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert learning.status_code == 400
    assert learning.json()["detail"]["error_code"] == "learning_admission_rejected"
    assert fetched.json()["learning_bindings"] == []


def test_learning_binding_rejects_unadmitted_admission_evidence_refs(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": ["evidence:unadmitted_learning_decision"],
        },
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert learning.status_code == 400
    assert learning.json()["detail"]["error_code"] == "learning_admission_rejected"
    assert fetched.json()["learning_bindings"] == []


def test_learning_binding_rejects_non_decision_evidence_refs(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": ["evidence:executive_objective"],
        },
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert learning.status_code == 400
    assert learning.json()["detail"]["error_code"] == "learning_admission_rejected"
    assert fetched.json()["learning_bindings"] == []


def test_case_proof_timeline_reports_closure_certificate_and_learning(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": ["evidence:learning_admission_decision"],
        },
    )

    response = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-timeline")
    payload = response.json()
    timeline_kinds = {item["kind"] for item in payload["proof_timeline"]}

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert learning.status_code == 200
    assert response.status_code == 200
    assert payload["summary"]["case_status"] == "closed"
    assert payload["summary"]["all_plan_steps_allowed"] is True
    assert payload["summary"]["has_terminal_closure"] is True
    assert payload["summary"]["learning_binding_count"] == 1
    assert payload["closure_certificate"]["terminal_certificate_id"] == "terminal:gateway-pilot"
    assert payload["closure_certificate"]["reconciliation"]["status"] == "match"
    assert payload["closure_certificate"]["effect_reconciled"] is True
    assert payload["closure_certificate"]["learning_admitted"] is True
    assert payload["closure_certificate"]["learning_admissions"][0]["evidence_refs"] == [
        "evidence:learning_admission_decision",
    ]
    learning_events = [item for item in payload["proof_timeline"] if item["kind"] == "learning_admission"]
    assert learning_events[0]["payload"]["evidence_refs"] == ["evidence:learning_admission_decision"]
    assert {step["gate_status"] for step in payload["plan_step_proof"]} == {"allowed"}
    assert {
        "approval",
        "case_event",
        "effect_reconciliation",
        "evidence",
        "gate_decision",
        "learning_admission",
        "terminal_closure",
    }.issubset(timeline_kinds)


def test_case_closure_certificate_view_is_read_only_and_escaped(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    escaped_certificate_id = "<script>alert('terminal')</script>"
    certificate_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": escaped_certificate_id,
            "requirement_id": "terminal_closure_certificate",
            "submitted_by": "operator",
        },
    )
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": [*_closure_gate_evidence_refs(), escaped_certificate_id],
            "terminal_disposition": "committed",
            "terminal_certificate_id": escaped_certificate_id,
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": ["evidence:learning_admission_decision"],
        },
    )
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    view = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate/view")
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert approval.status_code == 200
    assert certificate_evidence.status_code == 200
    assert closure.status_code == 200
    assert learning.status_code == 200
    assert certificate.status_code == 200
    assert certificate.json()["terminal_status"] == "closed_verified"
    assert certificate.json()["closure_certificate"]["effect_reconciled"] is True
    assert certificate.json()["closure_certificate"]["learning_admitted"] is True
    assert certificate.json()["learning_admissions"][0]["evidence_refs"] == [
        "evidence:learning_admission_decision",
    ]
    assert certificate.json()["closure_gate_evidence"]["required_gate_evidence_refs"] == _closure_gate_evidence_refs()
    assert certificate.json()["closure_gate_evidence"]["closure_evidence_refs"] == [
        *_closure_gate_evidence_refs(),
        escaped_certificate_id,
    ]
    assert certificate.json()["closure_gate_evidence"]["omitted_gate_evidence_refs"] == []
    assert certificate.json()["attention_items"] == []
    assert view.status_code == 200
    assert "text/html" in view.headers["content-type"]
    assert "Mullu OrgOS Terminal Closure Certificate" in view.text
    assert "json certificate" in view.text
    assert "proof timeline" in view.text
    assert "proof explorer" in view.text
    assert "evidence:learning_admission_decision" in view.text
    assert escaped_certificate_id not in view.text
    assert "&lt;script&gt;alert(&#x27;terminal&#x27;)&lt;/script&gt;" in view.text
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"]


def test_closed_case_reports_closure_packet_drift_after_gate_refresh(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": ["evidence:learning_admission_decision"],
        },
    )
    newer_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    refreshed_gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    view = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate/view")
    explorer = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-explorer")
    portfolio = client.get("/api/v1/orgs/org-mullu/case-portfolio")
    readiness = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert learning.status_code == 200
    assert newer_evidence.status_code == 200
    assert refreshed_gate.status_code == 200
    assert certificate.status_code == 200
    assert certificate.json()["terminal_status"] == "closed_packet_drift"
    assert certificate.json()["closure_gate_evidence"]["gate_decisions_fresh"] is True
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift"] is True
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_refs"] == [
        "evidence:engineering_health_endpoint:v2",
    ]
    assert certificate.json()["closure_gate_evidence"]["superseded_closure_evidence_refs"] == [
        "evidence:engineering_health_endpoint",
    ]
    assert certificate.json()["closure_gate_evidence"]["omitted_gate_evidence_refs"] == [
        "evidence:engineering_health_endpoint:v2",
    ]
    assert "closure_packet_drift" in {item["kind"] for item in certificate.json()["attention_items"]}
    assert "closure_gate_decision_stale" not in {item["kind"] for item in certificate.json()["attention_items"]}
    assert view.status_code == 200
    assert "Closure Packet Drift" in view.text
    assert "evidence:engineering_health_endpoint:v2" in view.text
    assert explorer.json()["terminal_status"] == "closed_packet_drift"
    assert "closure_packet_drift" in {item["kind"] for item in explorer.json()["attention_items"]}
    assert portfolio.json()["cases"][0]["terminal_status"] == "closed_packet_drift"
    assert "closure_packet_drift" in {item["kind"] for item in portfolio.json()["attention_items"]}
    assert readiness.json()["terminal_status"] == "closed_packet_drift"
    assert readiness.json()["closure_packet_drift"] is True
    assert readiness.json()["closure_packet_drift_refs"] == ["evidence:engineering_health_endpoint:v2"]


def test_closure_packet_drift_accepts_remediation_routing(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": ["evidence:learning_admission_decision"],
        },
    )
    newer_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    remediation_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:closure_drift_review",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
        },
    )
    refreshed_gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )
    remediation = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediations",
        json={
            "remediation_id": "remediation:gateway-pilot-drift-review",
            "closure_id": closure.json()["closure"]["closure_id"],
            "terminal_disposition": "requires_review",
            "drift_evidence_refs": ["evidence:engineering_health_endpoint:v2"],
            "superseded_evidence_refs": ["evidence:engineering_health_endpoint"],
            "authority_ref": "approval:security-dual-control",
            "evidence_refs": ["evidence:closure_drift_review"],
        },
    )

    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    view = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate/view")
    explorer = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-explorer")
    portfolio = client.get("/api/v1/orgs/org-mullu/case-portfolio")
    readiness = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness")
    events = client.get("/api/v1/cases/case.launch_gateway_pilot/events")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert learning.status_code == 200
    assert newer_evidence.status_code == 200
    assert remediation_evidence.status_code == 200
    assert refreshed_gate.status_code == 200
    assert remediation.status_code == 200
    assert remediation.json()["closure_drift_remediation"]["terminal_disposition"] == "requires_review"
    assert certificate.status_code == 200
    assert certificate.json()["terminal_status"] == "closed_drift_review_required"
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift"] is True
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediated"] is True
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediation"]["remediation_id"] == (
        "remediation:gateway-pilot-drift-review"
    )
    assert "closure_packet_drift_remediated" in {item["kind"] for item in certificate.json()["attention_items"]}
    assert "closure_packet_drift" not in {item["kind"] for item in certificate.json()["attention_items"]}
    assert "closure_gate_evidence_omitted" not in {item["kind"] for item in certificate.json()["attention_items"]}
    assert view.status_code == 200
    assert "Closure Drift Remediations" in view.text
    assert "remediation:gateway-pilot-drift-review" in view.text
    assert explorer.json()["terminal_status"] == "closed_drift_review_required"
    assert "closure_drift_remediation" in explorer.json()["proof_sections"]
    assert portfolio.json()["cases"][0]["terminal_status"] == "closed_drift_review_required"
    assert readiness.json()["terminal_status"] == "closed_drift_review_required"
    assert readiness.json()["closure_packet_drift_remediated"] is True
    assert "closure_drift_remediation_bound" in {item["event_type"] for item in events.json()["events"]}


def test_closure_packet_drift_remediation_rejects_mismatched_refs(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:closure_drift_review",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediations",
        json={
            "remediation_id": "remediation:gateway-pilot-drift-review",
            "closure_id": closure.json()["closure"]["closure_id"],
            "terminal_disposition": "accepted_risk",
            "drift_evidence_refs": ["evidence:not-current-drift"],
            "authority_ref": "approval:security-dual-control",
            "evidence_refs": ["evidence:closure_drift_review"],
        },
    )

    assert closure.status_code == 200
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "closure_drift_evidence_mismatch"


def test_closure_packet_drift_remediation_rejects_unrecorded_authority_ref(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    newer_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    remediation_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:closure_drift_review",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
        },
    )
    refreshed_gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediations",
        json={
            "remediation_id": "remediation:gateway-pilot-drift-review",
            "closure_id": closure.json()["closure"]["closure_id"],
            "terminal_disposition": "requires_review",
            "drift_evidence_refs": ["evidence:engineering_health_endpoint:v2"],
            "superseded_evidence_refs": ["evidence:engineering_health_endpoint"],
            "authority_ref": "approval:security-forged",
            "evidence_refs": ["evidence:closure_drift_review"],
        },
    )
    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert newer_evidence.status_code == 200
    assert remediation_evidence.status_code == 200
    assert refreshed_gate.status_code == 200
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "closure_drift_remediation_rejected"
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediated"] is False
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediation"] is None


def test_closure_packet_drift_remediation_rejects_unbound_superseded_evidence_refs(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    newer_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    remediation_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:closure_drift_review",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
        },
    )
    refreshed_gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediations",
        json={
            "remediation_id": "remediation:gateway-pilot-drift-review",
            "closure_id": closure.json()["closure"]["closure_id"],
            "terminal_disposition": "requires_review",
            "drift_evidence_refs": ["evidence:engineering_health_endpoint:v2"],
            "superseded_evidence_refs": ["evidence:engineering_health_endpoint:v2"],
            "authority_ref": "approval:security-dual-control",
            "evidence_refs": ["evidence:closure_drift_review"],
        },
    )
    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert newer_evidence.status_code == 200
    assert remediation_evidence.status_code == 200
    assert refreshed_gate.status_code == 200
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "closure_drift_remediation_rejected"
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediated"] is False
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediation"] is None


def test_closure_packet_drift_remediation_rejects_unmet_disposition_policy(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    newer_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    remediation_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:closure_drift_review",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
            "metadata": {"evidence_type": "closure_drift_review_decision"},
        },
    )
    refreshed_gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediations",
        json={
            "remediation_id": "remediation:gateway-pilot-accepted-risk",
            "closure_id": closure.json()["closure"]["closure_id"],
            "terminal_disposition": "accepted_risk",
            "drift_evidence_refs": ["evidence:engineering_health_endpoint:v2"],
            "superseded_evidence_refs": ["evidence:engineering_health_endpoint"],
            "authority_ref": "approval:security-dual-control",
            "evidence_refs": ["evidence:closure_drift_review"],
        },
    )
    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert newer_evidence.status_code == 200
    assert remediation_evidence.status_code == 200
    assert refreshed_gate.status_code == 200
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "closure_drift_remediation_policy_unmet"
    assert response.json()["detail"]["missing_evidence_types"] == [
        "accepted_risk_record",
        "risk_owner_approval",
    ]
    assert response.json()["detail"]["missing_authority_refs"] == []
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediated"] is False
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediation"] is None


def test_closure_packet_drift_operator_actions_report_policy_requirements(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    before = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediation-actions")
    review_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:closure_drift_review",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
            "metadata": {"evidence_type": "closure_drift_review_decision"},
        },
    )
    after = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediation-actions")
    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    certificate_view = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate/view")
    explorer = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-explorer")
    explorer_view = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-explorer/view")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert before.status_code == 200
    assert before.json()["closure_packet_drift"] is True
    assert before.json()["closure_id"] == closure.json()["closure"]["closure_id"]
    assert before.json()["drift_evidence_refs"] == ["evidence:engineering_health_endpoint:v2"]
    assert {item["terminal_disposition"] for item in before.json()["actions"]} == {
        "requires_review",
        "compensated",
        "accepted_risk",
    }
    before_by_disposition = {item["terminal_disposition"]: item for item in before.json()["actions"]}
    assert before_by_disposition["requires_review"]["missing_evidence_types"] == [
        "closure_drift_review_decision",
    ]
    assert before_by_disposition["compensated"]["missing_evidence_types"] == [
        "compensation_receipt",
        "compensation_effect_reconciliation",
    ]
    assert before_by_disposition["accepted_risk"]["missing_evidence_types"] == [
        "accepted_risk_record",
        "risk_owner_approval",
    ]
    assert before_by_disposition["requires_review"]["runbook"] is None
    compensated_runbook = before_by_disposition["compensated"]["runbook"]
    accepted_risk_runbook = before_by_disposition["accepted_risk"]["runbook"]
    assert compensated_runbook["runbook_id"] == "runbook:closure-drift-compensation"
    assert compensated_runbook["stage_count"] == 5
    assert compensated_runbook["topology_valid"] is True
    assert compensated_runbook["missing_predecessor_ids"] == []
    assert compensated_runbook["invalid_stage_types"] == []
    assert "approval_gate" in compensated_runbook["stage_types"]
    assert compensated_runbook["stages"][-1]["verification_evidence"] == [
        "closure_drift_remediation_bound",
    ]
    assert before_by_disposition["compensated"]["runbook_binding"] == {
        "runbook_id": "runbook:closure-drift-compensation",
        "terminal_stage_id": "append_remediation_binding",
        "terminal_condition": "append closure drift remediation with terminal_disposition=compensated",
        "terminal_verification_evidence": ["closure_drift_remediation_bound"],
        "stage_count": 5,
        "topology_valid": True,
        "binding_valid": True,
        "validation_errors": [],
    }
    assert accepted_risk_runbook["runbook_id"] == "runbook:closure-drift-accepted-risk"
    assert accepted_risk_runbook["stage_count"] == 5
    assert accepted_risk_runbook["topology_valid"] is True
    assert "wait_for_event" in accepted_risk_runbook["stage_types"]
    assert accepted_risk_runbook["terminal_condition"] == (
        "append closure drift remediation with terminal_disposition=accepted_risk"
    )
    assert before_by_disposition["accepted_risk"]["runbook_binding"]["binding_valid"] is True
    assert before_by_disposition["accepted_risk"]["runbook_binding"]["terminal_stage_id"] == (
        "append_remediation_binding"
    )
    assert before_by_disposition["requires_review"]["runbook_binding"] is None
    assert before_by_disposition["requires_review"]["authority_refs"] == [
        "approval:security-dual-control",
    ]
    assert before_by_disposition["requires_review"]["ready"] is False
    assert review_evidence.status_code == 200
    after_by_disposition = {item["terminal_disposition"]: item for item in after.json()["actions"]}
    assert after_by_disposition["requires_review"]["ready"] is True
    assert after_by_disposition["requires_review"]["missing_evidence_types"] == []
    assert after_by_disposition["requires_review"]["available_evidence_refs_by_type"] == {
        "closure_drift_review_decision": ["evidence:closure_drift_review"],
    }
    assert certificate.status_code == 200
    certificate_actions = certificate.json()["closure_drift_remediation_actions"]
    assert certificate_actions["ready_action_count"] == 1
    assert certificate_actions["action_count"] == 3
    assert certificate_actions["drift_evidence_refs"] == ["evidence:engineering_health_endpoint:v2"]
    certificate_actions_by_disposition = {
        item["terminal_disposition"]: item for item in certificate_actions["actions"]
    }
    assert certificate_actions_by_disposition["requires_review"]["ready"] is True
    assert certificate_actions_by_disposition["compensated"]["ready"] is False
    assert certificate_actions_by_disposition["compensated"]["runbook"]["topology_valid"] is True
    assert certificate_actions_by_disposition["accepted_risk"]["runbook"]["stage_count"] == 5
    assert explorer.status_code == 200
    assert explorer.json()["closure_drift_remediation_actions"]["ready_action_count"] == 1
    assert explorer.json()["status_cards"][-1] == {
        "label": "closure_drift_actions",
        "value": 3,
        "status": "ready",
    }
    assert certificate_view.status_code == 200
    assert "Closure Drift Actions" in certificate_view.text
    assert "binding_terminal_stage_id" in certificate_view.text
    assert "append_remediation_binding" in certificate_view.text
    assert "closure_drift_remediation_bound" in certificate_view.text
    assert "review_required" in certificate_view.text
    assert "runbook:closure-drift-compensation" in certificate_view.text
    assert "compensation_effect_reconciliation" in certificate_view.text
    assert explorer_view.status_code == 200
    assert "Closure Drift Actions" in explorer_view.text
    assert "binding_valid" in explorer_view.text
    assert "runbook:closure-drift-accepted-risk" in explorer_view.text
    assert "accepted_risk_record" in explorer_view.text


def test_closure_packet_drift_operator_action_binds_review_remediation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    remediation_evidence = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:closure_drift_review",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
            "metadata": {"evidence_type": "closure_drift_review_decision"},
        },
    )
    refreshed_gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediation-actions",
        json={
            "action_id": "action:closure-drift-review",
            "closure_id": closure.json()["closure"]["closure_id"],
            "terminal_disposition": "requires_review",
            "authority_ref": "approval:security-dual-control",
            "evidence_refs": ["evidence:closure_drift_review"],
        },
    )
    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    events = client.get("/api/v1/cases/case.launch_gateway_pilot/events")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert remediation_evidence.status_code == 200
    assert refreshed_gate.status_code == 200
    assert response.status_code == 200
    remediation = response.json()["closure_drift_remediation"]
    assert remediation["terminal_disposition"] == "requires_review"
    assert remediation["drift_evidence_refs"] == ["evidence:engineering_health_endpoint:v2"]
    assert remediation["superseded_evidence_refs"] == ["evidence:engineering_health_endpoint"]
    assert remediation["metadata"]["operator_action_id"] == "action:closure-drift-review"
    assert remediation["metadata"]["policy_action_kind"] == "review_required"
    assert remediation["metadata"]["policy_required_evidence_types"] == [
        "closure_drift_review_decision",
    ]
    assert response.json()["action"]["policy"]["ready"] is True
    assert certificate.json()["terminal_status"] == "closed_drift_review_required"
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediated"] is True
    assert "closure_packet_drift_remediated" in {item["kind"] for item in certificate.json()["attention_items"]}
    assert "closure_drift_remediation_bound" in {item["event_type"] for item in events.json()["events"]}


def test_closure_packet_drift_operator_action_binds_compensation_runbook_remediation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    compensation_receipt = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:compensation_receipt",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
            "metadata": {"evidence_type": "compensation_receipt"},
        },
    )
    compensation_reconciliation = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:compensation_effect_reconciliation",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
            "metadata": {"evidence_type": "compensation_effect_reconciliation"},
        },
    )
    refreshed_gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediation-actions",
        json={
            "action_id": "action:closure-drift-compensation",
            "closure_id": closure.json()["closure"]["closure_id"],
            "terminal_disposition": "compensated",
            "authority_ref": "approval:security-dual-control",
            "evidence_refs": [
                "evidence:compensation_receipt",
                "evidence:compensation_effect_reconciliation",
            ],
        },
    )
    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    events = client.get("/api/v1/cases/case.launch_gateway_pilot/events")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert compensation_receipt.status_code == 200
    assert compensation_reconciliation.status_code == 200
    assert refreshed_gate.status_code == 200
    assert response.status_code == 200
    runbook_binding = response.json()["action"]["runbook_binding"]
    assert runbook_binding["runbook_id"] == "runbook:closure-drift-compensation"
    assert runbook_binding["terminal_stage_id"] == "append_remediation_binding"
    assert runbook_binding["terminal_verification_evidence"] == ["closure_drift_remediation_bound"]
    assert runbook_binding["binding_valid"] is True
    remediation = response.json()["closure_drift_remediation"]
    assert remediation["terminal_disposition"] == "compensated"
    assert remediation["metadata"]["operator_action_id"] == "action:closure-drift-compensation"
    assert remediation["metadata"]["runbook_binding"] == runbook_binding
    assert certificate.json()["terminal_status"] == "closed_drift_compensated"
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediated"] is True
    assert "closure_drift_remediation_bound" in {item["event_type"] for item in events.json()["events"]}


def test_closure_packet_drift_operator_action_binds_accepted_risk_runbook_remediation(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    accepted_risk_record = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:accepted_risk_record",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "risk-owner",
            "metadata": {"evidence_type": "accepted_risk_record"},
        },
    )
    risk_owner_approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:risk_owner_approval",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "risk-owner",
            "metadata": {"evidence_type": "risk_owner_approval"},
        },
    )
    refreshed_gate = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediation-actions",
        json={
            "action_id": "action:closure-drift-accepted-risk",
            "closure_id": closure.json()["closure"]["closure_id"],
            "terminal_disposition": "accepted_risk",
            "authority_ref": "approval:security-dual-control",
            "evidence_refs": [
                "evidence:accepted_risk_record",
                "evidence:risk_owner_approval",
            ],
        },
    )
    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")
    events = client.get("/api/v1/cases/case.launch_gateway_pilot/events")

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert accepted_risk_record.status_code == 200
    assert risk_owner_approval.status_code == 200
    assert refreshed_gate.status_code == 200
    assert response.status_code == 200
    runbook_binding = response.json()["action"]["runbook_binding"]
    assert runbook_binding["runbook_id"] == "runbook:closure-drift-accepted-risk"
    assert runbook_binding["terminal_stage_id"] == "append_remediation_binding"
    assert runbook_binding["terminal_condition"] == (
        "append closure drift remediation with terminal_disposition=accepted_risk"
    )
    assert runbook_binding["terminal_verification_evidence"] == ["closure_drift_remediation_bound"]
    assert runbook_binding["binding_valid"] is True
    remediation = response.json()["closure_drift_remediation"]
    assert remediation["terminal_disposition"] == "accepted_risk"
    assert remediation["metadata"]["operator_action_id"] == "action:closure-drift-accepted-risk"
    assert remediation["metadata"]["policy_action_kind"] == "accepted_risk"
    assert remediation["metadata"]["runbook_binding"] == runbook_binding
    assert certificate.json()["terminal_status"] == "closed_drift_accepted_risk"
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediated"] is True
    assert "closure_drift_remediation_bound" in {item["event_type"] for item in events.json()["events"]}


def test_closure_packet_drift_operator_action_rejects_missing_policy_evidence(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:engineering_health_endpoint:v2",
            "requirement_id": "engineering_health_endpoint",
            "submitted_by": "operator",
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/evidence",
        json={
            "evidence_ref": "evidence:compensation_receipt",
            "requirement_id": "security_public_claim_boundary",
            "submitted_by": "human-executive",
            "metadata": {"evidence_type": "compensation_receipt"},
        },
    )
    client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/gate",
        json={"checked_preconditions": ["launch_boundary_defined"]},
    )

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/closure-drift-remediation-actions",
        json={
            "action_id": "action:closure-drift-compensation",
            "closure_id": closure.json()["closure"]["closure_id"],
            "terminal_disposition": "compensated",
            "authority_ref": "approval:security-dual-control",
            "evidence_refs": ["evidence:compensation_receipt"],
        },
    )
    certificate = client.get("/api/v1/cases/case.launch_gateway_pilot/closure-certificate")

    assert closure.status_code == 200
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "closure_drift_remediation_policy_unmet"
    assert response.json()["detail"]["missing_evidence_types"] == [
        "compensation_effect_reconciliation",
    ]
    assert response.json()["detail"]["missing_authority_refs"] == []
    assert certificate.json()["terminal_status"] == "closed_packet_drift"
    assert certificate.json()["closure_gate_evidence"]["closure_packet_drift_remediated"] is False


def test_case_proof_explorer_reports_closed_verified_case(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _admit_all_pilot_evidence(client)
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:security-dual-control",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )
    _allow_all_plan_steps(client)
    closure = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/close",
        json={
            "reconciliation_id": "reconciliation:gateway-pilot",
            "expected_effect": "gateway_pilot_ready",
            "observed_effect": "gateway_pilot_ready",
            "reconciliation_status": "match",
            "forbidden_effects_checked": True,
            "evidence_refs": _terminal_closure_evidence_refs(),
            "terminal_disposition": "committed",
            "terminal_certificate_id": "terminal:gateway-pilot",
        },
    )
    learning = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/learning-admissions",
        json={
            "binding_id": "learning:gateway-pilot",
            "closure_id": closure.json()["closure"]["closure_id"],
            "decision_id": "learning-admission:gateway-pilot",
            "admitted": True,
            "evidence_refs": ["evidence:learning_admission_decision"],
        },
    )

    response = client.get("/api/v1/cases/case.launch_gateway_pilot/proof-explorer")
    payload = response.json()

    assert approval.status_code == 200
    assert closure.status_code == 200
    assert learning.status_code == 200
    assert response.status_code == 200
    assert payload["terminal_status"] == "closed_verified"
    assert payload["attention_items"] == []
    assert payload["closure_panel"]["terminal_certificate_id"] == "terminal:gateway-pilot"
    assert payload["closure_panel"]["effect_reconciled"] is True
    assert payload["closure_panel"]["learning_admitted"] is True
    assert payload["closure_panel"]["learning_admissions"][0]["evidence_refs"] == [
        "evidence:learning_admission_decision",
    ]
    assert {item["label"]: item["status"] for item in payload["status_cards"]} == {
        "case_status": "closed",
        "plan_steps": "ready",
        "evidence": "ready",
        "gate_decisions": "ready",
        "closure": "ready",
        "learning": "ready",
    }
    assert {item["kind"] for section in payload["proof_sections"].values() for item in section}.issuperset({
        "approval",
        "effect_reconciliation",
        "gate_decision",
        "learning_admission",
        "terminal_closure",
    })


def test_launch_gateway_pilot_collects_deployment_witness_and_allows_engineering_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    monkeypatch.setenv("MULLU_RUNTIME_WITNESS_SECRET", "runtime-secret")
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    witness_payload = _signed_runtime_witness(secret="runtime-secret")
    conformance_payload = _signed_conformance_certificate(secret="conformance-secret")

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/deployment-witness",
        json={
            "gateway_url": "https://gateway.example",
            "expected_environment": "pilot",
            "metadata": {"operator_action": "collect_gateway_pilot_evidence"},
        },
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")

    assert response.status_code == 200
    assert response.json()["deployment_witness"]["deployment_claim"] == "published"
    assert response.json()["gate_decision"]["status"] == "allowed"
    assert {
        item["requirement_id"]
        for item in response.json()["admitted_evidence"]
    } == {
        "engineering_health_endpoint",
        "engineering_gateway_witness",
        "engineering_runtime_conformance",
    }
    assert len(fetched.json()["evidence"]) == 3
    assert "runtime-secret" not in json.dumps(fetched.json(), sort_keys=True)
    assert "conformance-secret" not in json.dumps(fetched.json(), sort_keys=True)


def test_launch_gateway_pilot_deployment_witness_without_secrets_blocks_engineering_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    monkeypatch.delenv("MULLU_RUNTIME_WITNESS_SECRET", raising=False)
    monkeypatch.delenv("MULLU_RUNTIME_CONFORMANCE_SECRET", raising=False)
    witness_payload = _signed_runtime_witness(secret="runtime-secret")
    conformance_payload = _signed_conformance_certificate(secret="conformance-secret")

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/deployment-witness",
        json={"gateway_url": "https://gateway.example"},
    )

    assert response.status_code == 200
    assert response.json()["deployment_witness"]["deployment_claim"] == "not-published"
    assert response.json()["gate_decision"]["status"] == "blocked"
    assert response.json()["gate_decision"]["reason"] == "evidence_missing"
    assert [
        item["requirement_id"] for item in response.json()["admitted_evidence"]
    ] == ["engineering_health_endpoint"]


def test_launch_gateway_pilot_deployment_witness_rejects_scoped_gateway_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)

    def fail_urlopen(url, timeout):
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)
    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/deployment-witness",
        json={"gateway_url": "https://gateway.example/private?token=hidden"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "gateway_url_scope_rejected"
    assert response.json()["detail"]["governed"] is True


def test_launch_gateway_pilot_readiness_read_model_reports_missing_evidence(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)

    response = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness")
    payload = response.json()

    assert response.status_code == 200
    assert payload["case_status"] == "planned"
    assert payload["terminal_status"] == "awaiting_evidence"
    assert payload["ready_to_close"] is False
    assert set(payload["missing_evidence"]) == {
        "executive_objective",
        "product_launch_boundary",
        "engineering_health_endpoint",
        "engineering_gateway_witness",
        "engineering_runtime_conformance",
        "security_public_claim_boundary",
        "security_approval",
        "finance_budget_check",
    }
    assert payload["approval_refs"] == []
    assert {step["gate_status"] for step in payload["plan_steps"]} == {"not_evaluated"}


def test_launch_gateway_pilot_gate_preview_is_non_mutating(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    before = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    response = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/gate-preview")
    after = client.get("/api/v1/cases/case.launch_gateway_pilot").json()
    preview_by_step = {
        item["step_id"]: item
        for item in response.json()["gate_preview"]
    }

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert response.json()["blocked_steps"] == [
        "executive_objective_freeze",
        "product_launch_boundary",
        "engineering_runtime_witness",
        "security_claim_boundary",
        "finance_budget_check",
    ]
    assert preview_by_step["executive_objective_freeze"]["reason"] == "evidence_missing"
    assert preview_by_step["product_launch_boundary"]["missing_preconditions"] == ["objective_frozen"]
    assert before["events"] == after["events"]
    assert before["gate_decisions"] == after["gate_decisions"] == []


def test_launch_gateway_pilot_gate_preview_allows_without_writing_decisions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _bind_verified_deployment_witness(client, monkeypatch, auto_gate_engineering_step=False)
    for requirement_id in (
        "executive_objective",
        "product_launch_boundary",
        "security_public_claim_boundary",
        "security_approval",
        "finance_budget_check",
    ):
        evidence = client.post(
            "/api/v1/cases/case.launch_gateway_pilot/evidence",
            json={
                "evidence_ref": f"evidence:preview:{requirement_id}",
                "requirement_id": requirement_id,
                "submitted_by": "operator",
            },
        )
        assert evidence.status_code == 200
        assert evidence.json()["evidence"]["requirement_id"] == requirement_id
        assert evidence.json()["governed"] is True
    approval = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/approvals",
        json={
            "approval_id": "approval:preview-security",
            "role_id": "executive.owner",
            "approval_scope": "security_approval",
            "approved_by": "human-executive",
        },
    )

    response = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/gate-preview")
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")
    readiness = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness")

    assert approval.status_code == 200
    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["blocked_steps"] == []
    assert {item["status"] for item in response.json()["gate_preview"]} == {"allowed"}
    assert all(item["metadata"]["mutates_state"] is False for item in response.json()["gate_preview"])
    assert fetched.json()["gate_decisions"] == []
    assert readiness.json()["ready_to_close"] is False
    assert readiness.json()["preview_ready_to_close"] is True
    assert readiness.json()["required_closure_evidence_refs"] == []
    assert readiness.json()["preview_required_closure_evidence_refs"]
    assert readiness.json()["terminal_status"] == "awaiting_gate"
    assert readiness.json()["preview_terminal_status"] == "ready_to_close"


def test_launch_gateway_pilot_readiness_packet_closes_after_verified_witness(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    _bind_verified_deployment_witness(client, monkeypatch)

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness-closure",
        json=_readiness_closure_payload(),
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")
    readiness = client.get("/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness")

    assert response.status_code == 200
    assert response.json()["closure_status"] == "closed"
    assert response.json()["closure"]["terminal_disposition"] == "committed"
    assert response.json()["blocked_gate_decisions"] == []
    assert len(response.json()["admitted_evidence"]) == 6
    assert {item["status"] for item in response.json()["gate_decisions"]} == {"allowed"}
    assert "approval:security-dual-control" in response.json()["closure"]["evidence_refs"]
    assert "terminal:gateway-pilot-readiness" in response.json()["closure"]["evidence_refs"]
    assert fetched.json()["case"]["status"] == "closed"
    assert fetched.json()["closure"]["terminal_certificate_id"] == "terminal:gateway-pilot-readiness"
    assert readiness.status_code == 200
    assert readiness.json()["terminal_status"] == "closed"
    assert readiness.json()["ready_to_close"] is False
    assert readiness.json()["missing_evidence"] == []
    assert readiness.json()["closure"]["terminal_certificate_id"] == "terminal:gateway-pilot-readiness"


def test_launch_gateway_pilot_readiness_packet_blocks_without_engineering_witness(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness-closure",
        json=_readiness_closure_payload(),
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")
    blocked = {
        item["step_id"]: item["reason"]
        for item in response.json()["blocked_gate_decisions"]
    }

    assert response.status_code == 200
    assert response.json()["closure_status"] == "blocked_by_gate"
    assert response.json()["closure"] is None
    assert blocked["engineering_runtime_witness"] == "evidence_missing"
    assert blocked["security_claim_boundary"] == "preconditions_missing"
    assert blocked["finance_budget_check"] == "preconditions_missing"
    assert fetched.json()["case"]["status"] == "planned"
    assert fetched.json()["closure"] is None


def test_launch_gateway_pilot_readiness_packet_rejects_duplicate_evidence_refs(
    tmp_path: Path,
) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    payload = _readiness_closure_payload()
    payload["finance_budget_check"] = {
        "evidence_ref": payload["executive_objective"]["evidence_ref"],
        "metadata": {"budget_ref": "budget:duplicate"},
    }

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/launch-gateway-pilot/readiness-closure",
        json=payload,
    )
    fetched = client.get("/api/v1/cases/case.launch_gateway_pilot")

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "launch_gateway_pilot_readiness_closure_rejected"
    assert fetched.json()["case"]["status"] == "planned"
    assert fetched.json()["evidence"] == []
    assert fetched.json()["approvals"] == []


def test_default_routers_include_organization_kernel_paths() -> None:
    app = FastAPI()
    include_default_routers(app)
    paths = set(app.openapi()["paths"])

    assert "/api/v1/orgs" in paths
    assert "/api/v1/cases" in paths
    assert "/api/v1/orgs/{org_id}/department-registry" in paths
    assert "/api/v1/orgs/{org_id}/department-registry/view" in paths
    assert "/api/v1/orgs/{org_id}/authority-map" in paths
    assert "/api/v1/orgs/{org_id}/authority-map/view" in paths
    assert "/api/v1/orgs/{org_id}/case-portfolio" in paths
    assert "/api/v1/orgs/{org_id}/case-portfolio/view" in paths
    assert "/api/v1/orgs/{org_id}/action-queue" in paths
    assert "/api/v1/orgs/{org_id}/action-queue/view" in paths
    assert "/api/v1/orgs/{org_id}/action-queue/selection-preview" in paths
    assert "/api/v1/orgs/{org_id}/action-queue/approval-packet-preview" in paths
    assert "/api/v1/orgs/{org_id}/action-queue/dispatch-lease-preview" in paths
    assert "/api/v1/orgs/{org_id}/action-queue/worker-lease" in paths
    assert "/api/v1/orgs/{org_id}/action-queue/worker-dispatch-receipt" in paths
    assert "/api/v1/cases/{case_id}/closure-certificate" in paths
    assert "/api/v1/cases/{case_id}/closure-certificate/view" in paths
    assert "/api/v1/cases/{case_id}/closure-drift-remediations" in paths
    assert "/api/v1/cases/{case_id}/closure-drift-remediation-actions" in paths
    assert "/api/v1/cases/{case_id}/audit-explorer" in paths
    assert "/api/v1/cases/{case_id}/audit-explorer/view" in paths
    assert "/api/v1/cases/{case_id}/step-handoffs" in paths
    assert "/api/v1/cases/{case_id}/step-handoffs/view" in paths
    assert "/api/v1/cases/{case_id}/proof-timeline" in paths
    assert "/api/v1/cases/{case_id}/proof-explorer" in paths
    assert "/api/v1/cases/{case_id}/proof-explorer/view" in paths
    assert "/api/v1/cases/{case_id}/launch-gateway-pilot/deployment-witness" in paths
    assert "/api/v1/cases/{case_id}/launch-gateway-pilot/gate-preview" in paths
    assert "/api/v1/cases/{case_id}/launch-gateway-pilot/readiness" in paths
    assert "/api/v1/cases/{case_id}/launch-gateway-pilot/readiness-closure" in paths
    assert "/api/v1/cases/{case_id}/close" in paths
    assert "/api/v1/cases/{case_id}/plan-steps/{step_id}/admission-preview" in paths
    assert "/api/v1/cases/{case_id}/plan-steps/{step_id}/worker-receipt" in paths


def test_worker_receipt_endpoint_admits_evidence_for_plan_step(tmp_path: Path) -> None:
    client, store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)
    lease_id, dispatch_request_id, dispatch_receipt_id = _record_engineering_dispatch_receipt_for_route(
        client,
        "engineering_health_endpoint",
    )

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/worker-receipt",
        json={
            "binding_id": "binding.eng.health",
            "requirement_id": "engineering_health_endpoint",
            "worker_lease_id": lease_id,
            "dispatch_request_id": dispatch_request_id,
            "dispatch_receipt_id": dispatch_receipt_id,
            "worker_output_hash": "hash-health",
            "receipt_evidence_refs": ["worker-evidence:/health"],
            "admitted_evidence_ref": "evidence:engineering_health_endpoint",
        },
    )
    events = client.get("/api/v1/cases/case.launch_gateway_pilot/events").json()["events"]

    assert response.status_code == 200
    body = response.json()
    assert body["governed"] is True
    assert body["worker_receipt_binding"]["requirement_id"] == "engineering_health_endpoint"
    assert body["worker_receipt_binding"]["dispatch_receipt_id"] == dispatch_receipt_id
    assert any(event["event_type"] == "plan_step_worker_receipt_bound" for event in events)
    assert store.exists()


def test_worker_receipt_endpoint_rejects_missing_dispatch_receipt(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/worker-receipt",
        json={
            "binding_id": "binding.eng.health",
            "requirement_id": "engineering_health_endpoint",
            "worker_lease_id": "lease.eng.gateway.engineering_health_endpoint",
            "dispatch_request_id": "req.engineering_health_endpoint",
            "dispatch_receipt_id": "receipt.engineering_health_endpoint",
            "worker_output_hash": "hash-health",
            "receipt_evidence_refs": ["worker-evidence:/health"],
            "admitted_evidence_ref": "evidence:engineering_health_endpoint",
        },
    )
    case_bundle = client.get("/api/v1/cases/case.launch_gateway_pilot").json()

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "worker_receipt_binding_rejected"
    assert case_bundle["worker_dispatch_receipts"] == []
    assert all(item["requirement_id"] != "engineering_health_endpoint" for item in case_bundle["evidence"])


def test_worker_receipt_endpoint_rejects_requirement_outside_plan_step(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/worker-receipt",
        json={
            "binding_id": "binding.bad",
            "requirement_id": "finance_budget_check",
            "worker_lease_id": "lease.x",
            "dispatch_request_id": "req.x",
            "dispatch_receipt_id": "receipt.x",
            "worker_output_hash": "hash-x",
            "receipt_evidence_refs": ["worker-evidence:budget"],
            "admitted_evidence_ref": "evidence:finance_budget_check",
        },
    )

    assert response.status_code == 400
