"""Phase 137 — Multi-Pack Margin Optimization / Profitability Engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# 137A — Unit Economics
@dataclass
class CustomerUnitEconomics:
    customer_id: str
    pack: str
    monthly_revenue: float = 0.0
    implementation_cost: float = 0.0
    monthly_support_cost: float = 0.0
    monthly_connector_cost: float = 0.0
    monthly_compute_cost: float = 0.0
    delivery_hours: float = 0.0
    hypercare_hours: float = 0.0

    @property
    def total_monthly_cost(self) -> float:
        return self.monthly_support_cost + self.monthly_connector_cost + self.monthly_compute_cost

    @property
    def gross_margin(self) -> float:
        if self.monthly_revenue == 0: return 0.0
        return round((self.monthly_revenue - self.total_monthly_cost) / self.monthly_revenue, 3)

    @property
    def margin_status(self) -> str:
        m = self.gross_margin
        if m >= 0.7: return "healthy"
        if m >= 0.5: return "acceptable"
        if m >= 0.3: return "thin"
        return "unprofitable"

# 137C — Pricing Fitness
@dataclass
class PricingFitness:
    customer_id: str
    current_tier: str
    actual_cost_ratio: float  # cost/revenue
    usage_intensity: str  # "light", "moderate", "heavy"
    recommendation: str  # "appropriate", "underpriced", "upgrade_candidate", "premium_support_candidate", "over_serviced"

# 137E — Expansion Efficiency
@dataclass
class ExpansionRecommendation:
    customer_id: str
    current_pack: str
    recommended_pack: str
    expected_additional_mrr: float
    support_risk: str  # "low", "medium", "high"
    profit_aware: bool = True
    reason: str = ""

class ProfitabilityEngine:
    """Tracks and optimizes unit economics across the portfolio."""

    def __init__(self):
        self._economics: dict[str, CustomerUnitEconomics] = {}
        self._fitness: dict[str, PricingFitness] = {}
        self._expansions: list[ExpansionRecommendation] = []

    def register_economics(self, economics: CustomerUnitEconomics) -> None:
        self._economics[economics.customer_id] = economics

    def get_economics(self, customer_id: str) -> CustomerUnitEconomics:
        return self._economics[customer_id]

    # 137B — Margin Dashboard
    def margin_by_pack(self) -> dict[str, float]:
        pack_revenue: dict[str, float] = {}
        pack_cost: dict[str, float] = {}
        for e in self._economics.values():
            pack_revenue[e.pack] = pack_revenue.get(e.pack, 0) + e.monthly_revenue
            pack_cost[e.pack] = pack_cost.get(e.pack, 0) + e.total_monthly_cost
        return {p: round((pack_revenue[p] - pack_cost[p]) / pack_revenue[p], 3) if pack_revenue[p] else 0.0 for p in pack_revenue}

    def below_margin_target(self, target: float = 0.5) -> list[CustomerUnitEconomics]:
        return [e for e in self._economics.values() if e.gross_margin < target]

    def support_heavy_accounts(self, threshold: float = 500.0) -> list[CustomerUnitEconomics]:
        return [e for e in self._economics.values() if e.monthly_support_cost > threshold]

    def highest_margin_pack(self) -> str | None:
        margins = self.margin_by_pack()
        return max(margins, key=margins.get) if margins else None

    def lowest_margin_pack(self) -> str | None:
        margins = self.margin_by_pack()
        return min(margins, key=margins.get) if margins else None

    # 137C — Pricing Fitness
    def assess_pricing(self, customer_id: str) -> PricingFitness:
        e = self._economics[customer_id]
        cost_ratio = e.total_monthly_cost / e.monthly_revenue if e.monthly_revenue else 1.0

        if e.monthly_support_cost > 800: usage = "heavy"
        elif e.monthly_support_cost > 300: usage = "moderate"
        else: usage = "light"

        if cost_ratio > 0.7: rec = "underpriced"
        elif cost_ratio > 0.5 and usage == "heavy": rec = "premium_support_candidate"
        elif cost_ratio < 0.2 and usage == "light": rec = "over_serviced"
        elif usage == "heavy": rec = "upgrade_candidate"
        else: rec = "appropriate"

        fitness = PricingFitness(customer_id, e.pack, round(cost_ratio, 3), usage, rec)
        self._fitness[customer_id] = fitness
        return fitness

    # 137D — Delivery Efficiency
    def delivery_efficiency_report(self) -> dict[str, Any]:
        if not self._economics: return {"accounts": 0}
        avg_delivery = sum(e.delivery_hours for e in self._economics.values()) / len(self._economics)
        avg_hypercare = sum(e.hypercare_hours for e in self._economics.values()) / len(self._economics)
        by_pack = {}
        for e in self._economics.values():
            by_pack.setdefault(e.pack, []).append(e.delivery_hours)
        pack_avg = {p: round(sum(hrs)/len(hrs), 1) for p, hrs in by_pack.items()}
        return {
            "accounts": len(self._economics),
            "avg_delivery_hours": round(avg_delivery, 1),
            "avg_hypercare_hours": round(avg_hypercare, 1),
            "delivery_hours_by_pack": pack_avg,
        }

    # 137E — Expansion
    def recommend_expansion(self, customer_id: str, recommended_pack: str, expected_mrr: float) -> ExpansionRecommendation:
        e = self._economics.get(customer_id)
        support_risk = "high" if e and e.monthly_support_cost > 500 else "medium" if e and e.monthly_support_cost > 200 else "low"
        profit_aware = support_risk != "high"
        reason = f"Current margin {e.gross_margin if e else 0}, support risk {support_risk}"
        rec = ExpansionRecommendation(customer_id, e.pack if e else "unknown", recommended_pack, expected_mrr, support_risk, profit_aware, reason)
        self._expansions.append(rec)
        return rec

    # 137F — Executive Dashboard
    def profitability_dashboard(self) -> dict[str, Any]:
        return {
            "total_accounts": len(self._economics),
            "total_mrr": sum(e.monthly_revenue for e in self._economics.values()),
            "total_cost": sum(e.total_monthly_cost for e in self._economics.values()),
            "blended_margin": round(
                (sum(e.monthly_revenue for e in self._economics.values()) - sum(e.total_monthly_cost for e in self._economics.values())) /
                max(1, sum(e.monthly_revenue for e in self._economics.values())), 3
            ),
            "margin_by_pack": self.margin_by_pack(),
            "highest_margin_pack": self.highest_margin_pack(),
            "lowest_margin_pack": self.lowest_margin_pack(),
            "below_target_count": len(self.below_margin_target()),
            "support_heavy_count": len(self.support_heavy_accounts()),
            "expansion_recs": len(self._expansions),
            "profit_aware_expansions": sum(1 for r in self._expansions if r.profit_aware),
        }
