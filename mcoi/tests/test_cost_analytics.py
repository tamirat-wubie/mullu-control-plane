"""Phase 209D — Cost analytics engine tests."""

import math

import pytest
from mcoi_runtime.core.cost_analytics import CostAnalyticsEngine

def fixed_clock() -> str:
    return "2026-03-26T12:00:00Z"


class TestCostAnalytics:
    def _engine(self):
        eng = CostAnalyticsEngine(clock=fixed_clock)
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
        eng = CostAnalyticsEngine(clock=fixed_clock)
        entry = eng.record("t1", "model", 0.01, 100)
        assert entry.tenant_id == "t1"
        assert eng.entry_count == 1

    @pytest.mark.parametrize(
        ("args", "field_name"),
        [
            (("", "model", 0.01, 100), "tenant_id"),
            (("   ", "model", 0.01, 100), "tenant_id"),
            ((123, "model", 0.01, 100), "tenant_id"),
            (("t" * 257, "model", 0.01, 100), "tenant_id"),
            (("t1", "", 0.01, 100), "model"),
            (("t1", "   ", 0.01, 100), "model"),
            (("t1", 123, 0.01, 100), "model"),
            (("t1", "m" * 257, 0.01, 100), "model"),
            (("t1", "model", -0.01, 100), "cost"),
            (("t1", "model", math.nan, 100), "cost"),
            (("t1", "model", math.inf, 100), "cost"),
            (("t1", "model", True, 100), "cost"),
            (("t1", "model", "0.01", 100), "cost"),
            (("t1", "model", 0.01, -1), "tokens"),
            (("t1", "model", 0.01, 1.5), "tokens"),
            (("t1", "model", 0.01, math.inf), "tokens"),
            (("t1", "model", 0.01, False), "tokens"),
            (("t1", "model", 0.01, "100"), "tokens"),
        ],
    )
    def test_record_rejects_invalid_financial_samples_without_mutating_state(self, args, field_name):
        eng = CostAnalyticsEngine(clock=fixed_clock)
        with pytest.raises(ValueError, match=field_name):
            eng.record(*args)
        assert eng.entry_count == 0
        assert eng.summary()["total_entries"] == 0
        assert eng.model_usage() == {}

    def test_record_normalizes_identity_and_integer_like_tokens(self):
        eng = CostAnalyticsEngine(clock=lambda: " 2026-03-26T12:00:00Z ")
        entry = eng.record(" t1 ", " model ", 1, 100.0)
        assert entry.tenant_id == "t1"
        assert entry.model == "model"
        assert entry.cost == 1.0
        assert entry.tokens == 100
        assert entry.timestamp == "2026-03-26T12:00:00Z"

    @pytest.mark.parametrize("clock_value", ["", "   ", 123])
    def test_record_rejects_invalid_clock_timestamp_without_mutating_state(self, clock_value):
        eng = CostAnalyticsEngine(clock=lambda: clock_value)
        with pytest.raises(ValueError, match="timestamp"):
            eng.record("t1", "model", 0.01, 100)
        assert eng.entry_count == 0
        assert eng.summary()["tenant_count"] == 0

    @pytest.mark.parametrize("tenant_id", ["", "   ", 12, "t" * 257])
    def test_tenant_breakdown_rejects_invalid_tenant_identity(self, tenant_id):
        eng = self._engine()
        with pytest.raises(ValueError, match="tenant_id"):
            eng.tenant_breakdown(tenant_id)
        assert eng.entry_count == 4

    @pytest.mark.parametrize(
        ("kwargs", "field_name"),
        [
            ({"budget": -0.01}, "budget"),
            ({"budget": math.nan}, "budget"),
            ({"budget": True}, "budget"),
            ({"days_elapsed": 0}, "days_elapsed"),
            ({"days_elapsed": -1}, "days_elapsed"),
            ({"days_elapsed": math.inf}, "days_elapsed"),
            ({"days_elapsed": "1"}, "days_elapsed"),
        ],
    )
    def test_project_rejects_invalid_projection_inputs(self, kwargs, field_name):
        eng = self._engine()
        with pytest.raises(ValueError, match=field_name):
            eng.project("t1", **kwargs)
        assert eng.entry_count == 4

    @pytest.mark.parametrize("limit", [-1, 1.5, math.inf, True, "10"])
    def test_top_spenders_rejects_invalid_limit_values(self, limit):
        eng = self._engine()
        with pytest.raises(ValueError, match="limit"):
            eng.top_spenders(limit=limit)
        assert eng.entry_count == 4

    def test_top_spenders_zero_limit_returns_empty_list(self):
        eng = self._engine()
        top = eng.top_spenders(limit=0)
        assert top == []
        assert eng.entry_count == 4
