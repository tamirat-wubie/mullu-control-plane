"""Phase 161 — Bundle Portfolio Optimization."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class BundleScore:
    bundle_name: str
    acv: float
    gross_margin: float  # 0-1
    deployment_effort_days: int
    support_burden_monthly: float
    expansion_rate: float  # 0-1
    renewal_strength: float  # 0-10

    @property
    def composite(self) -> float:
        return round(
            (min(self.acv, 100000) / 100000) * 0.25 +
            self.gross_margin * 0.20 +
            (1 - min(self.deployment_effort_days, 30) / 30) * 0.15 +
            (1 - min(self.support_burden_monthly, 5000) / 5000) * 0.10 +
            self.expansion_rate * 0.15 +
            (self.renewal_strength / 10) * 0.15,
            3
        )

    @property
    def recommendation(self) -> str:
        s = self.composite
        if s >= 0.7: return "push_hard"
        if s >= 0.55: return "grow"
        if s >= 0.4: return "maintain"
        return "review"

ALL_OFFERINGS = {
    "regulated_financial_suite": BundleScore("Regulated Financial Suite", 54000, 0.72, 21, 1200, 0.45, 8.5),
    "industrial_operations_suite": BundleScore("Industrial Operations Suite", 78000, 0.65, 28, 2000, 0.55, 7.5),
    "healthcare_financial_suite": BundleScore("Healthcare Financial Suite", 69000, 0.70, 24, 1500, 0.40, 8.0),
    "public_sector_governance_suite": BundleScore("Public Sector Governance Suite", 48000, 0.68, 21, 1100, 0.35, 7.0),
    "service_governance_suite": BundleScore("Enterprise Service Governance Suite", 48000, 0.70, 18, 900, 0.50, 8.0),
    "regulated_ops_standalone": BundleScore("Regulated Operations (standalone)", 30000, 0.75, 14, 600, 0.60, 9.0),
    "enterprise_service_standalone": BundleScore("Enterprise Service (standalone)", 30000, 0.70, 14, 700, 0.45, 7.5),
    "financial_control_standalone": BundleScore("Financial Control (standalone)", 36000, 0.73, 16, 800, 0.50, 7.5),
    "factory_quality_standalone": BundleScore("Factory Quality (standalone)", 48000, 0.62, 21, 1500, 0.55, 7.0),
    "supply_chain_standalone": BundleScore("Supply Chain (standalone)", 30000, 0.60, 18, 1200, 0.40, 6.5),
    "research_lab_standalone": BundleScore("Research / Lab (standalone)", 30000, 0.65, 18, 800, 0.25, 5.5),
    "public_sector_standalone": BundleScore("Public Sector (standalone)", 30000, 0.68, 16, 700, 0.35, 6.5),
    "healthcare_standalone": BundleScore("Healthcare (standalone)", 48000, 0.67, 20, 1200, 0.30, 7.0),
}

LAND_EXPAND_SEQUENCES = [
    {"land": "regulated_ops_standalone", "expand_to": "regulated_financial_suite", "acv_multiplier": 1.8, "typical_months": 3},
    {"land": "regulated_ops_standalone", "expand_to": "service_governance_suite", "acv_multiplier": 1.6, "typical_months": 4},
    {"land": "enterprise_service_standalone", "expand_to": "service_governance_suite", "acv_multiplier": 1.6, "typical_months": 3},
    {"land": "factory_quality_standalone", "expand_to": "industrial_operations_suite", "acv_multiplier": 1.6, "typical_months": 2},
    {"land": "healthcare_standalone", "expand_to": "healthcare_financial_suite", "acv_multiplier": 1.44, "typical_months": 3},
    {"land": "public_sector_standalone", "expand_to": "public_sector_governance_suite", "acv_multiplier": 1.6, "typical_months": 4},
]

def rank_offerings() -> list[tuple[str, float, str]]:
    return sorted([(k, v.composite, v.recommendation) for k, v in ALL_OFFERINGS.items()], key=lambda x: x[1], reverse=True)

def best_land_expand() -> list[dict[str, Any]]:
    return sorted(LAND_EXPAND_SEQUENCES, key=lambda x: x["acv_multiplier"], reverse=True)

def allocation_recommendation() -> dict[str, dict[str, float]]:
    ranked = rank_offerings()
    total = sum(v.composite for v in ALL_OFFERINGS.values())
    return {k: {"pct": round(v.composite / total * 100, 1), "action": v.recommendation} for k, v in ALL_OFFERINGS.items()}

def portfolio_dashboard() -> dict[str, Any]:
    ranked = rank_offerings()
    push = [r[0] for r in ranked if r[2] == "push_hard"]
    grow = [r[0] for r in ranked if r[2] == "grow"]
    maintain = [r[0] for r in ranked if r[2] == "maintain"]
    review = [r[0] for r in ranked if r[2] == "review"]
    total_acv = sum(v.acv for v in ALL_OFFERINGS.values())
    avg_margin = sum(v.gross_margin for v in ALL_OFFERINGS.values()) / len(ALL_OFFERINGS)
    return {
        "total_offerings": len(ALL_OFFERINGS),
        "push_hard": push, "grow": grow, "maintain": maintain, "review": review,
        "total_portfolio_acv": total_acv,
        "avg_margin": round(avg_margin, 3),
        "best_land_expand": best_land_expand()[:3],
        "strongest": ranked[0][0],
        "weakest": ranked[-1][0],
    }
