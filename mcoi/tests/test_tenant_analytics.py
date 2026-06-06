"""Phase 221B — Tenant analytics tests."""

import math

import pytest
from mcoi_runtime.core.tenant_analytics import TenantAnalyticsEngine


def fixed_clock() -> str:
    return "2026-03-26T12:00:00Z"


class TestTenantAnalytics:
    def test_compute(self):
        eng = TenantAnalyticsEngine(clock=fixed_clock)
        eng.register_collector("llm_calls", lambda tid: 42)
        eng.register_collector("total_cost", lambda tid: 1.5)
        analytics = eng.compute("t1")
        assert analytics.tenant_id == "t1"
        assert analytics.llm_calls == 42
        assert analytics.total_cost == 1.5

    def test_missing_collector(self):
        eng = TenantAnalyticsEngine(clock=fixed_clock)
        analytics = eng.compute("t1")
        assert analytics.llm_calls == 0

    def test_error_collector(self):
        eng = TenantAnalyticsEngine(clock=fixed_clock)
        eng.register_collector("llm_calls", lambda tid: (_ for _ in ()).throw(RuntimeError("fail")))
        analytics = eng.compute("t1")
        assert analytics.llm_calls == 0

    def test_compute_all(self):
        eng = TenantAnalyticsEngine(clock=fixed_clock)
        eng.register_collector("llm_calls", lambda tid: 10)
        results = eng.compute_all(["t1", "t2"])
        assert len(results) == 2

    def test_summary(self):
        eng = TenantAnalyticsEngine(clock=fixed_clock)
        eng.register_collector("a", lambda tid: 0)
        assert "a" in eng.summary()["collectors"]

    @pytest.mark.parametrize(
        ("metric", "value", "expected_field"),
        [
            ("llm_calls", "secret-count", "llm_calls"),
            ("conversations", True, "conversations"),
            ("workflows", -1, "workflows"),
            ("tool_invocations", 1.5, "tool_invocations"),
            ("memories", math.inf, "memories"),
            ("active_sessions", math.nan, "active_sessions"),
            ("total_cost", -0.01, "total_cost"),
            ("budget_utilization_pct", False, "budget_utilization_pct"),
        ],
    )
    def test_invalid_known_collector_values_fail_closed_to_zero(self, metric, value, expected_field):
        eng = TenantAnalyticsEngine(clock=fixed_clock)
        eng.register_collector(metric, lambda tid: value)
        analytics = eng.compute("t1")
        assert getattr(analytics, expected_field) == 0
        assert analytics.tenant_id == "t1"
        assert eng.summary()["collectors"] == [metric]

    def test_valid_known_collector_values_are_normalized(self):
        eng = TenantAnalyticsEngine(clock=lambda: " 2026-03-26T12:00:00Z ")
        eng.register_collector("llm_calls", lambda tid: 42.0)
        eng.register_collector("total_cost", lambda tid: 3)
        eng.register_collector("budget_utilization_pct", lambda tid: 12.5)
        analytics = eng.compute(" t1 ")
        assert analytics.tenant_id == "t1"
        assert analytics.llm_calls == 42
        assert analytics.total_cost == 3.0
        assert analytics.budget_utilization_pct == 12.5
        assert analytics.generated_at == "2026-03-26T12:00:00Z"

    @pytest.mark.parametrize("tenant_id", ["", "   ", 12, "t" * 257])
    def test_compute_rejects_invalid_tenant_identity(self, tenant_id):
        eng = TenantAnalyticsEngine(clock=fixed_clock)
        with pytest.raises(ValueError, match="tenant_id"):
            eng.compute(tenant_id)
        assert eng.summary()["collectors"] == []

    @pytest.mark.parametrize("metric", ["", "   ", 12, "m" * 257])
    def test_register_collector_rejects_invalid_metric_identity(self, metric):
        eng = TenantAnalyticsEngine(clock=fixed_clock)
        with pytest.raises(ValueError, match="metric"):
            eng.register_collector(metric, lambda tid: 0)
        assert eng.summary()["collectors"] == []

    def test_register_collector_requires_callable(self):
        eng = TenantAnalyticsEngine(clock=fixed_clock)
        with pytest.raises(ValueError, match="collector"):
            eng.register_collector("llm_calls", object())
        assert eng.summary()["collectors"] == []

    @pytest.mark.parametrize("clock_value", ["", "   ", 123])
    def test_compute_rejects_invalid_clock_timestamp(self, clock_value):
        eng = TenantAnalyticsEngine(clock=lambda: clock_value)
        with pytest.raises(ValueError, match="generated_at"):
            eng.compute("t1")
        assert eng.summary()["collectors"] == []
