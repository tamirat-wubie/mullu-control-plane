"""Gateway Authority Graph - approval resolver governance.

Purpose: Decides whether a channel identity may resolve an approval request
    for a governed command action.
Governance scope: gateway approval resolution only.
Dependencies: gateway approval, command spine, tenant identity contracts.
Invariants:
  - Approval requires tenant and channel continuity.
  - Approval requires explicit resolver authority.
  - Capability role requirements must be satisfied by resolver roles.
  - Self-approval is blocked for high-risk world-mutating capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass

from gateway.approval import ApprovalRequest, RiskTier
from gateway.command_spine import GovernedAction
from gateway.tenant_identity import TenantMapping


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    """Authority decision for one approval resolver."""

    allowed: bool
    reason: str
    required_roles: tuple[str, ...] = ()
    resolver_roles: tuple[str, ...] = ()


def _has_required_role(required_role: str, resolver_roles: tuple[str, ...]) -> bool:
    """Return True when the resolver role set satisfies one authority symbol."""
    if required_role == "tenant_member":
        return True
    return required_role in resolver_roles


def evaluate_approval_authority(
    *,
    request: ApprovalRequest,
    resolver: TenantMapping,
    governed_action: GovernedAction | None,
) -> AuthorityDecision:
    """Evaluate whether resolver may decide the approval request."""
    if request.tenant_id != resolver.tenant_id:
        return AuthorityDecision(False, "tenant_mismatch")
    if request.channel != resolver.channel:
        return AuthorityDecision(False, "channel_mismatch")
    if not resolver.approval_authority:
        return AuthorityDecision(
            False,
            "resolver_lacks_approval_authority",
            resolver_roles=tuple(resolver.roles),
        )

    required_roles = governed_action.authority_required if governed_action is not None else ("tenant_member",)
    resolver_roles = tuple(resolver.roles)
    missing_roles = tuple(
        role for role in required_roles
        if not _has_required_role(role, resolver_roles)
    )
    if missing_roles:
        return AuthorityDecision(
            False,
            "resolver_lacks_required_role",
            required_roles=missing_roles,
            resolver_roles=resolver_roles,
        )

    if (
        governed_action is not None
        and request.risk_tier == RiskTier.HIGH
        and governed_action.risk_tier == "high"
        and resolver.identity_id == request.identity_id
    ):
        return AuthorityDecision(
            False,
            "self_approval_denied",
            required_roles=required_roles,
            resolver_roles=resolver_roles,
        )

    return AuthorityDecision(
        True,
        "authority_proven",
        required_roles=required_roles,
        resolver_roles=resolver_roles,
    )
