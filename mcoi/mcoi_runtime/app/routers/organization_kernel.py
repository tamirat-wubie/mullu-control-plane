"""Purpose: Organization Kernel HTTP endpoints.
Governance scope: orgs, departments, cases, plans, evidence, approvals,
plan-step gates, terminal closure, learning admission, and read models.
Dependencies: FastAPI, router deps, OrganizationKernel contracts and runtime.
Invariants:
  - HTTP requests adapt into governed kernel contracts; they do not bypass the kernel.
  - Events are emitted by kernel mutations and are not client-authored.
  - Mutations persist the exact kernel state when a store is configured.
  - Responses expose bounded errors and governed=True.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from html import escape
from typing import Any
from urllib.parse import quote, urlparse

from mcoi_runtime.governance.network.ssrf import is_private_host

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.musia_auth import require_admin

from scripts.collect_deployment_witness import (
    DeploymentWitness,
    collect_deployment_witness,
)

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope
from mcoi_runtime.contracts.effect_assurance import ReconciliationStatus
from mcoi_runtime.contracts.organization_kernel import (
    ApprovalRecord,
    CaseEvidence,
    DepartmentPack,
    LearningAdmissionBinding,
    OrganizationCase,
    OrganizationCaseStatus,
    OrganizationEffectReconciliation,
    OrganizationPlan,
    OrganizationProfile,
    OrganizationRisk,
    PlanStep,
    PlanStepGateStatus,
    PlanStepWorkerReceiptBinding,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.organization_kernel import (
    LAUNCH_GATEWAY_PILOT_CASE_TYPE,
    OrganizationKernel,
    bootstrap_minimum_organization,
    open_launch_gateway_pilot,
)
from mcoi_runtime.persistence.errors import PersistenceError

router = APIRouter()


class OrganizationCreateRequest(BaseModel):
    org_id: str
    tenant_id: str
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrganizationBootstrapRequest(BaseModel):
    tenant_id: str
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerReceiptBindRequest(BaseModel):
    binding_id: str
    requirement_id: str
    worker_lease_id: str
    dispatch_request_id: str
    dispatch_receipt_id: str
    worker_output_hash: str
    receipt_evidence_refs: list[str]
    admitted_evidence_ref: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DepartmentCreateRequest(BaseModel):
    department_id: str
    org_id: str
    name: str
    mission: str
    owns: list[str]
    allowed_case_types: list[str]
    allowed_capabilities: list[str]
    required_evidence: list[str]
    escalation_departments: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrganizationCaseCreateRequest(BaseModel):
    case_id: str
    org_id: str
    department_id: str
    case_type: str
    goal: str
    risk: str = OrganizationRisk.MEDIUM.value
    owner_role_id: str
    assigned_department_ids: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class LaunchGatewayPilotRequest(BaseModel):
    org_id: str
    case_id: str = "case.launch_gateway_pilot"
    owner_role_id: str = "executive.owner"


class PlanStepRequest(BaseModel):
    step_id: str
    department_id: str
    responsible_role_id: str
    capability_id: str
    action: str
    expected_effect: str
    preconditions: list[str]
    postconditions: list[str]
    evidence_required: list[str]
    approvals_required: list[str] = Field(default_factory=list)
    predecessor_step_ids: list[str] = Field(default_factory=list)
    rollback_plan_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrganizationPlanCreateRequest(BaseModel):
    plan_id: str
    steps: list[PlanStepRequest]
    version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceAdmitRequest(BaseModel):
    evidence_ref: str
    requirement_id: str
    submitted_by: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRecordRequest(BaseModel):
    approval_id: str
    role_id: str
    approval_scope: str
    approved_by: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanStepGateRequest(BaseModel):
    checked_preconditions: list[str]


class OrganizationCaseCloseRequest(BaseModel):
    reconciliation_id: str
    expected_effect: str
    observed_effect: str
    reconciliation_status: str = ReconciliationStatus.MATCH.value
    forbidden_effects_checked: bool
    evidence_refs: list[str]
    terminal_disposition: str = TerminalClosureDisposition.COMMITTED.value
    terminal_certificate_id: str
    learning_admission_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningAdmissionRequest(BaseModel):
    binding_id: str
    closure_id: str
    decision_id: str
    admitted: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class LaunchGatewayPilotEvidenceCollectionRequest(BaseModel):
    gateway_url: str
    expected_environment: str = "pilot"
    require_production_evidence: bool = False
    submitted_by: str = "operator"
    auto_gate_engineering_step: bool = True
    checked_preconditions: list[str] = Field(default_factory=lambda: ["launch_boundary_defined"])
    metadata: dict[str, Any] = Field(default_factory=dict)


class LaunchGatewayPilotEvidencePacketItem(BaseModel):
    evidence_ref: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LaunchGatewayPilotReadinessClosureRequest(BaseModel):
    submitted_by: str = "operator"
    executive_objective: LaunchGatewayPilotEvidencePacketItem
    product_launch_boundary: LaunchGatewayPilotEvidencePacketItem
    security_public_claim_boundary: LaunchGatewayPilotEvidencePacketItem
    security_approval: LaunchGatewayPilotEvidencePacketItem
    finance_budget_check: LaunchGatewayPilotEvidencePacketItem
    approval_id: str = "approval:security-dual-control"
    approved_by: str
    expected_effect: str = "gateway_pilot_ready"
    observed_effect: str
    reconciliation_id: str = "reconciliation:gateway-pilot-readiness"
    reconciliation_status: str = ReconciliationStatus.MATCH.value
    forbidden_effects_checked: bool = True
    closure_evidence_refs: list[str] = Field(default_factory=list)
    terminal_disposition: str = TerminalClosureDisposition.COMMITTED.value
    terminal_certificate_id: str
    learning_admission_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _default_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clock_now() -> str:
    try:
        clock = deps.clock
    except RuntimeError:
        return _default_clock()
    return clock()


_fallback_kernel = OrganizationKernel(clock=_clock_now)


def reset_organization_kernel_for_tests() -> None:
    """Reset fallback state for isolated router tests."""
    global _fallback_kernel
    _fallback_kernel = OrganizationKernel(clock=_clock_now)


def _error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _kernel() -> OrganizationKernel:
    try:
        return deps.organization_kernel
    except RuntimeError:
        return _fallback_kernel


def _inc_metric(name: str) -> None:
    try:
        deps.metrics.inc(name)
    except RuntimeError:
        return


def _persist_kernel(kernel: OrganizationKernel) -> str | None:
    try:
        store = deps.organization_kernel_store
    except RuntimeError:
        return None
    try:
        return store.save_kernel(kernel)
    except PersistenceError as exc:
        raise HTTPException(
            500,
            detail=_error_detail("organization kernel persistence failed", "organization_persistence_failed"),
        ) from exc


def _case_or_404(kernel: OrganizationKernel, case_id: str) -> OrganizationCase:
    organization_case = kernel.get_case(case_id)
    if organization_case is None:
        raise HTTPException(404, detail=_error_detail("case not found", "case_not_found"))
    return organization_case


def _organization_or_404(kernel: OrganizationKernel, org_id: str) -> OrganizationProfile:
    organization = next((item for item in kernel.snapshot_state().organizations if item.org_id == org_id), None)
    if organization is None:
        raise HTTPException(404, detail=_error_detail("organization not found", "organization_not_found"))
    return organization


def _enforce_known_organization_tenant(request: Request, kernel: OrganizationKernel, org_id: str) -> None:
    tenant_id = kernel.organization_tenant(org_id)
    if tenant_id:
        enforce_tenant_scope(request, tenant_id)


def _enforce_organization_tenant(request: Request, kernel: OrganizationKernel, org_id: str) -> OrganizationProfile:
    organization = _organization_or_404(kernel, org_id)
    enforce_tenant_scope(request, organization.tenant_id)
    return organization


def _enforce_case_tenant(request: Request, kernel: OrganizationKernel, case_id: str) -> None:
    """Reject access to a case owned by another tenant.

    Organization cases carry an org_id, not a tenant_id; the owning tenant is
    resolved through the organization. A no-op for operators (wildcard scope) and
    unauthenticated dev requests, so existing suites are unaffected.
    """
    organization_case = _case_or_404(kernel, case_id)
    tenant_id = kernel.organization_tenant(organization_case.org_id)
    if tenant_id:
        enforce_tenant_scope(request, tenant_id)


def _require_launch_gateway_pilot_case(kernel: OrganizationKernel, case_id: str) -> OrganizationCase:
    organization_case = _case_or_404(kernel, case_id)
    if organization_case.case_type != LAUNCH_GATEWAY_PILOT_CASE_TYPE:
        raise HTTPException(
            400,
            detail=_error_detail(
                "case is not a launch gateway pilot",
                "case_not_launch_gateway_pilot",
            ),
        )
    return organization_case


def _body(record: Any) -> dict[str, Any]:
    return record.to_json_dict()


def _state_case_bundle(kernel: OrganizationKernel, case_id: str) -> dict[str, Any]:
    organization_case = _case_or_404(kernel, case_id)
    state = kernel.snapshot_state()
    plan = next((item for item in state.plans if item.case_id == case_id), None)
    closure = next((item for item in state.closures if item.case_id == case_id), None)
    return {
        "case": _body(organization_case),
        "plan": _body(plan) if plan is not None else None,
        "evidence": [_body(item) for item in state.case_evidence if item.case_id == case_id],
        "approvals": [_body(item) for item in state.approvals if item.case_id == case_id],
        "gate_decisions": [_body(item) for item in state.gate_decisions if item.case_id == case_id],
        "reconciliations": [_body(item) for item in state.reconciliations if item.case_id == case_id],
        "closure": _body(closure) if closure is not None else None,
        "learning_bindings": [_body(item) for item in state.learning_bindings if item.case_id == case_id],
        "events": [_body(item) for item in kernel.list_case_events(case_id)],
        "governed": True,
    }


def _timeline_item(
    *,
    kind: str,
    occurred_at: str,
    ref: str,
    status: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "occurred_at": occurred_at,
        "ref": ref,
        "status": status,
        "payload": payload or {},
    }


def _case_proof_timeline(kernel: OrganizationKernel, case_id: str) -> dict[str, Any]:
    organization_case = _case_or_404(kernel, case_id)
    state = kernel.snapshot_state()
    plan = next((item for item in state.plans if item.case_id == case_id), None)
    closure = next((item for item in state.closures if item.case_id == case_id), None)
    evidence = tuple(item for item in state.case_evidence if item.case_id == case_id)
    approvals = tuple(item for item in state.approvals if item.case_id == case_id)
    gate_decisions = tuple(item for item in state.gate_decisions if item.case_id == case_id)
    worker_receipts = tuple(item for item in state.worker_receipt_bindings if item.case_id == case_id)
    reconciliations = tuple(item for item in state.reconciliations if item.case_id == case_id)
    learning_bindings = tuple(item for item in state.learning_bindings if item.case_id == case_id)
    gate_by_id = {decision.decision_id: decision for decision in gate_decisions}
    latest_gate_by_step = {
        ref.step_id: gate_by_id[ref.decision_id]
        for ref in state.latest_gate_decisions
        if ref.case_id == case_id and ref.decision_id in gate_by_id
    }
    evidence_by_requirement: dict[str, list[str]] = {}
    for item in evidence:
        evidence_by_requirement.setdefault(item.requirement_id, []).append(item.evidence_ref)
    worker_receipts_by_step: dict[str, list[dict[str, Any]]] = {}
    for binding in worker_receipts:
        worker_receipts_by_step.setdefault(binding.step_id, []).append(_body(binding))

    plan_step_proof = []
    if plan is not None:
        for step in plan.steps:
            evidence_refs = [
                ref
                for requirement_id in step.evidence_required
                for ref in evidence_by_requirement.get(requirement_id, [])
            ]
            missing_evidence = [
                requirement_id
                for requirement_id in step.evidence_required
                if requirement_id not in evidence_by_requirement
            ]
            latest_decision = latest_gate_by_step.get(step.step_id)
            plan_step_proof.append({
                "step_id": step.step_id,
                "department_id": step.department_id,
                "responsible_role_id": step.responsible_role_id,
                "capability_id": step.capability_id,
                "evidence_refs": evidence_refs,
                "missing_evidence": missing_evidence,
                "worker_receipt_bindings": worker_receipts_by_step.get(step.step_id, []),
                "latest_gate_decision": _body(latest_decision) if latest_decision is not None else None,
                "gate_status": latest_decision.status.value if latest_decision is not None else "not_evaluated",
            })

    proof_timeline = [
        _timeline_item(
            kind="case_event",
            occurred_at=event.emitted_at,
            ref=event.event_id,
            status=event.event_type,
            payload={"event_type": event.event_type, "payload": _body(event)["payload"]},
        )
        for event in kernel.list_case_events(case_id)
    ]
    proof_timeline.extend(
        _timeline_item(
            kind="evidence",
            occurred_at=item.submitted_at,
            ref=item.evidence_ref,
            status="admitted",
            payload={"requirement_id": item.requirement_id, "submitted_by": item.submitted_by},
        )
        for item in evidence
    )
    proof_timeline.extend(
        _timeline_item(
            kind="approval",
            occurred_at=item.approved_at,
            ref=item.approval_id,
            status="recorded",
            payload={"role_id": item.role_id, "approval_scope": item.approval_scope},
        )
        for item in approvals
    )
    proof_timeline.extend(
        _timeline_item(
            kind="worker_receipt_binding",
            occurred_at=item.bound_at,
            ref=item.binding_id,
            status="bound",
            payload={
                "step_id": item.step_id,
                "requirement_id": item.requirement_id,
                "dispatch_receipt_id": item.dispatch_receipt_id,
                "admitted_evidence_ref": item.admitted_evidence_ref,
            },
        )
        for item in worker_receipts
    )
    proof_timeline.extend(
        _timeline_item(
            kind="gate_decision",
            occurred_at=item.decided_at,
            ref=item.decision_id,
            status=item.status.value,
            payload={"step_id": item.step_id, "reason": item.reason},
        )
        for item in gate_decisions
    )
    proof_timeline.extend(
        _timeline_item(
            kind="effect_reconciliation",
            occurred_at=item.reconciled_at,
            ref=item.reconciliation_id,
            status=item.status.value,
            payload={
                "expected_effect": item.expected_effect,
                "observed_effect": item.observed_effect,
                "forbidden_effects_checked": item.forbidden_effects_checked,
            },
        )
        for item in reconciliations
    )
    if closure is not None:
        proof_timeline.append(
            _timeline_item(
                kind="terminal_closure",
                occurred_at=closure.closed_at,
                ref=closure.closure_id,
                status=closure.terminal_disposition.value,
                payload={"terminal_certificate_id": closure.terminal_certificate_id},
            )
        )
    proof_timeline.extend(
        _timeline_item(
            kind="learning_admission",
            occurred_at=item.created_at,
            ref=item.binding_id,
            status="admitted" if item.admitted else "rejected",
            payload={"closure_id": item.closure_id, "decision_id": item.decision_id},
        )
        for item in learning_bindings
    )
    proof_timeline = sorted(
        proof_timeline,
        key=lambda item: (item["occurred_at"], item["kind"], item["ref"]),
    )

    blocked_steps = [
        row["step_id"] for row in plan_step_proof
        if row["gate_status"] != PlanStepGateStatus.ALLOWED.value
    ]
    closure_reconciliation = None
    learning_for_closure: tuple[LearningAdmissionBinding, ...] = ()
    if closure is not None:
        closure_reconciliation = next(
            (item for item in reconciliations if item.reconciliation_id == closure.reconciliation_id),
            None,
        )
        learning_for_closure = tuple(item for item in learning_bindings if item.closure_id == closure.closure_id)
    closure_certificate = None
    if closure is not None:
        effect_reconciled = False
        if closure_reconciliation is not None:
            effect_reconciled = True
            if closure.terminal_disposition is TerminalClosureDisposition.COMMITTED:
                effect_reconciled = (
                    closure_reconciliation.status is ReconciliationStatus.MATCH
                    and closure_reconciliation.expected_effect == closure_reconciliation.observed_effect
                    and closure_reconciliation.forbidden_effects_checked
                )
        closure_certificate = {
            "closure_id": closure.closure_id,
            "terminal_certificate_id": closure.terminal_certificate_id,
            "terminal_disposition": closure.terminal_disposition.value,
            "closed_at": closure.closed_at,
            "evidence_refs": list(closure.evidence_refs),
            "reconciliation": _body(closure_reconciliation) if closure_reconciliation is not None else None,
            "learning_admissions": [_body(item) for item in learning_for_closure],
            "effect_reconciled": effect_reconciled,
            "learning_admitted": any(item.admitted for item in learning_for_closure),
        }

    return {
        "case_id": case_id,
        "case": _body(organization_case),
        "plan_id": plan.plan_id if plan is not None else None,
        "summary": {
            "case_status": organization_case.status.value,
            "has_plan": plan is not None,
            "evidence_count": len(evidence),
            "approval_count": len(approvals),
            "gate_decision_count": len(gate_decisions),
            "worker_receipt_count": len(worker_receipts),
            "reconciliation_count": len(reconciliations),
            "has_terminal_closure": closure is not None,
            "learning_binding_count": len(learning_bindings),
            "blocked_steps": blocked_steps,
            "all_plan_steps_allowed": plan is not None and not blocked_steps,
            "terminal_status": organization_case.status.value,
        },
        "plan_step_proof": plan_step_proof,
        "proof_timeline": proof_timeline,
        "closure_certificate": closure_certificate,
        "governed": True,
    }


def _proof_status_card(label: str, value: object, status: str) -> dict[str, object]:
    return {"label": label, "value": value, "status": status}


def _case_proof_explorer(kernel: OrganizationKernel, case_id: str) -> dict[str, Any]:
    proof = _case_proof_timeline(kernel, case_id)
    organization_case = proof["case"]
    summary = proof["summary"]
    plan_step_proof = proof["plan_step_proof"]
    closure_certificate = proof["closure_certificate"]
    evidence_timeline_by_ref = {
        item["ref"]: item
        for item in proof["proof_timeline"]
        if item["kind"] == "evidence"
    }
    evidence_requirements: dict[str, dict[str, Any]] = {}
    department_lanes: dict[str, dict[str, Any]] = {}
    attention_items: list[dict[str, object]] = []

    for step in plan_step_proof:
        department_id = step["department_id"]
        lane = department_lanes.setdefault(
            department_id,
            {
                "department_id": department_id,
                "step_ids": [],
                "allowed_step_count": 0,
                "blocked_step_count": 0,
                "missing_evidence_count": 0,
                "evidence_ref_count": 0,
            },
        )
        lane["step_ids"].append(step["step_id"])
        lane["evidence_ref_count"] += len(step["evidence_refs"])
        lane["missing_evidence_count"] += len(step["missing_evidence"])
        if step["gate_status"] == PlanStepGateStatus.ALLOWED.value:
            lane["allowed_step_count"] += 1
        else:
            lane["blocked_step_count"] += 1
            attention_items.append({
                "kind": "blocked_plan_step",
                "severity": "review",
                "ref": step["step_id"],
                "message": "plan step is not allowed by the latest gate decision",
            })
        for requirement_id in step["missing_evidence"]:
            evidence_row = evidence_requirements.setdefault(
                requirement_id,
                {
                    "requirement_id": requirement_id,
                    "present": False,
                    "evidence_refs": [],
                    "step_ids": [],
                },
            )
            evidence_row["step_ids"].append(step["step_id"])
            attention_items.append({
                "kind": "missing_evidence",
                "severity": "blocker",
                "ref": requirement_id,
                "message": "required evidence is not admitted for this case",
            })
        for evidence_ref in step["evidence_refs"]:
            timeline_item = evidence_timeline_by_ref.get(evidence_ref)
            if timeline_item is None:
                continue
            requirement_id = timeline_item["payload"]["requirement_id"]
            evidence_row = evidence_requirements.setdefault(
                requirement_id,
                {
                    "requirement_id": requirement_id,
                    "present": True,
                    "evidence_refs": [],
                    "step_ids": [],
                },
            )
            evidence_row["present"] = True
            evidence_row["evidence_refs"].append(evidence_ref)
            evidence_row["step_ids"].append(step["step_id"])

    if not summary["has_terminal_closure"]:
        attention_items.append({
            "kind": "missing_terminal_closure",
            "severity": "review",
            "ref": case_id,
            "message": "case has no terminal closure certificate",
        })
    elif closure_certificate is not None and not closure_certificate["effect_reconciled"]:
        attention_items.append({
            "kind": "effect_not_reconciled",
            "severity": "blocker",
            "ref": closure_certificate["closure_id"],
            "message": "terminal closure does not have a reconciled external effect",
        })
    elif closure_certificate is not None and not closure_certificate["learning_admitted"]:
        attention_items.append({
            "kind": "learning_not_admitted",
            "severity": "review",
            "ref": closure_certificate["closure_id"],
            "message": "closure has not been admitted into reusable learning",
        })

    proof_sections: dict[str, list[dict[str, Any]]] = {}
    for item in proof["proof_timeline"]:
        proof_sections.setdefault(item["kind"], []).append(item)

    terminal_status = "awaiting_closure"
    if closure_certificate is not None:
        if closure_certificate["effect_reconciled"] and closure_certificate["learning_admitted"]:
            terminal_status = "closed_verified"
        elif closure_certificate["effect_reconciled"]:
            terminal_status = "closed_awaiting_learning"
        else:
            terminal_status = "closed_requires_review"
    elif summary["blocked_steps"]:
        terminal_status = "blocked_by_plan_gate"
    elif summary["has_plan"]:
        terminal_status = "awaiting_evidence"

    return {
        "explorer_id": f"proof-explorer:{case_id}",
        "case_id": case_id,
        "title": organization_case["goal"],
        "terminal_status": terminal_status,
        "read_only": True,
        "status_cards": [
            _proof_status_card(
                "case_status",
                summary["case_status"],
                "closed" if summary["case_status"] == "closed" else "open",
            ),
            _proof_status_card("plan_steps", len(plan_step_proof), "ready" if plan_step_proof else "missing"),
            _proof_status_card("evidence", summary["evidence_count"], "ready" if summary["evidence_count"] else "missing"),
            _proof_status_card(
                "gate_decisions",
                summary["gate_decision_count"],
                "ready" if summary["all_plan_steps_allowed"] else "blocked",
            ),
            _proof_status_card(
                "closure",
                summary["has_terminal_closure"],
                "ready" if summary["has_terminal_closure"] else "missing",
            ),
            _proof_status_card(
                "learning",
                summary["learning_binding_count"],
                "ready" if summary["learning_binding_count"] else "missing",
            ),
        ],
        "attention_items": attention_items,
        "department_lanes": sorted(department_lanes.values(), key=lambda item: item["department_id"]),
        "evidence_matrix": sorted(evidence_requirements.values(), key=lambda item: item["requirement_id"]),
        "proof_sections": {key: proof_sections[key] for key in sorted(proof_sections)},
        "closure_panel": closure_certificate,
        "source_timeline": proof,
        "governed": True,
    }


def _audit_layer(kind: object) -> str:
    if kind == "case_event":
        return "case"
    if kind == "evidence":
        return "evidence"
    if kind in {"approval", "gate_decision"}:
        return "authority"
    if kind == "worker_receipt_binding":
        return "execution"
    if kind == "effect_reconciliation":
        return "reconciliation"
    if kind == "terminal_closure":
        return "closure"
    if kind == "learning_admission":
        return "learning"
    return "unknown"


def _case_audit_explorer(kernel: OrganizationKernel, case_id: str) -> dict[str, Any]:
    proof = _case_proof_timeline(kernel, case_id)
    explorer = _case_proof_explorer(kernel, case_id)
    audit_rows: list[dict[str, object]] = []
    proof_timeline = proof["proof_timeline"]
    for sequence, item in enumerate(proof_timeline, start=1):
        payload = item.get("payload", {})
        payload = payload if isinstance(payload, dict) else {}
        audit_rows.append({
            "sequence": sequence,
            "occurred_at": item.get("occurred_at", ""),
            "layer": _audit_layer(item.get("kind")),
            "kind": item.get("kind", ""),
            "ref": item.get("ref", ""),
            "status": item.get("status", ""),
            "actor": payload.get("submitted_by") or payload.get("approved_by") or "",
            "department_id": payload.get("department_id", ""),
            "step_id": payload.get("step_id", ""),
            "evidence_ref": payload.get("admitted_evidence_ref", ""),
            "reason": payload.get("reason", ""),
        })

    attention_items = explorer["attention_items"]
    blocker_count = sum(1 for item in attention_items if item.get("severity") == "blocker")
    review_count = sum(1 for item in attention_items if item.get("severity") == "review")
    proof_sections = explorer["proof_sections"]
    return {
        "audit_id": f"case-audit:{case_id}",
        "case_id": case_id,
        "title": proof["case"]["goal"],
        "terminal_status": explorer["terminal_status"],
        "read_only": True,
        "case": proof["case"],
        "summary": {
            "case_status": proof["summary"]["case_status"],
            "timeline_count": len(audit_rows),
            "case_event_count": len(proof_sections.get("case_event", [])),
            "attention_count": len(attention_items),
            "blocker_count": blocker_count,
            "review_count": review_count,
            "first_occurred_at": audit_rows[0]["occurred_at"] if audit_rows else "",
            "last_occurred_at": audit_rows[-1]["occurred_at"] if audit_rows else "",
            "has_terminal_closure": proof["summary"]["has_terminal_closure"],
            "learning_binding_count": proof["summary"]["learning_binding_count"],
        },
        "attention_items": attention_items,
        "audit_timeline": audit_rows,
        "proof_section_counts": [
            {"section": key, "count": len(value)}
            for key, value in sorted(proof_sections.items())
        ],
        "source_timeline_url": f"/api/v1/cases/{quote(case_id, safe='')}/proof-timeline",
        "source_explorer_url": f"/api/v1/cases/{quote(case_id, safe='')}/proof-explorer",
        "closure_certificate_url": f"/api/v1/cases/{quote(case_id, safe='')}/closure-certificate",
        "governed": True,
    }


def _step_handoff_status(step_proof: dict[str, Any]) -> str:
    missing_evidence = step_proof["missing_evidence"]
    worker_receipts = step_proof["worker_receipt_bindings"]
    gate_status = step_proof["gate_status"]
    if worker_receipts and missing_evidence:
        return "receipt_bound_awaiting_evidence"
    if worker_receipts and gate_status == PlanStepGateStatus.ALLOWED.value:
        return "worker_receipt_bound"
    if worker_receipts:
        return "receipt_bound_awaiting_gate"
    if missing_evidence:
        return "awaiting_evidence"
    if gate_status != PlanStepGateStatus.ALLOWED.value:
        return "awaiting_gate"
    return "ready_for_worker_receipt"


def _step_handoff_next_action(handoff_status: str) -> str:
    if handoff_status in {"receipt_bound_awaiting_evidence", "awaiting_evidence"}:
        return "collect_required_evidence"
    if handoff_status in {"receipt_bound_awaiting_gate", "awaiting_gate"}:
        return "evaluate_plan_step_gate"
    if handoff_status == "ready_for_worker_receipt":
        return "bind_worker_receipt"
    if handoff_status == "worker_receipt_bound":
        return "review_bound_receipt"
    return "review_step_state"


def _case_step_handoffs(kernel: OrganizationKernel, case_id: str) -> dict[str, Any]:
    proof = _case_proof_timeline(kernel, case_id)
    state = kernel.snapshot_state()
    plan = next((item for item in state.plans if item.case_id == case_id), None)
    steps_by_id = {step.step_id: step for step in plan.steps} if plan is not None else {}
    attention_items: list[dict[str, object]] = []
    handoff_rows: list[dict[str, Any]] = []

    if plan is None:
        attention_items.append({
            "kind": "missing_plan",
            "severity": "review",
            "ref": case_id,
            "message": "case has no governed plan",
        })

    for step_proof in proof["plan_step_proof"]:
        step = steps_by_id.get(step_proof["step_id"])
        handoff_status = _step_handoff_status(step_proof)
        next_action = _step_handoff_next_action(handoff_status)
        if step_proof["missing_evidence"]:
            attention_items.append({
                "kind": "handoff_missing_evidence",
                "severity": "blocker",
                "ref": step_proof["step_id"],
                "message": "step handoff is missing required evidence",
                "missing_evidence": step_proof["missing_evidence"],
            })
        elif step_proof["gate_status"] != PlanStepGateStatus.ALLOWED.value:
            attention_items.append({
                "kind": "handoff_gate_not_allowed",
                "severity": "review",
                "ref": step_proof["step_id"],
                "message": "step handoff gate is not allowed",
                "gate_status": step_proof["gate_status"],
            })
        elif not step_proof["worker_receipt_bindings"]:
            attention_items.append({
                "kind": "handoff_ready_for_receipt",
                "severity": "review",
                "ref": step_proof["step_id"],
                "message": "step handoff is ready for worker receipt binding",
            })
        handoff_rows.append({
            "step_id": step_proof["step_id"],
            "department_id": step_proof["department_id"],
            "responsible_role_id": step_proof["responsible_role_id"],
            "capability_id": step_proof["capability_id"],
            "action": step.action if step is not None else "",
            "expected_effect": step.expected_effect if step is not None else "",
            "preconditions": list(step.preconditions) if step is not None else [],
            "postconditions": list(step.postconditions) if step is not None else [],
            "approvals_required": list(step.approvals_required) if step is not None else [],
            "predecessor_step_ids": list(step.predecessor_step_ids) if step is not None else [],
            "rollback_plan_id": step.rollback_plan_id if step is not None else None,
            "gate_status": step_proof["gate_status"],
            "handoff_status": handoff_status,
            "next_action": next_action,
            "dispatch_authority": False,
            "evidence_refs": step_proof["evidence_refs"],
            "missing_evidence": step_proof["missing_evidence"],
            "worker_receipt_count": len(step_proof["worker_receipt_bindings"]),
            "worker_receipt_bindings": step_proof["worker_receipt_bindings"],
            "worker_receipt_url": (
                f"/api/v1/cases/{quote(case_id, safe='')}/plan-steps/"
                f"{quote(str(step_proof['step_id']), safe='')}/worker-receipt"
            ),
        })

    statuses = [row["handoff_status"] for row in handoff_rows]
    return {
        "handoff_id": f"step-handoffs:{case_id}",
        "case_id": case_id,
        "title": proof["case"]["goal"],
        "read_only": True,
        "case": proof["case"],
        "summary": {
            "step_count": len(handoff_rows),
            "ready_for_worker_receipt_count": statuses.count("ready_for_worker_receipt"),
            "worker_receipt_bound_count": statuses.count("worker_receipt_bound"),
            "receipt_bound_awaiting_evidence_count": statuses.count("receipt_bound_awaiting_evidence"),
            "receipt_bound_awaiting_gate_count": statuses.count("receipt_bound_awaiting_gate"),
            "awaiting_evidence_count": statuses.count("awaiting_evidence"),
            "awaiting_gate_count": statuses.count("awaiting_gate"),
            "attention_count": len(attention_items),
            "dispatch_authority_granted": False,
        },
        "handoffs": handoff_rows,
        "attention_items": attention_items,
        "source_timeline_url": f"/api/v1/cases/{quote(case_id, safe='')}/proof-timeline",
        "source_audit_url": f"/api/v1/cases/{quote(case_id, safe='')}/audit-explorer",
        "governed": True,
    }


def _proof_explorer_rows(rows: list[dict[str, object]], columns: tuple[str, ...]) -> str:
    if not rows:
        return f"<tr><td colspan=\"{len(columns)}\">No records</td></tr>"
    return "\n".join(
        "<tr>"
        + "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns)
        + "</tr>"
        for row in rows
    )


def _proof_explorer_table(title: str, columns: tuple[str, ...], rows: list[dict[str, object]]) -> str:
    heading = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = _proof_explorer_rows(rows, columns)
    return f"""
    <section>
      <h2>{escape(title)}</h2>
      <table>
        <thead><tr>{heading}</tr></thead>
        <tbody>{body}</tbody>
      </table>
    </section>
    """


def _proof_explorer_ref_list(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(ref) for ref in value)
    return ""


def _render_case_proof_explorer_html(payload: dict[str, Any]) -> str:
    title = escape(str(payload.get("title", "")))
    raw_case_id = str(payload.get("case_id", ""))
    case_id = escape(raw_case_id)
    terminal_status = escape(str(payload.get("terminal_status", "")))
    quoted_case_id = quote(raw_case_id, safe="")
    json_url = f"/api/v1/cases/{quoted_case_id}/proof-explorer"
    timeline_url = f"/api/v1/cases/{quoted_case_id}/proof-timeline"
    status_cards = "\n".join(
        "<li>"
        f"<span>{escape(str(item.get('label', '')))}</span>"
        f"<strong>{escape(str(item.get('value', '')))}</strong>"
        f"<em>{escape(str(item.get('status', '')))}</em>"
        "</li>"
        for item in payload.get("status_cards", [])
        if isinstance(item, dict)
    )
    attention_rows = [
        {
            "severity": item.get("severity", ""),
            "kind": item.get("kind", ""),
            "ref": item.get("ref", ""),
            "message": item.get("message", ""),
        }
        for item in payload.get("attention_items", [])
        if isinstance(item, dict)
    ]
    department_rows = [
        {
            "department_id": item.get("department_id", ""),
            "steps": len(item.get("step_ids", [])) if isinstance(item.get("step_ids", []), list) else 0,
            "allowed": item.get("allowed_step_count", 0),
            "blocked": item.get("blocked_step_count", 0),
            "missing_evidence": item.get("missing_evidence_count", 0),
            "evidence_refs": item.get("evidence_ref_count", 0),
        }
        for item in payload.get("department_lanes", [])
        if isinstance(item, dict)
    ]
    evidence_rows = [
        {
            "requirement_id": item.get("requirement_id", ""),
            "present": item.get("present", False),
            "evidence_refs": _proof_explorer_ref_list(item.get("evidence_refs", [])),
            "step_ids": _proof_explorer_ref_list(item.get("step_ids", [])),
        }
        for item in payload.get("evidence_matrix", [])
        if isinstance(item, dict)
    ]
    proof_sections = payload.get("proof_sections", {})
    section_rows = [
        {"section": key, "count": len(value) if isinstance(value, list) else 0}
        for key, value in sorted(proof_sections.items())
    ] if isinstance(proof_sections, dict) else []
    closure_panel = payload.get("closure_panel")
    closure_rows: list[dict[str, object]] = []
    if isinstance(closure_panel, dict):
        closure_rows = [
            {"field": "closure_id", "value": closure_panel.get("closure_id", "")},
            {"field": "terminal_certificate_id", "value": closure_panel.get("terminal_certificate_id", "")},
            {"field": "terminal_disposition", "value": closure_panel.get("terminal_disposition", "")},
            {"field": "effect_reconciled", "value": closure_panel.get("effect_reconciled", False)},
            {"field": "learning_admitted", "value": closure_panel.get("learning_admitted", False)},
        ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mullu OrgOS Proof Explorer</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; color: #1f2937; background: #f7f7f4; }}
    header {{ background: #16372e; color: #ffffff; padding: 24px 28px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 22px; }}
    nav {{ display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }}
    nav a {{ color: #b8f3dc; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; letter-spacing: 0; }}
    .status {{ margin-top: 8px; color: #d9efe6; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; padding: 0; margin: 18px 0; }}
    .metrics li {{ list-style: none; border: 1px solid #cfd7d1; border-radius: 6px; padding: 10px; background: #ffffff; min-height: 76px; }}
    .metrics span, .metrics em {{ display: block; color: #5b6470; font-size: 12px; font-style: normal; }}
    .metrics strong {{ display: block; margin: 5px 0; font-size: 20px; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; overflow-wrap: anywhere; }}
    th {{ background: #edf1ee; color: #26312d; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu OrgOS Proof Explorer</h1>
    <div class="status">Case <strong>{case_id}</strong> | Status <strong>{terminal_status}</strong></div>
    <nav>
      <a href="{escape(json_url)}">json explorer</a>
      <a href="{escape(timeline_url)}">proof timeline</a>
    </nav>
  </header>
  <main>
    <h2>{title}</h2>
    <ul class="metrics">{status_cards}</ul>
    {_proof_explorer_table("Attention", ("severity", "kind", "ref", "message"), attention_rows)}
    {_proof_explorer_table("Departments", ("department_id", "steps", "allowed", "blocked", "missing_evidence", "evidence_refs"), department_rows)}
    {_proof_explorer_table("Evidence", ("requirement_id", "present", "evidence_refs", "step_ids"), evidence_rows)}
    {_proof_explorer_table("Closure", ("field", "value"), closure_rows)}
    {_proof_explorer_table("Proof Sections", ("section", "count"), section_rows)}
  </main>
</body>
</html>
"""


def _render_case_audit_explorer_html(payload: dict[str, Any]) -> str:
    raw_case_id = str(payload.get("case_id", ""))
    case_id = escape(raw_case_id)
    title = escape(str(payload.get("title", "")))
    terminal_status = escape(str(payload.get("terminal_status", "")))
    summary = payload.get("summary", {})
    summary_rows = [
        {"metric": key, "value": value}
        for key, value in sorted(summary.items())
    ] if isinstance(summary, dict) else []
    attention_rows = [
        {
            "severity": item.get("severity", ""),
            "kind": item.get("kind", ""),
            "ref": item.get("ref", ""),
            "message": item.get("message", ""),
        }
        for item in payload.get("attention_items", [])
        if isinstance(item, dict)
    ]
    timeline_rows = [
        {
            "sequence": item.get("sequence", ""),
            "occurred_at": item.get("occurred_at", ""),
            "layer": item.get("layer", ""),
            "kind": item.get("kind", ""),
            "ref": item.get("ref", ""),
            "status": item.get("status", ""),
            "step_id": item.get("step_id", ""),
            "reason": item.get("reason", ""),
        }
        for item in payload.get("audit_timeline", [])
        if isinstance(item, dict)
    ]
    section_rows = [
        {
            "section": item.get("section", ""),
            "count": item.get("count", 0),
        }
        for item in payload.get("proof_section_counts", [])
        if isinstance(item, dict)
    ]
    json_url = f"/api/v1/cases/{quote(raw_case_id, safe='')}/audit-explorer"
    case_url = f"/api/v1/cases/{quote(raw_case_id, safe='')}"
    proof_timeline_url = escape(str(payload.get("source_timeline_url", "")))
    proof_explorer_url = escape(str(payload.get("source_explorer_url", "")))
    closure_certificate_url = escape(str(payload.get("closure_certificate_url", "")))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mullu OrgOS Case Audit Explorer</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; color: #1f2937; background: #f7f7f4; }}
    header {{ background: #263238; color: #ffffff; padding: 24px 28px; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 22px; }}
    nav {{ display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }}
    nav a {{ color: #cde8ff; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; letter-spacing: 0; }}
    .status {{ margin-top: 8px; color: #e0edf2; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; overflow-wrap: anywhere; }}
    th {{ background: #edf2f5; color: #253238; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu OrgOS Case Audit Explorer</h1>
    <div class="status">Case <strong>{case_id}</strong> | Status <strong>{terminal_status}</strong></div>
    <nav>
      <a href="{escape(json_url)}">json audit</a>
      <a href="{escape(case_url)}">case bundle</a>
      <a href="{proof_timeline_url}">proof timeline</a>
      <a href="{proof_explorer_url}">proof explorer</a>
      <a href="{closure_certificate_url}">closure certificate</a>
    </nav>
  </header>
  <main>
    <h2>{title}</h2>
    {_proof_explorer_table("Summary", ("metric", "value"), summary_rows)}
    {_proof_explorer_table("Attention", ("severity", "kind", "ref", "message"), attention_rows)}
    {_proof_explorer_table("Audit Timeline", ("sequence", "occurred_at", "layer", "kind", "ref", "status", "step_id", "reason"), timeline_rows)}
    {_proof_explorer_table("Proof Sections", ("section", "count"), section_rows)}
  </main>
</body>
</html>
"""


def _render_case_step_handoffs_html(payload: dict[str, Any]) -> str:
    raw_case_id = str(payload.get("case_id", ""))
    case_id = escape(raw_case_id)
    title = escape(str(payload.get("title", "")))
    summary = payload.get("summary", {})
    summary_rows = [
        {"metric": key, "value": value}
        for key, value in sorted(summary.items())
    ] if isinstance(summary, dict) else []
    attention_rows = [
        {
            "severity": item.get("severity", ""),
            "kind": item.get("kind", ""),
            "ref": item.get("ref", ""),
            "message": item.get("message", ""),
        }
        for item in payload.get("attention_items", [])
        if isinstance(item, dict)
    ]
    handoff_rows = [
        {
            "step_id": item.get("step_id", ""),
            "department": item.get("department_id", ""),
            "capability": item.get("capability_id", ""),
            "action": item.get("action", ""),
            "gate_status": item.get("gate_status", ""),
            "handoff_status": item.get("handoff_status", ""),
            "next_action": item.get("next_action", ""),
            "worker_receipts": item.get("worker_receipt_count", 0),
            "dispatch_authority": item.get("dispatch_authority", False),
        }
        for item in payload.get("handoffs", [])
        if isinstance(item, dict)
    ]
    quoted_case_id = quote(raw_case_id, safe="")
    json_url = f"/api/v1/cases/{quoted_case_id}/step-handoffs"
    timeline_url = escape(str(payload.get("source_timeline_url", "")))
    audit_url = escape(str(payload.get("source_audit_url", "")))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mullu OrgOS Step Handoffs</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; color: #1f2937; background: #f7f7f4; }}
    header {{ background: #2f353f; color: #ffffff; padding: 24px 28px; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 22px; }}
    nav {{ display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }}
    nav a {{ color: #d2e8ff; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; letter-spacing: 0; }}
    .status {{ margin-top: 8px; color: #e4edf6; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; overflow-wrap: anywhere; }}
    th {{ background: #edf0f5; color: #263041; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu OrgOS Step Handoffs</h1>
    <div class="status">Case <strong>{case_id}</strong></div>
    <nav>
      <a href="{escape(json_url)}">json handoffs</a>
      <a href="{timeline_url}">proof timeline</a>
      <a href="{audit_url}">case audit</a>
    </nav>
  </header>
  <main>
    <h2>{title}</h2>
    {_proof_explorer_table("Summary", ("metric", "value"), summary_rows)}
    {_proof_explorer_table("Attention", ("severity", "kind", "ref", "message"), attention_rows)}
    {_proof_explorer_table("Step Handoffs", ("step_id", "department", "capability", "action", "gate_status", "handoff_status", "next_action", "worker_receipts", "dispatch_authority"), handoff_rows)}
  </main>
</body>
</html>
"""


def _closure_status(closure_certificate: dict[str, Any] | None) -> str:
    if closure_certificate is None:
        return "awaiting_closure"
    if closure_certificate["effect_reconciled"] and closure_certificate["learning_admitted"]:
        return "closed_verified"
    if closure_certificate["effect_reconciled"]:
        return "closed_awaiting_learning"
    return "closed_requires_review"


def _case_closure_certificate(kernel: OrganizationKernel, case_id: str) -> dict[str, Any]:
    proof = _case_proof_timeline(kernel, case_id)
    closure_certificate = proof["closure_certificate"]
    status = _closure_status(closure_certificate)
    attention_items: list[dict[str, object]] = []
    reconciliation: dict[str, Any] | None = None
    learning_admissions: list[dict[str, Any]] = []
    evidence_refs: list[str] = []

    if closure_certificate is None:
        attention_items.append({
            "kind": "missing_terminal_closure",
            "severity": "review",
            "ref": case_id,
            "message": "case has no terminal closure certificate",
        })
    else:
        reconciliation_value = closure_certificate.get("reconciliation")
        if isinstance(reconciliation_value, dict):
            reconciliation = reconciliation_value
        learning_value = closure_certificate.get("learning_admissions")
        if isinstance(learning_value, list):
            learning_admissions = [item for item in learning_value if isinstance(item, dict)]
        evidence_value = closure_certificate.get("evidence_refs")
        if isinstance(evidence_value, list):
            evidence_refs = [str(item) for item in evidence_value]
        if reconciliation is None:
            attention_items.append({
                "kind": "missing_reconciliation",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "terminal closure is not bound to an effect reconciliation record",
            })
        elif not closure_certificate["effect_reconciled"]:
            attention_items.append({
                "kind": "effect_not_reconciled",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "expected effect and observed effect are not closure-matched",
            })
        if not closure_certificate["learning_admitted"]:
            attention_items.append({
                "kind": "learning_not_admitted",
                "severity": "review",
                "ref": closure_certificate["closure_id"],
                "message": "closure has not been admitted into reusable learning",
            })

    return {
        "certificate_view_id": f"closure-certificate:{case_id}",
        "case_id": case_id,
        "title": proof["case"]["goal"],
        "terminal_status": status,
        "read_only": True,
        "case": proof["case"],
        "summary": proof["summary"],
        "closure_certificate": closure_certificate,
        "reconciliation": reconciliation,
        "learning_admissions": learning_admissions,
        "evidence_refs": evidence_refs,
        "attention_items": attention_items,
        "source_timeline_url": f"/api/v1/cases/{quote(case_id, safe='')}/proof-timeline",
        "source_explorer_url": f"/api/v1/cases/{quote(case_id, safe='')}/proof-explorer",
        "governed": True,
    }


def _render_case_closure_certificate_html(payload: dict[str, Any]) -> str:
    raw_case_id = str(payload.get("case_id", ""))
    case_id = escape(raw_case_id)
    title = escape(str(payload.get("title", "")))
    terminal_status = escape(str(payload.get("terminal_status", "")))
    closure_certificate = payload.get("closure_certificate")
    certificate_rows: list[dict[str, object]] = []
    if isinstance(closure_certificate, dict):
        certificate_rows = [
            {"field": "closure_id", "value": closure_certificate.get("closure_id", "")},
            {"field": "terminal_certificate_id", "value": closure_certificate.get("terminal_certificate_id", "")},
            {"field": "terminal_disposition", "value": closure_certificate.get("terminal_disposition", "")},
            {"field": "closed_at", "value": closure_certificate.get("closed_at", "")},
            {"field": "effect_reconciled", "value": closure_certificate.get("effect_reconciled", False)},
            {"field": "learning_admitted", "value": closure_certificate.get("learning_admitted", False)},
        ]
    attention_rows = [
        {
            "severity": item.get("severity", ""),
            "kind": item.get("kind", ""),
            "ref": item.get("ref", ""),
            "message": item.get("message", ""),
        }
        for item in payload.get("attention_items", [])
        if isinstance(item, dict)
    ]
    reconciliation = payload.get("reconciliation")
    reconciliation_rows: list[dict[str, object]] = []
    if isinstance(reconciliation, dict):
        reconciliation_rows = [
            {"field": "reconciliation_id", "value": reconciliation.get("reconciliation_id", "")},
            {"field": "status", "value": reconciliation.get("status", "")},
            {"field": "expected_effect", "value": reconciliation.get("expected_effect", "")},
            {"field": "observed_effect", "value": reconciliation.get("observed_effect", "")},
            {"field": "forbidden_effects_checked", "value": reconciliation.get("forbidden_effects_checked", False)},
        ]
    evidence_rows = [{"evidence_ref": ref} for ref in payload.get("evidence_refs", []) if isinstance(ref, str)]
    learning_rows = [
        {
            "binding_id": item.get("binding_id", ""),
            "decision_id": item.get("decision_id", ""),
            "admitted": item.get("admitted", False),
            "created_at": item.get("created_at", ""),
        }
        for item in payload.get("learning_admissions", [])
        if isinstance(item, dict)
    ]
    proof_timeline_url = escape(str(payload.get("source_timeline_url", "")))
    proof_explorer_url = escape(str(payload.get("source_explorer_url", "")))
    json_url = f"/api/v1/cases/{quote(raw_case_id, safe='')}/closure-certificate"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mullu OrgOS Terminal Closure Certificate</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; color: #1f2937; background: #f8f7f2; }}
    header {{ background: #293326; color: #ffffff; padding: 24px 28px; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 22px; }}
    nav {{ display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }}
    nav a {{ color: #c9f1c9; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; letter-spacing: 0; }}
    .status {{ margin-top: 8px; color: #dfeadd; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d9ded7; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; overflow-wrap: anywhere; }}
    th {{ background: #edf0e9; color: #263126; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu OrgOS Terminal Closure Certificate</h1>
    <div class="status">Case <strong>{case_id}</strong> | Status <strong>{terminal_status}</strong></div>
    <nav>
      <a href="{escape(json_url)}">json certificate</a>
      <a href="{proof_timeline_url}">proof timeline</a>
      <a href="{proof_explorer_url}">proof explorer</a>
    </nav>
  </header>
  <main>
    <h2>{title}</h2>
    {_proof_explorer_table("Attention", ("severity", "kind", "ref", "message"), attention_rows)}
    {_proof_explorer_table("Certificate", ("field", "value"), certificate_rows)}
    {_proof_explorer_table("Reconciliation", ("field", "value"), reconciliation_rows)}
    {_proof_explorer_table("Evidence Refs", ("evidence_ref",), evidence_rows)}
    {_proof_explorer_table("Learning Admissions", ("binding_id", "decision_id", "admitted", "created_at"), learning_rows)}
  </main>
</body>
</html>
"""


def _text_list(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return ""


def _organization_department_registry(kernel: OrganizationKernel, org_id: str) -> dict[str, Any]:
    organization = _organization_or_404(kernel, org_id)
    state = kernel.snapshot_state()
    departments = tuple(item for item in state.departments if item.org_id == org_id)
    roles_by_department: dict[str, list[dict[str, Any]]] = {}
    authority_by_department: dict[str, list[dict[str, Any]]] = {}
    capabilities_by_department: dict[str, list[dict[str, Any]]] = {}
    evidence_by_department: dict[str, list[dict[str, Any]]] = {}
    cases_by_primary_department: dict[str, int] = {}
    cases_by_assigned_department: dict[str, int] = {}
    attention_items: list[dict[str, object]] = []

    for role in state.roles:
        if role.org_id == org_id:
            roles_by_department.setdefault(role.department_id, []).append(_body(role))
    for rule in state.authority_rules:
        if rule.org_id == org_id:
            authority_by_department.setdefault(rule.department_id, []).append(_body(rule))
    for capability in state.capabilities:
        if capability.org_id == org_id:
            capabilities_by_department.setdefault(capability.department_id, []).append(_body(capability))
    for requirement in state.evidence_requirements:
        if requirement.org_id == org_id:
            evidence_by_department.setdefault(requirement.department_id, []).append(_body(requirement))
    for organization_case in state.cases:
        if organization_case.org_id != org_id:
            continue
        cases_by_primary_department[organization_case.department_id] = (
            cases_by_primary_department.get(organization_case.department_id, 0) + 1
        )
        for department_id in organization_case.assigned_department_ids:
            cases_by_assigned_department[department_id] = cases_by_assigned_department.get(department_id, 0) + 1

    department_rows: list[dict[str, Any]] = []
    for department in sorted(departments, key=lambda item: item.department_id):
        roles = roles_by_department.get(department.department_id, [])
        authority_rules = authority_by_department.get(department.department_id, [])
        capabilities = capabilities_by_department.get(department.department_id, [])
        evidence_requirements = evidence_by_department.get(department.department_id, [])
        role_ids = {str(item.get("role_id", "")) for item in roles}
        capability_ids = {str(item.get("capability_id", "")) for item in capabilities}
        evidence_ids = {str(item.get("requirement_id", "")) for item in evidence_requirements}
        missing_owner_roles = not any(
            item.get("is_human_accountable") and "own_case" in item.get("permissions", ())
            for item in roles
        )
        missing_capability_bindings = [
            capability_id for capability_id in department.allowed_capabilities
            if capability_id not in capability_ids
        ]
        uncertified_capabilities = [
            str(item.get("capability_id", ""))
            for item in capabilities
            if not item.get("certified", False)
        ]
        missing_evidence_rules = [
            requirement_id for requirement_id in department.required_evidence
            if requirement_id not in evidence_ids
        ]
        authority_role_gaps = [
            str(item.get("rule_id", ""))
            for item in authority_rules
            if str(item.get("role_id", "")) not in role_ids
        ]
        readiness_gaps = (
            (["missing_owner_role"] if missing_owner_roles else [])
            + [f"missing_capability:{item}" for item in missing_capability_bindings]
            + [f"uncertified_capability:{item}" for item in uncertified_capabilities]
            + [f"missing_evidence_rule:{item}" for item in missing_evidence_rules]
            + [f"authority_role_gap:{item}" for item in authority_role_gaps]
        )
        readiness = "ready" if not readiness_gaps else "needs_review"
        if readiness_gaps:
            attention_items.append({
                "kind": "department_readiness_gap",
                "severity": "review",
                "ref": department.department_id,
                "message": "department readiness gaps require review",
                "gaps": readiness_gaps,
            })
        department_rows.append({
            "department": _body(department),
            "readiness": readiness,
            "readiness_gaps": readiness_gaps,
            "role_ids": sorted(role_ids),
            "authority_rule_ids": sorted(str(item.get("rule_id", "")) for item in authority_rules),
            "capability_ids": sorted(capability_ids),
            "evidence_requirement_ids": sorted(evidence_ids),
            "primary_case_count": cases_by_primary_department.get(department.department_id, 0),
            "assigned_case_count": cases_by_assigned_department.get(department.department_id, 0),
            "roles": sorted(roles, key=lambda item: str(item.get("role_id", ""))),
            "authority_rules": sorted(authority_rules, key=lambda item: str(item.get("rule_id", ""))),
            "capabilities": sorted(capabilities, key=lambda item: str(item.get("capability_id", ""))),
            "evidence_requirements": sorted(
                evidence_requirements,
                key=lambda item: str(item.get("requirement_id", "")),
            ),
        })

    ready_count = sum(1 for item in department_rows if item["readiness"] == "ready")
    return {
        "registry_id": f"department-registry:{org_id}",
        "org_id": org_id,
        "organization": _body(organization),
        "read_only": True,
        "summary": {
            "department_count": len(department_rows),
            "ready_department_count": ready_count,
            "review_department_count": len(department_rows) - ready_count,
            "role_count": sum(len(item["roles"]) for item in department_rows),
            "authority_rule_count": sum(len(item["authority_rules"]) for item in department_rows),
            "capability_count": sum(len(item["capabilities"]) for item in department_rows),
            "evidence_requirement_count": sum(len(item["evidence_requirements"]) for item in department_rows),
        },
        "departments": department_rows,
        "attention_items": attention_items,
        "governed": True,
    }


def _escalation_path(
    department: DepartmentPack,
    departments_by_id: dict[str, DepartmentPack],
) -> list[dict[str, Any]]:
    return [
        {
            "department_id": escalation_department_id,
            "name": departments_by_id[escalation_department_id].name
            if escalation_department_id in departments_by_id
            else None,
            "known": escalation_department_id in departments_by_id,
        }
        for escalation_department_id in department.escalation_departments
    ]


def _organization_authority_map(kernel: OrganizationKernel, org_id: str) -> dict[str, Any]:
    organization = _organization_or_404(kernel, org_id)
    state = kernel.snapshot_state()
    departments = tuple(item for item in state.departments if item.org_id == org_id)
    departments_by_id = {department.department_id: department for department in departments}
    roles_by_department: dict[str, list[Any]] = {}
    authority_by_department: dict[str, list[Any]] = {}
    authority_by_role: dict[str, list[Any]] = {}
    capabilities_by_department: dict[str, list[Any]] = {}
    capabilities_by_id: dict[str, list[Any]] = {}
    evidence_by_department: dict[str, list[Any]] = {}
    attention_items: list[dict[str, object]] = []

    for role in state.roles:
        if role.org_id == org_id:
            roles_by_department.setdefault(role.department_id, []).append(role)
    for rule in state.authority_rules:
        if rule.org_id == org_id:
            authority_by_department.setdefault(rule.department_id, []).append(rule)
            authority_by_role.setdefault(rule.role_id, []).append(rule)
    for capability in state.capabilities:
        if capability.org_id == org_id:
            capabilities_by_department.setdefault(capability.department_id, []).append(capability)
            capabilities_by_id.setdefault(capability.capability_id, []).append(capability)
    for requirement in state.evidence_requirements:
        if requirement.org_id == org_id:
            evidence_by_department.setdefault(requirement.department_id, []).append(requirement)

    department_rows: list[dict[str, Any]] = []
    for department in sorted(departments, key=lambda item: item.department_id):
        department_roles = sorted(
            roles_by_department.get(department.department_id, []),
            key=lambda item: item.role_id,
        )
        department_authority = sorted(
            authority_by_department.get(department.department_id, []),
            key=lambda item: item.rule_id,
        )
        department_capabilities = sorted(
            capabilities_by_department.get(department.department_id, []),
            key=lambda item: item.capability_id,
        )
        department_evidence = sorted(
            evidence_by_department.get(department.department_id, []),
            key=lambda item: item.requirement_id,
        )
        department_role_ids = {role.role_id for role in department_roles}
        capability_ids = {capability.capability_id for capability in department_capabilities}
        evidence_ids = {requirement.requirement_id for requirement in department_evidence}
        role_authority_chains: list[dict[str, Any]] = []
        department_gaps: list[str] = []

        if not any(role.is_human_accountable and "own_case" in role.permissions for role in department_roles):
            department_gaps.append("missing_owner_role")
        for rule in department_authority:
            if rule.role_id not in department_role_ids:
                department_gaps.append(f"authority_role_gap:{rule.rule_id}")
        for capability_id in department.allowed_capabilities:
            if capability_id not in capability_ids:
                department_gaps.append(f"missing_capability:{capability_id}")
        for capability in department_capabilities:
            if not capability.certified:
                department_gaps.append(f"uncertified_capability:{capability.capability_id}")
        for requirement_id in department.required_evidence:
            if requirement_id not in evidence_ids:
                department_gaps.append(f"missing_evidence_rule:{requirement_id}")
        for escalation_ref in _escalation_path(department, departments_by_id):
            if not escalation_ref["known"]:
                department_gaps.append(f"unknown_escalation_department:{escalation_ref['department_id']}")

        for role in department_roles:
            role_rules = sorted(
                (
                    rule for rule in authority_by_role.get(role.role_id, [])
                    if rule.department_id == department.department_id
                ),
                key=lambda item: item.rule_id,
            )
            role_gaps: list[str] = []
            if not role_rules:
                role_gaps.append("role_has_no_authority_rule")
            authority_chain: list[dict[str, Any]] = []
            for rule in role_rules:
                matching_capabilities = [
                    capability
                    for capability in capabilities_by_id.get(rule.resource_type, [])
                    if capability.department_id == department.department_id
                ]
                matching_evidence = [
                    requirement
                    for requirement in department_evidence
                    if requirement.requirement_id in department.required_evidence
                ]
                rule_gaps: list[str] = []
                if not matching_capabilities:
                    rule_gaps.append(f"missing_capability:{rule.resource_type}")
                for capability in matching_capabilities:
                    if not capability.certified:
                        rule_gaps.append(f"uncertified_capability:{capability.capability_id}")
                for requirement_id in department.required_evidence:
                    if requirement_id not in evidence_ids:
                        rule_gaps.append(f"missing_evidence_rule:{requirement_id}")
                authority_chain.append({
                    "authority_rule": _body(rule),
                    "capabilities": [_body(capability) for capability in matching_capabilities],
                    "capability_ids": sorted(capability.capability_id for capability in matching_capabilities),
                    "evidence_requirements": [_body(requirement) for requirement in matching_evidence],
                    "evidence_requirement_ids": sorted(
                        requirement.requirement_id for requirement in matching_evidence
                    ),
                    "escalation_path": _escalation_path(department, departments_by_id),
                    "gaps": rule_gaps,
                })
            role_authority_chains.append({
                "role": _body(role),
                "authority_chain": authority_chain,
                "gaps": role_gaps,
            })
            department_gaps.extend(role_gaps)

        if department_gaps:
            attention_items.append({
                "kind": "authority_map_gap",
                "severity": "review",
                "ref": department.department_id,
                "message": "department authority map has unresolved bindings",
                "gaps": sorted(set(department_gaps)),
            })
        department_rows.append({
            "department": _body(department),
            "map_status": "mapped" if not department_gaps else "needs_review",
            "gaps": sorted(set(department_gaps)),
            "role_authority_chains": role_authority_chains,
            "role_ids": sorted(department_role_ids),
            "authority_rule_ids": sorted(rule.rule_id for rule in department_authority),
            "capability_ids": sorted(capability_ids),
            "evidence_requirement_ids": sorted(evidence_ids),
            "escalation_path": _escalation_path(department, departments_by_id),
        })

    mapped_count = sum(1 for item in department_rows if item["map_status"] == "mapped")
    return {
        "authority_map_id": f"authority-map:{org_id}",
        "org_id": org_id,
        "organization": _body(organization),
        "read_only": True,
        "summary": {
            "department_count": len(department_rows),
            "mapped_department_count": mapped_count,
            "review_department_count": len(department_rows) - mapped_count,
            "role_count": sum(len(item["role_ids"]) for item in department_rows),
            "authority_rule_count": sum(len(item["authority_rule_ids"]) for item in department_rows),
            "capability_count": sum(len(item["capability_ids"]) for item in department_rows),
            "evidence_requirement_count": sum(len(item["evidence_requirement_ids"]) for item in department_rows),
            "escalation_path_count": sum(len(item["escalation_path"]) for item in department_rows),
            "map_gap_count": sum(len(item["gaps"]) for item in department_rows),
        },
        "departments": department_rows,
        "attention_items": attention_items,
        "governed": True,
    }


def _open_case_terminal_status(proof: dict[str, Any]) -> str:
    summary = proof["summary"]
    if summary["blocked_steps"]:
        return "blocked_by_plan_gate"
    if summary["has_plan"]:
        return "awaiting_evidence"
    return "awaiting_plan"


def _case_portfolio_terminal_status(proof: dict[str, Any]) -> str:
    closure_certificate = proof["closure_certificate"]
    if closure_certificate is not None:
        return _closure_status(closure_certificate)
    return _open_case_terminal_status(proof)


def _case_portfolio_attention(case_id: str, proof: dict[str, Any]) -> list[dict[str, object]]:
    summary = proof["summary"]
    closure_certificate = proof["closure_certificate"]
    attention_items: list[dict[str, object]] = []
    if not summary["has_plan"]:
        attention_items.append({
            "kind": "missing_plan",
            "severity": "review",
            "ref": case_id,
            "message": "case has no governed plan",
        })
    if summary["blocked_steps"]:
        attention_items.append({
            "kind": "blocked_plan_steps",
            "severity": "blocker",
            "ref": case_id,
            "message": "case has blocked or unevaluated plan steps",
            "step_ids": summary["blocked_steps"],
        })
    if closure_certificate is None:
        attention_items.append({
            "kind": "missing_terminal_closure",
            "severity": "review",
            "ref": case_id,
            "message": "case has no terminal closure certificate",
        })
    elif not closure_certificate["effect_reconciled"]:
        attention_items.append({
            "kind": "effect_not_reconciled",
            "severity": "blocker",
            "ref": closure_certificate["closure_id"],
            "message": "terminal closure does not have a reconciled external effect",
        })
    elif not closure_certificate["learning_admitted"]:
        attention_items.append({
            "kind": "learning_not_admitted",
            "severity": "review",
            "ref": closure_certificate["closure_id"],
            "message": "closure has not been admitted into reusable learning",
        })
    return attention_items


def _organization_case_portfolio(kernel: OrganizationKernel, org_id: str) -> dict[str, Any]:
    organization = _organization_or_404(kernel, org_id)
    state = kernel.snapshot_state()
    departments = tuple(item for item in state.departments if item.org_id == org_id)
    departments_by_id = {department.department_id: department for department in departments}
    cases = tuple(
        sorted(
            (item for item in state.cases if item.org_id == org_id),
            key=lambda item: item.case_id,
        )
    )
    department_lanes: dict[str, dict[str, object]] = {
        department.department_id: {
            "department_id": department.department_id,
            "name": department.name,
            "primary_case_count": 0,
            "assigned_case_count": 0,
            "open_case_count": 0,
            "closed_case_count": 0,
            "blocked_case_count": 0,
            "review_case_count": 0,
            "case_ids": [],
        }
        for department in departments
    }
    case_rows: list[dict[str, Any]] = []
    attention_items: list[dict[str, object]] = []

    for organization_case in cases:
        proof = _case_proof_timeline(kernel, organization_case.case_id)
        closure_certificate = proof["closure_certificate"]
        terminal_status = _case_portfolio_terminal_status(proof)
        case_attention = _case_portfolio_attention(organization_case.case_id, proof)
        blocker_count = sum(1 for item in case_attention if item.get("severity") == "blocker")
        review_count = sum(1 for item in case_attention if item.get("severity") == "review")
        primary_lane = department_lanes.setdefault(
            organization_case.department_id,
            {
                "department_id": organization_case.department_id,
                "name": departments_by_id.get(organization_case.department_id).name
                if organization_case.department_id in departments_by_id
                else "",
                "primary_case_count": 0,
                "assigned_case_count": 0,
                "open_case_count": 0,
                "closed_case_count": 0,
                "blocked_case_count": 0,
                "review_case_count": 0,
                "case_ids": [],
            },
        )
        primary_lane["primary_case_count"] = int(primary_lane["primary_case_count"]) + 1
        primary_lane["case_ids"].append(organization_case.case_id)
        if organization_case.status is OrganizationCaseStatus.CLOSED:
            primary_lane["closed_case_count"] = int(primary_lane["closed_case_count"]) + 1
        else:
            primary_lane["open_case_count"] = int(primary_lane["open_case_count"]) + 1
        if blocker_count:
            primary_lane["blocked_case_count"] = int(primary_lane["blocked_case_count"]) + 1
        if review_count:
            primary_lane["review_case_count"] = int(primary_lane["review_case_count"]) + 1
        for department_id in organization_case.assigned_department_ids:
            assigned_lane = department_lanes.setdefault(
                department_id,
                {
                    "department_id": department_id,
                    "name": departments_by_id.get(department_id).name if department_id in departments_by_id else "",
                    "primary_case_count": 0,
                    "assigned_case_count": 0,
                    "open_case_count": 0,
                    "closed_case_count": 0,
                    "blocked_case_count": 0,
                    "review_case_count": 0,
                    "case_ids": [],
                },
            )
            assigned_lane["assigned_case_count"] = int(assigned_lane["assigned_case_count"]) + 1
        attention_items.extend(case_attention)
        case_rows.append({
            "case": _body(organization_case),
            "terminal_status": terminal_status,
            "attention_count": len(case_attention),
            "blocker_count": blocker_count,
            "review_count": review_count,
            "plan_id": proof["plan_id"],
            "blocked_step_count": len(proof["summary"]["blocked_steps"]),
            "evidence_count": proof["summary"]["evidence_count"],
            "approval_count": proof["summary"]["approval_count"],
            "gate_decision_count": proof["summary"]["gate_decision_count"],
            "worker_receipt_count": proof["summary"]["worker_receipt_count"],
            "has_terminal_closure": closure_certificate is not None,
            "effect_reconciled": bool(closure_certificate and closure_certificate["effect_reconciled"]),
            "learning_admitted": bool(closure_certificate and closure_certificate["learning_admitted"]),
            "links": {
                "case": f"/api/v1/cases/{quote(organization_case.case_id, safe='')}",
                "audit": f"/api/v1/cases/{quote(organization_case.case_id, safe='')}/audit-explorer/view",
                "proof": f"/api/v1/cases/{quote(organization_case.case_id, safe='')}/proof-explorer/view",
                "closure": f"/api/v1/cases/{quote(organization_case.case_id, safe='')}/closure-certificate/view",
            },
        })

    open_count = sum(1 for item in cases if item.status is not OrganizationCaseStatus.CLOSED)
    closed_count = len(cases) - open_count
    high_risk_count = sum(
        1 for item in cases
        if item.risk in {OrganizationRisk.HIGH, OrganizationRisk.CRITICAL}
    )
    blocked_case_count = sum(1 for item in case_rows if item["blocker_count"])
    review_case_count = sum(1 for item in case_rows if item["review_count"])
    return {
        "portfolio_id": f"case-portfolio:{org_id}",
        "org_id": org_id,
        "organization": _body(organization),
        "read_only": True,
        "summary": {
            "case_count": len(case_rows),
            "open_case_count": open_count,
            "closed_case_count": closed_count,
            "high_risk_case_count": high_risk_count,
            "blocked_case_count": blocked_case_count,
            "review_case_count": review_case_count,
            "department_count": len(department_lanes),
            "terminal_closure_count": sum(1 for item in case_rows if item["has_terminal_closure"]),
            "learning_admitted_count": sum(1 for item in case_rows if item["learning_admitted"]),
            "attention_count": len(attention_items),
        },
        "department_lanes": sorted(department_lanes.values(), key=lambda item: str(item["department_id"])),
        "cases": case_rows,
        "attention_items": attention_items,
        "governed": True,
    }


def _render_department_registry_html(payload: dict[str, Any]) -> str:
    raw_org_id = str(payload.get("org_id", ""))
    org_id = escape(raw_org_id)
    organization = payload.get("organization", {})
    org_name = escape(str(organization.get("name", ""))) if isinstance(organization, dict) else ""
    summary = payload.get("summary", {})
    summary_rows = [
        {"metric": key, "value": value}
        for key, value in sorted(summary.items())
    ] if isinstance(summary, dict) else []
    department_rows = [
        {
            "department_id": item.get("department", {}).get("department_id", ""),
            "name": item.get("department", {}).get("name", ""),
            "readiness": item.get("readiness", ""),
            "owns": _text_list(item.get("department", {}).get("owns", [])),
            "case_types": _text_list(item.get("department", {}).get("allowed_case_types", [])),
            "capabilities": _text_list(item.get("capability_ids", [])),
            "evidence": _text_list(item.get("evidence_requirement_ids", [])),
            "escalation": _text_list(item.get("department", {}).get("escalation_departments", [])),
        }
        for item in payload.get("departments", [])
        if isinstance(item, dict) and isinstance(item.get("department"), dict)
    ]
    attention_rows = [
        {
            "severity": item.get("severity", ""),
            "kind": item.get("kind", ""),
            "ref": item.get("ref", ""),
            "message": item.get("message", ""),
        }
        for item in payload.get("attention_items", [])
        if isinstance(item, dict)
    ]
    quoted_org_id = quote(raw_org_id, safe="")
    json_url = f"/api/v1/orgs/{quoted_org_id}/department-registry"
    simple_url = f"/api/v1/orgs/{quoted_org_id}/departments"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mullu OrgOS Department Registry</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; color: #1f2937; background: #f7f7f4; }}
    header {{ background: #2d3342; color: #ffffff; padding: 24px 28px; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 22px; }}
    nav {{ display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }}
    nav a {{ color: #c8dcff; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; letter-spacing: 0; }}
    .status {{ margin-top: 8px; color: #e4e9f6; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; overflow-wrap: anywhere; }}
    th {{ background: #edf0f5; color: #263041; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu OrgOS Department Registry</h1>
    <div class="status">Organization <strong>{org_id}</strong> | <strong>{org_name}</strong></div>
    <nav>
      <a href="{escape(json_url)}">json registry</a>
      <a href="{escape(simple_url)}">department list</a>
    </nav>
  </header>
  <main>
    {_proof_explorer_table("Summary", ("metric", "value"), summary_rows)}
    {_proof_explorer_table("Attention", ("severity", "kind", "ref", "message"), attention_rows)}
    {_proof_explorer_table("Departments", ("department_id", "name", "readiness", "owns", "case_types", "capabilities", "evidence", "escalation"), department_rows)}
  </main>
</body>
</html>
"""


def _render_authority_map_html(payload: dict[str, Any]) -> str:
    raw_org_id = str(payload.get("org_id", ""))
    org_id = escape(raw_org_id)
    organization = payload.get("organization", {})
    org_name = escape(str(organization.get("name", ""))) if isinstance(organization, dict) else ""
    summary = payload.get("summary", {})
    summary_rows = [
        {"metric": key, "value": value}
        for key, value in sorted(summary.items())
    ] if isinstance(summary, dict) else []
    authority_rows: list[dict[str, object]] = []
    for department_row in payload.get("departments", []):
        if not isinstance(department_row, dict) or not isinstance(department_row.get("department"), dict):
            continue
        department = department_row["department"]
        department_id = str(department.get("department_id", ""))
        for role_chain in department_row.get("role_authority_chains", []):
            if not isinstance(role_chain, dict) or not isinstance(role_chain.get("role"), dict):
                continue
            role = role_chain["role"]
            authority_chain = role_chain.get("authority_chain", [])
            if not authority_chain:
                authority_rows.append({
                    "department": department_id,
                    "role": role.get("role_id", ""),
                    "authority": "",
                    "action": "",
                    "capability": "",
                    "evidence": "",
                    "escalation": _text_list([
                        item.get("department_id", "")
                        for item in department_row.get("escalation_path", [])
                        if isinstance(item, dict)
                    ]),
                    "gaps": _text_list(role_chain.get("gaps", [])),
                })
            for authority_binding in authority_chain:
                if not isinstance(authority_binding, dict):
                    continue
                authority_rule = authority_binding.get("authority_rule", {})
                authority_rule = authority_rule if isinstance(authority_rule, dict) else {}
                authority_rows.append({
                    "department": department_id,
                    "role": role.get("role_id", ""),
                    "authority": authority_rule.get("rule_id", ""),
                    "action": authority_rule.get("action", ""),
                    "capability": _text_list(authority_binding.get("capability_ids", [])),
                    "evidence": _text_list(authority_binding.get("evidence_requirement_ids", [])),
                    "escalation": _text_list([
                        item.get("department_id", "")
                        for item in authority_binding.get("escalation_path", [])
                        if isinstance(item, dict)
                    ]),
                    "gaps": _text_list(authority_binding.get("gaps", [])),
                })
    attention_rows = [
        {
            "severity": item.get("severity", ""),
            "kind": item.get("kind", ""),
            "ref": item.get("ref", ""),
            "message": item.get("message", ""),
        }
        for item in payload.get("attention_items", [])
        if isinstance(item, dict)
    ]
    quoted_org_id = quote(raw_org_id, safe="")
    json_url = f"/api/v1/orgs/{quoted_org_id}/authority-map"
    registry_url = f"/api/v1/orgs/{quoted_org_id}/department-registry/view"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mullu OrgOS Authority Map</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; color: #1f2937; background: #f7f7f4; }}
    header {{ background: #243447; color: #ffffff; padding: 24px 28px; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 22px; }}
    nav {{ display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }}
    nav a {{ color: #c9e4ff; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; letter-spacing: 0; }}
    .status {{ margin-top: 8px; color: #e4edf6; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; overflow-wrap: anywhere; }}
    th {{ background: #edf0f5; color: #263041; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu OrgOS Authority Map</h1>
    <div class="status">Organization <strong>{org_id}</strong> | <strong>{org_name}</strong></div>
    <nav>
      <a href="{escape(json_url)}">json authority map</a>
      <a href="{escape(registry_url)}">department registry</a>
    </nav>
  </header>
  <main>
    {_proof_explorer_table("Summary", ("metric", "value"), summary_rows)}
    {_proof_explorer_table("Attention", ("severity", "kind", "ref", "message"), attention_rows)}
    {_proof_explorer_table("Authority Chain", ("department", "role", "authority", "action", "capability", "evidence", "escalation", "gaps"), authority_rows)}
  </main>
</body>
</html>
"""


def _render_case_portfolio_html(payload: dict[str, Any]) -> str:
    raw_org_id = str(payload.get("org_id", ""))
    org_id = escape(raw_org_id)
    organization = payload.get("organization", {})
    org_name = escape(str(organization.get("name", ""))) if isinstance(organization, dict) else ""
    summary = payload.get("summary", {})
    summary_rows = [
        {"metric": key, "value": value}
        for key, value in sorted(summary.items())
    ] if isinstance(summary, dict) else []
    attention_rows = [
        {
            "severity": item.get("severity", ""),
            "kind": item.get("kind", ""),
            "ref": item.get("ref", ""),
            "message": item.get("message", ""),
        }
        for item in payload.get("attention_items", [])
        if isinstance(item, dict)
    ]
    department_rows = [
        {
            "department_id": item.get("department_id", ""),
            "name": item.get("name", ""),
            "primary_cases": item.get("primary_case_count", 0),
            "assigned_cases": item.get("assigned_case_count", 0),
            "open_cases": item.get("open_case_count", 0),
            "closed_cases": item.get("closed_case_count", 0),
            "blocked_cases": item.get("blocked_case_count", 0),
            "review_cases": item.get("review_case_count", 0),
        }
        for item in payload.get("department_lanes", [])
        if isinstance(item, dict)
    ]
    case_rows = [
        {
            "case_id": item.get("case", {}).get("case_id", ""),
            "goal": item.get("case", {}).get("goal", ""),
            "department": item.get("case", {}).get("department_id", ""),
            "status": item.get("case", {}).get("status", ""),
            "risk": item.get("case", {}).get("risk", ""),
            "terminal_status": item.get("terminal_status", ""),
            "blocked_steps": item.get("blocked_step_count", 0),
            "evidence": item.get("evidence_count", 0),
            "attention": item.get("attention_count", 0),
        }
        for item in payload.get("cases", [])
        if isinstance(item, dict) and isinstance(item.get("case"), dict)
    ]
    quoted_org_id = quote(raw_org_id, safe="")
    json_url = f"/api/v1/orgs/{quoted_org_id}/case-portfolio"
    registry_url = f"/api/v1/orgs/{quoted_org_id}/department-registry/view"
    authority_url = f"/api/v1/orgs/{quoted_org_id}/authority-map/view"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mullu OrgOS Case Portfolio</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; color: #1f2937; background: #f7f7f4; }}
    header {{ background: #2f3a35; color: #ffffff; padding: 24px 28px; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 22px; }}
    nav {{ display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }}
    nav a {{ color: #d4f4e8; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; letter-spacing: 0; }}
    .status {{ margin-top: 8px; color: #e4eee9; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; overflow-wrap: anywhere; }}
    th {{ background: #eef2ef; color: #29342f; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu OrgOS Case Portfolio</h1>
    <div class="status">Organization <strong>{org_id}</strong> | <strong>{org_name}</strong></div>
    <nav>
      <a href="{escape(json_url)}">json portfolio</a>
      <a href="{escape(registry_url)}">department registry</a>
      <a href="{escape(authority_url)}">authority map</a>
    </nav>
  </header>
  <main>
    {_proof_explorer_table("Summary", ("metric", "value"), summary_rows)}
    {_proof_explorer_table("Attention", ("severity", "kind", "ref", "message"), attention_rows)}
    {_proof_explorer_table("Departments", ("department_id", "name", "primary_cases", "assigned_cases", "open_cases", "closed_cases", "blocked_cases", "review_cases"), department_rows)}
    {_proof_explorer_table("Cases", ("case_id", "goal", "department", "status", "risk", "terminal_status", "blocked_steps", "evidence", "attention"), case_rows)}
  </main>
</body>
</html>
"""


def _validate_gateway_base_url(gateway_url: str) -> str:
    parsed = urlparse(gateway_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            400,
            detail=_error_detail("gateway URL must be absolute http(s)", "invalid_gateway_url"),
        )
    if parsed.username or parsed.password:
        raise HTTPException(
            400,
            detail=_error_detail("gateway URL must not contain credentials", "gateway_url_credentials_rejected"),
        )
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise HTTPException(
            400,
            detail=_error_detail("gateway URL must be an origin without path/query/fragment", "gateway_url_scope_rejected"),
        )
    # SSRF: the deployment-witness collector fetches this origin, so reject
    # private/loopback/link-local/metadata destinations. Unresolvable hosts are
    # permitted (the collector's own connect fails closed on them) so that a
    # legitimate-but-currently-unresolvable gateway is not hard-rejected.
    if is_private_host(parsed.hostname or "", block_unresolvable=False):
        raise HTTPException(
            400,
            detail=_error_detail(
                "gateway URL must resolve to a public address",
                "gateway_url_private_address_rejected",
            ),
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def _witness_step_passed(witness: DeploymentWitness, name: str) -> bool:
    return any(step.name == name and step.passed for step in witness.steps)


def _launch_gateway_evidence_bindings(
    witness: DeploymentWitness,
    *,
    expected_environment: str,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    environment_ok = not expected_environment or _witness_step_passed(witness, "runtime environment")
    bindings: list[tuple[str, dict[str, Any]]] = []

    if _witness_step_passed(witness, "gateway health"):
        bindings.append((
            "engineering_health_endpoint",
            {
                "public_health_endpoint": witness.public_health_endpoint,
                "health_http_status": witness.health_http_status,
                "health_response_digest": witness.health_response_digest,
                "health_status": witness.health_status,
            },
        ))
    if (
        environment_ok
        and _witness_step_passed(witness, "gateway runtime witness")
        and _witness_step_passed(witness, "runtime witness signature")
    ):
        bindings.append((
            "engineering_gateway_witness",
            {
                "runtime_witness_id": witness.runtime_witness_id,
                "runtime_witness_status": witness.runtime_witness_status,
                "runtime_signature_key_id": witness.runtime_signature_key_id,
                "signature_status": witness.signature_status,
                "runtime_environment": witness.runtime_environment,
                "latest_command_event_hash": witness.latest_command_event_hash,
                "latest_terminal_certificate_id": witness.latest_terminal_certificate_id,
            },
        ))
    if (
        environment_ok
        and _witness_step_passed(witness, "runtime conformance certificate")
        and _witness_step_passed(witness, "runtime conformance signature")
    ):
        bindings.append((
            "engineering_runtime_conformance",
            {
                "latest_conformance_certificate_id": witness.latest_conformance_certificate_id,
                "conformance_status": witness.conformance_status,
                "conformance_signature_status": witness.conformance_signature_status,
                "authority_responsibility_debt_clear": witness.authority_responsibility_debt_clear,
                "authority_open_obligation_count": witness.authority_open_obligation_count,
                "authority_overdue_obligation_count": witness.authority_overdue_obligation_count,
                "authority_escalated_obligation_count": witness.authority_escalated_obligation_count,
                "authority_unowned_high_risk_capability_count": (
                    witness.authority_unowned_high_risk_capability_count
                ),
            },
        ))
    return tuple(bindings)


def _admit_launch_gateway_witness_evidence(
    kernel: OrganizationKernel,
    *,
    case_id: str,
    witness: DeploymentWitness,
    submitted_by: str,
    expected_environment: str,
    request_metadata: dict[str, Any],
) -> tuple[CaseEvidence, ...]:
    admitted: list[CaseEvidence] = []
    for requirement_id, evidence_metadata in _launch_gateway_evidence_bindings(
        witness,
        expected_environment=expected_environment,
    ):
        evidence = kernel.admit_case_evidence(
            CaseEvidence(
                evidence_ref=f"evidence:{case_id}:{requirement_id}:{witness.witness_id}",
                case_id=case_id,
                requirement_id=requirement_id,
                submitted_by=submitted_by,
                submitted_at=_clock_now(),
                metadata={
                    "source": "deployment_witness_collection",
                    "witness_id": witness.witness_id,
                    "gateway_url": witness.gateway_url,
                    "deployment_claim": witness.deployment_claim,
                    "collected_at": witness.collected_at,
                    "request": request_metadata,
                    **evidence_metadata,
                },
            )
        )
        admitted.append(evidence)
    return tuple(admitted)


def _launch_gateway_readiness_packet_items(
    req: LaunchGatewayPilotReadinessClosureRequest,
) -> tuple[tuple[str, LaunchGatewayPilotEvidencePacketItem], ...]:
    return (
        ("executive_objective", req.executive_objective),
        ("product_launch_boundary", req.product_launch_boundary),
        ("security_public_claim_boundary", req.security_public_claim_boundary),
        ("security_approval", req.security_approval),
        ("finance_budget_check", req.finance_budget_check),
    )


def _launch_gateway_readiness_gate_checks() -> tuple[tuple[str, tuple[str, ...], str | None], ...]:
    return (
        ("executive_objective_freeze", ("objective_received",), None),
        ("product_launch_boundary", ("objective_frozen",), "executive_objective_freeze"),
        ("engineering_runtime_witness", ("launch_boundary_defined",), "product_launch_boundary"),
        ("security_claim_boundary", ("runtime_witness_collected",), "engineering_runtime_witness"),
        ("finance_budget_check", ("runtime_witness_collected",), "engineering_runtime_witness"),
    )


def _launch_gateway_required_evidence_ids() -> tuple[str, ...]:
    return (
        "executive_objective",
        "product_launch_boundary",
        "engineering_health_endpoint",
        "engineering_gateway_witness",
        "engineering_runtime_conformance",
        "security_public_claim_boundary",
        "security_approval",
        "finance_budget_check",
    )


def _admit_launch_gateway_readiness_packet(
    kernel: OrganizationKernel,
    *,
    case_id: str,
    req: LaunchGatewayPilotReadinessClosureRequest,
) -> tuple[CaseEvidence, ...]:
    refs = [item.evidence_ref for _requirement_id, item in _launch_gateway_readiness_packet_items(req)]
    if len(set(refs)) != len(refs):
        raise RuntimeCoreInvariantError("readiness packet evidence refs must be unique")
    state = kernel.snapshot_state()
    existing_evidence_refs = {
        evidence.evidence_ref for evidence in state.case_evidence
        if evidence.case_id == case_id
    }
    if any(ref in existing_evidence_refs for ref in refs):
        raise RuntimeCoreInvariantError("readiness packet evidence already admitted")
    if any(approval.approval_id == req.approval_id for approval in state.approvals):
        raise RuntimeCoreInvariantError("readiness packet approval already recorded")

    admitted: list[CaseEvidence] = []
    for requirement_id, item in _launch_gateway_readiness_packet_items(req):
        evidence = kernel.admit_case_evidence(
            CaseEvidence(
                evidence_ref=item.evidence_ref,
                case_id=case_id,
                requirement_id=requirement_id,
                submitted_by=req.submitted_by,
                submitted_at=_clock_now(),
                metadata={
                    "source": "launch_gateway_pilot_readiness_packet",
                    "request": req.metadata,
                    **item.metadata,
                },
            )
        )
        admitted.append(evidence)
    return tuple(admitted)


def _launch_gateway_closure_evidence_refs(
    req: LaunchGatewayPilotReadinessClosureRequest,
    gate_decisions: tuple[Any, ...],
) -> tuple[str, ...]:
    refs: list[str] = []
    for decision in gate_decisions:
        refs.extend(decision.evidence_refs)
        refs.extend(decision.approval_refs)
    refs.extend(req.closure_evidence_refs)
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return tuple(deduped)


def _validate_launch_gateway_closure_request(req: LaunchGatewayPilotReadinessClosureRequest) -> None:
    reconciliation_status = ReconciliationStatus(req.reconciliation_status)
    terminal_disposition = TerminalClosureDisposition(req.terminal_disposition)
    if terminal_disposition is not TerminalClosureDisposition.COMMITTED:
        return
    if reconciliation_status is not ReconciliationStatus.MATCH:
        raise RuntimeCoreInvariantError("committed readiness closure requires reconciliation match")
    if req.expected_effect != req.observed_effect:
        raise RuntimeCoreInvariantError("committed readiness closure requires matched observed effect")
    if not req.forbidden_effects_checked:
        raise RuntimeCoreInvariantError("committed readiness closure requires forbidden effect check")


def _launch_gateway_gate_preview(kernel: OrganizationKernel, case_id: str) -> tuple[Any, ...]:
    _require_launch_gateway_pilot_case(kernel, case_id)
    previews = []
    gate_status_by_step: dict[str, bool] = {}
    for step_id, checked_preconditions, predecessor_step_id in _launch_gateway_readiness_gate_checks():
        predecessor_allowed = (
            predecessor_step_id is None
            or gate_status_by_step.get(predecessor_step_id, False)
        )
        preview = kernel.preview_plan_step(
            case_id=case_id,
            step_id=step_id,
            checked_preconditions=checked_preconditions if predecessor_allowed else (),
        )
        previews.append(preview)
        gate_status_by_step[step_id] = preview.status is PlanStepGateStatus.ALLOWED
    return tuple(previews)


def _launch_gateway_readiness_model(kernel: OrganizationKernel, case_id: str) -> dict[str, Any]:
    organization_case = _require_launch_gateway_pilot_case(kernel, case_id)
    state = kernel.snapshot_state()
    plan = next((item for item in state.plans if item.case_id == case_id), None)
    closure = next((item for item in state.closures if item.case_id == case_id), None)
    gate_preview = _launch_gateway_gate_preview(kernel, case_id)
    evidence_by_requirement = {
        requirement_id: [
            evidence for evidence in state.case_evidence
            if evidence.case_id == case_id and evidence.requirement_id == requirement_id
        ]
        for requirement_id in _launch_gateway_required_evidence_ids()
    }
    requirements_by_id = {
        requirement.requirement_id: requirement
        for requirement in state.evidence_requirements
        if requirement.case_type == LAUNCH_GATEWAY_PILOT_CASE_TYPE
    }
    gate_by_id = {decision.decision_id: decision for decision in state.gate_decisions}
    latest_gate_by_step = {
        ref.step_id: gate_by_id[ref.decision_id]
        for ref in state.latest_gate_decisions
        if ref.case_id == case_id and ref.decision_id in gate_by_id
    }
    approvals = [
        approval for approval in state.approvals
        if approval.case_id == case_id and approval.approval_scope == "security_approval"
    ]
    evidence_rows = []
    for requirement_id in _launch_gateway_required_evidence_ids():
        requirement = requirements_by_id.get(requirement_id)
        refs = [evidence.evidence_ref for evidence in evidence_by_requirement[requirement_id]]
        evidence_rows.append({
            "requirement_id": requirement_id,
            "department_id": requirement.department_id if requirement is not None else None,
            "present": bool(refs),
            "evidence_refs": refs,
        })
    plan_steps = plan.steps if plan is not None else ()
    plan_step_rows = []
    for step in plan_steps:
        decision = latest_gate_by_step.get(step.step_id)
        plan_step_rows.append({
            "step_id": step.step_id,
            "department_id": step.department_id,
            "required_evidence": list(step.evidence_required),
            "latest_gate_decision": _body(decision) if decision is not None else None,
            "gate_status": decision.status.value if decision is not None else "not_evaluated",
        })
    missing_evidence = [
        row["requirement_id"] for row in evidence_rows
        if not row["present"]
    ]
    blocked_steps = [
        row["step_id"] for row in plan_step_rows
        if row["gate_status"] != PlanStepGateStatus.ALLOWED.value
    ]
    preview_blocked_steps = [
        preview.step_id for preview in gate_preview
        if preview.status is not PlanStepGateStatus.ALLOWED
    ]
    ready_to_close = (
        closure is None
        and not missing_evidence
        and bool(approvals)
        and not blocked_steps
    )
    preview_ready_to_close = (
        closure is None
        and not missing_evidence
        and bool(approvals)
        and not preview_blocked_steps
    )
    if closure is not None:
        terminal_status = "closed"
    elif missing_evidence:
        terminal_status = "awaiting_evidence"
    elif not approvals:
        terminal_status = "awaiting_approval"
    elif blocked_steps:
        terminal_status = "awaiting_gate"
    else:
        terminal_status = "ready_to_close"
    if closure is not None:
        preview_terminal_status = "closed"
    elif missing_evidence:
        preview_terminal_status = "awaiting_evidence"
    elif not approvals:
        preview_terminal_status = "awaiting_approval"
    elif preview_blocked_steps:
        preview_terminal_status = "awaiting_gate"
    else:
        preview_terminal_status = "ready_to_close"
    return {
        "case_id": organization_case.case_id,
        "case_status": organization_case.status.value,
        "plan_id": plan.plan_id if plan is not None else None,
        "required_evidence": evidence_rows,
        "missing_evidence": missing_evidence,
        "approval_scope": "security_approval",
        "approval_refs": [approval.approval_id for approval in approvals],
        "plan_steps": plan_step_rows,
        "blocked_steps": blocked_steps,
        "gate_preview": [_body(preview) for preview in gate_preview],
        "preview_blocked_steps": preview_blocked_steps,
        "ready_to_close": ready_to_close,
        "preview_ready_to_close": preview_ready_to_close,
        "terminal_status": terminal_status,
        "preview_terminal_status": preview_terminal_status,
        "closure": _body(closure) if closure is not None else None,
        "governed": True,
    }


@router.post("/api/v1/orgs")
def create_organization(req: OrganizationCreateRequest, _: str = Depends(require_admin)):
    """Create an organization profile in the Organization Kernel."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    try:
        organization = kernel.register_organization(
            OrganizationProfile(
                org_id=req.org_id,
                tenant_id=req.tenant_id,
                name=req.name,
                created_at=_clock_now(),
                metadata=req.metadata,
            )
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("organization create rejected", "organization_create_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {"organization": _body(organization), "governed": True}


@router.post("/api/v1/orgs/{org_id}/bootstrap-minimum")
def bootstrap_minimum_org(org_id: str, req: OrganizationBootstrapRequest, _: str = Depends(require_admin)):
    """Create the five-department minimum Organization Kernel v0 surface."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    try:
        organization = bootstrap_minimum_organization(
            kernel,
            OrganizationProfile(
                org_id=org_id,
                tenant_id=req.tenant_id,
                name=req.name,
                created_at=_clock_now(),
                metadata=req.metadata,
            ),
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("organization bootstrap rejected", "organization_bootstrap_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {
        "organization": _body(organization),
        "department_count": kernel.department_count,
        "governed": True,
    }


@router.post("/api/v1/departments")
def create_department(req: DepartmentCreateRequest, request: Request):
    """Register a governed department pack."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_known_organization_tenant(request, kernel, req.org_id)
    try:
        department = kernel.register_department(
            DepartmentPack(
                department_id=req.department_id,
                org_id=req.org_id,
                name=req.name,
                mission=req.mission,
                owns=tuple(req.owns),
                allowed_case_types=tuple(req.allowed_case_types),
                allowed_capabilities=tuple(req.allowed_capabilities),
                required_evidence=tuple(req.required_evidence),
                escalation_departments=tuple(req.escalation_departments),
                metrics=tuple(req.metrics),
                failure_modes=tuple(req.failure_modes),
                metadata=req.metadata,
            )
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("department create rejected", "department_create_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {"department": _body(department), "governed": True}


@router.get("/api/v1/orgs/{org_id}/departments")
def list_organization_departments(org_id: str, request: Request):
    """List departments for one organization."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    departments = [
        department for department in kernel.list_departments()
        if department.org_id == org_id
    ]
    return {
        "departments": [_body(department) for department in departments],
        "count": len(departments),
        "governed": True,
    }


@router.get("/api/v1/orgs/{org_id}/department-registry")
def get_organization_department_registry(org_id: str, request: Request):
    """Return a read-only department mandate, authority, evidence, and capability registry."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    return _organization_department_registry(kernel, org_id)


@router.get("/api/v1/orgs/{org_id}/department-registry/view")
def get_organization_department_registry_view(org_id: str, request: Request):
    """Return a browser-facing read-only department registry view."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    return HTMLResponse(_render_department_registry_html(_organization_department_registry(kernel, org_id)))


@router.get("/api/v1/orgs/{org_id}/authority-map")
def get_organization_authority_map(org_id: str, request: Request):
    """Return a read-only department, role, authority, capability, and evidence map."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    return _organization_authority_map(kernel, org_id)


@router.get("/api/v1/orgs/{org_id}/authority-map/view")
def get_organization_authority_map_view(org_id: str, request: Request):
    """Return a browser-facing read-only organization authority map."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    return HTMLResponse(_render_authority_map_html(_organization_authority_map(kernel, org_id)))


@router.get("/api/v1/orgs/{org_id}/case-portfolio")
def get_organization_case_portfolio(org_id: str, request: Request):
    """Return a read-only organization case portfolio and department lane projection."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    return _organization_case_portfolio(kernel, org_id)


@router.get("/api/v1/orgs/{org_id}/case-portfolio/view")
def get_organization_case_portfolio_view(org_id: str, request: Request):
    """Return a browser-facing read-only organization case portfolio view."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    return HTMLResponse(_render_case_portfolio_html(_organization_case_portfolio(kernel, org_id)))


@router.post("/api/v1/cases/launch-gateway-pilot")
def create_launch_gateway_pilot(req: LaunchGatewayPilotRequest):
    """Open and plan the default Launch Gateway Pilot case."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    try:
        organization_case, plan = open_launch_gateway_pilot(
            kernel,
            org_id=req.org_id,
            case_id=req.case_id,
            owner_role_id=req.owner_role_id,
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("launch gateway pilot rejected", "launch_gateway_pilot_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {"case": _body(organization_case), "plan": _body(plan), "governed": True}


@router.post("/api/v1/cases/{case_id}/launch-gateway-pilot/deployment-witness")
def collect_launch_gateway_pilot_deployment_witness(
    case_id: str,
    req: LaunchGatewayPilotEvidenceCollectionRequest,
    request: Request,
):
    """Collect deployment witness evidence and bind verified engineering proof."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    _require_launch_gateway_pilot_case(kernel, case_id)
    gateway_url = _validate_gateway_base_url(req.gateway_url)
    try:
        witness = collect_deployment_witness(
            gateway_url=gateway_url,
            witness_secret=os.environ.get("MULLU_RUNTIME_WITNESS_SECRET", ""),
            conformance_secret=os.environ.get("MULLU_RUNTIME_CONFORMANCE_SECRET", ""),
            deployment_witness_secret=os.environ.get("MULLU_DEPLOYMENT_WITNESS_SECRET", ""),
            expected_environment=req.expected_environment,
            require_production_evidence=req.require_production_evidence,
            clock=_clock_now,
        )
        admitted = _admit_launch_gateway_witness_evidence(
            kernel,
            case_id=case_id,
            witness=witness,
            submitted_by=req.submitted_by,
            expected_environment=req.expected_environment,
            request_metadata=req.metadata,
        )
        decision = None
        if req.auto_gate_engineering_step:
            decision = kernel.evaluate_plan_step(
                case_id=case_id,
                step_id="engineering_runtime_witness",
                checked_preconditions=tuple(req.checked_preconditions),
            )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("deployment witness binding rejected", "deployment_witness_binding_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {
        "deployment_witness": witness.to_json_dict(),
        "admitted_evidence": [_body(evidence) for evidence in admitted],
        "gate_decision": _body(decision) if decision is not None else None,
        "governed": True,
    }


@router.get("/api/v1/cases/{case_id}/launch-gateway-pilot/gate-preview")
def get_launch_gateway_pilot_gate_preview(case_id: str, request: Request):
    """Return non-mutating plan-step gate previews for the Launch Gateway Pilot case."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    previews = _launch_gateway_gate_preview(kernel, case_id)
    blocked_steps = [
        preview.step_id for preview in previews
        if preview.status is not PlanStepGateStatus.ALLOWED
    ]
    return {
        "case_id": case_id,
        "gate_preview": [_body(preview) for preview in previews],
        "blocked_steps": blocked_steps,
        "ready": not blocked_steps,
        "governed": True,
    }


@router.get("/api/v1/cases/{case_id}/launch-gateway-pilot/readiness")
def get_launch_gateway_pilot_readiness(case_id: str, request: Request):
    """Return non-mutating readiness state for the Launch Gateway Pilot case."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return _launch_gateway_readiness_model(kernel, case_id)


@router.post("/api/v1/cases/{case_id}/launch-gateway-pilot/readiness-closure")
def close_launch_gateway_pilot_readiness(
    case_id: str,
    req: LaunchGatewayPilotReadinessClosureRequest,
    request: Request,
):
    """Bind a five-department readiness packet and close only after all gates pass."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    _require_launch_gateway_pilot_case(kernel, case_id)
    try:
        _validate_launch_gateway_closure_request(req)
        admitted = _admit_launch_gateway_readiness_packet(kernel, case_id=case_id, req=req)
        approval = kernel.record_approval(
            ApprovalRecord(
                approval_id=req.approval_id,
                case_id=case_id,
                role_id="executive.owner",
                approval_scope="security_approval",
                approved_by=req.approved_by,
                approved_at=_clock_now(),
                metadata={
                    "source": "launch_gateway_pilot_readiness_packet",
                    "request": req.metadata,
                    "security_approval_evidence_ref": req.security_approval.evidence_ref,
                },
            )
        )
        gate_decision_list = []
        gate_status_by_step: dict[str, bool] = {}
        for step_id, checked_preconditions, predecessor_step_id in _launch_gateway_readiness_gate_checks():
            predecessor_allowed = (
                predecessor_step_id is None
                or gate_status_by_step.get(predecessor_step_id, False)
            )
            decision = kernel.evaluate_plan_step(
                case_id=case_id,
                step_id=step_id,
                checked_preconditions=checked_preconditions if predecessor_allowed else (),
            )
            gate_decision_list.append(decision)
            gate_status_by_step[step_id] = decision.status is PlanStepGateStatus.ALLOWED
        gate_decisions = tuple(gate_decision_list)
        blocked_decisions = tuple(
            decision for decision in gate_decisions
            if decision.status is not PlanStepGateStatus.ALLOWED
        )
        closure = None
        closure_status = "blocked_by_gate"
        if not blocked_decisions:
            closure = kernel.close_case(
                reconciliation=OrganizationEffectReconciliation(
                    reconciliation_id=req.reconciliation_id,
                    case_id=case_id,
                    expected_effect=req.expected_effect,
                    observed_effect=req.observed_effect,
                    status=ReconciliationStatus(req.reconciliation_status),
                    forbidden_effects_checked=req.forbidden_effects_checked,
                    evidence_refs=_launch_gateway_closure_evidence_refs(req, gate_decisions),
                    reconciled_at=_clock_now(),
                    metadata={
                        "source": "launch_gateway_pilot_readiness_packet",
                        "request": req.metadata,
                    },
                ),
                terminal_disposition=TerminalClosureDisposition(req.terminal_disposition),
                terminal_certificate_id=req.terminal_certificate_id,
                learning_admission_id=req.learning_admission_id,
            )
            closure_status = (
                "closed"
                if TerminalClosureDisposition(req.terminal_disposition) is TerminalClosureDisposition.COMMITTED
                else req.terminal_disposition
            )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail(
                "launch gateway pilot readiness closure rejected",
                "launch_gateway_pilot_readiness_closure_rejected",
            ),
        ) from exc
    _persist_kernel(kernel)
    return {
        "admitted_evidence": [_body(evidence) for evidence in admitted],
        "approval": _body(approval),
        "gate_decisions": [_body(decision) for decision in gate_decisions],
        "blocked_gate_decisions": [_body(decision) for decision in blocked_decisions],
        "closure_status": closure_status,
        "closure": _body(closure) if closure is not None else None,
        "governed": True,
    }


@router.post("/api/v1/cases")
def create_case(req: OrganizationCaseCreateRequest):
    """Open a governed organization case."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    try:
        organization_case = kernel.open_case(
            OrganizationCase(
                case_id=req.case_id,
                org_id=req.org_id,
                department_id=req.department_id,
                case_type=req.case_type,
                goal=req.goal,
                risk=OrganizationRisk(req.risk),
                owner_role_id=req.owner_role_id,
                status=OrganizationCaseStatus.OPEN,
                assigned_department_ids=tuple(req.assigned_department_ids),
                created_at=_clock_now(),
                metadata=req.metadata,
            )
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(400, detail=_error_detail("case create rejected", "case_create_rejected")) from exc
    _persist_kernel(kernel)
    return {"case": _body(organization_case), "governed": True}


@router.get("/api/v1/cases/{case_id}")
def get_case(case_id: str, request: Request):
    """Return a case read model with plan, proof, and event surfaces."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return _state_case_bundle(kernel, case_id)


@router.get("/api/v1/cases/{case_id}/proof-timeline")
def get_case_proof_timeline(case_id: str, request: Request):
    """Return a non-mutating proof timeline and closure certificate read model."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return _case_proof_timeline(kernel, case_id)


@router.get("/api/v1/cases/{case_id}/proof-explorer")
def get_case_proof_explorer(case_id: str, request: Request):
    """Return an operator proof explorer projection without mutating case state."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return _case_proof_explorer(kernel, case_id)


@router.get("/api/v1/cases/{case_id}/proof-explorer/view")
def get_case_proof_explorer_view(case_id: str, request: Request):
    """Return a browser-facing read-only proof explorer view."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return HTMLResponse(_render_case_proof_explorer_html(_case_proof_explorer(kernel, case_id)))


@router.get("/api/v1/cases/{case_id}/audit-explorer")
def get_case_audit_explorer(case_id: str, request: Request):
    """Return a read-only causal audit explorer projection for a case."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return _case_audit_explorer(kernel, case_id)


@router.get("/api/v1/cases/{case_id}/audit-explorer/view")
def get_case_audit_explorer_view(case_id: str, request: Request):
    """Return a browser-facing read-only case audit explorer view."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return HTMLResponse(_render_case_audit_explorer_html(_case_audit_explorer(kernel, case_id)))


@router.get("/api/v1/cases/{case_id}/step-handoffs")
def get_case_step_handoffs(case_id: str, request: Request):
    """Return read-only plan-step handoff status and worker receipt bindings."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return _case_step_handoffs(kernel, case_id)


@router.get("/api/v1/cases/{case_id}/step-handoffs/view")
def get_case_step_handoffs_view(case_id: str, request: Request):
    """Return a browser-facing read-only step handoff view."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return HTMLResponse(_render_case_step_handoffs_html(_case_step_handoffs(kernel, case_id)))


@router.get("/api/v1/cases/{case_id}/closure-certificate")
def get_case_closure_certificate(case_id: str, request: Request):
    """Return a read-only terminal closure certificate projection."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return _case_closure_certificate(kernel, case_id)


@router.get("/api/v1/cases/{case_id}/closure-certificate/view")
def get_case_closure_certificate_view(case_id: str, request: Request):
    """Return a browser-facing read-only terminal closure certificate view."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    return HTMLResponse(_render_case_closure_certificate_html(_case_closure_certificate(kernel, case_id)))


@router.post("/api/v1/cases/{case_id}/plan")
def create_case_plan(case_id: str, req: OrganizationPlanCreateRequest, request: Request):
    """Create a governed plan DAG for a case."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    try:
        plan = OrganizationPlan(
            plan_id=req.plan_id,
            case_id=case_id,
            steps=tuple(
                PlanStep(
                    step_id=step.step_id,
                    case_id=case_id,
                    department_id=step.department_id,
                    responsible_role_id=step.responsible_role_id,
                    capability_id=step.capability_id,
                    action=step.action,
                    expected_effect=step.expected_effect,
                    preconditions=tuple(step.preconditions),
                    postconditions=tuple(step.postconditions),
                    evidence_required=tuple(step.evidence_required),
                    approvals_required=tuple(step.approvals_required),
                    predecessor_step_ids=tuple(step.predecessor_step_ids),
                    rollback_plan_id=step.rollback_plan_id,
                    metadata=step.metadata,
                )
                for step in req.steps
            ),
            created_at=_clock_now(),
            version=req.version,
            metadata=req.metadata,
        )
        registered = kernel.create_plan(plan)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(400, detail=_error_detail("plan create rejected", "plan_create_rejected")) from exc
    _persist_kernel(kernel)
    return {"plan": _body(registered), "governed": True}


@router.post("/api/v1/cases/{case_id}/evidence")
def admit_case_evidence(case_id: str, req: EvidenceAdmitRequest, request: Request):
    """Admit evidence against a case requirement."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    try:
        evidence = kernel.admit_case_evidence(
            CaseEvidence(
                evidence_ref=req.evidence_ref,
                case_id=case_id,
                requirement_id=req.requirement_id,
                submitted_by=req.submitted_by,
                submitted_at=_clock_now(),
                metadata=req.metadata,
            )
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("evidence admission rejected", "evidence_admission_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {"evidence": _body(evidence), "governed": True}


@router.post("/api/v1/cases/{case_id}/approvals")
def record_case_approval(case_id: str, req: ApprovalRecordRequest, request: Request):
    """Record an explicit case approval receipt."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    try:
        approval = kernel.record_approval(
            ApprovalRecord(
                approval_id=req.approval_id,
                case_id=case_id,
                role_id=req.role_id,
                approval_scope=req.approval_scope,
                approved_by=req.approved_by,
                approved_at=_clock_now(),
                metadata=req.metadata,
            )
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(400, detail=_error_detail("approval rejected", "approval_rejected")) from exc
    _persist_kernel(kernel)
    return {"approval": _body(approval), "governed": True}


@router.post("/api/v1/cases/{case_id}/plan-steps/{step_id}/gate")
def evaluate_case_plan_step(case_id: str, step_id: str, req: PlanStepGateRequest, request: Request):
    """Evaluate one plan step gate with checked preconditions."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    try:
        decision = kernel.evaluate_plan_step(
            case_id=case_id,
            step_id=step_id,
            checked_preconditions=tuple(req.checked_preconditions),
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(400, detail=_error_detail("plan step gate rejected", "plan_step_gate_rejected")) from exc
    _persist_kernel(kernel)
    return {"decision": _body(decision), "governed": True}


@router.post("/api/v1/cases/{case_id}/plan-steps/{step_id}/worker-receipt")
def bind_plan_step_worker_receipt(case_id: str, step_id: str, req: WorkerReceiptBindRequest, request: Request):
    """Admit a bounded worker dispatch receipt as evidence for a plan step.

    The receipt is produced by the governed worker mesh under its own lease and
    budget controls; this endpoint only admits it as case evidence and never
    grants dispatch authority or terminal closure.
    """
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    try:
        binding = kernel.bind_worker_receipt_evidence(
            PlanStepWorkerReceiptBinding(
                binding_id=req.binding_id,
                case_id=case_id,
                step_id=step_id,
                requirement_id=req.requirement_id,
                worker_lease_id=req.worker_lease_id,
                dispatch_request_id=req.dispatch_request_id,
                dispatch_receipt_id=req.dispatch_receipt_id,
                worker_output_hash=req.worker_output_hash,
                receipt_evidence_refs=tuple(req.receipt_evidence_refs),
                admitted_evidence_ref=req.admitted_evidence_ref,
                bound_at=_clock_now(),
                metadata=req.metadata,
            )
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("worker receipt binding rejected", "worker_receipt_binding_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {"worker_receipt_binding": _body(binding), "governed": True}


@router.post("/api/v1/cases/{case_id}/close")
def close_case(case_id: str, req: OrganizationCaseCloseRequest, request: Request):
    """Close a case through explicit effect reconciliation and disposition."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    try:
        closure = kernel.close_case(
            reconciliation=OrganizationEffectReconciliation(
                reconciliation_id=req.reconciliation_id,
                case_id=case_id,
                expected_effect=req.expected_effect,
                observed_effect=req.observed_effect,
                status=ReconciliationStatus(req.reconciliation_status),
                forbidden_effects_checked=req.forbidden_effects_checked,
                evidence_refs=tuple(req.evidence_refs),
                reconciled_at=_clock_now(),
                metadata=req.metadata,
            ),
            terminal_disposition=TerminalClosureDisposition(req.terminal_disposition),
            terminal_certificate_id=req.terminal_certificate_id,
            learning_admission_id=req.learning_admission_id,
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(400, detail=_error_detail("case closure rejected", "case_closure_rejected")) from exc
    _persist_kernel(kernel)
    return {"closure": _body(closure), "governed": True}


@router.post("/api/v1/cases/{case_id}/learning-admissions")
def bind_case_learning_admission(case_id: str, req: LearningAdmissionRequest, request: Request):
    """Bind a closure-derived learning admission decision to the case."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    try:
        binding = kernel.bind_learning_admission(
            LearningAdmissionBinding(
                binding_id=req.binding_id,
                case_id=case_id,
                closure_id=req.closure_id,
                decision_id=req.decision_id,
                admitted=req.admitted,
                created_at=_clock_now(),
                metadata=req.metadata,
            )
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("learning admission rejected", "learning_admission_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {"learning_admission": _body(binding), "governed": True}


@router.get("/api/v1/cases/{case_id}/events")
def list_case_events(case_id: str, request: Request):
    """List kernel-emitted case events."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    events = kernel.list_case_events(case_id)
    return {
        "events": [_body(event) for event in events],
        "count": len(events),
        "governed": True,
    }
