"""Purpose: autonomous improvement loop contracts.
Governance scope: typed descriptors for improvement candidates, sessions,
    autonomy policies, confidence thresholds, rollback triggers, learning
    windows, suppression records, and outcome assessments.
Dependencies: _base contract utilities.
Invariants:
  - Every improvement has explicit confidence and autonomy thresholds.
  - Suppression prevents repeated bad patterns.
  - Learning windows bound observation periods.
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


class ImprovementDisposition(Enum):
    """Decision about an improvement candidate."""
    PENDING = "pending"
    AUTO_PROMOTED = "auto_promoted"
    APPROVAL_REQUIRED = "approval_required"
    SUPPRESSED = "suppressed"
    REJECTED = "rejected"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class AutonomyLevel(Enum):
    """How much autonomy the system has for a change."""
    FULL_HUMAN = "full_human"
    APPROVAL_REQUIRED = "approval_required"
    BOUNDED_AUTO = "bounded_auto"
    FULL_AUTO = "full_auto"


class ImprovementOutcomeVerdict(Enum):
    """Post-change assessment verdict."""
    IMPROVED = "improved"
    NEUTRAL = "neutral"
    DEGRADED = "degraded"
    INCONCLUSIVE = "inconclusive"


class SuppressionReason(Enum):
    """Why an improvement pattern was suppressed."""
    REPEATED_FAILURE = "repeated_failure"
    ROLLBACK_TRIGGERED = "rollback_triggered"
    DEGRADED_KPI = "degraded_kpi"
    COST_EXCEEDED = "cost_exceeded"
    MANUAL_BLOCK = "manual_block"


class LearningWindowStatus(Enum):
    """Status of a post-change learning/observation window."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"
    TIMED_OUT = "timed_out"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ImprovementCandidate(ContractRecord):
    """A recommendation evaluated for autonomous promotion."""

    candidate_id: str = ""
    recommendation_id: str = ""
    change_type: str = ""
    scope_ref_id: str = ""
    title: str = ""
    confidence: float = 0.0
    estimated_improvement_pct: float = 0.0
    estimated_cost_delta: float = 0.0
    risk_score: float = 0.0
    disposition: ImprovementDisposition = ImprovementDisposition.PENDING
    autonomy_level: AutonomyLevel = AutonomyLevel.APPROVAL_REQUIRED
    reason: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", require_non_empty_text(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "recommendation_id", require_non_empty_text(self.recommendation_id, "recommendation_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "risk_score", require_unit_float(self.risk_score, "risk_score"))
        if not isinstance(self.disposition, ImprovementDisposition):
            raise ValueError("disposition must be an ImprovementDisposition")
        if not isinstance(self.autonomy_level, AutonomyLevel):
            raise ValueError("autonomy_level must be an AutonomyLevel")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AutonomyPolicy(ContractRecord):
    """Policy governing when autonomous changes are allowed."""

    policy_id: str = ""
    change_type: str = ""
    min_confidence: float = 0.8
    max_risk_score: float = 0.3
    max_cost_delta: float = 100.0
    max_auto_changes_per_window: int = 5
    require_approval_above_cost: float = 500.0
    require_approval_above_risk: float = 0.5
    failure_suppression_threshold: int = 3
    learning_window_seconds: float = 3600.0
    rollback_tolerance_pct: float = 5.0
    enabled: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "min_confidence", require_unit_float(self.min_confidence, "min_confidence"))
        object.__setattr__(self, "max_risk_score", require_unit_float(self.max_risk_score, "max_risk_score"))
        object.__setattr__(self, "max_cost_delta", require_non_negative_float(self.max_cost_delta, "max_cost_delta"))
        object.__setattr__(self, "max_auto_changes_per_window", require_non_negative_int(self.max_auto_changes_per_window, "max_auto_changes_per_window"))
        object.__setattr__(self, "require_approval_above_cost", require_non_negative_float(self.require_approval_above_cost, "require_approval_above_cost"))
        object.__setattr__(self, "require_approval_above_risk", require_unit_float(self.require_approval_above_risk, "require_approval_above_risk"))
        object.__setattr__(self, "failure_suppression_threshold", require_non_negative_int(self.failure_suppression_threshold, "failure_suppression_threshold"))
        object.__setattr__(self, "learning_window_seconds", require_non_negative_float(self.learning_window_seconds, "learning_window_seconds"))
        object.__setattr__(self, "rollback_tolerance_pct", require_non_negative_float(self.rollback_tolerance_pct, "rollback_tolerance_pct"))
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class LearningWindow(ContractRecord):
    """Post-change observation window for measuring impact."""

    window_id: str = ""
    change_id: str = ""
    candidate_id: str = ""
    metric_name: str = ""
    baseline_value: float = 0.0
    duration_seconds: float = 3600.0
    status: LearningWindowStatus = LearningWindowStatus.ACTIVE
    current_value: float = 0.0
    improvement_pct: float = 0.0
    samples_collected: int = 0
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", require_non_empty_text(self.window_id, "window_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "metric_name", require_non_empty_text(self.metric_name, "metric_name"))
        object.__setattr__(self, "duration_seconds", require_non_negative_float(self.duration_seconds, "duration_seconds"))
        if not isinstance(self.status, LearningWindowStatus):
            raise ValueError("status must be a LearningWindowStatus")
        object.__setattr__(self, "samples_collected", require_non_negative_int(self.samples_collected, "samples_collected"))
        require_datetime_text(self.started_at, "started_at")


@dataclass(frozen=True, slots=True)
class ImprovementSession(ContractRecord):
    """Record of a full improvement attempt lifecycle."""

    session_id: str = ""
    candidate_id: str = ""
    change_id: str = ""
    autonomy_level: AutonomyLevel = AutonomyLevel.APPROVAL_REQUIRED
    disposition: ImprovementDisposition = ImprovementDisposition.PENDING
    verdict: ImprovementOutcomeVerdict = ImprovementOutcomeVerdict.INCONCLUSIVE
    improvement_pct: float = 0.0
    rollback_triggered: bool = False
    suppression_applied: bool = False
    learning_window_ids: tuple[str, ...] = ()
    started_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "candidate_id", require_non_empty_text(self.candidate_id, "candidate_id"))
        if not isinstance(self.autonomy_level, AutonomyLevel):
            raise ValueError("autonomy_level must be an AutonomyLevel")
        if not isinstance(self.disposition, ImprovementDisposition):
            raise ValueError("disposition must be an ImprovementDisposition")
        if not isinstance(self.verdict, ImprovementOutcomeVerdict):
            raise ValueError("verdict must be an ImprovementOutcomeVerdict")
        if not isinstance(self.rollback_triggered, bool):
            raise ValueError("rollback_triggered must be a boolean")
        if not isinstance(self.suppression_applied, bool):
            raise ValueError("suppression_applied must be a boolean")
        object.__setattr__(self, "learning_window_ids", freeze_value(list(self.learning_window_ids)))
        require_datetime_text(self.started_at, "started_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SuppressionRecord(ContractRecord):
    """Record of a suppressed improvement pattern."""

    suppression_id: str = ""
    change_type: str = ""
    scope_ref_id: str = ""
    reason: SuppressionReason = SuppressionReason.REPEATED_FAILURE
    failure_count: int = 0
    suppressed_at: str = ""
    expires_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "suppression_id", require_non_empty_text(self.suppression_id, "suppression_id"))
        object.__setattr__(self, "change_type", require_non_empty_text(self.change_type, "change_type"))
        if not isinstance(self.reason, SuppressionReason):
            raise ValueError("reason must be a SuppressionReason")
        object.__setattr__(self, "failure_count", require_non_negative_int(self.failure_count, "failure_count"))
        require_datetime_text(self.suppressed_at, "suppressed_at")


@dataclass(frozen=True, slots=True)
class ImprovementOutcome(ContractRecord):
    """Final outcome of an improvement attempt."""

    outcome_id: str = ""
    session_id: str = ""
    candidate_id: str = ""
    change_id: str = ""
    verdict: ImprovementOutcomeVerdict = ImprovementOutcomeVerdict.INCONCLUSIVE
    baseline_value: float = 0.0
    final_value: float = 0.0
    improvement_pct: float = 0.0
    confidence: float = 0.0
    rollback_triggered: bool = False
    suppression_triggered: bool = False
    reinforcement_applied: bool = False
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome_id", require_non_empty_text(self.outcome_id, "outcome_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "candidate_id", require_non_empty_text(self.candidate_id, "candidate_id"))
        if not isinstance(self.verdict, ImprovementOutcomeVerdict):
            raise ValueError("verdict must be an ImprovementOutcomeVerdict")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        if not isinstance(self.rollback_triggered, bool):
            raise ValueError("rollback_triggered must be a boolean")
        if not isinstance(self.suppression_triggered, bool):
            raise ValueError("suppression_triggered must be a boolean")
        if not isinstance(self.reinforcement_applied, bool):
            raise ValueError("reinforcement_applied must be a boolean")
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RollbackTrigger(ContractRecord):
    """Record of an automatic rollback trigger."""

    trigger_id: str = ""
    change_id: str = ""
    session_id: str = ""
    metric_name: str = ""
    baseline_value: float = 0.0
    observed_value: float = 0.0
    degradation_pct: float = 0.0
    tolerance_pct: float = 5.0
    triggered_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "trigger_id", require_non_empty_text(self.trigger_id, "trigger_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "metric_name", require_non_empty_text(self.metric_name, "metric_name"))
        object.__setattr__(self, "tolerance_pct", require_non_negative_float(self.tolerance_pct, "tolerance_pct"))
        require_datetime_text(self.triggered_at, "triggered_at")
