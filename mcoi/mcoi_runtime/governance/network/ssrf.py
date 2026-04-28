"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.ssrf_policy`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.ssrf_policy`` path or the new ``governance.network.ssrf`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.ssrf_policy import (  # noqa: F401
    is_private_host,
    is_private_ip,
    is_private_url,
    resolve_and_check,
)

__all__ = (
    "is_private_host",
    "is_private_ip",
    "is_private_url",
    "resolve_and_check",
)
