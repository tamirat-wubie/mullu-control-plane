"""Purpose: asset / configuration / inventory runtime contracts.
Governance scope: typed descriptors for assets, configuration items,
    inventory records, asset assignments, asset dependencies, lifecycle
    events, asset assessments, asset snapshots, asset violations, and
    closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every asset has explicit kind and owner.
  - Retired assets cannot be assigned.
  - Dependencies must reference valid assets.
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


class AssetStatus(Enum):
    """Status of an asset."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"
    DISPOSED = "disposed"


class AssetKind(Enum):
    """Kind of asset."""
    HARDWARE = "hardware"
    SOFTWARE = "software"
    LICENSE = "license"
    SERVICE = "service"
    INFRASTRUCTURE = "infrastructure"
    DATA = "data"


class ConfigurationItemStatus(Enum):
    """Status of a configuration item."""
    ACTIVE = "active"
    PENDING = "pending"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class InventoryDisposition(Enum):
    """Disposition of an inventory record."""
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    RESERVED = "reserved"
    DEPLETED = "depleted"
    EXPIRED = "expired"


class OwnershipType(Enum):
    """Type of asset ownership."""
    OWNED = "owned"
    LEASED = "leased"
    LICENSED = "licensed"
    SHARED = "shared"
    VENDOR_MANAGED = "vendor_managed"


class LifecycleDisposition(Enum):
    """Disposition of a lifecycle event."""
    PROVISIONED = "provisioned"
    DEPLOYED = "deployed"
    UPGRADED = "upgraded"
    DECOMMISSIONED = "decommissioned"
    TRANSFERRED = "transferred"
    RENEWED = "renewed"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AssetRecord(ContractRecord):
    """A registered asset."""

    asset_id: str = ""
    name: str = ""
    tenant_id: str = ""
    kind: AssetKind = AssetKind.HARDWARE
    status: AssetStatus = AssetStatus.ACTIVE
    ownership: OwnershipType = OwnershipType.OWNED
    owner_ref: str = ""
    vendor_ref: str = ""
    value: float = 0.0
    registered_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_id", require_non_empty_text(self.asset_id, "asset_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, AssetKind):
            raise ValueError("kind must be an AssetKind")
        if not isinstance(self.status, AssetStatus):
            raise ValueError("status must be an AssetStatus")
        if not isinstance(self.ownership, OwnershipType):
            raise ValueError("ownership must be an OwnershipType")
        object.__setattr__(self, "value", require_non_negative_float(self.value, "value"))
        require_datetime_text(self.registered_at, "registered_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConfigurationItem(ContractRecord):
    """A configuration item in the CMDB."""

    ci_id: str = ""
    asset_id: str = ""
    name: str = ""
    status: ConfigurationItemStatus = ConfigurationItemStatus.ACTIVE
    environment_ref: str = ""
    workspace_ref: str = ""
    version: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "ci_id", require_non_empty_text(self.ci_id, "ci_id"))
        object.__setattr__(self, "asset_id", require_non_empty_text(self.asset_id, "asset_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.status, ConfigurationItemStatus):
            raise ValueError("status must be a ConfigurationItemStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InventoryRecord(ContractRecord):
    """An inventory record tracking quantity and disposition."""

    inventory_id: str = ""
    asset_id: str = ""
    tenant_id: str = ""
    disposition: InventoryDisposition = InventoryDisposition.AVAILABLE
    total_quantity: int = 0
    assigned_quantity: int = 0
    available_quantity: int = 0
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "inventory_id", require_non_empty_text(self.inventory_id, "inventory_id"))
        object.__setattr__(self, "asset_id", require_non_empty_text(self.asset_id, "asset_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, InventoryDisposition):
            raise ValueError("disposition must be an InventoryDisposition")
        object.__setattr__(self, "total_quantity", require_non_negative_int(self.total_quantity, "total_quantity"))
        object.__setattr__(self, "assigned_quantity", require_non_negative_int(self.assigned_quantity, "assigned_quantity"))
        object.__setattr__(self, "available_quantity", require_non_negative_int(self.available_quantity, "available_quantity"))
        require_datetime_text(self.updated_at, "updated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssetAssignment(ContractRecord):
    """An assignment of an asset to a scope (campaign, program, environment)."""

    assignment_id: str = ""
    asset_id: str = ""
    scope_ref_id: str = ""
    scope_ref_type: str = ""
    assigned_by: str = ""
    assigned_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignment_id", require_non_empty_text(self.assignment_id, "assignment_id"))
        object.__setattr__(self, "asset_id", require_non_empty_text(self.asset_id, "asset_id"))
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        object.__setattr__(self, "scope_ref_type", require_non_empty_text(self.scope_ref_type, "scope_ref_type"))
        object.__setattr__(self, "assigned_by", require_non_empty_text(self.assigned_by, "assigned_by"))
        require_datetime_text(self.assigned_at, "assigned_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssetDependency(ContractRecord):
    """A dependency between two assets."""

    dependency_id: str = ""
    asset_id: str = ""
    depends_on_asset_id: str = ""
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dependency_id", require_non_empty_text(self.dependency_id, "dependency_id"))
        object.__setattr__(self, "asset_id", require_non_empty_text(self.asset_id, "asset_id"))
        object.__setattr__(self, "depends_on_asset_id", require_non_empty_text(self.depends_on_asset_id, "depends_on_asset_id"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LifecycleEvent(ContractRecord):
    """A lifecycle event for an asset."""

    event_id: str = ""
    asset_id: str = ""
    disposition: LifecycleDisposition = LifecycleDisposition.PROVISIONED
    description: str = ""
    performed_by: str = ""
    performed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", require_non_empty_text(self.event_id, "event_id"))
        object.__setattr__(self, "asset_id", require_non_empty_text(self.asset_id, "asset_id"))
        if not isinstance(self.disposition, LifecycleDisposition):
            raise ValueError("disposition must be a LifecycleDisposition")
        object.__setattr__(self, "performed_by", require_non_empty_text(self.performed_by, "performed_by"))
        require_datetime_text(self.performed_at, "performed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssetAssessment(ContractRecord):
    """A health/risk assessment of an asset."""

    assessment_id: str = ""
    asset_id: str = ""
    health_score: float = 0.0
    risk_score: float = 0.0
    assessed_by: str = ""
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "asset_id", require_non_empty_text(self.asset_id, "asset_id"))
        object.__setattr__(self, "health_score", require_unit_float(self.health_score, "health_score"))
        object.__setattr__(self, "risk_score", require_unit_float(self.risk_score, "risk_score"))
        object.__setattr__(self, "assessed_by", require_non_empty_text(self.assessed_by, "assessed_by"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssetSnapshot(ContractRecord):
    """Point-in-time asset state snapshot."""

    snapshot_id: str = ""
    total_assets: int = 0
    total_active: int = 0
    total_retired: int = 0
    total_config_items: int = 0
    total_inventory: int = 0
    total_assignments: int = 0
    total_dependencies: int = 0
    total_violations: int = 0
    total_asset_value: float = 0.0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_assets", require_non_negative_int(self.total_assets, "total_assets"))
        object.__setattr__(self, "total_active", require_non_negative_int(self.total_active, "total_active"))
        object.__setattr__(self, "total_retired", require_non_negative_int(self.total_retired, "total_retired"))
        object.__setattr__(self, "total_config_items", require_non_negative_int(self.total_config_items, "total_config_items"))
        object.__setattr__(self, "total_inventory", require_non_negative_int(self.total_inventory, "total_inventory"))
        object.__setattr__(self, "total_assignments", require_non_negative_int(self.total_assignments, "total_assignments"))
        object.__setattr__(self, "total_dependencies", require_non_negative_int(self.total_dependencies, "total_dependencies"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_asset_value", require_non_negative_float(self.total_asset_value, "total_asset_value"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssetViolation(ContractRecord):
    """A detected asset/inventory violation."""

    violation_id: str = ""
    asset_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "asset_id", require_non_empty_text(self.asset_id, "asset_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssetClosureReport(ContractRecord):
    """Summary report for asset lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_assets: int = 0
    total_active: int = 0
    total_retired: int = 0
    total_assignments: int = 0
    total_dependencies: int = 0
    total_asset_value: float = 0.0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_assets", require_non_negative_int(self.total_assets, "total_assets"))
        object.__setattr__(self, "total_active", require_non_negative_int(self.total_active, "total_active"))
        object.__setattr__(self, "total_retired", require_non_negative_int(self.total_retired, "total_retired"))
        object.__setattr__(self, "total_assignments", require_non_negative_int(self.total_assignments, "total_assignments"))
        object.__setattr__(self, "total_dependencies", require_non_negative_int(self.total_dependencies, "total_dependencies"))
        object.__setattr__(self, "total_asset_value", require_non_negative_float(self.total_asset_value, "total_asset_value"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
