"""Phase 140 — Portfolio Governance Tests."""
import pytest
from mcoi_runtime.pilot.portfolio_governance import (
    PackScore, CapitalAllocation, CROSS_SELL_SEQUENCES,
    PortfolioGovernanceEngine,
)

def _all_scores() -> list[PackScore]:
    return [
        PackScore("regulated_ops", pipeline_strength=8, conversion_rate=0.6, deployment_effort=3, support_burden=4, gross_margin=0.7, renewal_strength=8, expansion_potential=7, moat_strength=7),
        PackScore("enterprise_service", pipeline_strength=7, conversion_rate=0.5, deployment_effort=4, support_burden=5, gross_margin=0.65, renewal_strength=7, expansion_potential=6, moat_strength=5),
        PackScore("financial_control", pipeline_strength=6, conversion_rate=0.45, deployment_effort=4, support_burden=4, gross_margin=0.75, renewal_strength=7, expansion_potential=8, moat_strength=6),
        PackScore("factory_quality", pipeline_strength=5, conversion_rate=0.35, deployment_effort=6, support_burden=6, gross_margin=0.6, renewal_strength=6, expansion_potential=9, moat_strength=9),
        PackScore("research_lab", pipeline_strength=4, conversion_rate=0.3, deployment_effort=5, support_burden=3, gross_margin=0.65, renewal_strength=5, expansion_potential=5, moat_strength=8),
        PackScore("supply_chain", pipeline_strength=5, conversion_rate=0.35, deployment_effort=5, support_burden=5, gross_margin=0.6, renewal_strength=6, expansion_potential=8, moat_strength=7),
    ]

class TestPackScoring:
    def test_composite_score(self):
        s = PackScore("test", pipeline_strength=10, conversion_rate=1.0, deployment_effort=0, support_burden=0, gross_margin=1.0, renewal_strength=10, expansion_potential=10, moat_strength=10)
        assert s.composite == 1.0

    def test_recommendation_invest(self):
        s = PackScore("test", pipeline_strength=8, conversion_rate=0.8, deployment_effort=2, support_burden=2, gross_margin=0.8, renewal_strength=8, expansion_potential=8, moat_strength=8)
        assert s.recommendation == "invest"

    def test_recommendation_sunset(self):
        s = PackScore("test", pipeline_strength=1, conversion_rate=0.1, deployment_effort=9, support_burden=9, gross_margin=0.1, renewal_strength=1, expansion_potential=1, moat_strength=1)
        assert s.recommendation == "sunset_watch"

class TestPortfolioEngine:
    def test_rank_6_packs(self):
        engine = PortfolioGovernanceEngine()
        for s in _all_scores():
            engine.score_pack(s)
        ranked = engine.rank_packs()
        assert len(ranked) == 6
        assert ranked[0][2] in ("invest", "maintain")

    def test_strongest_weakest(self):
        engine = PortfolioGovernanceEngine()
        for s in _all_scores():
            engine.score_pack(s)
        assert engine.identify_strongest() is not None
        assert engine.identify_weakest() is not None
        assert engine.identify_strongest() != engine.identify_weakest()

    def test_auto_allocate(self):
        engine = PortfolioGovernanceEngine()
        for s in _all_scores():
            engine.score_pack(s)
        allocs = engine.auto_allocate()
        assert len(allocs) == 6
        total_eng = sum(a.engineering_pct for a in allocs.values())
        assert 99.0 <= total_eng <= 101.0  # ~100% with rounding

class TestCrossSell:
    def test_sequences_exist(self):
        assert len(CROSS_SELL_SEQUENCES) == 6

    def test_best_sequence(self):
        engine = PortfolioGovernanceEngine()
        best = engine.best_land_sequence()
        assert len(best) >= 3
        assert best[0][1] >= best[1][1]  # sorted by multiplier

class TestDashboard:
    def test_portfolio_dashboard(self):
        engine = PortfolioGovernanceEngine()
        for s in _all_scores():
            engine.score_pack(s)
        engine.auto_allocate()
        d = engine.portfolio_dashboard()
        assert d["total_packs"] == 6
        assert d["strongest"] is not None
        assert d["weakest"] is not None
        assert len(d["best_land_sequence"]) == 3
        assert len(d["allocations"]) == 6

class TestGoldenProof:
    def test_full_portfolio_governance(self):
        engine = PortfolioGovernanceEngine()

        # 1. Score all 6 packs
        for s in _all_scores():
            engine.score_pack(s)
        ranked = engine.rank_packs()
        assert len(ranked) == 6

        # 2. Least attractive identifiable
        weakest = engine.identify_weakest()
        assert weakest is not None

        # 3. Highest-leverage identifiable
        strongest = engine.identify_strongest()
        assert strongest is not None
        assert strongest != weakest

        # 4. Cross-sell ranked by return
        best = engine.best_land_sequence()
        assert best[0][1] >= 2.0  # best multiplier >= 2x

        # 5. Staffing recommendation produced
        allocs = engine.auto_allocate()
        assert len(allocs) == 6
        strongest_alloc = allocs[strongest]
        weakest_alloc = allocs[weakest]
        assert strongest_alloc.engineering_pct > weakest_alloc.engineering_pct

        # 6. Executive portfolio view usable
        d = engine.portfolio_dashboard()
        assert d["total_packs"] == 6
        assert len(d["invest"]) + len(d["maintain"]) + len(d["fix"]) + len(d["incubate"]) + len(d["sunset_watch"]) == 6
