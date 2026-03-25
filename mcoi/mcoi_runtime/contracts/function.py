"""Purpose: canonical organizational function runtime contracts.
Governance scope: function template, policy binding, SLA, queue, outcome, and metrics typing.
Dependencies: docs/30_organizational_function_runtime.md, shared contract base helpers.
Invariants:
  - Every function carries explicit identity, type, and lifecycle status.
  - No active function without an explicit policy binding.
  - No function queue without team and role assignment.
  - No silent SLA skip; every outcome is recorded and evaluated.
  - SLA escalation threshold must not exceed target completion time.
  - Metrics snapshot counts are non-negative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
)


# --- Classification enums ---


class FunctionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class FunctionType(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    DEPLOYMENT_REVIEW = "deployment_review"
    DOCUMENT_INTAKE = "document_intake"
    APPROVAL_DESK = "approval_desk"
    CODE_REVIEW = "code_review"
    CUSTOM = "custom"


class CommunicationStyle(StrEnum):
    FORMAL = "formal"
    STANDARD = "standard"
    URGENT = "urgent"
    SILENT = "silent"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class ServiceFunctionTemplate(ContractRecord):
    """Identity and metadata for a named organizational function."""

    function_id: str
    name: str
    function_type: FunctionType
    description: str
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_id", require_non_empty_text(self.function_id, "function_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.function_type, FunctionType):
            raise ValueError("function_type must be a FunctionType value")
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class FunctionPolicyBinding(ContractRecord):
    """Links a function to its policy pack, autonomy mode, and review requirements."""

    binding_id: str
    function_id: str
    policy_pack_id: str
    autonomy_mode: str
    review_required: bool
    deployment_profile_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "function_id", require_non_empty_text(self.function_id, "function_id"))
        object.__setattr__(self, "policy_pack_id", require_non_empty_text(self.policy_pack_id, "policy_pack_id"))
        object.__setattr__(self, "autonomy_mode", require_non_empty_text(self.autonomy_mode, "autonomy_mode"))
        if not isinstance(self.review_required, bool):
            raise ValueError("review_required must be a boolean")
        if self.deployment_profile_id is not None:
            object.__setattr__(
                self, "deployment_profile_id",
                require_non_empty_text(self.deployment_profile_id, "deployment_profile_id"),
            )


@dataclass(frozen=True, slots=True)
class FunctionSlaProfile(ContractRecord):
    """SLA targets for a function: completion time, approval latency, escalation threshold."""

    function_id: str
    target_completion_minutes: int
    approval_latency_minutes: int
    escalation_threshold_minutes: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_id", require_non_empty_text(self.function_id, "function_id"))
        if not isinstance(self.target_completion_minutes, int) or self.target_completion_minutes < 1:
            raise ValueError("target_completion_minutes must be a positive integer")
        if not isinstance(self.approval_latency_minutes, int) or self.approval_latency_minutes < 1:
            raise ValueError("approval_latency_minutes must be a positive integer")
        if not isinstance(self.escalation_threshold_minutes, int) or self.escalation_threshold_minutes < 1:
            raise ValueError("escalation_threshold_minutes must be a positive integer")
        if self.escalation_threshold_minutes > self.target_completion_minutes:
            raise ValueError(
                "escalation_threshold_minutes must not exceed target_completion_minutes"
            )


@dataclass(frozen=True, slots=True)
class FunctionQueueProfile(ContractRecord):
    """Binds a function to a team, role, escalation chain, and concurrency limit."""

    function_id: str
    team_id: str
    default_role_id: str
    communication_style: CommunicationStyle
    max_concurrent_jobs: int
    escalation_chain_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_id", require_non_empty_text(self.function_id, "function_id"))
        object.__setattr__(self, "team_id", require_non_empty_text(self.team_id, "team_id"))
        object.__setattr__(self, "default_role_id", require_non_empty_text(self.default_role_id, "default_role_id"))
        if not isinstance(self.communication_style, CommunicationStyle):
            raise ValueError("communication_style must be a CommunicationStyle value")
        if not isinstance(self.max_concurrent_jobs, int) or self.max_concurrent_jobs < 1:
            raise ValueError("max_concurrent_jobs must be a positive integer")
        if self.escalation_chain_id is not None:
            object.__setattr__(
                self, "escalation_chain_id",
                require_non_empty_text(self.escalation_chain_id, "escalation_chain_id"),
            )


@dataclass(frozen=True, slots=True)
class FunctionOutcomeRecord(ContractRecord):
    """Per-job outcome audit record for a function."""

    outcome_id: str
    function_id: str
    job_id: str
    completed: bool
    completion_minutes: int
    escalated: bool
    drift_detected: bool
    recorded_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome_id", require_non_empty_text(self.outcome_id, "outcome_id"))
        object.__setattr__(self, "function_id", require_non_empty_text(self.function_id, "function_id"))
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        if not isinstance(self.completed, bool):
            raise ValueError("completed must be a boolean")
        if not isinstance(self.completion_minutes, int) or self.completion_minutes < 0:
            raise ValueError("completion_minutes must be a non-negative integer")
        if not isinstance(self.escalated, bool):
            raise ValueError("escalated must be a boolean")
        if not isinstance(self.drift_detected, bool):
            raise ValueError("drift_detected must be a boolean")
        object.__setattr__(self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at"))


@dataclass(frozen=True, slots=True)
class FunctionMetricsSnapshot(ContractRecord):
    """Periodic aggregate metrics for a function."""

    function_id: str
    period_start: str
    period_end: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    avg_completion_minutes: float
    escalation_count: int
    drift_count: int
    captured_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_id", require_non_empty_text(self.function_id, "function_id"))
        object.__setattr__(self, "period_start", require_datetime_text(self.period_start, "period_start"))
        object.__setattr__(self, "period_end", require_datetime_text(self.period_end, "period_end"))
        if not isinstance(self.total_jobs, int) or self.total_jobs < 0:
            raise ValueError("total_jobs must be a non-negative integer")
        if not isinstance(self.completed_jobs, int) or self.completed_jobs < 0:
            raise ValueError("completed_jobs must be a non-negative integer")
        if not isinstance(self.failed_jobs, int) or self.failed_jobs < 0:
            raise ValueError("failed_jobs must be a non-negative integer")
        import math
        if not isinstance(self.avg_completion_minutes, (int, float)) or not math.isfinite(self.avg_completion_minutes) or self.avg_completion_minutes < 0:
            raise ValueError("avg_completion_minutes must be a non-negative finite number")
        object.__setattr__(self, "avg_completion_minutes", float(self.avg_completion_minutes))
        if not isinstance(self.escalation_count, int) or self.escalation_count < 0:
            raise ValueError("escalation_count must be a non-negative integer")
        if not isinstance(self.drift_count, int) or self.drift_count < 0:
            raise ValueError("drift_count must be a non-negative integer")
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))
