"""Purpose: governed organization kernel v0 runtime.
Governance scope: organization, department, authority, case, plan, evidence,
approval, reconciliation, terminal closure, and learning-admission binding.
Dependencies: organization kernel contracts and runtime invariant helpers.
Invariants:
  - Cases cannot open without organization, department, assigned departments, and owner role.
  - Plan steps cannot be admitted without checked preconditions, authority, capability certification, evidence, and approvals.
  - Case terminal closure requires all plan steps admitted plus effect reconciliation evidence and certificate evidence.
  - Learning admission can only bind after terminal closure exists and admission evidence is admitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

from mcoi_runtime.contracts.effect_assurance import ReconciliationStatus
from mcoi_runtime.contracts.organization_kernel import (
    ApprovalRecord,
    AuthorityRule,
    CapabilityBinding,
    CapabilityMaturity,
    CaseEvidence,
    ClosureDriftRemediationBinding,
    DepartmentPack,
    EvidenceRequirement,
    LearningAdmissionBinding,
    OrganizationCase,
    OrganizationCaseEvent,
    OrganizationCaseStatus,
    OrganizationEffectReconciliation,
    OrganizationPlan,
    OrganizationProfile,
    OrganizationRisk,
    OrganizationRole,
    OrganizationTerminalClosure,
    PlanStep,
    PlanStepGateDecision,
    PlanStepGatePreview,
    PlanStepGateStatus,
    PlanStepWorkerDispatchReceipt,
    PlanStepWorkerLeaseReceipt,
    PlanStepWorkerReceiptBinding,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from .request_tenant_guard import assert_owns


LAUNCH_GATEWAY_PILOT_CASE_TYPE = "launch_gateway_pilot"
TERMINAL_CLOSURE_CERTIFICATE_REQUIREMENT = "terminal_closure_certificate"
LEARNING_ADMISSION_DECISION_REQUIREMENT = "learning_admission_decision"
DEFAULT_ORGANIZATION_DEPARTMENT_IDS = (
    "executive",
    "product",
    "engineering",
    "security_compliance",
    "finance",
)

_RISK_RANK: dict[OrganizationRisk, int] = {
    OrganizationRisk.LOW: 0,
    OrganizationRisk.MEDIUM: 1,
    OrganizationRisk.HIGH: 2,
    OrganizationRisk.CRITICAL: 3,
}

_NON_COMMITTED_TERMINAL_DISPOSITIONS = frozenset(
    {
        TerminalClosureDisposition.COMPENSATED,
        TerminalClosureDisposition.ACCEPTED_RISK,
        TerminalClosureDisposition.REQUIRES_REVIEW,
    }
)


@dataclass(frozen=True, slots=True)
class LatestPlanStepGateDecisionRef:
    """Reference that preserves the latest gate decision per case step."""

    case_id: str
    step_id: str
    decision_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", ensure_non_empty_text("case_id", self.case_id))
        object.__setattr__(self, "step_id", ensure_non_empty_text("step_id", self.step_id))
        object.__setattr__(self, "decision_id", ensure_non_empty_text("decision_id", self.decision_id))


@dataclass(frozen=True, slots=True)
class _PlanStepGateAssessment:
    """Pure assessment result shared by mutating gate decisions and dry-run previews."""

    status: PlanStepGateStatus
    reason: str
    authority_rule_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    approval_refs: tuple[str, ...]
    missing_preconditions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OrganizationKernelState:
    """Exact serializable state witness for OrganizationKernel persistence."""

    organizations: tuple[OrganizationProfile, ...] = ()
    departments: tuple[DepartmentPack, ...] = ()
    roles: tuple[OrganizationRole, ...] = ()
    authority_rules: tuple[AuthorityRule, ...] = ()
    capabilities: tuple[CapabilityBinding, ...] = ()
    evidence_requirements: tuple[EvidenceRequirement, ...] = ()
    cases: tuple[OrganizationCase, ...] = ()
    plans: tuple[OrganizationPlan, ...] = ()
    case_evidence: tuple[CaseEvidence, ...] = ()
    approvals: tuple[ApprovalRecord, ...] = ()
    gate_decisions: tuple[PlanStepGateDecision, ...] = ()
    latest_gate_decisions: tuple[LatestPlanStepGateDecisionRef, ...] = ()
    reconciliations: tuple[OrganizationEffectReconciliation, ...] = ()
    closures: tuple[OrganizationTerminalClosure, ...] = ()
    closure_drift_remediations: tuple[ClosureDriftRemediationBinding, ...] = ()
    learning_bindings: tuple[LearningAdmissionBinding, ...] = ()
    worker_lease_receipts: tuple[PlanStepWorkerLeaseReceipt, ...] = ()
    worker_dispatch_receipts: tuple[PlanStepWorkerDispatchReceipt, ...] = ()
    worker_receipt_bindings: tuple[PlanStepWorkerReceiptBinding, ...] = ()
    events: tuple[OrganizationCaseEvent, ...] = ()
    event_sequence: int = 0

    def __post_init__(self) -> None:
        for field_name in (
            "organizations",
            "departments",
            "roles",
            "authority_rules",
            "capabilities",
            "evidence_requirements",
            "cases",
            "plans",
            "case_evidence",
            "approvals",
            "gate_decisions",
            "latest_gate_decisions",
            "reconciliations",
            "closures",
            "closure_drift_remediations",
            "learning_bindings",
            "worker_lease_receipts",
            "worker_dispatch_receipts",
            "worker_receipt_bindings",
            "events",
        ):
            value = getattr(self, field_name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise ValueError(f"{field_name} must be a tuple")
        if not isinstance(self.event_sequence, int) or self.event_sequence < len(self.events):
            raise ValueError("event_sequence must cover emitted events")


def _risk_allows(max_risk: OrganizationRisk, requested_risk: OrganizationRisk) -> bool:
    return _RISK_RANK[requested_risk] <= _RISK_RANK[max_risk]


def _timestamp_expired(expires_at: str | None, now: str) -> bool:
    if expires_at is None:
        return False
    expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    return current >= expiry


class OrganizationKernel:
    """Small governed organization kernel for durable cases and closure proof."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._organizations: dict[str, OrganizationProfile] = {}
        self._departments: dict[str, DepartmentPack] = {}
        self._roles: dict[str, OrganizationRole] = {}
        self._authority_rules: dict[str, AuthorityRule] = {}
        self._capabilities: dict[str, CapabilityBinding] = {}
        self._evidence_requirements: dict[str, EvidenceRequirement] = {}
        self._cases: dict[str, OrganizationCase] = {}
        self._plans: dict[str, OrganizationPlan] = {}
        self._plan_by_case: dict[str, str] = {}
        self._case_evidence: dict[str, CaseEvidence] = {}
        self._approvals: dict[str, ApprovalRecord] = {}
        self._gate_decisions: dict[str, PlanStepGateDecision] = {}
        self._latest_gate_by_step: dict[tuple[str, str], str] = {}
        self._reconciliations: dict[str, OrganizationEffectReconciliation] = {}
        self._closures: dict[str, OrganizationTerminalClosure] = {}
        self._closure_drift_remediations: dict[str, ClosureDriftRemediationBinding] = {}
        self._learning_bindings: dict[str, LearningAdmissionBinding] = {}
        self._worker_lease_receipts: dict[str, PlanStepWorkerLeaseReceipt] = {}
        self._worker_dispatch_receipts: dict[str, PlanStepWorkerDispatchReceipt] = {}
        self._worker_receipt_bindings: dict[str, PlanStepWorkerReceiptBinding] = {}
        self._events: list[OrganizationCaseEvent] = []
        self._event_sequence = 0

    @property
    def organization_count(self) -> int:
        return len(self._organizations)

    def organization_tenant(self, org_id: str) -> str | None:
        """Return the tenant that owns an organization, or None if unknown."""
        organization = self._organizations.get(org_id)
        return organization.tenant_id if organization is not None else None

    @property
    def department_count(self) -> int:
        return len(self._departments)

    @property
    def case_count(self) -> int:
        return len(self._cases)

    @property
    def closure_count(self) -> int:
        return len(self._closures)

    def register_organization(self, organization: OrganizationProfile) -> OrganizationProfile:
        if organization.org_id in self._organizations:
            raise RuntimeCoreInvariantError("organization already registered")
        self._organizations[organization.org_id] = organization
        return organization

    def register_department(self, department: DepartmentPack) -> DepartmentPack:
        if department.department_id in self._departments:
            raise RuntimeCoreInvariantError("department already registered")
        if department.org_id not in self._organizations:
            raise RuntimeCoreInvariantError("department organization unavailable")
        self._departments[department.department_id] = department
        return department

    def register_role(self, role: OrganizationRole) -> OrganizationRole:
        if role.role_id in self._roles:
            raise RuntimeCoreInvariantError("role already registered")
        if role.org_id not in self._organizations:
            raise RuntimeCoreInvariantError("role organization unavailable")
        department = self._departments.get(role.department_id)
        if department is None or department.org_id != role.org_id:
            raise RuntimeCoreInvariantError("role department unavailable")
        self._roles[role.role_id] = role
        return role

    def register_authority_rule(self, rule: AuthorityRule) -> AuthorityRule:
        if rule.rule_id in self._authority_rules:
            raise RuntimeCoreInvariantError("authority rule already registered")
        role = self._roles.get(rule.role_id)
        if role is None:
            raise RuntimeCoreInvariantError("authority role unavailable")
        if role.department_id != rule.department_id or role.org_id != rule.org_id:
            raise RuntimeCoreInvariantError("authority rule role binding mismatch")
        self._authority_rules[rule.rule_id] = rule
        return rule

    def register_capability(self, capability: CapabilityBinding) -> CapabilityBinding:
        if capability.capability_id in self._capabilities:
            raise RuntimeCoreInvariantError("capability already registered")
        department = self._departments.get(capability.department_id)
        if department is None or department.org_id != capability.org_id:
            raise RuntimeCoreInvariantError("capability department unavailable")
        if capability.capability_id not in department.allowed_capabilities:
            raise RuntimeCoreInvariantError("capability outside department mandate")
        self._capabilities[capability.capability_id] = capability
        return capability

    def register_evidence_requirement(self, requirement: EvidenceRequirement) -> EvidenceRequirement:
        if requirement.requirement_id in self._evidence_requirements:
            raise RuntimeCoreInvariantError("evidence requirement already registered")
        department = self._departments.get(requirement.department_id)
        if department is None or department.org_id != requirement.org_id:
            raise RuntimeCoreInvariantError("evidence requirement department unavailable")
        if requirement.requirement_id not in department.required_evidence:
            raise RuntimeCoreInvariantError("evidence requirement outside department mandate")
        self._evidence_requirements[requirement.requirement_id] = requirement
        return requirement

    def open_case(self, organization_case: OrganizationCase) -> OrganizationCase:
        if organization_case.case_id in self._cases:
            raise RuntimeCoreInvariantError("case already opened")
        if organization_case.org_id not in self._organizations:
            raise RuntimeCoreInvariantError("case organization unavailable")
        department = self._departments.get(organization_case.department_id)
        if department is None or department.org_id != organization_case.org_id:
            raise RuntimeCoreInvariantError("case department unavailable")
        if organization_case.case_type not in department.allowed_case_types:
            raise RuntimeCoreInvariantError("case type outside department mandate")
        owner = self._roles.get(organization_case.owner_role_id)
        if owner is None or owner.org_id != organization_case.org_id:
            raise RuntimeCoreInvariantError("case owner role unavailable")
        for department_id in organization_case.assigned_department_ids:
            assigned_department = self._departments.get(department_id)
            if assigned_department is None or assigned_department.org_id != organization_case.org_id:
                raise RuntimeCoreInvariantError("assigned department unavailable")
            if organization_case.case_type not in assigned_department.allowed_case_types:
                raise RuntimeCoreInvariantError("assigned department cannot handle case type")
        self._cases[organization_case.case_id] = organization_case
        self._emit(organization_case.case_id, "case_opened", {"case_type": organization_case.case_type})
        return organization_case

    def create_plan(self, plan: OrganizationPlan) -> OrganizationPlan:
        if plan.plan_id in self._plans:
            raise RuntimeCoreInvariantError("plan already registered")
        organization_case = self._require_case(plan.case_id)
        if organization_case.status is OrganizationCaseStatus.CLOSED:
            raise RuntimeCoreInvariantError("closed case cannot receive plan")
        for step in plan.steps:
            self._validate_plan_step(organization_case, step)
        self._plans[plan.plan_id] = plan
        self._plan_by_case[plan.case_id] = plan.plan_id
        self._cases[plan.case_id] = OrganizationCase(
            case_id=organization_case.case_id,
            org_id=organization_case.org_id,
            department_id=organization_case.department_id,
            case_type=organization_case.case_type,
            goal=organization_case.goal,
            risk=organization_case.risk,
            owner_role_id=organization_case.owner_role_id,
            status=OrganizationCaseStatus.PLANNED,
            assigned_department_ids=organization_case.assigned_department_ids,
            created_at=organization_case.created_at,
            plan_id=plan.plan_id,
            terminal_closure_id=organization_case.terminal_closure_id,
            metadata=organization_case.metadata,
        )
        self._emit(plan.case_id, "case_planned", {"plan_id": plan.plan_id})
        return plan

    def admit_case_evidence(self, evidence: CaseEvidence) -> CaseEvidence:
        if evidence.evidence_ref in self._case_evidence:
            raise RuntimeCoreInvariantError("case evidence already admitted")
        organization_case = self._require_case(evidence.case_id)
        requirement = self._evidence_requirements.get(evidence.requirement_id)
        if requirement is None:
            raise RuntimeCoreInvariantError("evidence requirement unavailable")
        if requirement.org_id != organization_case.org_id or requirement.case_type != organization_case.case_type:
            raise RuntimeCoreInvariantError("evidence requirement case mismatch")
        if requirement.department_id not in organization_case.assigned_department_ids:
            raise RuntimeCoreInvariantError("evidence requirement department not assigned")
        self._case_evidence[evidence.evidence_ref] = evidence
        self._emit(evidence.case_id, "case_evidence_admitted", {"requirement_id": evidence.requirement_id})
        return evidence

    def record_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        if approval.approval_id in self._approvals:
            raise RuntimeCoreInvariantError("approval already recorded")
        organization_case = self._require_case(approval.case_id)
        role = self._roles.get(approval.role_id)
        if role is None or role.org_id != organization_case.org_id:
            raise RuntimeCoreInvariantError("approval role unavailable")
        if role.department_id not in organization_case.assigned_department_ids:
            raise RuntimeCoreInvariantError("approval role department not assigned")
        self._approvals[approval.approval_id] = approval
        self._emit(approval.case_id, "approval_recorded", {"approval_scope": approval.approval_scope})
        return approval

    def evaluate_plan_step(
        self,
        *,
        case_id: str,
        step_id: str,
        checked_preconditions: tuple[str, ...],
    ) -> PlanStepGateDecision:
        organization_case = self._require_case(case_id)
        plan = self._require_case_plan(case_id)
        step = self._require_plan_step(plan, step_id)
        assessment = self._assess_plan_step_gate(organization_case, step, checked_preconditions)
        return self._store_gate_decision(
            organization_case,
            step,
            assessment.status,
            assessment.reason,
            assessment.authority_rule_ids,
            assessment.evidence_refs,
            assessment.approval_refs,
        )

    def preview_plan_step(
        self,
        *,
        case_id: str,
        step_id: str,
        checked_preconditions: tuple[str, ...],
    ) -> PlanStepGatePreview:
        organization_case = self._require_case(case_id)
        plan = self._require_case_plan(case_id)
        step = self._require_plan_step(plan, step_id)
        normalized_preconditions = tuple(checked_preconditions)
        assessment = self._assess_plan_step_gate(organization_case, step, normalized_preconditions)
        previewed_at = self._clock()
        return PlanStepGatePreview(
            preview_id=stable_identifier(
                "org-step-gate-preview",
                {
                    "case_id": organization_case.case_id,
                    "step_id": step.step_id,
                    "status": assessment.status.value,
                    "reason": assessment.reason,
                    "checked_preconditions": list(normalized_preconditions),
                    "authority_rule_ids": list(assessment.authority_rule_ids),
                    "evidence_refs": list(assessment.evidence_refs),
                    "approval_refs": list(assessment.approval_refs),
                    "previewed_at": previewed_at,
                },
            ),
            case_id=organization_case.case_id,
            step_id=step.step_id,
            status=assessment.status,
            reason=assessment.reason,
            checked_preconditions=normalized_preconditions,
            missing_preconditions=assessment.missing_preconditions,
            authority_rule_ids=assessment.authority_rule_ids,
            evidence_refs=assessment.evidence_refs,
            approval_refs=assessment.approval_refs,
            previewed_at=previewed_at,
            metadata={"mutates_state": False},
        )

    def close_case(
        self,
        *,
        reconciliation: OrganizationEffectReconciliation,
        terminal_disposition: TerminalClosureDisposition,
        terminal_certificate_id: str,
        learning_admission_id: str | None = None,
    ) -> OrganizationTerminalClosure:
        organization_case = self._require_case(reconciliation.case_id)
        if organization_case.terminal_closure_id is not None:
            raise RuntimeCoreInvariantError("case already has terminal closure")
        if not isinstance(terminal_disposition, TerminalClosureDisposition):
            raise RuntimeCoreInvariantError("terminal disposition unavailable")
        self._require_case_plan(organization_case.case_id)
        if not self._all_plan_steps_allowed(organization_case.case_id):
            raise RuntimeCoreInvariantError("case closure requires allowed plan step gates")
        certificate_id = ensure_non_empty_text("terminal_certificate_id", terminal_certificate_id)
        self._validate_closure_gate_evidence(organization_case.case_id, reconciliation.evidence_refs)
        self._validate_terminal_certificate_evidence(
            organization_case.case_id,
            certificate_id,
            reconciliation.evidence_refs,
        )
        self._validate_terminal_reconciliation(reconciliation, terminal_disposition)
        self._reconciliations[reconciliation.reconciliation_id] = reconciliation
        closed_at = self._clock()
        closure_id = stable_identifier(
            "org-terminal-closure",
            {
                "case_id": organization_case.case_id,
                "reconciliation_id": reconciliation.reconciliation_id,
                "terminal_disposition": terminal_disposition.value,
                "closed_at": closed_at,
            },
        )
        closure = OrganizationTerminalClosure(
            closure_id=closure_id,
            case_id=organization_case.case_id,
            reconciliation_id=reconciliation.reconciliation_id,
            terminal_certificate_id=certificate_id,
            terminal_disposition=terminal_disposition,
            evidence_refs=reconciliation.evidence_refs,
            closed_at=closed_at,
            learning_admission_id=learning_admission_id,
        )
        self._closures[closure.closure_id] = closure
        status = OrganizationCaseStatus.CLOSED
        if terminal_disposition is TerminalClosureDisposition.REQUIRES_REVIEW:
            status = OrganizationCaseStatus.REQUIRES_REVIEW
        self._cases[organization_case.case_id] = OrganizationCase(
            case_id=organization_case.case_id,
            org_id=organization_case.org_id,
            department_id=organization_case.department_id,
            case_type=organization_case.case_type,
            goal=organization_case.goal,
            risk=organization_case.risk,
            owner_role_id=organization_case.owner_role_id,
            status=status,
            assigned_department_ids=organization_case.assigned_department_ids,
            created_at=organization_case.created_at,
            plan_id=organization_case.plan_id,
            terminal_closure_id=closure.closure_id,
            metadata=organization_case.metadata,
        )
        self._emit(organization_case.case_id, "case_terminal_closure_recorded", {"closure_id": closure.closure_id})
        return closure

    def bind_learning_admission(self, binding: LearningAdmissionBinding) -> LearningAdmissionBinding:
        if binding.binding_id in self._learning_bindings:
            raise RuntimeCoreInvariantError("learning binding already recorded")
        closure = self._closures.get(binding.closure_id)
        if closure is None:
            raise RuntimeCoreInvariantError("terminal closure unavailable")
        if closure.case_id != binding.case_id:
            raise RuntimeCoreInvariantError("learning binding case mismatch")
        self._validate_learning_admission_evidence(binding.case_id, binding.evidence_refs)
        self._learning_bindings[binding.binding_id] = binding
        self._emit(binding.case_id, "learning_admission_bound", {"binding_id": binding.binding_id})
        return binding

    def bind_closure_drift_remediation(
        self,
        binding: ClosureDriftRemediationBinding,
    ) -> ClosureDriftRemediationBinding:
        """Bind review, compensation, or accepted-risk routing to a drifted closure."""
        if binding.remediation_id in self._closure_drift_remediations:
            raise RuntimeCoreInvariantError("closure drift remediation already recorded")
        closure = self._closures.get(binding.closure_id)
        if closure is None:
            raise RuntimeCoreInvariantError("terminal closure unavailable")
        if closure.case_id != binding.case_id:
            raise RuntimeCoreInvariantError("closure drift remediation case mismatch")
        if binding.terminal_disposition not in _NON_COMMITTED_TERMINAL_DISPOSITIONS:
            raise RuntimeCoreInvariantError("closure drift remediation requires non-committed disposition")
        self._validate_closure_drift_authority(binding.case_id, binding.authority_ref)
        self._validate_closure_drift_superseded_evidence(
            binding.case_id,
            closure.evidence_refs,
            binding.superseded_evidence_refs,
        )
        for evidence_ref in (*binding.drift_evidence_refs, *binding.evidence_refs):
            evidence = self._case_evidence.get(evidence_ref)
            if evidence is None or evidence.case_id != binding.case_id:
                raise RuntimeCoreInvariantError("closure drift remediation evidence unavailable")
        self._closure_drift_remediations[binding.remediation_id] = binding
        self._emit(
            binding.case_id,
            "closure_drift_remediation_bound",
            {
                "remediation_id": binding.remediation_id,
                "closure_id": binding.closure_id,
                "terminal_disposition": binding.terminal_disposition.value,
            },
        )
        return binding

    def create_worker_lease_receipt(
        self,
        receipt: PlanStepWorkerLeaseReceipt,
    ) -> PlanStepWorkerLeaseReceipt:
        """Record a bounded worker lease envelope without dispatching work."""
        if receipt.lease_id in self._worker_lease_receipts:
            raise RuntimeCoreInvariantError("worker lease already recorded")
        organization_case = self._require_case(receipt.case_id)
        if organization_case.status is OrganizationCaseStatus.CLOSED:
            raise RuntimeCoreInvariantError("closed case cannot receive worker lease")
        plan = self._require_case_plan(receipt.case_id)
        step = self._require_plan_step(plan, receipt.step_id)
        if receipt.capability_id != step.capability_id:
            raise RuntimeCoreInvariantError("worker lease capability mismatch")
        if receipt.responsible_role_id != step.responsible_role_id:
            raise RuntimeCoreInvariantError("worker lease responsible role mismatch")
        if receipt.capability_action != step.action:
            raise RuntimeCoreInvariantError("worker lease action mismatch")
        role = self._roles.get(receipt.requested_by_role_id)
        if role is None or role.org_id != organization_case.org_id:
            raise RuntimeCoreInvariantError("worker lease requesting role unavailable")
        if role.role_id != step.responsible_role_id:
            raise RuntimeCoreInvariantError("worker lease must be requested by responsible role")
        for evidence_ref in receipt.evidence_refs:
            evidence = self._case_evidence.get(evidence_ref)
            if evidence is None or evidence.case_id != receipt.case_id:
                raise RuntimeCoreInvariantError("worker lease evidence unavailable")
        self._worker_lease_receipts[receipt.lease_id] = receipt
        self._emit(
            receipt.case_id,
            "plan_step_worker_lease_created",
            {
                "lease_id": receipt.lease_id,
                "step_id": receipt.step_id,
                "capability_id": receipt.capability_id,
                "dispatch_lease_preview_id": receipt.dispatch_lease_preview_id,
            },
        )
        return receipt

    def record_worker_dispatch_receipt(
        self,
        receipt: PlanStepWorkerDispatchReceipt,
    ) -> PlanStepWorkerDispatchReceipt:
        """Record a bounded dispatch request envelope without executing a worker."""
        if receipt.dispatch_receipt_id in self._worker_dispatch_receipts:
            raise RuntimeCoreInvariantError("worker dispatch receipt already recorded")
        if any(
            existing.dispatch_request_id == receipt.dispatch_request_id
            for existing in self._worker_dispatch_receipts.values()
        ):
            raise RuntimeCoreInvariantError("worker dispatch request already recorded")
        if any(
            existing.worker_lease_id == receipt.worker_lease_id
            for existing in self._worker_dispatch_receipts.values()
        ):
            raise RuntimeCoreInvariantError("worker lease already has dispatch receipt")

        lease_receipt = self._worker_lease_receipts.get(receipt.worker_lease_id)
        if lease_receipt is None:
            raise RuntimeCoreInvariantError("worker dispatch receipt lease unavailable")
        organization_case = self._require_case(receipt.case_id)
        if organization_case.status is OrganizationCaseStatus.CLOSED:
            raise RuntimeCoreInvariantError("closed case cannot receive worker dispatch receipt")
        plan = self._require_case_plan(receipt.case_id)
        step = self._require_plan_step(plan, receipt.step_id)
        if receipt.case_id != lease_receipt.case_id:
            raise RuntimeCoreInvariantError("worker dispatch receipt case mismatch")
        if receipt.step_id != lease_receipt.step_id:
            raise RuntimeCoreInvariantError("worker dispatch receipt step mismatch")
        if receipt.capability_id != lease_receipt.capability_id or receipt.capability_id != step.capability_id:
            raise RuntimeCoreInvariantError("worker dispatch receipt capability mismatch")
        if (
            receipt.responsible_role_id != lease_receipt.responsible_role_id
            or receipt.responsible_role_id != step.responsible_role_id
        ):
            raise RuntimeCoreInvariantError("worker dispatch receipt responsible role mismatch")
        if receipt.requested_by_role_id != lease_receipt.requested_by_role_id:
            raise RuntimeCoreInvariantError("worker dispatch receipt requester mismatch")
        if receipt.expected_effect != lease_receipt.expected_effect:
            raise RuntimeCoreInvariantError("worker dispatch receipt expected effect mismatch")
        if receipt.evidence_refs != lease_receipt.evidence_refs:
            raise RuntimeCoreInvariantError("worker dispatch receipt evidence mismatch")
        if receipt.lease_created_at != lease_receipt.created_at:
            raise RuntimeCoreInvariantError("worker dispatch receipt lease timestamp mismatch")

        role = self._roles.get(receipt.requested_by_role_id)
        if role is None or role.org_id != organization_case.org_id or role.role_id != step.responsible_role_id:
            raise RuntimeCoreInvariantError("worker dispatch receipt requesting role mismatch")
        for evidence_ref in receipt.evidence_refs:
            evidence = self._case_evidence.get(evidence_ref)
            if evidence is None or evidence.case_id != receipt.case_id:
                raise RuntimeCoreInvariantError("worker dispatch receipt evidence unavailable")

        self._worker_dispatch_receipts[receipt.dispatch_receipt_id] = receipt
        self._emit(
            receipt.case_id,
            "plan_step_worker_dispatch_recorded",
            {
                "dispatch_receipt_id": receipt.dispatch_receipt_id,
                "dispatch_request_id": receipt.dispatch_request_id,
                "worker_lease_id": receipt.worker_lease_id,
                "step_id": receipt.step_id,
                "capability_id": receipt.capability_id,
                "worker_id": receipt.worker_id,
            },
        )
        return receipt

    def bind_worker_receipt_evidence(
        self,
        binding: PlanStepWorkerReceiptBinding,
    ) -> PlanStepWorkerReceiptBinding:
        """Admit a bounded worker dispatch receipt as plan-step case evidence.

        This consumes a receipt produced by the governed worker mesh; it does
        not dispatch work or grant dispatch authority. The receipt must carry
        its own evidence refs, must satisfy a requirement declared by the plan
        step, must reference a recorded dispatch receipt, and is never treated
        as a terminal closure.
        """
        if binding.binding_id in self._worker_receipt_bindings:
            raise RuntimeCoreInvariantError("worker receipt binding already admitted")
        plan = self._require_case_plan(binding.case_id)
        step = self._require_plan_step(plan, binding.step_id)
        if binding.requirement_id not in step.evidence_required:
            raise RuntimeCoreInvariantError("worker receipt requirement outside plan step evidence")
        if not binding.receipt_evidence_refs:
            raise RuntimeCoreInvariantError("worker receipt requires evidence refs")
        dispatch_receipt = self._worker_dispatch_receipts.get(binding.dispatch_receipt_id)
        if dispatch_receipt is None:
            raise RuntimeCoreInvariantError("worker receipt dispatch receipt unavailable")
        if dispatch_receipt.dispatch_request_id != binding.dispatch_request_id:
            raise RuntimeCoreInvariantError("worker receipt dispatch request mismatch")
        if dispatch_receipt.worker_lease_id != binding.worker_lease_id:
            raise RuntimeCoreInvariantError("worker receipt lease mismatch")
        if dispatch_receipt.case_id != binding.case_id:
            raise RuntimeCoreInvariantError("worker receipt case mismatch")
        if dispatch_receipt.step_id != binding.step_id:
            raise RuntimeCoreInvariantError("worker receipt step mismatch")
        evidence = self.admit_case_evidence(
            CaseEvidence(
                evidence_ref=binding.admitted_evidence_ref,
                case_id=binding.case_id,
                requirement_id=binding.requirement_id,
                submitted_by=f"worker_mesh:{binding.worker_lease_id}",
                submitted_at=binding.bound_at,
                metadata={
                    "source": "worker_dispatch_receipt",
                    "dispatch_request_id": binding.dispatch_request_id,
                    "dispatch_receipt_id": binding.dispatch_receipt_id,
                    "worker_output_hash": binding.worker_output_hash,
                    "receipt_evidence_refs": binding.receipt_evidence_refs,
                    "worker_dispatch_receipt_required": True,
                    "worker_receipt_is_terminal_closure": False,
                },
            )
        )
        self._worker_receipt_bindings[binding.binding_id] = binding
        self._emit(
            binding.case_id,
            "plan_step_worker_receipt_bound",
            {
                "step_id": binding.step_id,
                "requirement_id": binding.requirement_id,
                "dispatch_receipt_id": binding.dispatch_receipt_id,
                "evidence_ref": evidence.evidence_ref,
            },
        )
        return binding

    def get_case(self, case_id: str) -> OrganizationCase | None:
        ensure_non_empty_text("case_id", case_id)
        case = self._cases.get(case_id)
        if case is not None:
            # Defense-in-depth (see request_tenant_guard): an organization case
            # carries an org_id, not a tenant_id, so resolve the owning tenant
            # through the organization and refuse to hand the case to a different
            # tenant even if a caller forgot _enforce_case_tenant. No-op unless the
            # middleware bound a non-operator authenticated tenant for this request;
            # an unknown org resolves to no tenant and is left unguarded (matching
            # the router's ``if tenant_id`` resolution).
            tenant_id = self.organization_tenant(case.org_id)
            if tenant_id:
                assert_owns(tenant_id, resource="organization case")
        return case

    def get_plan(self, plan_id: str) -> OrganizationPlan | None:
        ensure_non_empty_text("plan_id", plan_id)
        return self._plans.get(plan_id)

    # --- O(1) by-id lookups ---
    #
    # Routers previously located these records with
    # ``next(item for item in snapshot_state().<collection> if item.<id> == x)``,
    # which rebuilds + sorts the ENTIRE kernel state on every call (O(total
    # state)) and then linearly scans the collection. The kernel already stores
    # everything in dicts (plus a _plan_by_case index), so these direct lookups
    # are O(1)/O(closures) and return the identical record object. Measured ~2400x
    # faster than snapshot_state()+scan at a few thousand records.

    def get_organization(self, org_id: str) -> OrganizationProfile | None:
        ensure_non_empty_text("org_id", org_id)
        return self._organizations.get(org_id)

    def get_role(self, role_id: str) -> OrganizationRole | None:
        ensure_non_empty_text("role_id", role_id)
        return self._roles.get(role_id)

    def plan_for_case(self, case_id: str) -> OrganizationPlan | None:
        ensure_non_empty_text("case_id", case_id)
        plan_id = self._plan_by_case.get(case_id)
        return self._plans.get(plan_id) if plan_id is not None else None

    def closure_for_case(self, case_id: str) -> OrganizationTerminalClosure | None:
        ensure_non_empty_text("case_id", case_id)
        # Closures are append-only and at most one per case (terminal); scanning
        # the (small) closures dict avoids the full snapshot_state() rebuild.
        for closure in self._closures.values():
            if closure.case_id == case_id:
                return closure
        return None

    def closure_drift_remediations_for_case(self, case_id: str) -> tuple[ClosureDriftRemediationBinding, ...]:
        ensure_non_empty_text("case_id", case_id)
        return tuple(
            item for item in self._closure_drift_remediations.values()
            if item.case_id == case_id
        )

    def list_departments(self) -> tuple[DepartmentPack, ...]:
        return tuple(self._departments[department_id] for department_id in sorted(self._departments))

    def list_case_events(self, case_id: str | None = None) -> tuple[OrganizationCaseEvent, ...]:
        if case_id is None:
            return tuple(self._events)
        ensure_non_empty_text("case_id", case_id)
        return tuple(event for event in self._events if event.case_id == case_id)

    def snapshot_state(self) -> OrganizationKernelState:
        """Return an exact state witness for deterministic persistence."""
        latest_gate_decisions = tuple(
            LatestPlanStepGateDecisionRef(
                case_id=case_id,
                step_id=step_id,
                decision_id=decision_id,
            )
            for (case_id, step_id), decision_id in sorted(self._latest_gate_by_step.items())
        )
        return OrganizationKernelState(
            organizations=tuple(self._organizations[key] for key in sorted(self._organizations)),
            departments=tuple(self._departments[key] for key in sorted(self._departments)),
            roles=tuple(self._roles[key] for key in sorted(self._roles)),
            authority_rules=tuple(self._authority_rules[key] for key in sorted(self._authority_rules)),
            capabilities=tuple(self._capabilities[key] for key in sorted(self._capabilities)),
            evidence_requirements=tuple(
                self._evidence_requirements[key] for key in sorted(self._evidence_requirements)
            ),
            cases=tuple(self._cases[key] for key in sorted(self._cases)),
            plans=tuple(self._plans[key] for key in sorted(self._plans)),
            case_evidence=tuple(self._case_evidence[key] for key in sorted(self._case_evidence)),
            approvals=tuple(self._approvals[key] for key in sorted(self._approvals)),
            gate_decisions=tuple(
                sorted(
                    self._gate_decisions.values(),
                    key=lambda decision: (decision.decided_at, decision.case_id, decision.step_id, decision.decision_id),
                )
            ),
            latest_gate_decisions=latest_gate_decisions,
            reconciliations=tuple(self._reconciliations[key] for key in sorted(self._reconciliations)),
            closures=tuple(self._closures[key] for key in sorted(self._closures)),
            closure_drift_remediations=tuple(
                self._closure_drift_remediations[key] for key in sorted(self._closure_drift_remediations)
            ),
            learning_bindings=tuple(self._learning_bindings[key] for key in sorted(self._learning_bindings)),
            worker_lease_receipts=tuple(
                self._worker_lease_receipts[key] for key in sorted(self._worker_lease_receipts)
            ),
            worker_dispatch_receipts=tuple(
                self._worker_dispatch_receipts[key] for key in sorted(self._worker_dispatch_receipts)
            ),
            worker_receipt_bindings=tuple(
                self._worker_receipt_bindings[key] for key in sorted(self._worker_receipt_bindings)
            ),
            events=tuple(self._events),
            event_sequence=self._event_sequence,
        )

    def restore_state(self, state: OrganizationKernelState) -> OrganizationKernelState:
        """Restore an exact persisted state into an empty organization kernel."""
        if not isinstance(state, OrganizationKernelState):
            raise RuntimeCoreInvariantError("organization kernel state unavailable")
        if self._has_state():
            raise RuntimeCoreInvariantError("organization kernel restore requires empty kernel")

        candidate = OrganizationKernel(clock=self._clock)
        candidate._organizations = candidate._keyed(state.organizations, "org_id", "organization")
        candidate._departments = candidate._keyed(state.departments, "department_id", "department")
        candidate._roles = candidate._keyed(state.roles, "role_id", "role")
        candidate._authority_rules = candidate._keyed(state.authority_rules, "rule_id", "authority rule")
        candidate._capabilities = candidate._keyed(state.capabilities, "capability_id", "capability")
        candidate._evidence_requirements = candidate._keyed(
            state.evidence_requirements,
            "requirement_id",
            "evidence requirement",
        )
        candidate._cases = candidate._keyed(state.cases, "case_id", "case")
        candidate._plans = candidate._keyed(state.plans, "plan_id", "plan")
        candidate._plan_by_case = candidate._keyed_plan_cases(state.plans)
        candidate._case_evidence = candidate._keyed(state.case_evidence, "evidence_ref", "case evidence")
        candidate._approvals = candidate._keyed(state.approvals, "approval_id", "approval")
        candidate._gate_decisions = candidate._keyed(state.gate_decisions, "decision_id", "gate decision")
        candidate._latest_gate_by_step = candidate._latest_gate_index(state.latest_gate_decisions)
        candidate._reconciliations = candidate._keyed(
            state.reconciliations,
            "reconciliation_id",
            "reconciliation",
        )
        candidate._closures = candidate._keyed(state.closures, "closure_id", "terminal closure")
        candidate._closure_drift_remediations = candidate._keyed(
            state.closure_drift_remediations,
            "remediation_id",
            "closure drift remediation",
        )
        candidate._learning_bindings = candidate._keyed(state.learning_bindings, "binding_id", "learning binding")
        candidate._worker_lease_receipts = candidate._keyed(
            state.worker_lease_receipts,
            "lease_id",
            "worker lease receipt",
        )
        candidate._worker_dispatch_receipts = candidate._keyed(
            state.worker_dispatch_receipts,
            "dispatch_receipt_id",
            "worker dispatch receipt",
        )
        candidate._worker_receipt_bindings = candidate._keyed(
            state.worker_receipt_bindings,
            "binding_id",
            "worker receipt binding",
        )
        candidate._events = list(state.events)
        candidate._event_sequence = state.event_sequence
        candidate._validate_restored_state()

        self._organizations = candidate._organizations
        self._departments = candidate._departments
        self._roles = candidate._roles
        self._authority_rules = candidate._authority_rules
        self._capabilities = candidate._capabilities
        self._evidence_requirements = candidate._evidence_requirements
        self._cases = candidate._cases
        self._plans = candidate._plans
        self._plan_by_case = candidate._plan_by_case
        self._case_evidence = candidate._case_evidence
        self._approvals = candidate._approvals
        self._gate_decisions = candidate._gate_decisions
        self._latest_gate_by_step = candidate._latest_gate_by_step
        self._reconciliations = candidate._reconciliations
        self._closures = candidate._closures
        self._closure_drift_remediations = candidate._closure_drift_remediations
        self._learning_bindings = candidate._learning_bindings
        self._worker_lease_receipts = candidate._worker_lease_receipts
        self._worker_dispatch_receipts = candidate._worker_dispatch_receipts
        self._worker_receipt_bindings = candidate._worker_receipt_bindings
        self._events = candidate._events
        self._event_sequence = candidate._event_sequence
        return state

    def _has_state(self) -> bool:
        return any(
            (
                self._organizations,
                self._departments,
                self._roles,
                self._authority_rules,
                self._capabilities,
                self._evidence_requirements,
                self._cases,
                self._plans,
                self._case_evidence,
                self._approvals,
                self._gate_decisions,
                self._reconciliations,
                self._closures,
                self._closure_drift_remediations,
                self._learning_bindings,
                self._worker_lease_receipts,
                self._worker_dispatch_receipts,
                self._worker_receipt_bindings,
                self._events,
            )
        )

    @staticmethod
    def _keyed(items: tuple[object, ...], key_name: str, label: str) -> dict[str, object]:
        keyed: dict[str, object] = {}
        for item in items:
            key = getattr(item, key_name, None)
            if not isinstance(key, str) or not key.strip():
                raise RuntimeCoreInvariantError(f"{label} restore id unavailable")
            if key in keyed:
                raise RuntimeCoreInvariantError(f"{label} restore id collision")
            keyed[key] = item
        return keyed

    @staticmethod
    def _keyed_plan_cases(plans: tuple[OrganizationPlan, ...]) -> dict[str, str]:
        keyed: dict[str, str] = {}
        for plan in plans:
            existing = keyed.get(plan.case_id)
            if existing is not None and existing != plan.plan_id:
                raise RuntimeCoreInvariantError("case restore has multiple plans")
            keyed[plan.case_id] = plan.plan_id
        return keyed

    @staticmethod
    def _latest_gate_index(
        latest_gate_refs: tuple[LatestPlanStepGateDecisionRef, ...],
    ) -> dict[tuple[str, str], str]:
        keyed: dict[tuple[str, str], str] = {}
        for ref in latest_gate_refs:
            key = (ref.case_id, ref.step_id)
            if key in keyed:
                raise RuntimeCoreInvariantError("latest gate decision restore collision")
            keyed[key] = ref.decision_id
        return keyed

    def _validate_restored_state(self) -> None:
        for department in self._departments.values():
            if department.org_id not in self._organizations:
                raise RuntimeCoreInvariantError("restored department organization unavailable")
        for role in self._roles.values():
            department = self._departments.get(role.department_id)
            if department is None or department.org_id != role.org_id:
                raise RuntimeCoreInvariantError("restored role department unavailable")
        for rule in self._authority_rules.values():
            role = self._roles.get(rule.role_id)
            if role is None or role.org_id != rule.org_id or role.department_id != rule.department_id:
                raise RuntimeCoreInvariantError("restored authority rule role mismatch")
        for capability in self._capabilities.values():
            department = self._departments.get(capability.department_id)
            if department is None or department.org_id != capability.org_id:
                raise RuntimeCoreInvariantError("restored capability department unavailable")
            if capability.capability_id not in department.allowed_capabilities:
                raise RuntimeCoreInvariantError("restored capability outside department mandate")
        for requirement in self._evidence_requirements.values():
            department = self._departments.get(requirement.department_id)
            if department is None or department.org_id != requirement.org_id:
                raise RuntimeCoreInvariantError("restored evidence requirement department unavailable")
            if requirement.requirement_id not in department.required_evidence:
                raise RuntimeCoreInvariantError("restored evidence requirement outside mandate")
        for organization_case in self._cases.values():
            self._validate_restored_case(organization_case)
        for plan in self._plans.values():
            organization_case = self._cases.get(plan.case_id)
            if organization_case is None:
                raise RuntimeCoreInvariantError("restored plan case unavailable")
            for step in plan.steps:
                self._validate_plan_step(organization_case, step)
        for evidence in self._case_evidence.values():
            self._validate_restored_evidence(evidence)
        for approval in self._approvals.values():
            self._validate_restored_approval(approval)
        for decision in self._gate_decisions.values():
            self._validate_restored_gate_decision(decision)
        for (case_id, step_id), decision_id in self._latest_gate_by_step.items():
            decision = self._gate_decisions.get(decision_id)
            if decision is None or decision.case_id != case_id or decision.step_id != step_id:
                raise RuntimeCoreInvariantError("restored latest gate decision mismatch")
        for reconciliation in self._reconciliations.values():
            if reconciliation.case_id not in self._cases:
                raise RuntimeCoreInvariantError("restored reconciliation case unavailable")
        for closure in self._closures.values():
            organization_case = self._cases.get(closure.case_id)
            reconciliation = self._reconciliations.get(closure.reconciliation_id)
            if organization_case is None or reconciliation is None or reconciliation.case_id != closure.case_id:
                raise RuntimeCoreInvariantError("restored terminal closure binding mismatch")
            if organization_case.terminal_closure_id != closure.closure_id:
                raise RuntimeCoreInvariantError("restored case terminal closure mismatch")
        for organization_case in self._cases.values():
            if organization_case.terminal_closure_id is not None and organization_case.terminal_closure_id not in self._closures:
                raise RuntimeCoreInvariantError("restored case terminal closure unavailable")
        for remediation in self._closure_drift_remediations.values():
            closure = self._closures.get(remediation.closure_id)
            if closure is None or closure.case_id != remediation.case_id:
                raise RuntimeCoreInvariantError("restored closure drift remediation closure mismatch")
            self._validate_closure_drift_authority(remediation.case_id, remediation.authority_ref)
            self._validate_closure_drift_superseded_evidence(
                remediation.case_id,
                closure.evidence_refs,
                remediation.superseded_evidence_refs,
                error_prefix="restored ",
            )
            for evidence_ref in (*remediation.drift_evidence_refs, *remediation.evidence_refs):
                evidence = self._case_evidence.get(evidence_ref)
                if evidence is None or evidence.case_id != remediation.case_id:
                    raise RuntimeCoreInvariantError("restored closure drift remediation evidence unavailable")
        for binding in self._learning_bindings.values():
            closure = self._closures.get(binding.closure_id)
            if closure is None or closure.case_id != binding.case_id:
                raise RuntimeCoreInvariantError("restored learning binding closure mismatch")
            self._validate_learning_admission_evidence(binding.case_id, binding.evidence_refs)
        for lease_receipt in self._worker_lease_receipts.values():
            organization_case = self._cases.get(lease_receipt.case_id)
            plan_id = self._plan_by_case.get(lease_receipt.case_id)
            if organization_case is None or plan_id is None:
                raise RuntimeCoreInvariantError("restored worker lease case unavailable")
            step = next(
                (candidate for candidate in self._plans[plan_id].steps if candidate.step_id == lease_receipt.step_id),
                None,
            )
            if step is None:
                raise RuntimeCoreInvariantError("restored worker lease step unavailable")
            if lease_receipt.capability_id != step.capability_id:
                raise RuntimeCoreInvariantError("restored worker lease capability mismatch")
            if lease_receipt.responsible_role_id != step.responsible_role_id:
                raise RuntimeCoreInvariantError("restored worker lease role mismatch")
            if lease_receipt.capability_action != step.action:
                raise RuntimeCoreInvariantError("restored worker lease action mismatch")
            role = self._roles.get(lease_receipt.requested_by_role_id)
            if role is None or role.role_id != step.responsible_role_id or role.org_id != organization_case.org_id:
                raise RuntimeCoreInvariantError("restored worker lease requesting role mismatch")
            for evidence_ref in lease_receipt.evidence_refs:
                evidence = self._case_evidence.get(evidence_ref)
                if evidence is None or evidence.case_id != lease_receipt.case_id:
                    raise RuntimeCoreInvariantError("restored worker lease evidence unavailable")
        dispatch_request_ids: set[str] = set()
        dispatched_lease_ids: set[str] = set()
        for dispatch_receipt in self._worker_dispatch_receipts.values():
            lease_receipt = self._worker_lease_receipts.get(dispatch_receipt.worker_lease_id)
            if lease_receipt is None:
                raise RuntimeCoreInvariantError("restored worker dispatch lease unavailable")
            if dispatch_receipt.dispatch_request_id in dispatch_request_ids:
                raise RuntimeCoreInvariantError("restored worker dispatch request collision")
            dispatch_request_ids.add(dispatch_receipt.dispatch_request_id)
            if dispatch_receipt.worker_lease_id in dispatched_lease_ids:
                raise RuntimeCoreInvariantError("restored worker lease has multiple dispatch receipts")
            dispatched_lease_ids.add(dispatch_receipt.worker_lease_id)
            if dispatch_receipt.case_id != lease_receipt.case_id:
                raise RuntimeCoreInvariantError("restored worker dispatch case mismatch")
            if dispatch_receipt.step_id != lease_receipt.step_id:
                raise RuntimeCoreInvariantError("restored worker dispatch step mismatch")
            if dispatch_receipt.capability_id != lease_receipt.capability_id:
                raise RuntimeCoreInvariantError("restored worker dispatch capability mismatch")
            if dispatch_receipt.responsible_role_id != lease_receipt.responsible_role_id:
                raise RuntimeCoreInvariantError("restored worker dispatch role mismatch")
            if dispatch_receipt.requested_by_role_id != lease_receipt.requested_by_role_id:
                raise RuntimeCoreInvariantError("restored worker dispatch requester mismatch")
            if dispatch_receipt.expected_effect != lease_receipt.expected_effect:
                raise RuntimeCoreInvariantError("restored worker dispatch expected effect mismatch")
            if dispatch_receipt.evidence_refs != lease_receipt.evidence_refs:
                raise RuntimeCoreInvariantError("restored worker dispatch evidence mismatch")
            if dispatch_receipt.lease_created_at != lease_receipt.created_at:
                raise RuntimeCoreInvariantError("restored worker dispatch lease timestamp mismatch")
        for receipt_binding in self._worker_receipt_bindings.values():
            organization_case = self._cases.get(receipt_binding.case_id)
            plan_id = self._plan_by_case.get(receipt_binding.case_id)
            if organization_case is None or plan_id is None:
                raise RuntimeCoreInvariantError("restored worker receipt binding case unavailable")
            step = next(
                (candidate for candidate in self._plans[plan_id].steps if candidate.step_id == receipt_binding.step_id),
                None,
            )
            if step is None or receipt_binding.requirement_id not in step.evidence_required:
                raise RuntimeCoreInvariantError("restored worker receipt binding step mismatch")
            dispatch_receipt = self._worker_dispatch_receipts.get(receipt_binding.dispatch_receipt_id)
            if dispatch_receipt is None:
                raise RuntimeCoreInvariantError("restored worker receipt dispatch unavailable")
            if dispatch_receipt.dispatch_request_id != receipt_binding.dispatch_request_id:
                raise RuntimeCoreInvariantError("restored worker receipt dispatch request mismatch")
            if dispatch_receipt.worker_lease_id != receipt_binding.worker_lease_id:
                raise RuntimeCoreInvariantError("restored worker receipt lease mismatch")
            if dispatch_receipt.case_id != receipt_binding.case_id:
                raise RuntimeCoreInvariantError("restored worker receipt case mismatch")
            if dispatch_receipt.step_id != receipt_binding.step_id:
                raise RuntimeCoreInvariantError("restored worker receipt step mismatch")
            if receipt_binding.admitted_evidence_ref not in self._case_evidence:
                raise RuntimeCoreInvariantError("restored worker receipt evidence unavailable")
        if self._event_sequence < len(self._events):
            raise RuntimeCoreInvariantError("restored event sequence is behind event count")
        for event in self._events:
            if event.case_id not in self._cases:
                raise RuntimeCoreInvariantError("restored event case unavailable")

    def _validate_restored_case(self, organization_case: OrganizationCase) -> None:
        if organization_case.org_id not in self._organizations:
            raise RuntimeCoreInvariantError("restored case organization unavailable")
        department = self._departments.get(organization_case.department_id)
        if department is None or department.org_id != organization_case.org_id:
            raise RuntimeCoreInvariantError("restored case department unavailable")
        if organization_case.case_type not in department.allowed_case_types:
            raise RuntimeCoreInvariantError("restored case outside department mandate")
        owner = self._roles.get(organization_case.owner_role_id)
        if owner is None or owner.org_id != organization_case.org_id:
            raise RuntimeCoreInvariantError("restored case owner unavailable")
        for department_id in organization_case.assigned_department_ids:
            assigned = self._departments.get(department_id)
            if assigned is None or assigned.org_id != organization_case.org_id:
                raise RuntimeCoreInvariantError("restored assigned department unavailable")
            if organization_case.case_type not in assigned.allowed_case_types:
                raise RuntimeCoreInvariantError("restored assigned department cannot handle case type")

    def _validate_restored_evidence(self, evidence: CaseEvidence) -> None:
        organization_case = self._cases.get(evidence.case_id)
        requirement = self._evidence_requirements.get(evidence.requirement_id)
        if organization_case is None or requirement is None:
            raise RuntimeCoreInvariantError("restored evidence binding unavailable")
        if requirement.org_id != organization_case.org_id or requirement.case_type != organization_case.case_type:
            raise RuntimeCoreInvariantError("restored evidence case mismatch")
        if requirement.department_id not in organization_case.assigned_department_ids:
            raise RuntimeCoreInvariantError("restored evidence department not assigned")

    def _validate_restored_approval(self, approval: ApprovalRecord) -> None:
        organization_case = self._cases.get(approval.case_id)
        role = self._roles.get(approval.role_id)
        if organization_case is None or role is None or role.org_id != organization_case.org_id:
            raise RuntimeCoreInvariantError("restored approval role unavailable")
        if role.department_id not in organization_case.assigned_department_ids:
            raise RuntimeCoreInvariantError("restored approval department not assigned")

    def _validate_restored_gate_decision(self, decision: PlanStepGateDecision) -> None:
        self._require_case(decision.case_id)
        plan = self._require_case_plan(decision.case_id)
        self._require_plan_step(plan, decision.step_id)
        for rule_id in decision.authority_rule_ids:
            if rule_id not in self._authority_rules:
                raise RuntimeCoreInvariantError("restored gate authority unavailable")
        for evidence_ref in decision.evidence_refs:
            if evidence_ref not in self._case_evidence:
                raise RuntimeCoreInvariantError("restored gate evidence unavailable")
        for approval_ref in decision.approval_refs:
            if approval_ref not in self._approvals:
                raise RuntimeCoreInvariantError("restored gate approval unavailable")

    def _validate_plan_step(self, organization_case: OrganizationCase, step: PlanStep) -> None:
        if step.case_id != organization_case.case_id:
            raise RuntimeCoreInvariantError("plan step case mismatch")
        if step.department_id not in organization_case.assigned_department_ids:
            raise RuntimeCoreInvariantError("plan step department not assigned")
        department = self._departments.get(step.department_id)
        if department is None:
            raise RuntimeCoreInvariantError("plan step department unavailable")
        if organization_case.case_type not in department.allowed_case_types:
            raise RuntimeCoreInvariantError("plan step department cannot handle case type")
        if step.capability_id not in department.allowed_capabilities:
            raise RuntimeCoreInvariantError("plan step capability outside department mandate")
        role = self._roles.get(step.responsible_role_id)
        if role is None:
            raise RuntimeCoreInvariantError("plan step role unavailable")
        if role.org_id != organization_case.org_id or role.department_id != step.department_id:
            raise RuntimeCoreInvariantError("plan step role department mismatch")
        for requirement_id in step.evidence_required:
            requirement = self._evidence_requirements.get(requirement_id)
            if requirement is None:
                raise RuntimeCoreInvariantError("plan step evidence requirement unavailable")
            if requirement.department_id != step.department_id or requirement.case_type != organization_case.case_type:
                raise RuntimeCoreInvariantError("plan step evidence requirement mismatch")

    def _assess_plan_step_gate(
        self,
        organization_case: OrganizationCase,
        step: PlanStep,
        checked_preconditions: tuple[str, ...],
    ) -> _PlanStepGateAssessment:
        checked = frozenset(checked_preconditions)
        missing_preconditions = tuple(
            precondition for precondition in step.preconditions if precondition not in checked
        )
        if missing_preconditions:
            return _PlanStepGateAssessment(
                status=PlanStepGateStatus.BLOCKED,
                reason="preconditions_missing",
                authority_rule_ids=(),
                evidence_refs=(),
                approval_refs=(),
                missing_preconditions=missing_preconditions,
            )

        capability = self._capabilities.get(step.capability_id)
        if capability is None or not capability.certified:
            return _PlanStepGateAssessment(
                status=PlanStepGateStatus.BLOCKED,
                reason="capability_not_certified",
                authority_rule_ids=(),
                evidence_refs=(),
                approval_refs=(),
            )
        if not _risk_allows(capability.risk_ceiling, organization_case.risk):
            return _PlanStepGateAssessment(
                status=PlanStepGateStatus.BLOCKED,
                reason="capability_risk_exceeded",
                authority_rule_ids=(),
                evidence_refs=(),
                approval_refs=(),
            )

        authority_rules = self._matching_authority_rules(organization_case, step)
        authority_rule_ids = tuple(rule.rule_id for rule in authority_rules)
        if not authority_rules:
            return _PlanStepGateAssessment(
                status=PlanStepGateStatus.BLOCKED,
                reason="authority_missing",
                authority_rule_ids=(),
                evidence_refs=(),
                approval_refs=(),
            )

        evidence_refs = self._evidence_refs_for_step(organization_case.case_id, step)
        if len(evidence_refs) < len(step.evidence_required):
            return _PlanStepGateAssessment(
                status=PlanStepGateStatus.BLOCKED,
                reason="evidence_missing",
                authority_rule_ids=authority_rule_ids,
                evidence_refs=evidence_refs,
                approval_refs=(),
            )

        approval_refs = self._approval_refs_for_step(organization_case.case_id, step)
        if len(approval_refs) < len(step.approvals_required):
            return _PlanStepGateAssessment(
                status=PlanStepGateStatus.BLOCKED,
                reason="approval_missing",
                authority_rule_ids=authority_rule_ids,
                evidence_refs=evidence_refs,
                approval_refs=approval_refs,
            )
        if any(rule.requires_dual_control for rule in authority_rules):
            if not self._has_dual_control_approval(organization_case.case_id, step, authority_rules):
                return _PlanStepGateAssessment(
                    status=PlanStepGateStatus.BLOCKED,
                    reason="dual_control_missing",
                    authority_rule_ids=authority_rule_ids,
                    evidence_refs=evidence_refs,
                    approval_refs=approval_refs,
                )

        return _PlanStepGateAssessment(
            status=PlanStepGateStatus.ALLOWED,
            reason="allowed",
            authority_rule_ids=authority_rule_ids,
            evidence_refs=evidence_refs,
            approval_refs=approval_refs,
        )

    def _matching_authority_rules(
        self,
        organization_case: OrganizationCase,
        step: PlanStep,
    ) -> tuple[AuthorityRule, ...]:
        now = self._clock()
        matching: list[AuthorityRule] = []
        for rule in self._authority_rules.values():
            if rule.org_id != organization_case.org_id:
                continue
            if rule.department_id != step.department_id or rule.role_id != step.responsible_role_id:
                continue
            if rule.action not in (step.action, "*"):
                continue
            if rule.resource_type not in (step.capability_id, "capability", "*"):
                continue
            if _timestamp_expired(rule.expires_at, now):
                continue
            if not _risk_allows(rule.max_risk, organization_case.risk):
                continue
            matching.append(rule)
        return tuple(sorted(matching, key=lambda rule: rule.rule_id))

    def _evidence_refs_for_step(self, case_id: str, step: PlanStep) -> tuple[str, ...]:
        refs: list[str] = []
        for requirement_id in step.evidence_required:
            matching = [
                evidence for evidence in self._case_evidence.values()
                if evidence.case_id == case_id and evidence.requirement_id == requirement_id
            ]
            if matching:
                latest = max(matching, key=lambda evidence: (evidence.submitted_at, evidence.evidence_ref))
                refs.append(latest.evidence_ref)
        return tuple(refs)

    def _approval_refs_for_step(self, case_id: str, step: PlanStep) -> tuple[str, ...]:
        refs: list[str] = []
        for approval_scope in step.approvals_required:
            for approval in self._approvals.values():
                if approval.case_id == case_id and approval.approval_scope == approval_scope:
                    refs.append(approval.approval_id)
                    break
        return tuple(refs)

    def _has_dual_control_approval(
        self,
        case_id: str,
        step: PlanStep,
        authority_rules: Iterable[AuthorityRule],
    ) -> bool:
        restricted_roles = {step.responsible_role_id}
        for rule in authority_rules:
            restricted_roles.update(rule.separation_of_duty)
        for approval in self._approvals.values():
            if approval.case_id != case_id:
                continue
            if approval.approval_scope not in step.approvals_required:
                continue
            if approval.role_id not in restricted_roles:
                return True
        return False

    def _store_gate_decision(
        self,
        organization_case: OrganizationCase,
        step: PlanStep,
        status: PlanStepGateStatus,
        reason: str,
        authority_rule_ids: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        approval_refs: tuple[str, ...],
    ) -> PlanStepGateDecision:
        decided_at = self._clock()
        decision = PlanStepGateDecision(
            decision_id=stable_identifier(
                "org-step-gate",
                {
                    "case_id": organization_case.case_id,
                    "step_id": step.step_id,
                    "status": status.value,
                    "reason": reason,
                    "decided_at": decided_at,
                },
            ),
            case_id=organization_case.case_id,
            step_id=step.step_id,
            status=status,
            reason=reason,
            authority_rule_ids=authority_rule_ids,
            evidence_refs=evidence_refs,
            approval_refs=approval_refs,
            decided_at=decided_at,
        )
        self._gate_decisions[decision.decision_id] = decision
        self._latest_gate_by_step[(organization_case.case_id, step.step_id)] = decision.decision_id
        self._emit(organization_case.case_id, "plan_step_gate_decided", {"step_id": step.step_id, "status": status.value})
        return decision

    def _validate_terminal_reconciliation(
        self,
        reconciliation: OrganizationEffectReconciliation,
        terminal_disposition: TerminalClosureDisposition,
    ) -> None:
        if terminal_disposition is TerminalClosureDisposition.COMMITTED:
            if reconciliation.status is not ReconciliationStatus.MATCH:
                raise RuntimeCoreInvariantError("committed closure requires reconciliation match")
            if reconciliation.expected_effect != reconciliation.observed_effect:
                raise RuntimeCoreInvariantError("committed closure requires matched observed effect")
            if not reconciliation.forbidden_effects_checked:
                raise RuntimeCoreInvariantError("committed closure requires forbidden effect check")
            return
        if terminal_disposition not in _NON_COMMITTED_TERMINAL_DISPOSITIONS:
            raise RuntimeCoreInvariantError("terminal disposition unavailable")

    def _validate_closure_gate_evidence(self, case_id: str, closure_evidence_refs: tuple[str, ...]) -> None:
        admitted_refs = {
            evidence.evidence_ref
            for evidence in self._case_evidence.values()
            if evidence.case_id == case_id
        }
        closure_refs = set(closure_evidence_refs)
        missing_from_closure: list[str] = []
        missing_from_case: list[str] = []
        plan = self._require_case_plan(case_id)
        for step in plan.steps:
            decision_id = self._latest_gate_by_step.get((case_id, step.step_id))
            if decision_id is None:
                continue
            decision = self._gate_decisions[decision_id]
            if decision.status is not PlanStepGateStatus.ALLOWED:
                continue
            for evidence_ref in decision.evidence_refs:
                if evidence_ref not in admitted_refs:
                    missing_from_case.append(evidence_ref)
                if evidence_ref not in closure_refs:
                    missing_from_closure.append(evidence_ref)
        if missing_from_case:
            raise RuntimeCoreInvariantError("closure gate evidence unavailable")
        if missing_from_closure:
            raise RuntimeCoreInvariantError("closure requires gate evidence refs")

    def _validate_terminal_certificate_evidence(
        self,
        case_id: str,
        terminal_certificate_id: str,
        closure_evidence_refs: tuple[str, ...],
    ) -> None:
        certificate = self._case_evidence.get(terminal_certificate_id)
        if certificate is None or certificate.case_id != case_id:
            raise RuntimeCoreInvariantError("terminal closure certificate evidence unavailable")
        if terminal_certificate_id not in set(closure_evidence_refs):
            raise RuntimeCoreInvariantError("closure requires terminal certificate evidence ref")

    def _validate_learning_admission_evidence(self, case_id: str, evidence_refs: tuple[str, ...]) -> None:
        for evidence_ref in evidence_refs:
            evidence = self._case_evidence.get(evidence_ref)
            if evidence is None or evidence.case_id != case_id:
                raise RuntimeCoreInvariantError("learning admission evidence unavailable")
            if evidence.requirement_id != LEARNING_ADMISSION_DECISION_REQUIREMENT:
                raise RuntimeCoreInvariantError("learning admission decision evidence unavailable")

    def _validate_closure_drift_authority(self, case_id: str, authority_ref: str) -> None:
        approval = self._approvals.get(authority_ref)
        if approval is None or approval.case_id != case_id:
            raise RuntimeCoreInvariantError("closure drift remediation authority unavailable")

    def _validate_closure_drift_superseded_evidence(
        self,
        case_id: str,
        closure_evidence_refs: tuple[str, ...],
        superseded_evidence_refs: tuple[str, ...],
        *,
        error_prefix: str = "",
    ) -> None:
        closure_evidence_ref_set = set(closure_evidence_refs)
        for evidence_ref in superseded_evidence_refs:
            evidence = self._case_evidence.get(evidence_ref)
            if (
                evidence is None
                or evidence.case_id != case_id
                or evidence_ref not in closure_evidence_ref_set
            ):
                raise RuntimeCoreInvariantError(
                    f"{error_prefix}closure drift remediation superseded evidence unavailable"
                )

    def _all_plan_steps_allowed(self, case_id: str) -> bool:
        plan = self._require_case_plan(case_id)
        for step in plan.steps:
            decision_id = self._latest_gate_by_step.get((case_id, step.step_id))
            if decision_id is None:
                return False
            decision = self._gate_decisions[decision_id]
            if decision.status is not PlanStepGateStatus.ALLOWED:
                return False
        return True

    def _require_case(self, case_id: str) -> OrganizationCase:
        ensure_non_empty_text("case_id", case_id)
        organization_case = self._cases.get(case_id)
        if organization_case is None:
            raise RuntimeCoreInvariantError("case unavailable")
        return organization_case

    def _require_case_plan(self, case_id: str) -> OrganizationPlan:
        plan_id = self._plan_by_case.get(case_id)
        if plan_id is None:
            raise RuntimeCoreInvariantError("case plan unavailable")
        return self._plans[plan_id]

    @staticmethod
    def _require_plan_step(plan: OrganizationPlan, step_id: str) -> PlanStep:
        ensure_non_empty_text("step_id", step_id)
        for step in plan.steps:
            if step.step_id == step_id:
                return step
        raise RuntimeCoreInvariantError("plan step unavailable")

    def _emit(self, case_id: str, event_type: str, payload: dict[str, object]) -> OrganizationCaseEvent:
        emitted_at = self._clock()
        self._event_sequence += 1
        event = OrganizationCaseEvent(
            event_id=stable_identifier(
                "org-case-event",
                {
                    "case_id": case_id,
                    "event_type": event_type,
                    "emitted_at": emitted_at,
                    "sequence": self._event_sequence,
                },
            ),
            case_id=case_id,
            event_type=event_type,
            emitted_at=emitted_at,
            payload=payload,
        )
        self._events.append(event)
        return event


def default_department_packs(org_id: str) -> tuple[DepartmentPack, ...]:
    """Return the five minimum Organization Kernel v0 department packs."""
    ensure_non_empty_text("org_id", org_id)
    case_types = (LAUNCH_GATEWAY_PILOT_CASE_TYPE,)
    return (
        DepartmentPack(
            department_id="executive",
            org_id=org_id,
            name="Executive",
            mission="Set objective, risk tolerance, and accountable closure boundary.",
            owns=("objectives", "risk_tolerance", "closure_boundary"),
            allowed_case_types=case_types,
            allowed_capabilities=("executive.objective.freeze",),
            required_evidence=(
                "executive_objective",
                TERMINAL_CLOSURE_CERTIFICATE_REQUIREMENT,
                LEARNING_ADMISSION_DECISION_REQUIREMENT,
            ),
            escalation_departments=("security_compliance",),
            metrics=("objective_change_count", "unresolved_risk_count"),
            failure_modes=("unowned_objective", "risk_tolerance_missing"),
        ),
        DepartmentPack(
            department_id="product",
            org_id=org_id,
            name="Product",
            mission="Define user-facing launch boundary and acceptance scope.",
            owns=("requirements", "launch_boundary", "user_acceptance"),
            allowed_case_types=case_types,
            allowed_capabilities=("product.launch_boundary.define",),
            required_evidence=("product_launch_boundary",),
            escalation_departments=("executive", "engineering"),
            metrics=("requirement_change_count", "launch_boundary_defect_count"),
            failure_modes=("undefined_launch_boundary", "acceptance_scope_missing"),
        ),
        DepartmentPack(
            department_id="engineering",
            org_id=org_id,
            name="Engineering",
            mission="Prepare runtime, gateway, health, witness, and conformance surfaces.",
            owns=("runtime", "api_gateway", "health_endpoints", "deployment_witness"),
            allowed_case_types=case_types,
            allowed_capabilities=("engineering.gateway_runtime.verify",),
            required_evidence=(
                "engineering_health_endpoint",
                "engineering_gateway_witness",
                "engineering_runtime_conformance",
            ),
            escalation_departments=("security_compliance",),
            metrics=("runtime_conformance_gap_count", "gateway_witness_gap_count"),
            failure_modes=("health_endpoint_unreachable", "runtime_conformance_missing"),
        ),
        DepartmentPack(
            department_id="security_compliance",
            org_id=org_id,
            name="Security Compliance",
            mission="Check authorization, secrets, evidence, and public claim boundary.",
            owns=("authorization", "secrets", "public_claim_boundary", "evidence_policy"),
            allowed_case_types=case_types,
            allowed_capabilities=("security.public_claim_boundary.check",),
            required_evidence=("security_public_claim_boundary", "security_approval"),
            escalation_departments=("executive",),
            metrics=("claim_boundary_violation_count", "unresolved_secret_gap_count"),
            failure_modes=("public_claim_unproven", "credential_boundary_unknown"),
        ),
        DepartmentPack(
            department_id="finance",
            org_id=org_id,
            name="Finance",
            mission="Check hosting and provider budget before launch execution.",
            owns=("budgets", "provider_spend", "hosting_costs"),
            allowed_case_types=case_types,
            allowed_capabilities=("finance.provider_budget.check",),
            required_evidence=("finance_budget_check",),
            escalation_departments=("executive",),
            metrics=("budget_variance", "unapproved_spend_count"),
            failure_modes=("budget_unverified", "provider_cost_unknown"),
        ),
    )


def default_roles(org_id: str) -> tuple[OrganizationRole, ...]:
    """Return one accountable owner role for each v0 department."""
    ensure_non_empty_text("org_id", org_id)
    return tuple(
        OrganizationRole(
            role_id=f"{department_id}.owner",
            org_id=org_id,
            department_id=department_id,
            name="Department Owner",
            permissions=("own_case", "execute_plan_step", "review_evidence"),
        )
        for department_id in DEFAULT_ORGANIZATION_DEPARTMENT_IDS
    )


def default_capability_bindings(org_id: str) -> tuple[CapabilityBinding, ...]:
    """Return certified capability bindings for the launch gateway pilot."""
    ensure_non_empty_text("org_id", org_id)
    return (
        CapabilityBinding(
            capability_id="executive.objective.freeze",
            org_id=org_id,
            department_id="executive",
            maturity=CapabilityMaturity.CERTIFIED,
            risk_ceiling=OrganizationRisk.HIGH,
            receipt_schema_refs=("orgos.executive_objective_receipt.v1",),
            certified=True,
        ),
        CapabilityBinding(
            capability_id="product.launch_boundary.define",
            org_id=org_id,
            department_id="product",
            maturity=CapabilityMaturity.CERTIFIED,
            risk_ceiling=OrganizationRisk.HIGH,
            receipt_schema_refs=("orgos.product_launch_boundary_receipt.v1",),
            certified=True,
        ),
        CapabilityBinding(
            capability_id="engineering.gateway_runtime.verify",
            org_id=org_id,
            department_id="engineering",
            maturity=CapabilityMaturity.CERTIFIED,
            risk_ceiling=OrganizationRisk.HIGH,
            receipt_schema_refs=("orgos.gateway_runtime_witness_receipt.v1",),
            certified=True,
        ),
        CapabilityBinding(
            capability_id="security.public_claim_boundary.check",
            org_id=org_id,
            department_id="security_compliance",
            maturity=CapabilityMaturity.CERTIFIED,
            risk_ceiling=OrganizationRisk.HIGH,
            receipt_schema_refs=("orgos.security_claim_boundary_receipt.v1",),
            certified=True,
        ),
        CapabilityBinding(
            capability_id="finance.provider_budget.check",
            org_id=org_id,
            department_id="finance",
            maturity=CapabilityMaturity.CERTIFIED,
            risk_ceiling=OrganizationRisk.HIGH,
            receipt_schema_refs=("orgos.finance_budget_receipt.v1",),
            certified=True,
        ),
    )


def default_authority_rules(org_id: str) -> tuple[AuthorityRule, ...]:
    """Return authority rules for the launch gateway pilot plan."""
    ensure_non_empty_text("org_id", org_id)
    return (
        AuthorityRule(
            rule_id="authority.executive.objective.freeze",
            org_id=org_id,
            department_id="executive",
            role_id="executive.owner",
            action="freeze_objective",
            resource_type="executive.objective.freeze",
            max_risk=OrganizationRisk.HIGH,
        ),
        AuthorityRule(
            rule_id="authority.product.launch_boundary.define",
            org_id=org_id,
            department_id="product",
            role_id="product.owner",
            action="define_launch_boundary",
            resource_type="product.launch_boundary.define",
            max_risk=OrganizationRisk.HIGH,
        ),
        AuthorityRule(
            rule_id="authority.engineering.gateway_runtime.verify",
            org_id=org_id,
            department_id="engineering",
            role_id="engineering.owner",
            action="verify_gateway_runtime",
            resource_type="engineering.gateway_runtime.verify",
            max_risk=OrganizationRisk.HIGH,
        ),
        AuthorityRule(
            rule_id="authority.security.public_claim_boundary.check",
            org_id=org_id,
            department_id="security_compliance",
            role_id="security_compliance.owner",
            action="check_public_claim_boundary",
            resource_type="security.public_claim_boundary.check",
            max_risk=OrganizationRisk.HIGH,
            requires_dual_control=True,
            separation_of_duty=("security_compliance.owner",),
        ),
        AuthorityRule(
            rule_id="authority.finance.provider_budget.check",
            org_id=org_id,
            department_id="finance",
            role_id="finance.owner",
            action="check_provider_budget",
            resource_type="finance.provider_budget.check",
            max_risk=OrganizationRisk.HIGH,
        ),
    )


def default_evidence_requirements(org_id: str) -> tuple[EvidenceRequirement, ...]:
    """Return launch gateway pilot evidence requirements."""
    ensure_non_empty_text("org_id", org_id)
    return (
        EvidenceRequirement(
            requirement_id="executive_objective",
            org_id=org_id,
            department_id="executive",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="objective_record",
            description="Frozen objective and risk tolerance.",
        ),
        EvidenceRequirement(
            requirement_id=TERMINAL_CLOSURE_CERTIFICATE_REQUIREMENT,
            org_id=org_id,
            department_id="executive",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="terminal_closure_certificate",
            description="Evidence that the terminal closure certificate was minted and bound to the case.",
        ),
        EvidenceRequirement(
            requirement_id=LEARNING_ADMISSION_DECISION_REQUIREMENT,
            org_id=org_id,
            department_id="executive",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="learning_admission_decision",
            description="Evidence that a closure-derived learning admission decision was reviewed.",
        ),
        EvidenceRequirement(
            requirement_id="product_launch_boundary",
            org_id=org_id,
            department_id="product",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="launch_boundary_record",
            description="User-facing launch boundary and acceptance scope.",
        ),
        EvidenceRequirement(
            requirement_id="engineering_health_endpoint",
            org_id=org_id,
            department_id="engineering",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="health_endpoint_receipt",
            description="Reachable health endpoint receipt.",
        ),
        EvidenceRequirement(
            requirement_id="engineering_gateway_witness",
            org_id=org_id,
            department_id="engineering",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="gateway_witness_receipt",
            description="Reachable gateway witness receipt.",
        ),
        EvidenceRequirement(
            requirement_id="engineering_runtime_conformance",
            org_id=org_id,
            department_id="engineering",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="runtime_conformance_receipt",
            description="Reachable runtime conformance receipt.",
        ),
        EvidenceRequirement(
            requirement_id="security_public_claim_boundary",
            org_id=org_id,
            department_id="security_compliance",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="public_claim_boundary_review",
            description="Security and public claim boundary review.",
        ),
        EvidenceRequirement(
            requirement_id="security_approval",
            org_id=org_id,
            department_id="security_compliance",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="dual_control_approval",
            description="Dual control approval for launch claim boundary.",
        ),
        EvidenceRequirement(
            requirement_id="finance_budget_check",
            org_id=org_id,
            department_id="finance",
            case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
            evidence_type="provider_budget_receipt",
            description="Hosting and provider budget check receipt.",
        ),
    )


def bootstrap_minimum_organization(
    kernel: OrganizationKernel,
    organization: OrganizationProfile,
) -> OrganizationProfile:
    """Register the minimum v0 organization surface into the kernel."""
    kernel.register_organization(organization)
    for department in default_department_packs(organization.org_id):
        kernel.register_department(department)
    for role in default_roles(organization.org_id):
        kernel.register_role(role)
    for capability in default_capability_bindings(organization.org_id):
        kernel.register_capability(capability)
    for rule in default_authority_rules(organization.org_id):
        kernel.register_authority_rule(rule)
    for requirement in default_evidence_requirements(organization.org_id):
        kernel.register_evidence_requirement(requirement)
    return organization


def open_launch_gateway_pilot(
    kernel: OrganizationKernel,
    *,
    org_id: str,
    case_id: str = "case.launch_gateway_pilot",
    owner_role_id: str = "executive.owner",
) -> tuple[OrganizationCase, OrganizationPlan]:
    """Open and plan the v0 Launch Gateway Pilot case."""
    now = kernel._clock()
    organization_case = OrganizationCase(
        case_id=case_id,
        org_id=org_id,
        department_id="executive",
        case_type=LAUNCH_GATEWAY_PILOT_CASE_TYPE,
        goal="Publish a gateway pilot only after runtime, security, and budget evidence are reconciled.",
        risk=OrganizationRisk.HIGH,
        owner_role_id=owner_role_id,
        status=OrganizationCaseStatus.OPEN,
        assigned_department_ids=DEFAULT_ORGANIZATION_DEPARTMENT_IDS,
        created_at=now,
    )
    kernel.open_case(organization_case)
    plan = OrganizationPlan(
        plan_id="plan.launch_gateway_pilot.v1",
        case_id=case_id,
        steps=_launch_gateway_pilot_steps(case_id),
        created_at=kernel._clock(),
    )
    kernel.create_plan(plan)
    return kernel._require_case(case_id), plan


def _launch_gateway_pilot_steps(case_id: str) -> tuple[PlanStep, ...]:
    return (
        PlanStep(
            step_id="executive_objective_freeze",
            case_id=case_id,
            department_id="executive",
            responsible_role_id="executive.owner",
            capability_id="executive.objective.freeze",
            action="freeze_objective",
            expected_effect="gateway_pilot_objective_frozen",
            preconditions=("objective_received",),
            postconditions=("objective_frozen",),
            evidence_required=("executive_objective",),
        ),
        PlanStep(
            step_id="product_launch_boundary",
            case_id=case_id,
            department_id="product",
            responsible_role_id="product.owner",
            capability_id="product.launch_boundary.define",
            action="define_launch_boundary",
            expected_effect="gateway_pilot_launch_boundary_defined",
            preconditions=("objective_frozen",),
            postconditions=("launch_boundary_defined",),
            evidence_required=("product_launch_boundary",),
            predecessor_step_ids=("executive_objective_freeze",),
        ),
        PlanStep(
            step_id="engineering_runtime_witness",
            case_id=case_id,
            department_id="engineering",
            responsible_role_id="engineering.owner",
            capability_id="engineering.gateway_runtime.verify",
            action="verify_gateway_runtime",
            expected_effect="gateway_runtime_witnessed",
            preconditions=("launch_boundary_defined",),
            postconditions=("runtime_witness_collected",),
            evidence_required=(
                "engineering_health_endpoint",
                "engineering_gateway_witness",
                "engineering_runtime_conformance",
            ),
            predecessor_step_ids=("product_launch_boundary",),
        ),
        PlanStep(
            step_id="security_claim_boundary",
            case_id=case_id,
            department_id="security_compliance",
            responsible_role_id="security_compliance.owner",
            capability_id="security.public_claim_boundary.check",
            action="check_public_claim_boundary",
            expected_effect="public_claim_boundary_checked",
            preconditions=("runtime_witness_collected",),
            postconditions=("public_claim_boundary_approved",),
            evidence_required=("security_public_claim_boundary", "security_approval"),
            approvals_required=("security_approval",),
            predecessor_step_ids=("engineering_runtime_witness",),
        ),
        PlanStep(
            step_id="finance_budget_check",
            case_id=case_id,
            department_id="finance",
            responsible_role_id="finance.owner",
            capability_id="finance.provider_budget.check",
            action="check_provider_budget",
            expected_effect="provider_budget_checked",
            preconditions=("runtime_witness_collected",),
            postconditions=("provider_budget_approved",),
            evidence_required=("finance_budget_check",),
            predecessor_step_ids=("engineering_runtime_witness",),
        ),
    )
