"""Phase 161 — Bundle Portfolio Optimization Tests."""
import pytest
from mcoi_runtime.pilot.bundle_optimization import (
    ALL_OFFERINGS, LAND_EXPAND_SEQUENCES, rank_offerings, best_land_expand,
    allocation_recommendation, portfolio_dashboard, BundleScore,
)

class TestScoring:
    def test_13_offerings(self):
        assert len(ALL_OFFERINGS) == 13

    def test_composite_range(self):
        for v in ALL_OFFERINGS.values():
            assert 0 <= v.composite <= 1

    def test_recommendation_values(self):
        for v in ALL_OFFERINGS.values():
            assert v.recommendation in ("push_hard", "grow", "maintain", "review")

class TestRanking:
    def test_rank_order(self):
        ranked = rank_offerings()
        assert len(ranked) == 13
        assert ranked[0][1] >= ranked[-1][1]

    def test_strongest_weakest_different(self):
        ranked = rank_offerings()
        assert ranked[0][0] != ranked[-1][0]

class TestExpansion:
    def test_6_sequences(self):
        assert len(LAND_EXPAND_SEQUENCES) == 6

    def test_best_multiplier(self):
        best = best_land_expand()
        assert best[0]["acv_multiplier"] >= 1.5

class TestAllocation:
    def test_sums_near_100(self):
        alloc = allocation_recommendation()
        total = sum(v["pct"] for v in alloc.values())
        assert 99 <= total <= 101

class TestDashboard:
    def test_dashboard(self):
        d = portfolio_dashboard()
        assert d["total_offerings"] == 13
        assert d["strongest"]
        assert d["weakest"]
        assert d["total_portfolio_acv"] > 0
        assert len(d["best_land_expand"]) == 3

class TestGoldenProof:
    def test_full_optimization(self):
        ranked = rank_offerings()
        assert len(ranked) == 13
        alloc = allocation_recommendation()
        assert len(alloc) == 13
        d = portfolio_dashboard()
        assert len(d["push_hard"]) + len(d["grow"]) + len(d["maintain"]) + len(d["review"]) == 13
        best = best_land_expand()
        assert best[0]["acv_multiplier"] >= 1.5
