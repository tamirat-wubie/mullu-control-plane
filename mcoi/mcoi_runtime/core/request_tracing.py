"""Phase 222B — Distributed Request Tracing Middleware.

Purpose: Propagate trace IDs across all governed operations for end-to-end
    observability. Every request gets a unique trace_id + span_id. Child
    spans link back to parent for causal ordering.
Dependencies: None (stdlib only).
Invariants:
  - Every trace has a globally unique trace_id (UUID4).
  - Spans form a DAG rooted at the request entry span.
  - Completed spans are immutable.
  - Trace context propagates via X-Trace-Id / X-Span-Id headers.
"""
from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class SpanStatus(Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class Span:
    """Single unit of work within a trace."""
    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation: str
    start_time: float
    end_time: float | None = None
    status: SpanStatus = SpanStatus.OK
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    @property
    def is_root(self) -> bool:
        return self.parent_span_id is None

    def finish(self, status: SpanStatus = SpanStatus.OK) -> None:
        self.end_time = time.monotonic()
        self.status = status

    def add_event(self, name: str, **attrs: Any) -> None:
        self.events.append({"name": name, "time": time.monotonic(), **attrs})

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": self.events,
            "is_root": self.is_root,
        }


@dataclass
class TraceContext:
    """Propagation context for distributed tracing."""
    trace_id: str
    span_id: str
    parent_span_id: str | None = None

    @classmethod
    def new(cls) -> TraceContext:
        return cls(trace_id=uuid.uuid4().hex, span_id=uuid.uuid4().hex[:16])

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> TraceContext:
        trace_id = headers.get("x-trace-id") or headers.get("X-Trace-Id") or uuid.uuid4().hex
        span_id = headers.get("x-span-id") or headers.get("X-Span-Id") or uuid.uuid4().hex[:16]
        return cls(trace_id=trace_id, span_id=span_id)

    def child(self) -> TraceContext:
        return TraceContext(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=self.span_id,
        )

    def to_headers(self) -> dict[str, str]:
        return {"X-Trace-Id": self.trace_id, "X-Span-Id": self.span_id}


class RequestTracer:
    """Collects and manages spans for distributed request tracing."""

    def __init__(self, max_traces: int = 10_000, on_span_finish: Callable[[Span], None] | None = None):
        self._traces: dict[str, list[Span]] = {}
        self._max_traces = max_traces
        self._on_span_finish = on_span_finish
        self._total_spans = 0

    def start_span(self, ctx: TraceContext, operation: str, **attrs: Any) -> Span:
        span = Span(
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
            parent_span_id=ctx.parent_span_id,
            operation=operation,
            start_time=time.monotonic(),
            attributes=attrs,
        )
        if ctx.trace_id not in self._traces:
            if len(self._traces) >= self._max_traces:
                oldest = next(iter(self._traces))
                del self._traces[oldest]
            self._traces[ctx.trace_id] = []
        self._traces[ctx.trace_id].append(span)
        self._total_spans += 1
        return span

    def finish_span(self, span: Span, status: SpanStatus = SpanStatus.OK) -> None:
        span.finish(status)
        if self._on_span_finish:
            self._on_span_finish(span)

    def get_trace(self, trace_id: str) -> list[Span]:
        return list(self._traces.get(trace_id, []))

    @property
    def trace_count(self) -> int:
        return len(self._traces)

    @property
    def total_spans(self) -> int:
        return self._total_spans

    def summary(self) -> dict[str, Any]:
        return {
            "active_traces": self.trace_count,
            "total_spans": self.total_spans,
            "max_traces": self._max_traces,
        }

    def slow_traces(self, threshold_ms: float = 1000.0) -> list[dict[str, Any]]:
        """Return traces with root span duration exceeding threshold."""
        result = []
        for trace_id, spans in self._traces.items():
            roots = [s for s in spans if s.is_root and s.duration_ms is not None]
            for root in roots:
                if root.duration_ms and root.duration_ms > threshold_ms:
                    result.append({
                        "trace_id": trace_id,
                        "operation": root.operation,
                        "duration_ms": root.duration_ms,
                        "span_count": len(spans),
                    })
        return result
