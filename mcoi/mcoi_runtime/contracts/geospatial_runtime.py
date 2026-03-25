"""Purpose: Geospatial / Spatial runtime contracts.
Governance scope: typed descriptors for geo-features, territories, routes,
    depots, sites, decisions, assessments, violations, snapshots, and
    closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Latitude/longitude fields reject bool, inf, and nan.
  - Distance fields are non-negative floats.
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


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GeoStatus(Enum):
    """Status of a geospatial feature."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RESTRICTED = "restricted"
    CLOSED = "closed"


class GeoFeatureKind(Enum):
    """Kind of geospatial feature."""
    POINT = "point"
    ROUTE = "route"
    REGION = "region"
    DEPOT = "depot"
    SITE = "site"
    ZONE = "zone"


class TerritoryDisposition(Enum):
    """Disposition of a territory."""
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    CONTESTED = "contested"
    RESTRICTED = "restricted"


class RouteStatus(Enum):
    """Status of a route."""
    OPEN = "open"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class DistanceUnit(Enum):
    """Unit of distance measurement."""
    METERS = "meters"
    KILOMETERS = "kilometers"
    MILES = "miles"
    NAUTICAL_MILES = "nautical_miles"


class GeoRiskLevel(Enum):
    """Risk level for geospatial assessment."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GeoFeature(ContractRecord):
    """A registered geospatial feature."""

    feature_id: str = ""
    tenant_id: str = ""
    kind: GeoFeatureKind = GeoFeatureKind.POINT
    display_name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    status: GeoStatus = GeoStatus.ACTIVE
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_id", require_non_empty_text(self.feature_id, "feature_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, GeoFeatureKind):
            raise ValueError("kind must be a GeoFeatureKind")
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "latitude", _require_finite_float(self.latitude, "latitude"))
        object.__setattr__(self, "longitude", _require_finite_float(self.longitude, "longitude"))
        if not isinstance(self.status, GeoStatus):
            raise ValueError("status must be a GeoStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TerritoryRecord(ContractRecord):
    """A registered territory."""

    territory_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    disposition: TerritoryDisposition = TerritoryDisposition.UNASSIGNED
    assigned_ref: str = ""
    feature_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "territory_id", require_non_empty_text(self.territory_id, "territory_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.disposition, TerritoryDisposition):
            raise ValueError("disposition must be a TerritoryDisposition")
        # assigned_ref may be empty for UNASSIGNED territories
        object.__setattr__(self, "feature_count", require_non_negative_int(self.feature_count, "feature_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RouteRecord(ContractRecord):
    """A registered route between two references."""

    route_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    origin_ref: str = ""
    destination_ref: str = ""
    distance: float = 0.0
    unit: DistanceUnit = DistanceUnit.METERS
    status: RouteStatus = RouteStatus.OPEN
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", require_non_empty_text(self.route_id, "route_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "origin_ref", require_non_empty_text(self.origin_ref, "origin_ref"))
        object.__setattr__(self, "destination_ref", require_non_empty_text(self.destination_ref, "destination_ref"))
        object.__setattr__(self, "distance", require_non_negative_float(self.distance, "distance"))
        if not isinstance(self.unit, DistanceUnit):
            raise ValueError("unit must be a DistanceUnit")
        if not isinstance(self.status, RouteStatus):
            raise ValueError("status must be a RouteStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DepotRecord(ContractRecord):
    """A registered depot linked to a geo-feature."""

    depot_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    feature_ref: str = ""
    capacity: int = 0
    current_load: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "depot_id", require_non_empty_text(self.depot_id, "depot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "feature_ref", require_non_empty_text(self.feature_ref, "feature_ref"))
        object.__setattr__(self, "capacity", require_non_negative_int(self.capacity, "capacity"))
        object.__setattr__(self, "current_load", require_non_negative_int(self.current_load, "current_load"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SiteRecord(ContractRecord):
    """A registered site linked to a feature and territory."""

    site_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    feature_ref: str = ""
    territory_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "site_id", require_non_empty_text(self.site_id, "site_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "feature_ref", require_non_empty_text(self.feature_ref, "feature_ref"))
        object.__setattr__(self, "territory_ref", require_non_empty_text(self.territory_ref, "territory_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GeoDecision(ContractRecord):
    """A decision related to a geospatial feature."""

    decision_id: str = ""
    tenant_id: str = ""
    feature_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "feature_ref", require_non_empty_text(self.feature_ref, "feature_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GeoAssessment(ContractRecord):
    """Assessment of geospatial runtime health for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_features: int = 0
    total_territories: int = 0
    total_routes: int = 0
    coverage_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_features", require_non_negative_int(self.total_features, "total_features"))
        object.__setattr__(self, "total_territories", require_non_negative_int(self.total_territories, "total_territories"))
        object.__setattr__(self, "total_routes", require_non_negative_int(self.total_routes, "total_routes"))
        object.__setattr__(self, "coverage_rate", require_unit_float(self.coverage_rate, "coverage_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GeoViolation(ContractRecord):
    """A geospatial violation record."""

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
class GeoSnapshot(ContractRecord):
    """Point-in-time snapshot of geospatial runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_features: int = 0
    total_territories: int = 0
    total_routes: int = 0
    total_depots: int = 0
    total_sites: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_features", require_non_negative_int(self.total_features, "total_features"))
        object.__setattr__(self, "total_territories", require_non_negative_int(self.total_territories, "total_territories"))
        object.__setattr__(self, "total_routes", require_non_negative_int(self.total_routes, "total_routes"))
        object.__setattr__(self, "total_depots", require_non_negative_int(self.total_depots, "total_depots"))
        object.__setattr__(self, "total_sites", require_non_negative_int(self.total_sites, "total_sites"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GeoClosureReport(ContractRecord):
    """Closure report summarising geospatial runtime state."""

    report_id: str = ""
    tenant_id: str = ""
    total_features: int = 0
    total_territories: int = 0
    total_routes: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_features", require_non_negative_int(self.total_features, "total_features"))
        object.__setattr__(self, "total_territories", require_non_negative_int(self.total_territories, "total_territories"))
        object.__setattr__(self, "total_routes", require_non_negative_int(self.total_routes, "total_routes"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
