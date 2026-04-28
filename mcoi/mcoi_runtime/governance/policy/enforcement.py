"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.policy_enforcement`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.policy_enforcement`` path or the new ``governance.policy.enforcement`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.policy_enforcement import (  # noqa: F401
    EnforcementAuditRecord,
    EnforcementDecision,
    EnforcementEvent,
    PolicyEnforcementEngine,
    PolicySessionBinding,
    PrivilegeElevationDecision,
    PrivilegeElevationRequest,
    PrivilegeLevel,
    RevocationReason,
    RevocationRecord,
    SessionClosureReport,
    SessionConstraint,
    SessionKind,
    SessionRecord,
    SessionSnapshot,
    SessionStatus,
    StepUpStatus,
)

__all__ = (
    "EnforcementAuditRecord",
    "EnforcementDecision",
    "EnforcementEvent",
    "PolicyEnforcementEngine",
    "PolicySessionBinding",
    "PrivilegeElevationDecision",
    "PrivilegeElevationRequest",
    "PrivilegeLevel",
    "RevocationReason",
    "RevocationRecord",
    "SessionClosureReport",
    "SessionConstraint",
    "SessionKind",
    "SessionRecord",
    "SessionSnapshot",
    "SessionStatus",
    "StepUpStatus",
)
