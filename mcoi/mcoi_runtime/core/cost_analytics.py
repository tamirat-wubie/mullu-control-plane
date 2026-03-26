"""Phase 209D — Cost Analytics Engine.

Purpose: Per-tenant cost breakdowns, trend analysis, and cost projections.
    Aggregates LLM spending data for budget planning and optimization.
Governance scope: cost analysis only — read-only over spending data.
Dependencies: none (pure computation over input data).
Invariants:
  - Analytics are computed, never cached stale.
  - All cost values are in the same currency unit.
  - Projections are clearly marked as estimates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CostEntry:
    """Single cost event for analytics."""

    tenant_id: str
    model: str
    cost: float
    tokens: int
    timestamp: str


@dataclass(frozen=True, slots=True)
class TenantCostBreakdown:
    """Cost breakdown for a single tenant."""

    tenant_id: str
    total_cost: float
    total_tokens: int
    call_count: int
    avg_cost_per_call: float
    by_model: dict[str, float]
    most_expensive_model: str


@dataclass(frozen=True, slots=True)
class CostProjection:
    """Estimated future cost based on current trends."""

    tenant_id: str
    current_daily_rate: float
    projected_monthly: float
    budget_remaining: float
    days_until_exhaustion: float  # -1 if budget not set


class CostAnalyticsEngine:
    """Computes cost analytics from spending data."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._entries: list[CostEntry] = []

    def record(self, tenant_id: str, model: str, cost: float, tokens: int) -> CostEntry:
        """Record a cost event."""
        entry = CostEntry(
            tenant_id=tenant_id, model=model, cost=cost,
            tokens=tokens, timestamp=self._clock(),
        )
        self._entries.append(entry)
        return entry

    def tenant_breakdown(self, tenant_id: str) -> TenantCostBreakdown:
        """Compute cost breakdown for a tenant."""
        entries = [e for e in self._entries if e.tenant_id == tenant_id]
        if not entries:
            return TenantCostBreakdown(
                tenant_id=tenant_id, total_cost=0.0, total_tokens=0,
                call_count=0, avg_cost_per_call=0.0, by_model={}, most_expensive_model="",
            )

        total_cost = sum(e.cost for e in entries)
        total_tokens = sum(e.tokens for e in entries)
        by_model: dict[str, float] = {}
        for e in entries:
            by_model[e.model] = by_model.get(e.model, 0.0) + e.cost

        most_expensive = max(by_model, key=by_model.get) if by_model else ""

        return TenantCostBreakdown(
            tenant_id=tenant_id,
            total_cost=round(total_cost, 6),
            total_tokens=total_tokens,
            call_count=len(entries),
            avg_cost_per_call=round(total_cost / len(entries), 6),
            by_model={k: round(v, 6) for k, v in by_model.items()},
            most_expensive_model=most_expensive,
        )

    def project(self, tenant_id: str, budget: float = 0.0, days_elapsed: float = 1.0) -> CostProjection:
        """Project future costs based on current spending."""
        breakdown = self.tenant_breakdown(tenant_id)
        daily_rate = breakdown.total_cost / max(days_elapsed, 0.01)
        monthly = daily_rate * 30

        days_left = -1.0
        if budget > 0 and daily_rate > 0:
            remaining = budget - breakdown.total_cost
            days_left = remaining / daily_rate if remaining > 0 else 0.0

        return CostProjection(
            tenant_id=tenant_id,
            current_daily_rate=round(daily_rate, 6),
            projected_monthly=round(monthly, 4),
            budget_remaining=round(max(0, budget - breakdown.total_cost), 6),
            days_until_exhaustion=round(days_left, 1),
        )

    def top_spenders(self, limit: int = 10) -> list[TenantCostBreakdown]:
        """Top spending tenants."""
        tenant_ids = set(e.tenant_id for e in self._entries)
        breakdowns = [self.tenant_breakdown(tid) for tid in tenant_ids]
        breakdowns.sort(key=lambda b: b.total_cost, reverse=True)
        return breakdowns[:limit]

    def model_usage(self) -> dict[str, dict[str, Any]]:
        """Usage breakdown by model across all tenants."""
        by_model: dict[str, dict[str, Any]] = {}
        for e in self._entries:
            if e.model not in by_model:
                by_model[e.model] = {"cost": 0.0, "tokens": 0, "calls": 0}
            by_model[e.model]["cost"] = round(by_model[e.model]["cost"] + e.cost, 6)
            by_model[e.model]["tokens"] += e.tokens
            by_model[e.model]["calls"] += 1
        return by_model

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def summary(self) -> dict[str, Any]:
        total_cost = sum(e.cost for e in self._entries)
        tenant_count = len(set(e.tenant_id for e in self._entries))
        return {
            "total_entries": self.entry_count,
            "total_cost": round(total_cost, 6),
            "tenant_count": tenant_count,
            "model_count": len(set(e.model for e in self._entries)),
        }
