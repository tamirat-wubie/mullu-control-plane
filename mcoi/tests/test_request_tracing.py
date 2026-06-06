"""Tests for Phase 222B — Distributed Request Tracing.

Governance scope: validate trace context propagation, span lifecycle,
    parent-child relationships, and trace eviction.
"""
from __future__ import annotations

import math
import os
from collections.abc import Iterator

import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - optional runtime dependency guard
    TestClient = None  # type: ignore[assignment]

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
        assert s1.operation == "root"
        assert s2.operation == "child"
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

    @pytest.mark.parametrize("threshold_ms", [-1, math.inf, math.nan, "1000", True])
    def test_slow_traces_rejects_invalid_threshold(self, threshold_ms):
        tracer = RequestTracer()

        with pytest.raises(ValueError, match="threshold_ms"):
            tracer.slow_traces(threshold_ms=threshold_ms)

        assert tracer.trace_count == 0
        assert tracer.total_spans == 0

    @pytest.mark.parametrize("max_traces", [0, -1, math.inf, 1.5, "100", False])
    def test_constructor_rejects_invalid_max_traces(self, max_traces):
        with pytest.raises(ValueError, match="max_traces"):
            RequestTracer(max_traces=max_traces)

    def test_get_nonexistent_trace(self):
        tracer = RequestTracer()
        assert tracer.get_trace("nonexistent") == []


@pytest.fixture
def client() -> Iterator[TestClient]:
    if TestClient is None:
        pytest.skip("FastAPI test client is unavailable")

    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    os.environ["MULLU_CERT_INTERVAL"] = "0"

    from mcoi_runtime.app.server import app

    with TestClient(app) as test_client:
        yield test_client


class TestTraceObservabilityEndpoints:
    def test_trace_summary_route_bounded(self, client: TestClient):
        response = client.get("/api/v1/traces")

        assert response.status_code == 200
        body = response.json()
        assert body["governed"] is True
        assert "active_traces" in body["tracing"]
        assert "total_spans" in body["tracing"]

    def test_trace_lookup_route_bounded(self, client: TestClient):
        from mcoi_runtime.app.routers.deps import deps

        trace_context = TraceContext.new()
        span = deps.request_tracer.start_span(trace_context, "trace_lookup_route_bounded")
        deps.request_tracer.finish_span(span)

        response = client.get(f"/api/v1/traces/{trace_context.trace_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["governed"] is True
        assert body["trace_id"] == trace_context.trace_id
        assert body["spans"][0]["operation"] == "trace_lookup_route_bounded"

    def test_trace_lookup_missing_route_governed_404(self, client: TestClient):
        response = client.get("/api/v1/traces/missing-trace")

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["governed"] is True
        assert detail["error_code"] == "trace_not_found"
        assert detail["error"] == "trace not found"

    def test_slow_trace_route_bounded(self, client: TestClient):
        response = client.get("/api/v1/traces/slow")

        assert response.status_code == 200
        body = response.json()
        assert body["governed"] is True
        assert "slow_traces" in body
        assert isinstance(body["slow_traces"], list)

    @pytest.mark.parametrize("threshold_ms", ["-1", "nan", "inf"])
    def test_slow_trace_route_invalid_threshold_returns_bounded_422(
        self,
        client: TestClient,
        threshold_ms: str,
    ):
        response = client.get("/api/v1/traces/slow", params={"threshold_ms": threshold_ms})

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["governed"] is True
        assert detail["error"] == "invalid tracing request"
        assert detail["error_code"] == "tracing_invalid_request"
        assert threshold_ms not in str(response.json())
        assert "threshold_ms" not in str(response.json())

    def test_otel_trace_summary_route_bounded(self, client: TestClient):
        response = client.get("/api/v1/traces/summary")

        assert response.status_code == 200
        body = response.json()
        assert body["governed"] is True
        assert "traces" in body
        assert "service_name" in body["traces"]
        assert "failed_exports" in body["traces"]
