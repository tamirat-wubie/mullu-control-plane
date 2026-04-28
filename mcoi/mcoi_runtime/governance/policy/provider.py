"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.provider_policy`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.provider_policy`` path or the new ``governance.policy.provider`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.provider_policy import (  # noqa: F401
    HttpProviderPolicy,
    PolicyViolationSeverity,
    ProcessProviderPolicy,
    ProviderInvocationCheck,
    ProviderPolicyEnforcer,
    ProviderPolicyType,
    ProviderPolicyViolation,
    SmtpProviderPolicy,
)

__all__ = (
    "HttpProviderPolicy",
    "PolicyViolationSeverity",
    "ProcessProviderPolicy",
    "ProviderInvocationCheck",
    "ProviderPolicyEnforcer",
    "ProviderPolicyType",
    "ProviderPolicyViolation",
    "SmtpProviderPolicy",
)
