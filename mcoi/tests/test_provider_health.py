"""Provider Health Monitor Tests — Latency tracking, error rate, fleet health."""

import pytest
from mcoi_runtime.core.provider_health import (
    HealthSample,
    ProviderHealthMonitor,
    ProviderHealthReport,
    ProviderHealthStatus,
    ProviderHealthTracker,
)


# ── ProviderHealthTracker ──────────────────────────────────────

class TestProviderHealthTracker:
    def test_empty_report_is_unknown(self):
        tracker = ProviderHealthTracker("anthropic")
        report = tracker.report()
        assert report.status == ProviderHealthStatus.UNKNOWN
        assert report.sample_count == 0
        assert report.health_score == 0.5

    def test_healthy_after_good_samples(self):
        tracker = ProviderHealthTracker("anthropic")
        for i in range(10):
            tracker.record_success(200.0, clock=lambda: float(i))
        report = tracker.report()
        assert report.status == ProviderHealthStatus.HEALTHY
        assert report.health_score > 0.8
        assert report.error_rate == 0.0
        assert report.avg_latency_ms == 200.0

    def test_degraded_on_elevated_error_rate(self):
        tracker = ProviderHealthTracker("openai")
        for i in range(8):
            tracker.record_success(300.0, clock=lambda: float(i))
        for i in range(2):
            tracker.record_failure(0.0, "timeout", clock=lambda: float(10 + i))
        report = tracker.report()
        assert report.error_rate == 0.2  # 2/10
        assert report.status == ProviderHealthStatus.DEGRADED

    def test_unhealthy_on_high_error_rate(self):
        tracker = ProviderHealthTracker("groq")
        for i in range(5):
            tracker.record_success(100.0, clock=lambda: float(i))
        for i in range(6):
            tracker.record_failure(0.0, "error", clock=lambda: float(10 + i))
        report = tracker.report()
        # 6/11 ≈ 0.545 > 0.5 threshold
        assert report.status == ProviderHealthStatus.UNHEALTHY

    def test_degraded_on_high_latency(self):
        tracker = ProviderHealthTracker("gemini")
        for i in range(10):
            tracker.record_success(6000.0, clock=lambda: float(i))
        report = tracker.report()
        assert report.p95_latency_ms >= 5000.0
        assert report.status == ProviderHealthStatus.DEGRADED

    def test_unhealthy_on_extreme_latency(self):
        tracker = ProviderHealthTracker("deepseek")
        for i in range(10):
            tracker.record_success(16000.0, clock=lambda: float(i))
        report = tracker.report()
        assert report.p95_latency_ms >= 15000.0
        assert report.status == ProviderHealthStatus.UNHEALTHY

    def test_consecutive_failures_tracked(self):
        tracker = ProviderHealthTracker("mistral")
        tracker.record_success(100.0)
        tracker.record_failure(0.0, "err")
        tracker.record_failure(0.0, "err")
        assert tracker.consecutive_failures == 2
        tracker.record_success(100.0)
        assert tracker.consecutive_failures == 0

    def test_5_consecutive_failures_is_unhealthy(self):
        tracker = ProviderHealthTracker("grok")
        for _ in range(5):
            tracker.record_failure(0.0, "down")
        report = tracker.report()
        assert report.consecutive_failures == 5
        assert report.status == ProviderHealthStatus.UNHEALTHY

    def test_window_bounded(self):
        tracker = ProviderHealthTracker("test")
        for i in range(200):
            tracker.record_success(100.0, clock=lambda: float(i))
        assert tracker.sample_count == tracker.WINDOW_SIZE  # 100

    def test_p95_computed(self):
        tracker = ProviderHealthTracker("test")
        for i in range(100):
            latency = 100.0 + i  # 100-199
            tracker.record_success(latency, clock=lambda: float(i))
        report = tracker.report()
        assert report.p95_latency_ms >= 190.0
        assert report.p95_latency_ms <= 200.0

    def test_health_score_bounds(self):
        tracker = ProviderHealthTracker("test")
        tracker.record_success(100.0)
        report = tracker.report()
        assert 0.0 <= report.health_score <= 1.0


# ── ProviderHealthMonitor ──────────────────────────────────────

class TestProviderHealthMonitor:
    def test_record_and_report(self):
        monitor = ProviderHealthMonitor()
        monitor.record_invocation("anthropic", latency_ms=200, success=True)
        report = monitor.provider_report("anthropic")
        assert report is not None
        assert report.sample_count == 1
        assert report.status == ProviderHealthStatus.HEALTHY

    def test_unknown_provider_returns_none(self):
        monitor = ProviderHealthMonitor()
        assert monitor.provider_report("nonexistent") is None

    def test_multiple_providers(self):
        monitor = ProviderHealthMonitor()
        monitor.record_invocation("anthropic", latency_ms=200, success=True)
        monitor.record_invocation("openai", latency_ms=300, success=True)
        monitor.record_invocation("groq", latency_ms=100, success=True)
        assert monitor.provider_count == 3

    def test_fleet_health_all_healthy(self):
        monitor = ProviderHealthMonitor()
        for p in ("anthropic", "openai", "groq"):
            for _ in range(10):
                monitor.record_invocation(p, latency_ms=200, success=True)
        fleet = monitor.fleet_health()
        assert fleet["overall_status"] == "healthy"
        assert fleet["healthy_count"] == 3
        assert fleet["overall_score"] > 0.8

    def test_fleet_health_partial_degradation(self):
        monitor = ProviderHealthMonitor()
        for _ in range(10):
            monitor.record_invocation("anthropic", latency_ms=200, success=True)
        # 50% error rate → UNHEALTHY for openai
        for _ in range(5):
            monitor.record_invocation("openai", latency_ms=200, success=True)
        for _ in range(5):
            monitor.record_invocation("openai", latency_ms=0, success=False, error="timeout")
        fleet = monitor.fleet_health()
        assert fleet["overall_status"] == "degraded"
        assert fleet["unhealthy_count"] >= 1

    def test_fleet_health_empty(self):
        monitor = ProviderHealthMonitor()
        fleet = monitor.fleet_health()
        assert fleet["overall_status"] == "unknown"
        assert fleet["providers"] == []

    def test_best_provider(self):
        monitor = ProviderHealthMonitor()
        for _ in range(10):
            monitor.record_invocation("fast", latency_ms=100, success=True)
            monitor.record_invocation("slow", latency_ms=5000, success=True)
        best = monitor.best_provider()
        assert best == "fast"

    def test_best_provider_empty(self):
        monitor = ProviderHealthMonitor()
        assert monitor.best_provider() is None

    def test_unhealthy_providers(self):
        monitor = ProviderHealthMonitor()
        for _ in range(10):
            monitor.record_invocation("good", latency_ms=200, success=True)
        for _ in range(10):
            monitor.record_invocation("bad", latency_ms=0, success=False, error="down")
        unhealthy = monitor.unhealthy_providers()
        assert "bad" in unhealthy
        assert "good" not in unhealthy

    def test_provider_eviction_at_capacity(self):
        monitor = ProviderHealthMonitor()
        # Override max for testing
        monitor.MAX_PROVIDERS = 5
        for i in range(10):
            monitor.record_invocation(f"provider-{i}", latency_ms=100, success=True)
        assert monitor.provider_count <= 5

    def test_fleet_health_providers_detail(self):
        monitor = ProviderHealthMonitor()
        monitor.record_invocation("anthropic", latency_ms=200, success=True)
        fleet = monitor.fleet_health()
        assert len(fleet["providers"]) == 1
        p = fleet["providers"][0]
        assert p["name"] == "anthropic"
        assert p["status"] == "healthy"
        assert "score" in p
        assert "avg_latency_ms" in p
        assert "error_rate" in p


# ── HealthSample ───────────────────────────────────────────────

class TestHealthSample:
    def test_sample_immutable(self):
        s = HealthSample(timestamp=1.0, latency_ms=200, success=True)
        with pytest.raises(AttributeError):
            s.latency_ms = 300

    def test_sample_with_error(self):
        s = HealthSample(timestamp=1.0, latency_ms=0, success=False, error="timeout")
        assert s.error == "timeout"
        assert s.success is False


# ── Edge cases ─────────────────────────────────────────────────

class TestEdgeCases:
    def test_all_failures_score(self):
        tracker = ProviderHealthTracker("dead")
        for i in range(10):
            tracker.record_failure(0.0, "down", clock=lambda: float(i))
        report = tracker.report()
        assert report.health_score == 0.0
        assert report.error_rate == 1.0

    def test_single_sample_healthy(self):
        tracker = ProviderHealthTracker("single")
        tracker.record_success(500.0)
        report = tracker.report()
        assert report.status == ProviderHealthStatus.HEALTHY
        assert report.sample_count == 1

    def test_single_failure_not_unhealthy(self):
        tracker = ProviderHealthTracker("flaky")
        tracker.record_failure(0.0, "blip")
        report = tracker.report()
        # Single failure → 100% error rate but only 1 consecutive
        assert report.error_rate == 1.0
        assert report.consecutive_failures == 1

    def test_recovery_after_failures(self):
        tracker = ProviderHealthTracker("recovering")
        for _ in range(5):
            tracker.record_failure(0.0, "down")
        for _ in range(20):
            tracker.record_success(200.0)
        report = tracker.report()
        assert report.consecutive_failures == 0
        assert report.status == ProviderHealthStatus.DEGRADED  # Error rate still > 10% in window
