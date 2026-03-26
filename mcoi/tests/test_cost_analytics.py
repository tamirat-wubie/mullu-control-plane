"""Phase 209D — Cost analytics engine tests."""

import pytest
from mcoi_runtime.core.cost_analytics import CostAnalyticsEngine

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestCostAnalytics:
    def _engine(self):
        eng = CostAnalyticsEngine(clock=FIXED_CLOCK)
        eng.record("t1", "claude-sonnet", 0.003, 1000)
        eng.record("t1", "claude-sonnet", 0.005, 2000)
        eng.record("t1", "gpt-4o", 0.010, 3000)
        eng.record("t2", "claude-sonnet", 0.002, 500)
        return eng

    def test_tenant_breakdown(self):
        eng = self._engine()
        bd = eng.tenant_breakdown("t1")
        assert bd.call_count == 3
        assert bd.total_cost == pytest.approx(0.018, abs=0.001)
        assert "claude-sonnet" in bd.by_model
        assert "gpt-4o" in bd.by_model

    def test_empty_tenant(self):
        eng = self._engine()
        bd = eng.tenant_breakdown("nonexistent")
        assert bd.call_count == 0
        assert bd.total_cost == 0.0

    def test_most_expensive_model(self):
        eng = self._engine()
        bd = eng.tenant_breakdown("t1")
        assert bd.most_expensive_model == "gpt-4o"

    def test_avg_cost(self):
        eng = self._engine()
        bd = eng.tenant_breakdown("t1")
        assert bd.avg_cost_per_call == pytest.approx(0.006, abs=0.001)

    def test_project(self):
        eng = self._engine()
        proj = eng.project("t1", budget=1.0, days_elapsed=1.0)
        assert proj.current_daily_rate > 0
        assert proj.projected_monthly > 0
        assert proj.budget_remaining > 0
        assert proj.days_until_exhaustion > 0

    def test_project_no_budget(self):
        eng = self._engine()
        proj = eng.project("t1")
        assert proj.days_until_exhaustion == -1.0

    def test_top_spenders(self):
        eng = self._engine()
        top = eng.top_spenders(limit=5)
        assert len(top) == 2
        assert top[0].tenant_id == "t1"  # t1 spent more

    def test_model_usage(self):
        eng = self._engine()
        usage = eng.model_usage()
        assert "claude-sonnet" in usage
        assert usage["claude-sonnet"]["calls"] == 3

    def test_summary(self):
        eng = self._engine()
        s = eng.summary()
        assert s["total_entries"] == 4
        assert s["tenant_count"] == 2
        assert s["model_count"] == 2

    def test_record(self):
        eng = CostAnalyticsEngine(clock=FIXED_CLOCK)
        entry = eng.record("t1", "model", 0.01, 100)
        assert entry.tenant_id == "t1"
        assert eng.entry_count == 1
