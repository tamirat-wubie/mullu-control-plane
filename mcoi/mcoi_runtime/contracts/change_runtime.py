"""Purpose: controlled change / recommendation execution runtime contracts.
Governance scope: typed descriptors for change requests, plans, steps,
    executions, approvals, evidence, rollbacks, outcomes, and impact
    assessments.
Dependencies: _base contract utilities.
Invariants:
  - Every change has explicit type, scope, and status.
  - Changes require approval bindings before execution.
  - Rollout modes govern how changes are staged.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ChangeType(Enum):
    """Kind of change being made."""
    CONNECTOR_PREFERENCE = "connector_preference"
    BUDGET_THRESHOLD = "budget_threshold"
    ESCALATION_TIMING = "escalation_timing"
    SCHEDULE_POLICY = "schedule_policy"
    CAMPAIGN_TEMPLATE_PATH = "campaign_template_path"
    DOMAIN_PACK_ACTIVATION = "domain_pack_activation"
    FALLBACK_CHAIN = "fallback_chain"
    ROUTING_RULE = "routing_rule"
    AVAILABILITY_POLICY = "availability_policy"
    CONFIGURATION = "configuration"


class ChangeScope(Enum):
    """Scope at which the change applies."""
    GLOBAL = "global"
    PORTFOLIO = "portfolio"
    CAMPAIGN = "campaign"
    CONNECTOR = "connector"
    TEAM = "team"
    FUNCTION = "function"
    CHANNEL = "channel"
    DOMAIN_PACK = "domain_pack"


class ChangeStatus(Enum):
    """Lifecycle status of a change."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class RolloutMode(Enum):
    """How the change is staged."""
    IMMEDIATE = "immediate"
    CANARY = "canary"
    PARTIAL = "partial"
    PHASED = "phased"
    FULL = "full"
    DRY_RUN = "dry_run"


class RollbackDisposition(Enum):
    """Outcome of a rollback attempt."""
    NOT_NEEDED = "not_needed"
    TRIGGERED = "triggered"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ChangeEvidenceKind(Enum):
    """Type of evidence collected for a change."""
    METRIC_BEFORE = "metric_before"
    METRIC_AFTER = "metric_after"
    LOG_ENTRY = "log_entry"
    EVENT_TRACE = "event_trace"
    APPROVAL_RECORD = "approval_record"
    ROLLBACK_RECORD = "rollback_record"
    IMPACT_ASSESSMENT = "impact_assessment"
    USER_FEEDBACK = "user_feedback"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChangeRequest(ContractRecord):
    """A request to make a controlled change."""

    change_id: str = ""
    recommendation_id: str = ""
    change_type: ChangeType = ChangeType.CONFIGURATION
    scope: ChangeScope = ChangeScope.GLOBAL
    scope_ref_id: str = ""
    title: str = ""
    description: str = ""
    status: ChangeStatus = ChangeStatus.DRAFT
    rollout_mode: RolloutMode = RolloutMode.IMMEDIATE
    priority: str = "normal"
    requested_by: str = ""
    reason: str = ""
    approval_required: bool = True
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.change_type, ChangeType):
            raise ValueError("change_type must be a ChangeType")
        if not isinstance(self.scope, ChangeScope):
            raise ValueError("scope must be a ChangeScope")
        if not isinstance(self.status, ChangeStatus):
            raise ValueError("status must be a ChangeStatus")
        if not isinstance(self.rollout_mode, RolloutMode):
            raise ValueError("rollout_mode must be a RolloutMode")
        if not isinstance(self.approval_required, bool):
            raise ValueError("approval_required must be a boolean")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ChangePlan(ContractRecord):
    """An ordered set of steps forming a change plan."""

    plan_id: str = ""
    change_id: str = ""
    title: str = ""
    step_ids: tuple[str, ...] = ()
    rollout_mode: RolloutMode = RolloutMode.IMMEDIATE
    estimated_duration_seconds: float = 0.0
    rollback_plan_id: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.rollout_mode, RolloutMode):
            raise ValueError("rollout_mode must be a RolloutMode")
        object.__setattr__(self, "estimated_duration_seconds", require_non_negative_float(self.estimated_duration_seconds, "estimated_duration_seconds"))
        object.__setattr__(self, "step_ids", freeze_value(list(self.step_ids)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ChangeStep(ContractRecord):
    """A single step within a change plan."""

    step_id: str = ""
    plan_id: str = ""
    change_id: str = ""
    ordinal: int = 0
    action: str = ""
    target_ref_id: str = ""
    description: str = ""
    status: ChangeStatus = ChangeStatus.DRAFT
    started_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", require_non_empty_text(self.step_id, "step_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "ordinal", require_non_negative_int(self.ordinal, "ordinal"))
        object.__setattr__(self, "action", require_non_empty_text(self.action, "action"))
        if not isinstance(self.status, ChangeStatus):
            raise ValueError("status must be a ChangeStatus")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ChangeExecution(ContractRecord):
    """Record of a change execution."""

    execution_id: str = ""
    change_id: str = ""
    plan_id: str = ""
    status: ChangeStatus = ChangeStatus.IN_PROGRESS
    steps_total: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    rollout_mode: RolloutMode = RolloutMode.IMMEDIATE
    started_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        if not isinstance(self.status, ChangeStatus):
            raise ValueError("status must be a ChangeStatus")
        if not isinstance(self.rollout_mode, RolloutMode):
            raise ValueError("rollout_mode must be a RolloutMode")
        object.__setattr__(self, "steps_total", require_non_negative_int(self.steps_total, "steps_total"))
        object.__setattr__(self, "steps_completed", require_non_negative_int(self.steps_completed, "steps_completed"))
        object.__setattr__(self, "steps_failed", require_non_negative_int(self.steps_failed, "steps_failed"))
        if self.steps_completed + self.steps_failed > self.steps_total:
            raise ValueError("steps_completed + steps_failed must not exceed steps_total")
        require_datetime_text(self.started_at, "started_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ChangeApprovalBinding(ContractRecord):
    """Approval decision for a change."""

    approval_id: str = ""
    change_id: str = ""
    approved_by: str = ""
    approved: bool = False
    reason: str = ""
    approved_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "approval_id", require_non_empty_text(self.approval_id, "approval_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "approved_by", require_non_empty_text(self.approved_by, "approved_by"))
        if not isinstance(self.approved, bool):
            raise ValueError("approved must be a boolean")
        require_datetime_text(self.approved_at, "approved_at")


@dataclass(frozen=True, slots=True)
class ChangeEvidence(ContractRecord):
    """Evidence collected during a change."""

    evidence_id: str = ""
    change_id: str = ""
    kind: ChangeEvidenceKind = ChangeEvidenceKind.LOG_ENTRY
    metric_name: str = ""
    metric_value: float = 0.0
    description: str = ""
    collected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", require_non_empty_text(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        if not isinstance(self.kind, ChangeEvidenceKind):
            raise ValueError("kind must be a ChangeEvidenceKind")
        require_datetime_text(self.collected_at, "collected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RollbackPlan(ContractRecord):
    """Plan for rolling back a change."""

    rollback_id: str = ""
    change_id: str = ""
    disposition: RollbackDisposition = RollbackDisposition.NOT_NEEDED
    rollback_steps: tuple[str, ...] = ()
    reason: str = ""
    triggered_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "rollback_id", require_non_empty_text(self.rollback_id, "rollback_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        if not isinstance(self.disposition, RollbackDisposition):
            raise ValueError("disposition must be a RollbackDisposition")
        object.__setattr__(self, "rollback_steps", freeze_value(list(self.rollback_steps)))
        require_datetime_text(self.triggered_at, "triggered_at")


@dataclass(frozen=True, slots=True)
class ChangeOutcome(ContractRecord):
    """Final outcome of a change."""

    outcome_id: str = ""
    change_id: str = ""
    execution_id: str = ""
    status: ChangeStatus = ChangeStatus.COMPLETED
    success: bool = True
    improvement_observed: bool = False
    improvement_pct: float = 0.0
    rollback_disposition: RollbackDisposition = RollbackDisposition.NOT_NEEDED
    evidence_count: int = 0
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome_id", require_non_empty_text(self.outcome_id, "outcome_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        if not isinstance(self.status, ChangeStatus):
            raise ValueError("status must be a ChangeStatus")
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")
        if not isinstance(self.improvement_observed, bool):
            raise ValueError("improvement_observed must be a boolean")
        if not isinstance(self.rollback_disposition, RollbackDisposition):
            raise ValueError("rollback_disposition must be a RollbackDisposition")
        object.__setattr__(self, "evidence_count", require_non_negative_int(self.evidence_count, "evidence_count"))
        require_datetime_text(self.completed_at, "completed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ChangeImpactAssessment(ContractRecord):
    """Assessment of a change's impact on a metric."""

    assessment_id: str = ""
    change_id: str = ""
    metric_name: str = ""
    baseline_value: float = 0.0
    current_value: float = 0.0
    improvement_pct: float = 0.0
    confidence: float = 1.0
    assessment_window_seconds: float = 0.0
    assessed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "metric_name", require_non_empty_text(self.metric_name, "metric_name"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "assessment_window_seconds", require_non_negative_float(self.assessment_window_seconds, "assessment_window_seconds"))
        require_datetime_text(self.assessed_at, "assessed_at")
