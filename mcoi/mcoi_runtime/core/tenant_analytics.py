"""Phase 221B — Tenant Analytics Dashboard.

Purpose: Per-tenant analytics combining all subsystem data into
    a single dashboard view. Provides operational intelligence
    for tenant management.
Governance scope: analytics computation only — read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class TenantAnalytics:
    """Complete analytics for a single tenant."""

    tenant_id: str
    llm_calls: int
    total_cost: float
    conversations: int
    workflows: int
    tool_invocations: int
    memories: int
    budget_utilization_pct: float
    active_sessions: int
    generated_at: str


class TenantAnalyticsEngine:
    """Computes per-tenant analytics from all subsystems."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._collectors: dict[str, Callable[[str], Any]] = {}

    def register_collector(self, metric: str, fn: Callable[[str], Any]) -> None:
        self._collectors[metric] = fn

    def compute(self, tenant_id: str) -> TenantAnalytics:
        data: dict[str, Any] = {}
        for metric, fn in self._collectors.items():
            try:
                data[metric] = fn(tenant_id)
            except Exception:
                data[metric] = 0

        return TenantAnalytics(
            tenant_id=tenant_id,
            llm_calls=data.get("llm_calls", 0),
            total_cost=data.get("total_cost", 0.0),
            conversations=data.get("conversations", 0),
            workflows=data.get("workflows", 0),
            tool_invocations=data.get("tool_invocations", 0),
            memories=data.get("memories", 0),
            budget_utilization_pct=data.get("budget_utilization_pct", 0.0),
            active_sessions=data.get("active_sessions", 0),
            generated_at=self._clock(),
        )

    def compute_all(self, tenant_ids: list[str]) -> list[TenantAnalytics]:
        return [self.compute(tid) for tid in tenant_ids]

    def summary(self) -> dict[str, Any]:
        return {"collectors": list(self._collectors.keys())}
