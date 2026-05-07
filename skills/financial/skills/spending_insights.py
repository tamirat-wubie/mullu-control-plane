"""Spending Insights Skill — Analyze spending patterns.

Permission: read_financial
Risk: medium (auto-approve with audit)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from skills.financial.providers.base import ReadOnlyFinancialProvider


@dataclass(frozen=True, slots=True)
class SpendingInsight:
    """A single spending insight."""

    category: str
    total: str  # Decimal as string
    count: int
    percentage: float


@dataclass(frozen=True, slots=True)
class SpendingInsightsResult:
    """Result of spending analysis."""

    success: bool
    total_spent: str = "0"
    transaction_count: int = 0
    categories: tuple[SpendingInsight, ...] = ()
    top_merchants: tuple[dict[str, Any], ...] = ()
    error: str = ""


def analyze_spending(
    provider: ReadOnlyFinancialProvider,
    tenant_id: str,
    account_id: str,
    *,
    days: int = 30,
) -> SpendingInsightsResult:
    """Analyze spending patterns for an account."""
    result = provider.get_transactions(tenant_id, account_id, days=days, limit=500)
    if not result.success:
        return SpendingInsightsResult(success=False, error=result.error)

    txs = result.data
    if not txs:
        return SpendingInsightsResult(success=True, total_spent="0", transaction_count=0)

    # Aggregate by category
    category_totals: dict[str, Decimal] = defaultdict(Decimal)
    category_counts: dict[str, int] = defaultdict(int)
    merchant_totals: dict[str, Decimal] = defaultdict(Decimal)
    total = Decimal("0")

    for tx in txs:
        # Only count debits (negative or positive depending on convention)
        amt = abs(tx.amount)
        cat = tx.category or "uncategorized"
        category_totals[cat] += amt
        category_counts[cat] += 1
        if tx.merchant:
            merchant_totals[tx.merchant] += amt
        total += amt

    # Build category insights
    categories = tuple(
        SpendingInsight(
            category=cat,
            total=str(category_totals[cat]),
            count=category_counts[cat],
            percentage=float(category_totals[cat] / total * 100) if total > 0 else 0.0,
        )
        for cat in sorted(category_totals, key=lambda c: category_totals[c], reverse=True)
    )

    # Top merchants
    top_merchants = tuple(
        {"merchant": m, "total": str(t)}
        for m, t in sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    )

    return SpendingInsightsResult(
        success=True,
        total_spent=str(total),
        transaction_count=len(txs),
        categories=categories,
        top_merchants=top_merchants,
    )
