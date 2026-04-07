"""Request Tracing Tests — Decision chain reconstruction."""

import time
import pytest
from mcoi_runtime.core.request_trace import (
    TraceBuilder, TraceStore, RequestTrace, TraceSpan,
)


class TestTraceBuilder:
    def test_build_simple_trace(self):
        builder = TraceBuilder(tenant_id="t1", endpoint="/api/v1/llm")
        trace = builder.finish(outcome="allowed")
        assert trace.trace_id.startswith("trace-")
        assert trace.tenant_id == "t1"
        assert trace.outcome == "allowed"
        assert trace.total_duration_ms >= 0

    def test_span_context_manager(self):
        builder = TraceBuilder(tenant_id="t1", endpoint="/test")
        with builder.span("guard:rate_limit") as s:
            s.set_detail({"allowed": True})
        trace = builder.finish()
        assert len(trace.spans) == 1
        assert trace.spans[0].name == "guard:rate_limit"
        assert trace.spans[0].status == "ok"
        assert trace.spans[0].detail["allowed"] is True

    def test_multiple_spans(self):
        builder = TraceBuilder(tenant_id="t1", endpoint="/test")
        with builder.span("guard:auth"):
            pass
        with builder.span("guard:rbac"):
            pass
        with builder.span("llm:anthropic"):
            pass
        trace = builder.finish()
        assert len(trace.spans) == 3
        names = [s.name for s in trace.spans]
        assert names == ["guard:auth", "guard:rbac", "llm:anthropic"]

    def test_span_error_captured(self):
        builder = TraceBuilder(tenant_id="t1", endpoint="/test")
        with pytest.raises(RuntimeError, match="budget exhausted"):
            with builder.span("guard:budget") as s:
                raise RuntimeError("budget exhausted")
        trace = builder.finish(outcome="denied")
        assert trace.spans[0].status == "error"
        assert trace.spans[0].detail["error_type"] == "RuntimeError"

    def test_set_provider_and_cost(self):
        builder = TraceBuilder(tenant_id="t1", endpoint="/test")
        builder.set_provider("anthropic")
        builder.set_cost(0.003)
        trace = builder.finish()
        assert trace.provider_used == "anthropic"
        assert trace.cost == 0.003

    def test_trace_to_dict(self):
        builder = TraceBuilder(tenant_id="t1", identity_id="u1", endpoint="/api/v1/llm")
        with builder.span("guard:auth") as s:
            s.set_detail({"method": "jwt"})
        builder.set_provider("groq")
        trace = builder.finish(outcome="allowed")
        data = trace.to_dict()
        assert data["trace_id"].startswith("trace-")
        assert data["tenant_id"] == "t1"
        assert data["outcome"] == "allowed"
        assert data["provider_used"] == "groq"
        assert len(data["spans"]) == 1
        assert data["spans"][0]["name"] == "guard:auth"

    def test_max_spans_bounded(self):
        builder = TraceBuilder(tenant_id="t1", endpoint="/test")
        for i in range(builder.MAX_SPANS + 10):
            with builder.span(f"span-{i}"):
                pass
        trace = builder.finish()
        assert len(trace.spans) <= builder.MAX_SPANS

    def test_span_duration_measured(self):
        builder = TraceBuilder(tenant_id="t1", endpoint="/test")
        with builder.span("slow_op"):
            time.sleep(0.01)
        trace = builder.finish()
        assert trace.spans[0].duration_ms >= 5  # At least 5ms

    def test_trace_id_unique(self):
        b1 = TraceBuilder(tenant_id="t1", endpoint="/a")
        b2 = TraceBuilder(tenant_id="t1", endpoint="/a")
        assert b1._trace_id != b2._trace_id  # Different start times


class TestTraceStore:
    def test_store_and_get(self):
        store = TraceStore()
        builder = TraceBuilder(tenant_id="t1", endpoint="/test")
        trace = builder.finish()
        store.store(trace)
        found = store.get(trace.trace_id)
        assert found is not None
        assert found.trace_id == trace.trace_id

    def test_get_not_found(self):
        store = TraceStore()
        assert store.get("nonexistent") is None

    def test_query_by_tenant(self):
        store = TraceStore()
        for tid in ("t1", "t1", "t2"):
            store.store(TraceBuilder(tenant_id=tid, endpoint="/test").finish())
        assert len(store.query(tenant_id="t1")) == 2
        assert len(store.query(tenant_id="t2")) == 1

    def test_query_by_outcome(self):
        store = TraceStore()
        store.store(TraceBuilder(tenant_id="t1", endpoint="/a").finish(outcome="allowed"))
        store.store(TraceBuilder(tenant_id="t1", endpoint="/b").finish(outcome="denied"))
        assert len(store.query(outcome="denied")) == 1

    def test_bounded(self):
        store = TraceStore()
        for i in range(store.MAX_TRACES + 100):
            store.store(TraceBuilder(tenant_id="t1", endpoint=f"/{i}").finish())
        assert store.trace_count <= store.MAX_TRACES

    def test_summary(self):
        store = TraceStore()
        store.store(TraceBuilder(tenant_id="t1", endpoint="/test").finish(outcome="allowed"))
        summary = store.summary()
        assert summary["count"] == 1
        assert "avg_duration_ms" in summary
        assert summary["recent_outcomes"]["allowed"] == 1

    def test_empty_summary(self):
        store = TraceStore()
        summary = store.summary()
        assert summary["count"] == 0
