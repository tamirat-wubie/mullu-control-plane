"""Purpose: tenant / workspace / environment isolation runtime contracts.
Governance scope: typed descriptors for tenants, workspaces, environments,
    boundary policies, workspace bindings, environment promotions, isolation
    violations, tenant health, tenant decisions, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every tenant has explicit status and isolation level.
  - Workspaces belong to exactly one tenant.
  - Environments belong to exactly one workspace.
  - Boundary policies enforce isolation between scopes.
  - Promotions are gated by compliance checks.
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


class TenantStatus(Enum):
    """Status of a tenant."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PROVISIONING = "provisioning"
    DECOMMISSIONING = "decommissioning"
    ARCHIVED = "archived"


class WorkspaceStatus(Enum):
    """Status of a workspace."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PROVISIONING = "provisioning"
    ARCHIVED = "archived"


class EnvironmentKind(Enum):
    """Kind of environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    SANDBOX = "sandbox"
    DR = "dr"


class IsolationLevel(Enum):
    """Isolation level for a tenant or workspace."""
    STRICT = "strict"
    STANDARD = "standard"
    SHARED = "shared"
    CUSTOM = "custom"


class ScopeBoundaryKind(Enum):
    """Kind of scope boundary enforced by a policy."""
    MEMORY = "memory"
    CONNECTOR = "connector"
    BUDGET = "budget"
    CAMPAIGN = "campaign"
    PROGRAM = "program"
    CONTROL = "control"
    REPORT = "report"
    GRAPH = "graph"


class PromotionStatus(Enum):
    """Status of an environment promotion."""
    REQUESTED = "requested"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TenantRecord(ContractRecord):
    """A registered tenant in the platform."""

    tenant_id: str = ""
    name: str = ""
    status: TenantStatus = TenantStatus.ACTIVE
    isolation_level: IsolationLevel = IsolationLevel.STANDARD
    owner: str = ""
    workspace_ids: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.status, TenantStatus):
            raise ValueError("status must be a TenantStatus")
        if not isinstance(self.isolation_level, IsolationLevel):
            raise ValueError("isolation_level must be an IsolationLevel")
        object.__setattr__(self, "workspace_ids", freeze_value(list(self.workspace_ids)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkspaceRecord(ContractRecord):
    """A workspace within a tenant."""

    workspace_id: str = ""
    tenant_id: str = ""
    name: str = ""
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE
    isolation_level: IsolationLevel = IsolationLevel.STANDARD
    environment_ids: tuple[str, ...] = ()
    resource_bindings: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_id", require_non_empty_text(self.workspace_id, "workspace_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.status, WorkspaceStatus):
            raise ValueError("status must be a WorkspaceStatus")
        if not isinstance(self.isolation_level, IsolationLevel):
            raise ValueError("isolation_level must be an IsolationLevel")
        object.__setattr__(self, "environment_ids", freeze_value(list(self.environment_ids)))
        object.__setattr__(self, "resource_bindings", freeze_value(list(self.resource_bindings)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EnvironmentRecord(ContractRecord):
    """An environment within a workspace."""

    environment_id: str = ""
    workspace_id: str = ""
    kind: EnvironmentKind = EnvironmentKind.DEVELOPMENT
    name: str = ""
    promoted_from: str = ""
    connector_ids: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment_id", require_non_empty_text(self.environment_id, "environment_id"))
        object.__setattr__(self, "workspace_id", require_non_empty_text(self.workspace_id, "workspace_id"))
        if not isinstance(self.kind, EnvironmentKind):
            raise ValueError("kind must be an EnvironmentKind")
        object.__setattr__(self, "connector_ids", freeze_value(list(self.connector_ids)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BoundaryPolicy(ContractRecord):
    """A boundary policy enforcing isolation."""

    policy_id: str = ""
    tenant_id: str = ""
    boundary_kind: ScopeBoundaryKind = ScopeBoundaryKind.MEMORY
    isolation_level: IsolationLevel = IsolationLevel.STRICT
    enforced: bool = True
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.boundary_kind, ScopeBoundaryKind):
            raise ValueError("boundary_kind must be a ScopeBoundaryKind")
        if not isinstance(self.isolation_level, IsolationLevel):
            raise ValueError("isolation_level must be an IsolationLevel")
        if not isinstance(self.enforced, bool):
            raise ValueError("enforced must be a boolean")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkspaceBinding(ContractRecord):
    """Binds a resource to a workspace."""

    binding_id: str = ""
    workspace_id: str = ""
    resource_ref_id: str = ""
    resource_type: ScopeBoundaryKind = ScopeBoundaryKind.CAMPAIGN
    environment_id: str = ""
    bound_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "workspace_id", require_non_empty_text(self.workspace_id, "workspace_id"))
        object.__setattr__(self, "resource_ref_id", require_non_empty_text(self.resource_ref_id, "resource_ref_id"))
        if not isinstance(self.resource_type, ScopeBoundaryKind):
            raise ValueError("resource_type must be a ScopeBoundaryKind")
        require_datetime_text(self.bound_at, "bound_at")


@dataclass(frozen=True, slots=True)
class EnvironmentPromotion(ContractRecord):
    """A promotion of an environment (e.g., dev → staging → prod)."""

    promotion_id: str = ""
    source_environment_id: str = ""
    target_environment_id: str = ""
    status: PromotionStatus = PromotionStatus.REQUESTED
    compliance_check_passed: bool = False
    promoted_by: str = ""
    requested_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "promotion_id", require_non_empty_text(self.promotion_id, "promotion_id"))
        object.__setattr__(self, "source_environment_id", require_non_empty_text(self.source_environment_id, "source_environment_id"))
        object.__setattr__(self, "target_environment_id", require_non_empty_text(self.target_environment_id, "target_environment_id"))
        if not isinstance(self.status, PromotionStatus):
            raise ValueError("status must be a PromotionStatus")
        if not isinstance(self.compliance_check_passed, bool):
            raise ValueError("compliance_check_passed must be a boolean")
        require_datetime_text(self.requested_at, "requested_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class IsolationViolation(ContractRecord):
    """A detected isolation violation."""

    violation_id: str = ""
    tenant_id: str = ""
    workspace_id: str = ""
    boundary_kind: ScopeBoundaryKind = ScopeBoundaryKind.MEMORY
    violating_resource_ref: str = ""
    description: str = ""
    escalated: bool = False
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.boundary_kind, ScopeBoundaryKind):
            raise ValueError("boundary_kind must be a ScopeBoundaryKind")
        if not isinstance(self.escalated, bool):
            raise ValueError("escalated must be a boolean")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TenantHealth(ContractRecord):
    """Health snapshot for a tenant."""

    tenant_id: str = ""
    total_workspaces: int = 0
    active_workspaces: int = 0
    total_environments: int = 0
    total_bindings: int = 0
    total_violations: int = 0
    compliance_pct: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_workspaces", require_non_negative_int(self.total_workspaces, "total_workspaces"))
        object.__setattr__(self, "active_workspaces", require_non_negative_int(self.active_workspaces, "active_workspaces"))
        object.__setattr__(self, "total_environments", require_non_negative_int(self.total_environments, "total_environments"))
        object.__setattr__(self, "total_bindings", require_non_negative_int(self.total_bindings, "total_bindings"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "compliance_pct", require_non_negative_float(self.compliance_pct, "compliance_pct"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TenantDecision(ContractRecord):
    """A recorded tenant-level decision."""

    decision_id: str = ""
    tenant_id: str = ""
    title: str = ""
    description: str = ""
    confidence: float = 0.0
    decided_by: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TenantClosureReport(ContractRecord):
    """Closure report for a tenant."""

    report_id: str = ""
    tenant_id: str = ""
    total_workspaces: int = 0
    total_environments: int = 0
    total_bindings: int = 0
    total_promotions: int = 0
    total_violations: int = 0
    total_decisions: int = 0
    compliance_pct: float = 0.0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_workspaces", require_non_negative_int(self.total_workspaces, "total_workspaces"))
        object.__setattr__(self, "total_environments", require_non_negative_int(self.total_environments, "total_environments"))
        object.__setattr__(self, "total_bindings", require_non_negative_int(self.total_bindings, "total_bindings"))
        object.__setattr__(self, "total_promotions", require_non_negative_int(self.total_promotions, "total_promotions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "compliance_pct", require_non_negative_float(self.compliance_pct, "compliance_pct"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
