"""
Bridge: existing `GovernanceGuardChain` → MUSIA `Φ_gov` external_validators.

Closes the v4.1.0 deferred gap. Before this module, MUSIA's Φ_gov had a
slot for external validators but no one was wiring the existing platform's
`GovernanceGuardChain` (rate limits, budgets, tenant guards, JWT, RBAC,
etc.) into it. As a result, MUSIA writes ran through MUSIA's own
governance but not through the existing chain — two parallel governance
paths, neither aware of the other.

This module provides the adapter:

    chain = GovernanceGuardChain()
    chain.add(create_rate_limit_guard(...))
    chain.add(create_budget_guard(...))

    configure_musia_governance_chain(chain)
    # Now every POST /constructs/* runs the chain alongside Φ_agent.

The chain runs as ONE of the external validators. Returning False with
a reason → MUSIA's standard 403 with a detail naming the blocking guard.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from mcoi_runtime.governance.guards.chain import (
    GovernanceGuardChain,
    GuardChainResult,
)
from mcoi_runtime.substrate.phi_gov import (
    Authority,
    GovernanceContext,
    ProposedDelta,
)
from mcoi_runtime.app.routers.musia_governance_metrics import (
    REGISTRY as _METRICS,
    SURFACE_DOMAIN_RUN,
    SURFACE_WRITE,
)


_log = logging.getLogger(__name__)


# Module-level state. configure_musia_governance_chain() installs.
_CHAIN: Optional[GovernanceGuardChain] = None


def configure_musia_governance_chain(
    chain: GovernanceGuardChain | None,
) -> None:
    """Install or uninstall the platform governance chain that fronts MUSIA writes.

    Pass None to detach. When detached, MUSIA writes go through Φ_gov's
    Φ_agent filter only — backward-compatible with v4.14.x.
    """
    global _CHAIN
    _CHAIN = chain


def configured_chain() -> GovernanceGuardChain | None:
    """Inspect the current chain. Returns None when detached."""
    return _CHAIN


def chain_to_validator(
    chain: GovernanceGuardChain,
) -> Callable[[ProposedDelta, GovernanceContext, Authority], tuple[bool, str]]:
    """Wrap a GovernanceGuardChain into the Φ_gov external_validator shape.

    The returned callable is consumable by ``PhiGov.evaluate`` via its
    ``external_validators`` parameter. Each Φ_gov call invokes the chain
    once per delta, building the chain's GuardContext from the delta +
    governance context + authority.
    """

    def validator(
        delta: ProposedDelta,
        ctx: GovernanceContext,
        auth: Authority,
    ) -> tuple[bool, str]:
        guard_ctx: dict[str, Any] = {
            "tenant_id": ctx.tenant_id,
            "endpoint": f"musia/constructs/{delta.operation}",
            "method": "POST" if delta.operation in ("create", "update") else "DELETE",
            # Authority/identity bridging — auth here is MUSIA's, not the
            # chain's own auth guards. We surface it as authenticated_subject
            # so chain guards that key off subject (rate limit, RBAC) work.
            "authenticated_subject": auth.identifier,
            "authenticated_tenant_id": ctx.tenant_id,
            # Domain-specific extras the chain may inspect
            "construct_type": delta.payload.get("type"),
            "construct_tier": delta.payload.get("tier"),
            "operation": delta.operation,
        }
        # Time the chain.evaluate() call. v4.21.0+: duration_seconds is
        # passed to _METRICS.record() so the latency histogram populates
        # for every verdict (allowed, denied, exception). monotonic_ns
        # is immune to wall-clock drift.
        start_ns = time.monotonic_ns()
        try:
            result: GuardChainResult = chain.evaluate(guard_ctx)
        except Exception as exc:
            duration_s = (time.monotonic_ns() - start_ns) / 1e9
            # Defensive: a guard that raises is treated as denial,
            # logged at WARNING for forensic follow-up.
            _log.warning(
                "MUSIA governance bridge: chain raised %s — denying delta %s",
                type(exc).__name__,
                delta.construct_id,
            )
            _METRICS.record(
                surface=SURFACE_WRITE,
                tenant_id=ctx.tenant_id,
                allowed=False,
                blocking_guard=type(exc).__name__,
                reason="chain_exception",
                exception=True,
                duration_seconds=duration_s,
            )
            return (False, f"chain_exception:{type(exc).__name__}")

        duration_s = (time.monotonic_ns() - start_ns) / 1e9
        if result.allowed:
            _METRICS.record(
                surface=SURFACE_WRITE,
                tenant_id=ctx.tenant_id,
                allowed=True,
                duration_seconds=duration_s,
            )
            return (True, "")
        _METRICS.record(
            surface=SURFACE_WRITE,
            tenant_id=ctx.tenant_id,
            allowed=False,
            blocking_guard=result.blocking_guard,
            reason=result.reason or "",
            duration_seconds=duration_s,
        )
        return (
            False,
            f"blocked_by:{result.blocking_guard or 'unknown_guard'} "
            f"({result.reason or 'no reason provided'})",
        )

    return validator


def installed_validator_or_none() -> (
    Callable[[ProposedDelta, GovernanceContext, Authority], tuple[bool, str]] | None
):
    """Return the bridge validator if a chain is installed, else None.

    Used by the constructs router to optionally extend Φ_gov's
    external_validators tuple.
    """
    if _CHAIN is None:
        return None
    return chain_to_validator(_CHAIN)


# ---- Per-domain gate (v4.16.0) ----


def gate_domain_run(
    *,
    domain: str,
    tenant_id: str,
    summary: str,
    actor_identifier: str | None = None,
) -> tuple[bool, str]:
    """Check the installed chain before a /domains/<name>/process run.

    Whereas ``installed_validator_or_none()`` adapts the chain into Φ_gov's
    per-construct external_validator slot, this helper invokes the chain
    directly with a domain-run-shaped GuardContext. Used by the domain
    router to gate the entire domain run *before* the cycle executes.

    The shape of the guard context is intentionally distinct from the
    construct-write path so chain guards can write domain-aware policy:

    - ``operation = "domain_run"`` (vs. ``"create"``/``"update"`` for writes)
    - ``domain = <domain_name>``  (e.g. "software_dev", "healthcare")
    - ``summary = <request_summary>``
    - No ``construct_type`` / ``construct_tier`` (this is a domain action,
      not a single-construct write)

    Returns (ok, reason). When chain is detached, always (True, "").
    Buggy guards that raise are treated as denial (defensive, matches
    the per-construct bridge).
    """
    chain = _CHAIN
    if chain is None:
        return (True, "")

    guard_ctx: dict[str, Any] = {
        "tenant_id": tenant_id,
        "endpoint": f"musia/domains/{domain}/process",
        "method": "POST",
        "operation": "domain_run",
        "domain": domain,
        "summary": summary,
    }
    if actor_identifier is not None:
        guard_ctx["authenticated_subject"] = actor_identifier
        guard_ctx["authenticated_tenant_id"] = tenant_id

    # v4.21.0+: time the chain.evaluate() call for the latency histogram.
    start_ns = time.monotonic_ns()
    try:
        result = chain.evaluate(guard_ctx)
    except Exception as exc:
        duration_s = (time.monotonic_ns() - start_ns) / 1e9
        _log.warning(
            "MUSIA governance bridge: chain raised %s on domain run "
            "(domain=%s, tenant=%s) — denying",
            type(exc).__name__,
            domain,
            tenant_id,
        )
        _METRICS.record(
            surface=SURFACE_DOMAIN_RUN,
            tenant_id=tenant_id,
            allowed=False,
            blocking_guard=type(exc).__name__,
            reason="chain_exception",
            exception=True,
            duration_seconds=duration_s,
        )
        return (False, f"chain_exception:{type(exc).__name__}")

    duration_s = (time.monotonic_ns() - start_ns) / 1e9
    if result.allowed:
        _METRICS.record(
            surface=SURFACE_DOMAIN_RUN,
            tenant_id=tenant_id,
            allowed=True,
            duration_seconds=duration_s,
        )
        return (True, "")
    _METRICS.record(
        surface=SURFACE_DOMAIN_RUN,
        tenant_id=tenant_id,
        allowed=False,
        blocking_guard=result.blocking_guard,
        reason=result.reason or "",
        duration_seconds=duration_s,
    )
    return (
        False,
        f"blocked_by:{result.blocking_guard or 'unknown_guard'} "
        f"({result.reason or 'no reason provided'})",
    )
