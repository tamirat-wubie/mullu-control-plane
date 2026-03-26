"""Tests for Phase 222B — Distributed Request Tracing.

Governance scope: validate trace context propagation, span lifecycle,
    parent-child relationships, and trace eviction.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.core.request_tracing import (
    RequestTracer,
    SpanStatus,
    TraceContext,
    Span,
)


class TestTraceContext:
    def test_new_creates_unique(self):
        c1 = TraceContext.new()
        c2 = TraceContext.new()
        assert c1.trace_id != c2.trace_id
        assert c1.span_id != c2.span_id

    def test_child_preserves_trace_id(self):
        parent = TraceContext.new()
        child = parent.child()
        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id
        assert child.span_id != parent.span_id

    def test_from_headers(self):
        ctx = TraceContext.from_headers({"X-Trace-Id": "abc123", "X-Span-Id": "span456"})
        assert ctx.trace_id == "abc123"
        assert ctx.span_id == "span456"

    def test_from_headers_generates_missing(self):
        ctx = TraceContext.from_headers({})
        assert len(ctx.trace_id) == 32  # uuid4 hex
        assert len(ctx.span_id) > 0

    def test_to_headers(self):
        ctx = TraceContext(trace_id="t1", span_id="s1")
        h = ctx.to_headers()
        assert h["X-Trace-Id"] == "t1"
        assert h["X-Span-Id"] == "s1"

    def test_roundtrip_headers(self):
        ctx = TraceContext.new()
        h = ctx.to_headers()
        restored = TraceContext.from_headers(h)
        assert restored.trace_id == ctx.trace_id
        assert restored.span_id == ctx.span_id


class TestSpan:
    def test_root_span(self):
        s = Span(trace_id="t", span_id="s", parent_span_id=None,
                 operation="test", start_time=1.0)
        assert s.is_root
        assert s.duration_ms is None

    def test_finish_sets_duration(self):
        s = Span(trace_id="t", span_id="s", parent_span_id=None,
                 operation="test", start_time=1.0)
        s.finish(SpanStatus.OK)
        assert s.end_time is not None
        assert s.duration_ms is not None
        assert s.status == SpanStatus.OK

    def test_child_span_not_root(self):
        s = Span(trace_id="t", span_id="s", parent_span_id="p",
                 operation="child", start_time=1.0)
        assert not s.is_root

    def test_add_event(self):
        s = Span(trace_id="t", span_id="s", parent_span_id=None,
                 operation="test", start_time=1.0)
        s.add_event("checkpoint", data="hello")
        assert len(s.events) == 1
        assert s.events[0]["name"] == "checkpoint"
        assert s.events[0]["data"] == "hello"

    def test_to_dict(self):
        s = Span(trace_id="t", span_id="s", parent_span_id=None,
                 operation="op", start_time=1.0, attributes={"key": "val"})
        d = s.to_dict()
        assert d["trace_id"] == "t"
        assert d["operation"] == "op"
        assert d["is_root"] is True
        assert d["attributes"]["key"] == "val"


class TestRequestTracer:
    def test_start_and_finish_span(self):
        tracer = RequestTracer()
        ctx = TraceContext.new()
        span = tracer.start_span(ctx, "request")
        assert tracer.trace_count == 1
        assert tracer.total_spans == 1
        tracer.finish_span(span)
        assert span.status == SpanStatus.OK

    def test_multiple_spans_same_trace(self):
        tracer = RequestTracer()
        ctx = TraceContext.new()
        s1 = tracer.start_span(ctx, "root")
        child_ctx = ctx.child()
        s2 = tracer.start_span(child_ctx, "child")
        assert tracer.trace_count == 1
        assert tracer.total_spans == 2
        spans = tracer.get_trace(ctx.trace_id)
        assert len(spans) == 2

    def test_eviction_when_max_traces(self):
        tracer = RequestTracer(max_traces=2)
        for _ in range(3):
            ctx = TraceContext.new()
            tracer.start_span(ctx, "op")
        assert tracer.trace_count == 2

    def test_on_span_finish_callback(self):
        finished = []
        tracer = RequestTracer(on_span_finish=lambda s: finished.append(s))
        ctx = TraceContext.new()
        span = tracer.start_span(ctx, "op")
        tracer.finish_span(span)
        assert len(finished) == 1
        assert finished[0] is span

    def test_error_status(self):
        tracer = RequestTracer()
        ctx = TraceContext.new()
        span = tracer.start_span(ctx, "fail")
        tracer.finish_span(span, SpanStatus.ERROR)
        assert span.status == SpanStatus.ERROR

    def test_summary(self):
        tracer = RequestTracer(max_traces=100)
        ctx = TraceContext.new()
        tracer.start_span(ctx, "op")
        s = tracer.summary()
        assert s["active_traces"] == 1
        assert s["total_spans"] == 1
        assert s["max_traces"] == 100

    def test_slow_traces_empty(self):
        tracer = RequestTracer()
        assert tracer.slow_traces() == []

    def test_get_nonexistent_trace(self):
        tracer = RequestTracer()
        assert tracer.get_trace("nonexistent") == []
