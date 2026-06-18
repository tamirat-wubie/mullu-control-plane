"""Purpose: governed organizational operating kernel contracts.
Governance scope: organizations, departments, roles, authority rules, cases,
plan steps, evidence, approvals, reconciliation, closure, and learning binding.
Dependencies: shared contract helpers, effect assurance status, terminal closure disposition.
Invariants:
  - Every organization case has an owner, primary department, assigned departments, and risk.
  - Every department has a mandate, owned objects, allowed case types, capabilities, and evidence rules.
  - Plan steps bind to explicit responsible roles, capabilities, preconditions, evidence, and effects.
  - Case closure requires explicit reconciliation, terminal disposition, and evidence references.
  - Learning admission can only bind to a terminal organization closure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, TypeVar, cast

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
)
from .effect_assurance import ReconciliationStatus
from .terminal_closure import TerminalClosureDisposition

TContract = TypeVar("TContract", bound=ContractRecord)


class OrganizationRisk(StrEnum):
    """Risk level used by organization authority and case gates."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OrganizationCaseStatus(StrEnum):
    """Durable case lifecycle state for the organization kernel."""

    OPEN = "open"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    AWAITING_EVIDENCE = "awaiting_evidence"
    CLOSED = "closed"
    REQUIRES_REVIEW = "requires_review"


class PlanStepGateStatus(StrEnum):
    """Admission outcome for one plan step."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"


class CapabilityMaturity(StrEnum):
    """Minimum capability maturity ladder for organization execution."""

    CANDIDATE = "candidate"
    PROVISIONAL = "provisional"
    CERTIFIED = "certified"
    PRODUCTION = "production"


def _freeze_text_array(
    values: tuple[str, ...] | list[str],
    field_name: str,
    *,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    if not values and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    frozen = cast(tuple[str, ...], freeze_value(list(values)))
    for idx, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{idx}]")
    return frozen


def _freeze_contract_array(
    values: tuple[TContract, ...] | list[TContract],
    field_name: str,
    record_type: type[TContract],
    *,
    allow_empty: bool = True,
) -> tuple[TContract, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    if not values and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    frozen = cast(tuple[TContract, ...], freeze_value(list(values)))
    for idx, item in enumerate(frozen):
        if not isinstance(item, record_type):
            raise ValueError(f"{field_name}[{idx}] must be a {record_type.__name__}")
    return frozen


def _require_unique_text(values: tuple[str, ...], field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must not contain duplicates")


@dataclass(frozen=True, slots=True)
class OrganizationProfile(ContractRecord):
    """Tenant-scoped organization modeled by the organization kernel."""

    org_id: str
    tenant_id: str
    name: str
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "org_id", require_non_empty_text(self.org_id, "org_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class DepartmentPack(ContractRecord):
    """Governed department surface with mandate, allowed work, evidence, and escalation."""

    department_id: str
    org_id: str
    name: str
    mission: str
    owns: tuple[str, ...]
    allowed_case_types: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    required_evidence: tuple[str, ...]
    escalation_departments: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "department_id", require_non_empty_text(self.department_id, "department_id"))
        object.__setattr__(self, "org_id", require_non_empty_text(self.org_id, "org_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "mission", require_non_empty_text(self.mission, "mission"))
        for field_name in (
            "owns",
            "allowed_case_types",
            "allowed_capabilities",
            "required_evidence",
        ):
            frozen = _freeze_text_array(getattr(self, field_name), field_name, allow_empty=False)
            _require_unique_text(frozen, field_name)
            object.__setattr__(self, field_name, frozen)
        for field_name in ("escalation_departments", "metrics", "failure_modes"):
            frozen = _freeze_text_array(getattr(self, field_name), field_name)
            _require_unique_text(frozen, field_name)
            object.__setattr__(self, field_name, frozen)
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OrganizationRole(ContractRecord):
    """Role that may own, execute, approve, or review organization work."""

    role_id: str
    org_id: str
    department_id: str
    name: str
    permissions: tuple[str, ...]
    is_human_accountable: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_id", require_non_empty_text(self.role_id, "role_id"))
        object.__setattr__(self, "org_id", require_non_empty_text(self.org_id, "org_id"))
        object.__setattr__(self, "department_id", require_non_empty_text(self.department_id, "department_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(
            self,
            "permissions",
            _freeze_text_array(self.permissions, "permissions", allow_empty=False),
        )
        if not isinstance(self.is_human_accountable, bool):
            raise ValueError("is_human_accountable must be a boolean")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class AuthorityRule(ContractRecord):
    """Authority rule for a role, action, resource type, and risk ceiling."""

    rule_id: str
    org_id: str
    department_id: str
    role_id: str
    action: str
    resource_type: str
    max_risk: OrganizationRisk
    requires_dual_control: bool = False
    separation_of_duty: tuple[str, ...] = ()
    expires_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("rule_id", "org_id", "department_id", "role_id", "action", "resource_type"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.max_risk, OrganizationRisk):
            raise ValueError("max_risk must be an OrganizationRisk value")
        if not isinstance(self.requires_dual_control, bool):
            raise ValueError("requires_dual_control must be a boolean")
        object.__setattr__(self, "separation_of_duty", _freeze_text_array(self.separation_of_duty, "separation_of_duty"))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", require_datetime_text(self.expires_at, "expires_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class CapabilityBinding(ContractRecord):
    """Registered capability available to one department under a maturity and risk ceiling."""

    capability_id: str
    org_id: str
    department_id: str
    maturity: CapabilityMaturity
    risk_ceiling: OrganizationRisk
    receipt_schema_refs: tuple[str, ...]
    certified: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", require_non_empty_text(self.capability_id, "capability_id"))
        object.__setattr__(self, "org_id", require_non_empty_text(self.org_id, "org_id"))
        object.__setattr__(self, "department_id", require_non_empty_text(self.department_id, "department_id"))
        if not isinstance(self.maturity, CapabilityMaturity):
            raise ValueError("maturity must be a CapabilityMaturity value")
        if not isinstance(self.risk_ceiling, OrganizationRisk):
            raise ValueError("risk_ceiling must be an OrganizationRisk value")
        object.__setattr__(
            self,
            "receipt_schema_refs",
            _freeze_text_array(self.receipt_schema_refs, "receipt_schema_refs", allow_empty=False),
        )
        if not isinstance(self.certified, bool):
            raise ValueError("certified must be a boolean")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class EvidenceRequirement(ContractRecord):
    """Evidence requirement that a department imposes on a case type."""

    requirement_id: str
    org_id: str
    department_id: str
    case_type: str
    evidence_type: str
    description: str
    required: bool = True

    def __post_init__(self) -> None:
        for field_name in ("requirement_id", "org_id", "department_id", "case_type", "evidence_type"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.required, bool):
            raise ValueError("required must be a boolean")


@dataclass(frozen=True, slots=True)
class OrganizationCase(ContractRecord):
    """Durable governed work container."""

    case_id: str
    org_id: str
    department_id: str
    case_type: str
    goal: str
    risk: OrganizationRisk
    owner_role_id: str
    status: OrganizationCaseStatus
    assigned_department_ids: tuple[str, ...]
    created_at: str
    plan_id: str | None = None
    terminal_closure_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("case_id", "org_id", "department_id", "case_type", "goal", "owner_role_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.risk, OrganizationRisk):
            raise ValueError("risk must be an OrganizationRisk value")
        if not isinstance(self.status, OrganizationCaseStatus):
            raise ValueError("status must be an OrganizationCaseStatus value")
        assigned = _freeze_text_array(self.assigned_department_ids, "assigned_department_ids", allow_empty=False)
        _require_unique_text(assigned, "assigned_department_ids")
        if self.department_id not in assigned:
            raise ValueError("assigned_department_ids must include department_id")
        object.__setattr__(self, "assigned_department_ids", assigned)
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        for field_name in ("plan_id", "terminal_closure_id"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_non_empty_text(value, field_name))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class PlanStep(ContractRecord):
    """One governed step in an organization case plan."""

    step_id: str
    case_id: str
    department_id: str
    responsible_role_id: str
    capability_id: str
    action: str
    expected_effect: str
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]
    evidence_required: tuple[str, ...]
    approvals_required: tuple[str, ...] = ()
    predecessor_step_ids: tuple[str, ...] = ()
    rollback_plan_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "step_id",
            "case_id",
            "department_id",
            "responsible_role_id",
            "capability_id",
            "action",
            "expected_effect",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in ("preconditions", "postconditions", "evidence_required"):
            frozen = _freeze_text_array(getattr(self, field_name), field_name, allow_empty=False)
            _require_unique_text(frozen, field_name)
            object.__setattr__(self, field_name, frozen)
        for field_name in ("approvals_required", "predecessor_step_ids"):
            frozen = _freeze_text_array(getattr(self, field_name), field_name)
            _require_unique_text(frozen, field_name)
            object.__setattr__(self, field_name, frozen)
        if self.rollback_plan_id is not None:
            object.__setattr__(self, "rollback_plan_id", require_non_empty_text(self.rollback_plan_id, "rollback_plan_id"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OrganizationPlan(ContractRecord):
    """Case plan DAG over governed organization plan steps."""

    plan_id: str
    case_id: str
    steps: tuple[PlanStep, ...]
    created_at: str
    version: int = 1
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(
            self,
            "steps",
            _freeze_contract_array(self.steps, "steps", PlanStep, allow_empty=False),
        )
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version must be a positive integer")
        self._validate_step_graph()
        object.__setattr__(self, "metadata", freeze_value(self.metadata))

    def _validate_step_graph(self) -> None:
        step_ids: set[str] = set()
        for step in self.steps:
            if step.case_id != self.case_id:
                raise ValueError("plan steps must reference the plan case_id")
            if step.step_id in step_ids:
                raise ValueError("plan steps must declare unique step_id values")
            step_ids.add(step.step_id)
        predecessor_graph = {step.step_id: step.predecessor_step_ids for step in self.steps}
        for step in self.steps:
            for predecessor_id in step.predecessor_step_ids:
                if predecessor_id == step.step_id:
                    raise ValueError("plan step cannot depend on itself")
                if predecessor_id not in step_ids:
                    raise ValueError("plan step predecessor must reference declared step_id values")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visited:
                return
            if step_id in visiting:
                raise ValueError("organization plan step graph must not contain cycles")
            visiting.add(step_id)
            for predecessor_id in predecessor_graph[step_id]:
                visit(predecessor_id)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in step_ids:
            visit(step_id)


@dataclass(frozen=True, slots=True)
class CaseEvidence(ContractRecord):
    """Evidence admitted against one case requirement."""

    evidence_ref: str
    case_id: str
    requirement_id: str
    submitted_by: str
    submitted_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("evidence_ref", "case_id", "requirement_id", "submitted_by"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "submitted_at", require_datetime_text(self.submitted_at, "submitted_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ApprovalRecord(ContractRecord):
    """Explicit approval bound to a case, role, and approval scope."""

    approval_id: str
    case_id: str
    role_id: str
    approval_scope: str
    approved_by: str
    approved_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("approval_id", "case_id", "role_id", "approval_scope", "approved_by"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "approved_at", require_datetime_text(self.approved_at, "approved_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class PlanStepGateDecision(ContractRecord):
    """Admission decision for executing one case plan step."""

    decision_id: str
    case_id: str
    step_id: str
    status: PlanStepGateStatus
    reason: str
    authority_rule_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    approval_refs: tuple[str, ...]
    decided_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "case_id", "step_id", "reason"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, PlanStepGateStatus):
            raise ValueError("status must be a PlanStepGateStatus value")
        for field_name in ("authority_rule_ids", "evidence_refs", "approval_refs"):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))
        if self.status is PlanStepGateStatus.ALLOWED:
            if not self.authority_rule_ids:
                raise ValueError("allowed step gate decisions require authority_rule_ids")
            if not self.evidence_refs:
                raise ValueError("allowed step gate decisions require evidence_refs")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class PlanStepGatePreview(ContractRecord):
    """Non-mutating admission preview for one case plan step."""

    preview_id: str
    case_id: str
    step_id: str
    status: PlanStepGateStatus
    reason: str
    checked_preconditions: tuple[str, ...]
    missing_preconditions: tuple[str, ...]
    authority_rule_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    approval_refs: tuple[str, ...]
    previewed_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("preview_id", "case_id", "step_id", "reason"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, PlanStepGateStatus):
            raise ValueError("status must be a PlanStepGateStatus value")
        for field_name in (
            "checked_preconditions",
            "missing_preconditions",
            "authority_rule_ids",
            "evidence_refs",
            "approval_refs",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        object.__setattr__(self, "previewed_at", require_datetime_text(self.previewed_at, "previewed_at"))
        if self.status is PlanStepGateStatus.ALLOWED:
            if not self.authority_rule_ids:
                raise ValueError("allowed step gate previews require authority_rule_ids")
            if not self.evidence_refs:
                raise ValueError("allowed step gate previews require evidence_refs")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OrganizationEffectReconciliation(ContractRecord):
    """Case-level expected-versus-observed effect reconciliation."""

    reconciliation_id: str
    case_id: str
    expected_effect: str
    observed_effect: str
    status: ReconciliationStatus
    forbidden_effects_checked: bool
    evidence_refs: tuple[str, ...]
    reconciled_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("reconciliation_id", "case_id", "expected_effect", "observed_effect"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, ReconciliationStatus):
            raise ValueError("status must be a ReconciliationStatus value")
        if not isinstance(self.forbidden_effects_checked, bool):
            raise ValueError("forbidden_effects_checked must be a boolean")
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_array(
                require_non_empty_tuple(self.evidence_refs, "evidence_refs"),
                "evidence_refs",
            ),
        )
        object.__setattr__(self, "reconciled_at", require_datetime_text(self.reconciled_at, "reconciled_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OrganizationTerminalClosure(ContractRecord):
    """Terminal closure binding for one organization case."""

    closure_id: str
    case_id: str
    reconciliation_id: str
    terminal_certificate_id: str
    terminal_disposition: TerminalClosureDisposition
    evidence_refs: tuple[str, ...]
    closed_at: str
    learning_admission_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("closure_id", "case_id", "reconciliation_id", "terminal_certificate_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.terminal_disposition, TerminalClosureDisposition):
            raise ValueError("terminal_disposition must be a TerminalClosureDisposition value")
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_array(
                require_non_empty_tuple(self.evidence_refs, "evidence_refs"),
                "evidence_refs",
            ),
        )
        object.__setattr__(self, "closed_at", require_datetime_text(self.closed_at, "closed_at"))
        if self.learning_admission_id is not None:
            object.__setattr__(
                self,
                "learning_admission_id",
                require_non_empty_text(self.learning_admission_id, "learning_admission_id"),
            )
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ClosureDriftRemediationBinding(ContractRecord):
    """Post-closure binding that resolves a detected closure packet drift."""

    remediation_id: str
    case_id: str
    closure_id: str
    terminal_disposition: TerminalClosureDisposition
    drift_evidence_refs: tuple[str, ...]
    superseded_evidence_refs: tuple[str, ...]
    authority_ref: str
    evidence_refs: tuple[str, ...]
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("remediation_id", "case_id", "closure_id", "authority_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.terminal_disposition, TerminalClosureDisposition):
            raise ValueError("terminal_disposition must be a TerminalClosureDisposition value")
        if self.terminal_disposition is TerminalClosureDisposition.COMMITTED:
            raise ValueError("closure drift remediation cannot use committed disposition")
        for field_name in ("drift_evidence_refs", "evidence_refs"):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_array(
                    require_non_empty_tuple(getattr(self, field_name), field_name),
                    field_name,
                ),
            )
        object.__setattr__(
            self,
            "superseded_evidence_refs",
            _freeze_text_array(self.superseded_evidence_refs, "superseded_evidence_refs"),
        )
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class LearningAdmissionBinding(ContractRecord):
    """Decision binding that permits or rejects closure-derived learning."""

    binding_id: str
    case_id: str
    closure_id: str
    decision_id: str
    admitted: bool
    evidence_refs: tuple[str, ...]
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("binding_id", "case_id", "closure_id", "decision_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.admitted, bool):
            raise ValueError("admitted must be a boolean")
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_array(
                require_non_empty_tuple(self.evidence_refs, "evidence_refs"),
                "evidence_refs",
            ),
        )
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OrganizationCaseEvent(ContractRecord):
    """Append-only event emitted by the organization kernel."""

    event_id: str
    case_id: str
    event_type: str
    emitted_at: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("event_id", "case_id", "event_type"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "emitted_at", require_datetime_text(self.emitted_at, "emitted_at"))
        object.__setattr__(self, "payload", freeze_value(self.payload))


@dataclass(frozen=True, slots=True)
class PlanStepWorkerLeaseReceipt(ContractRecord):
    """Bounded worker lease envelope recorded for one plan step.

    The lease receipt records that OrgOS admitted a lease request envelope after
    dispatch-lease preview readiness. It does NOT dispatch a worker, bind worker
    output, admit step evidence, or close a case.
    """

    lease_id: str
    case_id: str
    step_id: str
    capability_id: str
    responsible_role_id: str
    requested_by_role_id: str
    dispatch_lease_preview_id: str
    queued_action: str
    capability_action: str
    expected_effect: str
    evidence_refs: tuple[str, ...]
    timeout_seconds: int
    budget_ref: str
    created_at: str
    expires_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "lease_id",
            "case_id",
            "step_id",
            "capability_id",
            "responsible_role_id",
            "requested_by_role_id",
            "dispatch_lease_preview_id",
            "queued_action",
            "capability_action",
            "expected_effect",
            "budget_ref",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_array(
                require_non_empty_tuple(self.evidence_refs, "evidence_refs"),
                "evidence_refs",
            ),
        )
        if not isinstance(self.timeout_seconds, int) or isinstance(self.timeout_seconds, bool):
            raise ValueError("timeout_seconds must be an integer")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", require_datetime_text(self.expires_at, "expires_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class PlanStepWorkerDispatchReceipt(ContractRecord):
    """Bounded dispatch request envelope recorded for one worker lease.

    The dispatch receipt records that OrgOS created a dispatch request envelope
    from an existing worker lease. It does NOT execute a worker, bind worker
    output, admit evidence, create approval, mutate case status, or close a case.
    """

    dispatch_receipt_id: str
    dispatch_request_id: str
    case_id: str
    step_id: str
    worker_lease_id: str
    capability_id: str
    responsible_role_id: str
    requested_by_role_id: str
    worker_id: str
    dispatch_intent: str
    expected_effect: str
    evidence_refs: tuple[str, ...]
    lease_created_at: str
    dispatched_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "dispatch_receipt_id",
            "dispatch_request_id",
            "case_id",
            "step_id",
            "worker_lease_id",
            "capability_id",
            "responsible_role_id",
            "requested_by_role_id",
            "worker_id",
            "dispatch_intent",
            "expected_effect",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_array(
                require_non_empty_tuple(self.evidence_refs, "evidence_refs"),
                "evidence_refs",
            ),
        )
        object.__setattr__(self, "lease_created_at", require_datetime_text(self.lease_created_at, "lease_created_at"))
        object.__setattr__(self, "dispatched_at", require_datetime_text(self.dispatched_at, "dispatched_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class PlanStepWorkerReceiptBinding(ContractRecord):
    """Bounded worker dispatch receipt admitted as evidence for one plan step.

    The binding records that a worker-mesh dispatch receipt satisfied one of a
    plan step's declared evidence requirements. It does NOT grant dispatch
    authority: the receipt is produced by the governed worker mesh under its own
    lease, budget, and sandbox controls, and is admitted here only as case
    evidence. A worker receipt is never a terminal closure.
    """

    binding_id: str
    case_id: str
    step_id: str
    requirement_id: str
    worker_lease_id: str
    dispatch_request_id: str
    dispatch_receipt_id: str
    worker_output_hash: str
    receipt_evidence_refs: tuple[str, ...]
    admitted_evidence_ref: str
    bound_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "binding_id",
            "case_id",
            "step_id",
            "requirement_id",
            "worker_lease_id",
            "dispatch_request_id",
            "dispatch_receipt_id",
            "worker_output_hash",
            "admitted_evidence_ref",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "receipt_evidence_refs",
            _freeze_text_array(
                require_non_empty_tuple(self.receipt_evidence_refs, "receipt_evidence_refs"),
                "receipt_evidence_refs",
            ),
        )
        object.__setattr__(self, "bound_at", require_datetime_text(self.bound_at, "bound_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
