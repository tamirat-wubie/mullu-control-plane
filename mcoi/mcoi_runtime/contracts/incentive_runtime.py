"""Purpose: mechanism design / incentives runtime contracts.
Governance scope: typed descriptors for incentives, behavior observations,
    gaming detection, policy effects, decisions, contract bindings,
    assessments, violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every incentive has a lifecycle: ACTIVE -> SUSPENDED/EXPIRED/RETIRED.
  - Gaming detections reference actor and incentive.
  - EXPIRED/RETIRED incentives are terminal.
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


class IncentiveStatus(Enum):
    """Status of an incentive."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    RETIRED = "retired"


class IncentiveKind(Enum):
    """Kind of incentive mechanism."""
    REWARD = "reward"
    PENALTY = "penalty"
    BONUS = "bonus"
    DISCOUNT = "discount"
    COMMISSION = "commission"
    THRESHOLD = "threshold"


class BehaviorDisposition(Enum):
    """Disposition of observed behavior relative to incentive."""
    ALIGNED = "aligned"
    MISALIGNED = "misaligned"
    GAMING = "gaming"
    NEUTRAL = "neutral"


class RiskOfGaming(Enum):
    """Risk level for gaming detection."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyEffectKind(Enum):
    """Kind of policy effect from an incentive."""
    INTENDED = "intended"
    UNINTENDED = "unintended"
    PERVERSE = "perverse"
    NEUTRAL = "neutral"


class IncentiveRiskLevel(Enum):
    """Risk level for incentive operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IncentiveRecord(ContractRecord):
    """An incentive mechanism targeting an actor."""

    incentive_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: IncentiveKind = IncentiveKind.REWARD
    status: IncentiveStatus = IncentiveStatus.ACTIVE
    target_actor_ref: str = ""
    value: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "incentive_id", require_non_empty_text(self.incentive_id, "incentive_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, IncentiveKind):
            raise ValueError("kind must be an IncentiveKind")
        if not isinstance(self.status, IncentiveStatus):
            raise ValueError("status must be an IncentiveStatus")
        object.__setattr__(self, "target_actor_ref", require_non_empty_text(self.target_actor_ref, "target_actor_ref"))
        object.__setattr__(self, "value", require_non_negative_float(self.value, "value"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BehaviorObservation(ContractRecord):
    """An observation of actor behavior relative to an incentive."""

    observation_id: str = ""
    tenant_id: str = ""
    actor_ref: str = ""
    incentive_ref: str = ""
    disposition: BehaviorDisposition = BehaviorDisposition.NEUTRAL
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", require_non_empty_text(self.observation_id, "observation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "actor_ref", require_non_empty_text(self.actor_ref, "actor_ref"))
        object.__setattr__(self, "incentive_ref", require_non_empty_text(self.incentive_ref, "incentive_ref"))
        if not isinstance(self.disposition, BehaviorDisposition):
            raise ValueError("disposition must be a BehaviorDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GamingDetection(ContractRecord):
    """A detection of gaming behavior."""

    detection_id: str = ""
    tenant_id: str = ""
    actor_ref: str = ""
    incentive_ref: str = ""
    risk: RiskOfGaming = RiskOfGaming.LOW
    evidence: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "detection_id", require_non_empty_text(self.detection_id, "detection_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "actor_ref", require_non_empty_text(self.actor_ref, "actor_ref"))
        object.__setattr__(self, "incentive_ref", require_non_empty_text(self.incentive_ref, "incentive_ref"))
        if not isinstance(self.risk, RiskOfGaming):
            raise ValueError("risk must be a RiskOfGaming")
        object.__setattr__(self, "evidence", require_non_empty_text(self.evidence, "evidence"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PolicyEffect(ContractRecord):
    """An observed effect of a policy on incentive outcomes."""

    effect_id: str = ""
    tenant_id: str = ""
    policy_ref: str = ""
    kind: PolicyEffectKind = PolicyEffectKind.NEUTRAL
    description: str = ""
    measured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect_id", require_non_empty_text(self.effect_id, "effect_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "policy_ref", require_non_empty_text(self.policy_ref, "policy_ref"))
        if not isinstance(self.kind, PolicyEffectKind):
            raise ValueError("kind must be a PolicyEffectKind")
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        require_datetime_text(self.measured_at, "measured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class IncentiveDecision(ContractRecord):
    """A decision made about an incentive."""

    decision_id: str = ""
    tenant_id: str = ""
    incentive_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "incentive_ref", require_non_empty_text(self.incentive_ref, "incentive_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContractIncentiveBinding(ContractRecord):
    """Binding between a contract and an incentive."""

    binding_id: str = ""
    tenant_id: str = ""
    contract_ref: str = ""
    incentive_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "contract_ref", require_non_empty_text(self.contract_ref, "contract_ref"))
        object.__setattr__(self, "incentive_ref", require_non_empty_text(self.incentive_ref, "incentive_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class IncentiveAssessment(ContractRecord):
    """Assessment summary of incentive activity."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_incentives: int = 0
    total_observations: int = 0
    total_gaming_detections: int = 0
    alignment_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_incentives", require_non_negative_int(self.total_incentives, "total_incentives"))
        object.__setattr__(self, "total_observations", require_non_negative_int(self.total_observations, "total_observations"))
        object.__setattr__(self, "total_gaming_detections", require_non_negative_int(self.total_gaming_detections, "total_gaming_detections"))
        object.__setattr__(self, "alignment_rate", require_unit_float(self.alignment_rate, "alignment_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class IncentiveViolation(ContractRecord):
    """A violation detected in the incentive system."""

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
class IncentiveSnapshot(ContractRecord):
    """Point-in-time incentive state snapshot."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_incentives: int = 0
    total_observations: int = 0
    total_detections: int = 0
    total_effects: int = 0
    total_bindings: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_incentives", require_non_negative_int(self.total_incentives, "total_incentives"))
        object.__setattr__(self, "total_observations", require_non_negative_int(self.total_observations, "total_observations"))
        object.__setattr__(self, "total_detections", require_non_negative_int(self.total_detections, "total_detections"))
        object.__setattr__(self, "total_effects", require_non_negative_int(self.total_effects, "total_effects"))
        object.__setattr__(self, "total_bindings", require_non_negative_int(self.total_bindings, "total_bindings"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class IncentiveClosureReport(ContractRecord):
    """Summary report for incentive lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_incentives: int = 0
    total_observations: int = 0
    total_detections: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_incentives", require_non_negative_int(self.total_incentives, "total_incentives"))
        object.__setattr__(self, "total_observations", require_non_negative_int(self.total_observations, "total_observations"))
        object.__setattr__(self, "total_detections", require_non_negative_int(self.total_detections, "total_detections"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
