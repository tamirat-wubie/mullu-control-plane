"""Purpose: temporal reasoning runtime contracts.
Governance scope: typed descriptors for temporal events, intervals, constraints,
    persistence records, sequences, decisions, assessments, violations,
    snapshots, action policy decisions, clock samples, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Intervals auto-derive disposition from start/end.
  - Constraints relate temporal events.
  - Persistence tracks fact validity windows.
  - Temporal action policy fields preserve UTC audit surfaces and bounded
    optional windows.
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


class TemporalStatus(Enum):
    """Status of a temporal entity."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class IntervalDisposition(Enum):
    """Disposition of a temporal interval."""
    OPEN = "open"
    CLOSED = "closed"
    OVERLAPPING = "overlapping"
    GAP = "gap"


class TemporalRelation(Enum):
    """Relation between temporal events (Allen's interval algebra subset)."""
    BEFORE = "before"
    AFTER = "after"
    DURING = "during"
    OVERLAPS = "overlaps"
    MEETS = "meets"
    CONTAINS = "contains"
    EQUALS = "equals"


class PersistenceStatus(Enum):
    """Status of a persisting fact."""
    PERSISTING = "persisting"
    CEASED = "ceased"
    UNKNOWN = "unknown"
    INTERMITTENT = "intermittent"


class EventSequenceStatus(Enum):
    """Status of an event sequence."""
    ORDERED = "ordered"
    DISORDERED = "disordered"
    INCOMPLETE = "incomplete"
    CYCLIC = "cyclic"


class TemporalRiskLevel(Enum):
    """Risk level for temporal reasoning."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TemporalPolicyVerdict(Enum):
    """Verdict produced by temporal policy checks."""
    ALLOW = "allow"
    DENY = "deny"
    DEFER = "defer"
    ESCALATE = "escalate"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TemporalEvent(ContractRecord):
    """A temporal event with timestamp and duration."""

    event_id: str = ""
    tenant_id: str = ""
    label: str = ""
    occurred_at: str = ""
    duration_ms: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", require_non_empty_text(self.event_id, "event_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        require_datetime_text(self.occurred_at, "occurred_at")
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalInterval(ContractRecord):
    """A temporal interval with start, end, and disposition."""

    interval_id: str = ""
    tenant_id: str = ""
    label: str = ""
    start_at: str = ""
    end_at: str = ""
    disposition: IntervalDisposition = IntervalDisposition.OPEN
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "interval_id", require_non_empty_text(self.interval_id, "interval_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        require_datetime_text(self.start_at, "start_at")
        # end_at can be empty for OPEN intervals
        if self.end_at:
            require_datetime_text(self.end_at, "end_at")
        if not isinstance(self.disposition, IntervalDisposition):
            raise ValueError("disposition must be an IntervalDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalConstraint(ContractRecord):
    """A constraint between two temporal events."""

    constraint_id: str = ""
    tenant_id: str = ""
    event_a_ref: str = ""
    event_b_ref: str = ""
    relation: TemporalRelation = TemporalRelation.BEFORE
    max_gap_ms: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", require_non_empty_text(self.constraint_id, "constraint_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "event_a_ref", require_non_empty_text(self.event_a_ref, "event_a_ref"))
        object.__setattr__(self, "event_b_ref", require_non_empty_text(self.event_b_ref, "event_b_ref"))
        if not isinstance(self.relation, TemporalRelation):
            raise ValueError("relation must be a TemporalRelation")
        object.__setattr__(self, "max_gap_ms", require_non_negative_float(self.max_gap_ms, "max_gap_ms"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PersistenceRecord(ContractRecord):
    """A record of a persisting fact with validity window."""

    persistence_id: str = ""
    tenant_id: str = ""
    fact_ref: str = ""
    status: PersistenceStatus = PersistenceStatus.PERSISTING
    valid_from: str = ""
    valid_until: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "persistence_id", require_non_empty_text(self.persistence_id, "persistence_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "fact_ref", require_non_empty_text(self.fact_ref, "fact_ref"))
        if not isinstance(self.status, PersistenceStatus):
            raise ValueError("status must be a PersistenceStatus")
        require_datetime_text(self.valid_from, "valid_from")
        # valid_until is optional; validate if non-empty
        if self.valid_until:
            require_datetime_text(self.valid_until, "valid_until")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalClockSample(ContractRecord):
    """Runtime-owned time sample for user-facing temporal resolution."""

    sample_id: str = ""
    tenant_id: str = ""
    utc_now: str = ""
    user_timezone: str = "UTC"
    local_user_time: str = ""
    original_text: str = ""
    resolved_at: str = ""
    monotonic_ns: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sample_id", require_non_empty_text(self.sample_id, "sample_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        require_datetime_text(self.utc_now, "utc_now")
        object.__setattr__(self, "user_timezone", require_non_empty_text(self.user_timezone, "user_timezone"))
        require_datetime_text(self.local_user_time, "local_user_time")
        if self.original_text:
            object.__setattr__(self, "original_text", require_non_empty_text(self.original_text, "original_text"))
        require_datetime_text(self.resolved_at, "resolved_at")
        object.__setattr__(self, "monotonic_ns", require_non_negative_int(self.monotonic_ns, "monotonic_ns"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalActionRequest(ContractRecord):
    """Action request with explicit temporal authorization windows."""

    action_id: str = ""
    tenant_id: str = ""
    actor_id: str = ""
    action_type: str = ""
    risk: TemporalRiskLevel = TemporalRiskLevel.LOW
    requested_at: str = ""
    execute_at: str = ""
    not_before: str = ""
    expires_at: str = ""
    approval_expires_at: str = ""
    evidence_fresh_until: str = ""
    retry_after: str = ""
    max_attempts: int = 0
    attempt_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "actor_id", require_non_empty_text(self.actor_id, "actor_id"))
        object.__setattr__(self, "action_type", require_non_empty_text(self.action_type, "action_type"))
        if not isinstance(self.risk, TemporalRiskLevel):
            raise ValueError("risk must be a TemporalRiskLevel")
        require_datetime_text(self.requested_at, "requested_at")
        for field_name in (
            "execute_at",
            "not_before",
            "expires_at",
            "approval_expires_at",
            "evidence_fresh_until",
            "retry_after",
        ):
            value = getattr(self, field_name)
            if value:
                require_datetime_text(value, field_name)
        object.__setattr__(self, "max_attempts", require_non_negative_int(self.max_attempts, "max_attempts"))
        object.__setattr__(self, "attempt_count", require_non_negative_int(self.attempt_count, "attempt_count"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalActionDecision(ContractRecord):
    """Temporal policy decision for an action request."""

    decision_id: str = ""
    tenant_id: str = ""
    action_ref: str = ""
    verdict: TemporalPolicyVerdict = TemporalPolicyVerdict.ALLOW
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "action_ref", require_non_empty_text(self.action_ref, "action_ref"))
        if not isinstance(self.verdict, TemporalPolicyVerdict):
            raise ValueError("verdict must be a TemporalPolicyVerdict")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalSequence(ContractRecord):
    """An ordered sequence of temporal events."""

    sequence_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    event_count: int = 0
    status: EventSequenceStatus = EventSequenceStatus.ORDERED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sequence_id", require_non_empty_text(self.sequence_id, "sequence_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "event_count", require_non_negative_int(self.event_count, "event_count"))
        if not isinstance(self.status, EventSequenceStatus):
            raise ValueError("status must be an EventSequenceStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalDecision(ContractRecord):
    """A decision about a temporal constraint satisfaction."""

    decision_id: str = ""
    tenant_id: str = ""
    constraint_ref: str = ""
    satisfied: bool = True
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "constraint_ref", require_non_empty_text(self.constraint_ref, "constraint_ref"))
        if not isinstance(self.satisfied, bool):
            raise ValueError("satisfied must be a bool")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalAssessment(ContractRecord):
    """An assessment of temporal reasoning state."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_events: int = 0
    total_intervals: int = 0
    total_constraints: int = 0
    compliance_rate: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_events", require_non_negative_int(self.total_events, "total_events"))
        object.__setattr__(self, "total_intervals", require_non_negative_int(self.total_intervals, "total_intervals"))
        object.__setattr__(self, "total_constraints", require_non_negative_int(self.total_constraints, "total_constraints"))
        object.__setattr__(self, "compliance_rate", require_unit_float(self.compliance_rate, "compliance_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalViolation(ContractRecord):
    """A temporal reasoning violation."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalSnapshot(ContractRecord):
    """Point-in-time snapshot of the temporal runtime."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_events: int = 0
    total_intervals: int = 0
    total_constraints: int = 0
    total_sequences: int = 0
    total_persistence: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_events", require_non_negative_int(self.total_events, "total_events"))
        object.__setattr__(self, "total_intervals", require_non_negative_int(self.total_intervals, "total_intervals"))
        object.__setattr__(self, "total_constraints", require_non_negative_int(self.total_constraints, "total_constraints"))
        object.__setattr__(self, "total_sequences", require_non_negative_int(self.total_sequences, "total_sequences"))
        object.__setattr__(self, "total_persistence", require_non_negative_int(self.total_persistence, "total_persistence"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TemporalClosureReport(ContractRecord):
    """Summary report for temporal runtime lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_events: int = 0
    total_intervals: int = 0
    total_constraints: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_events", require_non_negative_int(self.total_events, "total_events"))
        object.__setattr__(self, "total_intervals", require_non_negative_int(self.total_intervals, "total_intervals"))
        object.__setattr__(self, "total_constraints", require_non_negative_int(self.total_constraints, "total_constraints"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
