"""Purpose: comprehensive tests for the ObservabilityRuntimeEngine.
Governance scope: runtime-core observability / telemetry / debug engine.
Dependencies: observability_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Cross-tenant observability access is denied fail-closed.
  - Every mutation emits an event.
  - All returns are immutable.
  - Terminal-state transitions raise.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.observability_runtime import ObservabilityRuntimeEngine
from mcoi_runtime.contracts.observability_runtime import (
    AnomalySeverity,
    DebugDisposition,
    MetricRecord,
    LogRecord,
    TraceRecord,
    SpanRecord,
    AnomalyRecord,
    DebugSession,
    ObservabilityScope,
    ObservabilitySnapshot,
    ObservabilityAssessment,
    ObservabilityClosureReport,
    ObservabilityViolation,
    TraceStatus,
    TelemetryStatus,
    SignalKind,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# =====================================================================
# Fixture
# =====================================================================


@pytest.fixture
def env():
    es = EventSpineEngine()
    eng = ObservabilityRuntimeEngine(es)
    return es, eng


# =====================================================================
# Helpers
# =====================================================================

T = "tenant-1"
T2 = "tenant-2"
RT = "runtime-alpha"
RT2 = "runtime-beta"


def _metric(eng, mid="m-1", tid=T, name="cpu", value=42.0, runtime=RT,
            scope=ObservabilityScope.RUNTIME):
    return eng.record_metric(mid, tid, name, value, runtime, scope)


def _log(eng, lid="l-1", tid=T, level="INFO", msg="hello", runtime=RT,
         trace_id="none"):
    return eng.record_log(lid, tid, level, msg, runtime, trace_id)


def _trace(eng, trid="tr-1", tid=T, name="my-trace", runtime=RT):
    return eng.open_trace(trid, tid, name, runtime)


def _span(eng, sid="sp-1", trid="tr-1", tid=T, name="my-span", runtime=RT,
          parent="root", dur=0.0):
    return eng.add_span(sid, trid, tid, name, runtime, parent, dur)


def _anomaly(eng, aid="an-1", tid=T, runtime=RT, desc="something wrong",
             severity=AnomalySeverity.WARNING, trace_id="none"):
    return eng.register_anomaly(aid, tid, runtime, desc, severity, trace_id)


def _debug(eng, sid="ds-1", tid=T, op="operator-1", target=RT,
           trace_id="none"):
    return eng.open_debug_session(sid, tid, op, target, trace_id)


# =====================================================================
# 1. Constructor / Init
# =====================================================================


class TestConstructor:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ObservabilityRuntimeEngine("not-a-spine")

    def test_accepts_event_spine(self, env):
        _, eng = env
        assert eng.metric_count == 0
        assert eng.log_count == 0
        assert eng.trace_count == 0
        assert eng.span_count == 0
        assert eng.anomaly_count == 0
        assert eng.debug_session_count == 0
        assert eng.violation_count == 0
        assert eng.assessment_count == 0

    def test_none_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ObservabilityRuntimeEngine(None)

    def test_int_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ObservabilityRuntimeEngine(42)


# =====================================================================
# 2. Metrics
# =====================================================================


class TestRecordMetric:
    def test_basic_record(self, env):
        _, eng = env
        m = _metric(eng)
        assert isinstance(m, MetricRecord)
        assert m.metric_id == "m-1"
        assert m.tenant_id == T
        assert m.metric_name == "cpu"
        assert m.value == 42.0
        assert m.source_runtime == RT
        assert m.scope == ObservabilityScope.RUNTIME

    def test_duplicate_raises(self, env):
        _, eng = env
        _metric(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate metric_id"):
            _metric(eng)

    def test_different_ids_ok(self, env):
        _, eng = env
        _metric(eng, "m-1")
        _metric(eng, "m-2")
        assert eng.metric_count == 2

    def test_increments_count(self, env):
        _, eng = env
        for i in range(5):
            _metric(eng, f"m-{i}")
        assert eng.metric_count == 5

    def test_emits_event(self, env):
        es, eng = env
        before = es.event_count
        _metric(eng)
        assert es.event_count == before + 1

    def test_scope_tenant(self, env):
        _, eng = env
        m = _metric(eng, scope=ObservabilityScope.TENANT)
        assert m.scope == ObservabilityScope.TENANT

    def test_scope_global(self, env):
        _, eng = env
        m = _metric(eng, scope=ObservabilityScope.GLOBAL)
        assert m.scope == ObservabilityScope.GLOBAL

    def test_scope_service(self, env):
        _, eng = env
        m = _metric(eng, scope=ObservabilityScope.SERVICE)
        assert m.scope == ObservabilityScope.SERVICE

    def test_scope_workspace(self, env):
        _, eng = env
        m = _metric(eng, scope=ObservabilityScope.WORKSPACE)
        assert m.scope == ObservabilityScope.WORKSPACE

    def test_scope_endpoint(self, env):
        _, eng = env
        m = _metric(eng, scope=ObservabilityScope.ENDPOINT)
        assert m.scope == ObservabilityScope.ENDPOINT

    def test_zero_value(self, env):
        _, eng = env
        m = _metric(eng, value=0.0)
        assert m.value == 0.0

    def test_large_value(self, env):
        _, eng = env
        m = _metric(eng, value=999999.99)
        assert m.value == 999999.99

    def test_recorded_at_populated(self, env):
        _, eng = env
        m = _metric(eng)
        assert m.recorded_at  # non-empty ISO string


class TestGetMetric:
    def test_existing(self, env):
        _, eng = env
        _metric(eng)
        got = eng.get_metric("m-1")
        assert got.metric_id == "m-1"

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown metric_id"):
            eng.get_metric("no-such")

    def test_returns_same_data(self, env):
        _, eng = env
        created = _metric(eng)
        got = eng.get_metric("m-1")
        assert created.value == got.value
        assert created.metric_name == got.metric_name


class TestMetricsForTenant:
    def test_empty(self, env):
        _, eng = env
        assert eng.metrics_for_tenant(T) == ()

    def test_filters_by_tenant(self, env):
        _, eng = env
        _metric(eng, "m-1", T)
        _metric(eng, "m-2", T2)
        _metric(eng, "m-3", T)
        result = eng.metrics_for_tenant(T)
        assert len(result) == 2
        assert all(m.tenant_id == T for m in result)

    def test_returns_tuple(self, env):
        _, eng = env
        _metric(eng)
        result = eng.metrics_for_tenant(T)
        assert isinstance(result, tuple)

    def test_no_match(self, env):
        _, eng = env
        _metric(eng)
        assert eng.metrics_for_tenant("other") == ()


class TestMetricsForRuntime:
    def test_filters_by_runtime(self, env):
        _, eng = env
        _metric(eng, "m-1", T, runtime=RT)
        _metric(eng, "m-2", T, runtime=RT2)
        _metric(eng, "m-3", T, runtime=RT)
        result = eng.metrics_for_runtime(T, RT)
        assert len(result) == 2

    def test_cross_tenant_excluded(self, env):
        _, eng = env
        _metric(eng, "m-1", T, runtime=RT)
        _metric(eng, "m-2", T2, runtime=RT)
        result = eng.metrics_for_runtime(T, RT)
        assert len(result) == 1

    def test_empty(self, env):
        _, eng = env
        assert eng.metrics_for_runtime(T, RT) == ()


# =====================================================================
# 3. Logs
# =====================================================================


class TestRecordLog:
    def test_basic(self, env):
        _, eng = env
        log = _log(eng)
        assert isinstance(log, LogRecord)
        assert log.log_id == "l-1"
        assert log.level == "INFO"
        assert log.message == "hello"

    def test_duplicate_raises(self, env):
        _, eng = env
        _log(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate log_id"):
            _log(eng)

    def test_emits_event(self, env):
        es, eng = env
        before = es.event_count
        _log(eng)
        assert es.event_count == before + 1

    def test_trace_id_default(self, env):
        _, eng = env
        log = _log(eng)
        assert log.trace_id == "none"

    def test_trace_id_custom(self, env):
        _, eng = env
        log = _log(eng, trace_id="tr-99")
        assert log.trace_id == "tr-99"

    def test_different_levels(self, env):
        _, eng = env
        for i, lvl in enumerate(["DEBUG", "INFO", "WARN", "ERROR"]):
            l = _log(eng, f"l-{i}", level=lvl)
            assert l.level == lvl

    def test_increments_count(self, env):
        _, eng = env
        for i in range(3):
            _log(eng, f"l-{i}")
        assert eng.log_count == 3

    def test_logged_at_populated(self, env):
        _, eng = env
        log = _log(eng)
        assert log.logged_at


class TestGetLog:
    def test_existing(self, env):
        _, eng = env
        _log(eng)
        got = eng.get_log("l-1")
        assert got.log_id == "l-1"

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown log_id"):
            eng.get_log("nope")


class TestLogsForTenant:
    def test_filters(self, env):
        _, eng = env
        _log(eng, "l-1", T)
        _log(eng, "l-2", T2)
        result = eng.logs_for_tenant(T)
        assert len(result) == 1

    def test_empty(self, env):
        _, eng = env
        assert eng.logs_for_tenant(T) == ()


class TestLogsForTrace:
    def test_filters(self, env):
        _, eng = env
        _log(eng, "l-1", trace_id="tr-1")
        _log(eng, "l-2", trace_id="tr-2")
        _log(eng, "l-3", trace_id="tr-1")
        result = eng.logs_for_trace("tr-1")
        assert len(result) == 2

    def test_empty(self, env):
        _, eng = env
        assert eng.logs_for_trace("tr-0") == ()


# =====================================================================
# 4. Traces
# =====================================================================


class TestOpenTrace:
    def test_basic(self, env):
        _, eng = env
        tr = _trace(eng)
        assert isinstance(tr, TraceRecord)
        assert tr.trace_id == "tr-1"
        assert tr.status == TraceStatus.OPEN
        assert tr.span_count == 0
        assert tr.duration_ms == 0.0

    def test_duplicate_raises(self, env):
        _, eng = env
        _trace(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate trace_id"):
            _trace(eng)

    def test_emits_event(self, env):
        es, eng = env
        before = es.event_count
        _trace(eng)
        assert es.event_count == before + 1

    def test_increments_count(self, env):
        _, eng = env
        for i in range(4):
            _trace(eng, f"tr-{i}")
        assert eng.trace_count == 4

    def test_started_at_populated(self, env):
        _, eng = env
        tr = _trace(eng)
        assert tr.started_at


class TestCloseTrace:
    def test_basic(self, env):
        _, eng = env
        _trace(eng)
        closed = eng.close_trace("tr-1", 100.0)
        assert closed.status == TraceStatus.CLOSED
        assert closed.duration_ms == 100.0

    def test_terminal_guard_closed(self, env):
        _, eng = env
        _trace(eng)
        eng.close_trace("tr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.close_trace("tr-1")

    def test_terminal_guard_error(self, env):
        _, eng = env
        _trace(eng)
        eng.error_trace("tr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.close_trace("tr-1")

    def test_terminal_guard_timeout(self, env):
        _, eng = env
        _trace(eng)
        eng.timeout_trace("tr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.close_trace("tr-1")

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown trace_id"):
            eng.close_trace("nope")

    def test_preserves_span_count(self, env):
        _, eng = env
        _trace(eng)
        _span(eng, "sp-1", "tr-1")
        _span(eng, "sp-2", "tr-1")
        closed = eng.close_trace("tr-1")
        assert closed.span_count == 2

    def test_emits_event(self, env):
        es, eng = env
        _trace(eng)
        before = es.event_count
        eng.close_trace("tr-1")
        assert es.event_count == before + 1

    def test_default_duration(self, env):
        _, eng = env
        _trace(eng)
        closed = eng.close_trace("tr-1")
        assert closed.duration_ms == 0.0


class TestErrorTrace:
    def test_basic(self, env):
        _, eng = env
        _trace(eng)
        err = eng.error_trace("tr-1", 50.0)
        assert err.status == TraceStatus.ERROR
        assert err.duration_ms == 50.0

    def test_terminal_guard_from_closed(self, env):
        _, eng = env
        _trace(eng)
        eng.close_trace("tr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.error_trace("tr-1")

    def test_terminal_guard_from_error(self, env):
        _, eng = env
        _trace(eng)
        eng.error_trace("tr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.error_trace("tr-1")

    def test_terminal_guard_from_timeout(self, env):
        _, eng = env
        _trace(eng)
        eng.timeout_trace("tr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.error_trace("tr-1")

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown trace_id"):
            eng.error_trace("nope")

    def test_emits_event(self, env):
        es, eng = env
        _trace(eng)
        before = es.event_count
        eng.error_trace("tr-1")
        assert es.event_count == before + 1


class TestTimeoutTrace:
    def test_basic(self, env):
        _, eng = env
        _trace(eng)
        to = eng.timeout_trace("tr-1", 30000.0)
        assert to.status == TraceStatus.TIMEOUT
        assert to.duration_ms == 30000.0

    def test_terminal_guard_from_closed(self, env):
        _, eng = env
        _trace(eng)
        eng.close_trace("tr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.timeout_trace("tr-1")

    def test_terminal_guard_from_error(self, env):
        _, eng = env
        _trace(eng)
        eng.error_trace("tr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.timeout_trace("tr-1")

    def test_terminal_guard_from_timeout(self, env):
        _, eng = env
        _trace(eng)
        eng.timeout_trace("tr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.timeout_trace("tr-1")

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown trace_id"):
            eng.timeout_trace("nope")

    def test_emits_event(self, env):
        es, eng = env
        _trace(eng)
        before = es.event_count
        eng.timeout_trace("tr-1")
        assert es.event_count == before + 1


class TestGetTrace:
    def test_existing(self, env):
        _, eng = env
        _trace(eng)
        got = eng.get_trace("tr-1")
        assert got.trace_id == "tr-1"

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown trace_id"):
            eng.get_trace("nope")

    def test_reflects_status_update(self, env):
        _, eng = env
        _trace(eng)
        eng.close_trace("tr-1", 100.0)
        got = eng.get_trace("tr-1")
        assert got.status == TraceStatus.CLOSED
        assert got.duration_ms == 100.0


class TestTracesForTenant:
    def test_filters(self, env):
        _, eng = env
        _trace(eng, "tr-1", T)
        _trace(eng, "tr-2", T2)
        _trace(eng, "tr-3", T)
        result = eng.traces_for_tenant(T)
        assert len(result) == 2

    def test_empty(self, env):
        _, eng = env
        assert eng.traces_for_tenant(T) == ()

    def test_returns_tuple(self, env):
        _, eng = env
        _trace(eng)
        assert isinstance(eng.traces_for_tenant(T), tuple)


# =====================================================================
# 5. Spans
# =====================================================================


class TestAddSpan:
    def test_basic(self, env):
        _, eng = env
        _trace(eng)
        sp = _span(eng)
        assert isinstance(sp, SpanRecord)
        assert sp.span_id == "sp-1"
        assert sp.trace_id == "tr-1"
        assert sp.status == TraceStatus.OPEN
        assert sp.parent_span_id == "root"

    def test_duplicate_raises(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate span_id"):
            _span(eng)

    def test_unknown_trace_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown trace_id"):
            _span(eng, "sp-1", "no-such-trace")

    def test_cross_tenant_raises(self, env):
        _, eng = env
        _trace(eng, "tr-1", T)
        with pytest.raises(RuntimeCoreInvariantError, match="cross-tenant"):
            eng.add_span("sp-1", "tr-1", T2, "span-x", RT)

    def test_increments_trace_span_count(self, env):
        _, eng = env
        _trace(eng)
        _span(eng, "sp-1")
        assert eng.get_trace("tr-1").span_count == 1
        _span(eng, "sp-2")
        assert eng.get_trace("tr-1").span_count == 2

    def test_emits_event(self, env):
        es, eng = env
        _trace(eng)
        before = es.event_count
        _span(eng)
        assert es.event_count == before + 1

    def test_parent_span_custom(self, env):
        _, eng = env
        _trace(eng)
        sp1 = _span(eng, "sp-1")
        sp2 = _span(eng, "sp-2", parent="sp-1")
        assert sp2.parent_span_id == "sp-1"

    def test_with_duration(self, env):
        _, eng = env
        _trace(eng)
        sp = _span(eng, dur=123.45)
        assert sp.duration_ms == 123.45

    def test_increments_engine_span_count(self, env):
        _, eng = env
        _trace(eng)
        for i in range(3):
            _span(eng, f"sp-{i}")
        assert eng.span_count == 3

    def test_span_started_at(self, env):
        _, eng = env
        _trace(eng)
        sp = _span(eng)
        assert sp.started_at


class TestCloseSpan:
    def test_basic(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        closed = eng.close_span("sp-1", 55.0)
        assert closed.status == TraceStatus.CLOSED
        assert closed.duration_ms == 55.0

    def test_terminal_guard(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        eng.close_span("sp-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.close_span("sp-1")

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown span_id"):
            eng.close_span("nope")

    def test_emits_event(self, env):
        es, eng = env
        _trace(eng)
        _span(eng)
        before = es.event_count
        eng.close_span("sp-1")
        assert es.event_count == before + 1

    def test_default_duration(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        closed = eng.close_span("sp-1")
        assert closed.duration_ms == 0.0

    def test_preserves_other_fields(self, env):
        _, eng = env
        _trace(eng)
        _span(eng, "sp-1", name="my-span", parent="root")
        closed = eng.close_span("sp-1", 10.0)
        assert closed.display_name == "my-span"
        assert closed.parent_span_id == "root"
        assert closed.trace_id == "tr-1"


class TestSpansForTrace:
    def test_filters(self, env):
        _, eng = env
        _trace(eng, "tr-1")
        _trace(eng, "tr-2")
        _span(eng, "sp-1", "tr-1")
        _span(eng, "sp-2", "tr-2")
        _span(eng, "sp-3", "tr-1")
        result = eng.spans_for_trace("tr-1")
        assert len(result) == 2

    def test_empty(self, env):
        _, eng = env
        assert eng.spans_for_trace("tr-0") == ()

    def test_returns_tuple(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        assert isinstance(eng.spans_for_trace("tr-1"), tuple)


# =====================================================================
# 6. Anomalies
# =====================================================================


class TestRegisterAnomaly:
    def test_basic(self, env):
        _, eng = env
        a = _anomaly(eng)
        assert isinstance(a, AnomalyRecord)
        assert a.anomaly_id == "an-1"
        assert a.severity == AnomalySeverity.WARNING

    def test_duplicate_raises(self, env):
        _, eng = env
        _anomaly(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate anomaly_id"):
            _anomaly(eng)

    def test_emits_event(self, env):
        es, eng = env
        before = es.event_count
        _anomaly(eng)
        assert es.event_count == before + 1

    def test_severity_critical(self, env):
        _, eng = env
        a = _anomaly(eng, severity=AnomalySeverity.CRITICAL)
        assert a.severity == AnomalySeverity.CRITICAL

    def test_severity_error(self, env):
        _, eng = env
        a = _anomaly(eng, severity=AnomalySeverity.ERROR)
        assert a.severity == AnomalySeverity.ERROR

    def test_severity_info(self, env):
        _, eng = env
        a = _anomaly(eng, severity=AnomalySeverity.INFO)
        assert a.severity == AnomalySeverity.INFO

    def test_trace_id_default(self, env):
        _, eng = env
        a = _anomaly(eng)
        assert a.trace_id == "none"

    def test_trace_id_custom(self, env):
        _, eng = env
        a = _anomaly(eng, trace_id="tr-99")
        assert a.trace_id == "tr-99"

    def test_detected_at_populated(self, env):
        _, eng = env
        a = _anomaly(eng)
        assert a.detected_at

    def test_increments_count(self, env):
        _, eng = env
        for i in range(4):
            _anomaly(eng, f"an-{i}")
        assert eng.anomaly_count == 4


class TestGetAnomaly:
    def test_existing(self, env):
        _, eng = env
        _anomaly(eng)
        got = eng.get_anomaly("an-1")
        assert got.anomaly_id == "an-1"

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown anomaly_id"):
            eng.get_anomaly("nope")


class TestAnomaliesForTenant:
    def test_filters(self, env):
        _, eng = env
        _anomaly(eng, "an-1", T)
        _anomaly(eng, "an-2", T2)
        _anomaly(eng, "an-3", T)
        result = eng.anomalies_for_tenant(T)
        assert len(result) == 2

    def test_empty(self, env):
        _, eng = env
        assert eng.anomalies_for_tenant(T) == ()


class TestCriticalAnomalies:
    def test_only_critical(self, env):
        _, eng = env
        _anomaly(eng, "an-1", T, severity=AnomalySeverity.CRITICAL)
        _anomaly(eng, "an-2", T, severity=AnomalySeverity.WARNING)
        _anomaly(eng, "an-3", T, severity=AnomalySeverity.CRITICAL)
        result = eng.critical_anomalies(T)
        assert len(result) == 2
        assert all(a.severity == AnomalySeverity.CRITICAL for a in result)

    def test_empty(self, env):
        _, eng = env
        _anomaly(eng, "an-1", T, severity=AnomalySeverity.WARNING)
        assert eng.critical_anomalies(T) == ()

    def test_cross_tenant(self, env):
        _, eng = env
        _anomaly(eng, "an-1", T, severity=AnomalySeverity.CRITICAL)
        _anomaly(eng, "an-2", T2, severity=AnomalySeverity.CRITICAL)
        assert len(eng.critical_anomalies(T)) == 1


# =====================================================================
# 7. Debug Sessions
# =====================================================================


class TestOpenDebugSession:
    def test_basic(self, env):
        _, eng = env
        ds = _debug(eng)
        assert isinstance(ds, DebugSession)
        assert ds.session_id == "ds-1"
        assert ds.disposition == DebugDisposition.OPEN

    def test_duplicate_raises(self, env):
        _, eng = env
        _debug(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate session_id"):
            _debug(eng)

    def test_emits_event(self, env):
        es, eng = env
        before = es.event_count
        _debug(eng)
        assert es.event_count == before + 1

    def test_trace_id_default(self, env):
        _, eng = env
        ds = _debug(eng)
        assert ds.trace_id == "none"

    def test_trace_id_custom(self, env):
        _, eng = env
        ds = _debug(eng, trace_id="tr-99")
        assert ds.trace_id == "tr-99"

    def test_increments_count(self, env):
        _, eng = env
        for i in range(3):
            _debug(eng, f"ds-{i}")
        assert eng.debug_session_count == 3

    def test_created_at_populated(self, env):
        _, eng = env
        ds = _debug(eng)
        assert ds.created_at


class TestInvestigateSession:
    def test_basic(self, env):
        _, eng = env
        _debug(eng)
        inv = eng.investigate_session("ds-1")
        assert inv.disposition == DebugDisposition.INVESTIGATING

    def test_terminal_guard_resolved(self, env):
        _, eng = env
        _debug(eng)
        eng.resolve_session("ds-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.investigate_session("ds-1")

    def test_terminal_guard_abandoned(self, env):
        _, eng = env
        _debug(eng)
        eng.abandon_session("ds-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.investigate_session("ds-1")

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown session_id"):
            eng.investigate_session("nope")

    def test_emits_event(self, env):
        es, eng = env
        _debug(eng)
        before = es.event_count
        eng.investigate_session("ds-1")
        assert es.event_count == before + 1

    def test_from_open(self, env):
        _, eng = env
        _debug(eng)
        inv = eng.investigate_session("ds-1")
        assert inv.disposition == DebugDisposition.INVESTIGATING

    def test_double_investigate(self, env):
        _, eng = env
        _debug(eng)
        eng.investigate_session("ds-1")
        # investigating is not terminal, so this should work
        inv2 = eng.investigate_session("ds-1")
        assert inv2.disposition == DebugDisposition.INVESTIGATING


class TestResolveSession:
    def test_basic(self, env):
        _, eng = env
        _debug(eng)
        res = eng.resolve_session("ds-1")
        assert res.disposition == DebugDisposition.RESOLVED

    def test_terminal_guard_resolved(self, env):
        _, eng = env
        _debug(eng)
        eng.resolve_session("ds-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.resolve_session("ds-1")

    def test_terminal_guard_abandoned(self, env):
        _, eng = env
        _debug(eng)
        eng.abandon_session("ds-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.resolve_session("ds-1")

    def test_from_investigating(self, env):
        _, eng = env
        _debug(eng)
        eng.investigate_session("ds-1")
        res = eng.resolve_session("ds-1")
        assert res.disposition == DebugDisposition.RESOLVED

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown session_id"):
            eng.resolve_session("nope")

    def test_emits_event(self, env):
        es, eng = env
        _debug(eng)
        before = es.event_count
        eng.resolve_session("ds-1")
        assert es.event_count == before + 1


class TestAbandonSession:
    def test_basic(self, env):
        _, eng = env
        _debug(eng)
        ab = eng.abandon_session("ds-1")
        assert ab.disposition == DebugDisposition.ABANDONED

    def test_terminal_guard_resolved(self, env):
        _, eng = env
        _debug(eng)
        eng.resolve_session("ds-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.abandon_session("ds-1")

    def test_terminal_guard_abandoned(self, env):
        _, eng = env
        _debug(eng)
        eng.abandon_session("ds-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.abandon_session("ds-1")

    def test_from_investigating(self, env):
        _, eng = env
        _debug(eng)
        eng.investigate_session("ds-1")
        ab = eng.abandon_session("ds-1")
        assert ab.disposition == DebugDisposition.ABANDONED

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown session_id"):
            eng.abandon_session("nope")

    def test_emits_event(self, env):
        es, eng = env
        _debug(eng)
        before = es.event_count
        eng.abandon_session("ds-1")
        assert es.event_count == before + 1


class TestGetDebugSession:
    def test_existing(self, env):
        _, eng = env
        _debug(eng)
        got = eng.get_debug_session("ds-1")
        assert got.session_id == "ds-1"

    def test_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="unknown session_id"):
            eng.get_debug_session("nope")

    def test_reflects_update(self, env):
        _, eng = env
        _debug(eng)
        eng.resolve_session("ds-1")
        got = eng.get_debug_session("ds-1")
        assert got.disposition == DebugDisposition.RESOLVED


class TestDebugSessionsForTenant:
    def test_filters(self, env):
        _, eng = env
        _debug(eng, "ds-1", T)
        _debug(eng, "ds-2", T2)
        _debug(eng, "ds-3", T)
        result = eng.debug_sessions_for_tenant(T)
        assert len(result) == 2

    def test_empty(self, env):
        _, eng = env
        assert eng.debug_sessions_for_tenant(T) == ()

    def test_returns_tuple(self, env):
        _, eng = env
        _debug(eng)
        assert isinstance(eng.debug_sessions_for_tenant(T), tuple)


# =====================================================================
# 8. Snapshot
# =====================================================================


class TestObservabilitySnapshot:
    def test_empty_tenant(self, env):
        _, eng = env
        snap = eng.observability_snapshot("snap-1", T)
        assert isinstance(snap, ObservabilitySnapshot)
        assert snap.total_metrics == 0
        assert snap.total_logs == 0
        assert snap.total_traces == 0
        assert snap.total_spans == 0
        assert snap.total_anomalies == 0
        assert snap.total_debug_sessions == 0
        assert snap.total_violations == 0

    def test_populated(self, env):
        _, eng = env
        _metric(eng)
        _log(eng)
        _trace(eng)
        _span(eng)
        _anomaly(eng)
        _debug(eng)
        snap = eng.observability_snapshot("snap-1", T)
        assert snap.total_metrics == 1
        assert snap.total_logs == 1
        assert snap.total_traces == 1
        assert snap.total_spans == 1
        assert snap.total_anomalies == 1
        assert snap.total_debug_sessions == 1

    def test_cross_tenant_excluded(self, env):
        _, eng = env
        _metric(eng, "m-1", T)
        _metric(eng, "m-2", T2)
        snap = eng.observability_snapshot("snap-1", T)
        assert snap.total_metrics == 1

    def test_emits_event(self, env):
        es, eng = env
        before = es.event_count
        eng.observability_snapshot("snap-1", T)
        assert es.event_count == before + 1

    def test_snapshot_id_preserved(self, env):
        _, eng = env
        snap = eng.observability_snapshot("snap-xyz", T)
        assert snap.snapshot_id == "snap-xyz"

    def test_captured_at_populated(self, env):
        _, eng = env
        snap = eng.observability_snapshot("snap-1", T)
        assert snap.captured_at

    def test_violations_counted(self, env):
        _, eng = env
        # Create stale open trace violation
        _trace(eng)
        _span(eng)
        eng.close_span("sp-1")
        eng.detect_observability_violations(T)
        snap = eng.observability_snapshot("snap-1", T)
        assert snap.total_violations >= 1


# =====================================================================
# 9. Assessment
# =====================================================================


class TestObservabilityAssessment:
    def test_empty(self, env):
        _, eng = env
        a = eng.observability_assessment("a-1", T)
        assert isinstance(a, ObservabilityAssessment)
        assert a.total_signals == 0
        assert a.anomaly_rate == 0.0
        assert a.trace_error_rate == 0.0

    def test_duplicate_raises(self, env):
        _, eng = env
        eng.observability_assessment("a-1", T)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate assessment_id"):
            eng.observability_assessment("a-1", T)

    def test_total_signals(self, env):
        _, eng = env
        _metric(eng)
        _log(eng)
        _trace(eng)
        a = eng.observability_assessment("a-1", T)
        assert a.total_signals == 3  # 1 metric + 1 log + 1 trace

    def test_anomaly_rate(self, env):
        _, eng = env
        _metric(eng)
        _log(eng)
        _trace(eng)
        _anomaly(eng)
        a = eng.observability_assessment("a-1", T)
        # 1 anomaly / 3 signals = 0.3333
        assert a.anomaly_rate == pytest.approx(0.3333, abs=0.001)

    def test_trace_error_rate(self, env):
        _, eng = env
        _trace(eng, "tr-1")
        _trace(eng, "tr-2")
        eng.error_trace("tr-1")
        eng.close_trace("tr-2")
        a = eng.observability_assessment("a-1", T)
        assert a.trace_error_rate == 0.5

    def test_trace_error_rate_all_errors(self, env):
        _, eng = env
        _trace(eng, "tr-1")
        _trace(eng, "tr-2")
        eng.error_trace("tr-1")
        eng.error_trace("tr-2")
        a = eng.observability_assessment("a-1", T)
        assert a.trace_error_rate == 1.0

    def test_trace_error_rate_no_errors(self, env):
        _, eng = env
        _trace(eng, "tr-1")
        eng.close_trace("tr-1")
        a = eng.observability_assessment("a-1", T)
        assert a.trace_error_rate == 0.0

    def test_emits_event(self, env):
        es, eng = env
        before = es.event_count
        eng.observability_assessment("a-1", T)
        assert es.event_count == before + 1

    def test_violations_counted(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        eng.close_span("sp-1")
        eng.detect_observability_violations(T)
        a = eng.observability_assessment("a-1", T)
        assert a.total_violations >= 1

    def test_cross_tenant_excluded(self, env):
        _, eng = env
        _metric(eng, "m-1", T)
        _metric(eng, "m-2", T2)
        a = eng.observability_assessment("a-1", T)
        assert a.total_signals == 1

    def test_anomaly_rate_capped_at_1(self, env):
        _, eng = env
        _metric(eng)  # 1 signal
        for i in range(5):
            _anomaly(eng, f"an-{i}")  # 5 anomalies but rate capped
        a = eng.observability_assessment("a-1", T)
        assert a.anomaly_rate <= 1.0

    def test_assessed_at_populated(self, env):
        _, eng = env
        a = eng.observability_assessment("a-1", T)
        assert a.assessed_at


# =====================================================================
# 10. Violations
# =====================================================================


class TestDetectViolations:
    def test_stale_open_trace(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        eng.close_span("sp-1")
        violations = eng.detect_observability_violations(T)
        assert len(violations) == 1
        assert violations[0].operation == "stale_open_trace"

    def test_stale_open_trace_no_spans(self, env):
        _, eng = env
        _trace(eng)
        violations = eng.detect_observability_violations(T)
        # No spans means span_count is 0, so no stale violation
        assert not any(v.operation == "stale_open_trace" for v in violations)

    def test_stale_open_trace_span_still_open(self, env):
        _, eng = env
        _trace(eng)
        _span(eng, "sp-1")
        _span(eng, "sp-2")
        eng.close_span("sp-1")
        # sp-2 still open, so not stale
        violations = eng.detect_observability_violations(T)
        assert not any(v.operation == "stale_open_trace" for v in violations)

    def test_critical_no_debug(self, env):
        _, eng = env
        _anomaly(eng, severity=AnomalySeverity.CRITICAL)
        violations = eng.detect_observability_violations(T)
        assert any(v.operation == "critical_no_debug" for v in violations)

    def test_critical_with_debug_no_violation(self, env):
        _, eng = env
        _anomaly(eng, severity=AnomalySeverity.CRITICAL, trace_id="tr-1")
        _debug(eng, trace_id="tr-1")
        violations = eng.detect_observability_violations(T)
        assert not any(v.operation == "critical_no_debug" for v in violations)

    def test_critical_no_debug_trace_none(self, env):
        _, eng = env
        # Critical anomaly with trace_id="none" -- even if debug session also has
        # trace_id="none", the code checks s.trace_id != "none", so no match
        _anomaly(eng, severity=AnomalySeverity.CRITICAL, trace_id="none")
        _debug(eng, trace_id="none")
        violations = eng.detect_observability_violations(T)
        assert any(v.operation == "critical_no_debug" for v in violations)

    def test_warning_no_debug_no_violation(self, env):
        _, eng = env
        _anomaly(eng, severity=AnomalySeverity.WARNING)
        violations = eng.detect_observability_violations(T)
        assert not any(v.operation == "critical_no_debug" for v in violations)

    def test_high_trace_error_rate(self, env):
        _, eng = env
        # Need >= 5 traces with > 50% errors
        for i in range(6):
            _trace(eng, f"tr-{i}")
        for i in range(4):
            eng.error_trace(f"tr-{i}")
        for i in range(4, 6):
            eng.close_trace(f"tr-{i}")
        # 4/6 = 66% > 50%
        violations = eng.detect_observability_violations(T)
        assert any(v.operation == "high_trace_error_rate" for v in violations)

    def test_high_trace_error_rate_below_threshold(self, env):
        _, eng = env
        for i in range(6):
            _trace(eng, f"tr-{i}")
        for i in range(3):
            eng.error_trace(f"tr-{i}")
        for i in range(3, 6):
            eng.close_trace(f"tr-{i}")
        # 3/6 = 50%, not > 50%
        violations = eng.detect_observability_violations(T)
        assert not any(v.operation == "high_trace_error_rate" for v in violations)

    def test_high_trace_error_rate_under_5_traces(self, env):
        _, eng = env
        for i in range(4):
            _trace(eng, f"tr-{i}")
            eng.error_trace(f"tr-{i}")
        # 4/4 = 100% but only 4 traces (< 5)
        violations = eng.detect_observability_violations(T)
        assert not any(v.operation == "high_trace_error_rate" for v in violations)

    def test_idempotent(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        eng.close_span("sp-1")
        v1 = eng.detect_observability_violations(T)
        v2 = eng.detect_observability_violations(T)
        assert len(v1) >= 1
        assert len(v2) == 0  # already detected

    def test_emits_event_when_violations_found(self, env):
        es, eng = env
        _trace(eng)
        _span(eng)
        eng.close_span("sp-1")
        before = es.event_count
        eng.detect_observability_violations(T)
        assert es.event_count == before + 1

    def test_no_event_when_no_violations(self, env):
        es, eng = env
        before = es.event_count
        eng.detect_observability_violations(T)
        assert es.event_count == before

    def test_cross_tenant_isolation(self, env):
        _, eng = env
        _trace(eng, "tr-1", T)
        _span(eng, "sp-1", "tr-1", T)
        eng.close_span("sp-1")
        violations = eng.detect_observability_violations(T2)
        assert len(violations) == 0

    def test_returns_tuple(self, env):
        _, eng = env
        result = eng.detect_observability_violations(T)
        assert isinstance(result, tuple)

    def test_multiple_violation_types(self, env):
        _, eng = env
        # stale trace
        _trace(eng, "tr-stale")
        eng.add_span("sp-stale", "tr-stale", T, "span", RT)
        eng.close_span("sp-stale")
        # critical anomaly with no debug
        _anomaly(eng, "an-crit", severity=AnomalySeverity.CRITICAL)
        # high error rate: need 5+ traces with >50% error
        for i in range(5):
            _trace(eng, f"tr-err-{i}")
            eng.error_trace(f"tr-err-{i}")
        violations = eng.detect_observability_violations(T)
        ops = {v.operation for v in violations}
        assert "stale_open_trace" in ops
        assert "critical_no_debug" in ops
        assert "high_trace_error_rate" in ops


class TestViolationsForTenant:
    def test_filters(self, env):
        _, eng = env
        _trace(eng, "tr-1", T)
        eng.add_span("sp-1", "tr-1", T, "s", RT)
        eng.close_span("sp-1")
        eng.detect_observability_violations(T)
        assert len(eng.violations_for_tenant(T)) >= 1
        assert len(eng.violations_for_tenant(T2)) == 0


# =====================================================================
# 11. Closure Report
# =====================================================================


class TestClosureReport:
    def test_empty(self, env):
        _, eng = env
        r = eng.closure_report("r-1", T)
        assert isinstance(r, ObservabilityClosureReport)
        assert r.total_metrics == 0
        assert r.total_logs == 0

    def test_populated(self, env):
        _, eng = env
        _metric(eng)
        _log(eng)
        _trace(eng)
        _span(eng)
        _anomaly(eng)
        _debug(eng)
        r = eng.closure_report("r-1", T)
        assert r.total_metrics == 1
        assert r.total_logs == 1
        assert r.total_traces == 1
        assert r.total_spans == 1
        assert r.total_anomalies == 1
        assert r.total_debug_sessions == 1

    def test_cross_tenant_excluded(self, env):
        _, eng = env
        _metric(eng, "m-1", T)
        _metric(eng, "m-2", T2)
        r = eng.closure_report("r-1", T)
        assert r.total_metrics == 1

    def test_emits_event(self, env):
        es, eng = env
        before = es.event_count
        eng.closure_report("r-1", T)
        assert es.event_count == before + 1

    def test_report_id_preserved(self, env):
        _, eng = env
        r = eng.closure_report("r-xyz", T)
        assert r.report_id == "r-xyz"

    def test_created_at_populated(self, env):
        _, eng = env
        r = eng.closure_report("r-1", T)
        assert r.created_at


# =====================================================================
# 12. State Hash
# =====================================================================


class TestStateHash:
    def test_empty_deterministic(self, env):
        _, eng = env
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2

    def test_changes_on_metric(self, env):
        _, eng = env
        h1 = eng.state_hash()
        _metric(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_log(self, env):
        _, eng = env
        h1 = eng.state_hash()
        _log(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_trace(self, env):
        _, eng = env
        h1 = eng.state_hash()
        _trace(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_span(self, env):
        _, eng = env
        _trace(eng)
        h1 = eng.state_hash()
        _span(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_anomaly(self, env):
        _, eng = env
        h1 = eng.state_hash()
        _anomaly(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_debug_session(self, env):
        _, eng = env
        h1 = eng.state_hash()
        _debug(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_violation(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        eng.close_span("sp-1")
        h1 = eng.state_hash()
        eng.detect_observability_violations(T)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_trace_status(self, env):
        _, eng = env
        _trace(eng)
        h1 = eng.state_hash()
        eng.close_trace("tr-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_session_disposition(self, env):
        _, eng = env
        _debug(eng)
        h1 = eng.state_hash()
        eng.resolve_session("ds-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_returns_hex_string(self, env):
        _, eng = env
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_same_data_same_hash(self, env):
        es1 = EventSpineEngine()
        eng1 = ObservabilityRuntimeEngine(es1)
        es2 = EventSpineEngine()
        eng2 = ObservabilityRuntimeEngine(es2)
        _metric(eng1, "m-1")
        _metric(eng2, "m-1")
        assert eng1.state_hash() == eng2.state_hash()


# =====================================================================
# 13. Properties
# =====================================================================


class TestProperties:
    def test_metric_count(self, env):
        _, eng = env
        assert eng.metric_count == 0
        _metric(eng)
        assert eng.metric_count == 1

    def test_log_count(self, env):
        _, eng = env
        assert eng.log_count == 0
        _log(eng)
        assert eng.log_count == 1

    def test_trace_count(self, env):
        _, eng = env
        assert eng.trace_count == 0
        _trace(eng)
        assert eng.trace_count == 1

    def test_span_count(self, env):
        _, eng = env
        assert eng.span_count == 0
        _trace(eng)
        _span(eng)
        assert eng.span_count == 1

    def test_anomaly_count(self, env):
        _, eng = env
        assert eng.anomaly_count == 0
        _anomaly(eng)
        assert eng.anomaly_count == 1

    def test_debug_session_count(self, env):
        _, eng = env
        assert eng.debug_session_count == 0
        _debug(eng)
        assert eng.debug_session_count == 1

    def test_violation_count(self, env):
        _, eng = env
        assert eng.violation_count == 0
        _trace(eng)
        _span(eng)
        eng.close_span("sp-1")
        eng.detect_observability_violations(T)
        assert eng.violation_count >= 1

    def test_assessment_count(self, env):
        _, eng = env
        assert eng.assessment_count == 0
        eng.observability_assessment("a-1", T)
        assert eng.assessment_count == 1


# =====================================================================
# 14. Event Emission Verification
# =====================================================================


class TestEventEmission:
    """Verify that every mutation emits an event to the spine."""

    def test_record_metric_emits(self, env):
        es, eng = env
        c = es.event_count
        _metric(eng)
        assert es.event_count == c + 1

    def test_record_log_emits(self, env):
        es, eng = env
        c = es.event_count
        _log(eng)
        assert es.event_count == c + 1

    def test_open_trace_emits(self, env):
        es, eng = env
        c = es.event_count
        _trace(eng)
        assert es.event_count == c + 1

    def test_close_trace_emits(self, env):
        es, eng = env
        _trace(eng)
        c = es.event_count
        eng.close_trace("tr-1")
        assert es.event_count == c + 1

    def test_error_trace_emits(self, env):
        es, eng = env
        _trace(eng)
        c = es.event_count
        eng.error_trace("tr-1")
        assert es.event_count == c + 1

    def test_timeout_trace_emits(self, env):
        es, eng = env
        _trace(eng)
        c = es.event_count
        eng.timeout_trace("tr-1")
        assert es.event_count == c + 1

    def test_add_span_emits(self, env):
        es, eng = env
        _trace(eng)
        c = es.event_count
        _span(eng)
        assert es.event_count == c + 1

    def test_close_span_emits(self, env):
        es, eng = env
        _trace(eng)
        _span(eng)
        c = es.event_count
        eng.close_span("sp-1")
        assert es.event_count == c + 1

    def test_register_anomaly_emits(self, env):
        es, eng = env
        c = es.event_count
        _anomaly(eng)
        assert es.event_count == c + 1

    def test_open_debug_session_emits(self, env):
        es, eng = env
        c = es.event_count
        _debug(eng)
        assert es.event_count == c + 1

    def test_investigate_session_emits(self, env):
        es, eng = env
        _debug(eng)
        c = es.event_count
        eng.investigate_session("ds-1")
        assert es.event_count == c + 1

    def test_resolve_session_emits(self, env):
        es, eng = env
        _debug(eng)
        c = es.event_count
        eng.resolve_session("ds-1")
        assert es.event_count == c + 1

    def test_abandon_session_emits(self, env):
        es, eng = env
        _debug(eng)
        c = es.event_count
        eng.abandon_session("ds-1")
        assert es.event_count == c + 1

    def test_snapshot_emits(self, env):
        es, eng = env
        c = es.event_count
        eng.observability_snapshot("snap-1", T)
        assert es.event_count == c + 1

    def test_assessment_emits(self, env):
        es, eng = env
        c = es.event_count
        eng.observability_assessment("a-1", T)
        assert es.event_count == c + 1

    def test_closure_report_emits(self, env):
        es, eng = env
        c = es.event_count
        eng.closure_report("r-1", T)
        assert es.event_count == c + 1


# =====================================================================
# 15. Immutability Checks
# =====================================================================


class TestImmutability:
    def test_metric_record_frozen(self, env):
        _, eng = env
        m = _metric(eng)
        with pytest.raises(AttributeError):
            m.value = 99.0

    def test_log_record_frozen(self, env):
        _, eng = env
        log = _log(eng)
        with pytest.raises(AttributeError):
            log.message = "changed"

    def test_trace_record_frozen(self, env):
        _, eng = env
        tr = _trace(eng)
        with pytest.raises(AttributeError):
            tr.status = TraceStatus.CLOSED

    def test_span_record_frozen(self, env):
        _, eng = env
        _trace(eng)
        sp = _span(eng)
        with pytest.raises(AttributeError):
            sp.status = TraceStatus.CLOSED

    def test_anomaly_record_frozen(self, env):
        _, eng = env
        a = _anomaly(eng)
        with pytest.raises(AttributeError):
            a.severity = AnomalySeverity.CRITICAL

    def test_debug_session_frozen(self, env):
        _, eng = env
        ds = _debug(eng)
        with pytest.raises(AttributeError):
            ds.disposition = DebugDisposition.RESOLVED

    def test_snapshot_frozen(self, env):
        _, eng = env
        snap = eng.observability_snapshot("snap-1", T)
        with pytest.raises(AttributeError):
            snap.total_metrics = 99

    def test_assessment_frozen(self, env):
        _, eng = env
        a = eng.observability_assessment("a-1", T)
        with pytest.raises(AttributeError):
            a.anomaly_rate = 0.99

    def test_closure_report_frozen(self, env):
        _, eng = env
        r = eng.closure_report("r-1", T)
        with pytest.raises(AttributeError):
            r.total_metrics = 99

    def test_metrics_for_tenant_returns_tuple(self, env):
        _, eng = env
        _metric(eng)
        result = eng.metrics_for_tenant(T)
        assert isinstance(result, tuple)

    def test_logs_for_tenant_returns_tuple(self, env):
        _, eng = env
        _log(eng)
        result = eng.logs_for_tenant(T)
        assert isinstance(result, tuple)

    def test_traces_for_tenant_returns_tuple(self, env):
        _, eng = env
        _trace(eng)
        result = eng.traces_for_tenant(T)
        assert isinstance(result, tuple)

    def test_spans_for_trace_returns_tuple(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        result = eng.spans_for_trace("tr-1")
        assert isinstance(result, tuple)

    def test_anomalies_for_tenant_returns_tuple(self, env):
        _, eng = env
        _anomaly(eng)
        result = eng.anomalies_for_tenant(T)
        assert isinstance(result, tuple)

    def test_debug_sessions_for_tenant_returns_tuple(self, env):
        _, eng = env
        _debug(eng)
        result = eng.debug_sessions_for_tenant(T)
        assert isinstance(result, tuple)

    def test_violations_returns_tuple(self, env):
        _, eng = env
        result = eng.detect_observability_violations(T)
        assert isinstance(result, tuple)


# =====================================================================
# 16. Enum Smoke Tests
# =====================================================================


class TestEnumValues:
    def test_telemetry_status_values(self):
        assert TelemetryStatus.ACTIVE.value == "active"
        assert TelemetryStatus.BUFFERED.value == "buffered"
        assert TelemetryStatus.FLUSHED.value == "flushed"
        assert TelemetryStatus.DROPPED.value == "dropped"

    def test_signal_kind_values(self):
        assert SignalKind.METRIC.value == "metric"
        assert SignalKind.LOG.value == "log"
        assert SignalKind.TRACE.value == "trace"
        assert SignalKind.SPAN.value == "span"
        assert SignalKind.ANOMALY.value == "anomaly"

    def test_trace_status_values(self):
        assert TraceStatus.OPEN.value == "open"
        assert TraceStatus.CLOSED.value == "closed"
        assert TraceStatus.ERROR.value == "error"
        assert TraceStatus.TIMEOUT.value == "timeout"

    def test_anomaly_severity_values(self):
        assert AnomalySeverity.INFO.value == "info"
        assert AnomalySeverity.WARNING.value == "warning"
        assert AnomalySeverity.ERROR.value == "error"
        assert AnomalySeverity.CRITICAL.value == "critical"

    def test_debug_disposition_values(self):
        assert DebugDisposition.OPEN.value == "open"
        assert DebugDisposition.INVESTIGATING.value == "investigating"
        assert DebugDisposition.RESOLVED.value == "resolved"
        assert DebugDisposition.ABANDONED.value == "abandoned"

    def test_observability_scope_values(self):
        assert ObservabilityScope.TENANT.value == "tenant"
        assert ObservabilityScope.WORKSPACE.value == "workspace"
        assert ObservabilityScope.RUNTIME.value == "runtime"
        assert ObservabilityScope.SERVICE.value == "service"
        assert ObservabilityScope.GLOBAL.value == "global"
        assert ObservabilityScope.ENDPOINT.value == "endpoint"


# =====================================================================
# 17. Multi-Tenant Isolation
# =====================================================================


class TestMultiTenantIsolation:
    def test_metrics_isolated(self, env):
        _, eng = env
        _metric(eng, "m-1", T)
        _metric(eng, "m-2", T2)
        assert len(eng.metrics_for_tenant(T)) == 1
        assert len(eng.metrics_for_tenant(T2)) == 1

    def test_logs_isolated(self, env):
        _, eng = env
        _log(eng, "l-1", T)
        _log(eng, "l-2", T2)
        assert len(eng.logs_for_tenant(T)) == 1
        assert len(eng.logs_for_tenant(T2)) == 1

    def test_traces_isolated(self, env):
        _, eng = env
        _trace(eng, "tr-1", T)
        _trace(eng, "tr-2", T2)
        assert len(eng.traces_for_tenant(T)) == 1
        assert len(eng.traces_for_tenant(T2)) == 1

    def test_anomalies_isolated(self, env):
        _, eng = env
        _anomaly(eng, "an-1", T)
        _anomaly(eng, "an-2", T2)
        assert len(eng.anomalies_for_tenant(T)) == 1
        assert len(eng.anomalies_for_tenant(T2)) == 1

    def test_debug_sessions_isolated(self, env):
        _, eng = env
        _debug(eng, "ds-1", T)
        _debug(eng, "ds-2", T2)
        assert len(eng.debug_sessions_for_tenant(T)) == 1
        assert len(eng.debug_sessions_for_tenant(T2)) == 1

    def test_snapshot_isolated(self, env):
        _, eng = env
        _metric(eng, "m-1", T)
        _metric(eng, "m-2", T2)
        snap_t1 = eng.observability_snapshot("s-1", T)
        snap_t2 = eng.observability_snapshot("s-2", T2)
        assert snap_t1.total_metrics == 1
        assert snap_t2.total_metrics == 1

    def test_closure_report_isolated(self, env):
        _, eng = env
        _log(eng, "l-1", T)
        _log(eng, "l-2", T2)
        r1 = eng.closure_report("r-1", T)
        r2 = eng.closure_report("r-2", T2)
        assert r1.total_logs == 1
        assert r2.total_logs == 1

    def test_violations_isolated(self, env):
        _, eng = env
        _trace(eng, "tr-1", T)
        eng.add_span("sp-1", "tr-1", T, "s", RT)
        eng.close_span("sp-1")
        eng.detect_observability_violations(T)
        eng.detect_observability_violations(T2)
        assert len(eng.violations_for_tenant(T)) >= 1
        assert len(eng.violations_for_tenant(T2)) == 0


# =====================================================================
# 18. Edge Cases
# =====================================================================


class TestEdgeCases:
    def test_close_trace_preserves_display_name(self, env):
        _, eng = env
        _trace(eng, name="special-trace")
        closed = eng.close_trace("tr-1")
        assert closed.display_name == "special-trace"

    def test_error_trace_preserves_source_runtime(self, env):
        _, eng = env
        _trace(eng, runtime="my-rt")
        err = eng.error_trace("tr-1")
        assert err.source_runtime == "my-rt"

    def test_timeout_trace_preserves_tenant(self, env):
        _, eng = env
        _trace(eng, tid="t-special")
        to = eng.timeout_trace("tr-1")
        assert to.tenant_id == "t-special"

    def test_close_span_preserves_source_runtime(self, env):
        _, eng = env
        _trace(eng)
        _span(eng, runtime="rt-span")
        closed = eng.close_span("sp-1")
        assert closed.source_runtime == "rt-span"

    def test_investigate_preserves_operator(self, env):
        _, eng = env
        _debug(eng, op="ops-1")
        inv = eng.investigate_session("ds-1")
        assert inv.operator_ref == "ops-1"

    def test_resolve_preserves_target_runtime(self, env):
        _, eng = env
        _debug(eng, target="rt-target")
        res = eng.resolve_session("ds-1")
        assert res.target_runtime == "rt-target"

    def test_abandon_preserves_trace_id(self, env):
        _, eng = env
        _debug(eng, trace_id="tr-linked")
        ab = eng.abandon_session("ds-1")
        assert ab.trace_id == "tr-linked"

    def test_many_metrics(self, env):
        _, eng = env
        for i in range(100):
            _metric(eng, f"m-{i}", value=float(i))
        assert eng.metric_count == 100

    def test_many_logs(self, env):
        _, eng = env
        for i in range(100):
            _log(eng, f"l-{i}")
        assert eng.log_count == 100

    def test_many_traces(self, env):
        _, eng = env
        for i in range(50):
            _trace(eng, f"tr-{i}")
        assert eng.trace_count == 50

    def test_span_with_zero_duration(self, env):
        _, eng = env
        _trace(eng)
        sp = _span(eng, dur=0.0)
        assert sp.duration_ms == 0.0

    def test_assessment_no_traces(self, env):
        _, eng = env
        _metric(eng)
        a = eng.observability_assessment("a-1", T)
        assert a.trace_error_rate == 0.0

    def test_snapshot_multiple_calls(self, env):
        _, eng = env
        _metric(eng)
        s1 = eng.observability_snapshot("s-1", T)
        _metric(eng, "m-2")
        s2 = eng.observability_snapshot("s-2", T)
        assert s1.total_metrics == 1
        assert s2.total_metrics == 2


# =====================================================================
# 19. Trace Lifecycle (Full State Machine)
# =====================================================================


class TestTraceLifecycle:
    def test_open_to_closed(self, env):
        _, eng = env
        tr = _trace(eng)
        assert tr.status == TraceStatus.OPEN
        closed = eng.close_trace("tr-1", 10.0)
        assert closed.status == TraceStatus.CLOSED

    def test_open_to_error(self, env):
        _, eng = env
        _trace(eng)
        err = eng.error_trace("tr-1", 5.0)
        assert err.status == TraceStatus.ERROR

    def test_open_to_timeout(self, env):
        _, eng = env
        _trace(eng)
        to = eng.timeout_trace("tr-1", 9999.0)
        assert to.status == TraceStatus.TIMEOUT

    def test_closed_is_terminal(self, env):
        _, eng = env
        _trace(eng)
        eng.close_trace("tr-1")
        for fn in [eng.close_trace, eng.error_trace, eng.timeout_trace]:
            with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
                fn("tr-1")

    def test_error_is_terminal(self, env):
        _, eng = env
        _trace(eng)
        eng.error_trace("tr-1")
        for fn in [eng.close_trace, eng.error_trace, eng.timeout_trace]:
            with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
                fn("tr-1")

    def test_timeout_is_terminal(self, env):
        _, eng = env
        _trace(eng)
        eng.timeout_trace("tr-1")
        for fn in [eng.close_trace, eng.error_trace, eng.timeout_trace]:
            with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
                fn("tr-1")


# =====================================================================
# 20. Debug Session Lifecycle (Full State Machine)
# =====================================================================


class TestDebugSessionLifecycle:
    def test_open_to_investigating(self, env):
        _, eng = env
        _debug(eng)
        inv = eng.investigate_session("ds-1")
        assert inv.disposition == DebugDisposition.INVESTIGATING

    def test_open_to_resolved(self, env):
        _, eng = env
        _debug(eng)
        res = eng.resolve_session("ds-1")
        assert res.disposition == DebugDisposition.RESOLVED

    def test_open_to_abandoned(self, env):
        _, eng = env
        _debug(eng)
        ab = eng.abandon_session("ds-1")
        assert ab.disposition == DebugDisposition.ABANDONED

    def test_investigating_to_resolved(self, env):
        _, eng = env
        _debug(eng)
        eng.investigate_session("ds-1")
        res = eng.resolve_session("ds-1")
        assert res.disposition == DebugDisposition.RESOLVED

    def test_investigating_to_abandoned(self, env):
        _, eng = env
        _debug(eng)
        eng.investigate_session("ds-1")
        ab = eng.abandon_session("ds-1")
        assert ab.disposition == DebugDisposition.ABANDONED

    def test_resolved_is_terminal(self, env):
        _, eng = env
        _debug(eng)
        eng.resolve_session("ds-1")
        for fn in [eng.investigate_session, eng.resolve_session, eng.abandon_session]:
            with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
                fn("ds-1")

    def test_abandoned_is_terminal(self, env):
        _, eng = env
        _debug(eng)
        eng.abandon_session("ds-1")
        for fn in [eng.investigate_session, eng.resolve_session, eng.abandon_session]:
            with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
                fn("ds-1")


# =====================================================================
# GOLDEN SCENARIOS
# =====================================================================


class TestGoldenScenario1FailedServiceRequest:
    """A failed service request produces a trace + anomaly."""

    def test_full_flow(self, env):
        _, eng = env
        # 1. Open trace for the request
        tr = eng.open_trace("tr-svc-1", T, "svc-request", RT)
        assert tr.status == TraceStatus.OPEN

        # 2. Add a span for the request handling
        sp = eng.add_span("sp-svc-1", "tr-svc-1", T, "handle-request", RT)
        assert sp.status == TraceStatus.OPEN

        # 3. Close span with duration
        eng.close_span("sp-svc-1", 200.0)

        # 4. Error the trace (service failed)
        err = eng.error_trace("tr-svc-1", 250.0)
        assert err.status == TraceStatus.ERROR

        # 5. Register anomaly for the failure
        anomaly = eng.register_anomaly(
            "an-svc-1", T, RT, "service request failed with 500",
            AnomalySeverity.ERROR, "tr-svc-1",
        )
        assert anomaly.trace_id == "tr-svc-1"

        # 6. Log the error
        log = eng.record_log(
            "l-svc-1", T, "ERROR", "request failed", RT, "tr-svc-1",
        )
        assert log.trace_id == "tr-svc-1"

        # 7. Verify logs for trace
        logs = eng.logs_for_trace("tr-svc-1")
        assert len(logs) == 1

        # 8. Snapshot reflects the state
        snap = eng.observability_snapshot("snap-svc-1", T)
        assert snap.total_traces == 1
        assert snap.total_anomalies == 1
        assert snap.total_logs == 1


class TestGoldenScenario2ContinuityDisruption:
    """Continuity disruption creates an observability alert chain."""

    def test_alert_chain(self, env):
        _, eng = env
        # 1. Multiple traces to establish baseline
        for i in range(6):
            eng.open_trace(f"tr-cd-{i}", T, f"trace-{i}", RT)

        # 2. Error most of them (disruption)
        for i in range(4):
            eng.error_trace(f"tr-cd-{i}")
        for i in range(4, 6):
            eng.close_trace(f"tr-cd-{i}")

        # 3. Register critical anomaly
        eng.register_anomaly(
            "an-cd-1", T, RT, "continuity disrupted",
            AnomalySeverity.CRITICAL,
        )

        # 4. Detect violations: should find high_trace_error_rate + critical_no_debug
        violations = eng.detect_observability_violations(T)
        ops = {v.operation for v in violations}
        assert "high_trace_error_rate" in ops
        assert "critical_no_debug" in ops

        # 5. Assessment confirms high error rate
        a = eng.observability_assessment("a-cd-1", T)
        assert a.trace_error_rate > 0.5


class TestGoldenScenario3ExecutiveIssueDebugSnapshot:
    """Executive issue appears in debug snapshot."""

    def test_executive_debug(self, env):
        _, eng = env
        # 1. Open trace for executive report generation
        eng.open_trace("tr-exec-1", T, "exec-report-gen", RT)
        eng.add_span("sp-exec-1", "tr-exec-1", T, "data-gather", RT)
        eng.close_span("sp-exec-1", 500.0)
        eng.error_trace("tr-exec-1", 600.0)

        # 2. Register critical anomaly
        eng.register_anomaly(
            "an-exec-1", T, RT, "executive report generation failed",
            AnomalySeverity.CRITICAL, "tr-exec-1",
        )

        # 3. Open debug session linked to trace
        ds = eng.open_debug_session(
            "ds-exec-1", T, "cto-ops", RT, "tr-exec-1",
        )
        assert ds.disposition == DebugDisposition.OPEN

        # 4. Investigate
        eng.investigate_session("ds-exec-1")

        # 5. Snapshot includes the debug session
        snap = eng.observability_snapshot("snap-exec-1", T)
        assert snap.total_debug_sessions == 1
        assert snap.total_anomalies == 1
        assert snap.total_traces == 1

        # 6. Resolve session
        resolved = eng.resolve_session("ds-exec-1")
        assert resolved.disposition == DebugDisposition.RESOLVED


class TestGoldenScenario4CrossTenantAccessDenied:
    """Cross-tenant observability access denied fail-closed (add_span)."""

    def test_cross_tenant_span_denied(self, env):
        _, eng = env
        # 1. Tenant 1 opens a trace
        eng.open_trace("tr-ct-1", T, "private-trace", RT)

        # 2. Tenant 2 tries to add a span -- denied
        with pytest.raises(RuntimeCoreInvariantError, match="cross-tenant"):
            eng.add_span("sp-ct-1", "tr-ct-1", T2, "evil-span", RT2)

        # 3. Original tenant can still add spans
        sp = eng.add_span("sp-ct-ok", "tr-ct-1", T, "legit-span", RT)
        assert sp.tenant_id == T

        # 4. Verify no span was created for tenant 2
        assert eng.span_count == 1

    def test_cross_tenant_metric_isolation(self, env):
        _, eng = env
        _metric(eng, "m-ct-1", T)
        _metric(eng, "m-ct-2", T2)
        assert len(eng.metrics_for_tenant(T)) == 1
        assert len(eng.metrics_for_tenant(T2)) == 1

    def test_cross_tenant_anomaly_isolation(self, env):
        _, eng = env
        _anomaly(eng, "an-ct-1", T)
        assert len(eng.anomalies_for_tenant(T2)) == 0


class TestGoldenScenario5ReplayRestore:
    """Replay/restore preserves metrics, traces, debug sessions (state_hash)."""

    def test_state_hash_preserves_across_replay(self, env):
        _, eng = env
        # Build up state
        _metric(eng, "m-rr-1")
        _log(eng, "l-rr-1")
        _trace(eng, "tr-rr-1")
        _span(eng, "sp-rr-1", "tr-rr-1")
        eng.close_span("sp-rr-1", 50.0)
        eng.close_trace("tr-rr-1", 100.0)
        _anomaly(eng, "an-rr-1")
        _debug(eng, "ds-rr-1")
        eng.resolve_session("ds-rr-1")

        hash_before = eng.state_hash()

        # Replay the same operations on a fresh engine
        es2 = EventSpineEngine()
        eng2 = ObservabilityRuntimeEngine(es2)
        _metric(eng2, "m-rr-1")
        _log(eng2, "l-rr-1")
        _trace(eng2, "tr-rr-1")
        _span(eng2, "sp-rr-1", "tr-rr-1")
        eng2.close_span("sp-rr-1", 50.0)
        eng2.close_trace("tr-rr-1", 100.0)
        _anomaly(eng2, "an-rr-1")
        _debug(eng2, "ds-rr-1")
        eng2.resolve_session("ds-rr-1")

        assert eng2.state_hash() == hash_before

    def test_state_hash_differs_on_divergence(self, env):
        _, eng = env
        _metric(eng, "m-rr-1")
        hash1 = eng.state_hash()

        es2 = EventSpineEngine()
        eng2 = ObservabilityRuntimeEngine(es2)
        _metric(eng2, "m-rr-1", value=999.0)  # different value
        assert eng2.state_hash() != hash1  # value is in the hash

    def test_closure_report_matches_snapshot(self, env):
        _, eng = env
        _metric(eng)
        _log(eng)
        _trace(eng)
        _span(eng)
        _anomaly(eng)
        _debug(eng)
        snap = eng.observability_snapshot("snap-rr", T)
        report = eng.closure_report("r-rr", T)
        assert snap.total_metrics == report.total_metrics
        assert snap.total_logs == report.total_logs
        assert snap.total_traces == report.total_traces
        assert snap.total_spans == report.total_spans
        assert snap.total_anomalies == report.total_anomalies
        assert snap.total_debug_sessions == report.total_debug_sessions


class TestGoldenScenario6OrchestrationMultiStepTrace:
    """Orchestration plan generates multi-step trace lineage."""

    def test_multi_step_trace(self, env):
        _, eng = env
        # 1. Open the orchestration trace
        tr = eng.open_trace("tr-orch-1", T, "orchestration-plan", RT)
        assert tr.span_count == 0

        # 2. Add multiple sequential spans (steps in the plan)
        step_names = ["validate-input", "fetch-data", "transform", "persist", "notify"]
        for i, name in enumerate(step_names):
            parent = "root" if i == 0 else f"sp-orch-{i - 1}"
            eng.add_span(f"sp-orch-{i}", "tr-orch-1", T, name, RT, parent, float(i * 100))

        # 3. Verify span lineage
        spans = eng.spans_for_trace("tr-orch-1")
        assert len(spans) == 5

        # 4. Verify parent chain
        assert spans[0].parent_span_id == "root"
        for i in range(1, len(spans)):
            assert spans[i].parent_span_id == f"sp-orch-{i - 1}"

        # 5. Close all spans
        for i in range(5):
            eng.close_span(f"sp-orch-{i}", float((i + 1) * 100))

        # 6. Verify trace span count
        trace = eng.get_trace("tr-orch-1")
        assert trace.span_count == 5

        # 7. Close the trace
        closed = eng.close_trace("tr-orch-1", 1500.0)
        assert closed.status == TraceStatus.CLOSED
        assert closed.span_count == 5
        assert closed.duration_ms == 1500.0

        # 8. Metric for the orchestration
        eng.record_metric("m-orch-1", T, "orch-duration", 1500.0, RT)

        # 9. Assessment
        a = eng.observability_assessment("a-orch-1", T)
        assert a.total_signals >= 2  # metric + trace
        assert a.trace_error_rate == 0.0


class TestGoldenScenario7FullObservabilityWorkflow:
    """End-to-end: metrics, logs, traces, spans, anomalies, debug, violations,
    snapshot, assessment, closure report, state hash."""

    def test_full_workflow(self, env):
        _, eng = env
        # Metrics
        eng.record_metric("m-fw-1", T, "latency", 100.0, RT)
        eng.record_metric("m-fw-2", T, "throughput", 500.0, RT2)

        # Logs
        eng.record_log("l-fw-1", T, "INFO", "started", RT, "tr-fw-1")
        eng.record_log("l-fw-2", T, "ERROR", "failed", RT, "tr-fw-1")

        # Traces
        eng.open_trace("tr-fw-1", T, "workflow-trace", RT)
        eng.open_trace("tr-fw-2", T, "bg-task", RT2)

        # Spans
        eng.add_span("sp-fw-1", "tr-fw-1", T, "step-a", RT)
        eng.add_span("sp-fw-2", "tr-fw-1", T, "step-b", RT, "sp-fw-1")
        eng.close_span("sp-fw-1", 50.0)
        eng.close_span("sp-fw-2", 30.0)

        # Error one trace
        eng.error_trace("tr-fw-1", 200.0)
        eng.close_trace("tr-fw-2", 100.0)

        # Anomaly
        eng.register_anomaly("an-fw-1", T, RT, "workflow failed",
                             AnomalySeverity.CRITICAL, "tr-fw-1")

        # Debug session linked to trace
        eng.open_debug_session("ds-fw-1", T, "ops-team", RT, "tr-fw-1")
        eng.investigate_session("ds-fw-1")

        # Detect violations
        violations = eng.detect_observability_violations(T)
        # stale_open_trace should NOT fire (trace is errored, not open)
        # critical_no_debug should NOT fire (debug session exists for tr-fw-1)
        assert not any(v.operation == "stale_open_trace" for v in violations)
        assert not any(v.operation == "critical_no_debug" for v in violations)

        # Snapshot
        snap = eng.observability_snapshot("snap-fw-1", T)
        assert snap.total_metrics == 2
        assert snap.total_logs == 2
        assert snap.total_traces == 2
        assert snap.total_spans == 2
        assert snap.total_anomalies == 1
        assert snap.total_debug_sessions == 1

        # Assessment
        a = eng.observability_assessment("a-fw-1", T)
        assert a.total_signals == 6  # 2 metrics + 2 logs + 2 traces
        assert a.trace_error_rate == 0.5

        # Resolve debug
        eng.resolve_session("ds-fw-1")

        # Closure report
        report = eng.closure_report("r-fw-1", T)
        assert report.total_metrics == 2
        assert report.total_debug_sessions == 1

        # State hash is deterministic
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


# =====================================================================
# 20. Batch / Stress
# =====================================================================


class TestBatchOperations:
    def test_many_tenants(self, env):
        _, eng = env
        for i in range(20):
            tid = f"tenant-{i}"
            _metric(eng, f"m-batch-{i}", tid)
            _trace(eng, f"tr-batch-{i}", tid)
        assert eng.metric_count == 20
        assert eng.trace_count == 20
        for i in range(20):
            assert len(eng.metrics_for_tenant(f"tenant-{i}")) == 1

    def test_many_spans_per_trace(self, env):
        _, eng = env
        _trace(eng, "tr-big")
        for i in range(50):
            eng.add_span(f"sp-big-{i}", "tr-big", T, f"step-{i}", RT)
        assert eng.get_trace("tr-big").span_count == 50
        assert len(eng.spans_for_trace("tr-big")) == 50

    def test_many_anomalies(self, env):
        _, eng = env
        for i in range(30):
            sev = AnomalySeverity.CRITICAL if i % 3 == 0 else AnomalySeverity.WARNING
            _anomaly(eng, f"an-batch-{i}", severity=sev)
        assert eng.anomaly_count == 30
        crits = eng.critical_anomalies(T)
        assert len(crits) == 10  # every 3rd

    def test_many_debug_sessions(self, env):
        _, eng = env
        for i in range(20):
            _debug(eng, f"ds-batch-{i}")
        assert eng.debug_session_count == 20


# =====================================================================
# 21. Assessment Rate Calculations
# =====================================================================


class TestAssessmentRates:
    def test_anomaly_rate_zero_signals(self, env):
        _, eng = env
        a = eng.observability_assessment("a-rate-1", T)
        assert a.anomaly_rate == 0.0

    def test_anomaly_rate_no_anomalies(self, env):
        _, eng = env
        _metric(eng)
        _log(eng)
        a = eng.observability_assessment("a-rate-2", T)
        assert a.anomaly_rate == 0.0

    def test_anomaly_rate_some(self, env):
        _, eng = env
        for i in range(10):
            _metric(eng, f"m-rate-{i}")
        for i in range(3):
            _anomaly(eng, f"an-rate-{i}")
        a = eng.observability_assessment("a-rate-3", T)
        # 3 anomalies / 10 signals = 0.3
        assert a.anomaly_rate == pytest.approx(0.3, abs=0.001)

    def test_trace_error_rate_mixed(self, env):
        _, eng = env
        for i in range(10):
            _trace(eng, f"tr-rate-{i}")
        for i in range(3):
            eng.error_trace(f"tr-rate-{i}")
        for i in range(3, 10):
            eng.close_trace(f"tr-rate-{i}")
        a = eng.observability_assessment("a-rate-4", T)
        assert a.trace_error_rate == pytest.approx(0.3, abs=0.001)

    def test_signals_include_metrics_logs_traces(self, env):
        _, eng = env
        _metric(eng, "m-s1")
        _metric(eng, "m-s2")
        _log(eng, "l-s1")
        _trace(eng, "tr-s1")
        a = eng.observability_assessment("a-rate-5", T)
        assert a.total_signals == 4


# =====================================================================
# 22. Violation Details
# =====================================================================


class TestViolationDetails:
    def test_stale_open_trace_reason(self, env):
        _, eng = env
        _trace(eng)
        _span(eng)
        eng.close_span("sp-1")
        vs = eng.detect_observability_violations(T)
        stale = [v for v in vs if v.operation == "stale_open_trace"]
        assert len(stale) == 1
        assert stale[0].reason == "trace is open but all spans are closed"
        assert "tr-1" not in stale[0].reason
        assert T not in stale[0].reason

    def test_critical_no_debug_reason(self, env):
        _, eng = env
        _anomaly(eng, severity=AnomalySeverity.CRITICAL)
        vs = eng.detect_observability_violations(T)
        cnd = [v for v in vs if v.operation == "critical_no_debug"]
        assert len(cnd) == 1
        assert cnd[0].reason == "critical anomaly has no debug session"
        assert "an-1" not in cnd[0].reason
        assert T not in cnd[0].reason

    def test_high_error_rate_reason(self, env):
        _, eng = env
        for i in range(5):
            _trace(eng, f"tr-hr-{i}")
            eng.error_trace(f"tr-hr-{i}")
        vs = eng.detect_observability_violations(T)
        her = [v for v in vs if v.operation == "high_trace_error_rate"]
        assert len(her) == 1
        assert her[0].reason == "trace error rate above threshold"
        assert T not in her[0].reason
        assert "tr-hr-0" not in her[0].reason

    def test_violation_detected_at_populated(self, env):
        _, eng = env
        _anomaly(eng, severity=AnomalySeverity.CRITICAL)
        vs = eng.detect_observability_violations(T)
        assert all(v.detected_at for v in vs)

    def test_violation_tenant_id(self, env):
        _, eng = env
        _anomaly(eng, severity=AnomalySeverity.CRITICAL)
        vs = eng.detect_observability_violations(T)
        assert all(v.tenant_id == T for v in vs)


class TestBoundedContracts:
    def test_duplicate_metric_error_is_bounded(self, env):
        _, eng = env
        _metric(eng, mid="metric-secret", tid="tenant-secret")

        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            _metric(eng, mid="metric-secret", tid="tenant-secret")

        message = str(excinfo.value)
        assert message == "duplicate metric_id"
        assert "metric-secret" not in message
        assert "tenant-secret" not in message

    def test_violation_reasons_are_bounded(self, env):
        _, eng = env
        _trace(eng, trid="trace-secret", tid="tenant-secret")
        _span(eng, sid="span-secret", trid="trace-secret", tid="tenant-secret")
        eng.close_span("span-secret")
        _anomaly(eng, aid="anomaly-secret", tid="tenant-secret", severity=AnomalySeverity.CRITICAL)
        for index in range(5):
            trace_id = f"rate-trace-{index}"
            _trace(eng, trid=trace_id, tid="tenant-secret")
            eng.error_trace(trace_id)

        violations = eng.detect_observability_violations("tenant-secret")
        reasons = {violation.operation: violation.reason for violation in violations}
        joined = " ".join(reasons.values())

        assert reasons["stale_open_trace"] == "trace is open but all spans are closed"
        assert reasons["critical_no_debug"] == "critical anomaly has no debug session"
        assert reasons["high_trace_error_rate"] == "trace error rate above threshold"
        assert "trace-secret" not in joined
        assert "anomaly-secret" not in joined
        assert "tenant-secret" not in joined
