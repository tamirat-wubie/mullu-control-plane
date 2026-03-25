"""Purpose: Factory / Production / Quality runtime contracts.
Governance scope: typed descriptors for plants, lines, stations, machines,
    work orders, batches, quality checks, downtime events, snapshots, and
    closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every factory entity references a tenant.
  - All outputs are frozen and traceable.
  - Quality verdicts bind to batches.
  - Downtime events bind to machines.
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


class FactoryStatus(Enum):
    """Status of a factory plant."""
    ACTIVE = "active"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    SHUTDOWN = "shutdown"


class WorkOrderStatus(Enum):
    """Status of a work order."""
    DRAFT = "draft"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MachineStatus(Enum):
    """Status of a machine."""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    DOWN = "down"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"


class BatchStatus(Enum):
    """Status of a production batch."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    SCRAPPED = "scrapped"


class QualityVerdict(Enum):
    """Quality check verdict."""
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL = "conditional"
    NOT_TESTED = "not_tested"


class MaintenanceDisposition(Enum):
    """Disposition of a maintenance / downtime event."""
    SCHEDULED = "scheduled"
    UNSCHEDULED = "unscheduled"
    EMERGENCY = "emergency"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlantRecord(ContractRecord):
    """A registered factory plant."""

    plant_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: FactoryStatus = FactoryStatus.ACTIVE
    line_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plant_id", require_non_empty_text(self.plant_id, "plant_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, FactoryStatus):
            raise ValueError("status must be a FactoryStatus")
        object.__setattr__(self, "line_count", require_non_negative_int(self.line_count, "line_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LineRecord(ContractRecord):
    """A production line within a plant."""

    line_id: str = ""
    tenant_id: str = ""
    plant_id: str = ""
    display_name: str = ""
    station_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "line_id", require_non_empty_text(self.line_id, "line_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "plant_id", require_non_empty_text(self.plant_id, "plant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "station_count", require_non_negative_int(self.station_count, "station_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class StationRecord(ContractRecord):
    """A station within a production line."""

    station_id: str = ""
    tenant_id: str = ""
    line_id: str = ""
    display_name: str = ""
    machine_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "station_id", require_non_empty_text(self.station_id, "station_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "line_id", require_non_empty_text(self.line_id, "line_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "machine_ref", require_non_empty_text(self.machine_ref, "machine_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkOrder(ContractRecord):
    """A work order for production."""

    order_id: str = ""
    tenant_id: str = ""
    plant_id: str = ""
    product_ref: str = ""
    status: WorkOrderStatus = WorkOrderStatus.DRAFT
    quantity: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "order_id", require_non_empty_text(self.order_id, "order_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "plant_id", require_non_empty_text(self.plant_id, "plant_id"))
        object.__setattr__(self, "product_ref", require_non_empty_text(self.product_ref, "product_ref"))
        if not isinstance(self.status, WorkOrderStatus):
            raise ValueError("status must be a WorkOrderStatus")
        object.__setattr__(self, "quantity", require_non_negative_int(self.quantity, "quantity"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BatchRecord(ContractRecord):
    """A production batch linked to a work order."""

    batch_id: str = ""
    tenant_id: str = ""
    order_id: str = ""
    status: BatchStatus = BatchStatus.PLANNED
    unit_count: int = 0
    yield_rate: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "batch_id", require_non_empty_text(self.batch_id, "batch_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "order_id", require_non_empty_text(self.order_id, "order_id"))
        if not isinstance(self.status, BatchStatus):
            raise ValueError("status must be a BatchStatus")
        object.__setattr__(self, "unit_count", require_non_negative_int(self.unit_count, "unit_count"))
        object.__setattr__(self, "yield_rate", require_unit_float(self.yield_rate, "yield_rate"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MachineRecord(ContractRecord):
    """A registered machine in the factory."""

    machine_id: str = ""
    tenant_id: str = ""
    station_ref: str = ""
    display_name: str = ""
    status: MachineStatus = MachineStatus.OPERATIONAL
    uptime_hours: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "machine_id", require_non_empty_text(self.machine_id, "machine_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "station_ref", require_non_empty_text(self.station_ref, "station_ref"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, MachineStatus):
            raise ValueError("status must be a MachineStatus")
        object.__setattr__(self, "uptime_hours", require_non_negative_int(self.uptime_hours, "uptime_hours"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class QualityCheck(ContractRecord):
    """A quality check result for a batch."""

    check_id: str = ""
    tenant_id: str = ""
    batch_id: str = ""
    verdict: QualityVerdict = QualityVerdict.NOT_TESTED
    defect_count: int = 0
    inspector_ref: str = ""
    checked_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "check_id", require_non_empty_text(self.check_id, "check_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "batch_id", require_non_empty_text(self.batch_id, "batch_id"))
        if not isinstance(self.verdict, QualityVerdict):
            raise ValueError("verdict must be a QualityVerdict")
        object.__setattr__(self, "defect_count", require_non_negative_int(self.defect_count, "defect_count"))
        object.__setattr__(self, "inspector_ref", require_non_empty_text(self.inspector_ref, "inspector_ref"))
        require_datetime_text(self.checked_at, "checked_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DowntimeEvent(ContractRecord):
    """A machine downtime event."""

    event_id: str = ""
    tenant_id: str = ""
    machine_id: str = ""
    reason: str = ""
    duration_minutes: int = 0
    disposition: MaintenanceDisposition = MaintenanceDisposition.UNSCHEDULED
    recorded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", require_non_empty_text(self.event_id, "event_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "machine_id", require_non_empty_text(self.machine_id, "machine_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "duration_minutes", require_non_negative_int(self.duration_minutes, "duration_minutes"))
        if not isinstance(self.disposition, MaintenanceDisposition):
            raise ValueError("disposition must be a MaintenanceDisposition")
        require_datetime_text(self.recorded_at, "recorded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FactorySnapshot(ContractRecord):
    """Point-in-time snapshot of factory runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_plants: int = 0
    total_lines: int = 0
    total_orders: int = 0
    total_batches: int = 0
    total_checks: int = 0
    total_downtime_events: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_plants", require_non_negative_int(self.total_plants, "total_plants"))
        object.__setattr__(self, "total_lines", require_non_negative_int(self.total_lines, "total_lines"))
        object.__setattr__(self, "total_orders", require_non_negative_int(self.total_orders, "total_orders"))
        object.__setattr__(self, "total_batches", require_non_negative_int(self.total_batches, "total_batches"))
        object.__setattr__(self, "total_checks", require_non_negative_int(self.total_checks, "total_checks"))
        object.__setattr__(self, "total_downtime_events", require_non_negative_int(self.total_downtime_events, "total_downtime_events"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FactoryClosureReport(ContractRecord):
    """Closure report summarising factory runtime state."""

    report_id: str = ""
    tenant_id: str = ""
    total_plants: int = 0
    total_orders: int = 0
    total_batches: int = 0
    total_checks: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_plants", require_non_negative_int(self.total_plants, "total_plants"))
        object.__setattr__(self, "total_orders", require_non_negative_int(self.total_orders, "total_orders"))
        object.__setattr__(self, "total_batches", require_non_negative_int(self.total_batches, "total_batches"))
        object.__setattr__(self, "total_checks", require_non_negative_int(self.total_checks, "total_checks"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FactoryAssessment(ContractRecord):
    """Assessment of factory runtime health for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_plants: int = 0
    total_orders: int = 0
    total_batches: int = 0
    total_checks: int = 0
    total_violations: int = 0
    quality_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_plants", require_non_negative_int(self.total_plants, "total_plants"))
        object.__setattr__(self, "total_orders", require_non_negative_int(self.total_orders, "total_orders"))
        object.__setattr__(self, "total_batches", require_non_negative_int(self.total_batches, "total_batches"))
        object.__setattr__(self, "total_checks", require_non_negative_int(self.total_checks, "total_checks"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "quality_rate", require_unit_float(self.quality_rate, "quality_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
