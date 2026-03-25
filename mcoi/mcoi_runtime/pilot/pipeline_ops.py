"""Phase 133C+D — Pipeline Operations, Conversion Tracking, and Expansion Logic."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.pilot.revenue_funnel import RevenueFunnel

class PackPipeline:
    """Per-pack funnel tracking with cross-sell logic."""

    def __init__(self):
        self._funnels: dict[str, RevenueFunnel] = {}
        self._notes: list[dict[str, Any]] = []

    def get_funnel(self, pack_domain: str) -> RevenueFunnel:
        if pack_domain not in self._funnels:
            self._funnels[pack_domain] = RevenueFunnel()
        return self._funnels[pack_domain]

    def record_win_loss(self, pack_domain: str, customer_id: str, outcome: str, reason: str = "") -> None:
        self._notes.append({"pack": pack_domain, "customer": customer_id, "outcome": outcome, "reason": reason})

    def conversion_report(self) -> dict[str, Any]:
        return {
            pack: funnel.funnel_summary()
            for pack, funnel in self._funnels.items()
        }

    def total_mrr(self) -> float:
        return sum(f.total_mrr for f in self._funnels.values())

    def total_arr(self) -> float:
        return self.total_mrr() * 12

# Cross-sell / expansion logic (133D)
EXPANSION_PATHS = {
    "regulated_ops": ["financial_control", "enterprise_service"],
    "enterprise_service": ["regulated_ops", "financial_control"],
    "financial_control": ["regulated_ops", "enterprise_service"],
    "factory_quality": ["financial_control", "enterprise_service"],
}

@dataclass
class ExpansionScore:
    customer_id: str
    current_pack: str
    recommended_next: str
    score: float  # 0-1
    reason: str

def score_expansion(customer_id: str, current_pack: str, satisfaction: float, months_active: int) -> list[ExpansionScore]:
    paths = EXPANSION_PATHS.get(current_pack, [])
    results = []
    for next_pack in paths:
        score = min(1.0, (satisfaction / 10.0) * 0.6 + min(1.0, months_active / 12.0) * 0.4)
        reason = f"Satisfaction {satisfaction}/10, {months_active} months active"
        results.append(ExpansionScore(customer_id, current_pack, next_pack, round(score, 3), reason))
    return sorted(results, key=lambda x: x.score, reverse=True)
