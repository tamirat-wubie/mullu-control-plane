"""Phase 204C — Observability aggregator tests."""

import pytest
from mcoi_runtime.core.observability import ObservabilityAggregator, DashboardSnapshot

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestObservabilityAggregator:
    def test_register_source(self):
        agg = ObservabilityAggregator(clock=FIXED_CLOCK)
        agg.register_source("health", lambda: {"status": "healthy"})
        assert agg.source_count == 1

    def test_collect_single(self):
        agg = ObservabilityAggregator(clock=FIXED_CLOCK)
        agg.register_source("health", lambda: {"status": "healthy", "uptime": 3600})
        data = agg.collect("health")
        assert data["status"] == "healthy"
        assert data["uptime"] == 3600

    def test_collect_unknown(self):
        agg = ObservabilityAggregator(clock=FIXED_CLOCK)
        data = agg.collect("nonexistent")
        assert "error" in data

    def test_collect_error(self):
        agg = ObservabilityAggregator(clock=FIXED_CLOCK)
        agg.register_source("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        data = agg.collect("broken")
        assert "error" in data
        assert data["error"] == "observability source error (RuntimeError)"
        assert "boom" not in data["error"]

    def test_collect_all(self):
        agg = ObservabilityAggregator(clock=FIXED_CLOCK)
        agg.register_source("health", lambda: {"status": "healthy"})
        agg.register_source("llm", lambda: {"calls": 42})
        data = agg.collect_all()
        assert data["health"]["status"] == "healthy"
        assert data["llm"]["calls"] == 42
        assert data["source_count"] == 2

    def test_snapshot(self):
        agg = ObservabilityAggregator(clock=FIXED_CLOCK)
        agg.register_source("health", lambda: {"status": "healthy"})
        snap = agg.snapshot()
        assert isinstance(snap, DashboardSnapshot)
        assert snap.captured_at == "2026-03-26T12:00:00Z"

    def test_source_names(self):
        agg = ObservabilityAggregator(clock=FIXED_CLOCK)
        agg.register_source("b", lambda: {})
        agg.register_source("a", lambda: {})
        assert agg.source_names() == ["a", "b"]

    def test_empty_collect_all(self):
        agg = ObservabilityAggregator(clock=FIXED_CLOCK)
        data = agg.collect_all()
        assert data["source_count"] == 0
