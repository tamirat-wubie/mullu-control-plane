"""Purpose: define governed operator request and report models for the MCOI app layer.
Governance scope: operator entry contracts only.
Dependencies: runtime contracts, evidence contracts, and planning boundary results.
Invariants: request and report shapes are typed, deterministic, and reject empty identity fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from mcoi_runtime.adapters.filesystem_observer import FilesystemObservationRequest
from mcoi_runtime.adapters.observer_base import ObservationStatus
from mcoi_runtime.adapters.process_observer import ProcessObservationRequest
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.goal import GoalStatus
from mcoi_runtime.contracts.policy import PolicyDecision
from mcoi_runtime.contracts.provider_attribution import ProviderAttribution
from mcoi_runtime.contracts.skill import (
    SkillExecutionRecord,
    SkillOutcomeStatus,
    SkillSelectionDecision,
)
from mcoi_runtime.contracts.verification import VerificationResult
from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    WorkflowStatus,
)
from mcoi_runtime.core.errors import StructuredError
from mcoi_runtime.core.evidence_merger import (
    EvidenceInput,
    EvidenceState,
    EvidenceStateCategory,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.planning_boundary import PlanningBoundaryResult, PlanningKnowledge

from .skill_promotion_read_models import (
    SkillPromotionReceiptReadReport,
    SkillPromotionReceiptReadRequest,
    SkillPromotionReceiptSummary,
)


ObservationRequestT = FilesystemObservationRequest | ProcessObservationRequest


@dataclass(frozen=True, slots=True)
class ObservationDirective:
    observer_route: str
    request: ObservationRequestT
    state_key: str
    category: EvidenceStateCategory = EvidenceStateCategory.OBSERVED

    def __post_init__(self) -> None:
        if not isinstance(self.observer_route, str) or not self.observer_route.strip():
            raise RuntimeCoreInvariantError("observer_route must be a non-empty string")
        if not isinstance(self.state_key, str) or not self.state_key.strip():
            raise RuntimeCoreInvariantError("state_key must be a non-empty string")
        if not isinstance(self.category, EvidenceStateCategory):
            raise RuntimeCoreInvariantError("category must be an EvidenceStateCategory value")


@dataclass(frozen=True, slots=True)
class OperatorRequest:
    request_id: str
    subject_id: str
    goal_id: str
    template: Mapping[str, Any]
    bindings: Mapping[str, str]
    knowledge_entries: tuple[PlanningKnowledge, ...] = ()
    evidence_entries: tuple[EvidenceInput, ...] = ()
    observation_requests: tuple[ObservationDirective, ...] = ()
    blocked_knowledge_ids: tuple[str, ...] = ()
    missing_capability_ids: tuple[str, ...] = ()
    requires_operator_review: bool = False
    verification_result: VerificationResult | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id", "goal_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError("request identity fields must be non-empty strings")
        if not isinstance(self.template, Mapping):
            raise RuntimeCoreInvariantError("template must be a mapping")
        if not isinstance(self.bindings, Mapping):
            raise RuntimeCoreInvariantError("bindings must be a mapping")
        for key, value in self.bindings.items():
            if not isinstance(key, str) or not key.strip():
                raise RuntimeCoreInvariantError("binding names must be non-empty strings")
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError("binding values must be non-empty strings")
        for value in self.blocked_knowledge_ids:
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(
                    "blocked_knowledge_ids must contain non-empty strings"
                )
        for value in self.missing_capability_ids:
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(
                    "missing_capability_ids must contain non-empty strings"
                )


@dataclass(frozen=True, slots=True)
class SkillRequest:
    """Request to execute a skill through the governed runtime."""

    request_id: str
    subject_id: str
    goal_id: str
    skill_id: str | None = None
    input_context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id", "goal_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError("request identity fields must be non-empty strings")


@dataclass(frozen=True, slots=True)
class WorkflowResumeRequest:
    """Request to resume a persisted workflow execution explicitly."""

    request_id: str
    subject_id: str
    goal_id: str
    workflow_id: str
    execution_id: str
    input_context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id", "goal_id", "workflow_id", "execution_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class GoalResumeRequest:
    """Request to resume a persisted goal execution explicitly."""

    request_id: str
    subject_id: str
    goal_id: str
    input_context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id", "goal_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class GoalReconcileRequest:
    """Request to assess or restore persisted goal runtime witnesses."""

    request_id: str
    subject_id: str
    goal_ids: tuple[str, ...] = ()
    restore_from_store: bool = False

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")
        if not isinstance(self.goal_ids, tuple):
            raise RuntimeCoreInvariantError("goal_ids must be a tuple")
        for index, value in enumerate(self.goal_ids):
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(
                    f"goal_ids[{index}] must be a non-empty string"
                )
        if not isinstance(self.restore_from_store, bool):
            raise RuntimeCoreInvariantError("restore_from_store must be a bool")


@dataclass(frozen=True, slots=True)
class WorkforceReconcileRequest:
    """Request to assess or restore persisted workforce assignment state."""

    request_id: str
    subject_id: str
    tenant_id: str
    restore_from_store: bool = False
    detect_gaps: bool = True
    detect_violations: bool = True

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id", "tenant_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")
        for field_name in ("restore_from_store", "detect_gaps", "detect_violations"):
            value = getattr(self, field_name)
            if not isinstance(value, bool):
                raise RuntimeCoreInvariantError(f"{field_name} must be a bool")


@dataclass(frozen=True, slots=True)
class TeamQueueReconcileRequest:
    """Request to assess or restore persisted team queue-state witnesses."""

    request_id: str
    subject_id: str
    team_ids: tuple[str, ...] = ()
    restore_from_store: bool = False

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")
        if not isinstance(self.team_ids, tuple):
            raise RuntimeCoreInvariantError("team_ids must be a tuple")
        for index, value in enumerate(self.team_ids):
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(
                    f"team_ids[{index}] must be a non-empty string"
                )
        if not isinstance(self.restore_from_store, bool):
            raise RuntimeCoreInvariantError("restore_from_store must be a bool")


@dataclass(frozen=True, slots=True)
class WorkQueueReconcileRequest:
    """Request to assess or restore persisted work-queue entry carriers."""

    request_id: str
    subject_id: str
    entry_ids: tuple[str, ...] = ()
    restore_from_store: bool = False

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")
        if not isinstance(self.entry_ids, tuple):
            raise RuntimeCoreInvariantError("entry_ids must be a tuple")
        for index, value in enumerate(self.entry_ids):
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(
                    f"entry_ids[{index}] must be a non-empty string"
                )
        if not isinstance(self.restore_from_store, bool):
            raise RuntimeCoreInvariantError("restore_from_store must be a bool")


@dataclass(frozen=True, slots=True)
class JobReconcileRequest:
    """Request to assess or restore persisted job descriptors and states."""

    request_id: str
    subject_id: str
    job_ids: tuple[str, ...] = ()
    restore_from_store: bool = False

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")
        if not isinstance(self.job_ids, tuple):
            raise RuntimeCoreInvariantError("job_ids must be a tuple")
        for index, value in enumerate(self.job_ids):
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(
                    f"job_ids[{index}] must be a non-empty string"
                )
        if not isinstance(self.restore_from_store, bool):
            raise RuntimeCoreInvariantError("restore_from_store must be a bool")


@dataclass(frozen=True, slots=True)
class CoordinationRecoveryRequest:
    """Request to inspect or restore persisted coordination runtime carriers."""

    request_id: str
    subject_id: str
    restore_goals: bool = False
    restore_workflows: bool = False
    restore_jobs: bool = False
    restore_work_queue: bool = False
    restore_team_queue: bool = False
    restore_workforce: bool = False
    inspect_workflow_store: bool = False
    require_cross_store_consistency: bool = True

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")
        for field_name in (
            "restore_goals",
            "restore_workflows",
            "restore_jobs",
            "restore_work_queue",
            "restore_team_queue",
            "restore_workforce",
            "inspect_workflow_store",
            "require_cross_store_consistency",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, bool):
                raise RuntimeCoreInvariantError(f"{field_name} must be a bool")


@dataclass(frozen=True, slots=True)
class SkillRunReport:
    """Report from a skill execution through the operator loop."""

    request_id: str
    goal_id: str
    skill_id: str | None
    selection: SkillSelectionDecision | None
    execution_record: SkillExecutionRecord | None
    status: SkillOutcomeStatus
    completed: bool
    structured_errors: tuple[StructuredError, ...] = ()
    lifecycle_transition_warning: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status is SkillOutcomeStatus.SUCCEEDED


@dataclass(frozen=True, slots=True)
class WorkflowRunReport:
    """Report from a workflow execution through the operator loop."""

    workflow_id: str
    execution_id: str
    status: WorkflowStatus
    stage_summaries: tuple[StageExecutionResult, ...]
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class GoalRunReport:
    """Report from a goal execution through the operator loop."""

    goal_id: str
    status: GoalStatus
    plan_id: str | None
    completed_sub_goals: tuple[str, ...] = ()
    failed_sub_goals: tuple[str, ...] = ()
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class GoalReconcileReport:
    """Report from governed goal-runtime reconciliation or witness restore."""

    request_id: str
    restored: bool
    policy_decision_id: str | None
    policy_status: str | None
    autonomy_mode: str
    autonomy_decision: str
    goal_count: int
    goal_ids: tuple[str, ...]
    active_goal_count: int
    completed_goal_count: int
    failed_goal_count: int
    plan_count: int
    replan_count: int
    state_hash: str = ""
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class WorkforceReconcileReport:
    """Report from governed workforce reconciliation or restore assessment."""

    request_id: str
    tenant_id: str
    restored: bool
    assessment_id: str | None
    policy_decision_id: str | None
    policy_status: str | None
    autonomy_mode: str
    autonomy_decision: str
    worker_count: int
    active_worker_count: int
    request_count: int
    decision_count: int
    gap_count: int
    violation_count: int
    new_gap_ids: tuple[str, ...] = ()
    new_violation_ids: tuple[str, ...] = ()
    state_hash: str = ""
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class TeamQueueReconcileReport:
    """Report from governed team queue-state reconciliation or witness restore."""

    request_id: str
    restored: bool
    policy_decision_id: str | None
    policy_status: str | None
    autonomy_mode: str
    autonomy_decision: str
    queue_state_count: int
    team_ids: tuple[str, ...]
    total_queued_jobs: int
    total_assigned_jobs: int
    total_waiting_jobs: int
    total_overloaded_workers: int
    state_hash: str = ""
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class WorkQueueReconcileReport:
    """Report from governed work-queue entry reconciliation or witness restore."""

    request_id: str
    restored: bool
    policy_decision_id: str | None
    policy_status: str | None
    autonomy_mode: str
    autonomy_decision: str
    entry_count: int
    entry_ids: tuple[str, ...]
    next_entry_id: str | None
    assigned_person_entry_count: int
    assigned_team_entry_count: int
    state_hash: str = ""
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class JobReconcileReport:
    """Report from governed job-runtime reconciliation or witness restore."""

    request_id: str
    restored: bool
    policy_decision_id: str | None
    policy_status: str | None
    autonomy_mode: str
    autonomy_decision: str
    job_count: int
    job_ids: tuple[str, ...]
    active_job_count: int
    completed_job_count: int
    failed_job_count: int
    state_hash: str = ""
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class CoordinationRecoveryReport:
    """Report from governed persisted coordination recovery or inspection."""

    request_id: str
    restored_components: tuple[str, ...]
    inspected_components: tuple[str, ...]
    policy_decision_id: str | None
    policy_status: str | None
    autonomy_mode: str
    autonomy_decision: str
    job_count: int
    work_queue_entry_count: int
    team_queue_state_count: int
    workforce_worker_count: int
    workforce_request_count: int
    workforce_decision_count: int
    workflow_descriptor_count: int
    workflow_execution_count: int
    cross_store_checks_passed: bool
    goal_descriptor_count: int = 0
    goal_state_count: int = 0
    goal_plan_count: int = 0
    goal_replan_count: int = 0
    state_hash: str = ""
    errors: tuple[StructuredError, ...] = ()
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class ObservationReport:
    observer_route: str
    status: ObservationStatus
    state_key: str
    evidence_count: int
    failure_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OperatorRunReport:
    request_id: str
    goal_id: str
    policy_decision_id: str
    execution_id: str | None
    verification_id: str | None
    observation_reports: tuple[ObservationReport, ...]
    merged_state: EvidenceState
    planning_result: PlanningBoundaryResult
    policy_decision: PolicyDecision
    validation_passed: bool
    validation_error: str | None
    execution_result: ExecutionResult | None
    verification_closed: bool
    completed: bool
    verification_error: str | None
    dispatched: bool
    structured_errors: tuple[StructuredError, ...] = ()
    world_state_hash: str | None = None
    world_state_entity_count: int = 0
    world_state_contradiction_count: int = 0
    degraded_capabilities: tuple[str, ...] = ()
    escalation_recommendations: tuple[str, ...] = ()
    provider_count: int = 0
    unhealthy_providers: tuple[str, ...] = ()
    execution_route: str | None = None
    integration_provider_id: str | None = None
    communication_provider_id: str | None = None
    model_provider_id: str | None = None
    provider_attributions: tuple[ProviderAttribution, ...] = ()
    provider_attribution_count: int = 0
    receipt_attributed_provider_operation_count: int = 0
    routing_attributed_provider_operation_count: int = 0
    plane_attributed_provider_operation_count: int = 0
    autonomy_mode: str | None = None
    autonomy_decision: str | None = None
    mil_program_id: str | None = None
    mil_instruction_count: int = 0
    mil_verification_passed: bool | None = None
    mil_verification_issues: tuple[str, ...] = ()
    mil_instruction_trace: tuple[str, ...] = ()
    mil_audit_record_id: str | None = None
    mil_trace_ids: tuple[str, ...] = ()


__all__ = [
    "CoordinationRecoveryReport",
    "CoordinationRecoveryRequest",
    "GoalReconcileReport",
    "GoalReconcileRequest",
    "GoalResumeRequest",
    "GoalRunReport",
    "JobReconcileReport",
    "JobReconcileRequest",
    "ObservationDirective",
    "ObservationReport",
    "ObservationRequestT",
    "OperatorRequest",
    "OperatorRunReport",
    "SkillPromotionReceiptReadReport",
    "SkillPromotionReceiptReadRequest",
    "SkillPromotionReceiptSummary",
    "SkillRequest",
    "SkillRunReport",
    "TeamQueueReconcileReport",
    "TeamQueueReconcileRequest",
    "WorkQueueReconcileReport",
    "WorkQueueReconcileRequest",
    "WorkforceReconcileReport",
    "WorkforceReconcileRequest",
    "WorkflowResumeRequest",
    "WorkflowRunReport",
]
