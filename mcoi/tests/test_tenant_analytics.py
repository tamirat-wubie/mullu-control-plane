"""Phase 221B — Tenant analytics tests."""

import pytest
from mcoi_runtime.core.tenant_analytics import TenantAnalyticsEngine

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestTenantAnalytics:
    def test_compute(self):
        eng = TenantAnalyticsEngine(clock=FIXED_CLOCK)
        eng.register_collector("llm_calls", lambda tid: 42)
        eng.register_collector("total_cost", lambda tid: 1.5)
        analytics = eng.compute("t1")
        assert analytics.tenant_id == "t1"
        assert analytics.llm_calls == 42
        assert analytics.total_cost == 1.5

    def test_missing_collector(self):
        eng = TenantAnalyticsEngine(clock=FIXED_CLOCK)
        analytics = eng.compute("t1")
        assert analytics.llm_calls == 0

    def test_error_collector(self):
        eng = TenantAnalyticsEngine(clock=FIXED_CLOCK)
        eng.register_collector("llm_calls", lambda tid: (_ for _ in ()).throw(RuntimeError("fail")))
        analytics = eng.compute("t1")
        assert analytics.llm_calls == 0

    def test_compute_all(self):
        eng = TenantAnalyticsEngine(clock=FIXED_CLOCK)
        eng.register_collector("llm_calls", lambda tid: 10)
        results = eng.compute_all(["t1", "t2"])
        assert len(results) == 2

    def test_summary(self):
        eng = TenantAnalyticsEngine(clock=FIXED_CLOCK)
        eng.register_collector("a", lambda tid: 0)
        assert "a" in eng.summary()["collectors"]
