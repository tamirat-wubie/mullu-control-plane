"""Tests for Phase 226B — Prometheus Metrics Exporter."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.prometheus_exporter import (
    MetricSample, MetricType, PrometheusExporter,
)


class TestMetricSample:
    def test_simple_sample(self):
        s = MetricSample("test_total", 42.0)
        assert s.to_prometheus() == "test_total 42.0"

    def test_sample_with_labels(self):
        s = MetricSample("test_total", 5.0, labels={"method": "GET", "status": "200"})
        out = s.to_prometheus()
        assert 'method="GET"' in out
        assert 'status="200"' in out
        assert "5.0" in out

    def test_sample_with_timestamp(self):
        s = MetricSample("test_total", 1.0, timestamp=1700000000.0)
        assert "1700000000000" in s.to_prometheus()


class TestPrometheusExporter:
    def test_register_and_increment_counter(self):
        exp = PrometheusExporter()
        exp.register_counter("requests_total", "Total requests")
        exp.inc_counter("requests_total", 5.0)
        output = exp.export()
        assert "# HELP mullu_requests_total Total requests" in output
        assert "# TYPE mullu_requests_total counter" in output
        assert "mullu_requests_total 5.0" in output

    def test_register_and_set_gauge(self):
        exp = PrometheusExporter()
        exp.register_gauge("active_connections", "Active connections")
        exp.set_gauge("active_connections", 42.0)
        output = exp.export()
        assert "# TYPE mullu_active_connections gauge" in output
        assert "mullu_active_connections 42.0" in output

    def test_counter_with_labels(self):
        exp = PrometheusExporter()
        exp.register_counter("http_requests_total", "HTTP requests")
        exp.inc_counter("http_requests_total", 10.0, method="GET")
        exp.inc_counter("http_requests_total", 5.0, method="POST")
        output = exp.export()
        assert 'method="GET"' in output
        assert 'method="POST"' in output

    def test_gauge_with_labels(self):
        exp = PrometheusExporter()
        exp.register_gauge("cpu_usage", "CPU usage")
        exp.set_gauge("cpu_usage", 0.75, core="0")
        exp.set_gauge("cpu_usage", 0.60, core="1")
        output = exp.export()
        assert 'core="0"' in output

    def test_multiple_increments(self):
        exp = PrometheusExporter()
        exp.register_counter("total", "Total")
        exp.inc_counter("total")
        exp.inc_counter("total")
        exp.inc_counter("total")
        output = exp.export()
        assert "mullu_total 3.0" in output

    def test_custom_prefix(self):
        exp = PrometheusExporter(prefix="myapp")
        exp.register_counter("requests", "Requests")
        exp.inc_counter("requests")
        output = exp.export()
        assert "myapp_requests" in output

    def test_metric_count(self):
        exp = PrometheusExporter()
        exp.register_counter("a", "A")
        exp.register_gauge("b", "B")
        assert exp.metric_count == 2

    def test_summary(self):
        exp = PrometheusExporter()
        exp.register_counter("a", "A")
        exp.inc_counter("a")
        s = exp.summary()
        assert s["prefix"] == "mullu"
        assert s["counters"] == 1

    def test_empty_export(self):
        exp = PrometheusExporter()
        output = exp.export()
        assert output.strip() == ""
