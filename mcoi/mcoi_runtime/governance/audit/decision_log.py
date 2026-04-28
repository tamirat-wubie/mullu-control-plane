"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.governance_decision_log`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.governance_decision_log`` path or the new ``governance.audit.decision_log`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.governance_decision_log import (  # noqa: F401
    GovernanceDecision,
    GovernanceDecisionLog,
    GuardDecisionDetail,
)

__all__ = (
    "GovernanceDecision",
    "GovernanceDecisionLog",
    "GuardDecisionDetail",
)
