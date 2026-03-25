"""Purpose: work campaign contracts.
Governance scope: typed descriptors, statuses, steps, checkpoints, outcomes,
    escalations, execution records, dependencies, and closure reports for
    long-running, multi-step work campaigns across external systems and humans.
Dependencies: _base contract utilities.
Invariants:
  - Every campaign has explicit status, priority, and trigger.
  - Steps are typed by family (SEND_COMMUNICATION, INGEST_ARTIFACT, etc.).
  - Dependency ordering is enforced.
  - Checkpoints capture full campaign state.
  - Closure reports are immutable and complete.
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
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CampaignStatus(Enum):
    """Lifecycle status of a campaign."""
    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    WAITING = "waiting"
    ESCALATED = "escalated"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class CampaignPriority(Enum):
    """Priority classification for a campaign."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class CampaignTrigger(Enum):
    """What triggered this campaign."""
    MANUAL = "manual"
    INBOUND_MESSAGE = "inbound_message"
    ARTIFACT_INGESTED = "artifact_ingested"
    COMMITMENT_EXTRACTED = "commitment_extracted"
    OBLIGATION_CREATED = "obligation_created"
    INCIDENT_DETECTED = "incident_detected"
    SCHEDULED = "scheduled"
    DOMAIN_PACK = "domain_pack"
    SUPERVISOR_TICK = "supervisor_tick"
    ESCALATION = "escalation"


class CampaignStepType(Enum):
    """Family of campaign step."""
    SEND_COMMUNICATION = "send_communication"
    WAIT_FOR_REPLY = "wait_for_reply"
    INGEST_ARTIFACT = "ingest_artifact"
    EXTRACT_COMMITMENTS = "extract_commitments"
    CREATE_OBLIGATION = "create_obligation"
    RUN_WORKFLOW = "run_workflow"
    RUN_JOB = "run_job"
    CALL_CONNECTOR = "call_connector"
    ROUTE_TO_IDENTITY = "route_to_identity"
    REQUEST_APPROVAL = "request_approval"
    APPLY_RECOVERY = "apply_recovery"
    CHECK_CONDITION = "check_condition"
    ESCALATE = "escalate"
    CLOSE = "close"


class CampaignStepStatus(Enum):
    """Status of an individual campaign step."""
    PENDING = "pending"
    ACTIVE = "active"
    WAITING = "waiting"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    RETRYING = "retrying"


class CampaignOutcomeVerdict(Enum):
    """Outcome verdict for a campaign."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ABORTED = "aborted"
    ESCALATED = "escalated"


class CampaignEscalationReason(Enum):
    """Reason for campaign escalation."""
    STEP_FAILURE = "step_failure"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    APPROVAL_TIMEOUT = "approval_timeout"
    CONNECTOR_FAILURE = "connector_failure"
    HUMAN_UNAVAILABLE = "human_unavailable"
    POLICY_VIOLATION = "policy_violation"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CampaignDependency(ContractRecord):
    """Dependency between campaign steps."""

    dependency_id: str = ""
    campaign_id: str = ""
    source_step_id: str = ""
    target_step_id: str = ""
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "dependency_id",
            require_non_empty_text(self.dependency_id, "dependency_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(
            self, "source_step_id",
            require_non_empty_text(self.source_step_id, "source_step_id"),
        )
        object.__setattr__(
            self, "target_step_id",
            require_non_empty_text(self.target_step_id, "target_step_id"),
        )
        if not isinstance(self.required, bool):
            raise ValueError("required must be a boolean")


@dataclass(frozen=True, slots=True)
class CampaignStep(ContractRecord):
    """A single step in a campaign."""

    step_id: str = ""
    campaign_id: str = ""
    step_type: CampaignStepType = CampaignStepType.CHECK_CONDITION
    status: CampaignStepStatus = CampaignStepStatus.PENDING
    order: int = 0
    name: str = ""
    description: str = ""
    target_ref: str = ""
    input_payload: Mapping[str, Any] = field(default_factory=dict)
    output_payload: Mapping[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 0
    started_at: str = ""
    completed_at: str = ""
    error_message: str = ""
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "step_id",
            require_non_empty_text(self.step_id, "step_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        if not isinstance(self.step_type, CampaignStepType):
            raise ValueError("step_type must be a CampaignStepType")
        if not isinstance(self.status, CampaignStepStatus):
            raise ValueError("status must be a CampaignStepStatus")
        object.__setattr__(
            self, "order",
            require_non_negative_int(self.order, "order"),
        )
        object.__setattr__(
            self, "name",
            require_non_empty_text(self.name, "name"),
        )
        object.__setattr__(
            self, "retry_count",
            require_non_negative_int(self.retry_count, "retry_count"),
        )
        object.__setattr__(
            self, "max_retries",
            require_non_negative_int(self.max_retries, "max_retries"),
        )
        object.__setattr__(
            self, "timeout_seconds",
            require_non_negative_int(self.timeout_seconds, "timeout_seconds"),
        )
        object.__setattr__(
            self, "input_payload",
            freeze_value(dict(self.input_payload)),
        )
        object.__setattr__(
            self, "output_payload",
            freeze_value(dict(self.output_payload)),
        )
        object.__setattr__(
            self, "tags",
            freeze_value(list(self.tags)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )


@dataclass(frozen=True, slots=True)
class CampaignCheckpoint(ContractRecord):
    """Checkpoint capturing full campaign state at a point in time."""

    checkpoint_id: str = ""
    campaign_id: str = ""
    run_id: str = ""
    status: CampaignStatus = CampaignStatus.ACTIVE
    current_step_id: str = ""
    completed_step_ids: tuple[str, ...] = ()
    failed_step_ids: tuple[str, ...] = ()
    step_outputs: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "checkpoint_id",
            require_non_empty_text(self.checkpoint_id, "checkpoint_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(
            self, "run_id",
            require_non_empty_text(self.run_id, "run_id"),
        )
        if not isinstance(self.status, CampaignStatus):
            raise ValueError("status must be a CampaignStatus")
        object.__setattr__(
            self, "completed_step_ids",
            freeze_value(list(self.completed_step_ids)),
        )
        object.__setattr__(
            self, "failed_step_ids",
            freeze_value(list(self.failed_step_ids)),
        )
        object.__setattr__(
            self, "step_outputs",
            freeze_value(dict(self.step_outputs)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class CampaignEscalation(ContractRecord):
    """Escalation record for a campaign."""

    escalation_id: str = ""
    campaign_id: str = ""
    run_id: str = ""
    reason: CampaignEscalationReason = CampaignEscalationReason.MANUAL
    failed_step_id: str = ""
    escalated_to: str = ""
    description: str = ""
    severity: str = "medium"
    resolved: bool = False
    escalated_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "escalation_id",
            require_non_empty_text(self.escalation_id, "escalation_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(
            self, "run_id",
            require_non_empty_text(self.run_id, "run_id"),
        )
        if not isinstance(self.reason, CampaignEscalationReason):
            raise ValueError("reason must be a CampaignEscalationReason")
        if self.severity not in ("low", "medium", "high", "critical"):
            raise ValueError("severity must be low, medium, high, or critical")
        if not isinstance(self.resolved, bool):
            raise ValueError("resolved must be a boolean")
        require_datetime_text(self.escalated_at, "escalated_at")


@dataclass(frozen=True, slots=True)
class CampaignExecutionRecord(ContractRecord):
    """Record of a single step execution within a campaign."""

    record_id: str = ""
    campaign_id: str = ""
    run_id: str = ""
    step_id: str = ""
    step_type: CampaignStepType = CampaignStepType.CHECK_CONDITION
    success: bool = True
    latency_ms: float = 0.0
    input_summary: str = ""
    output_summary: str = ""
    error_message: str = ""
    executed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "record_id",
            require_non_empty_text(self.record_id, "record_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(
            self, "run_id",
            require_non_empty_text(self.run_id, "run_id"),
        )
        object.__setattr__(
            self, "step_id",
            require_non_empty_text(self.step_id, "step_id"),
        )
        if not isinstance(self.step_type, CampaignStepType):
            raise ValueError("step_type must be a CampaignStepType")
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.executed_at, "executed_at")


@dataclass(frozen=True, slots=True)
class CampaignOutcome(ContractRecord):
    """Outcome record for a campaign step or overall campaign."""

    outcome_id: str = ""
    campaign_id: str = ""
    run_id: str = ""
    verdict: CampaignOutcomeVerdict = CampaignOutcomeVerdict.SUCCESS
    steps_completed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    total_steps: int = 0
    summary: str = ""
    recorded_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "outcome_id",
            require_non_empty_text(self.outcome_id, "outcome_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(
            self, "run_id",
            require_non_empty_text(self.run_id, "run_id"),
        )
        if not isinstance(self.verdict, CampaignOutcomeVerdict):
            raise ValueError("verdict must be a CampaignOutcomeVerdict")
        object.__setattr__(
            self, "steps_completed",
            require_non_negative_int(self.steps_completed, "steps_completed"),
        )
        object.__setattr__(
            self, "steps_failed",
            require_non_negative_int(self.steps_failed, "steps_failed"),
        )
        object.__setattr__(
            self, "steps_skipped",
            require_non_negative_int(self.steps_skipped, "steps_skipped"),
        )
        object.__setattr__(
            self, "total_steps",
            require_non_negative_int(self.total_steps, "total_steps"),
        )
        require_datetime_text(self.recorded_at, "recorded_at")


@dataclass(frozen=True, slots=True)
class CampaignClosureReport(ContractRecord):
    """Immutable closure report for a completed/failed/aborted campaign."""

    report_id: str = ""
    campaign_id: str = ""
    run_id: str = ""
    final_status: CampaignStatus = CampaignStatus.COMPLETED
    outcome: CampaignOutcomeVerdict = CampaignOutcomeVerdict.SUCCESS
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    total_duration_ms: float = 0.0
    escalation_count: int = 0
    retry_count: int = 0
    obligations_created: int = 0
    messages_sent: int = 0
    artifacts_processed: int = 0
    connector_calls: int = 0
    summary: str = ""
    step_summaries: tuple[Mapping[str, Any], ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "report_id",
            require_non_empty_text(self.report_id, "report_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(
            self, "run_id",
            require_non_empty_text(self.run_id, "run_id"),
        )
        if not isinstance(self.final_status, CampaignStatus):
            raise ValueError("final_status must be a CampaignStatus")
        if not isinstance(self.outcome, CampaignOutcomeVerdict):
            raise ValueError("outcome must be a CampaignOutcomeVerdict")
        object.__setattr__(
            self, "total_steps",
            require_non_negative_int(self.total_steps, "total_steps"),
        )
        object.__setattr__(
            self, "completed_steps",
            require_non_negative_int(self.completed_steps, "completed_steps"),
        )
        object.__setattr__(
            self, "failed_steps",
            require_non_negative_int(self.failed_steps, "failed_steps"),
        )
        object.__setattr__(
            self, "skipped_steps",
            require_non_negative_int(self.skipped_steps, "skipped_steps"),
        )
        object.__setattr__(
            self, "escalation_count",
            require_non_negative_int(self.escalation_count, "escalation_count"),
        )
        object.__setattr__(
            self, "retry_count",
            require_non_negative_int(self.retry_count, "retry_count"),
        )
        object.__setattr__(
            self, "obligations_created",
            require_non_negative_int(self.obligations_created, "obligations_created"),
        )
        object.__setattr__(
            self, "messages_sent",
            require_non_negative_int(self.messages_sent, "messages_sent"),
        )
        object.__setattr__(
            self, "artifacts_processed",
            require_non_negative_int(self.artifacts_processed, "artifacts_processed"),
        )
        object.__setattr__(
            self, "connector_calls",
            require_non_negative_int(self.connector_calls, "connector_calls"),
        )
        object.__setattr__(
            self, "step_summaries",
            freeze_value(list(self.step_summaries)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class CampaignDescriptor(ContractRecord):
    """Full descriptor for a registered campaign."""

    campaign_id: str = ""
    name: str = ""
    description: str = ""
    status: CampaignStatus = CampaignStatus.DRAFT
    priority: CampaignPriority = CampaignPriority.NORMAL
    trigger: CampaignTrigger = CampaignTrigger.MANUAL
    trigger_ref_id: str = ""
    owner_id: str = ""
    domain_pack_id: str = ""
    step_count: int = 0
    tags: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(
            self, "name",
            require_non_empty_text(self.name, "name"),
        )
        if not isinstance(self.status, CampaignStatus):
            raise ValueError("status must be a CampaignStatus")
        if not isinstance(self.priority, CampaignPriority):
            raise ValueError("priority must be a CampaignPriority")
        if not isinstance(self.trigger, CampaignTrigger):
            raise ValueError("trigger must be a CampaignTrigger")
        object.__setattr__(
            self, "step_count",
            require_non_negative_int(self.step_count, "step_count"),
        )
        object.__setattr__(
            self, "tags",
            freeze_value(list(self.tags)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class CampaignRun(ContractRecord):
    """A single execution run of a campaign."""

    run_id: str = ""
    campaign_id: str = ""
    status: CampaignStatus = CampaignStatus.PENDING
    current_step_index: int = 0
    started_at: str = ""
    completed_at: str = ""
    paused_at: str = ""
    aborted_at: str = ""
    retry_count: int = 0
    checkpoint_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id",
            require_non_empty_text(self.run_id, "run_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        if not isinstance(self.status, CampaignStatus):
            raise ValueError("status must be a CampaignStatus")
        object.__setattr__(
            self, "current_step_index",
            require_non_negative_int(self.current_step_index, "current_step_index"),
        )
        object.__setattr__(
            self, "retry_count",
            require_non_negative_int(self.retry_count, "retry_count"),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
