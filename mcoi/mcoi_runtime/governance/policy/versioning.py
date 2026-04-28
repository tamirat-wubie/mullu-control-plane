"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.policy_versioning`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.policy_versioning`` path or the new ``governance.policy.versioning`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.policy_versioning import (  # noqa: F401
    PolicyArtifact,
    PolicyChangeKind,
    PolicyDecisionSnapshot,
    PolicyRuleDiff,
    PolicyVersionDiff,
    PolicyVersionRegistry,
    ShadowGovernanceEvaluator,
    ShadowGovernanceResult,
    VersionedPolicyRule,
    VersionedPolicyRuleLike,
)

__all__ = (
    "PolicyArtifact",
    "PolicyChangeKind",
    "PolicyDecisionSnapshot",
    "PolicyRuleDiff",
    "PolicyVersionDiff",
    "PolicyVersionRegistry",
    "ShadowGovernanceEvaluator",
    "ShadowGovernanceResult",
    "VersionedPolicyRule",
    "VersionedPolicyRuleLike",
)
