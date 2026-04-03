"""Phase 203C — Deep health check tests."""

import pytest
from mcoi_runtime.core.deep_health import DeepHealthChecker, HealthStatus

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestDeepHealthChecker:
    def test_no_checks(self):
        checker = DeepHealthChecker(clock=FIXED_CLOCK)
        result = checker.run()
        assert result.overall == HealthStatus.HEALTHY
        assert len(result.components) == 0

    def test_all_healthy(self):
        checker = DeepHealthChecker(clock=FIXED_CLOCK)
        checker.register("db", lambda: {"status": "healthy", "connections": 5})
        checker.register("llm", lambda: {"status": "healthy", "backend": "stub"})
        result = checker.run()
        assert result.overall == HealthStatus.HEALTHY
        assert len(result.components) == 2

    def test_one_degraded(self):
        checker = DeepHealthChecker(clock=FIXED_CLOCK)
        checker.register("db", lambda: {"status": "healthy"})
        checker.register("llm", lambda: {"status": "degraded", "reason": "high latency"})
        result = checker.run()
        assert result.overall == HealthStatus.DEGRADED

    def test_one_unhealthy(self):
        checker = DeepHealthChecker(clock=FIXED_CLOCK)
        checker.register("db", lambda: {"status": "healthy"})
        checker.register("llm", lambda: {"status": "unhealthy", "error": "timeout"})
        result = checker.run()
        assert result.overall == HealthStatus.UNHEALTHY

    def test_exception_marks_unhealthy(self):
        checker = DeepHealthChecker(clock=FIXED_CLOCK)
        checker.register("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = checker.run()
        assert result.overall == HealthStatus.UNHEALTHY
        assert result.components[0].detail["error"] == "health check error (RuntimeError)"
        assert "boom" not in result.components[0].detail["error"]

    def test_latency_tracked(self):
        checker = DeepHealthChecker(clock=FIXED_CLOCK)
        checker.register("fast", lambda: {"status": "healthy"})
        result = checker.run()
        assert result.components[0].latency_ms >= 0.0
        assert result.total_latency_ms >= 0.0

    def test_components_sorted(self):
        checker = DeepHealthChecker(clock=FIXED_CLOCK)
        checker.register("zebra", lambda: {"status": "healthy"})
        checker.register("alpha", lambda: {"status": "healthy"})
        result = checker.run()
        assert result.components[0].name == "alpha"
        assert result.components[1].name == "zebra"

    def test_checked_at(self):
        checker = DeepHealthChecker(clock=FIXED_CLOCK)
        result = checker.run()
        assert result.checked_at == "2026-03-26T12:00:00Z"

    def test_check_count(self):
        checker = DeepHealthChecker(clock=FIXED_CLOCK)
        checker.register("a", lambda: {"status": "healthy"})
        checker.register("b", lambda: {"status": "healthy"})
        assert checker.check_count == 2
