"""Purpose: canonical meta-reasoning contracts for self-model, uncertainty, and health.
Governance scope: meta-reasoning plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Confidence derives from historical data, never fabricated.
  - Uncertainty is explicit, never suppressed.
  - Health assessment is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class EscalationSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UncertaintySource(StrEnum):
    MISSING_EVIDENCE = "missing_evidence"
    LOW_CONFIDENCE = "low_confidence"
    CONTRADICTED_STATE = "contradicted_state"
    INCOMPLETE_OBSERVATION = "incomplete_observation"
    UNVERIFIED_ASSUMPTION = "unverified_assumption"


@dataclass(frozen=True, slots=True)
class CapabilityConfidence(ContractRecord):
    """Historical reliability score for a capability."""

    capability_id: str
    success_rate: float
    verification_pass_rate: float
    timeout_rate: float
    error_rate: float
    sample_count: int
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", require_non_empty_text(self.capability_id, "capability_id"))
        for rate_field in ("success_rate", "verification_pass_rate", "timeout_rate", "error_rate"):
            val = getattr(self, rate_field)
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                raise ValueError(f"{rate_field} must be in [0.0, 1.0]")
        if not isinstance(self.sample_count, int) or self.sample_count < 0:
            raise ValueError("sample_count must be a non-negative integer")
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))

    @property
    def overall_confidence(self) -> float:
        """Derived overall confidence: success * verification, penalized by errors."""
        if self.sample_count == 0:
            return 0.0
        return round(self.success_rate * self.verification_pass_rate * (1.0 - self.error_rate), 4)


@dataclass(frozen=True, slots=True)
class UncertaintyReport(ContractRecord):
    """Explicit declaration of what the system does not know."""

    report_id: str
    subject: str
    source: UncertaintySource
    description: str
    affected_ids: tuple[str, ...]
    created_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "subject", "description"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.source, UncertaintySource):
            raise ValueError("source must be an UncertaintySource value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class DegradedModeRecord(ContractRecord):
    """Record that a capability is operating below normal reliability."""

    record_id: str
    capability_id: str
    reason: str
    confidence_at_entry: float
    threshold: float
    entered_at: str
    exited_at: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("record_id", "capability_id", "reason"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for f in ("confidence_at_entry", "threshold"):
            val = getattr(self, f)
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                raise ValueError(f"{f} must be in [0.0, 1.0]")
        object.__setattr__(self, "entered_at", require_datetime_text(self.entered_at, "entered_at"))
        if self.exited_at is not None:
            object.__setattr__(self, "exited_at", require_datetime_text(self.exited_at, "exited_at"))


@dataclass(frozen=True, slots=True)
class EscalationRecommendation(ContractRecord):
    """Advisory recommendation to escalate based on self-assessment."""

    recommendation_id: str
    reason: str
    severity: EscalationSeverity
    affected_ids: tuple[str, ...]
    suggested_action: str
    created_at: str

    def __post_init__(self) -> None:
        for field_name in ("recommendation_id", "reason", "suggested_action"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.severity, EscalationSeverity):
            raise ValueError("severity must be an EscalationSeverity value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class SubsystemHealth(ContractRecord):
    """Health of one platform subsystem."""

    subsystem: str
    status: HealthStatus
    details: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "subsystem", require_non_empty_text(self.subsystem, "subsystem"))
        if not isinstance(self.status, HealthStatus):
            raise ValueError("status must be a HealthStatus value")
        object.__setattr__(self, "details", require_non_empty_text(self.details, "details"))


@dataclass(frozen=True, slots=True)
class SelfHealthSnapshot(ContractRecord):
    """Point-in-time assessment of platform health."""

    snapshot_id: str
    subsystems: tuple[SubsystemHealth, ...]
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        if not self.subsystems:
            raise ValueError("subsystems must contain at least one item")
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))

    @property
    def overall_status(self) -> HealthStatus:
        statuses = {s.status for s in self.subsystems}
        if HealthStatus.UNAVAILABLE in statuses:
            return HealthStatus.UNAVAILABLE
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        if HealthStatus.UNKNOWN in statuses:
            return HealthStatus.UNKNOWN
        return HealthStatus.HEALTHY
