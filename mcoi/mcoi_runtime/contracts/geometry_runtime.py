"""Purpose: geometry / spatial runtime contracts.
Governance scope: typed descriptors for geometry points, shapes, spatial regions,
    paths, constraints, decisions, assessments, violations, snapshots, and
    closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Coordinate fields reject bool, inf, and nan.
  - Boolean decision fields are strictly validated.
"""

from __future__ import annotations

import math
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
# Local validators
# ---------------------------------------------------------------------------


def _require_finite_float(value: float, field_name: str) -> float:
    """Validate that a float is finite (may be negative). Rejects bool, inf, nan."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    fval = float(value)
    if not math.isfinite(fval):
        raise ValueError(f"{field_name} must be finite")
    return fval


def _require_bool(value: bool, field_name: str) -> bool:
    """Validate that a value is strictly a bool."""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a bool")
    return value


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GeometryStatus(Enum):
    """Lifecycle status of a geometry entity."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class GeometryKind(Enum):
    """Category of geometric shape."""
    POINT = "point"
    LINE = "line"
    POLYGON = "polygon"
    BOX = "box"
    CIRCLE = "circle"
    VOLUME = "volume"


class SpatialRelation(Enum):
    """Relation between two spatial entities."""
    CONTAINS = "contains"
    INSIDE = "inside"
    OVERLAPS = "overlaps"
    DISJOINT = "disjoint"
    ADJACENT = "adjacent"
    INTERSECTS = "intersects"


class RegionDisposition(Enum):
    """Disposition of a spatial region."""
    VALID = "valid"
    RESTRICTED = "restricted"
    CLOSED = "closed"
    HAZARDOUS = "hazardous"


class RoutingDisposition(Enum):
    """Disposition of a spatial path for routing."""
    ROUTABLE = "routable"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class SpatialRiskLevel(Enum):
    """Risk level associated with spatial operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GeometryPoint(ContractRecord):
    """A point in 3D space."""

    point_id: str = ""
    tenant_id: str = ""
    label: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "point_id", require_non_empty_text(self.point_id, "point_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        object.__setattr__(self, "x", _require_finite_float(self.x, "x"))
        object.__setattr__(self, "y", _require_finite_float(self.y, "y"))
        object.__setattr__(self, "z", _require_finite_float(self.z, "z"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GeometryShape(ContractRecord):
    """A bounding-box shape in 2D space."""

    shape_id: str = ""
    tenant_id: str = ""
    kind: GeometryKind = GeometryKind.BOX
    label: str = ""
    x_min: float = 0.0
    y_min: float = 0.0
    x_max: float = 0.0
    y_max: float = 0.0
    area: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "shape_id", require_non_empty_text(self.shape_id, "shape_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, GeometryKind):
            raise ValueError("kind must be a GeometryKind")
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        object.__setattr__(self, "x_min", _require_finite_float(self.x_min, "x_min"))
        object.__setattr__(self, "y_min", _require_finite_float(self.y_min, "y_min"))
        object.__setattr__(self, "x_max", _require_finite_float(self.x_max, "x_max"))
        object.__setattr__(self, "y_max", _require_finite_float(self.y_max, "y_max"))
        object.__setattr__(self, "area", require_non_negative_float(self.area, "area"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpatialRegion(ContractRecord):
    """A named spatial region with disposition."""

    region_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    disposition: RegionDisposition = RegionDisposition.VALID
    parent_ref: str = "root"
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "region_id", require_non_empty_text(self.region_id, "region_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.disposition, RegionDisposition):
            raise ValueError("disposition must be a RegionDisposition")
        object.__setattr__(self, "parent_ref", require_non_empty_text(self.parent_ref, "parent_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpatialPath(ContractRecord):
    """A spatial path with routing disposition."""

    path_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    node_count: int = 0
    total_distance: float = 0.0
    routing: RoutingDisposition = RoutingDisposition.ROUTABLE
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", require_non_empty_text(self.path_id, "path_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "node_count", require_non_negative_int(self.node_count, "node_count"))
        object.__setattr__(self, "total_distance", require_non_negative_float(self.total_distance, "total_distance"))
        if not isinstance(self.routing, RoutingDisposition):
            raise ValueError("routing must be a RoutingDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpatialConstraint(ContractRecord):
    """A spatial constraint between two targets."""

    constraint_id: str = ""
    tenant_id: str = ""
    kind: str = ""
    target_a_ref: str = ""
    target_b_ref: str = ""
    threshold: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", require_non_empty_text(self.constraint_id, "constraint_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "kind", require_non_empty_text(self.kind, "kind"))
        object.__setattr__(self, "target_a_ref", require_non_empty_text(self.target_a_ref, "target_a_ref"))
        object.__setattr__(self, "target_b_ref", require_non_empty_text(self.target_b_ref, "target_b_ref"))
        object.__setattr__(self, "threshold", require_non_negative_float(self.threshold, "threshold"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpatialDecision(ContractRecord):
    """A decision resulting from constraint evaluation."""

    decision_id: str = ""
    tenant_id: str = ""
    constraint_ref: str = ""
    passed: bool = True
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "constraint_ref", require_non_empty_text(self.constraint_ref, "constraint_ref"))
        object.__setattr__(self, "passed", _require_bool(self.passed, "passed"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpatialAssessment(ContractRecord):
    """Assessment of spatial compliance for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_regions: int = 0
    total_shapes: int = 0
    total_violations: int = 0
    compliance_rate: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_regions", require_non_negative_int(self.total_regions, "total_regions"))
        object.__setattr__(self, "total_shapes", require_non_negative_int(self.total_shapes, "total_shapes"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "compliance_rate", require_unit_float(self.compliance_rate, "compliance_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpatialViolation(ContractRecord):
    """A violation detected in spatial operations."""

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
class SpatialSnapshot(ContractRecord):
    """Point-in-time snapshot of spatial runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_points: int = 0
    total_shapes: int = 0
    total_regions: int = 0
    total_paths: int = 0
    total_constraints: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_points", require_non_negative_int(self.total_points, "total_points"))
        object.__setattr__(self, "total_shapes", require_non_negative_int(self.total_shapes, "total_shapes"))
        object.__setattr__(self, "total_regions", require_non_negative_int(self.total_regions, "total_regions"))
        object.__setattr__(self, "total_paths", require_non_negative_int(self.total_paths, "total_paths"))
        object.__setattr__(self, "total_constraints", require_non_negative_int(self.total_constraints, "total_constraints"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpatialClosureReport(ContractRecord):
    """Final closure report for spatial runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_points: int = 0
    total_shapes: int = 0
    total_regions: int = 0
    total_paths: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_points", require_non_negative_int(self.total_points, "total_points"))
        object.__setattr__(self, "total_shapes", require_non_negative_int(self.total_shapes, "total_shapes"))
        object.__setattr__(self, "total_regions", require_non_negative_int(self.total_regions, "total_regions"))
        object.__setattr__(self, "total_paths", require_non_negative_int(self.total_paths, "total_paths"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
