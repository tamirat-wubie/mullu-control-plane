"""Phase 217B — Usage Reporter.

Purpose: Per-tenant usage reports combining LLM calls, costs, budgets,
    and activity metrics into a single exportable report.
Governance scope: report generation only — read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class UsageReport:
    """Complete usage report for a tenant."""

    tenant_id: str
    llm_calls: int
    total_cost: float
    budget_remaining: float
    conversations: int
    workflows: int
    tool_invocations: int
    events_published: int
    report_period: str
    generated_at: str


class UsageReporter:
    """Generates per-tenant usage reports."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._data_fns: dict[str, Callable[[str], Any]] = {}

    def register_source(self, name: str, fn: Callable[[str], Any]) -> None:
        self._data_fns[name] = fn

    def generate(self, tenant_id: str, period: str = "current") -> UsageReport:
        data: dict[str, Any] = {}
        for name, fn in self._data_fns.items():
            try:
                data[name] = fn(tenant_id)
            except Exception:
                data[name] = 0

        return UsageReport(
            tenant_id=tenant_id,
            llm_calls=data.get("llm_calls", 0),
            total_cost=data.get("total_cost", 0.0),
            budget_remaining=data.get("budget_remaining", 0.0),
            conversations=data.get("conversations", 0),
            workflows=data.get("workflows", 0),
            tool_invocations=data.get("tool_invocations", 0),
            events_published=data.get("events_published", 0),
            report_period=period,
            generated_at=self._clock(),
        )

    def summary(self) -> dict[str, Any]:
        return {"sources": list(self._data_fns.keys())}
