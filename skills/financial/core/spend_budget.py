"""Spend Budget — Real-money budget enforcement separate from LLM budgets.

Invariants:
  - Spend budgets are per-tenant, per-currency.
  - Over-budget requests are denied BEFORE provider execution.
  - Limits: per-transaction, daily, weekly, monthly.
  - Reset windows are time-based (UTC day/week/month boundaries).
  - Budget state is immutable — mutations return new objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from skills.financial.core.currency import Money


@dataclass(frozen=True, slots=True)
class SpendBudget:
    """Real-money spend budget for a tenant."""

    budget_id: str
    tenant_id: str
    currency: str
    per_tx_limit: Decimal
    daily_limit: Decimal
    weekly_limit: Decimal
    monthly_limit: Decimal
    spent_today: Decimal = Decimal("0")
    spent_this_week: Decimal = Decimal("0")
    spent_this_month: Decimal = Decimal("0")
    last_reset_at: str = ""


@dataclass(frozen=True, slots=True)
class SpendCheckResult:
    """Result of a spend budget check."""

    allowed: bool
    reason: str = ""
    budget_id: str = ""
    remaining_daily: Decimal = Decimal("0")
    remaining_monthly: Decimal = Decimal("0")


class SpendBudgetManager:
    """Manages real-money spend budgets per tenant.

    Checks must pass BEFORE any financial provider call.
    """

    def __init__(self) -> None:
        self._budgets: dict[str, SpendBudget] = {}  # tenant_id -> budget

    def register(self, budget: SpendBudget) -> None:
        self._budgets[budget.tenant_id] = budget

    def get(self, tenant_id: str) -> SpendBudget | None:
        return self._budgets.get(tenant_id)

    def check(self, tenant_id: str, amount: Decimal, currency: str) -> SpendCheckResult:
        """Check if a spend is within budget. Must be called before provider execution."""
        budget = self._budgets.get(tenant_id)
        if budget is None:
            return SpendCheckResult(allowed=False, reason="no spend budget registered")

        if currency != budget.currency:
            return SpendCheckResult(
                allowed=False, reason=f"currency mismatch: budget is {budget.currency}, request is {currency}",
                budget_id=budget.budget_id,
            )

        if amount > budget.per_tx_limit:
            return SpendCheckResult(
                allowed=False,
                reason=f"per-transaction limit exceeded: {amount} > {budget.per_tx_limit}",
                budget_id=budget.budget_id,
            )

        if budget.spent_today + amount > budget.daily_limit:
            return SpendCheckResult(
                allowed=False,
                reason=f"daily limit would be exceeded: {budget.spent_today} + {amount} > {budget.daily_limit}",
                budget_id=budget.budget_id,
                remaining_daily=budget.daily_limit - budget.spent_today,
            )

        if budget.spent_this_week + amount > budget.weekly_limit:
            return SpendCheckResult(
                allowed=False,
                reason=f"weekly limit would be exceeded",
                budget_id=budget.budget_id,
            )

        if budget.spent_this_month + amount > budget.monthly_limit:
            return SpendCheckResult(
                allowed=False,
                reason=f"monthly limit would be exceeded",
                budget_id=budget.budget_id,
                remaining_monthly=budget.monthly_limit - budget.spent_this_month,
            )

        return SpendCheckResult(
            allowed=True,
            budget_id=budget.budget_id,
            remaining_daily=budget.daily_limit - budget.spent_today - amount,
            remaining_monthly=budget.monthly_limit - budget.spent_this_month - amount,
        )

    def record_spend(self, tenant_id: str, amount: Decimal) -> SpendBudget:
        """Record a spend against the budget. Returns updated budget."""
        budget = self._budgets.get(tenant_id)
        if budget is None:
            raise ValueError(f"no spend budget for tenant {tenant_id}")

        updated = SpendBudget(
            budget_id=budget.budget_id,
            tenant_id=budget.tenant_id,
            currency=budget.currency,
            per_tx_limit=budget.per_tx_limit,
            daily_limit=budget.daily_limit,
            weekly_limit=budget.weekly_limit,
            monthly_limit=budget.monthly_limit,
            spent_today=budget.spent_today + amount,
            spent_this_week=budget.spent_this_week + amount,
            spent_this_month=budget.spent_this_month + amount,
            last_reset_at=budget.last_reset_at,
        )
        self._budgets[tenant_id] = updated
        return updated

    @property
    def tenant_count(self) -> int:
        return len(self._budgets)
