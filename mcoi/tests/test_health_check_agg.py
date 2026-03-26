"""Tests for Phase 226C — Health Check Aggregation."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.health_check_agg import (
    HealthCheckAggregator, HealthCheckDef, HealthStatus,
)


@pytest.fixture
def agg():
    a = HealthCheckAggregator()
    a.register(HealthCheckDef("db", lambda: {"status": "healthy"}, weight=2.0))
    a.register(HealthCheckDef("cache", lambda: {"status": "healthy"}, weight=1.0))
    a.register(HealthCheckDef("llm", lambda: {"status": "healthy"}, weight=1.5, critical=True))
    return a


class TestHealthCheckAggregator:
    def test_all_healthy(self, agg):
        result = agg.run()
        assert result.status == HealthStatus.HEALTHY
        assert result.score == 100.0
        assert result.is_healthy

    def test_degraded_check(self):
        a = HealthCheckAggregator()
        a.register(HealthCheckDef("ok", lambda: {"status": "healthy"}, weight=1.0))
        a.register(HealthCheckDef("slow", lambda: {"status": "degraded"}, weight=1.0))
        result = a.run()
        assert result.status == HealthStatus.DEGRADED
        assert result.score == 75.0  # (100 + 50) / 2

    def test_unhealthy_check(self):
        a = HealthCheckAggregator()
        a.register(HealthCheckDef("ok", lambda: {"status": "healthy"}, weight=1.0))
        a.register(HealthCheckDef("dead", lambda: {"status": "unhealthy"}, weight=1.0))
        result = a.run()
        assert result.status == HealthStatus.UNHEALTHY
        assert result.score == 50.0

    def test_critical_check_failure(self):
        a = HealthCheckAggregator()
        a.register(HealthCheckDef("ok", lambda: {"status": "healthy"}, weight=1.0))
        a.register(HealthCheckDef("critical", lambda: {"status": "unhealthy"}, weight=1.0, critical=True))
        result = a.run()
        assert result.status == HealthStatus.UNHEALTHY

    def test_exception_in_check(self):
        a = HealthCheckAggregator()
        a.register(HealthCheckDef("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")), weight=1.0))
        result = a.run()
        assert result.status == HealthStatus.UNHEALTHY
        assert "boom" in result.checks[0].message

    def test_empty_aggregator(self):
        a = HealthCheckAggregator()
        result = a.run()
        assert result.status == HealthStatus.HEALTHY
        assert result.score == 100.0

    def test_weighted_score(self):
        a = HealthCheckAggregator()
        a.register(HealthCheckDef("heavy", lambda: {"status": "healthy"}, weight=3.0))
        a.register(HealthCheckDef("light", lambda: {"status": "degraded"}, weight=1.0))
        result = a.run()
        # (3*100 + 1*50) / 4 = 87.5
        assert result.score == 87.5

    def test_to_dict(self, agg):
        result = agg.run()
        d = result.to_dict()
        assert d["status"] == "healthy"
        assert d["score"] == 100.0
        assert len(d["checks"]) == 3

    def test_last_result(self, agg):
        assert agg.last_result is None
        agg.run()
        assert agg.last_result is not None

    def test_summary(self, agg):
        agg.run()
        s = agg.summary()
        assert s["registered_checks"] == 3
        assert s["total_runs"] == 1
        assert s["last_status"] == "healthy"

    def test_unregister(self, agg):
        agg.unregister("cache")
        assert agg.check_count == 2
