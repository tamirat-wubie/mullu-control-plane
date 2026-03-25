"""Purpose: uncertainty / belief runtime contracts.
Governance scope: typed descriptors for beliefs, hypotheses, evidence weights,
    confidence intervals, belief updates, competing hypothesis sets, belief
    decisions, uncertainty assessments, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Beliefs start PROVISIONAL with default confidence 0.5.
  - Evidence weight auto-updates belief confidence.
  - Confidence intervals require lower <= upper.
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


class BeliefStatus(Enum):
    """Status of a belief."""
    PROVISIONAL = "provisional"
    SUPPORTED = "supported"
    CHALLENGED = "challenged"
    REFUTED = "refuted"
    ESTABLISHED = "established"


class EvidenceWeight(Enum):
    """Weight of evidence."""
    DECISIVE = "decisive"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NEGLIGIBLE = "negligible"


class ConfidenceDisposition(Enum):
    """Disposition of confidence."""
    HIGH_CONFIDENCE = "high_confidence"
    MODERATE_CONFIDENCE = "moderate_confidence"
    LOW_CONFIDENCE = "low_confidence"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


class UncertaintyType(Enum):
    """Kind of uncertainty (aliased to avoid conflict with math_runtime.UncertaintyKind)."""
    EPISTEMIC = "epistemic"
    ALEATORY = "aleatory"
    MODEL = "model"
    MEASUREMENT = "measurement"


class HypothesisDisposition(Enum):
    """Disposition of a hypothesis."""
    LEADING = "leading"
    COMPETING = "competing"
    REFUTED = "refuted"
    MERGED = "merged"


class BeliefRiskLevel(Enum):
    """Risk level of a belief."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BeliefRecord(ContractRecord):
    """A belief tracked in the uncertainty runtime."""

    belief_id: str = ""
    tenant_id: str = ""
    content: str = ""
    status: BeliefStatus = BeliefStatus.PROVISIONAL
    confidence: float = 0.5
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "belief_id", require_non_empty_text(self.belief_id, "belief_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "content", require_non_empty_text(self.content, "content"))
        if not isinstance(self.status, BeliefStatus):
            raise ValueError("status must be a BeliefStatus")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UncertaintyHypothesis(ContractRecord):
    """A hypothesis in the uncertainty runtime (distinct from research_runtime.HypothesisRecord)."""

    hypothesis_id: str = ""
    tenant_id: str = ""
    belief_ref: str = ""
    disposition: HypothesisDisposition = HypothesisDisposition.COMPETING
    prior_confidence: float = 0.5
    posterior_confidence: float = 0.5
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hypothesis_id", require_non_empty_text(self.hypothesis_id, "hypothesis_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "belief_ref", require_non_empty_text(self.belief_ref, "belief_ref"))
        if not isinstance(self.disposition, HypothesisDisposition):
            raise ValueError("disposition must be a HypothesisDisposition")
        object.__setattr__(self, "prior_confidence", require_unit_float(self.prior_confidence, "prior_confidence"))
        object.__setattr__(self, "posterior_confidence", require_unit_float(self.posterior_confidence, "posterior_confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EvidenceWeightRecord(ContractRecord):
    """Evidence weight applied to a belief."""

    weight_id: str = ""
    tenant_id: str = ""
    belief_ref: str = ""
    evidence_ref: str = ""
    weight: EvidenceWeight = EvidenceWeight.MODERATE
    impact: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "weight_id", require_non_empty_text(self.weight_id, "weight_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "belief_ref", require_non_empty_text(self.belief_ref, "belief_ref"))
        object.__setattr__(self, "evidence_ref", require_non_empty_text(self.evidence_ref, "evidence_ref"))
        if not isinstance(self.weight, EvidenceWeight):
            raise ValueError("weight must be an EvidenceWeight")
        object.__setattr__(self, "impact", require_unit_float(self.impact, "impact"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConfidenceInterval(ContractRecord):
    """A confidence interval for a belief."""

    interval_id: str = ""
    tenant_id: str = ""
    belief_ref: str = ""
    lower: float = 0.0
    upper: float = 1.0
    confidence_level: float = 0.95
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "interval_id", require_non_empty_text(self.interval_id, "interval_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "belief_ref", require_non_empty_text(self.belief_ref, "belief_ref"))
        object.__setattr__(self, "lower", require_unit_float(self.lower, "lower"))
        object.__setattr__(self, "upper", require_unit_float(self.upper, "upper"))
        object.__setattr__(self, "confidence_level", require_unit_float(self.confidence_level, "confidence_level"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BeliefUpdate(ContractRecord):
    """A record of updating a belief's confidence."""

    update_id: str = ""
    tenant_id: str = ""
    belief_ref: str = ""
    prior_confidence: float = 0.5
    posterior_confidence: float = 0.5
    evidence_ref: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "update_id", require_non_empty_text(self.update_id, "update_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "belief_ref", require_non_empty_text(self.belief_ref, "belief_ref"))
        object.__setattr__(self, "prior_confidence", require_unit_float(self.prior_confidence, "prior_confidence"))
        object.__setattr__(self, "posterior_confidence", require_unit_float(self.posterior_confidence, "posterior_confidence"))
        object.__setattr__(self, "evidence_ref", require_non_empty_text(self.evidence_ref, "evidence_ref"))
        require_datetime_text(self.updated_at, "updated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CompetingHypothesisSet(ContractRecord):
    """A set of competing hypotheses."""

    set_id: str = ""
    tenant_id: str = ""
    hypothesis_count: int = 0
    leading_hypothesis_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "set_id", require_non_empty_text(self.set_id, "set_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "hypothesis_count", require_non_negative_int(self.hypothesis_count, "hypothesis_count"))
        object.__setattr__(self, "leading_hypothesis_ref", require_non_empty_text(self.leading_hypothesis_ref, "leading_hypothesis_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BeliefDecision(ContractRecord):
    """A decision about a belief's disposition."""

    decision_id: str = ""
    tenant_id: str = ""
    belief_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "belief_ref", require_non_empty_text(self.belief_ref, "belief_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UncertaintyAssessment(ContractRecord):
    """An assessment of uncertainty across beliefs."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_beliefs: int = 0
    total_hypotheses: int = 0
    total_updates: int = 0
    avg_confidence: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_beliefs", require_non_negative_int(self.total_beliefs, "total_beliefs"))
        object.__setattr__(self, "total_hypotheses", require_non_negative_int(self.total_hypotheses, "total_hypotheses"))
        object.__setattr__(self, "total_updates", require_non_negative_int(self.total_updates, "total_updates"))
        object.__setattr__(self, "avg_confidence", require_unit_float(self.avg_confidence, "avg_confidence"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UncertaintySnapshot(ContractRecord):
    """Point-in-time snapshot of the uncertainty runtime."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_beliefs: int = 0
    total_hypotheses: int = 0
    total_weights: int = 0
    total_intervals: int = 0
    total_updates: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_beliefs", require_non_negative_int(self.total_beliefs, "total_beliefs"))
        object.__setattr__(self, "total_hypotheses", require_non_negative_int(self.total_hypotheses, "total_hypotheses"))
        object.__setattr__(self, "total_weights", require_non_negative_int(self.total_weights, "total_weights"))
        object.__setattr__(self, "total_intervals", require_non_negative_int(self.total_intervals, "total_intervals"))
        object.__setattr__(self, "total_updates", require_non_negative_int(self.total_updates, "total_updates"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UncertaintyClosureReport(ContractRecord):
    """Summary report for uncertainty runtime lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_beliefs: int = 0
    total_hypotheses: int = 0
    total_updates: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_beliefs", require_non_negative_int(self.total_beliefs, "total_beliefs"))
        object.__setattr__(self, "total_hypotheses", require_non_negative_int(self.total_hypotheses, "total_hypotheses"))
        object.__setattr__(self, "total_updates", require_non_negative_int(self.total_updates, "total_updates"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
