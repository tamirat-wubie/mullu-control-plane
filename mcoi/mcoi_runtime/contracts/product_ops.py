"""Purpose: product operations / release / lifecycle runtime contracts.
Governance scope: typed descriptors for product versions, releases, gates,
    promotions, rollbacks, lifecycle milestones, assessments, snapshots,
    violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every release references a tenant and version.
  - Gates must pass before promotion.
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


class ReleaseStatus(Enum):
    """Status of a release."""
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ReleaseKind(Enum):
    """Kind of release."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    HOTFIX = "hotfix"
    ROLLBACK = "rollback"


class PromotionDisposition(Enum):
    """Disposition of a promotion decision."""
    PROMOTED = "promoted"
    BLOCKED = "blocked"
    DEFERRED = "deferred"
    ROLLED_BACK = "rolled_back"


class RollbackStatus(Enum):
    """Status of a rollback."""
    INITIATED = "initiated"
    COMPLETED = "completed"
    FAILED = "failed"


class LifecycleStatus(Enum):
    """Lifecycle status of a product version."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    END_OF_LIFE = "end_of_life"
    RETIRED = "retired"


class ReleaseRiskLevel(Enum):
    """Risk level for a release."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProductVersionRecord(ContractRecord):
    """A version of a product."""

    version_id: str = ""
    product_id: str = ""
    tenant_id: str = ""
    version_label: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "version_id", require_non_empty_text(self.version_id, "version_id"))
        object.__setattr__(self, "product_id", require_non_empty_text(self.product_id, "product_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "version_label", require_non_empty_text(self.version_label, "version_label"))
        if not isinstance(self.lifecycle_status, LifecycleStatus):
            raise ValueError("lifecycle_status must be a LifecycleStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReleaseRecord(ContractRecord):
    """A release for a product version."""

    release_id: str = ""
    version_id: str = ""
    tenant_id: str = ""
    kind: ReleaseKind = ReleaseKind.MINOR
    status: ReleaseStatus = ReleaseStatus.DRAFT
    target_environment: str = ""
    gate_count: int = 0
    gates_passed: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "release_id", require_non_empty_text(self.release_id, "release_id"))
        object.__setattr__(self, "version_id", require_non_empty_text(self.version_id, "version_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, ReleaseKind):
            raise ValueError("kind must be a ReleaseKind")
        if not isinstance(self.status, ReleaseStatus):
            raise ValueError("status must be a ReleaseStatus")
        object.__setattr__(self, "target_environment", require_non_empty_text(self.target_environment, "target_environment"))
        object.__setattr__(self, "gate_count", require_non_negative_int(self.gate_count, "gate_count"))
        object.__setattr__(self, "gates_passed", require_non_negative_int(self.gates_passed, "gates_passed"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReleaseGate(ContractRecord):
    """A gate that must pass before a release can proceed."""

    gate_id: str = ""
    release_id: str = ""
    tenant_id: str = ""
    gate_name: str = ""
    passed: bool = False
    reason: str = ""
    evaluated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", require_non_empty_text(self.gate_id, "gate_id"))
        object.__setattr__(self, "release_id", require_non_empty_text(self.release_id, "release_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "gate_name", require_non_empty_text(self.gate_name, "gate_name"))
        require_datetime_text(self.evaluated_at, "evaluated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PromotionRecord(ContractRecord):
    """A promotion of a release to an environment."""

    promotion_id: str = ""
    release_id: str = ""
    tenant_id: str = ""
    from_environment: str = ""
    to_environment: str = ""
    disposition: PromotionDisposition = PromotionDisposition.PROMOTED
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "promotion_id", require_non_empty_text(self.promotion_id, "promotion_id"))
        object.__setattr__(self, "release_id", require_non_empty_text(self.release_id, "release_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "from_environment", require_non_empty_text(self.from_environment, "from_environment"))
        object.__setattr__(self, "to_environment", require_non_empty_text(self.to_environment, "to_environment"))
        if not isinstance(self.disposition, PromotionDisposition):
            raise ValueError("disposition must be a PromotionDisposition")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RollbackRecord(ContractRecord):
    """A rollback of a release."""

    rollback_id: str = ""
    release_id: str = ""
    tenant_id: str = ""
    reason: str = ""
    status: RollbackStatus = RollbackStatus.INITIATED
    initiated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rollback_id", require_non_empty_text(self.rollback_id, "rollback_id"))
        object.__setattr__(self, "release_id", require_non_empty_text(self.release_id, "release_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        if not isinstance(self.status, RollbackStatus):
            raise ValueError("status must be a RollbackStatus")
        require_datetime_text(self.initiated_at, "initiated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LifecycleMilestone(ContractRecord):
    """A lifecycle milestone for a product version."""

    milestone_id: str = ""
    version_id: str = ""
    tenant_id: str = ""
    from_status: LifecycleStatus = LifecycleStatus.ACTIVE
    to_status: LifecycleStatus = LifecycleStatus.DEPRECATED
    reason: str = ""
    recorded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "milestone_id", require_non_empty_text(self.milestone_id, "milestone_id"))
        object.__setattr__(self, "version_id", require_non_empty_text(self.version_id, "version_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.from_status, LifecycleStatus):
            raise ValueError("from_status must be a LifecycleStatus")
        if not isinstance(self.to_status, LifecycleStatus):
            raise ValueError("to_status must be a LifecycleStatus")
        require_datetime_text(self.recorded_at, "recorded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReleaseAssessment(ContractRecord):
    """An assessment of release risk and readiness."""

    assessment_id: str = ""
    release_id: str = ""
    tenant_id: str = ""
    risk_level: ReleaseRiskLevel = ReleaseRiskLevel.LOW
    readiness_score: float = 1.0
    customer_impact_score: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "release_id", require_non_empty_text(self.release_id, "release_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.risk_level, ReleaseRiskLevel):
            raise ValueError("risk_level must be a ReleaseRiskLevel")
        object.__setattr__(self, "readiness_score", require_unit_float(self.readiness_score, "readiness_score"))
        object.__setattr__(self, "customer_impact_score", require_unit_float(self.customer_impact_score, "customer_impact_score"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReleaseSnapshot(ContractRecord):
    """Point-in-time release runtime state snapshot."""

    snapshot_id: str = ""
    total_versions: int = 0
    total_releases: int = 0
    total_gates: int = 0
    total_promotions: int = 0
    total_rollbacks: int = 0
    total_milestones: int = 0
    total_assessments: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_versions", require_non_negative_int(self.total_versions, "total_versions"))
        object.__setattr__(self, "total_releases", require_non_negative_int(self.total_releases, "total_releases"))
        object.__setattr__(self, "total_gates", require_non_negative_int(self.total_gates, "total_gates"))
        object.__setattr__(self, "total_promotions", require_non_negative_int(self.total_promotions, "total_promotions"))
        object.__setattr__(self, "total_rollbacks", require_non_negative_int(self.total_rollbacks, "total_rollbacks"))
        object.__setattr__(self, "total_milestones", require_non_negative_int(self.total_milestones, "total_milestones"))
        object.__setattr__(self, "total_assessments", require_non_negative_int(self.total_assessments, "total_assessments"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReleaseViolation(ContractRecord):
    """A violation detected in release operations."""

    violation_id: str = ""
    tenant_id: str = ""
    release_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "release_id", require_non_empty_text(self.release_id, "release_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReleaseClosureReport(ContractRecord):
    """Summary report for release runtime lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_versions: int = 0
    total_releases: int = 0
    total_promotions: int = 0
    total_rollbacks: int = 0
    total_milestones: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_versions", require_non_negative_int(self.total_versions, "total_versions"))
        object.__setattr__(self, "total_releases", require_non_negative_int(self.total_releases, "total_releases"))
        object.__setattr__(self, "total_promotions", require_non_negative_int(self.total_promotions, "total_promotions"))
        object.__setattr__(self, "total_rollbacks", require_non_negative_int(self.total_rollbacks, "total_rollbacks"))
        object.__setattr__(self, "total_milestones", require_non_negative_int(self.total_milestones, "total_milestones"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
