"""Comprehensive tests for mcoi_runtime.contracts.observability_runtime.

Coverage targets:
  - All 6 enums: member count, values, lookup
  - All 10 frozen dataclasses: valid construction, frozen immutability,
    metadata as MappingProxyType, to_dict(), empty-string rejection,
    invalid-datetime rejection, non_negative_int / non_negative_float /
    unit_float validation, parametrized boundary tests
"""

from __future__ import annotations

import math
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.observability_runtime import (
    AnomalyRecord,
    AnomalySeverity,
    DebugDisposition,
    DebugSession,
    LogRecord,
    MetricRecord,
    ObservabilityAssessment,
    ObservabilityClosureReport,
    ObservabilityScope,
    ObservabilitySnapshot,
    ObservabilityViolation,
    SignalKind,
    SpanRecord,
    TraceRecord,
    TraceStatus,
    TelemetryStatus,
)

# ---------------------------------------------------------------------------
# Shared fixtures / factory helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T00:00:00Z"
TS_ALT = "2025-07-15T12:30:00+02:00"
TS_DATE_ONLY = "2025-06-01"  # valid in Python 3.11+


def _metric(**kw):
    defaults = dict(
        metric_id="m1", tenant_id="t1", metric_name="cpu",
        value=1.5, source_runtime="rt1",
        scope=ObservabilityScope.RUNTIME, recorded_at=TS,
    )
    defaults.update(kw)
    return MetricRecord(**defaults)


def _log(**kw):
    defaults = dict(
        log_id="l1", tenant_id="t1", level="INFO", message="hello",
        source_runtime="rt1", trace_id="tr1", logged_at=TS,
    )
    defaults.update(kw)
    return LogRecord(**defaults)


def _trace(**kw):
    defaults = dict(
        trace_id="tr1", tenant_id="t1", display_name="op",
        source_runtime="rt1", status=TraceStatus.OPEN,
        span_count=3, duration_ms=100.0, started_at=TS,
    )
    defaults.update(kw)
    return TraceRecord(**defaults)


def _span(**kw):
    defaults = dict(
        span_id="s1", trace_id="tr1", tenant_id="t1",
        display_name="span-op", source_runtime="rt1",
        parent_span_id="s0", status=TraceStatus.OPEN,
        duration_ms=50.0, started_at=TS,
    )
    defaults.update(kw)
    return SpanRecord(**defaults)


def _anomaly(**kw):
    defaults = dict(
        anomaly_id="a1", tenant_id="t1", source_runtime="rt1",
        description="spike", severity=AnomalySeverity.WARNING,
        trace_id="tr1", detected_at=TS,
    )
    defaults.update(kw)
    return AnomalyRecord(**defaults)


def _debug(**kw):
    defaults = dict(
        session_id="d1", tenant_id="t1", operator_ref="op1",
        target_runtime="rt1", disposition=DebugDisposition.OPEN,
        trace_id="tr1", created_at=TS,
    )
    defaults.update(kw)
    return DebugSession(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap1", tenant_id="t1",
        total_metrics=1, total_logs=2, total_traces=3,
        total_spans=4, total_anomalies=5,
        total_debug_sessions=6, total_violations=7,
        captured_at=TS,
    )
    defaults.update(kw)
    return ObservabilitySnapshot(**defaults)


def _violation(**kw):
    defaults = dict(
        violation_id="v1", tenant_id="t1",
        operation="write", reason="denied", detected_at=TS,
    )
    defaults.update(kw)
    return ObservabilityViolation(**defaults)


def _assessment(**kw):
    defaults = dict(
        assessment_id="as1", tenant_id="t1",
        total_signals=100, anomaly_rate=0.05,
        trace_error_rate=0.02, total_violations=3,
        assessed_at=TS,
    )
    defaults.update(kw)
    return ObservabilityAssessment(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="rpt1", tenant_id="t1",
        total_metrics=10, total_logs=20, total_traces=5,
        total_spans=15, total_anomalies=2,
        total_debug_sessions=1, created_at=TS,
    )
    defaults.update(kw)
    return ObservabilityClosureReport(**defaults)


# ===================================================================
# PART 1 — Enum tests
# ===================================================================


class TestTelemetryStatus:
    def test_member_count(self):
        assert len(TelemetryStatus) == 4

    @pytest.mark.parametrize("name,value", [
        ("ACTIVE", "active"), ("BUFFERED", "buffered"),
        ("FLUSHED", "flushed"), ("DROPPED", "dropped"),
    ])
    def test_values(self, name, value):
        assert TelemetryStatus[name].value == value

    @pytest.mark.parametrize("value", ["active", "buffered", "flushed", "dropped"])
    def test_lookup_by_value(self, value):
        assert TelemetryStatus(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            TelemetryStatus("nonexistent")


class TestSignalKind:
    def test_member_count(self):
        assert len(SignalKind) == 5

    @pytest.mark.parametrize("name,value", [
        ("METRIC", "metric"), ("LOG", "log"), ("TRACE", "trace"),
        ("SPAN", "span"), ("ANOMALY", "anomaly"),
    ])
    def test_values(self, name, value):
        assert SignalKind[name].value == value

    @pytest.mark.parametrize("value", ["metric", "log", "trace", "span", "anomaly"])
    def test_lookup_by_value(self, value):
        assert SignalKind(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            SignalKind("nonexistent")


class TestTraceStatus:
    def test_member_count(self):
        assert len(TraceStatus) == 4

    @pytest.mark.parametrize("name,value", [
        ("OPEN", "open"), ("CLOSED", "closed"),
        ("ERROR", "error"), ("TIMEOUT", "timeout"),
    ])
    def test_values(self, name, value):
        assert TraceStatus[name].value == value

    @pytest.mark.parametrize("value", ["open", "closed", "error", "timeout"])
    def test_lookup_by_value(self, value):
        assert TraceStatus(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            TraceStatus("nonexistent")


class TestAnomalySeverity:
    def test_member_count(self):
        assert len(AnomalySeverity) == 4

    @pytest.mark.parametrize("name,value", [
        ("INFO", "info"), ("WARNING", "warning"),
        ("ERROR", "error"), ("CRITICAL", "critical"),
    ])
    def test_values(self, name, value):
        assert AnomalySeverity[name].value == value

    @pytest.mark.parametrize("value", ["info", "warning", "error", "critical"])
    def test_lookup_by_value(self, value):
        assert AnomalySeverity(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            AnomalySeverity("nonexistent")


class TestDebugDisposition:
    def test_member_count(self):
        assert len(DebugDisposition) == 4

    @pytest.mark.parametrize("name,value", [
        ("OPEN", "open"), ("INVESTIGATING", "investigating"),
        ("RESOLVED", "resolved"), ("ABANDONED", "abandoned"),
    ])
    def test_values(self, name, value):
        assert DebugDisposition[name].value == value

    @pytest.mark.parametrize("value", ["open", "investigating", "resolved", "abandoned"])
    def test_lookup_by_value(self, value):
        assert DebugDisposition(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            DebugDisposition("nonexistent")


class TestObservabilityScope:
    def test_member_count(self):
        assert len(ObservabilityScope) == 6

    @pytest.mark.parametrize("name,value", [
        ("TENANT", "tenant"), ("WORKSPACE", "workspace"),
        ("RUNTIME", "runtime"), ("SERVICE", "service"),
        ("GLOBAL", "global"), ("ENDPOINT", "endpoint"),
    ])
    def test_values(self, name, value):
        assert ObservabilityScope[name].value == value

    @pytest.mark.parametrize("value", [
        "tenant", "workspace", "runtime", "service", "global", "endpoint",
    ])
    def test_lookup_by_value(self, value):
        assert ObservabilityScope(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            ObservabilityScope("nonexistent")


# ===================================================================
# PART 2 — MetricRecord
# ===================================================================


class TestMetricRecord:
    def test_valid_construction(self):
        m = _metric()
        assert m.metric_id == "m1"
        assert m.tenant_id == "t1"
        assert m.metric_name == "cpu"
        assert m.value == 1.5
        assert m.source_runtime == "rt1"
        assert m.scope is ObservabilityScope.RUNTIME
        assert m.recorded_at == TS

    def test_metadata_frozen(self):
        m = _metric(metadata={"k": "v"})
        assert isinstance(m.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            m.metadata["k2"] = "v2"

    def test_to_dict_preserves_enum(self):
        d = _metric().to_dict()
        assert d["scope"] is ObservabilityScope.RUNTIME

    def test_frozen_immutability(self):
        m = _metric()
        with pytest.raises(AttributeError):
            m.metric_id = "x"

    @pytest.mark.parametrize("field", [
        "metric_id", "tenant_id", "metric_name", "source_runtime",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _metric(**{field: ""})

    @pytest.mark.parametrize("field", [
        "metric_id", "tenant_id", "metric_name", "source_runtime",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _metric(**{field: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _metric(recorded_at="not-a-date")

    def test_date_only_accepted(self):
        m = _metric(recorded_at=TS_DATE_ONLY)
        assert m.recorded_at == TS_DATE_ONLY

    @pytest.mark.parametrize("val", [-1.0, -0.001])
    def test_negative_value_rejected(self, val):
        with pytest.raises(ValueError):
            _metric(value=val)

    def test_zero_value_accepted(self):
        m = _metric(value=0.0)
        assert m.value == 0.0

    @pytest.mark.parametrize("val", [float("inf"), float("-inf"), float("nan")])
    def test_non_finite_value_rejected(self, val):
        with pytest.raises(ValueError):
            _metric(value=val)

    def test_int_value_coerced(self):
        m = _metric(value=5)
        assert m.value == 5.0

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError):
            _metric(scope="runtime")

    def test_all_scopes_accepted(self):
        for s in ObservabilityScope:
            m = _metric(scope=s)
            assert m.scope is s

    def test_alt_datetime_accepted(self):
        m = _metric(recorded_at=TS_ALT)
        assert m.recorded_at == TS_ALT


# ===================================================================
# PART 3 — LogRecord
# ===================================================================


class TestLogRecord:
    def test_valid_construction(self):
        r = _log()
        assert r.log_id == "l1"
        assert r.level == "INFO"
        assert r.message == "hello"

    def test_metadata_frozen(self):
        r = _log(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _log().to_dict()
        assert d["log_id"] == "l1"

    def test_frozen_immutability(self):
        r = _log()
        with pytest.raises(AttributeError):
            r.log_id = "x"

    @pytest.mark.parametrize("field", [
        "log_id", "tenant_id", "level", "message",
        "source_runtime", "trace_id",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _log(**{field: ""})

    @pytest.mark.parametrize("field", [
        "log_id", "tenant_id", "level", "message",
        "source_runtime", "trace_id",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _log(**{field: "  "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _log(logged_at="bad")

    def test_date_only_accepted(self):
        r = _log(logged_at=TS_DATE_ONLY)
        assert r.logged_at == TS_DATE_ONLY


# ===================================================================
# PART 4 — TraceRecord
# ===================================================================


class TestTraceRecord:
    def test_valid_construction(self):
        t = _trace()
        assert t.trace_id == "tr1"
        assert t.span_count == 3
        assert t.duration_ms == 100.0
        assert t.status is TraceStatus.OPEN

    def test_metadata_frozen(self):
        t = _trace(metadata={"x": "y"})
        assert isinstance(t.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _trace().to_dict()
        assert d["status"] is TraceStatus.OPEN

    def test_frozen_immutability(self):
        t = _trace()
        with pytest.raises(AttributeError):
            t.trace_id = "x"

    @pytest.mark.parametrize("field", [
        "trace_id", "tenant_id", "display_name", "source_runtime",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _trace(**{field: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _trace(started_at="bad")

    def test_date_only_accepted(self):
        t = _trace(started_at=TS_DATE_ONLY)
        assert t.started_at == TS_DATE_ONLY

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _trace(status="open")

    def test_negative_span_count_rejected(self):
        with pytest.raises(ValueError):
            _trace(span_count=-1)

    def test_zero_span_count_accepted(self):
        t = _trace(span_count=0)
        assert t.span_count == 0

    def test_float_span_count_rejected(self):
        with pytest.raises(ValueError):
            _trace(span_count=1.5)

    def test_bool_span_count_rejected(self):
        with pytest.raises(ValueError):
            _trace(span_count=True)

    @pytest.mark.parametrize("val", [-1.0, -0.001])
    def test_negative_duration_rejected(self, val):
        with pytest.raises(ValueError):
            _trace(duration_ms=val)

    def test_zero_duration_accepted(self):
        t = _trace(duration_ms=0.0)
        assert t.duration_ms == 0.0

    @pytest.mark.parametrize("val", [float("inf"), float("-inf"), float("nan")])
    def test_non_finite_duration_rejected(self, val):
        with pytest.raises(ValueError):
            _trace(duration_ms=val)

    def test_all_trace_statuses(self):
        for s in TraceStatus:
            t = _trace(status=s)
            assert t.status is s


# ===================================================================
# PART 5 — SpanRecord
# ===================================================================


class TestSpanRecord:
    def test_valid_construction(self):
        s = _span()
        assert s.span_id == "s1"
        assert s.parent_span_id == "s0"
        assert s.duration_ms == 50.0

    def test_metadata_frozen(self):
        s = _span(metadata={"p": "q"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _span().to_dict()
        assert d["status"] is TraceStatus.OPEN

    def test_frozen_immutability(self):
        s = _span()
        with pytest.raises(AttributeError):
            s.span_id = "x"

    @pytest.mark.parametrize("field", [
        "span_id", "trace_id", "tenant_id", "display_name",
        "source_runtime", "parent_span_id",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _span(**{field: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _span(started_at="bad")

    def test_date_only_accepted(self):
        s = _span(started_at=TS_DATE_ONLY)
        assert s.started_at == TS_DATE_ONLY

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _span(status="open")

    @pytest.mark.parametrize("val", [-1.0, -0.001])
    def test_negative_duration_rejected(self, val):
        with pytest.raises(ValueError):
            _span(duration_ms=val)

    def test_zero_duration_accepted(self):
        s = _span(duration_ms=0.0)
        assert s.duration_ms == 0.0

    @pytest.mark.parametrize("val", [float("inf"), float("-inf"), float("nan")])
    def test_non_finite_duration_rejected(self, val):
        with pytest.raises(ValueError):
            _span(duration_ms=val)


# ===================================================================
# PART 6 — AnomalyRecord
# ===================================================================


class TestAnomalyRecord:
    def test_valid_construction(self):
        a = _anomaly()
        assert a.anomaly_id == "a1"
        assert a.severity is AnomalySeverity.WARNING

    def test_metadata_frozen(self):
        a = _anomaly(metadata={"sev": "high"})
        assert isinstance(a.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _anomaly().to_dict()
        assert d["severity"] is AnomalySeverity.WARNING

    def test_frozen_immutability(self):
        a = _anomaly()
        with pytest.raises(AttributeError):
            a.anomaly_id = "x"

    @pytest.mark.parametrize("field", [
        "anomaly_id", "tenant_id", "source_runtime",
        "description", "trace_id",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _anomaly(**{field: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _anomaly(detected_at="bad")

    def test_date_only_accepted(self):
        a = _anomaly(detected_at=TS_DATE_ONLY)
        assert a.detected_at == TS_DATE_ONLY

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError):
            _anomaly(severity="warning")

    def test_all_severities_accepted(self):
        for s in AnomalySeverity:
            a = _anomaly(severity=s)
            assert a.severity is s


# ===================================================================
# PART 7 — DebugSession
# ===================================================================


class TestDebugSession:
    def test_valid_construction(self):
        d = _debug()
        assert d.session_id == "d1"
        assert d.disposition is DebugDisposition.OPEN

    def test_metadata_frozen(self):
        d = _debug(metadata={"dbg": 1})
        assert isinstance(d.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        data = _debug().to_dict()
        assert data["disposition"] is DebugDisposition.OPEN

    def test_frozen_immutability(self):
        d = _debug()
        with pytest.raises(AttributeError):
            d.session_id = "x"

    @pytest.mark.parametrize("field", [
        "session_id", "tenant_id", "operator_ref",
        "target_runtime", "trace_id",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _debug(**{field: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _debug(created_at="bad")

    def test_date_only_accepted(self):
        d = _debug(created_at=TS_DATE_ONLY)
        assert d.created_at == TS_DATE_ONLY

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            _debug(disposition="open")

    def test_all_dispositions_accepted(self):
        for disp in DebugDisposition:
            d = _debug(disposition=disp)
            assert d.disposition is disp


# ===================================================================
# PART 8 — ObservabilitySnapshot
# ===================================================================


class TestObservabilitySnapshot:
    def test_valid_construction(self):
        s = _snapshot()
        assert s.snapshot_id == "snap1"
        assert s.total_metrics == 1
        assert s.total_violations == 7

    def test_metadata_frozen(self):
        s = _snapshot(metadata={"snap": True})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _snapshot().to_dict()
        assert d["snapshot_id"] == "snap1"
        assert d["total_metrics"] == 1

    def test_frozen_immutability(self):
        s = _snapshot()
        with pytest.raises(AttributeError):
            s.snapshot_id = "x"

    @pytest.mark.parametrize("field", ["snapshot_id", "tenant_id"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad")

    def test_date_only_accepted(self):
        s = _snapshot(captured_at=TS_DATE_ONLY)
        assert s.captured_at == TS_DATE_ONLY

    @pytest.mark.parametrize("field", [
        "total_metrics", "total_logs", "total_traces", "total_spans",
        "total_anomalies", "total_debug_sessions", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_metrics", "total_logs", "total_traces", "total_spans",
        "total_anomalies", "total_debug_sessions", "total_violations",
    ])
    def test_zero_int_accepted(self, field):
        s = _snapshot(**{field: 0})
        assert getattr(s, field) == 0

    @pytest.mark.parametrize("field", [
        "total_metrics", "total_logs", "total_traces", "total_spans",
        "total_anomalies", "total_debug_sessions", "total_violations",
    ])
    def test_float_int_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: 1.5})

    @pytest.mark.parametrize("field", [
        "total_metrics", "total_logs", "total_traces", "total_spans",
        "total_anomalies", "total_debug_sessions", "total_violations",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: True})


# ===================================================================
# PART 9 — ObservabilityViolation
# ===================================================================


class TestObservabilityViolation:
    def test_valid_construction(self):
        v = _violation()
        assert v.violation_id == "v1"
        assert v.operation == "write"
        assert v.reason == "denied"

    def test_metadata_frozen(self):
        v = _violation(metadata={"v": 1})
        assert isinstance(v.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _violation().to_dict()
        assert d["violation_id"] == "v1"

    def test_frozen_immutability(self):
        v = _violation()
        with pytest.raises(AttributeError):
            v.violation_id = "x"

    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _violation(**{field: ""})

    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _violation(**{field: "  "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _violation(detected_at="bad")

    def test_date_only_accepted(self):
        v = _violation(detected_at=TS_DATE_ONLY)
        assert v.detected_at == TS_DATE_ONLY


# ===================================================================
# PART 10 — ObservabilityAssessment
# ===================================================================


class TestObservabilityAssessment:
    def test_valid_construction(self):
        a = _assessment()
        assert a.assessment_id == "as1"
        assert a.anomaly_rate == 0.05
        assert a.trace_error_rate == 0.02

    def test_metadata_frozen(self):
        a = _assessment(metadata={"assess": True})
        assert isinstance(a.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _assessment().to_dict()
        assert d["assessment_id"] == "as1"

    def test_frozen_immutability(self):
        a = _assessment()
        with pytest.raises(AttributeError):
            a.assessment_id = "x"

    @pytest.mark.parametrize("field", ["assessment_id", "tenant_id"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _assessment(assessed_at="bad")

    def test_date_only_accepted(self):
        a = _assessment(assessed_at=TS_DATE_ONLY)
        assert a.assessed_at == TS_DATE_ONLY

    # --- non_negative_int fields ---

    @pytest.mark.parametrize("field", ["total_signals", "total_violations"])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: -1})

    @pytest.mark.parametrize("field", ["total_signals", "total_violations"])
    def test_zero_int_accepted(self, field):
        a = _assessment(**{field: 0})
        assert getattr(a, field) == 0

    @pytest.mark.parametrize("field", ["total_signals", "total_violations"])
    def test_float_int_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: 1.5})

    @pytest.mark.parametrize("field", ["total_signals", "total_violations"])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: True})

    # --- unit_float fields ---

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_zero(self, field):
        a = _assessment(**{field: 0.0})
        assert getattr(a, field) == 0.0

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_one(self, field):
        a = _assessment(**{field: 1.0})
        assert getattr(a, field) == 1.0

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_mid(self, field):
        a = _assessment(**{field: 0.5})
        assert getattr(a, field) == 0.5

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_negative_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: -0.01})

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_above_one_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: 1.01})

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_inf_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: float("inf")})

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_nan_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: float("nan")})

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_bool_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: True})

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_int_zero_accepted(self, field):
        a = _assessment(**{field: 0})
        assert getattr(a, field) == 0.0

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_unit_float_int_one_accepted(self, field):
        a = _assessment(**{field: 1})
        assert getattr(a, field) == 1.0


# ===================================================================
# PART 11 — ObservabilityClosureReport
# ===================================================================


class TestObservabilityClosureReport:
    def test_valid_construction(self):
        c = _closure()
        assert c.report_id == "rpt1"
        assert c.total_metrics == 10

    def test_metadata_frozen(self):
        c = _closure(metadata={"final": True})
        assert isinstance(c.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _closure().to_dict()
        assert d["report_id"] == "rpt1"

    def test_frozen_immutability(self):
        c = _closure()
        with pytest.raises(AttributeError):
            c.report_id = "x"

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: ""})

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: "  "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _closure(created_at="bad")

    def test_date_only_accepted(self):
        c = _closure(created_at=TS_DATE_ONLY)
        assert c.created_at == TS_DATE_ONLY

    @pytest.mark.parametrize("field", [
        "total_metrics", "total_logs", "total_traces", "total_spans",
        "total_anomalies", "total_debug_sessions",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_metrics", "total_logs", "total_traces", "total_spans",
        "total_anomalies", "total_debug_sessions",
    ])
    def test_zero_int_accepted(self, field):
        c = _closure(**{field: 0})
        assert getattr(c, field) == 0

    @pytest.mark.parametrize("field", [
        "total_metrics", "total_logs", "total_traces", "total_spans",
        "total_anomalies", "total_debug_sessions",
    ])
    def test_float_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: 1.5})

    @pytest.mark.parametrize("field", [
        "total_metrics", "total_logs", "total_traces", "total_spans",
        "total_anomalies", "total_debug_sessions",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: True})


# ===================================================================
# PART 12 — Parametrized boundary tests (cross-cutting)
# ===================================================================


class TestNonNegativeFloatBoundaries:
    """Boundary tests for require_non_negative_float fields."""

    @pytest.mark.parametrize("factory,field", [
        (_metric, "value"),
        (_trace, "duration_ms"),
        (_span, "duration_ms"),
    ])
    def test_exact_zero(self, factory, field):
        obj = factory(**{field: 0.0})
        assert getattr(obj, field) == 0.0

    @pytest.mark.parametrize("factory,field", [
        (_metric, "value"),
        (_trace, "duration_ms"),
        (_span, "duration_ms"),
    ])
    def test_small_positive(self, factory, field):
        obj = factory(**{field: 1e-15})
        assert getattr(obj, field) == pytest.approx(1e-15)

    @pytest.mark.parametrize("factory,field", [
        (_metric, "value"),
        (_trace, "duration_ms"),
        (_span, "duration_ms"),
    ])
    def test_small_negative_rejected(self, factory, field):
        with pytest.raises(ValueError):
            factory(**{field: -1e-15})

    @pytest.mark.parametrize("factory,field", [
        (_metric, "value"),
        (_trace, "duration_ms"),
        (_span, "duration_ms"),
    ])
    def test_large_positive(self, factory, field):
        obj = factory(**{field: 1e12})
        assert getattr(obj, field) == 1e12

    @pytest.mark.parametrize("factory,field", [
        (_metric, "value"),
        (_trace, "duration_ms"),
        (_span, "duration_ms"),
    ])
    def test_bool_rejected(self, factory, field):
        with pytest.raises(ValueError):
            factory(**{field: True})

    @pytest.mark.parametrize("factory,field", [
        (_metric, "value"),
        (_trace, "duration_ms"),
        (_span, "duration_ms"),
    ])
    def test_string_rejected(self, factory, field):
        with pytest.raises(ValueError):
            factory(**{field: "1.0"})


class TestUnitFloatBoundaries:
    """Boundary tests for require_unit_float fields."""

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    @pytest.mark.parametrize("val", [0.0, 0.5, 1.0])
    def test_valid_range(self, field, val):
        a = _assessment(**{field: val})
        assert getattr(a, field) == val

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    @pytest.mark.parametrize("val", [-0.001, -1.0, 1.001, 2.0])
    def test_out_of_range_rejected(self, field, val):
        with pytest.raises(ValueError):
            _assessment(**{field: val})

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    @pytest.mark.parametrize("val", [float("inf"), float("-inf"), float("nan")])
    def test_non_finite_rejected(self, field, val):
        with pytest.raises(ValueError):
            _assessment(**{field: val})

    @pytest.mark.parametrize("field", ["anomaly_rate", "trace_error_rate"])
    def test_string_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: "0.5"})


class TestNonNegativeIntBoundaries:
    """Boundary tests for require_non_negative_int fields."""

    SNAPSHOT_INT_FIELDS = [
        "total_metrics", "total_logs", "total_traces", "total_spans",
        "total_anomalies", "total_debug_sessions", "total_violations",
    ]

    @pytest.mark.parametrize("field", SNAPSHOT_INT_FIELDS)
    def test_large_positive(self, field):
        s = _snapshot(**{field: 999999})
        assert getattr(s, field) == 999999

    @pytest.mark.parametrize("field", SNAPSHOT_INT_FIELDS)
    def test_string_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: "1"})

    @pytest.mark.parametrize("field", SNAPSHOT_INT_FIELDS)
    def test_none_rejected(self, field):
        with pytest.raises((ValueError, TypeError)):
            _snapshot(**{field: None})


class TestMetadataDeepFreeze:
    """Ensure nested metadata structures are deeply frozen."""

    def test_nested_dict_frozen(self):
        m = _metric(metadata={"outer": {"inner": "val"}})
        assert isinstance(m.metadata["outer"], MappingProxyType)

    def test_nested_list_becomes_tuple(self):
        m = _metric(metadata={"items": [1, 2, 3]})
        assert isinstance(m.metadata["items"], tuple)
        assert m.metadata["items"] == (1, 2, 3)

    def test_empty_metadata_is_mapping_proxy(self):
        m = _metric()
        assert isinstance(m.metadata, MappingProxyType)
        assert len(m.metadata) == 0


class TestToDictCompleteness:
    """Ensure to_dict returns all fields."""

    def test_metric_to_dict_keys(self):
        d = _metric().to_dict()
        expected = {
            "metric_id", "tenant_id", "metric_name", "value",
            "source_runtime", "scope", "recorded_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_log_to_dict_keys(self):
        d = _log().to_dict()
        expected = {
            "log_id", "tenant_id", "level", "message",
            "source_runtime", "trace_id", "logged_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_trace_to_dict_keys(self):
        d = _trace().to_dict()
        expected = {
            "trace_id", "tenant_id", "display_name", "source_runtime",
            "status", "span_count", "duration_ms", "started_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_span_to_dict_keys(self):
        d = _span().to_dict()
        expected = {
            "span_id", "trace_id", "tenant_id", "display_name",
            "source_runtime", "parent_span_id", "status",
            "duration_ms", "started_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_anomaly_to_dict_keys(self):
        d = _anomaly().to_dict()
        expected = {
            "anomaly_id", "tenant_id", "source_runtime",
            "description", "severity", "trace_id",
            "detected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_debug_to_dict_keys(self):
        d = _debug().to_dict()
        expected = {
            "session_id", "tenant_id", "operator_ref",
            "target_runtime", "disposition", "trace_id",
            "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_snapshot_to_dict_keys(self):
        d = _snapshot().to_dict()
        expected = {
            "snapshot_id", "tenant_id",
            "total_metrics", "total_logs", "total_traces",
            "total_spans", "total_anomalies",
            "total_debug_sessions", "total_violations",
            "captured_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_violation_to_dict_keys(self):
        d = _violation().to_dict()
        expected = {
            "violation_id", "tenant_id", "operation",
            "reason", "detected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_assessment_to_dict_keys(self):
        d = _assessment().to_dict()
        expected = {
            "assessment_id", "tenant_id", "total_signals",
            "anomaly_rate", "trace_error_rate",
            "total_violations", "assessed_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_closure_to_dict_keys(self):
        d = _closure().to_dict()
        expected = {
            "report_id", "tenant_id",
            "total_metrics", "total_logs", "total_traces",
            "total_spans", "total_anomalies",
            "total_debug_sessions", "created_at", "metadata",
        }
        assert set(d.keys()) == expected


class TestFrozenImmutabilityAllDataclasses:
    """One frozen-immutability test per dataclass to ensure
    every class is truly frozen."""

    def test_metric_frozen(self):
        with pytest.raises(AttributeError):
            _metric().tenant_id = "x"

    def test_log_frozen(self):
        with pytest.raises(AttributeError):
            _log().tenant_id = "x"

    def test_trace_frozen(self):
        with pytest.raises(AttributeError):
            _trace().tenant_id = "x"

    def test_span_frozen(self):
        with pytest.raises(AttributeError):
            _span().tenant_id = "x"

    def test_anomaly_frozen(self):
        with pytest.raises(AttributeError):
            _anomaly().tenant_id = "x"

    def test_debug_frozen(self):
        with pytest.raises(AttributeError):
            _debug().tenant_id = "x"

    def test_snapshot_frozen(self):
        with pytest.raises(AttributeError):
            _snapshot().tenant_id = "x"

    def test_violation_frozen(self):
        with pytest.raises(AttributeError):
            _violation().tenant_id = "x"

    def test_assessment_frozen(self):
        with pytest.raises(AttributeError):
            _assessment().tenant_id = "x"

    def test_closure_frozen(self):
        with pytest.raises(AttributeError):
            _closure().tenant_id = "x"
