"""Phase 140 — Product-Line Portfolio Governance / Capital Allocation."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class PackScore:
    pack_domain: str
    pipeline_strength: float = 0.0  # 0-10
    conversion_rate: float = 0.0  # 0-1
    deployment_effort: float = 0.0  # 0-10 (lower is better)
    support_burden: float = 0.0  # 0-10 (lower is better)
    gross_margin: float = 0.0  # 0-1
    renewal_strength: float = 0.0  # 0-10
    expansion_potential: float = 0.0  # 0-10
    moat_strength: float = 0.0  # 0-10

    @property
    def composite(self) -> float:
        return round(
            (self.pipeline_strength / 10) * 0.15 +
            self.conversion_rate * 0.15 +
            (1 - self.deployment_effort / 10) * 0.10 +
            (1 - self.support_burden / 10) * 0.10 +
            self.gross_margin * 0.15 +
            (self.renewal_strength / 10) * 0.10 +
            (self.expansion_potential / 10) * 0.15 +
            (self.moat_strength / 10) * 0.10,
            3
        )

    @property
    def recommendation(self) -> str:
        s = self.composite
        if s >= 0.75: return "invest"
        if s >= 0.60: return "maintain"
        if s >= 0.45: return "fix"
        if s >= 0.30: return "incubate"
        return "sunset_watch"

@dataclass
class CapitalAllocation:
    pack_domain: str
    engineering_pct: float = 0.0
    gtm_pct: float = 0.0
    delivery_pct: float = 0.0
    support_pct: float = 0.0
    partner_pct: float = 0.0

CROSS_SELL_SEQUENCES = {
    "land_regulated_expand_financial": {
        "land": "regulated_ops",
        "expand_to": ["financial_control", "enterprise_service"],
        "estimated_expansion_multiplier": 2.5,
        "reason": "Compliance teams often own financial controls too",
    },
    "land_factory_expand_supply_chain": {
        "land": "factory_quality",
        "expand_to": ["supply_chain", "financial_control"],
        "estimated_expansion_multiplier": 3.0,
        "reason": "Manufacturing needs procurement and financial visibility",
    },
    "land_service_expand_regulated": {
        "land": "enterprise_service",
        "expand_to": ["regulated_ops", "financial_control"],
        "estimated_expansion_multiplier": 2.0,
        "reason": "IT governance often adjacent to compliance",
    },
    "land_financial_expand_regulated": {
        "land": "financial_control",
        "expand_to": ["regulated_ops", "supply_chain"],
        "estimated_expansion_multiplier": 2.2,
        "reason": "Finance teams need audit trail and procurement visibility",
    },
    "land_research_expand_regulated": {
        "land": "research_lab",
        "expand_to": ["regulated_ops"],
        "estimated_expansion_multiplier": 1.5,
        "reason": "Research compliance often requires regulated ops",
    },
    "land_supply_expand_factory": {
        "land": "supply_chain",
        "expand_to": ["factory_quality", "financial_control"],
        "estimated_expansion_multiplier": 2.8,
        "reason": "Procurement teams serve manufacturing and finance",
    },
}

class PortfolioGovernanceEngine:
    """Governs product-line investment decisions."""

    def __init__(self):
        self._scores: dict[str, PackScore] = {}
        self._allocations: dict[str, CapitalAllocation] = {}

    def score_pack(self, score: PackScore) -> None:
        self._scores[score.pack_domain] = score

    def get_score(self, pack: str) -> PackScore | None:
        return self._scores.get(pack)

    def rank_packs(self) -> list[tuple[str, float, str]]:
        return sorted(
            [(s.pack_domain, s.composite, s.recommendation) for s in self._scores.values()],
            key=lambda x: x[1], reverse=True,
        )

    def allocate(self, allocation: CapitalAllocation) -> None:
        self._allocations[allocation.pack_domain] = allocation

    def auto_allocate(self) -> dict[str, CapitalAllocation]:
        ranked = self.rank_packs()
        if not ranked:
            return {}
        total = sum(s.composite for s in self._scores.values())
        if total == 0:
            return {}
        for pack, composite, rec in ranked:
            weight = composite / total
            self._allocations[pack] = CapitalAllocation(
                pack_domain=pack,
                engineering_pct=round(weight * 100, 1),
                gtm_pct=round(weight * 100, 1),
                delivery_pct=round(weight * 100, 1),
                support_pct=round(weight * 100, 1),
                partner_pct=round(weight * 100, 1),
            )
        return dict(self._allocations)

    def best_land_sequence(self) -> list[tuple[str, float]]:
        return sorted(
            [(k, v["estimated_expansion_multiplier"]) for k, v in CROSS_SELL_SEQUENCES.items()],
            key=lambda x: x[1], reverse=True,
        )

    def identify_weakest(self) -> str | None:
        ranked = self.rank_packs()
        return ranked[-1][0] if ranked else None

    def identify_strongest(self) -> str | None:
        ranked = self.rank_packs()
        return ranked[0][0] if ranked else None

    def portfolio_dashboard(self) -> dict[str, Any]:
        ranked = self.rank_packs()
        return {
            "total_packs": len(self._scores),
            "rankings": ranked,
            "invest": [p for p, _, r in ranked if r == "invest"],
            "maintain": [p for p, _, r in ranked if r == "maintain"],
            "fix": [p for p, _, r in ranked if r == "fix"],
            "incubate": [p for p, _, r in ranked if r == "incubate"],
            "sunset_watch": [p for p, _, r in ranked if r == "sunset_watch"],
            "strongest": self.identify_strongest(),
            "weakest": self.identify_weakest(),
            "best_land_sequence": self.best_land_sequence()[:3],
            "allocations": {k: {"engineering": v.engineering_pct, "gtm": v.gtm_pct} for k, v in self._allocations.items()},
        }
