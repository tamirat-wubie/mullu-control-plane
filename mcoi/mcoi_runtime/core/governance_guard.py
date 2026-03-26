"""Phase 207B — Governance Guards.

Purpose: Pre-request validation layer that enforces governance invariants
    before any endpoint logic runs. Checks rate limits, budget,
    tenant validity, and audit logging in a single pass.
Governance scope: request validation only — never modifies business state.
Dependencies: rate_limiter, tenant_budget, audit_trail, metrics.
Invariants:
  - Guards run before every governed request.
  - Rejected requests are audited with reason.
  - Guard evaluation order is deterministic.
  - Guards never modify request payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class GuardResult:
    """Result of a governance guard check."""

    allowed: bool
    guard_name: str
    reason: str = ""
    detail: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class GuardChainResult:
    """Result of running the full guard chain."""

    allowed: bool
    results: tuple[GuardResult, ...]
    blocking_guard: str = ""
    reason: str = ""


class GovernanceGuard:
    """Named guard with a check function."""

    def __init__(self, name: str, check_fn: Callable[[dict[str, Any]], GuardResult]) -> None:
        self.name = name
        self._check_fn = check_fn

    def check(self, context: dict[str, Any]) -> GuardResult:
        try:
            return self._check_fn(context)
        except Exception as exc:
            return GuardResult(allowed=False, guard_name=self.name, reason=f"guard error: {exc}")


class GovernanceGuardChain:
    """Ordered chain of governance guards.

    Guards run in registration order. First failure stops the chain.
    """

    def __init__(self) -> None:
        self._guards: list[GovernanceGuard] = []

    def add(self, guard: GovernanceGuard) -> None:
        self._guards.append(guard)

    def evaluate(self, context: dict[str, Any]) -> GuardChainResult:
        """Run all guards in order. Stops on first failure."""
        results: list[GuardResult] = []
        for guard in self._guards:
            result = guard.check(context)
            results.append(result)
            if not result.allowed:
                return GuardChainResult(
                    allowed=False,
                    results=tuple(results),
                    blocking_guard=guard.name,
                    reason=result.reason,
                )
        return GuardChainResult(allowed=True, results=tuple(results))

    @property
    def guard_count(self) -> int:
        return len(self._guards)

    def guard_names(self) -> list[str]:
        return [g.name for g in self._guards]


def create_rate_limit_guard(
    rate_limiter: Any,
) -> GovernanceGuard:
    """Create a rate-limiting guard."""
    def check(ctx: dict[str, Any]) -> GuardResult:
        tenant_id = ctx.get("tenant_id", "system")
        endpoint = ctx.get("endpoint", "/unknown")
        result = rate_limiter.check(tenant_id, endpoint)
        if result.allowed:
            return GuardResult(allowed=True, guard_name="rate_limit")
        return GuardResult(
            allowed=False, guard_name="rate_limit",
            reason=f"rate limited: retry after {result.retry_after_seconds}s",
        )
    return GovernanceGuard("rate_limit", check)


def create_budget_guard(
    budget_mgr: Any,
) -> GovernanceGuard:
    """Create a budget-enforcement guard."""
    def check(ctx: dict[str, Any]) -> GuardResult:
        tenant_id = ctx.get("tenant_id", "")
        if not tenant_id:
            return GuardResult(allowed=True, guard_name="budget")
        report = budget_mgr.report(tenant_id)
        if report.exhausted:
            return GuardResult(
                allowed=False, guard_name="budget",
                reason=f"budget exhausted for tenant {tenant_id}",
            )
        if not report.enabled:
            return GuardResult(
                allowed=False, guard_name="budget",
                reason=f"tenant {tenant_id} is disabled",
            )
        return GuardResult(allowed=True, guard_name="budget")
    return GovernanceGuard("budget", check)


def create_tenant_guard() -> GovernanceGuard:
    """Create a tenant-validation guard."""
    def check(ctx: dict[str, Any]) -> GuardResult:
        tenant_id = ctx.get("tenant_id", "")
        if tenant_id and len(tenant_id) > 128:
            return GuardResult(
                allowed=False, guard_name="tenant",
                reason="tenant_id exceeds 128 characters",
            )
        return GuardResult(allowed=True, guard_name="tenant")
    return GovernanceGuard("tenant", check)
