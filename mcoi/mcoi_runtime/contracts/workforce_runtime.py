"""Purpose: organization / workforce / role capacity runtime contracts.
Governance scope: typed descriptors for workers, role capacities, team
    capacities, assignment requests, assignment decisions, coverage gaps,
    load snapshots, workforce assessments, violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every worker references a tenant and role.
  - Capacity values are non-negative.
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
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkerStatus(Enum):
    """Status of a worker in the workforce."""
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    UNAVAILABLE = "unavailable"
    SUSPENDED = "suspended"
    OFFBOARDED = "offboarded"


class CapacityStatus(Enum):
    """Status of a capacity record."""
    NOMINAL = "nominal"
    STRAINED = "strained"
    OVERLOADED = "overloaded"
    CRITICAL = "critical"
    EMPTY = "empty"


class AssignmentDisposition(Enum):
    """Disposition of a work assignment decision."""
    ASSIGNED = "assigned"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class EscalationMode(Enum):
    """Mode of escalation for workforce issues."""
    MANAGER = "manager"
    BACKUP = "backup"
    POOL = "pool"
    EXTERNAL = "external"


class LoadBand(Enum):
    """Qualitative load band for a worker or role."""
    IDLE = "idle"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    OVERLOADED = "overloaded"


class CoverageStatus(Enum):
    """Status of coverage for a role or function."""
    COVERED = "covered"
    PARTIAL = "partial"
    GAP = "gap"
    CRITICAL_GAP = "critical_gap"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkerRecord(ContractRecord):
    """A worker in the workforce."""

    worker_id: str = ""
    tenant_id: str = ""
    role_ref: str = ""
    team_ref: str = ""
    display_name: str = ""
    status: WorkerStatus = WorkerStatus.ACTIVE
    max_assignments: int = 0
    current_assignments: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", require_non_empty_text(self.worker_id, "worker_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "role_ref", require_non_empty_text(self.role_ref, "role_ref"))
        object.__setattr__(self, "team_ref", require_non_empty_text(self.team_ref, "team_ref"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, WorkerStatus):
            raise ValueError("status must be a WorkerStatus")
        object.__setattr__(self, "max_assignments", require_positive_int(self.max_assignments, "max_assignments"))
        object.__setattr__(self, "current_assignments", require_non_negative_int(self.current_assignments, "current_assignments"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RoleCapacityRecord(ContractRecord):
    """Capacity record for a role."""

    capacity_id: str = ""
    tenant_id: str = ""
    role_ref: str = ""
    total_workers: int = 0
    available_workers: int = 0
    total_capacity: int = 0
    used_capacity: int = 0
    utilization: float = 0.0
    status: CapacityStatus = CapacityStatus.NOMINAL
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capacity_id", require_non_empty_text(self.capacity_id, "capacity_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "role_ref", require_non_empty_text(self.role_ref, "role_ref"))
        object.__setattr__(self, "total_workers", require_non_negative_int(self.total_workers, "total_workers"))
        object.__setattr__(self, "available_workers", require_non_negative_int(self.available_workers, "available_workers"))
        object.__setattr__(self, "total_capacity", require_non_negative_int(self.total_capacity, "total_capacity"))
        object.__setattr__(self, "used_capacity", require_non_negative_int(self.used_capacity, "used_capacity"))
        object.__setattr__(self, "utilization", require_unit_float(self.utilization, "utilization"))
        if not isinstance(self.status, CapacityStatus):
            raise ValueError("status must be a CapacityStatus")
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TeamCapacityRecord(ContractRecord):
    """Capacity record for a team."""

    capacity_id: str = ""
    tenant_id: str = ""
    team_ref: str = ""
    total_members: int = 0
    available_members: int = 0
    total_capacity: int = 0
    used_capacity: int = 0
    utilization: float = 0.0
    status: CapacityStatus = CapacityStatus.NOMINAL
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capacity_id", require_non_empty_text(self.capacity_id, "capacity_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "team_ref", require_non_empty_text(self.team_ref, "team_ref"))
        object.__setattr__(self, "total_members", require_non_negative_int(self.total_members, "total_members"))
        object.__setattr__(self, "available_members", require_non_negative_int(self.available_members, "available_members"))
        object.__setattr__(self, "total_capacity", require_non_negative_int(self.total_capacity, "total_capacity"))
        object.__setattr__(self, "used_capacity", require_non_negative_int(self.used_capacity, "used_capacity"))
        object.__setattr__(self, "utilization", require_unit_float(self.utilization, "utilization"))
        if not isinstance(self.status, CapacityStatus):
            raise ValueError("status must be a CapacityStatus")
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssignmentRequest(ContractRecord):
    """A request to assign work to a worker."""

    request_id: str = ""
    tenant_id: str = ""
    scope_ref_id: str = ""
    role_ref: str = ""
    priority: int = 1
    source_type: str = ""
    requested_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        object.__setattr__(self, "role_ref", require_non_empty_text(self.role_ref, "role_ref"))
        object.__setattr__(self, "priority", require_positive_int(self.priority, "priority"))
        object.__setattr__(self, "source_type", require_non_empty_text(self.source_type, "source_type"))
        require_datetime_text(self.requested_at, "requested_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssignmentDecision(ContractRecord):
    """A decision on a work assignment request."""

    decision_id: str = ""
    request_id: str = ""
    worker_id: str = ""
    disposition: AssignmentDisposition = AssignmentDisposition.ASSIGNED
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "worker_id", require_non_empty_text(self.worker_id, "worker_id"))
        if not isinstance(self.disposition, AssignmentDisposition):
            raise ValueError("disposition must be an AssignmentDisposition")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CoverageGap(ContractRecord):
    """A detected gap in workforce coverage."""

    gap_id: str = ""
    tenant_id: str = ""
    role_ref: str = ""
    team_ref: str = ""
    status: CoverageStatus = CoverageStatus.GAP
    available_workers: int = 0
    required_workers: int = 1
    escalation_mode: EscalationMode = EscalationMode.MANAGER
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "gap_id", require_non_empty_text(self.gap_id, "gap_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "role_ref", require_non_empty_text(self.role_ref, "role_ref"))
        object.__setattr__(self, "team_ref", require_non_empty_text(self.team_ref, "team_ref"))
        if not isinstance(self.status, CoverageStatus):
            raise ValueError("status must be a CoverageStatus")
        object.__setattr__(self, "available_workers", require_non_negative_int(self.available_workers, "available_workers"))
        object.__setattr__(self, "required_workers", require_positive_int(self.required_workers, "required_workers"))
        if not isinstance(self.escalation_mode, EscalationMode):
            raise ValueError("escalation_mode must be an EscalationMode")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LoadSnapshot(ContractRecord):
    """Point-in-time load snapshot for the workforce."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_workers: int = 0
    active_workers: int = 0
    total_assignments: int = 0
    total_capacity: int = 0
    used_capacity: int = 0
    utilization: float = 0.0
    load_band: LoadBand = LoadBand.IDLE
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_workers", require_non_negative_int(self.total_workers, "total_workers"))
        object.__setattr__(self, "active_workers", require_non_negative_int(self.active_workers, "active_workers"))
        object.__setattr__(self, "total_assignments", require_non_negative_int(self.total_assignments, "total_assignments"))
        object.__setattr__(self, "total_capacity", require_non_negative_int(self.total_capacity, "total_capacity"))
        object.__setattr__(self, "used_capacity", require_non_negative_int(self.used_capacity, "used_capacity"))
        object.__setattr__(self, "utilization", require_unit_float(self.utilization, "utilization"))
        if not isinstance(self.load_band, LoadBand):
            raise ValueError("load_band must be a LoadBand")
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkforceAssessment(ContractRecord):
    """Overall workforce assessment."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_workers: int = 0
    active_workers: int = 0
    total_roles: int = 0
    total_teams: int = 0
    total_requests: int = 0
    total_decisions: int = 0
    total_gaps: int = 0
    total_violations: int = 0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_workers", require_non_negative_int(self.total_workers, "total_workers"))
        object.__setattr__(self, "active_workers", require_non_negative_int(self.active_workers, "active_workers"))
        object.__setattr__(self, "total_roles", require_non_negative_int(self.total_roles, "total_roles"))
        object.__setattr__(self, "total_teams", require_non_negative_int(self.total_teams, "total_teams"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_gaps", require_non_negative_int(self.total_gaps, "total_gaps"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkforceViolation(ContractRecord):
    """A violation detected in workforce operations."""

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
class WorkforceClosureReport(ContractRecord):
    """Summary report for workforce runtime lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_workers: int = 0
    total_role_capacities: int = 0
    total_team_capacities: int = 0
    total_requests: int = 0
    total_decisions: int = 0
    total_gaps: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_workers", require_non_negative_int(self.total_workers, "total_workers"))
        object.__setattr__(self, "total_role_capacities", require_non_negative_int(self.total_role_capacities, "total_role_capacities"))
        object.__setattr__(self, "total_team_capacities", require_non_negative_int(self.total_team_capacities, "total_team_capacities"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_gaps", require_non_negative_int(self.total_gaps, "total_gaps"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
