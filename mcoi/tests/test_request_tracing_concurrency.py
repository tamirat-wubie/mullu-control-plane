"""Concurrency regression: RequestTracer under the threadpool.

start_span runs on every request -- it evicts + inserts trace keys and appends
spans. Concurrent start_spans raced the check-then-evict-then-append (a KeyError
when one thread evicts the key another just created), and slow_traces iterating
self._traces could hit "dictionary changed size during iteration". A lock now
guards the _traces mutations + reads. This test reproduces the crash (fails
pre-fix) and keeps a single-threaded sanity check.
"""

from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.request_tracing import RequestTracer, TraceContext


@pytest.fixture(autouse=True)
def _force_thread_switches():
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_concurrent_start_span_and_slow_traces_no_crash():
    tracer = RequestTracer(max_traces=50)  # low -> exercises the eviction del path
    errors: list[str] = []
    guard = threading.Lock()
    stop = threading.Event()

    def starter(w: int) -> None:
        try:
            for i in range(2000):
                ctx = TraceContext(trace_id=f"tr-{w}-{i}", span_id=f"sp-{i}")
                tracer.start_span(ctx, "op").finish()
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    def reader() -> None:
        try:
            while not stop.is_set():
                tracer.slow_traces(threshold_ms=0.0)
        except BaseException as exc:  # noqa: BLE001
            with guard:
                errors.append(repr(exc))

    readers = [threading.Thread(target=reader) for _ in range(2)]
    starters = [threading.Thread(target=starter, args=(w,)) for w in range(6)]
    for thread in readers:
        thread.start()
    for thread in starters:
        thread.start()
    for thread in starters:
        thread.join()
    stop.set()
    for thread in readers:
        thread.join()

    # Pre-fix: KeyError (evict-vs-append) or RuntimeError (dict changed size).
    assert errors == [], f"concurrent tracing raised: {errors[:1]}"


def test_start_and_get_trace_single_threaded():
    tracer = RequestTracer()
    ctx = TraceContext(trace_id="t1", span_id="s1")
    tracer.start_span(ctx, "op").finish()
    spans = tracer.get_trace("t1")
    assert len(spans) == 1 and spans[0].operation == "op"
