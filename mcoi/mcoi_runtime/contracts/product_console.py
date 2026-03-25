"""Purpose: public product console / multi-tenant admin surface contracts.
Governance scope: typed descriptors for console surfaces, navigation nodes,
    admin panels, sessions, admin actions, decisions, snapshots, violations,
    assessments, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every console artefact references a tenant.
  - All outputs are frozen and traceable.
  - Multi-tenant isolation is enforced at the contract layer.
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


class ConsoleStatus(Enum):
    """Status of a console surface or session."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    MAINTENANCE = "maintenance"


class ViewMode(Enum):
    """View mode for an admin panel."""
    FULL = "full"
    RESTRICTED = "restricted"
    READ_ONLY = "read_only"
    HIDDEN = "hidden"


class AdminActionStatus(Enum):
    """Status of an admin action."""
    PENDING = "pending"
    EXECUTED = "executed"
    DENIED = "denied"
    ROLLED_BACK = "rolled_back"


class NavigationScope(Enum):
    """Scope of a navigation node."""
    TENANT = "tenant"
    WORKSPACE = "workspace"
    SERVICE = "service"
    PROGRAM = "program"
    GLOBAL = "global"


class SurfaceDisposition(Enum):
    """Disposition of a console surface."""
    VISIBLE = "visible"
    HIDDEN = "hidden"
    RESTRICTED = "restricted"
    LOCKED = "locked"


class ConsoleRole(Enum):
    """Role assigned to a console surface."""
    TENANT_ADMIN = "tenant_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    OPERATIONS_MANAGER = "operations_manager"
    CUSTOMER_ADMIN = "customer_admin"
    PARTNER_ADMIN = "partner_admin"
    COMPLIANCE_VIEWER = "compliance_viewer"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConsoleSurface(ContractRecord):
    """A registered console surface for a tenant."""

    surface_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: ConsoleStatus = ConsoleStatus.ACTIVE
    disposition: SurfaceDisposition = SurfaceDisposition.VISIBLE
    role: ConsoleRole = ConsoleRole.TENANT_ADMIN
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", require_non_empty_text(self.surface_id, "surface_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, ConsoleStatus):
            raise ValueError("status must be a ConsoleStatus")
        if not isinstance(self.disposition, SurfaceDisposition):
            raise ValueError("disposition must be a SurfaceDisposition")
        if not isinstance(self.role, ConsoleRole):
            raise ValueError("role must be a ConsoleRole")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class NavigationNode(ContractRecord):
    """A navigation node within a console surface."""

    node_id: str = ""
    tenant_id: str = ""
    surface_ref: str = ""
    parent_ref: str = ""
    label: str = ""
    scope: NavigationScope = NavigationScope.TENANT
    order: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_non_empty_text(self.node_id, "node_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "surface_ref", require_non_empty_text(self.surface_ref, "surface_ref"))
        object.__setattr__(self, "parent_ref", require_non_empty_text(self.parent_ref, "parent_ref"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        if not isinstance(self.scope, NavigationScope):
            raise ValueError("scope must be a NavigationScope")
        object.__setattr__(self, "order", require_non_negative_int(self.order, "order"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdminPanel(ContractRecord):
    """An admin panel within a console surface."""

    panel_id: str = ""
    tenant_id: str = ""
    surface_ref: str = ""
    display_name: str = ""
    target_runtime: str = ""
    view_mode: ViewMode = ViewMode.FULL
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "panel_id", require_non_empty_text(self.panel_id, "panel_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "surface_ref", require_non_empty_text(self.surface_ref, "surface_ref"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        if not isinstance(self.view_mode, ViewMode):
            raise ValueError("view_mode must be a ViewMode")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConsoleSession(ContractRecord):
    """A console session for an identity on a surface."""

    session_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    surface_ref: str = ""
    status: ConsoleStatus = ConsoleStatus.ACTIVE
    started_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        object.__setattr__(self, "surface_ref", require_non_empty_text(self.surface_ref, "surface_ref"))
        if not isinstance(self.status, ConsoleStatus):
            raise ValueError("status must be a ConsoleStatus")
        require_datetime_text(self.started_at, "started_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdminActionRecord(ContractRecord):
    """An admin action within a console session."""

    action_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    panel_ref: str = ""
    operation: str = ""
    status: AdminActionStatus = AdminActionStatus.PENDING
    performed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "panel_ref", require_non_empty_text(self.panel_ref, "panel_ref"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        if not isinstance(self.status, AdminActionStatus):
            raise ValueError("status must be an AdminActionStatus")
        require_datetime_text(self.performed_at, "performed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConsoleDecision(ContractRecord):
    """A decision associated with a console action."""

    decision_id: str = ""
    tenant_id: str = ""
    action_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "action_ref", require_non_empty_text(self.action_ref, "action_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConsoleSnapshot(ContractRecord):
    """Point-in-time snapshot of console state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_surfaces: int = 0
    total_panels: int = 0
    total_sessions: int = 0
    total_actions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_surfaces", require_non_negative_int(self.total_surfaces, "total_surfaces"))
        object.__setattr__(self, "total_panels", require_non_negative_int(self.total_panels, "total_panels"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_actions", require_non_negative_int(self.total_actions, "total_actions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConsoleViolation(ContractRecord):
    """A violation detected in console operations."""

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
class ConsoleAssessment(ContractRecord):
    """Assessment of console health for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_surfaces: int = 0
    total_active_sessions: int = 0
    action_success_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_surfaces", require_non_negative_int(self.total_surfaces, "total_surfaces"))
        object.__setattr__(self, "total_active_sessions", require_non_negative_int(self.total_active_sessions, "total_active_sessions"))
        object.__setattr__(self, "action_success_rate", require_unit_float(self.action_success_rate, "action_success_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConsoleClosureReport(ContractRecord):
    """Closure report for console operations for a tenant."""

    report_id: str = ""
    tenant_id: str = ""
    total_surfaces: int = 0
    total_panels: int = 0
    total_sessions: int = 0
    total_actions: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_surfaces", require_non_negative_int(self.total_surfaces, "total_surfaces"))
        object.__setattr__(self, "total_panels", require_non_negative_int(self.total_panels, "total_panels"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_actions", require_non_negative_int(self.total_actions, "total_actions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
