"""Purpose: 3D / digital twin runtime contracts.
Governance scope: typed descriptors for digital twin models, objects, assemblies,
    state records, telemetry bindings, sync records, assessments, violations,
    snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - RETIRED models cannot be reactivated.
  - Health score is always a unit float [0.0, 1.0].
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


class TwinStatus(Enum):
    """Lifecycle status of a digital twin model."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    RETIRED = "retired"


class TwinObjectKind(Enum):
    """Kind of object within a digital twin."""
    SITE = "site"
    LINE = "line"
    STATION = "station"
    MACHINE = "machine"
    COMPONENT = "component"
    SENSOR = "sensor"


class TwinStateDisposition(Enum):
    """Disposition of a twin object's state."""
    NOMINAL = "nominal"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class TwinLifecycleStatus(Enum):
    """Lifecycle status for a twin entity."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class TwinSyncStatus(Enum):
    """Synchronization status of a twin object."""
    SYNCED = "synced"
    STALE = "stale"
    DIVERGED = "diverged"
    DISCONNECTED = "disconnected"


class TwinRiskLevel(Enum):
    """Risk level for twin operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TwinModel(ContractRecord):
    """A digital twin model representing a physical system."""

    model_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: TwinStatus = TwinStatus.ACTIVE
    object_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", require_non_empty_text(self.model_id, "model_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, TwinStatus):
            raise ValueError("status must be a TwinStatus")
        object.__setattr__(self, "object_count", require_non_negative_int(self.object_count, "object_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TwinObject(ContractRecord):
    """An object within a digital twin model."""

    object_id: str = ""
    tenant_id: str = ""
    model_ref: str = ""
    kind: TwinObjectKind = TwinObjectKind.MACHINE
    display_name: str = ""
    parent_ref: str = "root"
    state: TwinStateDisposition = TwinStateDisposition.NOMINAL
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "object_id", require_non_empty_text(self.object_id, "object_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "model_ref", require_non_empty_text(self.model_ref, "model_ref"))
        if not isinstance(self.kind, TwinObjectKind):
            raise ValueError("kind must be a TwinObjectKind")
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "parent_ref", require_non_empty_text(self.parent_ref, "parent_ref"))
        if not isinstance(self.state, TwinStateDisposition):
            raise ValueError("state must be a TwinStateDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TwinAssembly(ContractRecord):
    """An assembly relationship between two twin objects."""

    assembly_id: str = ""
    tenant_id: str = ""
    parent_object_ref: str = ""
    child_object_ref: str = ""
    depth: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assembly_id", require_non_empty_text(self.assembly_id, "assembly_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "parent_object_ref", require_non_empty_text(self.parent_object_ref, "parent_object_ref"))
        object.__setattr__(self, "child_object_ref", require_non_empty_text(self.child_object_ref, "child_object_ref"))
        object.__setattr__(self, "depth", require_non_negative_int(self.depth, "depth"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TwinStateRecord(ContractRecord):
    """A state record bound to a twin object."""

    state_id: str = ""
    tenant_id: str = ""
    object_ref: str = ""
    disposition: TwinStateDisposition = TwinStateDisposition.NOMINAL
    source_runtime: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", require_non_empty_text(self.state_id, "state_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "object_ref", require_non_empty_text(self.object_ref, "object_ref"))
        if not isinstance(self.disposition, TwinStateDisposition):
            raise ValueError("disposition must be a TwinStateDisposition")
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        require_datetime_text(self.updated_at, "updated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TwinTelemetryBinding(ContractRecord):
    """A binding between a twin object and a telemetry source."""

    binding_id: str = ""
    tenant_id: str = ""
    object_ref: str = ""
    telemetry_ref: str = ""
    source_runtime: str = ""
    bound_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "object_ref", require_non_empty_text(self.object_ref, "object_ref"))
        object.__setattr__(self, "telemetry_ref", require_non_empty_text(self.telemetry_ref, "telemetry_ref"))
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        require_datetime_text(self.bound_at, "bound_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TwinSyncRecord(ContractRecord):
    """A synchronization record for a twin object."""

    sync_id: str = ""
    tenant_id: str = ""
    object_ref: str = ""
    status: TwinSyncStatus = TwinSyncStatus.SYNCED
    last_synced_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sync_id", require_non_empty_text(self.sync_id, "sync_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "object_ref", require_non_empty_text(self.object_ref, "object_ref"))
        if not isinstance(self.status, TwinSyncStatus):
            raise ValueError("status must be a TwinSyncStatus")
        require_datetime_text(self.last_synced_at, "last_synced_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TwinAssessment(ContractRecord):
    """Assessment of digital twin health for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_objects: int = 0
    total_nominal: int = 0
    total_degraded: int = 0
    health_score: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_objects", require_non_negative_int(self.total_objects, "total_objects"))
        object.__setattr__(self, "total_nominal", require_non_negative_int(self.total_nominal, "total_nominal"))
        object.__setattr__(self, "total_degraded", require_non_negative_int(self.total_degraded, "total_degraded"))
        object.__setattr__(self, "health_score", require_unit_float(self.health_score, "health_score"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TwinViolation(ContractRecord):
    """A violation detected in the digital twin lifecycle."""

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
class TwinSnapshot(ContractRecord):
    """Point-in-time snapshot of digital twin runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_models: int = 0
    total_objects: int = 0
    total_assemblies: int = 0
    total_states: int = 0
    total_bindings: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_models", require_non_negative_int(self.total_models, "total_models"))
        object.__setattr__(self, "total_objects", require_non_negative_int(self.total_objects, "total_objects"))
        object.__setattr__(self, "total_assemblies", require_non_negative_int(self.total_assemblies, "total_assemblies"))
        object.__setattr__(self, "total_states", require_non_negative_int(self.total_states, "total_states"))
        object.__setattr__(self, "total_bindings", require_non_negative_int(self.total_bindings, "total_bindings"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TwinClosureReport(ContractRecord):
    """Final closure report for digital twin runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_models: int = 0
    total_objects: int = 0
    total_assemblies: int = 0
    total_states: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_models", require_non_negative_int(self.total_models, "total_models"))
        object.__setattr__(self, "total_objects", require_non_negative_int(self.total_objects, "total_objects"))
        object.__setattr__(self, "total_assemblies", require_non_negative_int(self.total_assemblies, "total_assemblies"))
        object.__setattr__(self, "total_states", require_non_negative_int(self.total_states, "total_states"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
