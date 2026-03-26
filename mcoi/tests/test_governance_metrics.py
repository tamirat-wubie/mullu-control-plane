"""Phase 202B — Governance metrics engine tests."""

import pytest
from mcoi_runtime.core.governance_metrics import GovernanceMetricsEngine, MetricSnapshot

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestCounters:
    def test_inc_default(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        assert m.inc("requests_total") == 1
        assert m.inc("requests_total") == 2

    def test_inc_by_amount(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        assert m.inc("requests_total", 5) == 5

    def test_counter_read(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        assert m.counter("requests_total") == 0
        m.inc("requests_total", 3)
        assert m.counter("requests_total") == 3

    def test_unknown_counter_strict(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK, strict=True)
        with pytest.raises(ValueError, match="unknown counter"):
            m.inc("totally_fake_counter")

    def test_unknown_counter_non_strict(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK, strict=False)
        m.inc("custom_counter")
        assert m.counter("custom_counter") == 1


class TestGauges:
    def test_set_gauge(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        m.set_gauge("active_sessions", 42.0)
        assert m.gauge("active_sessions") == 42.0

    def test_inc_gauge(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        m.inc_gauge("active_sessions", 5.0)
        assert m.gauge("active_sessions") == 5.0

    def test_dec_gauge(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        m.set_gauge("active_sessions", 10.0)
        m.dec_gauge("active_sessions", 3.0)
        assert m.gauge("active_sessions") == 7.0

    def test_unknown_gauge_strict(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK, strict=True)
        with pytest.raises(ValueError, match="unknown gauge"):
            m.set_gauge("fake_gauge", 1.0)


class TestHistograms:
    def test_observe(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        m.observe("request_latency_ms", 150.0)
        m.observe("request_latency_ms", 200.0)
        stats = m.histogram_stats("request_latency_ms")
        assert stats["count"] == 2
        assert stats["avg"] == 175.0

    def test_empty_histogram(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        stats = m.histogram_stats("request_latency_ms")
        assert stats["count"] == 0

    def test_percentiles(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        for i in range(1, 101):
            m.observe("request_latency_ms", float(i))
        stats = m.histogram_stats("request_latency_ms")
        assert stats["count"] == 100
        assert stats["min"] == 1.0
        assert stats["max"] == 100.0
        assert stats["p50"] >= 49.0
        assert stats["p95"] >= 94.0


class TestSnapshot:
    def test_snapshot(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        m.inc("requests_total", 5)
        m.set_gauge("health_score", 0.99)
        snap = m.snapshot()
        assert isinstance(snap, MetricSnapshot)
        assert snap.counters["requests_total"] == 5
        assert snap.gauges["health_score"] == 0.99

    def test_to_dict(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        m.inc("requests_total")
        d = m.to_dict()
        assert "counters" in d
        assert "gauges" in d
        assert d["counters"]["requests_total"] == 1

    def test_reset(self):
        m = GovernanceMetricsEngine(clock=FIXED_CLOCK)
        m.inc("requests_total", 100)
        m.set_gauge("health_score", 0.5)
        m.observe("request_latency_ms", 50.0)
        m.reset()
        assert m.counter("requests_total") == 0
        assert m.gauge("health_score") == 0.0
        assert m.histogram_stats("request_latency_ms")["count"] == 0
