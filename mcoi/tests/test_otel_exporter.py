"""Tests for Phase 229A — OpenTelemetry Trace Exporter."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.otel_exporter import OtelExporter, SpanStatus


class TestOtelExporter:
    def test_start_and_end_span(self):
        exporter = OtelExporter()
        span = exporter.start_span("test-op", service="api")
        assert span.trace_id
        assert span.span_id
        assert span.duration_ms == 0.0
        exporter.end_span(span)
        assert span.duration_ms > 0
        assert span.status == SpanStatus.OK

    def test_span_with_error(self):
        exporter = OtelExporter()
        span = exporter.start_span("fail-op")
        exporter.end_span(span, status=SpanStatus.ERROR)
        assert span.status == SpanStatus.ERROR

    def test_span_events(self):
        exporter = OtelExporter()
        span = exporter.start_span("event-op")
        span.add_event("checkpoint", step=1)
        assert len(span.events) == 1
        assert span.events[0]["name"] == "checkpoint"

    def test_to_otlp_format(self):
        exporter = OtelExporter()
        span = exporter.start_span("otlp-op", key="val")
        exporter.end_span(span)
        otlp = span.to_otlp()
        assert otlp["name"] == "otlp-op"
        assert otlp["traceId"] == span.trace_id
        assert otlp["status"]["code"] == "ok"

    def test_flush_exports(self):
        exported = []
        exporter = OtelExporter(export_fn=lambda batch: (exported.append(batch) or True))
        span = exporter.start_span("flush-op")
        exporter.end_span(span)
        assert exporter.flush()
        assert len(exported) == 1

    def test_auto_flush_at_batch_size(self):
        exporter = OtelExporter(batch_size=2)
        for i in range(2):
            span = exporter.start_span(f"op-{i}")
            exporter.end_span(span)
        assert exporter.buffered_count == 0  # auto-flushed

    def test_failed_export(self):
        exporter = OtelExporter(export_fn=lambda _: False)
        span = exporter.start_span("fail")
        exporter.end_span(span)
        assert not exporter.flush()
        assert exporter.summary()["failed_exports"] == 1

    def test_parent_span(self):
        exporter = OtelExporter()
        parent = exporter.start_span("parent")
        child = exporter.start_span("child", trace_id=parent.trace_id, parent_span_id=parent.span_id)
        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id

    def test_summary(self):
        exporter = OtelExporter(service_name="test-svc")
        span = exporter.start_span("op")
        exporter.end_span(span)
        s = exporter.summary()
        assert s["service_name"] == "test-svc"
        assert s["total_spans"] == 1

    def test_empty_flush(self):
        exporter = OtelExporter()
        assert exporter.flush()  # no-op
