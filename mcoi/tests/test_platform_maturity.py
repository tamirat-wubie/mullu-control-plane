"""Phases 167-170 — Platform Maturity & Roadmap Tests."""
import pytest
from mcoi_runtime.pilot.platform_maturity import assess_platform_maturity, company_dashboard
from mcoi_runtime.pilot.roadmap_next import NEXT_ROADMAP, roadmap_summary, SESSION_SUMMARY

class TestMaturity:
    def test_10_dimensions(self):
        m = assess_platform_maturity()
        assert m["total_dimensions"] == 10

    def test_overall_advanced_or_better(self):
        m = assess_platform_maturity()
        assert m["maturity_level"] in ("advanced", "world_class")
        assert m["overall_score"] >= 8.0

    def test_strongest_weakest_different(self):
        m = assess_platform_maturity()
        assert m["strongest"] != m["weakest"]

class TestDashboard:
    def test_dashboard_structure(self):
        d = company_dashboard()
        assert d["platform"]["phases"] >= 166
        assert d["products"]["packs"] == 8
        assert d["products"]["bundles"] == 6
        assert d["market"]["regions"] == 7
        assert len(d["growth"]["channels"]) == 3
        assert len(d["intelligence"]["reasoning_layers"]) == 6

class TestRoadmap:
    def test_10_items(self):
        assert len(NEXT_ROADMAP) == 10

    def test_summary(self):
        s = roadmap_summary()
        assert s["total_items"] == 10
        assert len(s["immediate"]) >= 2

    def test_categories_covered(self):
        s = roadmap_summary()
        for cat in ("product", "platform", "distribution", "autonomy"):
            assert s["by_category"][cat] >= 1

class TestSessionSummary:
    def test_session_metrics(self):
        assert SESSION_SUMMARY["total_phases"] >= 166
        assert SESSION_SUMMARY["total_tests"] >= 42000
        assert SESSION_SUMMARY["products"] == 8
        assert SESSION_SUMMARY["bundles"] == 6

class TestGoldenProof:
    def test_full_maturity_assessment(self):
        m = assess_platform_maturity()
        d = company_dashboard()
        r = roadmap_summary()

        assert m["overall_score"] >= 8.0
        assert d["products"]["total_offerings"] >= 14
        assert d["intelligence"]["agent_roles"] == 6
        assert r["total_items"] == 10
        assert SESSION_SUMMARY["statement"]
