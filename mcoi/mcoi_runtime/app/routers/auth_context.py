"""Purpose: bind route-level actor claims to governed request identity.
Governance scope: request attribution for mutation endpoints.
Dependencies: FastAPI request state populated by GovernanceMiddleware.
Invariants:
  - Authenticated request identity overrides default body attribution.
  - Explicit body identity mismatches fail closed.
  - Routes without middleware context keep existing local/test behavior.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request


def governance_context_from_request(request: Request) -> dict[str, Any]:
    """Return the mutable guard context copied onto request state by middleware."""
    context = getattr(request.state, "governance_context", None)
    if isinstance(context, dict):
        return context
    return {}


def authenticated_actor_id(request: Request) -> str:
    """Resolve the authenticated actor available to route handlers."""
    context = governance_context_from_request(request)
    for key in ("authenticated_subject", "rbac_identity_id", "authenticated_key_id"):
        value = context.get(key, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def bind_claimed_actor(
    request: Request,
    claimed_actor_id: str,
    *,
    default_claims: tuple[str, ...] = (),
    error_code: str = "actor_identity_mismatch",
    error_message: str = "actor does not match authenticated identity",
) -> str:
    """Return the actor allowed for the request or raise on spoofed attribution."""
    authenticated = authenticated_actor_id(request)
    claimed = claimed_actor_id.strip() if isinstance(claimed_actor_id, str) else ""
    if not authenticated:
        return claimed
    if not claimed or claimed in default_claims:
        return authenticated
    if claimed != authenticated:
        raise HTTPException(
            status_code=403,
            detail={
                "error": error_message,
                "error_code": error_code,
                "governed": True,
            },
        )
    return authenticated
