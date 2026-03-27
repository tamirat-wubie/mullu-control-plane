"""Tests for Phase 229B — Circuit Breaker Dashboard Aggregator."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.circuit_dashboard import (
    CircuitDashboard, BreakerState, AlertThresholds,
)


class TestCircuitDashboard:
    def test_register_breaker(self):
        dash = CircuitDashboard()
        b = dash.register_breaker("llm-client")
        assert b.name == "llm-client"
        assert b.state == BreakerState.CLOSED

    def test_health_score_all_closed(self):
        dash = CircuitDashboard()
        dash.register_breaker("a")
        dash.register_breaker("b")
        assert dash.health_score == 100.0

    def test_health_score_mixed(self):
        dash = CircuitDashboard()
        dash.register_breaker("a")
        dash.register_breaker("b")
        dash.update_state("b", BreakerState.OPEN)
        # a=100, b=0 => avg=50
        assert dash.health_score == 50.0

    def test_health_score_empty(self):
        dash = CircuitDashboard()
        assert dash.health_score == 100.0

    def test_update_state(self):
        dash = CircuitDashboard()
        dash.register_breaker("svc")
        result = dash.update_state("svc", BreakerState.HALF_OPEN)
        assert result is not None
        assert result.state == BreakerState.HALF_OPEN

    def test_update_nonexistent(self):
        dash = CircuitDashboard()
        assert dash.update_state("missing", BreakerState.OPEN) is None

    def test_record_outcome(self):
        dash = CircuitDashboard()
        dash.register_breaker("svc")
        dash.record_outcome("svc", success=True)
        dash.record_outcome("svc", success=False)
        s = dash.summary()
        assert s["breakers"][0]["failure_rate"] == 0.5

    def test_alerts_too_many_open(self):
        dash = CircuitDashboard(AlertThresholds(max_open_breakers=1))
        dash.register_breaker("a")
        dash.register_breaker("b")
        dash.update_state("a", BreakerState.OPEN)
        dash.update_state("b", BreakerState.OPEN)
        alerts = dash.get_alerts()
        assert any("Too many open" in a for a in alerts)

    def test_alerts_low_health(self):
        dash = CircuitDashboard(AlertThresholds(min_health_score=80.0))
        dash.register_breaker("a")
        dash.update_state("a", BreakerState.OPEN)
        alerts = dash.get_alerts()
        assert any("Health score below" in a for a in alerts)

    def test_alerts_high_failure_rate(self):
        dash = CircuitDashboard(AlertThresholds(max_failure_rate=0.3))
        dash.register_breaker("svc")
        for _ in range(8):
            dash.record_outcome("svc", success=False)
        for _ in range(2):
            dash.record_outcome("svc", success=True)
        alerts = dash.get_alerts()
        assert any("High failure rate" in a for a in alerts)

    def test_summary(self):
        dash = CircuitDashboard()
        dash.register_breaker("a")
        dash.register_breaker("b")
        dash.update_state("b", BreakerState.HALF_OPEN)
        s = dash.summary()
        assert s["total_breakers"] == 2
        assert s["closed"] == 1
        assert s["half_open"] == 1
