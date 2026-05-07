"""Tests for Phase 225A — SLA Monitoring Engine."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.sla_monitor import SLAMonitor, SLATarget, SLAMetricType


@pytest.fixture
def monitor():
    m = SLAMonitor()
    m.add_target(SLATarget("uptime", "Platform Uptime", SLAMetricType.UPTIME, 99.9, "gte"))
    m.add_target(SLATarget("latency", "API Latency P99", SLAMetricType.LATENCY_P99, 200.0, "lte"))
    return m


class TestSLATarget:
    def test_frozen(self):
        t = SLATarget("id", "name", SLAMetricType.UPTIME, 99.9, "gte")
        with pytest.raises(AttributeError):
            t.threshold = 50.0  # type: ignore[misc]

    def test_gte_comparison(self):
        t = SLATarget("id", "name", SLAMetricType.UPTIME, 99.9, "gte")
        assert t.is_met(99.95)
        assert t.is_met(99.9)
        assert not t.is_met(99.8)

    def test_lte_comparison(self):
        t = SLATarget("id", "name", SLAMetricType.LATENCY_P99, 200.0, "lte")
        assert t.is_met(150.0)
        assert t.is_met(200.0)
        assert not t.is_met(250.0)


class TestSLAMonitor:
    def test_check_pass(self, monitor):
        assert monitor.check("uptime", 99.95)
        assert monitor.violation_count == 0

    def test_check_fail(self, monitor):
        assert not monitor.check("uptime", 99.0)
        assert monitor.violation_count == 1

    def test_compliance_100(self, monitor):
        monitor.check("uptime", 99.95)
        monitor.check("uptime", 99.99)
        assert monitor.compliance("uptime") == 100.0

    def test_compliance_partial(self, monitor):
        monitor.check("uptime", 99.95)
        monitor.check("uptime", 99.0)
        assert monitor.compliance("uptime") == 50.0

    def test_compliance_no_checks(self, monitor):
        assert monitor.compliance("uptime") == 100.0

    def test_violations_filtered(self, monitor):
        monitor.check("uptime", 99.0)
        monitor.check("latency", 250.0)
        assert len(monitor.violations("uptime")) == 1
        assert len(monitor.violations("latency")) == 1
        assert len(monitor.violations()) == 2

    def test_unknown_sla(self, monitor):
        with pytest.raises(ValueError, match="^unknown SLA$") as exc_info:
            monitor.check("nonexistent", 1.0)
        assert "nonexistent" not in str(exc_info.value)

    def test_summary(self, monitor):
        monitor.check("uptime", 99.95)
        monitor.check("latency", 250.0)
        s = monitor.summary()
        assert s["targets"] == 2
        assert s["total_violations"] == 1
        assert s["compliance"]["uptime"] == 100.0
        assert s["compliance"]["latency"] == 0.0
