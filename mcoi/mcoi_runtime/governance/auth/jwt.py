"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.jwt_auth`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.jwt_auth`` path or the new ``governance.auth.jwt`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.jwt_auth import (  # noqa: F401
    JWKSFetcher,
    JWTAlgorithm,
    JWTAuthResult,
    JWTAuthenticator,
    OIDCConfig,
)

__all__ = (
    "JWKSFetcher",
    "JWTAlgorithm",
    "JWTAuthResult",
    "JWTAuthenticator",
    "OIDCConfig",
)
