"""Purpose: self-tuning runtime contracts.
Governance scope: typed descriptors for learning signals, improvement proposals,
    parameter adjustments, policy tunings, execution tunings, improvement
    decisions, assessments, violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Risk-level gates approval requirements.
  - CONSTITUTIONAL scope always treated as CRITICAL risk.
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


class ImprovementStatus(Enum):
    """Lifecycle status of an improvement proposal."""
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


class ImprovementKind(Enum):
    """Category of improvement."""
    PARAMETER = "parameter"
    POLICY = "policy"
    EXECUTION = "execution"
    ROUTING = "routing"
    THRESHOLD = "threshold"
    STAFFING = "staffing"


class ImprovementScope(Enum):
    """Blast radius of an improvement."""
    LOCAL = "local"
    RUNTIME = "runtime"
    TENANT = "tenant"
    PLATFORM = "platform"
    CONSTITUTIONAL = "constitutional"


class ApprovalDisposition(Enum):
    """Disposition of an improvement decision."""
    AUTO_APPLIED = "auto_applied"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class LearningSignalKind(Enum):
    """Kind of learning signal that triggers improvement."""
    EXECUTION_FAILURE = "execution_failure"
    FORECAST_DRIFT = "forecast_drift"
    WORKFORCE_OVERLOAD = "workforce_overload"
    FINANCIAL_LOSS = "financial_loss"
    CONSTITUTIONAL_VIOLATION = "constitutional_violation"
    OBSERVABILITY_ANOMALY = "observability_anomaly"
    POLICY_SIMULATION = "policy_simulation"


class ImprovementRiskLevel(Enum):
    """Risk level of an improvement proposal."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LearningSignal(ContractRecord):
    """A detected learning signal that may trigger improvement."""

    signal_id: str = ""
    tenant_id: str = ""
    kind: LearningSignalKind = LearningSignalKind.EXECUTION_FAILURE
    source_runtime: str = ""
    description: str = ""
    occurrence_count: int = 0
    first_seen_at: str = ""
    last_seen_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", require_non_empty_text(self.signal_id, "signal_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, LearningSignalKind):
            raise ValueError("kind must be a LearningSignalKind")
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "occurrence_count", require_non_negative_int(self.occurrence_count, "occurrence_count"))
        require_datetime_text(self.first_seen_at, "first_seen_at")
        require_datetime_text(self.last_seen_at, "last_seen_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ImprovementProposal(ContractRecord):
    """A proposal for runtime improvement."""

    proposal_id: str = ""
    tenant_id: str = ""
    signal_ref: str = ""
    kind: ImprovementKind = ImprovementKind.PARAMETER
    scope: ImprovementScope = ImprovementScope.LOCAL
    risk_level: ImprovementRiskLevel = ImprovementRiskLevel.LOW
    status: ImprovementStatus = ImprovementStatus.PROPOSED
    description: str = ""
    justification: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_id", require_non_empty_text(self.proposal_id, "proposal_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "signal_ref", require_non_empty_text(self.signal_ref, "signal_ref"))
        if not isinstance(self.kind, ImprovementKind):
            raise ValueError("kind must be an ImprovementKind")
        if not isinstance(self.scope, ImprovementScope):
            raise ValueError("scope must be an ImprovementScope")
        if not isinstance(self.risk_level, ImprovementRiskLevel):
            raise ValueError("risk_level must be an ImprovementRiskLevel")
        if not isinstance(self.status, ImprovementStatus):
            raise ValueError("status must be an ImprovementStatus")
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "justification", require_non_empty_text(self.justification, "justification"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ParameterAdjustment(ContractRecord):
    """A parameter adjustment applied from an improvement proposal."""

    adjustment_id: str = ""
    tenant_id: str = ""
    proposal_ref: str = ""
    target_component: str = ""
    parameter_name: str = ""
    old_value: str = ""
    proposed_value: str = ""
    applied_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "adjustment_id", require_non_empty_text(self.adjustment_id, "adjustment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "proposal_ref", require_non_empty_text(self.proposal_ref, "proposal_ref"))
        object.__setattr__(self, "target_component", require_non_empty_text(self.target_component, "target_component"))
        object.__setattr__(self, "parameter_name", require_non_empty_text(self.parameter_name, "parameter_name"))
        object.__setattr__(self, "old_value", require_non_empty_text(self.old_value, "old_value"))
        object.__setattr__(self, "proposed_value", require_non_empty_text(self.proposed_value, "proposed_value"))
        if self.applied_at:
            require_datetime_text(self.applied_at, "applied_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PolicyTuningRecord(ContractRecord):
    """A policy tuning applied from an improvement proposal."""

    tuning_id: str = ""
    tenant_id: str = ""
    proposal_ref: str = ""
    rule_target: str = ""
    previous_setting: str = ""
    proposed_setting: str = ""
    blast_radius: ImprovementScope = ImprovementScope.LOCAL
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tuning_id", require_non_empty_text(self.tuning_id, "tuning_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "proposal_ref", require_non_empty_text(self.proposal_ref, "proposal_ref"))
        object.__setattr__(self, "rule_target", require_non_empty_text(self.rule_target, "rule_target"))
        object.__setattr__(self, "previous_setting", require_non_empty_text(self.previous_setting, "previous_setting"))
        object.__setattr__(self, "proposed_setting", require_non_empty_text(self.proposed_setting, "proposed_setting"))
        if not isinstance(self.blast_radius, ImprovementScope):
            raise ValueError("blast_radius must be an ImprovementScope")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionTuningRecord(ContractRecord):
    """An execution tuning applied from an improvement proposal."""

    tuning_id: str = ""
    tenant_id: str = ""
    proposal_ref: str = ""
    target_runtime: str = ""
    change_type: str = ""
    expected_gain: str = ""
    expected_risk: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tuning_id", require_non_empty_text(self.tuning_id, "tuning_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "proposal_ref", require_non_empty_text(self.proposal_ref, "proposal_ref"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "change_type", require_non_empty_text(self.change_type, "change_type"))
        object.__setattr__(self, "expected_gain", require_non_empty_text(self.expected_gain, "expected_gain"))
        object.__setattr__(self, "expected_risk", require_non_empty_text(self.expected_risk, "expected_risk"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ImprovementDecision(ContractRecord):
    """A decision on an improvement proposal."""

    decision_id: str = ""
    tenant_id: str = ""
    proposal_ref: str = ""
    disposition: ApprovalDisposition = ApprovalDisposition.PENDING_APPROVAL
    decided_by: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "proposal_ref", require_non_empty_text(self.proposal_ref, "proposal_ref"))
        if not isinstance(self.disposition, ApprovalDisposition):
            raise ValueError("disposition must be an ApprovalDisposition")
        object.__setattr__(self, "decided_by", require_non_empty_text(self.decided_by, "decided_by"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ImprovementAssessment(ContractRecord):
    """Assessment of improvement effectiveness for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_signals: int = 0
    total_proposals: int = 0
    total_applied: int = 0
    total_rolled_back: int = 0
    improvement_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_signals", require_non_negative_int(self.total_signals, "total_signals"))
        object.__setattr__(self, "total_proposals", require_non_negative_int(self.total_proposals, "total_proposals"))
        object.__setattr__(self, "total_applied", require_non_negative_int(self.total_applied, "total_applied"))
        object.__setattr__(self, "total_rolled_back", require_non_negative_int(self.total_rolled_back, "total_rolled_back"))
        object.__setattr__(self, "improvement_rate", require_unit_float(self.improvement_rate, "improvement_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ImprovementViolation(ContractRecord):
    """A violation detected in the improvement lifecycle."""

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
class ImprovementSnapshot(ContractRecord):
    """Point-in-time snapshot of self-tuning runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_signals: int = 0
    total_proposals: int = 0
    total_adjustments: int = 0
    total_policy_tunings: int = 0
    total_execution_tunings: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_signals", require_non_negative_int(self.total_signals, "total_signals"))
        object.__setattr__(self, "total_proposals", require_non_negative_int(self.total_proposals, "total_proposals"))
        object.__setattr__(self, "total_adjustments", require_non_negative_int(self.total_adjustments, "total_adjustments"))
        object.__setattr__(self, "total_policy_tunings", require_non_negative_int(self.total_policy_tunings, "total_policy_tunings"))
        object.__setattr__(self, "total_execution_tunings", require_non_negative_int(self.total_execution_tunings, "total_execution_tunings"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ImprovementClosureReport(ContractRecord):
    """Final closure report for improvement lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_signals: int = 0
    total_proposals: int = 0
    total_applied: int = 0
    total_rolled_back: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_signals", require_non_negative_int(self.total_signals, "total_signals"))
        object.__setattr__(self, "total_proposals", require_non_negative_int(self.total_proposals, "total_proposals"))
        object.__setattr__(self, "total_applied", require_non_negative_int(self.total_applied, "total_applied"))
        object.__setattr__(self, "total_rolled_back", require_non_negative_int(self.total_rolled_back, "total_rolled_back"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
