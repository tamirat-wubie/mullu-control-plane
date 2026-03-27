"""Phase 201A — Multi-tenant Budget Isolation.

Purpose: Per-tenant budget creation, enforcement, and reporting.
    Each tenant gets isolated cost controls — one tenant exhausting
    their budget cannot affect other tenants' LLM access.
Governance scope: tenant budget management only.
Dependencies: llm contracts, budget manager.
Invariants:
  - Budgets are tenant-scoped — cross-tenant spending is impossible.
  - Default tenant budget is created on first access if auto_create=True.
  - Budget exhaustion is hard — no soft limits or grace periods.
  - Tenant budget state is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mcoi_runtime.contracts.llm import LLMBudget


@dataclass(frozen=True, slots=True)
class TenantBudgetPolicy:
    """Policy governing a tenant's LLM budget allocation."""

    tenant_id: str
    max_cost: float = 10.0
    max_calls: int = 1000
    max_tokens_per_call: int = 4096
    auto_create: bool = True  # Create budget on first LLM call
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class TenantBudgetReport:
    """Snapshot of a tenant's budget state for reporting."""

    tenant_id: str
    budget_id: str
    max_cost: float
    spent: float
    remaining: float
    calls_made: int
    max_calls: int
    exhausted: bool
    enabled: bool
    utilization_pct: float  # spent/max_cost * 100


class TenantBudgetManager:
    """Manages per-tenant budget isolation.

    Each tenant gets their own LLMBudget with independent tracking.
    Cross-tenant spending is structurally impossible.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        default_policy: TenantBudgetPolicy | None = None,
    ) -> None:
        self._clock = clock
        self._policies: dict[str, TenantBudgetPolicy] = {}
        self._budgets: dict[str, LLMBudget] = {}
        self._default_policy = default_policy or TenantBudgetPolicy(tenant_id="__default__")

    def set_policy(self, policy: TenantBudgetPolicy) -> None:
        """Set or update a tenant's budget policy."""
        self._policies[policy.tenant_id] = policy

    def get_policy(self, tenant_id: str) -> TenantBudgetPolicy:
        """Get a tenant's policy, falling back to default."""
        return self._policies.get(tenant_id, TenantBudgetPolicy(
            tenant_id=tenant_id,
            max_cost=self._default_policy.max_cost,
            max_calls=self._default_policy.max_calls,
            max_tokens_per_call=self._default_policy.max_tokens_per_call,
            auto_create=self._default_policy.auto_create,
            enabled=self._default_policy.enabled,
        ))

    def ensure_budget(self, tenant_id: str) -> LLMBudget:
        """Get or create a budget for a tenant.

        If auto_create is True in the tenant's policy, creates the budget
        on first access. Otherwise raises if no budget exists.
        """
        if tenant_id in self._budgets:
            return self._budgets[tenant_id]

        policy = self.get_policy(tenant_id)
        if not policy.auto_create:
            raise ValueError(f"no budget for tenant {tenant_id} and auto_create is disabled")

        budget = LLMBudget(
            budget_id=f"tenant-{tenant_id}",
            tenant_id=tenant_id,
            max_cost=policy.max_cost,
            max_calls=policy.max_calls,
            max_tokens_per_call=policy.max_tokens_per_call,
        )
        self._budgets[tenant_id] = budget
        return budget

    def get_budget(self, tenant_id: str) -> LLMBudget | None:
        """Get a tenant's budget without auto-creating."""
        return self._budgets.get(tenant_id)

    def record_spend(self, tenant_id: str, cost: float, tokens: int = 0) -> LLMBudget:
        """Record spending against a tenant's budget.

        Returns the updated budget. Raises if budget is exhausted or cost is invalid.
        """
        if cost < 0.0:
            raise ValueError(f"cost must be non-negative, got {cost}")
        budget = self.ensure_budget(tenant_id)
        if budget.exhausted:
            raise ValueError(f"budget exhausted for tenant {tenant_id}")

        updated = LLMBudget(
            budget_id=budget.budget_id,
            tenant_id=budget.tenant_id,
            max_cost=budget.max_cost,
            spent=budget.spent + cost,
            max_tokens_per_call=budget.max_tokens_per_call,
            max_calls=budget.max_calls,
            calls_made=budget.calls_made + 1,
        )
        self._budgets[tenant_id] = updated
        return updated

    def report(self, tenant_id: str) -> TenantBudgetReport:
        """Generate a budget report for a tenant."""
        budget = self._budgets.get(tenant_id)
        policy = self.get_policy(tenant_id)

        if budget is None:
            return TenantBudgetReport(
                tenant_id=tenant_id,
                budget_id=f"tenant-{tenant_id}",
                max_cost=policy.max_cost,
                spent=0.0,
                remaining=policy.max_cost,
                calls_made=0,
                max_calls=policy.max_calls,
                exhausted=False,
                enabled=policy.enabled,
                utilization_pct=0.0,
            )

        utilization = (budget.spent / budget.max_cost * 100) if budget.max_cost > 0 else 0.0
        return TenantBudgetReport(
            tenant_id=tenant_id,
            budget_id=budget.budget_id,
            max_cost=budget.max_cost,
            spent=budget.spent,
            remaining=budget.remaining,
            calls_made=budget.calls_made,
            max_calls=budget.max_calls,
            exhausted=budget.exhausted,
            enabled=policy.enabled,
            utilization_pct=round(utilization, 2),
        )

    def all_reports(self) -> list[TenantBudgetReport]:
        """Budget reports for all tenants with budgets."""
        return [self.report(tid) for tid in sorted(self._budgets)]

    def tenant_count(self) -> int:
        """Number of tenants with active budgets."""
        return len(self._budgets)

    def total_spent(self) -> float:
        """Total spending across all tenants."""
        return sum(b.spent for b in self._budgets.values())

    def reset_budget(self, tenant_id: str) -> LLMBudget:
        """Reset a tenant's budget (zero out spending)."""
        budget = self._budgets.get(tenant_id)
        if budget is None:
            return self.ensure_budget(tenant_id)

        reset = LLMBudget(
            budget_id=budget.budget_id,
            tenant_id=budget.tenant_id,
            max_cost=budget.max_cost,
            spent=0.0,
            max_tokens_per_call=budget.max_tokens_per_call,
            max_calls=budget.max_calls,
            calls_made=0,
        )
        self._budgets[tenant_id] = reset
        return reset

    def disable_tenant(self, tenant_id: str) -> None:
        """Disable LLM access for a tenant."""
        policy = self.get_policy(tenant_id)
        self._policies[tenant_id] = TenantBudgetPolicy(
            tenant_id=tenant_id,
            max_cost=policy.max_cost,
            max_calls=policy.max_calls,
            max_tokens_per_call=policy.max_tokens_per_call,
            auto_create=policy.auto_create,
            enabled=False,
        )

    def is_enabled(self, tenant_id: str) -> bool:
        """Check if a tenant has LLM access enabled."""
        return self.get_policy(tenant_id).enabled
