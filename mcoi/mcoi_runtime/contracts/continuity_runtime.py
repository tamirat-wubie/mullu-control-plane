"""Purpose: business continuity / disaster recovery runtime contracts.
Governance scope: typed descriptors for continuity plans, recovery plans,
    failover records, disruption events, recovery objectives, recovery
    executions, verification records, continuity snapshots, continuity
    violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every recovery references a valid continuity plan.
  - Failed verification keeps system in degraded state.
  - Completed recoveries cannot be re-opened.
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


class ContinuityStatus(Enum):
    """Status of a continuity plan."""
    ACTIVE = "active"
    DRAFT = "draft"
    ACTIVATED = "activated"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class RecoveryStatus(Enum):
    """Status of a recovery execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DisruptionSeverity(Enum):
    """Severity of a disruption event."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContinuityScope(Enum):
    """Scope of a continuity plan."""
    ENVIRONMENT = "environment"
    SERVICE = "service"
    CONNECTOR = "connector"
    ASSET = "asset"
    WORKSPACE = "workspace"
    TENANT = "tenant"


class FailoverDisposition(Enum):
    """Disposition of a failover action."""
    INITIATED = "initiated"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RecoveryVerificationStatus(Enum):
    """Status of recovery verification."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContinuityPlan(ContractRecord):
    """A business continuity plan."""

    plan_id: str = ""
    name: str = ""
    tenant_id: str = ""
    scope: ContinuityScope = ContinuityScope.SERVICE
    status: ContinuityStatus = ContinuityStatus.DRAFT
    scope_ref_id: str = ""
    rto_minutes: int = 0
    rpo_minutes: int = 0
    failover_target_ref: str = ""
    owner_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.scope, ContinuityScope):
            raise ValueError("scope must be a ContinuityScope")
        if not isinstance(self.status, ContinuityStatus):
            raise ValueError("status must be a ContinuityStatus")
        object.__setattr__(self, "rto_minutes", require_non_negative_int(self.rto_minutes, "rto_minutes"))
        object.__setattr__(self, "rpo_minutes", require_non_negative_int(self.rpo_minutes, "rpo_minutes"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RecoveryPlan(ContractRecord):
    """A disaster recovery plan linked to a continuity plan."""

    recovery_plan_id: str = ""
    plan_id: str = ""
    name: str = ""
    tenant_id: str = ""
    status: RecoveryStatus = RecoveryStatus.PENDING
    priority: int = 0
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "recovery_plan_id", require_non_empty_text(self.recovery_plan_id, "recovery_plan_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.status, RecoveryStatus):
            raise ValueError("status must be a RecoveryStatus")
        object.__setattr__(self, "priority", require_non_negative_int(self.priority, "priority"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FailoverRecord(ContractRecord):
    """A failover action triggered during disruption."""

    failover_id: str = ""
    plan_id: str = ""
    disruption_id: str = ""
    disposition: FailoverDisposition = FailoverDisposition.INITIATED
    source_ref: str = ""
    target_ref: str = ""
    initiated_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "failover_id", require_non_empty_text(self.failover_id, "failover_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "disruption_id", require_non_empty_text(self.disruption_id, "disruption_id"))
        if not isinstance(self.disposition, FailoverDisposition):
            raise ValueError("disposition must be a FailoverDisposition")
        require_datetime_text(self.initiated_at, "initiated_at")
        if self.completed_at:
            require_datetime_text(self.completed_at, "completed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DisruptionEvent(ContractRecord):
    """A disruption event that triggers continuity response."""

    disruption_id: str = ""
    tenant_id: str = ""
    scope: ContinuityScope = ContinuityScope.SERVICE
    scope_ref_id: str = ""
    severity: DisruptionSeverity = DisruptionSeverity.MEDIUM
    description: str = ""
    detected_at: str = ""
    resolved_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "disruption_id", require_non_empty_text(self.disruption_id, "disruption_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.scope, ContinuityScope):
            raise ValueError("scope must be a ContinuityScope")
        if not isinstance(self.severity, DisruptionSeverity):
            raise ValueError("severity must be a DisruptionSeverity")
        require_datetime_text(self.detected_at, "detected_at")
        if self.resolved_at:
            require_datetime_text(self.resolved_at, "resolved_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RecoveryObjective(ContractRecord):
    """An RTO/RPO-style recovery objective."""

    objective_id: str = ""
    plan_id: str = ""
    name: str = ""
    target_minutes: int = 0
    actual_minutes: int = 0
    met: bool = False
    evaluated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective_id", require_non_empty_text(self.objective_id, "objective_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "target_minutes", require_non_negative_int(self.target_minutes, "target_minutes"))
        object.__setattr__(self, "actual_minutes", require_non_negative_int(self.actual_minutes, "actual_minutes"))
        require_datetime_text(self.evaluated_at, "evaluated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RecoveryExecution(ContractRecord):
    """A recovery execution tracking progress."""

    execution_id: str = ""
    recovery_plan_id: str = ""
    disruption_id: str = ""
    status: RecoveryStatus = RecoveryStatus.PENDING
    executed_by: str = ""
    started_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        object.__setattr__(self, "recovery_plan_id", require_non_empty_text(self.recovery_plan_id, "recovery_plan_id"))
        object.__setattr__(self, "disruption_id", require_non_empty_text(self.disruption_id, "disruption_id"))
        if not isinstance(self.status, RecoveryStatus):
            raise ValueError("status must be a RecoveryStatus")
        object.__setattr__(self, "executed_by", require_non_empty_text(self.executed_by, "executed_by"))
        require_datetime_text(self.started_at, "started_at")
        if self.completed_at:
            require_datetime_text(self.completed_at, "completed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VerificationRecord(ContractRecord):
    """A verification of recovery success."""

    verification_id: str = ""
    execution_id: str = ""
    status: RecoveryVerificationStatus = RecoveryVerificationStatus.PENDING
    verified_by: str = ""
    confidence: float = 0.0
    reason: str = ""
    verified_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "verification_id", require_non_empty_text(self.verification_id, "verification_id"))
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        if not isinstance(self.status, RecoveryVerificationStatus):
            raise ValueError("status must be a RecoveryVerificationStatus")
        object.__setattr__(self, "verified_by", require_non_empty_text(self.verified_by, "verified_by"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.verified_at, "verified_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContinuitySnapshot(ContractRecord):
    """Point-in-time continuity state snapshot."""

    snapshot_id: str = ""
    total_plans: int = 0
    total_active_plans: int = 0
    total_recovery_plans: int = 0
    total_disruptions: int = 0
    total_failovers: int = 0
    total_recoveries: int = 0
    total_verifications: int = 0
    total_violations: int = 0
    total_objectives: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_plans", require_non_negative_int(self.total_plans, "total_plans"))
        object.__setattr__(self, "total_active_plans", require_non_negative_int(self.total_active_plans, "total_active_plans"))
        object.__setattr__(self, "total_recovery_plans", require_non_negative_int(self.total_recovery_plans, "total_recovery_plans"))
        object.__setattr__(self, "total_disruptions", require_non_negative_int(self.total_disruptions, "total_disruptions"))
        object.__setattr__(self, "total_failovers", require_non_negative_int(self.total_failovers, "total_failovers"))
        object.__setattr__(self, "total_recoveries", require_non_negative_int(self.total_recoveries, "total_recoveries"))
        object.__setattr__(self, "total_verifications", require_non_negative_int(self.total_verifications, "total_verifications"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_objectives", require_non_negative_int(self.total_objectives, "total_objectives"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContinuityViolation(ContractRecord):
    """A detected continuity/recovery violation."""

    violation_id: str = ""
    plan_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContinuityClosureReport(ContractRecord):
    """Summary report for continuity lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_plans: int = 0
    total_disruptions: int = 0
    total_failovers: int = 0
    total_recoveries: int = 0
    total_verifications_passed: int = 0
    total_verifications_failed: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_plans", require_non_negative_int(self.total_plans, "total_plans"))
        object.__setattr__(self, "total_disruptions", require_non_negative_int(self.total_disruptions, "total_disruptions"))
        object.__setattr__(self, "total_failovers", require_non_negative_int(self.total_failovers, "total_failovers"))
        object.__setattr__(self, "total_recoveries", require_non_negative_int(self.total_recoveries, "total_recoveries"))
        object.__setattr__(self, "total_verifications_passed", require_non_negative_int(self.total_verifications_passed, "total_verifications_passed"))
        object.__setattr__(self, "total_verifications_failed", require_non_negative_int(self.total_verifications_failed, "total_verifications_failed"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
