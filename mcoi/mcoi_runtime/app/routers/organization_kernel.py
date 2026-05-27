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

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.organization_kernel import (
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


@router.post("/api/v1/orgs")
def create_organization(req: OrganizationCreateRequest):
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
def bootstrap_minimum_org(org_id: str, req: OrganizationBootstrapRequest):
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
