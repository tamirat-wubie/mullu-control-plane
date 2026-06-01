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
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.musia_auth import require_admin

from scripts.collect_deployment_witness import (
    DeploymentWitness,
    collect_deployment_witness,
)

from mcoi_runtime.app.routers.deps import deps
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
def create_department(req: DepartmentCreateRequest):
    """Register a governed department pack."""
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def list_organization_departments(org_id: str):
    """List departments for one organization."""
    _inc_metric("requests_governed")
    departments = [
        department for department in _kernel().list_departments()
        if department.org_id == org_id
    ]
    return {
        "departments": [_body(department) for department in departments],
        "count": len(departments),
        "governed": True,
    }


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
):
    """Collect deployment witness evidence and bind verified engineering proof."""
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def get_launch_gateway_pilot_gate_preview(case_id: str):
    """Return non-mutating plan-step gate previews for the Launch Gateway Pilot case."""
    _inc_metric("requests_governed")
    previews = _launch_gateway_gate_preview(_kernel(), case_id)
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
def get_launch_gateway_pilot_readiness(case_id: str):
    """Return non-mutating readiness state for the Launch Gateway Pilot case."""
    _inc_metric("requests_governed")
    return _launch_gateway_readiness_model(_kernel(), case_id)


@router.post("/api/v1/cases/{case_id}/launch-gateway-pilot/readiness-closure")
def close_launch_gateway_pilot_readiness(
    case_id: str,
    req: LaunchGatewayPilotReadinessClosureRequest,
):
    """Bind a five-department readiness packet and close only after all gates pass."""
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def get_case(case_id: str):
    """Return a case read model with plan, proof, and event surfaces."""
    _inc_metric("requests_governed")
    return _state_case_bundle(_kernel(), case_id)


@router.get("/api/v1/cases/{case_id}/proof-timeline")
def get_case_proof_timeline(case_id: str):
    """Return a non-mutating proof timeline and closure certificate read model."""
    _inc_metric("requests_governed")
    return _case_proof_timeline(_kernel(), case_id)


@router.post("/api/v1/cases/{case_id}/plan")
def create_case_plan(case_id: str, req: OrganizationPlanCreateRequest):
    """Create a governed plan DAG for a case."""
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def admit_case_evidence(case_id: str, req: EvidenceAdmitRequest):
    """Admit evidence against a case requirement."""
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def record_case_approval(case_id: str, req: ApprovalRecordRequest):
    """Record an explicit case approval receipt."""
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def evaluate_case_plan_step(case_id: str, step_id: str, req: PlanStepGateRequest):
    """Evaluate one plan step gate with checked preconditions."""
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def bind_plan_step_worker_receipt(case_id: str, step_id: str, req: WorkerReceiptBindRequest):
    """Admit a bounded worker dispatch receipt as evidence for a plan step.

    The receipt is produced by the governed worker mesh under its own lease and
    budget controls; this endpoint only admits it as case evidence and never
    grants dispatch authority or terminal closure.
    """
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def close_case(case_id: str, req: OrganizationCaseCloseRequest):
    """Close a case through explicit effect reconciliation and disposition."""
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def bind_case_learning_admission(case_id: str, req: LearningAdmissionRequest):
    """Bind a closure-derived learning admission decision to the case."""
    _inc_metric("requests_governed")
    kernel = _kernel()
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
def list_case_events(case_id: str):
    """List kernel-emitted case events."""
    _inc_metric("requests_governed")
    kernel = _kernel()
    _case_or_404(kernel, case_id)
    events = kernel.list_case_events(case_id)
    return {
        "events": [_body(event) for event in events],
        "count": len(events),
        "governed": True,
    }
