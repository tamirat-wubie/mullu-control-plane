"""Purpose: canonical incident and recovery contracts.
Governance scope: incident records, recovery decisions, and attempt typing.
Dependencies: shared contract base helpers.
Invariants:
  - Every failure that warrants action produces an explicit incident record.
  - Recovery decisions are governed by autonomy/profile/policy boundaries.
  - No uncontrolled retries or hidden rollbacks.
  - Recovery attempts are fully auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    OPEN = "open"
    RECOVERING = "recovering"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class RecoveryAction(StrEnum):
    RETRY = "retry"
    RETRY_VARIANT = "retry_variant"
    REOBSERVE = "reobserve"
    REPLAN = "replan"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    SKIP = "skip"
    NO_ACTION = "no_action"


class RecoveryDecisionStatus(StrEnum):
    APPROVED = "approved"
    BLOCKED_AUTONOMY = "blocked_autonomy"
    BLOCKED_PROFILE = "blocked_profile"
    BLOCKED_POLICY = "blocked_policy"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class IncidentRecord(ContractRecord):
    """A first-class failure event with source attribution and classification."""

    incident_id: str
    severity: IncidentSeverity
    status: IncidentStatus
    source_type: str
    source_id: str
    failure_family: str
    message: str
    occurred_at: str
    run_id: str | None = None
    skill_id: str | None = None
    provider_id: str | None = None
    escalation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "incident_id", require_non_empty_text(self.incident_id, "incident_id"))
        if not isinstance(self.severity, IncidentSeverity):
            raise ValueError("severity must be an IncidentSeverity value")
        if not isinstance(self.status, IncidentStatus):
            raise ValueError("status must be an IncidentStatus value")
        object.__setattr__(self, "source_type", require_non_empty_text(self.source_type, "source_type"))
        object.__setattr__(self, "source_id", require_non_empty_text(self.source_id, "source_id"))
        object.__setattr__(self, "failure_family", require_non_empty_text(self.failure_family, "failure_family"))
        object.__setattr__(self, "message", require_non_empty_text(self.message, "message"))
        object.__setattr__(self, "occurred_at", require_datetime_text(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class RecoveryDecision(ContractRecord):
    """Decision on whether and how to recover from an incident."""

    decision_id: str
    incident_id: str
    action: RecoveryAction
    status: RecoveryDecisionStatus
    reason: str
    autonomy_mode: str | None = None
    profile_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "incident_id", require_non_empty_text(self.incident_id, "incident_id"))
        if not isinstance(self.action, RecoveryAction):
            raise ValueError("action must be a RecoveryAction value")
        if not isinstance(self.status, RecoveryDecisionStatus):
            raise ValueError("status must be a RecoveryDecisionStatus value")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))

    @property
    def is_approved(self) -> bool:
        return self.status is RecoveryDecisionStatus.APPROVED


@dataclass(frozen=True, slots=True)
class RecoveryAttempt(ContractRecord):
    """Record of executing a recovery action."""

    attempt_id: str
    incident_id: str
    decision_id: str
    action: RecoveryAction
    succeeded: bool
    started_at: str
    finished_at: str
    error_message: str | None = None
    result_run_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attempt_id", require_non_empty_text(self.attempt_id, "attempt_id"))
        object.__setattr__(self, "incident_id", require_non_empty_text(self.incident_id, "incident_id"))
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        if not isinstance(self.action, RecoveryAction):
            raise ValueError("action must be a RecoveryAction value")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
