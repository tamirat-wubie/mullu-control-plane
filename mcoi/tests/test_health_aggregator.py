"""Phase 210B — Health aggregator tests."""

import pytest
from mcoi_runtime.core.health_aggregator import HealthAggregator

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestHealthAggregator:
    def test_all_healthy(self):
        agg = HealthAggregator(clock=FIXED_CLOCK)
        agg.register("a", lambda: {"status": "healthy"})
        agg.register("b", lambda: {"status": "healthy"})
        result = agg.compute()
        assert result.overall_score == 1.0
        assert result.status == "healthy"

    def test_one_degraded(self):
        agg = HealthAggregator(clock=FIXED_CLOCK)
        agg.register("a", lambda: {"status": "healthy"}, weight=1.0)
        agg.register("b", lambda: {"status": "degraded"}, weight=1.0)
        result = agg.compute()
        assert result.overall_score == 0.75
        assert result.status == "degraded"  # 0.75 < 0.8 threshold

    def test_one_unhealthy(self):
        agg = HealthAggregator(clock=FIXED_CLOCK)
        agg.register("a", lambda: {"status": "healthy"}, weight=1.0)
        agg.register("b", lambda: {"status": "unhealthy"}, weight=1.0)
        result = agg.compute()
        assert result.overall_score == 0.5
        assert result.status == "degraded"

    def test_all_unhealthy(self):
        agg = HealthAggregator(clock=FIXED_CLOCK)
        agg.register("a", lambda: {"status": "unhealthy"})
        result = agg.compute()
        assert result.overall_score == 0.0
        assert result.status == "unhealthy"

    def test_weighted_scoring(self):
        agg = HealthAggregator(clock=FIXED_CLOCK)
        agg.register("critical", lambda: {"status": "healthy"}, weight=10.0)
        agg.register("minor", lambda: {"status": "unhealthy"}, weight=1.0)
        result = agg.compute()
        # 10*1.0 + 1*0.0 / 11 ≈ 0.909
        assert result.overall_score > 0.9
        assert result.status == "healthy"

    def test_exception_marks_unhealthy(self):
        agg = HealthAggregator(clock=FIXED_CLOCK)
        agg.register("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = agg.compute()
        assert result.overall_score == 0.0
        assert result.components[0].status == "unhealthy"
        assert result.components[0].detail == "health check error (RuntimeError)"
        assert "boom" not in result.components[0].detail

    def test_empty(self):
        agg = HealthAggregator(clock=FIXED_CLOCK)
        result = agg.compute()
        assert result.overall_score == 1.0

    def test_component_count(self):
        agg = HealthAggregator(clock=FIXED_CLOCK)
        agg.register("a", lambda: {"status": "healthy"})
        agg.register("b", lambda: {"status": "healthy"})
        assert agg.component_count == 2
