"""Purpose: governed organization kernel v0 runtime.
Governance scope: organization, department, authority, case, plan, evidence,
approval, reconciliation, terminal closure, and learning-admission binding.
Dependencies: organization kernel contracts and runtime invariant helpers.
Invariants:
  - Cases cannot open without organization, department, assigned departments, and owner role.
  - Plan steps cannot be admitted without checked preconditions, authority, capability certification, evidence, and approvals.
  - Case terminal closure requires all plan steps admitted plus effect reconciliation evidence.
  - Learning admission can only bind after terminal closure exists.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable

from mcoi_runtime.contracts.effect_assurance import ReconciliationStatus
from mcoi_runtime.contracts.organization_kernel import (
    ApprovalRecord,
    AuthorityRule,
    CapabilityBinding,
    CapabilityMaturity,
    CaseEvidence,
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
    PlanStepGateStatus,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


LAUNCH_GATEWAY_PILOT_CASE_TYPE = "launch_gateway_pilot"
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
        self._learning_bindings: dict[str, LearningAdmissionBinding] = {}
        self._events: list[OrganizationCaseEvent] = []
        self._event_sequence = 0

    @property
    def organization_count(self) -> int:
        return len(self._organizations)

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
        checked = frozenset(checked_preconditions)

        missing_preconditions = tuple(
            precondition for precondition in step.preconditions if precondition not in checked
        )
        if missing_preconditions:
            return self._store_gate_decision(
                organization_case,
                step,
                PlanStepGateStatus.BLOCKED,
                "preconditions_missing",
                (),
                (),
                (),
            )

        capability = self._capabilities.get(step.capability_id)
        if capability is None or not capability.certified:
            return self._store_gate_decision(
                organization_case,
                step,
                PlanStepGateStatus.BLOCKED,
                "capability_not_certified",
                (),
                (),
                (),
            )
        if not _risk_allows(capability.risk_ceiling, organization_case.risk):
            return self._store_gate_decision(
                organization_case,
                step,
                PlanStepGateStatus.BLOCKED,
                "capability_risk_exceeded",
                (),
                (),
                (),
            )

        authority_rules = self._matching_authority_rules(organization_case, step)
        if not authority_rules:
            return self._store_gate_decision(
                organization_case,
                step,
                PlanStepGateStatus.BLOCKED,
                "authority_missing",
                (),
                (),
                (),
            )

        evidence_refs = self._evidence_refs_for_step(organization_case.case_id, step)
        if len(evidence_refs) < len(step.evidence_required):
            return self._store_gate_decision(
                organization_case,
                step,
                PlanStepGateStatus.BLOCKED,
                "evidence_missing",
                tuple(rule.rule_id for rule in authority_rules),
                evidence_refs,
                (),
            )

        approval_refs = self._approval_refs_for_step(organization_case.case_id, step)
        if len(approval_refs) < len(step.approvals_required):
            return self._store_gate_decision(
                organization_case,
                step,
                PlanStepGateStatus.BLOCKED,
                "approval_missing",
                tuple(rule.rule_id for rule in authority_rules),
                evidence_refs,
                approval_refs,
            )
        if any(rule.requires_dual_control for rule in authority_rules):
            if not self._has_dual_control_approval(organization_case.case_id, step, authority_rules):
                return self._store_gate_decision(
                    organization_case,
                    step,
                    PlanStepGateStatus.BLOCKED,
                    "dual_control_missing",
                    tuple(rule.rule_id for rule in authority_rules),
                    evidence_refs,
                    approval_refs,
                )

        return self._store_gate_decision(
            organization_case,
            step,
            PlanStepGateStatus.ALLOWED,
            "allowed",
            tuple(rule.rule_id for rule in authority_rules),
            evidence_refs,
            approval_refs,
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
        self._validate_terminal_reconciliation(reconciliation, terminal_disposition)
        self._reconciliations[reconciliation.reconciliation_id] = reconciliation
        certificate_id = ensure_non_empty_text("terminal_certificate_id", terminal_certificate_id)
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
        self._learning_bindings[binding.binding_id] = binding
        self._emit(binding.case_id, "learning_admission_bound", {"binding_id": binding.binding_id})
        return binding

    def get_case(self, case_id: str) -> OrganizationCase | None:
        ensure_non_empty_text("case_id", case_id)
        return self._cases.get(case_id)

    def get_plan(self, plan_id: str) -> OrganizationPlan | None:
        ensure_non_empty_text("plan_id", plan_id)
        return self._plans.get(plan_id)

    def list_departments(self) -> tuple[DepartmentPack, ...]:
        return tuple(self._departments[department_id] for department_id in sorted(self._departments))

    def list_case_events(self, case_id: str | None = None) -> tuple[OrganizationCaseEvent, ...]:
        if case_id is None:
            return tuple(self._events)
        ensure_non_empty_text("case_id", case_id)
        return tuple(event for event in self._events if event.case_id == case_id)

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
            for evidence in self._case_evidence.values():
                if evidence.case_id == case_id and evidence.requirement_id == requirement_id:
                    refs.append(evidence.evidence_ref)
                    break
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
            required_evidence=("executive_objective",),
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
