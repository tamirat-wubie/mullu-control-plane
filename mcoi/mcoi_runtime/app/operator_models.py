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
    "GoalRunReport",
    "ObservationDirective",
    "ObservationReport",
    "ObservationRequestT",
    "OperatorRequest",
    "OperatorRunReport",
    "SkillRequest",
    "SkillRunReport",
    "WorkflowRunReport",
]
