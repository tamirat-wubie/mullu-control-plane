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

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


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
            object.__setattr__(self, rate_field, require_unit_float(getattr(self, rate_field), rate_field))
        object.__setattr__(self, "sample_count", require_non_negative_int(self.sample_count, "sample_count"))
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
            object.__setattr__(self, f, require_unit_float(getattr(self, f), f))
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


# ---------------------------------------------------------------------------
# New enums
# ---------------------------------------------------------------------------


class ReplanReason(StrEnum):
    CONFIDENCE_TOO_LOW = "confidence_too_low"
    AMBIGUITY_TOO_HIGH = "ambiguity_too_high"
    PROVIDER_VOLATILITY = "provider_volatility"
    SLA_RISK = "sla_risk"
    LEARNING_UNRELIABLE = "learning_unreliable"
    SUBSYSTEM_DEGRADED = "subsystem_degraded"
    MULTIPLE_FAILURES = "multiple_failures"


# ---------------------------------------------------------------------------
# New frozen dataclasses
# ---------------------------------------------------------------------------

_VALID_RECOMMENDATIONS = ("proceed", "proceed_with_caution", "defer_to_review", "replan")


@dataclass(frozen=True, slots=True)
class ConfidenceEnvelope(ContractRecord):
    """Confidence interval around a point estimate."""

    assessment_id: str
    subject: str
    point_estimate: float
    lower_bound: float
    upper_bound: float
    sample_count: int
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "subject", require_non_empty_text(self.subject, "subject"))
        object.__setattr__(self, "point_estimate", require_unit_float(self.point_estimate, "point_estimate"))
        object.__setattr__(self, "lower_bound", require_unit_float(self.lower_bound, "lower_bound"))
        object.__setattr__(self, "upper_bound", require_unit_float(self.upper_bound, "upper_bound"))
        object.__setattr__(self, "sample_count", require_non_negative_int(self.sample_count, "sample_count"))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))
        if self.lower_bound > self.point_estimate:
            raise ValueError("lower_bound must be <= point_estimate")
        if self.point_estimate > self.upper_bound:
            raise ValueError("point_estimate must be <= upper_bound")


@dataclass(frozen=True, slots=True)
class DecisionReliability(ContractRecord):
    """Reliability assessment for a specific decision context."""

    reliability_id: str
    decision_context: str
    confidence_envelope: ConfidenceEnvelope
    uncertainty_factors: tuple[str, ...]
    dominant_risk: str
    recommendation: str
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reliability_id", require_non_empty_text(self.reliability_id, "reliability_id"))
        object.__setattr__(self, "decision_context", require_non_empty_text(self.decision_context, "decision_context"))
        if not isinstance(self.confidence_envelope, ConfidenceEnvelope):
            raise ValueError("confidence_envelope must be a ConfidenceEnvelope instance")
        object.__setattr__(self, "uncertainty_factors", freeze_value(self.uncertainty_factors))
        object.__setattr__(self, "dominant_risk", require_non_empty_text(self.dominant_risk, "dominant_risk"))
        object.__setattr__(self, "recommendation", require_non_empty_text(self.recommendation, "recommendation"))
        if self.recommendation not in _VALID_RECOMMENDATIONS:
            raise ValueError(f"recommendation must be one of {_VALID_RECOMMENDATIONS}")
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class ReplanRecommendation(ContractRecord):
    """Recommendation to replan a goal or workflow."""

    recommendation_id: str
    reason: ReplanReason
    description: str
    affected_entity_id: str
    severity: EscalationSeverity
    confidence_at_assessment: float
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommendation_id", require_non_empty_text(self.recommendation_id, "recommendation_id"))
        if not isinstance(self.reason, ReplanReason):
            raise ValueError("reason must be a ReplanReason value")
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "affected_entity_id", require_non_empty_text(self.affected_entity_id, "affected_entity_id"))
        if not isinstance(self.severity, EscalationSeverity):
            raise ValueError("severity must be an EscalationSeverity value")
        object.__setattr__(self, "confidence_at_assessment", require_unit_float(self.confidence_at_assessment, "confidence_at_assessment"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class MetaReasoningSnapshot(ContractRecord):
    """Comprehensive point-in-time meta-reasoning state."""

    snapshot_id: str
    captured_at: str
    health: SelfHealthSnapshot
    degraded_capabilities: tuple[DegradedModeRecord, ...]
    active_uncertainties: tuple[UncertaintyReport, ...]
    decision_reliabilities: tuple[DecisionReliability, ...]
    replan_recommendations: tuple[ReplanRecommendation, ...]
    escalation_recommendations: tuple[EscalationRecommendation, ...]
    overall_confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))
        if not isinstance(self.health, SelfHealthSnapshot):
            raise ValueError("health must be a SelfHealthSnapshot instance")
        # Freeze and validate degraded_capabilities
        object.__setattr__(self, "degraded_capabilities", freeze_value(self.degraded_capabilities))
        for item in self.degraded_capabilities:
            if not isinstance(item, DegradedModeRecord):
                raise ValueError("each degraded_capabilities element must be a DegradedModeRecord")
        # Freeze and validate active_uncertainties
        object.__setattr__(self, "active_uncertainties", freeze_value(self.active_uncertainties))
        for item in self.active_uncertainties:
            if not isinstance(item, UncertaintyReport):
                raise ValueError("each active_uncertainties element must be an UncertaintyReport")
        # Freeze and validate decision_reliabilities
        object.__setattr__(self, "decision_reliabilities", freeze_value(self.decision_reliabilities))
        for item in self.decision_reliabilities:
            if not isinstance(item, DecisionReliability):
                raise ValueError("each decision_reliabilities element must be a DecisionReliability")
        # Freeze and validate replan_recommendations
        object.__setattr__(self, "replan_recommendations", freeze_value(self.replan_recommendations))
        for item in self.replan_recommendations:
            if not isinstance(item, ReplanRecommendation):
                raise ValueError("each replan_recommendations element must be a ReplanRecommendation")
        # Freeze and validate escalation_recommendations
        object.__setattr__(self, "escalation_recommendations", freeze_value(self.escalation_recommendations))
        for item in self.escalation_recommendations:
            if not isinstance(item, EscalationRecommendation):
                raise ValueError("each escalation_recommendations element must be an EscalationRecommendation")
        object.__setattr__(self, "overall_confidence", require_unit_float(self.overall_confidence, "overall_confidence"))
