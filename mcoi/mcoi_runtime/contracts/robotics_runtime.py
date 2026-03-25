"""Purpose: Robotics / Control runtime contracts.
Governance scope: typed descriptors for workcells, actuators, sensors,
    control tasks, safety interlocks, control sequences, decisions,
    assessments, violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Task statuses follow strict lifecycle transitions.
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


class ControlMode(Enum):
    """Mode of control for a task."""
    MANUAL = "manual"
    SEMI_AUTO = "semi_auto"
    AUTOMATIC = "automatic"
    EMERGENCY_STOP = "emergency_stop"


class ActuatorStatus(Enum):
    """Status of an actuator."""
    IDLE = "idle"
    ACTIVE = "active"
    FAULTED = "faulted"
    LOCKED = "locked"
    MAINTENANCE = "maintenance"


class SensorStatus(Enum):
    """Status of a sensor."""
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    CALIBRATING = "calibrating"


class TaskExecutionStatus(Enum):
    """Execution status of a control task."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAULTED = "faulted"


class SafetyInterlockStatus(Enum):
    """Status of a safety interlock."""
    ARMED = "armed"
    TRIGGERED = "triggered"
    BYPASSED = "bypassed"
    CLEARED = "cleared"


class RoboticsRiskLevel(Enum):
    """Risk level for robotics assessment."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ControlTask(ContractRecord):
    """A control task for a robotics target."""

    task_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    target_ref: str = ""
    mode: ControlMode = ControlMode.MANUAL
    status: TaskExecutionStatus = TaskExecutionStatus.QUEUED
    sequence_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", require_non_empty_text(self.task_id, "task_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "target_ref", require_non_empty_text(self.target_ref, "target_ref"))
        if not isinstance(self.mode, ControlMode):
            raise ValueError("mode must be a ControlMode")
        if not isinstance(self.status, TaskExecutionStatus):
            raise ValueError("status must be a TaskExecutionStatus")
        object.__setattr__(self, "sequence_count", require_non_negative_int(self.sequence_count, "sequence_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ActuatorRecord(ContractRecord):
    """A registered actuator in a workcell."""

    actuator_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    cell_ref: str = ""
    status: ActuatorStatus = ActuatorStatus.IDLE
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "actuator_id", require_non_empty_text(self.actuator_id, "actuator_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "cell_ref", require_non_empty_text(self.cell_ref, "cell_ref"))
        if not isinstance(self.status, ActuatorStatus):
            raise ValueError("status must be an ActuatorStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SensorRecord(ContractRecord):
    """A registered sensor in a workcell."""

    sensor_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    cell_ref: str = ""
    status: SensorStatus = SensorStatus.ONLINE
    reading_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sensor_id", require_non_empty_text(self.sensor_id, "sensor_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "cell_ref", require_non_empty_text(self.cell_ref, "cell_ref"))
        if not isinstance(self.status, SensorStatus):
            raise ValueError("status must be a SensorStatus")
        object.__setattr__(self, "reading_count", require_non_negative_int(self.reading_count, "reading_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SafetyInterlock(ContractRecord):
    """A safety interlock for a workcell."""

    interlock_id: str = ""
    tenant_id: str = ""
    cell_ref: str = ""
    status: SafetyInterlockStatus = SafetyInterlockStatus.ARMED
    reason: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "interlock_id", require_non_empty_text(self.interlock_id, "interlock_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "cell_ref", require_non_empty_text(self.cell_ref, "cell_ref"))
        if not isinstance(self.status, SafetyInterlockStatus):
            raise ValueError("status must be a SafetyInterlockStatus")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ControlSequence(ContractRecord):
    """A control sequence linked to a task."""

    sequence_id: str = ""
    tenant_id: str = ""
    task_ref: str = ""
    step_count: int = 0
    completed_steps: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sequence_id", require_non_empty_text(self.sequence_id, "sequence_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "task_ref", require_non_empty_text(self.task_ref, "task_ref"))
        object.__setattr__(self, "step_count", require_non_negative_int(self.step_count, "step_count"))
        object.__setattr__(self, "completed_steps", require_non_negative_int(self.completed_steps, "completed_steps"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkcellRecord(ContractRecord):
    """A registered workcell."""

    cell_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    actuator_count: int = 0
    sensor_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cell_id", require_non_empty_text(self.cell_id, "cell_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "actuator_count", require_non_negative_int(self.actuator_count, "actuator_count"))
        object.__setattr__(self, "sensor_count", require_non_negative_int(self.sensor_count, "sensor_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RoboticsDecision(ContractRecord):
    """A decision related to a robotics task."""

    decision_id: str = ""
    tenant_id: str = ""
    task_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "task_ref", require_non_empty_text(self.task_ref, "task_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RoboticsAssessment(ContractRecord):
    """Assessment of robotics runtime health for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_cells: int = 0
    total_tasks: int = 0
    total_faults: int = 0
    availability_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_cells", require_non_negative_int(self.total_cells, "total_cells"))
        object.__setattr__(self, "total_tasks", require_non_negative_int(self.total_tasks, "total_tasks"))
        object.__setattr__(self, "total_faults", require_non_negative_int(self.total_faults, "total_faults"))
        object.__setattr__(self, "availability_rate", require_unit_float(self.availability_rate, "availability_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RoboticsSnapshot(ContractRecord):
    """Point-in-time snapshot of robotics runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_cells: int = 0
    total_actuators: int = 0
    total_sensors: int = 0
    total_tasks: int = 0
    total_interlocks: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_cells", require_non_negative_int(self.total_cells, "total_cells"))
        object.__setattr__(self, "total_actuators", require_non_negative_int(self.total_actuators, "total_actuators"))
        object.__setattr__(self, "total_sensors", require_non_negative_int(self.total_sensors, "total_sensors"))
        object.__setattr__(self, "total_tasks", require_non_negative_int(self.total_tasks, "total_tasks"))
        object.__setattr__(self, "total_interlocks", require_non_negative_int(self.total_interlocks, "total_interlocks"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RoboticsClosureReport(ContractRecord):
    """Closure report summarising robotics runtime state."""

    report_id: str = ""
    tenant_id: str = ""
    total_cells: int = 0
    total_tasks: int = 0
    total_faults: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_cells", require_non_negative_int(self.total_cells, "total_cells"))
        object.__setattr__(self, "total_tasks", require_non_negative_int(self.total_tasks, "total_tasks"))
        object.__setattr__(self, "total_faults", require_non_negative_int(self.total_faults, "total_faults"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
