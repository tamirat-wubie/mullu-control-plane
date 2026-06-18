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
from urllib.parse import quote, urlencode, urlparse

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
    ClosureDriftRemediationBinding,
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
    PlanStepWorkerDispatchReceipt,
    PlanStepWorkerLeaseReceipt,
    PlanStepWorkerReceiptBinding,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.organization_kernel import (
    LAUNCH_GATEWAY_PILOT_CASE_TYPE,
    OrganizationKernel,
    TERMINAL_CLOSURE_CERTIFICATE_REQUIREMENT,
    bootstrap_minimum_organization,
    open_launch_gateway_pilot,
)
from mcoi_runtime.core.private_pilot_story import (
    PrivatePilotStoryRequest,
    build_private_pilot_live_rehearsal_uao_record,
    build_private_pilot_story,
    load_private_pilot_uao_records,
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


class WorkerLeaseCreateRequest(BaseModel):
    action_id: str
    filters: dict[str, str] = Field(default_factory=dict)
    lease_id: str
    requested_by_role_id: str
    timeout_seconds: int
    budget_ref: str
    evidence_refs: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerDispatchReceiptCreateRequest(BaseModel):
    action_id: str
    filters: dict[str, str] = Field(default_factory=dict)
    worker_lease_id: str
    dispatch_request_id: str
    dispatch_receipt_id: str
    requested_by_role_id: str
    worker_id: str
    dispatch_intent: str = "request_worker_execution"
    evidence_refs: list[str]
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


class PlanStepActionAdmissionPreviewRequest(BaseModel):
    checked_preconditions: list[str]
    proposed_action: str = "bind_worker_receipt"
    requested_by_role_id: str | None = None
    allow_simulation_when_blocked: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionQueueSelectionPreviewRequest(BaseModel):
    action_id: str
    filters: dict[str, str] = Field(default_factory=dict)
    allow_simulation_when_blocked: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClosureDriftRemediationRequest(BaseModel):
    remediation_id: str
    closure_id: str
    terminal_disposition: str
    drift_evidence_refs: list[str]
    superseded_evidence_refs: list[str] = Field(default_factory=list)
    authority_ref: str
    evidence_refs: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClosureDriftRemediationActionRequest(BaseModel):
    action_id: str
    closure_id: str
    terminal_disposition: str
    authority_ref: str
    evidence_refs: list[str]
    remediation_id: str | None = None
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
    organization = kernel.get_organization(org_id)
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
    plan = kernel.plan_for_case(case_id)
    closure = kernel.closure_for_case(case_id)
    return {
        "case": _body(organization_case),
        "plan": _body(plan) if plan is not None else None,
        "evidence": [_body(item) for item in state.case_evidence if item.case_id == case_id],
        "approvals": [_body(item) for item in state.approvals if item.case_id == case_id],
        "gate_decisions": [_body(item) for item in state.gate_decisions if item.case_id == case_id],
        "reconciliations": [_body(item) for item in state.reconciliations if item.case_id == case_id],
        "closure": _body(closure) if closure is not None else None,
        "learning_bindings": [_body(item) for item in state.learning_bindings if item.case_id == case_id],
        "closure_drift_remediations": [
            _body(item) for item in state.closure_drift_remediations if item.case_id == case_id
        ],
        "worker_leases": [_body(item) for item in state.worker_lease_receipts if item.case_id == case_id],
        "worker_dispatch_receipts": [
            _body(item) for item in state.worker_dispatch_receipts if item.case_id == case_id
        ],
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
    plan = kernel.plan_for_case(case_id)
    closure = kernel.closure_for_case(case_id)
    evidence = tuple(item for item in state.case_evidence if item.case_id == case_id)
    approvals = tuple(item for item in state.approvals if item.case_id == case_id)
    gate_decisions = tuple(item for item in state.gate_decisions if item.case_id == case_id)
    worker_leases = tuple(item for item in state.worker_lease_receipts if item.case_id == case_id)
    worker_dispatch_receipts = tuple(item for item in state.worker_dispatch_receipts if item.case_id == case_id)
    worker_receipts = tuple(item for item in state.worker_receipt_bindings if item.case_id == case_id)
    reconciliations = tuple(item for item in state.reconciliations if item.case_id == case_id)
    learning_bindings = tuple(item for item in state.learning_bindings if item.case_id == case_id)
    closure_drift_remediations = tuple(
        item for item in state.closure_drift_remediations if item.case_id == case_id
    )
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
    worker_leases_by_step: dict[str, list[dict[str, Any]]] = {}
    for lease_receipt in worker_leases:
        worker_leases_by_step.setdefault(lease_receipt.step_id, []).append(_body(lease_receipt))
    worker_dispatch_receipts_by_step: dict[str, list[dict[str, Any]]] = {}
    for dispatch_receipt in worker_dispatch_receipts:
        worker_dispatch_receipts_by_step.setdefault(dispatch_receipt.step_id, []).append(_body(dispatch_receipt))

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
                "worker_lease_receipts": worker_leases_by_step.get(step.step_id, []),
                "worker_dispatch_receipts": worker_dispatch_receipts_by_step.get(step.step_id, []),
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
            kind="worker_lease_receipt",
            occurred_at=item.created_at,
            ref=item.lease_id,
            status="created",
            payload={
                "step_id": item.step_id,
                "capability_id": item.capability_id,
                "dispatch_lease_preview_id": item.dispatch_lease_preview_id,
                "worker_dispatch_started": False,
            },
        )
        for item in worker_leases
    )
    proof_timeline.extend(
        _timeline_item(
            kind="worker_dispatch_receipt",
            occurred_at=item.dispatched_at,
            ref=item.dispatch_receipt_id,
            status="dispatch_envelope_created",
            payload={
                "step_id": item.step_id,
                "capability_id": item.capability_id,
                "worker_lease_id": item.worker_lease_id,
                "dispatch_request_id": item.dispatch_request_id,
                "worker_execution_started": False,
            },
        )
        for item in worker_dispatch_receipts
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
            payload={
                "closure_id": item.closure_id,
                "decision_id": item.decision_id,
                "evidence_refs": list(item.evidence_refs),
            },
        )
        for item in learning_bindings
    )
    proof_timeline.extend(
        _timeline_item(
            kind="closure_drift_remediation",
            occurred_at=item.created_at,
            ref=item.remediation_id,
            status=item.terminal_disposition.value,
            payload={
                "closure_id": item.closure_id,
                "drift_evidence_refs": list(item.drift_evidence_refs),
                "superseded_evidence_refs": list(item.superseded_evidence_refs),
                "evidence_refs": list(item.evidence_refs),
            },
        )
        for item in closure_drift_remediations
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
            "worker_lease_count": len(worker_leases),
            "worker_dispatch_receipt_count": len(worker_dispatch_receipts),
            "worker_receipt_count": len(worker_receipts),
            "reconciliation_count": len(reconciliations),
            "has_terminal_closure": closure is not None,
            "learning_binding_count": len(learning_bindings),
            "closure_drift_remediation_count": len(closure_drift_remediations),
            "blocked_steps": blocked_steps,
            "all_plan_steps_allowed": plan is not None and not blocked_steps,
            "terminal_status": organization_case.status.value,
        },
        "plan_step_proof": plan_step_proof,
        "proof_timeline": proof_timeline,
        "closure_certificate": closure_certificate,
        "closure_drift_remediations": [_body(item) for item in closure_drift_remediations],
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
    closure_gate_evidence = _closure_gate_evidence_projection(proof)
    closure_drift_action_projection = _case_closure_drift_remediation_action_projection(
        kernel=kernel,
        case_id=case_id,
        proof=proof,
        closure_gate_evidence=closure_gate_evidence,
    )
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

    stale_attention = _closure_gate_stale_attention_item(case_id, closure_gate_evidence)
    if stale_attention is not None:
        attention_items.append(stale_attention)

    if not summary["has_terminal_closure"]:
        attention_items.append({
            "kind": "missing_terminal_closure",
            "severity": "review",
            "ref": case_id,
            "message": "case has no terminal closure certificate",
        })
        if closure_gate_evidence["required_gate_evidence_refs"]:
            attention_items.append({
                "kind": "closure_gate_evidence_required",
                "severity": "review",
                "ref": case_id,
                "message": "terminal closure must include the latest allowed gate evidence refs",
                "evidence_refs": closure_gate_evidence["required_gate_evidence_refs"],
            })
    elif closure_certificate is not None:
        drift_attention = _closure_packet_drift_attention_item(closure_certificate["closure_id"], closure_gate_evidence)
        if drift_attention is not None:
            attention_items.append(drift_attention)
        if closure_gate_evidence["unavailable_gate_evidence_refs"]:
            attention_items.append({
                "kind": "closure_gate_evidence_unavailable",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "latest gate evidence refs are not admitted for this case",
                "evidence_refs": closure_gate_evidence["unavailable_gate_evidence_refs"],
            })
        if (
            closure_gate_evidence["omitted_gate_evidence_refs"]
            and not closure_gate_evidence["closure_packet_drift_remediated"]
        ):
            attention_items.append({
                "kind": "closure_gate_evidence_omitted",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "terminal closure evidence packet omits refs used by allowed plan-step gates",
                "evidence_refs": closure_gate_evidence["omitted_gate_evidence_refs"],
            })
        if not closure_certificate["effect_reconciled"]:
            attention_items.append({
                "kind": "effect_not_reconciled",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "terminal closure does not have a reconciled external effect",
            })
        if not closure_certificate["learning_admitted"]:
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
        if closure_gate_evidence["closure_packet_drift"]:
            terminal_status = _closure_packet_drift_terminal_status(closure_gate_evidence)
        elif closure_certificate["effect_reconciled"] and closure_certificate["learning_admitted"]:
            terminal_status = "closed_verified"
        elif closure_certificate["effect_reconciled"]:
            terminal_status = "closed_awaiting_learning"
        else:
            terminal_status = "closed_requires_review"
    elif summary["blocked_steps"]:
        terminal_status = "blocked_by_plan_gate"
    elif closure_gate_evidence["stale_gate_decisions"]:
        terminal_status = "awaiting_gate_refresh"
    elif summary["has_plan"]:
        terminal_status = "awaiting_evidence"

    status_cards = [
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
    ]
    if closure_drift_action_projection["action_count"]:
        status_cards.append(
            _proof_status_card(
                "closure_drift_actions",
                closure_drift_action_projection["action_count"],
                "ready" if closure_drift_action_projection["ready_action_count"] else "blocked",
            )
        )

    return {
        "explorer_id": f"proof-explorer:{case_id}",
        "case_id": case_id,
        "title": organization_case["goal"],
        "terminal_status": terminal_status,
        "read_only": True,
        "status_cards": status_cards,
        "attention_items": attention_items,
        "closure_gate_evidence": closure_gate_evidence,
        "closure_drift_remediation_actions": closure_drift_action_projection,
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
    plan = kernel.plan_for_case(case_id)
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
            "worker_lease_count": len(step_proof["worker_lease_receipts"]),
            "worker_lease_receipts": step_proof["worker_lease_receipts"],
            "worker_dispatch_receipt_count": len(step_proof["worker_dispatch_receipts"]),
            "worker_dispatch_receipts": step_proof["worker_dispatch_receipts"],
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


def _gate_preview_to_admission_decision(
    *,
    gate_status: str,
    gate_reason: str,
    allow_simulation_when_blocked: bool,
) -> tuple[str, str]:
    if gate_status == PlanStepGateStatus.ALLOWED.value:
        return "allow", "plan_step_gate_allowed"
    if gate_reason in {"approval_missing", "dual_control_missing"}:
        return "escalate", gate_reason
    if gate_reason in {"preconditions_missing", "evidence_missing"}:
        if allow_simulation_when_blocked:
            return "simulate", f"{gate_reason}_simulation_available"
        return "defer", gate_reason
    return "block", gate_reason


def _case_step_action_admission_preview(
    kernel: OrganizationKernel,
    case_id: str,
    step_id: str,
    req: PlanStepActionAdmissionPreviewRequest,
) -> dict[str, Any]:
    organization_case = _case_or_404(kernel, case_id)
    state = kernel.snapshot_state()
    organization = next(
        (item for item in state.organizations if item.org_id == organization_case.org_id),
        None,
    )
    plan = kernel.plan_for_case(case_id)
    if plan is None:
        raise RuntimeCoreInvariantError("case plan unavailable")
    step = next((item for item in plan.steps if item.step_id == step_id), None)
    if step is None:
        raise RuntimeCoreInvariantError("plan step unavailable")

    preview = kernel.preview_plan_step(
        case_id=case_id,
        step_id=step_id,
        checked_preconditions=tuple(req.checked_preconditions),
    )
    preview_body = _body(preview)
    handoff_projection = _case_step_handoffs(kernel, case_id)
    handoff = next(
        (item for item in handoff_projection["handoffs"] if item["step_id"] == step_id),
        None,
    )
    if handoff is None:
        raise RuntimeCoreInvariantError("step handoff unavailable")

    decision, reason_code = _gate_preview_to_admission_decision(
        gate_status=preview_body["status"],
        gate_reason=preview_body["reason"],
        allow_simulation_when_blocked=req.allow_simulation_when_blocked,
    )
    supported_actions = {
        "bind_worker_receipt",
        "collect_required_evidence",
        "evaluate_plan_step_gate",
        "review_bound_receipt",
    }
    if req.proposed_action not in supported_actions:
        decision = "block"
        reason_code = "unsupported_handoff_action"
    elif decision == "allow" and req.proposed_action != handoff["next_action"]:
        decision = "defer"
        reason_code = f"handoff_next_action_required:{handoff['next_action']}"

    actor_guard = "not_required_for_preview"
    if req.requested_by_role_id is not None:
        role = kernel.get_role(req.requested_by_role_id)
        if role is None or role.org_id != organization_case.org_id:
            decision = "block"
            reason_code = "actor_role_unavailable"
            actor_guard = "Fail(actor_role_unavailable)"
        else:
            actor_guard = "Pass"

    guard_verdicts = {
        "identity_valid": actor_guard,
        "tenant_valid": "Pass" if organization is not None else "Unknown",
        "authority_valid": (
            "Pass"
            if preview_body["authority_rule_ids"]
            else f"Fail({preview_body['reason']})"
        ),
        "policy_allows": (
            "Pass"
            if preview_body["status"] == PlanStepGateStatus.ALLOWED.value
            else "blocked_by_gate"
        ),
        "risk_acceptable": (
            "Pass"
            if preview_body["reason"] != "capability_risk_exceeded"
            else "Fail(capability_risk_exceeded)"
        ),
        "budget_available": "not_required_for_read_only_preview",
        "evidence_sufficient": "Pass" if not handoff["missing_evidence"] else "Fail(evidence_missing)",
        "temporal_window_valid": "not_required_for_read_only_preview",
        "capability_certified": (
            "Pass"
            if preview_body["reason"] != "capability_not_certified"
            else "Fail(capability_not_certified)"
        ),
        "recovery_available": "Pass" if handoff["rollback_plan_id"] else "not_required_for_read_only_preview",
        "receipt_emittable": "Pass" if req.proposed_action == "bind_worker_receipt" else "not_requested",
    }
    admission_preview_id = stable_identifier(
        "orgos-handoff-action-admission-preview",
        {
            "case_id": case_id,
            "step_id": step_id,
            "proposed_action": req.proposed_action,
            "requested_by_role_id": req.requested_by_role_id,
            "checked_preconditions": req.checked_preconditions,
            "decision": decision,
            "reason_code": reason_code,
        },
    )
    return {
        "admission_preview_id": admission_preview_id,
        "case_id": case_id,
        "step_id": step_id,
        "read_only": True,
        "governed": True,
        "decision": decision,
        "reason_code": reason_code,
        "decision_set": ["allow", "block", "defer", "escalate", "simulate"],
        "decision_scope": "handoff_action_preview",
        "execution_authority_granted": False,
        "dispatch_authority_granted": False,
        "receipt_binding_authority_granted": decision == "allow" and req.proposed_action == "bind_worker_receipt",
        "proposed_action": req.proposed_action,
        "requested_by_role_id": req.requested_by_role_id,
        "gate_preview": preview_body,
        "handoff": handoff,
        "causal_decision_trace": {
            "intent": req.proposed_action,
            "actor": req.requested_by_role_id or "operator.preview",
            "tenant": organization.tenant_id if organization is not None else "",
            "entities": {
                "case_id": case_id,
                "step_id": step_id,
                "department_id": step.department_id,
                "capability_id": step.capability_id,
            },
            "assumptions": [
                "preview_only",
                "no_worker_dispatch",
                "no_case_state_mutation",
            ],
            "evidence_refs": preview_body["evidence_refs"],
            "constraints": [
                "checked_preconditions",
                "capability_certification",
                "authority_rule",
                "required_evidence",
                "required_approval",
                "dual_control",
            ],
            "conflicts": [] if decision == "allow" else [reason_code],
            "guard_verdicts": guard_verdicts,
            "decision": decision,
            "reason_code": reason_code,
            "receipt_ref": None,
            "closure_state": "preview_only",
        },
        "metadata": req.metadata,
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


def _closure_drift_action_table_row(item: dict[str, object]) -> dict[str, object]:
    runbook = item.get("runbook")
    runbook = runbook if isinstance(runbook, dict) else {}
    runbook_binding = item.get("runbook_binding")
    runbook_binding = runbook_binding if isinstance(runbook_binding, dict) else {}
    return {
        "terminal_disposition": item.get("terminal_disposition", ""),
        "action_kind": item.get("action_kind", ""),
        "ready": item.get("ready", False),
        "runbook_id": runbook.get("runbook_id", ""),
        "stage_count": runbook.get("stage_count", 0),
        "topology_valid": runbook.get("topology_valid", False),
        "binding_terminal_stage_id": runbook_binding.get("terminal_stage_id", ""),
        "binding_valid": runbook_binding.get("binding_valid", ""),
        "binding_evidence": _text_list(runbook_binding.get("terminal_verification_evidence", [])),
        "terminal_condition": runbook.get("terminal_condition", ""),
        "required_evidence_types": _text_list(item.get("required_evidence_types", [])),
        "missing_evidence_types": _text_list(item.get("missing_evidence_types", [])),
        "authority_refs": _text_list(item.get("authority_refs", [])),
        "endpoint": item.get("endpoint", ""),
    }


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
    closure_drift_action_projection = payload.get("closure_drift_remediation_actions", {})
    closure_drift_actions = (
        closure_drift_action_projection.get("actions", [])
        if isinstance(closure_drift_action_projection, dict)
        else []
    )
    closure_drift_action_rows = [
        _closure_drift_action_table_row(item)
        for item in closure_drift_actions
        if isinstance(item, dict)
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
    {_proof_explorer_table("Closure Drift Actions", ("terminal_disposition", "action_kind", "ready", "runbook_id", "stage_count", "topology_valid", "binding_terminal_stage_id", "binding_valid", "binding_evidence", "terminal_condition", "required_evidence_types", "missing_evidence_types", "authority_refs", "endpoint"), closure_drift_action_rows)}
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
            "worker_dispatch_receipts": item.get("worker_dispatch_receipt_count", 0),
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
    {_proof_explorer_table("Step Handoffs", ("step_id", "department", "capability", "action", "gate_status", "handoff_status", "next_action", "worker_dispatch_receipts", "worker_receipts", "dispatch_authority"), handoff_rows)}
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


def _closure_gate_evidence_projection(proof: dict[str, Any]) -> dict[str, Any]:
    required_refs: list[str] = []
    stale_gate_decisions: list[dict[str, Any]] = []
    evidence_timeline_by_ref = {
        item["ref"]: item
        for item in proof.get("proof_timeline", [])
        if isinstance(item, dict)
        and item.get("kind") == "evidence"
        and isinstance(item.get("ref"), str)
    }
    for step in proof.get("plan_step_proof", []):
        if not isinstance(step, dict):
            continue
        if step.get("gate_status") != PlanStepGateStatus.ALLOWED.value:
            continue
        decision = step.get("latest_gate_decision")
        decision_refs: list[str] = []
        if isinstance(decision, dict):
            decision_refs = [
                ref for ref in decision.get("evidence_refs", [])
                if isinstance(ref, str)
            ]
        for evidence_ref in decision_refs:
            if isinstance(evidence_ref, str) and evidence_ref not in required_refs:
                required_refs.append(evidence_ref)
        decided_at = decision.get("decided_at") if isinstance(decision, dict) else None
        decision_ref_set = set(decision_refs)
        newer_refs: list[str] = []
        newer_times: list[str] = []
        if isinstance(decided_at, str):
            for evidence_ref in step.get("evidence_refs", []):
                if not isinstance(evidence_ref, str) or evidence_ref in decision_ref_set:
                    continue
                timeline_item = evidence_timeline_by_ref.get(evidence_ref)
                if not isinstance(timeline_item, dict):
                    continue
                occurred_at = timeline_item.get("occurred_at")
                if isinstance(occurred_at, str) and occurred_at > decided_at:
                    newer_refs.append(evidence_ref)
                    newer_times.append(occurred_at)
        if newer_refs and isinstance(decision, dict):
            stale_gate_decisions.append({
                "step_id": step.get("step_id"),
                "decision_id": decision.get("decision_id"),
                "decided_at": decided_at,
                "gate_evidence_refs": decision_refs,
                "newer_evidence_refs": newer_refs,
                "latest_evidence_at": max(newer_times) if newer_times else None,
            })

    admitted_refs = {
        item["ref"]
        for item in proof.get("proof_timeline", [])
        if isinstance(item, dict)
        and item.get("kind") == "evidence"
        and isinstance(item.get("ref"), str)
    }
    unavailable_refs = [ref for ref in required_refs if ref not in admitted_refs]
    closure_certificate = proof.get("closure_certificate")
    closure_refs: list[str] = []
    if isinstance(closure_certificate, dict):
        closure_refs = [
            str(item)
            for item in closure_certificate.get("evidence_refs", [])
            if isinstance(item, str)
        ]
    bound_terminal_certificate_refs: set[str] = set()
    if isinstance(closure_certificate, dict) and isinstance(closure_certificate.get("terminal_certificate_id"), str):
        bound_terminal_certificate_refs.add(str(closure_certificate["terminal_certificate_id"]))
    closure_ref_set = set(closure_refs)
    omitted_refs = [
        ref for ref in required_refs
        if isinstance(closure_certificate, dict) and ref not in closure_ref_set
    ]
    superseded_closure_refs = [
        ref for ref in closure_refs
        if required_refs and ref not in required_refs and ref not in bound_terminal_certificate_refs
    ]
    stale_step_ids = [
        item["step_id"] for item in stale_gate_decisions
        if isinstance(item.get("step_id"), str)
    ]
    newer_gate_evidence_refs: list[str] = []
    for item in stale_gate_decisions:
        for evidence_ref in item.get("newer_evidence_refs", []):
            if isinstance(evidence_ref, str) and evidence_ref not in newer_gate_evidence_refs:
                newer_gate_evidence_refs.append(evidence_ref)
    remediation = _closure_drift_remediation_projection(proof, omitted_refs)
    return {
        "required_gate_evidence_refs": required_refs,
        "admitted_gate_evidence_refs": [ref for ref in required_refs if ref in admitted_refs],
        "unavailable_gate_evidence_refs": unavailable_refs,
        "closure_evidence_refs": closure_refs,
        "omitted_gate_evidence_refs": omitted_refs,
        "superseded_closure_evidence_refs": superseded_closure_refs,
        "closure_packet_drift_refs": omitted_refs,
        "closure_packet_drift": bool(omitted_refs),
        "closure_packet_drift_remediated": remediation is not None,
        "closure_packet_drift_remediation": remediation,
        "stale_gate_decisions": stale_gate_decisions,
        "stale_gate_step_ids": stale_step_ids,
        "newer_gate_evidence_refs": newer_gate_evidence_refs,
        "gate_decisions_fresh": not stale_gate_decisions,
        "closure_packet_present": isinstance(closure_certificate, dict),
        "ready_for_closure_packet": bool(required_refs) and not unavailable_refs and not stale_gate_decisions,
    }


def _closure_drift_remediation_projection(
    proof: dict[str, Any],
    drift_refs: list[str],
) -> dict[str, Any] | None:
    if not drift_refs:
        return None
    closure_certificate = proof.get("closure_certificate")
    if not isinstance(closure_certificate, dict):
        return None
    closure_id = closure_certificate.get("closure_id")
    if not isinstance(closure_id, str):
        return None
    drift_ref_set = set(drift_refs)
    candidates = [
        item for item in proof.get("closure_drift_remediations", [])
        if isinstance(item, dict)
        and item.get("closure_id") == closure_id
        and drift_ref_set.issubset({
            ref for ref in item.get("drift_evidence_refs", [])
            if isinstance(ref, str)
        })
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: str(item.get("created_at", "")))


def _closure_packet_drift_attention_item(
    ref: str,
    closure_gate_evidence: dict[str, Any],
) -> dict[str, object] | None:
    drift_refs = closure_gate_evidence.get("closure_packet_drift_refs", [])
    if not drift_refs:
        return None
    if closure_gate_evidence.get("closure_packet_drift_remediated"):
        remediation = closure_gate_evidence.get("closure_packet_drift_remediation")
        return {
            "kind": "closure_packet_drift_remediated",
            "severity": "review",
            "ref": ref,
            "message": "terminal closure packet drift has explicit remediation routing",
            "evidence_refs": drift_refs,
            "remediation": remediation if isinstance(remediation, dict) else None,
        }
    return {
        "kind": "closure_packet_drift",
        "severity": "blocker",
        "ref": ref,
        "message": "terminal closure packet predates the latest allowed gate evidence; issue review or compensation before relying on closure",
        "evidence_refs": drift_refs,
        "superseded_evidence_refs": closure_gate_evidence.get("superseded_closure_evidence_refs", []),
    }


def _closure_packet_drift_terminal_status(closure_gate_evidence: dict[str, Any]) -> str:
    remediation = closure_gate_evidence.get("closure_packet_drift_remediation")
    if not isinstance(remediation, dict):
        return "closed_packet_drift"
    disposition = remediation.get("terminal_disposition")
    if disposition == TerminalClosureDisposition.COMPENSATED.value:
        return "closed_drift_compensated"
    if disposition == TerminalClosureDisposition.ACCEPTED_RISK.value:
        return "closed_drift_accepted_risk"
    if disposition == TerminalClosureDisposition.REQUIRES_REVIEW.value:
        return "closed_drift_review_required"
    return "closed_packet_drift"


_CLOSURE_DRIFT_REMEDIATION_POLICIES: dict[TerminalClosureDisposition, dict[str, object]] = {
    TerminalClosureDisposition.REQUIRES_REVIEW: {
        "action_kind": "review_required",
        "required_evidence_types": ("closure_drift_review_decision",),
        "description": "Route the drifted closure packet to accountable review before relying on it.",
    },
    TerminalClosureDisposition.COMPENSATED: {
        "action_kind": "compensated",
        "required_evidence_types": ("compensation_receipt", "compensation_effect_reconciliation"),
        "description": "Record compensation evidence for the drifted closure packet.",
    },
    TerminalClosureDisposition.ACCEPTED_RISK: {
        "action_kind": "accepted_risk",
        "required_evidence_types": ("accepted_risk_record", "risk_owner_approval"),
        "description": "Accept the closure packet drift as explicit governed residual risk.",
    },
}


_CLOSURE_DRIFT_REMEDIATION_RUNBOOKS: dict[TerminalClosureDisposition, dict[str, object]] = {
    TerminalClosureDisposition.COMPENSATED: {
        "runbook_id": "runbook:closure-drift-compensation",
        "name": "Closure Drift Compensation",
        "goal": "Restore governed reliance after a terminal closure packet omitted newer gate evidence.",
        "actor": "human_finance_or_security_admin",
        "expected_effect": "closure_drift_compensated_with_reconciled_compensation_effect",
        "forbidden_effects": (
            "rewrite_original_closure_packet",
            "mark_compensation_complete_without_reconciliation",
            "self_approve_high_risk_compensation",
        ),
        "terminal_condition": "append closure drift remediation with terminal_disposition=compensated",
        "rollback_or_compensation": "If compensation evidence fails reconciliation, suspend closure reliance and route to requires_review.",
        "stages": (
            {
                "stage_id": "bind_drift_context",
                "stage_type": "observation",
                "predecessor_ids": (),
                "input_bindings": ("closure_id", "drift_evidence_refs", "superseded_evidence_refs"),
                "output_keys": ("current_drift_context",),
                "timeout": "PT10M",
                "verification_evidence": ("closure_packet_drift_refs",),
            },
            {
                "stage_id": "prepare_compensation",
                "stage_type": "skill_execution",
                "predecessor_ids": ("bind_drift_context",),
                "skill_id": "orgos.closure_drift.compensation.prepare",
                "input_bindings": ("current_drift_context",),
                "output_keys": ("compensation_plan",),
                "timeout": "PT30M",
                "verification_evidence": ("compensation_receipt",),
            },
            {
                "stage_id": "approve_compensation",
                "stage_type": "approval_gate",
                "predecessor_ids": ("prepare_compensation",),
                "input_bindings": ("compensation_plan", "authority_ref"),
                "output_keys": ("approval_ref",),
                "timeout": "P1D",
                "verification_evidence": ("approval_receipt",),
            },
            {
                "stage_id": "observe_compensation_effect",
                "stage_type": "observation",
                "predecessor_ids": ("approve_compensation",),
                "input_bindings": ("compensation_plan",),
                "output_keys": ("compensation_effect_reconciliation",),
                "timeout": "PT1H",
                "verification_evidence": ("compensation_effect_reconciliation",),
            },
            {
                "stage_id": "append_remediation_binding",
                "stage_type": "skill_execution",
                "predecessor_ids": ("observe_compensation_effect",),
                "skill_id": "orgos.closure_drift.remediation.bind",
                "input_bindings": (
                    "closure_id",
                    "authority_ref",
                    "compensation_receipt",
                    "compensation_effect_reconciliation",
                ),
                "output_keys": ("closure_drift_remediation",),
                "timeout": "PT10M",
                "verification_evidence": ("closure_drift_remediation_bound",),
            },
        ),
    },
    TerminalClosureDisposition.ACCEPTED_RISK: {
        "runbook_id": "runbook:closure-drift-accepted-risk",
        "name": "Closure Drift Accepted Risk",
        "goal": "Record bounded residual risk when closure drift cannot be compensated before reliance.",
        "actor": "risk_owner",
        "expected_effect": "closure_drift_recorded_as_bounded_accepted_risk_with_review_obligation",
        "forbidden_effects": (
            "treat_accepted_risk_as_verified_success",
            "accept_risk_without_owner_expiry_or_review",
            "rewrite_original_closure_packet",
        ),
        "terminal_condition": "append closure drift remediation with terminal_disposition=accepted_risk",
        "rollback_or_compensation": "If the risk owner withdraws approval or expiry passes, revoke reliance and open review-required remediation.",
        "stages": (
            {
                "stage_id": "bind_residual_risk_context",
                "stage_type": "observation",
                "predecessor_ids": (),
                "input_bindings": ("closure_id", "drift_evidence_refs", "superseded_evidence_refs"),
                "output_keys": ("residual_risk_context",),
                "timeout": "PT10M",
                "verification_evidence": ("closure_packet_drift_refs",),
            },
            {
                "stage_id": "draft_accepted_risk_record",
                "stage_type": "skill_execution",
                "predecessor_ids": ("bind_residual_risk_context",),
                "skill_id": "orgos.closure_drift.accepted_risk.draft",
                "input_bindings": ("residual_risk_context",),
                "output_keys": ("accepted_risk_record", "review_obligation"),
                "timeout": "PT30M",
                "verification_evidence": ("accepted_risk_record",),
            },
            {
                "stage_id": "risk_owner_approval",
                "stage_type": "approval_gate",
                "predecessor_ids": ("draft_accepted_risk_record",),
                "input_bindings": ("accepted_risk_record", "risk_owner_approval"),
                "output_keys": ("risk_owner_approval_ref",),
                "timeout": "P1D",
                "verification_evidence": ("risk_owner_approval",),
            },
            {
                "stage_id": "wait_for_review_window",
                "stage_type": "wait_for_event",
                "predecessor_ids": ("risk_owner_approval",),
                "input_bindings": ("review_obligation", "expires_at"),
                "output_keys": ("review_window_registered",),
                "timeout": "P1D",
                "verification_evidence": ("review_obligation",),
            },
            {
                "stage_id": "append_remediation_binding",
                "stage_type": "skill_execution",
                "predecessor_ids": ("wait_for_review_window",),
                "skill_id": "orgos.closure_drift.remediation.bind",
                "input_bindings": ("closure_id", "authority_ref", "accepted_risk_record", "risk_owner_approval"),
                "output_keys": ("closure_drift_remediation",),
                "timeout": "PT10M",
                "verification_evidence": ("closure_drift_remediation_bound",),
            },
        ),
    },
}


_CLOSURE_DRIFT_RUNBOOK_STAGE_TYPES = {
    "skill_execution",
    "approval_gate",
    "observation",
    "communication",
    "wait_for_event",
}


def _closure_drift_remediation_policy(disposition: TerminalClosureDisposition) -> dict[str, object]:
    policy = _CLOSURE_DRIFT_REMEDIATION_POLICIES.get(disposition)
    if policy is None:
        raise RuntimeCoreInvariantError("closure drift remediation policy unavailable")
    return policy


def _runbook_string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if isinstance(item, str))
    return ()


def _closure_drift_runbook_projection(disposition: TerminalClosureDisposition) -> dict[str, object] | None:
    runbook = _CLOSURE_DRIFT_REMEDIATION_RUNBOOKS.get(disposition)
    if runbook is None:
        return None
    stages = [
        stage for stage in runbook.get("stages", ())
        if isinstance(stage, dict)
    ]
    stage_ids = {
        str(stage.get("stage_id"))
        for stage in stages
        if isinstance(stage.get("stage_id"), str)
    }
    missing_predecessor_ids = sorted({
        predecessor_id
        for stage in stages
        for predecessor_id in _runbook_string_tuple(stage.get("predecessor_ids", ()))
        if predecessor_id not in stage_ids
    })
    invalid_stage_types = sorted({
        str(stage.get("stage_type"))
        for stage in stages
        if str(stage.get("stage_type")) not in _CLOSURE_DRIFT_RUNBOOK_STAGE_TYPES
    })
    projected_stages = [
        {
            "stage_id": stage.get("stage_id", ""),
            "stage_type": stage.get("stage_type", ""),
            "predecessor_ids": list(_runbook_string_tuple(stage.get("predecessor_ids", ()))),
            "skill_id": stage.get("skill_id", ""),
            "input_bindings": list(_runbook_string_tuple(stage.get("input_bindings", ()))),
            "output_keys": list(_runbook_string_tuple(stage.get("output_keys", ()))),
            "timeout": stage.get("timeout", ""),
            "verification_evidence": list(_runbook_string_tuple(stage.get("verification_evidence", ()))),
        }
        for stage in stages
    ]
    return {
        "runbook_id": runbook["runbook_id"],
        "name": runbook["name"],
        "goal": runbook["goal"],
        "actor": runbook["actor"],
        "expected_effect": runbook["expected_effect"],
        "forbidden_effects": list(_runbook_string_tuple(runbook.get("forbidden_effects", ()))),
        "terminal_condition": runbook["terminal_condition"],
        "rollback_or_compensation": runbook["rollback_or_compensation"],
        "stage_count": len(projected_stages),
        "stage_types": sorted({
            str(stage.get("stage_type"))
            for stage in stages
            if str(stage.get("stage_type")) in _CLOSURE_DRIFT_RUNBOOK_STAGE_TYPES
        }),
        "missing_predecessor_ids": missing_predecessor_ids,
        "invalid_stage_types": invalid_stage_types,
        "topology_valid": not missing_predecessor_ids and not invalid_stage_types,
        "stages": projected_stages,
    }


def _closure_drift_runbook_binding_projection(disposition: TerminalClosureDisposition) -> dict[str, object] | None:
    runbook = _closure_drift_runbook_projection(disposition)
    if runbook is None:
        return None
    stages = [
        stage for stage in runbook.get("stages", [])
        if isinstance(stage, dict)
    ]
    terminal_stages = [
        stage for stage in stages
        if "closure_drift_remediation" in _runbook_string_tuple(stage.get("output_keys", ()))
    ]
    terminal_stage = terminal_stages[-1] if terminal_stages else {}
    terminal_evidence = list(_runbook_string_tuple(terminal_stage.get("verification_evidence", ())))
    validation_errors: list[str] = []
    if runbook.get("topology_valid") is not True:
        validation_errors.append("runbook_topology_invalid")
    if not terminal_stage:
        validation_errors.append("missing_append_remediation_binding_stage")
    elif terminal_stage.get("stage_type") != "skill_execution":
        validation_errors.append("append_remediation_binding_stage_must_execute_skill")
    if "closure_drift_remediation_bound" not in terminal_evidence:
        validation_errors.append("missing_closure_drift_remediation_bound_evidence")
    return {
        "runbook_id": runbook["runbook_id"],
        "terminal_stage_id": terminal_stage.get("stage_id", ""),
        "terminal_condition": runbook["terminal_condition"],
        "terminal_verification_evidence": terminal_evidence,
        "stage_count": runbook["stage_count"],
        "topology_valid": runbook["topology_valid"],
        "binding_valid": not validation_errors,
        "validation_errors": validation_errors,
    }


def _case_evidence_by_ref(kernel: OrganizationKernel, case_id: str) -> dict[str, CaseEvidence]:
    state = kernel.snapshot_state()
    return {
        item.evidence_ref: item
        for item in state.case_evidence
        if item.case_id == case_id
    }


def _case_approval_refs(kernel: OrganizationKernel, case_id: str) -> set[str]:
    state = kernel.snapshot_state()
    return {
        item.approval_id
        for item in state.approvals
        if item.case_id == case_id
    }


def _evidence_type(evidence: CaseEvidence) -> str | None:
    evidence_type = evidence.metadata.get("evidence_type")
    if isinstance(evidence_type, str) and evidence_type:
        return evidence_type
    return None


def _closure_drift_action_readiness(
    *,
    disposition: TerminalClosureDisposition,
    evidence_by_ref: dict[str, CaseEvidence],
    approval_refs: set[str],
    evidence_refs: list[str] | None = None,
    authority_ref: str | None = None,
) -> dict[str, object]:
    policy = _closure_drift_remediation_policy(disposition)
    required_types = tuple(str(item) for item in policy["required_evidence_types"])
    selected_records = [
        evidence_by_ref[evidence_ref]
        for evidence_ref in (evidence_refs or list(evidence_by_ref))
        if evidence_ref in evidence_by_ref
    ]
    available_by_type: dict[str, list[str]] = {evidence_type: [] for evidence_type in required_types}
    for evidence in selected_records:
        evidence_type = _evidence_type(evidence)
        if evidence_type in available_by_type:
            available_by_type[evidence_type].append(evidence.evidence_ref)
    missing_types = [
        evidence_type for evidence_type in required_types
        if not available_by_type[evidence_type]
    ]
    missing_authority = []
    if authority_ref is not None and authority_ref not in approval_refs:
        missing_authority.append(authority_ref)
    return {
        "terminal_disposition": disposition.value,
        "action_kind": policy["action_kind"],
        "description": policy["description"],
        "required_evidence_types": list(required_types),
        "available_evidence_refs_by_type": available_by_type,
        "missing_evidence_types": missing_types,
        "authority_refs": sorted(approval_refs),
        "missing_authority_refs": missing_authority,
        "ready": not missing_types and not missing_authority,
    }


def _case_closure_drift_remediation_action_projection(
    *,
    kernel: OrganizationKernel,
    case_id: str,
    proof: dict[str, Any],
    closure_gate_evidence: dict[str, Any],
) -> dict[str, object]:
    evidence_by_ref = _case_evidence_by_ref(kernel, case_id)
    approval_refs = _case_approval_refs(kernel, case_id)
    closure_certificate = proof["closure_certificate"]
    closure_id = closure_certificate.get("closure_id") if isinstance(closure_certificate, dict) else None
    actions: list[dict[str, object]] = []
    if closure_gate_evidence["closure_packet_drift"]:
        for disposition in _CLOSURE_DRIFT_REMEDIATION_POLICIES:
            readiness = _closure_drift_action_readiness(
                disposition=disposition,
                evidence_by_ref=evidence_by_ref,
                approval_refs=approval_refs,
            )
            actions.append({
                **readiness,
                "runbook": _closure_drift_runbook_projection(disposition),
                "runbook_binding": _closure_drift_runbook_binding_projection(disposition),
                "action_id": stable_identifier(
                    "closure-drift-remediation-action",
                    {
                        "case_id": case_id,
                        "closure_id": closure_id or "",
                        "terminal_disposition": disposition.value,
                    },
                ),
                "closure_id": closure_id,
                "drift_evidence_refs": closure_gate_evidence["closure_packet_drift_refs"],
                "superseded_evidence_refs": closure_gate_evidence["superseded_closure_evidence_refs"],
                "endpoint": f"/api/v1/cases/{quote(case_id, safe='')}/closure-drift-remediation-actions",
            })
    return {
        "case_id": case_id,
        "closure_id": closure_id,
        "closure_packet_drift": closure_gate_evidence["closure_packet_drift"],
        "closure_packet_drift_remediated": closure_gate_evidence["closure_packet_drift_remediated"],
        "drift_evidence_refs": closure_gate_evidence["closure_packet_drift_refs"],
        "superseded_evidence_refs": closure_gate_evidence["superseded_closure_evidence_refs"],
        "action_count": len(actions),
        "ready_action_count": sum(1 for action in actions if action.get("ready") is True),
        "actions": actions,
    }


def _closure_gate_stale_attention_item(
    ref: str,
    closure_gate_evidence: dict[str, Any],
) -> dict[str, object] | None:
    stale_gate_decisions = closure_gate_evidence.get("stale_gate_decisions", [])
    if not stale_gate_decisions:
        return None
    return {
        "kind": "closure_gate_decision_stale",
        "severity": "blocker",
        "ref": ref,
        "message": "allowed plan-step gate predates newer admitted evidence; re-evaluate gate before terminal closure",
        "step_ids": closure_gate_evidence.get("stale_gate_step_ids", []),
        "evidence_refs": closure_gate_evidence.get("newer_gate_evidence_refs", []),
    }

def _case_closure_certificate(kernel: OrganizationKernel, case_id: str) -> dict[str, Any]:
    proof = _case_proof_timeline(kernel, case_id)
    closure_certificate = proof["closure_certificate"]
    closure_gate_evidence = _closure_gate_evidence_projection(proof)
    closure_drift_action_projection = _case_closure_drift_remediation_action_projection(
        kernel=kernel,
        case_id=case_id,
        proof=proof,
        closure_gate_evidence=closure_gate_evidence,
    )
    status = (
        _closure_packet_drift_terminal_status(closure_gate_evidence)
        if closure_gate_evidence["closure_packet_drift"]
        else _closure_status(closure_certificate)
    )
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
        if closure_gate_evidence["required_gate_evidence_refs"]:
            attention_items.append({
                "kind": "closure_gate_evidence_required",
                "severity": "review",
                "ref": case_id,
                "message": "terminal closure must include the latest allowed gate evidence refs",
                "evidence_refs": closure_gate_evidence["required_gate_evidence_refs"],
            })
        stale_attention = _closure_gate_stale_attention_item(case_id, closure_gate_evidence)
        if stale_attention is not None:
            attention_items.append(stale_attention)
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
        drift_attention = _closure_packet_drift_attention_item(closure_certificate["closure_id"], closure_gate_evidence)
        if drift_attention is not None:
            attention_items.append(drift_attention)
        stale_attention = _closure_gate_stale_attention_item(closure_certificate["closure_id"], closure_gate_evidence)
        if stale_attention is not None:
            attention_items.append(stale_attention)
        if closure_gate_evidence["unavailable_gate_evidence_refs"]:
            attention_items.append({
                "kind": "closure_gate_evidence_unavailable",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "latest gate evidence refs are not admitted for this case",
                "evidence_refs": closure_gate_evidence["unavailable_gate_evidence_refs"],
            })
        if (
            closure_gate_evidence["omitted_gate_evidence_refs"]
            and not closure_gate_evidence["closure_packet_drift_remediated"]
        ):
            attention_items.append({
                "kind": "closure_gate_evidence_omitted",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "terminal closure evidence packet omits refs used by allowed plan-step gates",
                "evidence_refs": closure_gate_evidence["omitted_gate_evidence_refs"],
            })
        if not closure_certificate["effect_reconciled"]:
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
        "closure_gate_evidence": closure_gate_evidence,
        "reconciliation": reconciliation,
        "learning_admissions": learning_admissions,
        "closure_drift_remediations": proof.get("closure_drift_remediations", []),
        "closure_drift_remediation_actions": closure_drift_action_projection,
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
    closure_gate_evidence = payload.get("closure_gate_evidence")
    gate_evidence_rows: list[dict[str, object]] = []
    if isinstance(closure_gate_evidence, dict):
        for evidence_ref in closure_gate_evidence.get("required_gate_evidence_refs", []):
            if not isinstance(evidence_ref, str):
                continue
            gate_evidence_rows.append({
                "evidence_ref": evidence_ref,
                "admitted": evidence_ref in closure_gate_evidence.get("admitted_gate_evidence_refs", []),
                "in_closure_packet": evidence_ref in closure_gate_evidence.get("closure_evidence_refs", []),
            })
    closure_packet_drift_rows: list[dict[str, object]] = []
    if isinstance(closure_gate_evidence, dict) and closure_gate_evidence.get("closure_packet_drift"):
        closure_packet_drift_rows.append({
            "missing_latest_evidence_refs": _text_list(closure_gate_evidence.get("closure_packet_drift_refs", [])),
            "superseded_closure_evidence_refs": _text_list(
                closure_gate_evidence.get("superseded_closure_evidence_refs", [])
            ),
        })
    gate_freshness_rows: list[dict[str, object]] = []
    if isinstance(closure_gate_evidence, dict):
        gate_freshness_rows = [
            {
                "step_id": item.get("step_id", ""),
                "decision_id": item.get("decision_id", ""),
                "decided_at": item.get("decided_at", ""),
                "newer_evidence_refs": _text_list(item.get("newer_evidence_refs", [])),
                "latest_evidence_at": item.get("latest_evidence_at", ""),
            }
            for item in closure_gate_evidence.get("stale_gate_decisions", [])
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
            "evidence_refs": _text_list(item.get("evidence_refs", [])),
            "created_at": item.get("created_at", ""),
        }
        for item in payload.get("learning_admissions", [])
        if isinstance(item, dict)
    ]
    remediation_rows = [
        {
            "remediation_id": item.get("remediation_id", ""),
            "terminal_disposition": item.get("terminal_disposition", ""),
            "drift_evidence_refs": _text_list(item.get("drift_evidence_refs", [])),
            "evidence_refs": _text_list(item.get("evidence_refs", [])),
            "created_at": item.get("created_at", ""),
        }
        for item in payload.get("closure_drift_remediations", [])
        if isinstance(item, dict)
    ]
    closure_drift_action_projection = payload.get("closure_drift_remediation_actions", {})
    closure_drift_actions = (
        closure_drift_action_projection.get("actions", [])
        if isinstance(closure_drift_action_projection, dict)
        else []
    )
    closure_drift_action_rows = [
        _closure_drift_action_table_row(item)
        for item in closure_drift_actions
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
    {_proof_explorer_table("Gate Evidence", ("evidence_ref", "admitted", "in_closure_packet"), gate_evidence_rows)}
    {_proof_explorer_table("Closure Packet Drift", ("missing_latest_evidence_refs", "superseded_closure_evidence_refs"), closure_packet_drift_rows)}
    {_proof_explorer_table("Gate Freshness", ("step_id", "decision_id", "decided_at", "newer_evidence_refs", "latest_evidence_at"), gate_freshness_rows)}
    {_proof_explorer_table("Reconciliation", ("field", "value"), reconciliation_rows)}
    {_proof_explorer_table("Evidence Refs", ("evidence_ref",), evidence_rows)}
    {_proof_explorer_table("Learning Admissions", ("binding_id", "decision_id", "admitted", "evidence_refs", "created_at"), learning_rows)}
    {_proof_explorer_table("Closure Drift Remediations", ("remediation_id", "terminal_disposition", "drift_evidence_refs", "evidence_refs", "created_at"), remediation_rows)}
    {_proof_explorer_table("Closure Drift Actions", ("terminal_disposition", "action_kind", "ready", "runbook_id", "stage_count", "topology_valid", "binding_terminal_stage_id", "binding_valid", "binding_evidence", "terminal_condition", "required_evidence_types", "missing_evidence_types", "authority_refs", "endpoint"), closure_drift_action_rows)}
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
    closure_gate_evidence = _closure_gate_evidence_projection(proof)
    if closure_gate_evidence["stale_gate_decisions"]:
        return "awaiting_gate_refresh"
    if summary["has_plan"]:
        return "awaiting_evidence"
    return "awaiting_plan"


def _case_portfolio_terminal_status(proof: dict[str, Any]) -> str:
    closure_certificate = proof["closure_certificate"]
    if closure_certificate is not None:
        closure_gate_evidence = _closure_gate_evidence_projection(proof)
        if closure_gate_evidence["closure_packet_drift"]:
            return _closure_packet_drift_terminal_status(closure_gate_evidence)
        return _closure_status(closure_certificate)
    return _open_case_terminal_status(proof)


def _case_portfolio_attention(case_id: str, proof: dict[str, Any]) -> list[dict[str, object]]:
    summary = proof["summary"]
    closure_certificate = proof["closure_certificate"]
    closure_gate_evidence = _closure_gate_evidence_projection(proof)
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
    stale_attention = _closure_gate_stale_attention_item(case_id, closure_gate_evidence)
    if stale_attention is not None:
        attention_items.append(stale_attention)
    if closure_certificate is None:
        attention_items.append({
            "kind": "missing_terminal_closure",
            "severity": "review",
            "ref": case_id,
            "message": "case has no terminal closure certificate",
        })
        if closure_gate_evidence["required_gate_evidence_refs"]:
            attention_items.append({
                "kind": "closure_gate_evidence_required",
                "severity": "review",
                "ref": case_id,
                "message": "terminal closure must include the latest allowed gate evidence refs",
                "evidence_refs": closure_gate_evidence["required_gate_evidence_refs"],
            })
    else:
        drift_attention = _closure_packet_drift_attention_item(closure_certificate["closure_id"], closure_gate_evidence)
        if drift_attention is not None:
            attention_items.append(drift_attention)
        if closure_gate_evidence["unavailable_gate_evidence_refs"]:
            attention_items.append({
                "kind": "closure_gate_evidence_unavailable",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "latest gate evidence refs are not admitted for this case",
                "evidence_refs": closure_gate_evidence["unavailable_gate_evidence_refs"],
            })
        if (
            closure_gate_evidence["omitted_gate_evidence_refs"]
            and not closure_gate_evidence["closure_packet_drift_remediated"]
        ):
            attention_items.append({
                "kind": "closure_gate_evidence_omitted",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "terminal closure evidence packet omits refs used by allowed plan-step gates",
                "evidence_refs": closure_gate_evidence["omitted_gate_evidence_refs"],
            })
        if not closure_certificate["effect_reconciled"]:
            attention_items.append({
                "kind": "effect_not_reconciled",
                "severity": "blocker",
                "ref": closure_certificate["closure_id"],
                "message": "terminal closure does not have a reconciled external effect",
            })
        if not closure_certificate["learning_admitted"]:
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
            "worker_dispatch_receipt_count": proof["summary"]["worker_dispatch_receipt_count"],
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


_ACTION_QUEUE_FILTER_KEYS = frozenset({
    "decision",
    "severity",
    "department_id",
    "responsible_role_id",
    "case_id",
    "next_action",
})


def _normalize_action_queue_filters(filters: dict[str, object]) -> dict[str, str]:
    unsupported_filters = sorted(set(filters) - _ACTION_QUEUE_FILTER_KEYS)
    if unsupported_filters:
        raise ValueError(f"unsupported action queue filters: {', '.join(unsupported_filters)}")
    return {
        key: value.strip()
        for key, value in filters.items()
        if isinstance(value, str) and value.strip()
    }


def _action_queue_filter_params(
    *,
    decision: str | None = None,
    severity: str | None = None,
    department_id: str | None = None,
    responsible_role_id: str | None = None,
    case_id: str | None = None,
    next_action: str | None = None,
) -> dict[str, str]:
    raw_filters = {
        "decision": decision,
        "severity": severity,
        "department_id": department_id,
        "responsible_role_id": responsible_role_id,
        "case_id": case_id,
        "next_action": next_action,
    }
    return _normalize_action_queue_filters(raw_filters)


def _action_queue_row_matches_filters(row: dict[str, Any], filters: dict[str, str]) -> bool:
    row_fields = {
        "decision": row.get("admission_decision"),
        "severity": row.get("queue_severity"),
        "department_id": row.get("department_id"),
        "responsible_role_id": row.get("responsible_role_id"),
        "case_id": row.get("case_id"),
        "next_action": row.get("next_action"),
    }
    return all(str(row_fields.get(key, "")) == expected for key, expected in filters.items())


def _organization_action_queue(
    kernel: OrganizationKernel,
    org_id: str,
    *,
    filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    organization = _organization_or_404(kernel, org_id)
    state = kernel.snapshot_state()
    cases = tuple(
        sorted(
            (
                item for item in state.cases
                if item.org_id == org_id and item.status is not OrganizationCaseStatus.CLOSED
            ),
            key=lambda item: item.case_id,
        )
    )
    action_rows: list[dict[str, Any]] = []
    attention_items: list[dict[str, object]] = []

    for organization_case in cases:
        handoff_projection = _case_step_handoffs(kernel, organization_case.case_id)
        for handoff in handoff_projection["handoffs"]:
            next_action = str(handoff["next_action"])
            admission_preview = _case_step_action_admission_preview(
                kernel,
                organization_case.case_id,
                str(handoff["step_id"]),
                PlanStepActionAdmissionPreviewRequest(
                    checked_preconditions=list(handoff["preconditions"]),
                    proposed_action=next_action,
                    requested_by_role_id=str(handoff["responsible_role_id"]),
                ),
            )
            queue_severity = "ready" if admission_preview["decision"] == "allow" else "review"
            if admission_preview["decision"] in {"block", "escalate"}:
                queue_severity = "blocker"
            action_id = stable_identifier(
                "orgos-operator-action-queue-item",
                {
                    "org_id": org_id,
                    "case_id": organization_case.case_id,
                    "step_id": handoff["step_id"],
                    "next_action": next_action,
                    "decision": admission_preview["decision"],
                    "reason_code": admission_preview["reason_code"],
                },
            )
            action_row = {
                "action_id": action_id,
                "org_id": org_id,
                "case_id": organization_case.case_id,
                "case_goal": organization_case.goal,
                "case_status": organization_case.status.value,
                "case_risk": organization_case.risk.value,
                "department_id": handoff["department_id"],
                "responsible_role_id": handoff["responsible_role_id"],
                "step_id": handoff["step_id"],
                "capability_id": handoff["capability_id"],
                "next_action": next_action,
                "handoff_status": handoff["handoff_status"],
                "admission_decision": admission_preview["decision"],
                "reason_code": admission_preview["reason_code"],
                "queue_severity": queue_severity,
                "missing_evidence": handoff["missing_evidence"],
                "worker_lease_count": handoff["worker_lease_count"],
                "worker_dispatch_receipt_count": handoff["worker_dispatch_receipt_count"],
                "worker_receipt_count": handoff["worker_receipt_count"],
                "execution_authority_granted": False,
                "dispatch_authority_granted": False,
                "receipt_binding_authority_granted": admission_preview["receipt_binding_authority_granted"],
                "links": {
                    "case": f"/api/v1/cases/{quote(organization_case.case_id, safe='')}",
                    "handoffs": f"/api/v1/cases/{quote(organization_case.case_id, safe='')}/step-handoffs/view",
                    "admission_preview": (
                        f"/api/v1/cases/{quote(organization_case.case_id, safe='')}/plan-steps/"
                        f"{quote(str(handoff['step_id']), safe='')}/admission-preview"
                    ),
                    "selection_preview": f"/api/v1/orgs/{quote(org_id, safe='')}/action-queue/selection-preview",
                    "approval_packet_preview": (
                        f"/api/v1/orgs/{quote(org_id, safe='')}/action-queue/approval-packet-preview"
                    ),
                    "dispatch_lease_preview": (
                        f"/api/v1/orgs/{quote(org_id, safe='')}/action-queue/dispatch-lease-preview"
                    ),
                    "worker_lease": f"/api/v1/orgs/{quote(org_id, safe='')}/action-queue/worker-lease",
                    "worker_dispatch_receipt": (
                        f"/api/v1/orgs/{quote(org_id, safe='')}/action-queue/worker-dispatch-receipt"
                    ),
                },
            }
            action_rows.append(action_row)
            if queue_severity != "ready":
                attention_items.append({
                    "kind": "queued_action_requires_attention",
                    "severity": queue_severity,
                    "ref": action_id,
                    "message": "queued handoff action is not currently allowed",
                    "case_id": organization_case.case_id,
                    "step_id": handoff["step_id"],
                    "reason_code": admission_preview["reason_code"],
                })

    active_filters = dict(filters or {})
    filtered_action_rows = [
        row for row in action_rows
        if _action_queue_row_matches_filters(row, active_filters)
    ]
    filtered_action_refs = {row["action_id"] for row in filtered_action_rows}
    filtered_attention_items = [
        item for item in attention_items
        if str(item.get("ref", "")) in filtered_action_refs
    ]

    decisions = [row["admission_decision"] for row in filtered_action_rows]
    severities = [row["queue_severity"] for row in filtered_action_rows]
    return {
        "queue_id": f"operator-action-queue:{org_id}",
        "org_id": org_id,
        "organization": _body(organization),
        "read_only": True,
        "governed": True,
        "filters": active_filters,
        "summary": {
            "open_case_count": len(cases),
            "total_action_count": len(action_rows),
            "action_count": len(filtered_action_rows),
            "filter_count": len(active_filters),
            "ready_action_count": severities.count("ready"),
            "review_action_count": severities.count("review"),
            "blocker_action_count": severities.count("blocker"),
            "allow_count": decisions.count("allow"),
            "block_count": decisions.count("block"),
            "defer_count": decisions.count("defer"),
            "escalate_count": decisions.count("escalate"),
            "simulate_count": decisions.count("simulate"),
            "execution_authority_granted": False,
            "dispatch_authority_granted": False,
        },
        "actions": filtered_action_rows,
        "attention_items": filtered_attention_items,
    }


def _organization_action_queue_selection_preview(
    kernel: OrganizationKernel,
    org_id: str,
    req: ActionQueueSelectionPreviewRequest,
) -> dict[str, Any]:
    filters = _normalize_action_queue_filters(req.filters)
    queue_projection = _organization_action_queue(kernel, org_id, filters=filters)
    selected_action = next(
        (
            item for item in queue_projection["actions"]
            if item["action_id"] == req.action_id
        ),
        None,
    )
    if selected_action is None:
        raise RuntimeCoreInvariantError("selected action is not visible in the filtered queue")

    case_id = str(selected_action["case_id"])
    step_id = str(selected_action["step_id"])
    handoff_projection = _case_step_handoffs(kernel, case_id)
    handoff = next(
        (item for item in handoff_projection["handoffs"] if item["step_id"] == step_id),
        None,
    )
    if handoff is None:
        raise RuntimeCoreInvariantError("selected action handoff unavailable")

    admission_preview = _case_step_action_admission_preview(
        kernel,
        case_id,
        step_id,
        PlanStepActionAdmissionPreviewRequest(
            checked_preconditions=list(handoff["preconditions"]),
            proposed_action=str(selected_action["next_action"]),
            requested_by_role_id=str(selected_action["responsible_role_id"]),
            allow_simulation_when_blocked=req.allow_simulation_when_blocked,
            metadata=req.metadata,
        ),
    )
    preview_id = stable_identifier(
        "orgos-action-queue-selection-preview",
        {
            "org_id": org_id,
            "action_id": req.action_id,
            "filters": filters,
            "decision": admission_preview["decision"],
            "reason_code": admission_preview["reason_code"],
        },
    )
    workflow_stages = [
        {
            "stage_id": "queue_projection_binding",
            "stage_type": "observation",
            "predecessor_ids": [],
            "input_bindings": ["org_id", "filters", "action_id"],
            "output_keys": ["selected_action"],
            "verification_evidence": [req.action_id],
            "authority_boundary": "read_only_projection",
        },
        {
            "stage_id": "handoff_admission_preview",
            "stage_type": "observation",
            "predecessor_ids": ["queue_projection_binding"],
            "input_bindings": ["case_id", "step_id", "checked_preconditions", "proposed_action"],
            "output_keys": ["admission_preview", "causal_decision_trace"],
            "verification_evidence": [admission_preview["admission_preview_id"]],
            "authority_boundary": "no_execution_no_dispatch",
        },
        {
            "stage_id": "operator_next_step_projection",
            "stage_type": "observation",
            "predecessor_ids": ["handoff_admission_preview"],
            "input_bindings": ["admission_decision", "reason_code"],
            "output_keys": ["operator_next_step"],
            "verification_evidence": [preview_id],
            "authority_boundary": "no_state_write",
        },
    ]
    next_steps_by_decision = {
        "allow": "bind_existing_worker_receipt_or_open_required_approval_surface",
        "block": "resolve_blocking_policy_or_capability_gap",
        "defer": "collect_required_evidence_or_preconditions",
        "escalate": "request_required_human_or_dual_control_approval",
        "simulate": "run_read_only_rehearsal_or_collect_missing_evidence",
    }
    return {
        "selection_preview_id": preview_id,
        "org_id": org_id,
        "queue_id": queue_projection["queue_id"],
        "action_id": req.action_id,
        "read_only": True,
        "governed": True,
        "filters": filters,
        "queue_context": {
            "action_count": queue_projection["summary"]["action_count"],
            "total_action_count": queue_projection["summary"]["total_action_count"],
            "filter_count": queue_projection["summary"]["filter_count"],
        },
        "selected_action": selected_action,
        "admission_preview": admission_preview,
        "selection_decision": admission_preview["decision"],
        "reason_code": admission_preview["reason_code"],
        "simulation_available": admission_preview["decision"] == "simulate",
        "operator_next_step": next_steps_by_decision.get(
            str(admission_preview["decision"]),
            "review_selection_preview",
        ),
        "workflow_projection": {
            "acyclic": True,
            "stage_count": len(workflow_stages),
            "terminal_closure_condition": "preview_only_no_execution",
            "stages": workflow_stages,
        },
        "execution_authority_granted": False,
        "dispatch_authority_granted": False,
        "receipt_binding_authority_granted": False,
        "receipt_ref": None,
        "closure_state": "preview_only",
        "forbidden_effects": [
            "worker_dispatch",
            "case_state_mutation",
            "approval_creation",
            "receipt_binding",
            "terminal_closure",
        ],
        "metadata": req.metadata,
    }


def _organization_action_queue_approval_packet_preview(
    kernel: OrganizationKernel,
    org_id: str,
    req: ActionQueueSelectionPreviewRequest,
) -> dict[str, Any]:
    selection_preview = _organization_action_queue_selection_preview(kernel, org_id, req)
    selected_action = selection_preview["selected_action"]
    admission_preview = selection_preview["admission_preview"]
    handoff = admission_preview["handoff"]
    required_approvals = list(handoff["approvals_required"])
    missing_evidence = list(handoff["missing_evidence"])
    approval_packet_id = stable_identifier(
        "orgos-action-queue-approval-packet-preview",
        {
            "org_id": org_id,
            "action_id": req.action_id,
            "selection_preview_id": selection_preview["selection_preview_id"],
            "required_approvals": required_approvals,
            "decision": admission_preview["decision"],
            "reason_code": admission_preview["reason_code"],
        },
    )
    approval_roles = [
        {
            "approval_scope": approval_scope,
            "required": True,
            "satisfied": False,
            "requested_role_id": selected_action["responsible_role_id"],
            "separation_of_duty_required": True,
            "self_approval_forbidden": True,
        }
        for approval_scope in required_approvals
    ]
    packet_decision = "approval_required" if required_approvals else "approval_not_required"
    if admission_preview["decision"] in {"block", "defer", "simulate"} and missing_evidence:
        packet_decision = "awaiting_evidence_before_approval"
    elif admission_preview["decision"] == "escalate":
        packet_decision = "approval_required"

    workflow_stages = [
        {
            "stage_id": "selection_preview_binding",
            "stage_type": "observation",
            "predecessor_ids": [],
            "input_bindings": ["org_id", "action_id", "filters"],
            "output_keys": ["selection_preview", "selected_action", "admission_preview"],
            "verification_evidence": [selection_preview["selection_preview_id"]],
            "authority_boundary": "read_only_projection",
        },
        {
            "stage_id": "approval_requirement_projection",
            "stage_type": "approval_gate",
            "predecessor_ids": ["selection_preview_binding"],
            "input_bindings": ["approvals_required", "responsible_role_id", "case_risk"],
            "output_keys": ["approval_roles", "approval_packet_decision"],
            "verification_evidence": [approval_packet_id],
            "authority_boundary": "no_approval_creation",
        },
        {
            "stage_id": "operator_review_packet",
            "stage_type": "observation",
            "predecessor_ids": ["approval_requirement_projection"],
            "input_bindings": ["approval_packet_decision", "missing_evidence", "reason_code"],
            "output_keys": ["operator_next_step"],
            "verification_evidence": [approval_packet_id],
            "authority_boundary": "no_dispatch_no_receipt_binding",
        },
    ]
    next_steps_by_decision = {
        "approval_required": "open_explicit_approval_request_after_evidence_is_complete",
        "approval_not_required": "continue_with_admission_preview_next_step",
        "awaiting_evidence_before_approval": "collect_required_evidence_before_requesting_approval",
    }
    return {
        "approval_packet_preview_id": approval_packet_id,
        "org_id": org_id,
        "action_id": req.action_id,
        "case_id": selected_action["case_id"],
        "step_id": selected_action["step_id"],
        "read_only": True,
        "governed": True,
        "selection_preview": selection_preview,
        "approval_packet_decision": packet_decision,
        "approval_roles": approval_roles,
        "required_approvals": required_approvals,
        "approval_count": len(required_approvals),
        "missing_evidence": missing_evidence,
        "evidence_ready": not missing_evidence,
        "separation_of_duty": {
            "required": bool(required_approvals),
            "requesting_role_id": selected_action["responsible_role_id"],
            "self_approval_forbidden": bool(required_approvals),
            "satisfied": False,
        },
        "workflow_projection": {
            "acyclic": True,
            "stage_count": len(workflow_stages),
            "terminal_closure_condition": "preview_only_no_approval_mutation",
            "stages": workflow_stages,
        },
        "operator_next_step": next_steps_by_decision[packet_decision],
        "approval_creation_authority_granted": False,
        "execution_authority_granted": False,
        "dispatch_authority_granted": False,
        "receipt_binding_authority_granted": False,
        "receipt_ref": None,
        "closure_state": "preview_only",
        "forbidden_effects": [
            "approval_creation",
            "approval_decision",
            "worker_dispatch",
            "case_state_mutation",
            "receipt_binding",
            "terminal_closure",
        ],
        "metadata": req.metadata,
    }


def _organization_action_queue_dispatch_lease_preview(
    kernel: OrganizationKernel,
    org_id: str,
    req: ActionQueueSelectionPreviewRequest,
) -> dict[str, Any]:
    selection_preview = _organization_action_queue_selection_preview(kernel, org_id, req)
    selected_action = selection_preview["selected_action"]
    admission_preview = selection_preview["admission_preview"]
    handoff = admission_preview["handoff"]
    missing_evidence = list(handoff["missing_evidence"])
    required_approvals = list(handoff["approvals_required"])
    decision = str(admission_preview["decision"])
    reason_code = str(admission_preview["reason_code"])
    lease_decision = "lease_not_admissible"
    if decision == "allow":
        lease_decision = "lease_request_ready"
    elif decision == "simulate":
        lease_decision = "simulation_only"
    elif reason_code in {"approval_missing", "dual_control_missing"}:
        lease_decision = "awaiting_approval"
    elif missing_evidence:
        lease_decision = "awaiting_evidence"

    lease_preview_id = stable_identifier(
        "orgos-action-queue-dispatch-lease-preview",
        {
            "org_id": org_id,
            "action_id": req.action_id,
            "selection_preview_id": selection_preview["selection_preview_id"],
            "capability_id": selected_action["capability_id"],
            "lease_decision": lease_decision,
            "reason_code": reason_code,
        },
    )
    lease_scope = {
        "case_id": selected_action["case_id"],
        "step_id": selected_action["step_id"],
        "department_id": selected_action["department_id"],
        "responsible_role_id": selected_action["responsible_role_id"],
        "capability_id": selected_action["capability_id"],
        "expected_effect": handoff["expected_effect"],
        "allowed_next_action": selected_action["next_action"],
        "sandbox_required": True,
        "receipt_required": True,
        "timeout_required": True,
        "budget_required": True,
    }
    blockers = []
    if missing_evidence:
        blockers.append({
            "kind": "missing_evidence",
            "refs": missing_evidence,
        })
    if lease_decision == "awaiting_approval":
        blockers.append({
            "kind": "approval_required",
            "refs": required_approvals,
        })
    if decision == "block":
        blockers.append({
            "kind": "admission_blocked",
            "refs": [reason_code],
        })

    workflow_stages = [
        {
            "stage_id": "selection_preview_binding",
            "stage_type": "observation",
            "predecessor_ids": [],
            "input_bindings": ["org_id", "action_id", "filters"],
            "output_keys": ["selection_preview", "admission_preview"],
            "verification_evidence": [selection_preview["selection_preview_id"]],
            "authority_boundary": "read_only_projection",
        },
        {
            "stage_id": "dispatch_lease_projection",
            "stage_type": "approval_gate",
            "predecessor_ids": ["selection_preview_binding"],
            "input_bindings": ["capability_id", "responsible_role_id", "evidence_refs", "approval_refs"],
            "output_keys": ["lease_scope", "lease_decision", "lease_blockers"],
            "verification_evidence": [lease_preview_id],
            "authority_boundary": "no_worker_lease_mutation",
        },
        {
            "stage_id": "operator_dispatch_review",
            "stage_type": "observation",
            "predecessor_ids": ["dispatch_lease_projection"],
            "input_bindings": ["lease_decision", "lease_scope", "lease_blockers"],
            "output_keys": ["operator_next_step"],
            "verification_evidence": [lease_preview_id],
            "authority_boundary": "no_worker_dispatch",
        },
    ]
    next_steps_by_decision = {
        "lease_request_ready": "open_bounded_worker_lease_request",
        "simulation_only": "run_read_only_simulation_or_collect_evidence",
        "awaiting_approval": "complete_required_approval_before_lease",
        "awaiting_evidence": "collect_required_evidence_before_lease",
        "lease_not_admissible": "resolve_admission_blocker_before_lease",
    }
    return {
        "dispatch_lease_preview_id": lease_preview_id,
        "org_id": org_id,
        "action_id": req.action_id,
        "case_id": selected_action["case_id"],
        "step_id": selected_action["step_id"],
        "read_only": True,
        "governed": True,
        "selection_preview": selection_preview,
        "lease_decision": lease_decision,
        "lease_scope": lease_scope,
        "lease_blockers": blockers,
        "lease_blocker_count": len(blockers),
        "required_approvals": required_approvals,
        "missing_evidence": missing_evidence,
        "workflow_projection": {
            "acyclic": True,
            "stage_count": len(workflow_stages),
            "terminal_closure_condition": "preview_only_no_worker_lease",
            "stages": workflow_stages,
        },
        "operator_next_step": next_steps_by_decision[lease_decision],
        "worker_lease_authority_granted": False,
        "execution_authority_granted": False,
        "dispatch_authority_granted": False,
        "receipt_binding_authority_granted": False,
        "receipt_ref": None,
        "closure_state": "preview_only",
        "forbidden_effects": [
            "worker_lease_creation",
            "worker_dispatch",
            "case_state_mutation",
            "approval_creation",
            "receipt_binding",
            "terminal_closure",
        ],
        "metadata": req.metadata,
    }


def _organization_action_queue_worker_lease(
    kernel: OrganizationKernel,
    org_id: str,
    req: WorkerLeaseCreateRequest,
) -> dict[str, Any]:
    dispatch_preview = _organization_action_queue_dispatch_lease_preview(
        kernel,
        org_id,
        ActionQueueSelectionPreviewRequest(
            action_id=req.action_id,
            filters=req.filters,
            allow_simulation_when_blocked=False,
            metadata=req.metadata,
        ),
    )
    if dispatch_preview["lease_decision"] != "lease_request_ready":
        raise RuntimeCoreInvariantError("worker lease requires ready dispatch lease preview")

    lease_scope = dispatch_preview["lease_scope"]
    admission_preview = dispatch_preview["selection_preview"]["admission_preview"]
    handoff = admission_preview["handoff"]
    if req.requested_by_role_id != lease_scope["responsible_role_id"]:
        raise RuntimeCoreInvariantError("worker lease requester must match responsible role")

    created_at = _clock_now()
    receipt = kernel.create_worker_lease_receipt(
        PlanStepWorkerLeaseReceipt(
            lease_id=req.lease_id,
            case_id=str(lease_scope["case_id"]),
            step_id=str(lease_scope["step_id"]),
            capability_id=str(lease_scope["capability_id"]),
            responsible_role_id=str(lease_scope["responsible_role_id"]),
            requested_by_role_id=req.requested_by_role_id,
            dispatch_lease_preview_id=str(dispatch_preview["dispatch_lease_preview_id"]),
            queued_action=str(lease_scope["allowed_next_action"]),
            capability_action=str(handoff["action"]),
            expected_effect=str(lease_scope["expected_effect"]),
            evidence_refs=tuple(req.evidence_refs),
            timeout_seconds=req.timeout_seconds,
            budget_ref=req.budget_ref,
            created_at=created_at,
            metadata={
                **req.metadata,
                "source": "orgos_action_queue_worker_lease",
                "worker_dispatch_started": False,
                "receipt_binding_created": False,
                "approval_creation_authority_granted": False,
                "terminal_closure_created": False,
            },
        )
    )
    return {
        "worker_lease": _body(receipt),
        "dispatch_lease_preview": dispatch_preview,
        "lease_created": True,
        "worker_dispatch_started": False,
        "receipt_binding_created": False,
        "approval_created": False,
        "terminal_closure_created": False,
        "execution_authority_granted": False,
        "dispatch_authority_granted": False,
        "receipt_binding_authority_granted": False,
        "closure_state": "worker_lease_created_only",
        "forbidden_effects": [
            "worker_dispatch",
            "worker_output_binding",
            "case_status_mutation",
            "evidence_admission",
            "approval_creation",
            "receipt_binding",
            "terminal_closure",
        ],
        "governed": True,
    }


def _organization_action_queue_worker_dispatch_receipt(
    kernel: OrganizationKernel,
    org_id: str,
    req: WorkerDispatchReceiptCreateRequest,
) -> dict[str, Any]:
    dispatch_preview = _organization_action_queue_dispatch_lease_preview(
        kernel,
        org_id,
        ActionQueueSelectionPreviewRequest(
            action_id=req.action_id,
            filters=req.filters,
            allow_simulation_when_blocked=False,
            metadata=req.metadata,
        ),
    )
    if dispatch_preview["lease_decision"] != "lease_request_ready":
        raise RuntimeCoreInvariantError("worker dispatch receipt requires ready dispatch lease preview")

    lease_scope = dispatch_preview["lease_scope"]
    state = kernel.snapshot_state()
    lease_receipt = next(
        (item for item in state.worker_lease_receipts if item.lease_id == req.worker_lease_id),
        None,
    )
    if lease_receipt is None:
        raise RuntimeCoreInvariantError("worker dispatch receipt lease unavailable")
    if lease_receipt.case_id != lease_scope["case_id"]:
        raise RuntimeCoreInvariantError("worker dispatch receipt selected case mismatch")
    if lease_receipt.step_id != lease_scope["step_id"]:
        raise RuntimeCoreInvariantError("worker dispatch receipt selected step mismatch")
    if lease_receipt.capability_id != lease_scope["capability_id"]:
        raise RuntimeCoreInvariantError("worker dispatch receipt selected capability mismatch")
    if req.requested_by_role_id != lease_receipt.requested_by_role_id:
        raise RuntimeCoreInvariantError("worker dispatch receipt requester must match lease requester")

    receipt = kernel.record_worker_dispatch_receipt(
        PlanStepWorkerDispatchReceipt(
            dispatch_receipt_id=req.dispatch_receipt_id,
            dispatch_request_id=req.dispatch_request_id,
            case_id=lease_receipt.case_id,
            step_id=lease_receipt.step_id,
            worker_lease_id=lease_receipt.lease_id,
            capability_id=lease_receipt.capability_id,
            responsible_role_id=lease_receipt.responsible_role_id,
            requested_by_role_id=req.requested_by_role_id,
            worker_id=req.worker_id,
            dispatch_intent=req.dispatch_intent,
            expected_effect=lease_receipt.expected_effect,
            evidence_refs=tuple(req.evidence_refs),
            lease_created_at=lease_receipt.created_at,
            dispatched_at=_clock_now(),
            metadata={
                **req.metadata,
                "source": "orgos_action_queue_worker_dispatch_receipt",
                "worker_execution_started": False,
                "worker_output_bound": False,
                "evidence_admitted": False,
                "approval_creation_authority_granted": False,
                "terminal_closure_created": False,
            },
        )
    )
    return {
        "worker_dispatch_receipt": _body(receipt),
        "dispatch_lease_preview": dispatch_preview,
        "dispatch_envelope_created": True,
        "worker_execution_started": False,
        "worker_output_bound": False,
        "receipt_binding_created": False,
        "evidence_admitted": False,
        "approval_created": False,
        "terminal_closure_created": False,
        "execution_authority_granted": False,
        "dispatch_authority_granted": False,
        "receipt_binding_authority_granted": False,
        "closure_state": "worker_dispatch_receipt_created_only",
        "forbidden_effects": [
            "worker_execution",
            "worker_output_binding",
            "case_status_mutation",
            "evidence_admission",
            "approval_creation",
            "receipt_binding",
            "terminal_closure",
        ],
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


def _render_action_queue_html(payload: dict[str, Any]) -> str:
    raw_org_id = str(payload.get("org_id", ""))
    org_id = escape(raw_org_id)
    organization = payload.get("organization", {})
    org_name = escape(str(organization.get("name", ""))) if isinstance(organization, dict) else ""
    summary = payload.get("summary", {})
    summary_rows = [
        {"metric": key, "value": value}
        for key, value in sorted(summary.items())
    ] if isinstance(summary, dict) else []
    filters = payload.get("filters", {})
    filter_rows = [
        {"filter": key, "value": value}
        for key, value in sorted(filters.items())
    ] if isinstance(filters, dict) else []
    action_rows = [
        {
            "severity": item.get("queue_severity", ""),
            "decision": item.get("admission_decision", ""),
            "next_action": item.get("next_action", ""),
            "case_id": item.get("case_id", ""),
            "step_id": item.get("step_id", ""),
            "department": item.get("department_id", ""),
            "role": item.get("responsible_role_id", ""),
            "reason": item.get("reason_code", ""),
            "dispatch_receipts": item.get("worker_dispatch_receipt_count", 0),
            "receipts": item.get("worker_receipt_count", 0),
        }
        for item in payload.get("actions", [])
        if isinstance(item, dict)
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
    filter_query = urlencode(filters) if isinstance(filters, dict) and filters else ""
    json_url = f"/api/v1/orgs/{quoted_org_id}/action-queue"
    if filter_query:
        json_url = f"{json_url}?{filter_query}"
    portfolio_url = f"/api/v1/orgs/{quoted_org_id}/case-portfolio/view"
    authority_url = f"/api/v1/orgs/{quoted_org_id}/authority-map/view"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mullu OrgOS Action Queue</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; color: #1f2937; background: #f7f7f4; }}
    header {{ background: #26313d; color: #ffffff; padding: 24px 28px; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 22px; }}
    nav {{ display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }}
    nav a {{ color: #d8ecff; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; letter-spacing: 0; }}
    .status {{ margin-top: 8px; color: #e4edf6; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; overflow-wrap: anywhere; }}
    th {{ background: #edf1f5; color: #26313d; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu OrgOS Action Queue</h1>
    <div class="status">Organization <strong>{org_id}</strong> | <strong>{org_name}</strong></div>
    <nav>
      <a href="{escape(json_url)}">json queue</a>
      <a href="{escape(portfolio_url)}">case portfolio</a>
      <a href="{escape(authority_url)}">authority map</a>
    </nav>
  </header>
  <main>
    {_proof_explorer_table("Summary", ("metric", "value"), summary_rows)}
    {_proof_explorer_table("Filters", ("filter", "value"), filter_rows)}
    {_proof_explorer_table("Attention", ("severity", "kind", "ref", "message"), attention_rows)}
    {_proof_explorer_table("Actions", ("severity", "decision", "next_action", "case_id", "step_id", "department", "role", "reason", "receipts"), action_rows)}
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
    admitted.append(
        kernel.admit_case_evidence(
            CaseEvidence(
                evidence_ref=req.terminal_certificate_id,
                case_id=case_id,
                requirement_id=TERMINAL_CLOSURE_CERTIFICATE_REQUIREMENT,
                submitted_by=req.submitted_by,
                submitted_at=_clock_now(),
                metadata={
                    "source": "launch_gateway_pilot_readiness_packet",
                    "request": req.metadata,
                    "terminal_certificate_id": req.terminal_certificate_id,
                },
            )
        )
    )
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
    refs.append(req.terminal_certificate_id)
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
    plan = kernel.plan_for_case(case_id)
    closure = kernel.closure_for_case(case_id)
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
    required_closure_evidence_refs: list[str] = []
    for row in plan_step_rows:
        decision = row.get("latest_gate_decision")
        if row["gate_status"] != PlanStepGateStatus.ALLOWED.value or not isinstance(decision, dict):
            continue
        for evidence_ref in decision.get("evidence_refs", []):
            if isinstance(evidence_ref, str) and evidence_ref not in required_closure_evidence_refs:
                required_closure_evidence_refs.append(evidence_ref)
    preview_blocked_steps = [
        preview.step_id for preview in gate_preview
        if preview.status is not PlanStepGateStatus.ALLOWED
    ]
    preview_required_closure_evidence_refs: list[str] = []
    for preview in gate_preview:
        if preview.status is not PlanStepGateStatus.ALLOWED:
            continue
        for evidence_ref in preview.evidence_refs:
            if evidence_ref not in preview_required_closure_evidence_refs:
                preview_required_closure_evidence_refs.append(evidence_ref)
    closure_evidence_refs = []
    if closure is not None:
        closure_evidence_refs = list(closure.evidence_refs)
    omitted_closure_gate_evidence_refs = [
        evidence_ref for evidence_ref in required_closure_evidence_refs
        if closure is not None and evidence_ref not in closure_evidence_refs
    ]
    closure_gate_evidence = _closure_gate_evidence_projection(_case_proof_timeline(kernel, case_id))
    stale_gate_steps = closure_gate_evidence["stale_gate_step_ids"]
    newer_gate_evidence_refs = closure_gate_evidence["newer_gate_evidence_refs"]
    ready_to_close = (
        closure is None
        and not missing_evidence
        and bool(approvals)
        and not blocked_steps
        and not stale_gate_steps
    )
    preview_ready_to_close = (
        closure is None
        and not missing_evidence
        and bool(approvals)
        and not preview_blocked_steps
    )
    if closure is not None:
        terminal_status = (
            _closure_packet_drift_terminal_status(closure_gate_evidence)
            if closure_gate_evidence["closure_packet_drift"]
            else "closed"
        )
    elif missing_evidence:
        terminal_status = "awaiting_evidence"
    elif not approvals:
        terminal_status = "awaiting_approval"
    elif blocked_steps:
        terminal_status = "awaiting_gate"
    elif stale_gate_steps:
        terminal_status = "awaiting_gate_refresh"
    else:
        terminal_status = "ready_to_close"
    if closure is not None:
        preview_terminal_status = (
            _closure_packet_drift_terminal_status(closure_gate_evidence)
            if closure_gate_evidence["closure_packet_drift"]
            else "closed"
        )
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
        "required_closure_evidence_refs": required_closure_evidence_refs,
        "gate_preview": [_body(preview) for preview in gate_preview],
        "preview_blocked_steps": preview_blocked_steps,
        "preview_required_closure_evidence_refs": preview_required_closure_evidence_refs,
        "omitted_closure_gate_evidence_refs": omitted_closure_gate_evidence_refs,
        "closure_packet_drift": closure_gate_evidence["closure_packet_drift"],
        "closure_packet_drift_refs": closure_gate_evidence["closure_packet_drift_refs"],
        "closure_packet_drift_remediated": closure_gate_evidence["closure_packet_drift_remediated"],
        "closure_packet_drift_remediation": closure_gate_evidence["closure_packet_drift_remediation"],
        "superseded_closure_evidence_refs": closure_gate_evidence["superseded_closure_evidence_refs"],
        "stale_gate_decisions": closure_gate_evidence["stale_gate_decisions"],
        "stale_gate_step_ids": stale_gate_steps,
        "newer_gate_evidence_refs": newer_gate_evidence_refs,
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


@router.get("/api/v1/orgs/{org_id}/action-queue")
def get_organization_action_queue(
    org_id: str,
    request: Request,
    decision: str | None = None,
    severity: str | None = None,
    department_id: str | None = None,
    responsible_role_id: str | None = None,
    case_id: str | None = None,
    next_action: str | None = None,
):
    """Return a read-only operator action queue for open case handoffs."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    return _organization_action_queue(
        kernel,
        org_id,
        filters=_action_queue_filter_params(
            decision=decision,
            severity=severity,
            department_id=department_id,
            responsible_role_id=responsible_role_id,
            case_id=case_id,
            next_action=next_action,
        ),
    )


@router.get("/api/v1/orgs/{org_id}/action-queue/view")
def get_organization_action_queue_view(
    org_id: str,
    request: Request,
    decision: str | None = None,
    severity: str | None = None,
    department_id: str | None = None,
    responsible_role_id: str | None = None,
    case_id: str | None = None,
    next_action: str | None = None,
):
    """Return a browser-facing read-only operator action queue."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    return HTMLResponse(
        _render_action_queue_html(
            _organization_action_queue(
                kernel,
                org_id,
                filters=_action_queue_filter_params(
                    decision=decision,
                    severity=severity,
                    department_id=department_id,
                    responsible_role_id=responsible_role_id,
                    case_id=case_id,
                    next_action=next_action,
                ),
            )
        )
    )


@router.post("/api/v1/orgs/{org_id}/action-queue/selection-preview")
def preview_organization_action_queue_selection(
    org_id: str,
    req: ActionQueueSelectionPreviewRequest,
    request: Request,
):
    """Preview a visible queued action selection without executing or mutating case state."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    try:
        return _organization_action_queue_selection_preview(kernel, org_id, req)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail(
                "action queue selection preview rejected",
                "action_queue_selection_preview_rejected",
            ),
        ) from exc


@router.post("/api/v1/orgs/{org_id}/action-queue/approval-packet-preview")
def preview_organization_action_queue_approval_packet(
    org_id: str,
    req: ActionQueueSelectionPreviewRequest,
    request: Request,
):
    """Preview approval requirements for a visible queued action without mutating approvals."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    try:
        return _organization_action_queue_approval_packet_preview(kernel, org_id, req)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail(
                "action queue approval packet preview rejected",
                "action_queue_approval_packet_preview_rejected",
            ),
        ) from exc


@router.post("/api/v1/orgs/{org_id}/action-queue/dispatch-lease-preview")
def preview_organization_action_queue_dispatch_lease(
    org_id: str,
    req: ActionQueueSelectionPreviewRequest,
    request: Request,
):
    """Preview a bounded worker lease envelope without creating a lease or dispatching work."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    try:
        return _organization_action_queue_dispatch_lease_preview(kernel, org_id, req)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail(
                "action queue dispatch lease preview rejected",
                "action_queue_dispatch_lease_preview_rejected",
            ),
        ) from exc


@router.post("/api/v1/orgs/{org_id}/action-queue/worker-lease")
def create_organization_action_queue_worker_lease(
    org_id: str,
    req: WorkerLeaseCreateRequest,
    request: Request,
):
    """Create a bounded worker lease receipt without dispatching a worker."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    try:
        payload = _organization_action_queue_worker_lease(kernel, org_id, req)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail(
                "action queue worker lease rejected",
                "action_queue_worker_lease_rejected",
            ),
        ) from exc
    _persist_kernel(kernel)
    return payload


@router.post("/api/v1/orgs/{org_id}/action-queue/worker-dispatch-receipt")
def create_organization_action_queue_worker_dispatch_receipt(
    org_id: str,
    req: WorkerDispatchReceiptCreateRequest,
    request: Request,
):
    """Record a bounded worker dispatch envelope without executing a worker."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_organization_tenant(request, kernel, org_id)
    try:
        payload = _organization_action_queue_worker_dispatch_receipt(kernel, org_id, req)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail(
                "action queue worker dispatch receipt rejected",
                "action_queue_worker_dispatch_receipt_rejected",
            ),
        ) from exc
    _persist_kernel(kernel)
    return payload


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


@router.post("/api/v1/cases/{case_id}/plan-steps/{step_id}/admission-preview")
def preview_case_plan_step_action_admission(
    case_id: str,
    step_id: str,
    req: PlanStepActionAdmissionPreviewRequest,
    request: Request,
):
    """Preview handoff action admission without executing or mutating case state."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    try:
        return _case_step_action_admission_preview(kernel, case_id, step_id, req)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail(
                "plan step action admission preview rejected",
                "plan_step_admission_preview_rejected",
            ),
        ) from exc


@router.post("/api/v1/cases/{case_id}/plan-steps/{step_id}/private-pilot/rehearsal")
def preview_case_private_pilot_live_rehearsal(
    case_id: str,
    step_id: str,
    req: PlanStepActionAdmissionPreviewRequest,
    request: Request,
):
    """Project a tenant-bound private pilot story from a live OrgOS preview."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    try:
        organization_case = _case_or_404(kernel, case_id)
        state = kernel.snapshot_state()
        organization = next(
            (item for item in state.organizations if item.org_id == organization_case.org_id),
            None,
        )
        if organization is None:
            raise RuntimeCoreInvariantError("organization unavailable")
        admission_preview = _case_step_action_admission_preview(kernel, case_id, step_id, req)
        story_request = PrivatePilotStoryRequest(
            tenant_id=organization.tenant_id,
            org_id=organization_case.org_id,
            case_id=case_id,
            actor_id=req.requested_by_role_id or "operator.preview",
        )
        rehearsal_uao = build_private_pilot_live_rehearsal_uao_record(
            story_request,
            (admission_preview,),
            created_at=_clock_now(),
        )
        uao_records = load_private_pilot_uao_records()
        uao_records["rehearsal"] = rehearsal_uao
        story = build_private_pilot_story(
            story_request,
            uao_records=uao_records,
            created_at=_clock_now(),
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail(
                "private pilot rehearsal rejected",
                "private_pilot_rehearsal_rejected",
            ),
        ) from exc
    return {
        "operation": "private_pilot_live_rehearsal",
        "case_id": case_id,
        "step_id": step_id,
        "read_only": True,
        "governed": True,
        "execution_authority_granted": False,
        "dispatch_authority_granted": False,
        "receipt_ref": rehearsal_uao["closure"]["closure_receipt_ref"],
        "admission_preview": admission_preview,
        "rehearsal_uao": rehearsal_uao,
        "story": story,
    }


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
                evidence_refs=tuple(req.evidence_refs),
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


@router.post("/api/v1/cases/{case_id}/closure-drift-remediations")
def bind_case_closure_drift_remediation(case_id: str, req: ClosureDriftRemediationRequest, request: Request):
    """Bind review, compensation, or accepted-risk routing for a drifted closure packet."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    proof = _case_proof_timeline(kernel, case_id)
    closure_gate_evidence = _closure_gate_evidence_projection(proof)
    if not closure_gate_evidence["closure_packet_drift"]:
        raise HTTPException(
            400,
            detail=_error_detail("closure packet drift unavailable", "closure_packet_drift_unavailable"),
        )
    current_drift_refs = set(closure_gate_evidence["closure_packet_drift_refs"])
    requested_drift_refs = set(req.drift_evidence_refs)
    if current_drift_refs != requested_drift_refs:
        raise HTTPException(
            400,
            detail=_error_detail("closure drift evidence mismatch", "closure_drift_evidence_mismatch"),
        )
    try:
        binding = kernel.bind_closure_drift_remediation(
            ClosureDriftRemediationBinding(
                remediation_id=req.remediation_id,
                case_id=case_id,
                closure_id=req.closure_id,
                terminal_disposition=TerminalClosureDisposition(req.terminal_disposition),
                drift_evidence_refs=tuple(req.drift_evidence_refs),
                superseded_evidence_refs=tuple(req.superseded_evidence_refs),
                authority_ref=req.authority_ref,
                evidence_refs=tuple(req.evidence_refs),
                created_at=_clock_now(),
                metadata=req.metadata,
            )
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("closure drift remediation rejected", "closure_drift_remediation_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {"closure_drift_remediation": _body(binding), "governed": True}


@router.get("/api/v1/cases/{case_id}/closure-drift-remediation-actions")
def get_case_closure_drift_remediation_actions(case_id: str, request: Request):
    """Return operator-ready remediation actions for a drifted closure packet."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    proof = _case_proof_timeline(kernel, case_id)
    closure_gate_evidence = _closure_gate_evidence_projection(proof)
    projection = _case_closure_drift_remediation_action_projection(
        kernel=kernel,
        case_id=case_id,
        proof=proof,
        closure_gate_evidence=closure_gate_evidence,
    )
    return {
        **projection,
        "governed": True,
    }


@router.post("/api/v1/cases/{case_id}/closure-drift-remediation-actions")
def execute_case_closure_drift_remediation_action(
    case_id: str,
    req: ClosureDriftRemediationActionRequest,
    request: Request,
):
    """Execute a policy-checked operator remediation action for a drifted closure packet."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _enforce_case_tenant(request, kernel, case_id)
    proof = _case_proof_timeline(kernel, case_id)
    closure_gate_evidence = _closure_gate_evidence_projection(proof)
    if not closure_gate_evidence["closure_packet_drift"]:
        raise HTTPException(
            400,
            detail=_error_detail("closure packet drift unavailable", "closure_packet_drift_unavailable"),
        )
    try:
        disposition = TerminalClosureDisposition(req.terminal_disposition)
        policy = _closure_drift_remediation_policy(disposition)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("closure drift remediation policy rejected", "closure_drift_remediation_policy_rejected"),
        ) from exc
    evidence_by_ref = _case_evidence_by_ref(kernel, case_id)
    approval_refs = _case_approval_refs(kernel, case_id)
    readiness = _closure_drift_action_readiness(
        disposition=disposition,
        evidence_by_ref=evidence_by_ref,
        approval_refs=approval_refs,
        evidence_refs=req.evidence_refs,
        authority_ref=req.authority_ref,
    )
    runbook_binding = _closure_drift_runbook_binding_projection(disposition)
    if isinstance(runbook_binding, dict) and runbook_binding.get("binding_valid") is not True:
        detail = _error_detail(
            "closure drift remediation runbook binding invalid",
            "closure_drift_runbook_binding_invalid",
        )
        detail["validation_errors"] = runbook_binding.get("validation_errors", [])
        raise HTTPException(400, detail=detail)
    if not readiness["ready"]:
        detail = _error_detail(
            "closure drift remediation policy unmet",
            "closure_drift_remediation_policy_unmet",
        )
        detail["missing_evidence_types"] = readiness["missing_evidence_types"]
        detail["missing_authority_refs"] = readiness["missing_authority_refs"]
        raise HTTPException(400, detail=detail)
    remediation_id = req.remediation_id or stable_identifier(
        "closure-drift-remediation",
        {
            "case_id": case_id,
            "closure_id": req.closure_id,
            "terminal_disposition": disposition.value,
            "action_id": req.action_id,
        },
    )
    metadata = {
        **req.metadata,
        "operator_action_id": req.action_id,
        "policy_action_kind": policy["action_kind"],
        "policy_required_evidence_types": list(policy["required_evidence_types"]),
    }
    if runbook_binding is not None:
        metadata["runbook_binding"] = runbook_binding
    try:
        binding = kernel.bind_closure_drift_remediation(
            ClosureDriftRemediationBinding(
                remediation_id=remediation_id,
                case_id=case_id,
                closure_id=req.closure_id,
                terminal_disposition=disposition,
                drift_evidence_refs=tuple(closure_gate_evidence["closure_packet_drift_refs"]),
                superseded_evidence_refs=tuple(closure_gate_evidence["superseded_closure_evidence_refs"]),
                authority_ref=req.authority_ref,
                evidence_refs=tuple(req.evidence_refs),
                created_at=_clock_now(),
                metadata=metadata,
            )
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            400,
            detail=_error_detail("closure drift remediation action rejected", "closure_drift_remediation_action_rejected"),
        ) from exc
    _persist_kernel(kernel)
    return {
        "action": {
            "action_id": req.action_id,
            "terminal_disposition": disposition.value,
            "policy": readiness,
            "runbook_binding": runbook_binding,
        },
        "closure_drift_remediation": _body(binding),
        "governed": True,
    }


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
