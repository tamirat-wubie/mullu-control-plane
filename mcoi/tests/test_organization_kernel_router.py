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
from mcoi_runtime.core.organization_kernel import OrganizationKernel
from mcoi_runtime.persistence.organization_kernel_store import FileOrganizationKernelStore


FIXED_CLOCK = "2026-05-27T12:00:00+00:00"


class MetricsStub:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value


class FixedClock:
    def __call__(self) -> str:
        return FIXED_CLOCK


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
        "proof_coverage_declared_route_count": 301,
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
    )
    for requirement_id in requirements:
        response = client.post(
            "/api/v1/cases/case.launch_gateway_pilot/evidence",
            json={
                "evidence_ref": f"evidence:{requirement_id}",
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
            "evidence_refs": ["evidence:closure:gateway-pilot"],
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
            "evidence_refs": ["evidence:closure:gateway-pilot"],
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
    assert len(response.json()["admitted_evidence"]) == 5
    assert {item["status"] for item in response.json()["gate_decisions"]} == {"allowed"}
    assert "approval:security-dual-control" in response.json()["closure"]["evidence_refs"]
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
    paths = {route.path for route in app.routes}

    assert "/api/v1/orgs" in paths
    assert "/api/v1/cases" in paths
    assert "/api/v1/cases/{case_id}/proof-timeline" in paths
    assert "/api/v1/cases/{case_id}/launch-gateway-pilot/deployment-witness" in paths
    assert "/api/v1/cases/{case_id}/launch-gateway-pilot/gate-preview" in paths
    assert "/api/v1/cases/{case_id}/launch-gateway-pilot/readiness" in paths
    assert "/api/v1/cases/{case_id}/launch-gateway-pilot/readiness-closure" in paths
    assert "/api/v1/cases/{case_id}/close" in paths
    assert "/api/v1/cases/{case_id}/plan-steps/{step_id}/worker-receipt" in paths


def test_worker_receipt_endpoint_admits_evidence_for_plan_step(tmp_path: Path) -> None:
    client, store = _client(tmp_path)
    _bootstrap_and_open_pilot(client)

    response = client.post(
        "/api/v1/cases/case.launch_gateway_pilot/plan-steps/engineering_runtime_witness/worker-receipt",
        json={
            "binding_id": "binding.eng.health",
            "requirement_id": "engineering_health_endpoint",
            "worker_lease_id": "lease.eng.gateway",
            "dispatch_request_id": "req.eng.health",
            "dispatch_receipt_id": "receipt.eng.health",
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
    assert any(event["event_type"] == "plan_step_worker_receipt_bound" for event in events)
    assert store.exists()


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
