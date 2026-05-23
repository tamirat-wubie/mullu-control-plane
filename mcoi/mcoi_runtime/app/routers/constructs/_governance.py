"""Φ_gov-mediated write path: quota → rate limit → governance → register."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from mcoi_runtime.app.routers.constructs._registry import _DEFAULT_AUTHORITY
from mcoi_runtime.substrate.cascade import CascadeEngine, registry_dispatch_checker
from mcoi_runtime.substrate.constructs import ConstructBase
from mcoi_runtime.substrate.phi_gov import (
    GovernanceContext,
    PhiGov,
    ProofState,
    ProposedDelta,
)
from mcoi_runtime.substrate.registry_store import STORE, TenantState


def _phi_gov_for(state: TenantState) -> PhiGov:
    """Build Φ_gov for a tenant. v4.15.0: also threads in the existing
    `GovernanceGuardChain` if one was installed via
    ``configure_musia_governance_chain()``.

    The chain's verdict joins Φ_agent's: both must approve. A chain
    rejection lands on the same 403 path Φ_gov uses for any
    external-validator failure.
    """
    from mcoi_runtime.app.routers.musia_governance_bridge import (
        installed_validator_or_none,
    )

    external_validators: tuple = ()
    bridge = installed_validator_or_none()
    if bridge is not None:
        external_validators = (bridge,)

    return PhiGov(
        graph=state.graph,
        # Route cascade invariant checks through the per-type validator
        # registry. Empty by default => identical to the permissive default,
        # so this is behavior-preserving until a type is registered.
        # (docs/INVARIANT_VALIDATOR_ROLLOUT_PROPOSAL.md)
        cascade_engine=CascadeEngine(
            state.graph, invariant_checker=registry_dispatch_checker
        ),
        phi_agent=state.phi_agent,
        external_validators=external_validators,
    )


def _governed_write(
    construct: ConstructBase,
    operation: str,
    depends_on: tuple[UUID, ...],
    state: TenantState,
) -> None:
    """Run a write through quota → rate limit → Φ_gov for the given tenant.

    Order of checks (cheapest first):
      1. Lifetime construct quota (HTTP 429, Retry-After: 0)
      2. Sliding-window rate limit (HTTP 429, Retry-After: <seconds>)
      3. Φ_gov / Φ_agent (HTTP 403)
    """
    # 1. Lifetime quota gate
    ok, reason = state.check_quota_for_write()
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "tenant quota exceeded",
                "reason": reason,
                "tenant_id": state.tenant_id,
            },
            headers={"Retry-After": "0"},
        )

    # 2. Sliding-window rate limit gate
    ok, retry_after, reason = state.check_rate_limit_for_write()
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "tenant rate limit exceeded",
                "reason": reason,
                "retry_after_seconds": retry_after,
                "tenant_id": state.tenant_id,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # 3. Φ_gov gate
    delta = ProposedDelta(
        construct_id=construct.id,
        operation=operation,
        payload={"type": construct.type.value, "tier": construct.tier.value},
    )
    ctx = GovernanceContext(
        correlation_id="api-write",
        tenant_id=state.tenant_id,
    )
    phi = _phi_gov_for(state)
    result = phi.evaluate((delta,), ctx, _DEFAULT_AUTHORITY)
    if result.judgment.state == ProofState.PASS:
        state.graph.register(construct, depends_on=depends_on)
        # Consume a rate-limit slot only on successful registration.
        state.record_write()
        # Auto-snapshot if persistence is configured with that mode.
        STORE.maybe_snapshot(state.tenant_id)
        return
    raise HTTPException(
        status_code=403,
        detail={
            "error": "Φ_gov rejected the write",
            "proof_state": result.judgment.state.value,
            "reason": result.judgment.reason,
            "phi_agent_level_passed": (
                result.judgment.phi_agent_level_passed.name
                if result.judgment.phi_agent_level_passed
                else None
            ),
            "rejected_deltas": [
                {
                    "construct_id": str(d.construct_id),
                    "operation": d.operation,
                }
                for d in result.judgment.rejected_deltas
            ],
            "tenant_id": state.tenant_id,
        },
    )
