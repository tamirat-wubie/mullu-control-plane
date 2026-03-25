"""Purpose: identity / access / authorization runtime contracts.
Governance scope: typed descriptors for identities, roles, permission rules,
    role bindings, delegations, access requests, evaluations, violations,
    snapshots, and audit records.
Dependencies: _base contract utilities.
Invariants:
  - Every identity has explicit kind and tenant scope.
  - Roles bind to scoped entities (tenant/workspace/environment).
  - Permission evaluation is deterministic and fail-closed.
  - Delegations are time-bounded and revocable.
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
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IdentityKind(Enum):
    """Kind of identity."""
    HUMAN = "human"
    SERVICE = "service"
    OPERATOR = "operator"
    SYSTEM = "system"
    API_KEY = "api_key"


class RoleKind(Enum):
    """Kind of role."""
    ADMIN = "admin"
    OPERATOR = "operator"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    AUDITOR = "auditor"
    SERVICE = "service"
    CUSTOM = "custom"


class PermissionEffect(Enum):
    """Effect of a permission rule."""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class AccessDecision(Enum):
    """Decision of an access evaluation."""
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"
    EXPIRED = "expired"
    VIOLATION = "violation"


class DelegationStatus(Enum):
    """Status of a delegation."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class AuthContextKind(Enum):
    """Kind of authorization context scope."""
    TENANT = "tenant"
    WORKSPACE = "workspace"
    ENVIRONMENT = "environment"
    GLOBAL = "global"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityRecord(ContractRecord):
    """A registered identity in the platform."""

    identity_id: str = ""
    name: str = ""
    kind: IdentityKind = IdentityKind.HUMAN
    tenant_id: str = ""
    enabled: bool = True
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.kind, IdentityKind):
            raise ValueError("kind must be an IdentityKind")
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RoleRecord(ContractRecord):
    """A role definition."""

    role_id: str = ""
    name: str = ""
    kind: RoleKind = RoleKind.VIEWER
    permissions: tuple[str, ...] = ()
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_id", require_non_empty_text(self.role_id, "role_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.kind, RoleKind):
            raise ValueError("kind must be a RoleKind")
        object.__setattr__(self, "permissions", freeze_value(list(self.permissions)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PermissionRule(ContractRecord):
    """A permission rule within the access system."""

    rule_id: str = ""
    resource_type: str = ""
    action: str = ""
    effect: PermissionEffect = PermissionEffect.DENY
    scope_kind: AuthContextKind = AuthContextKind.TENANT
    scope_ref_id: str = ""
    conditions: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "resource_type", require_non_empty_text(self.resource_type, "resource_type"))
        object.__setattr__(self, "action", require_non_empty_text(self.action, "action"))
        if not isinstance(self.effect, PermissionEffect):
            raise ValueError("effect must be a PermissionEffect")
        if not isinstance(self.scope_kind, AuthContextKind):
            raise ValueError("scope_kind must be an AuthContextKind")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        object.__setattr__(self, "conditions", freeze_value(dict(self.conditions)))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class RoleBinding(ContractRecord):
    """Binds a role to an identity within a scope."""

    binding_id: str = ""
    identity_id: str = ""
    role_id: str = ""
    scope_kind: AuthContextKind = AuthContextKind.TENANT
    scope_ref_id: str = ""
    bound_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        object.__setattr__(self, "role_id", require_non_empty_text(self.role_id, "role_id"))
        if not isinstance(self.scope_kind, AuthContextKind):
            raise ValueError("scope_kind must be an AuthContextKind")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        require_datetime_text(self.bound_at, "bound_at")


@dataclass(frozen=True, slots=True)
class DelegationRecord(ContractRecord):
    """A time-bounded permission delegation."""

    delegation_id: str = ""
    from_identity_id: str = ""
    to_identity_id: str = ""
    role_id: str = ""
    scope_kind: AuthContextKind = AuthContextKind.WORKSPACE
    scope_ref_id: str = ""
    status: DelegationStatus = DelegationStatus.ACTIVE
    expires_at: str = ""
    delegated_at: str = ""
    revoked_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "delegation_id", require_non_empty_text(self.delegation_id, "delegation_id"))
        object.__setattr__(self, "from_identity_id", require_non_empty_text(self.from_identity_id, "from_identity_id"))
        object.__setattr__(self, "to_identity_id", require_non_empty_text(self.to_identity_id, "to_identity_id"))
        object.__setattr__(self, "role_id", require_non_empty_text(self.role_id, "role_id"))
        if not isinstance(self.scope_kind, AuthContextKind):
            raise ValueError("scope_kind must be an AuthContextKind")
        if not isinstance(self.status, DelegationStatus):
            raise ValueError("status must be a DelegationStatus")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        require_datetime_text(self.delegated_at, "delegated_at")
        if self.expires_at:
            require_datetime_text(self.expires_at, "expires_at")
        if self.revoked_at:
            require_datetime_text(self.revoked_at, "revoked_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AccessRequest(ContractRecord):
    """A request to access a resource."""

    request_id: str = ""
    identity_id: str = ""
    resource_type: str = ""
    action: str = ""
    scope_kind: AuthContextKind = AuthContextKind.TENANT
    scope_ref_id: str = ""
    requested_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        object.__setattr__(self, "resource_type", require_non_empty_text(self.resource_type, "resource_type"))
        object.__setattr__(self, "action", require_non_empty_text(self.action, "action"))
        if not isinstance(self.scope_kind, AuthContextKind):
            raise ValueError("scope_kind must be an AuthContextKind")
        require_datetime_text(self.requested_at, "requested_at")


@dataclass(frozen=True, slots=True)
class AccessEvaluation(ContractRecord):
    """Result of evaluating an access request."""

    evaluation_id: str = ""
    request_id: str = ""
    decision: AccessDecision = AccessDecision.DENIED
    matching_rule_ids: tuple[str, ...] = ()
    matching_role_ids: tuple[str, ...] = ()
    reason: str = ""
    evaluated_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluation_id", require_non_empty_text(self.evaluation_id, "evaluation_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        if not isinstance(self.decision, AccessDecision):
            raise ValueError("decision must be an AccessDecision")
        object.__setattr__(self, "matching_rule_ids", freeze_value(list(self.matching_rule_ids)))
        object.__setattr__(self, "matching_role_ids", freeze_value(list(self.matching_role_ids)))
        require_datetime_text(self.evaluated_at, "evaluated_at")


@dataclass(frozen=True, slots=True)
class AccessViolation(ContractRecord):
    """A detected access violation."""

    violation_id: str = ""
    identity_id: str = ""
    resource_type: str = ""
    action: str = ""
    scope_kind: AuthContextKind = AuthContextKind.TENANT
    scope_ref_id: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        object.__setattr__(self, "resource_type", require_non_empty_text(self.resource_type, "resource_type"))
        object.__setattr__(self, "action", require_non_empty_text(self.action, "action"))
        if not isinstance(self.scope_kind, AuthContextKind):
            raise ValueError("scope_kind must be an AuthContextKind")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AccessSnapshot(ContractRecord):
    """Point-in-time access snapshot."""

    snapshot_id: str = ""
    scope_ref_id: str = ""
    total_identities: int = 0
    total_roles: int = 0
    total_bindings: int = 0
    total_rules: int = 0
    active_delegations: int = 0
    total_violations: int = 0
    total_evaluations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_identities", require_non_negative_int(self.total_identities, "total_identities"))
        object.__setattr__(self, "total_roles", require_non_negative_int(self.total_roles, "total_roles"))
        object.__setattr__(self, "total_bindings", require_non_negative_int(self.total_bindings, "total_bindings"))
        object.__setattr__(self, "total_rules", require_non_negative_int(self.total_rules, "total_rules"))
        object.__setattr__(self, "active_delegations", require_non_negative_int(self.active_delegations, "active_delegations"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_evaluations", require_non_negative_int(self.total_evaluations, "total_evaluations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AccessAuditRecord(ContractRecord):
    """An audit record for access operations."""

    audit_id: str = ""
    identity_id: str = ""
    action: str = ""
    resource_type: str = ""
    decision: AccessDecision = AccessDecision.DENIED
    scope_kind: AuthContextKind = AuthContextKind.TENANT
    scope_ref_id: str = ""
    recorded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "audit_id", require_non_empty_text(self.audit_id, "audit_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        object.__setattr__(self, "action", require_non_empty_text(self.action, "action"))
        object.__setattr__(self, "resource_type", require_non_empty_text(self.resource_type, "resource_type"))
        if not isinstance(self.decision, AccessDecision):
            raise ValueError("decision must be an AccessDecision")
        if not isinstance(self.scope_kind, AuthContextKind):
            raise ValueError("scope_kind must be an AuthContextKind")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        require_datetime_text(self.recorded_at, "recorded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
