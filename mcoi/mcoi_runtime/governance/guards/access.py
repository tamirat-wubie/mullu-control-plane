"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.access_runtime`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.access_runtime`` path or the new ``governance.guards.access`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.access_runtime import (  # noqa: F401
    AccessAuditRecord,
    AccessDecision,
    AccessEvaluation,
    AccessRequest,
    AccessRuntimeEngine,
    AccessSnapshot,
    AccessViolation,
    AuthContextKind,
    DelegationRecord,
    DelegationStatus,
    DuplicateRuntimeIdentifierError,
    EventRecord,
    EventSource,
    EventSpineEngine,
    EventType,
    IdentityKind,
    IdentityRecord,
    PermissionEffect,
    PermissionRule,
    RoleBinding,
    RoleKind,
    RoleRecord,
    RuntimeCoreInvariantError,
)

__all__ = (
    "AccessAuditRecord",
    "AccessDecision",
    "AccessEvaluation",
    "AccessRequest",
    "AccessRuntimeEngine",
    "AccessSnapshot",
    "AccessViolation",
    "AuthContextKind",
    "DelegationRecord",
    "DelegationStatus",
    "DuplicateRuntimeIdentifierError",
    "EventRecord",
    "EventSource",
    "EventSpineEngine",
    "EventType",
    "IdentityKind",
    "IdentityRecord",
    "PermissionEffect",
    "PermissionRule",
    "RoleBinding",
    "RoleKind",
    "RoleRecord",
    "RuntimeCoreInvariantError",
)
