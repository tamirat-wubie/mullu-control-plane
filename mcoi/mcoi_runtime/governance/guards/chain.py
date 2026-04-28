"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.governance_guard`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.governance_guard`` path or the new ``governance.guards.chain`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.governance_guard import (  # noqa: F401
    GovernanceGuard,
    GovernanceGuardChain,
    GuardChainResult,
    GuardContext,
    GuardResult,
    create_api_key_guard,
    create_budget_guard,
    create_jwt_guard,
    create_rate_limit_guard,
    create_rbac_guard,
    create_tenant_guard,
)

__all__ = (
    "GovernanceGuard",
    "GovernanceGuardChain",
    "GuardChainResult",
    "GuardContext",
    "GuardResult",
    "create_api_key_guard",
    "create_budget_guard",
    "create_jwt_guard",
    "create_rate_limit_guard",
    "create_rbac_guard",
    "create_tenant_guard",
)
