"""Purpose: observability / telemetry / debug runtime engine.
Governance scope: ingesting metrics/logs/traces/spans, registering anomalies,
    managing debug sessions, aggregating by tenant/runtime/scope,
    detecting violations, producing snapshots.
Dependencies: observability_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Cross-tenant observability access is denied fail-closed.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.observability_runtime import (
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
    TelemetryStatus,
    TraceRecord,
    TraceStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-obs", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_TRACE_TERMINAL = frozenset({TraceStatus.CLOSED, TraceStatus.ERROR, TraceStatus.TIMEOUT})
_DEBUG_TERMINAL = frozenset({DebugDisposition.RESOLVED, DebugDisposition.ABANDONED})


class ObservabilityRuntimeEngine:
    """Observability / telemetry / debug runtime engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._metrics: dict[str, MetricRecord] = {}
        self._logs: dict[str, LogRecord] = {}
        self._traces: dict[str, TraceRecord] = {}
        self._spans: dict[str, SpanRecord] = {}
        self._anomalies: dict[str, AnomalyRecord] = {}
        self._debug_sessions: dict[str, DebugSession] = {}
        self._violations: dict[str, ObservabilityViolation] = {}
        self._assessments: dict[str, ObservabilityAssessment] = {}

    # -- Properties ----------------------------------------------------------

    @property
    def metric_count(self) -> int:
        return len(self._metrics)

    @property
    def log_count(self) -> int:
        return len(self._logs)

    @property
    def trace_count(self) -> int:
        return len(self._traces)

    @property
    def span_count(self) -> int:
        return len(self._spans)

    @property
    def anomaly_count(self) -> int:
        return len(self._anomalies)

    @property
    def debug_session_count(self) -> int:
        return len(self._debug_sessions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    # -- Metrics -------------------------------------------------------------

    def record_metric(
        self,
        metric_id: str,
        tenant_id: str,
        metric_name: str,
        value: float,
        source_runtime: str,
        scope: ObservabilityScope = ObservabilityScope.RUNTIME,
    ) -> MetricRecord:
        if metric_id in self._metrics:
            raise RuntimeCoreInvariantError("duplicate metric_id")
        now = _now_iso()
        metric = MetricRecord(
            metric_id=metric_id, tenant_id=tenant_id, metric_name=metric_name,
            value=value, source_runtime=source_runtime, scope=scope,
            recorded_at=now,
        )
        self._metrics[metric_id] = metric
        _emit(self._events, "record_metric", {"metric_id": metric_id, "name": metric_name}, metric_id)
        return metric

    def get_metric(self, metric_id: str) -> MetricRecord:
        if metric_id not in self._metrics:
            raise RuntimeCoreInvariantError("unknown metric_id")
        return self._metrics[metric_id]

    def metrics_for_tenant(self, tenant_id: str) -> tuple[MetricRecord, ...]:
        return tuple(m for m in self._metrics.values() if m.tenant_id == tenant_id)

    def metrics_for_runtime(self, tenant_id: str, source_runtime: str) -> tuple[MetricRecord, ...]:
        return tuple(m for m in self._metrics.values() if m.tenant_id == tenant_id and m.source_runtime == source_runtime)

    # -- Logs ----------------------------------------------------------------

    def record_log(
        self,
        log_id: str,
        tenant_id: str,
        level: str,
        message: str,
        source_runtime: str,
        trace_id: str = "none",
    ) -> LogRecord:
        if log_id in self._logs:
            raise RuntimeCoreInvariantError("duplicate log_id")
        now = _now_iso()
        log = LogRecord(
            log_id=log_id, tenant_id=tenant_id, level=level,
            message=message, source_runtime=source_runtime,
            trace_id=trace_id, logged_at=now,
        )
        self._logs[log_id] = log
        _emit(self._events, "record_log", {"log_id": log_id, "level": level}, log_id)
        return log

    def get_log(self, log_id: str) -> LogRecord:
        if log_id not in self._logs:
            raise RuntimeCoreInvariantError("unknown log_id")
        return self._logs[log_id]

    def logs_for_tenant(self, tenant_id: str) -> tuple[LogRecord, ...]:
        return tuple(l for l in self._logs.values() if l.tenant_id == tenant_id)

    def logs_for_trace(self, trace_id: str) -> tuple[LogRecord, ...]:
        return tuple(l for l in self._logs.values() if l.trace_id == trace_id)

    # -- Traces --------------------------------------------------------------

    def open_trace(
        self,
        trace_id: str,
        tenant_id: str,
        display_name: str,
        source_runtime: str,
    ) -> TraceRecord:
        if trace_id in self._traces:
            raise RuntimeCoreInvariantError("duplicate trace_id")
        now = _now_iso()
        trace = TraceRecord(
            trace_id=trace_id, tenant_id=tenant_id, display_name=display_name,
            source_runtime=source_runtime, status=TraceStatus.OPEN,
            span_count=0, duration_ms=0.0, started_at=now,
        )
        self._traces[trace_id] = trace
        _emit(self._events, "open_trace", {"trace_id": trace_id}, trace_id)
        return trace

    def close_trace(self, trace_id: str, duration_ms: float = 0.0) -> TraceRecord:
        trace = self._get_trace(trace_id)
        if trace.status in _TRACE_TERMINAL:
            raise RuntimeCoreInvariantError("trace is in terminal state")
        now = _now_iso()
        updated = TraceRecord(
            trace_id=trace.trace_id, tenant_id=trace.tenant_id,
            display_name=trace.display_name, source_runtime=trace.source_runtime,
            status=TraceStatus.CLOSED, span_count=trace.span_count,
            duration_ms=duration_ms, started_at=trace.started_at,
        )
        self._traces[trace_id] = updated
        _emit(self._events, "close_trace", {"trace_id": trace_id, "duration_ms": duration_ms}, trace_id)
        return updated

    def error_trace(self, trace_id: str, duration_ms: float = 0.0) -> TraceRecord:
        trace = self._get_trace(trace_id)
        if trace.status in _TRACE_TERMINAL:
            raise RuntimeCoreInvariantError("trace is in terminal state")
        now = _now_iso()
        updated = TraceRecord(
            trace_id=trace.trace_id, tenant_id=trace.tenant_id,
            display_name=trace.display_name, source_runtime=trace.source_runtime,
            status=TraceStatus.ERROR, span_count=trace.span_count,
            duration_ms=duration_ms, started_at=trace.started_at,
        )
        self._traces[trace_id] = updated
        _emit(self._events, "error_trace", {"trace_id": trace_id}, trace_id)
        return updated

    def timeout_trace(self, trace_id: str, duration_ms: float = 0.0) -> TraceRecord:
        trace = self._get_trace(trace_id)
        if trace.status in _TRACE_TERMINAL:
            raise RuntimeCoreInvariantError("trace is in terminal state")
        updated = TraceRecord(
            trace_id=trace.trace_id, tenant_id=trace.tenant_id,
            display_name=trace.display_name, source_runtime=trace.source_runtime,
            status=TraceStatus.TIMEOUT, span_count=trace.span_count,
            duration_ms=duration_ms, started_at=trace.started_at,
        )
        self._traces[trace_id] = updated
        _emit(self._events, "timeout_trace", {"trace_id": trace_id}, trace_id)
        return updated

    def _get_trace(self, trace_id: str) -> TraceRecord:
        if trace_id not in self._traces:
            raise RuntimeCoreInvariantError("unknown trace_id")
        return self._traces[trace_id]

    def get_trace(self, trace_id: str) -> TraceRecord:
        return self._get_trace(trace_id)

    def traces_for_tenant(self, tenant_id: str) -> tuple[TraceRecord, ...]:
        return tuple(t for t in self._traces.values() if t.tenant_id == tenant_id)

    # -- Spans ---------------------------------------------------------------

    def add_span(
        self,
        span_id: str,
        trace_id: str,
        tenant_id: str,
        display_name: str,
        source_runtime: str,
        parent_span_id: str = "root",
        duration_ms: float = 0.0,
    ) -> SpanRecord:
        if span_id in self._spans:
            raise RuntimeCoreInvariantError("duplicate span_id")
        if trace_id not in self._traces:
            raise RuntimeCoreInvariantError("unknown trace_id")
        trace = self._traces[trace_id]
        if trace.tenant_id != tenant_id:
            raise RuntimeCoreInvariantError("cross-tenant span access denied")
        now = _now_iso()
        span = SpanRecord(
            span_id=span_id, trace_id=trace_id, tenant_id=tenant_id,
            display_name=display_name, source_runtime=source_runtime,
            parent_span_id=parent_span_id, status=TraceStatus.OPEN,
            duration_ms=duration_ms, started_at=now,
        )
        self._spans[span_id] = span
        # Increment trace span_count
        updated_trace = TraceRecord(
            trace_id=trace.trace_id, tenant_id=trace.tenant_id,
            display_name=trace.display_name, source_runtime=trace.source_runtime,
            status=trace.status, span_count=trace.span_count + 1,
            duration_ms=trace.duration_ms, started_at=trace.started_at,
        )
        self._traces[trace_id] = updated_trace
        _emit(self._events, "add_span", {"span_id": span_id, "trace_id": trace_id}, span_id)
        return span

    def close_span(self, span_id: str, duration_ms: float = 0.0) -> SpanRecord:
        if span_id not in self._spans:
            raise RuntimeCoreInvariantError("unknown span_id")
        span = self._spans[span_id]
        if span.status in _TRACE_TERMINAL:
            raise RuntimeCoreInvariantError("span is in terminal state")
        updated = SpanRecord(
            span_id=span.span_id, trace_id=span.trace_id, tenant_id=span.tenant_id,
            display_name=span.display_name, source_runtime=span.source_runtime,
            parent_span_id=span.parent_span_id, status=TraceStatus.CLOSED,
            duration_ms=duration_ms, started_at=span.started_at,
        )
        self._spans[span_id] = updated
        _emit(self._events, "close_span", {"span_id": span_id}, span_id)
        return updated

    def spans_for_trace(self, trace_id: str) -> tuple[SpanRecord, ...]:
        return tuple(s for s in self._spans.values() if s.trace_id == trace_id)

    # -- Anomalies -----------------------------------------------------------

    def register_anomaly(
        self,
        anomaly_id: str,
        tenant_id: str,
        source_runtime: str,
        description: str,
        severity: AnomalySeverity = AnomalySeverity.WARNING,
        trace_id: str = "none",
    ) -> AnomalyRecord:
        if anomaly_id in self._anomalies:
            raise RuntimeCoreInvariantError("duplicate anomaly_id")
        now = _now_iso()
        anomaly = AnomalyRecord(
            anomaly_id=anomaly_id, tenant_id=tenant_id,
            source_runtime=source_runtime, description=description,
            severity=severity, trace_id=trace_id, detected_at=now,
        )
        self._anomalies[anomaly_id] = anomaly
        _emit(self._events, "register_anomaly", {"anomaly_id": anomaly_id, "severity": severity.value}, anomaly_id)
        return anomaly

    def get_anomaly(self, anomaly_id: str) -> AnomalyRecord:
        if anomaly_id not in self._anomalies:
            raise RuntimeCoreInvariantError("unknown anomaly_id")
        return self._anomalies[anomaly_id]

    def anomalies_for_tenant(self, tenant_id: str) -> tuple[AnomalyRecord, ...]:
        return tuple(a for a in self._anomalies.values() if a.tenant_id == tenant_id)

    def critical_anomalies(self, tenant_id: str) -> tuple[AnomalyRecord, ...]:
        return tuple(a for a in self._anomalies.values() if a.tenant_id == tenant_id and a.severity == AnomalySeverity.CRITICAL)

    # -- Debug sessions ------------------------------------------------------

    def open_debug_session(
        self,
        session_id: str,
        tenant_id: str,
        operator_ref: str,
        target_runtime: str,
        trace_id: str = "none",
    ) -> DebugSession:
        if session_id in self._debug_sessions:
            raise RuntimeCoreInvariantError("duplicate session_id")
        now = _now_iso()
        session = DebugSession(
            session_id=session_id, tenant_id=tenant_id,
            operator_ref=operator_ref, target_runtime=target_runtime,
            disposition=DebugDisposition.OPEN, trace_id=trace_id,
            created_at=now,
        )
        self._debug_sessions[session_id] = session
        _emit(self._events, "open_debug_session", {"session_id": session_id}, session_id)
        return session

    def investigate_session(self, session_id: str) -> DebugSession:
        session = self._get_session(session_id)
        if session.disposition in _DEBUG_TERMINAL:
            raise RuntimeCoreInvariantError("session is in terminal state")
        now = _now_iso()
        updated = DebugSession(
            session_id=session.session_id, tenant_id=session.tenant_id,
            operator_ref=session.operator_ref, target_runtime=session.target_runtime,
            disposition=DebugDisposition.INVESTIGATING, trace_id=session.trace_id,
            created_at=now,
        )
        self._debug_sessions[session_id] = updated
        _emit(self._events, "investigate_session", {"session_id": session_id}, session_id)
        return updated

    def resolve_session(self, session_id: str) -> DebugSession:
        session = self._get_session(session_id)
        if session.disposition in _DEBUG_TERMINAL:
            raise RuntimeCoreInvariantError("session is in terminal state")
        now = _now_iso()
        updated = DebugSession(
            session_id=session.session_id, tenant_id=session.tenant_id,
            operator_ref=session.operator_ref, target_runtime=session.target_runtime,
            disposition=DebugDisposition.RESOLVED, trace_id=session.trace_id,
            created_at=now,
        )
        self._debug_sessions[session_id] = updated
        _emit(self._events, "resolve_session", {"session_id": session_id}, session_id)
        return updated

    def abandon_session(self, session_id: str) -> DebugSession:
        session = self._get_session(session_id)
        if session.disposition in _DEBUG_TERMINAL:
            raise RuntimeCoreInvariantError("session is in terminal state")
        now = _now_iso()
        updated = DebugSession(
            session_id=session.session_id, tenant_id=session.tenant_id,
            operator_ref=session.operator_ref, target_runtime=session.target_runtime,
            disposition=DebugDisposition.ABANDONED, trace_id=session.trace_id,
            created_at=now,
        )
        self._debug_sessions[session_id] = updated
        _emit(self._events, "abandon_session", {"session_id": session_id}, session_id)
        return updated

    def _get_session(self, session_id: str) -> DebugSession:
        if session_id not in self._debug_sessions:
            raise RuntimeCoreInvariantError("unknown session_id")
        return self._debug_sessions[session_id]

    def get_debug_session(self, session_id: str) -> DebugSession:
        return self._get_session(session_id)

    def debug_sessions_for_tenant(self, tenant_id: str) -> tuple[DebugSession, ...]:
        return tuple(s for s in self._debug_sessions.values() if s.tenant_id == tenant_id)

    # -- Snapshots -----------------------------------------------------------

    def observability_snapshot(self, snapshot_id: str, tenant_id: str) -> ObservabilitySnapshot:
        now = _now_iso()
        metrics = self.metrics_for_tenant(tenant_id)
        logs = self.logs_for_tenant(tenant_id)
        traces = self.traces_for_tenant(tenant_id)
        spans = [s for s in self._spans.values() if s.tenant_id == tenant_id]
        anomalies = self.anomalies_for_tenant(tenant_id)
        sessions = self.debug_sessions_for_tenant(tenant_id)
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        snap = ObservabilitySnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_metrics=len(metrics), total_logs=len(logs),
            total_traces=len(traces), total_spans=len(spans),
            total_anomalies=len(anomalies), total_debug_sessions=len(sessions),
            total_violations=len(violations), captured_at=now,
        )
        _emit(self._events, "observability_snapshot", {"snapshot_id": snapshot_id}, snapshot_id)
        return snap

    # -- Assessment ----------------------------------------------------------

    def observability_assessment(self, assessment_id: str, tenant_id: str) -> ObservabilityAssessment:
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError("duplicate assessment_id")
        now = _now_iso()
        metrics = self.metrics_for_tenant(tenant_id)
        logs = self.logs_for_tenant(tenant_id)
        traces = self.traces_for_tenant(tenant_id)
        anomalies = self.anomalies_for_tenant(tenant_id)
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        total_signals = len(metrics) + len(logs) + len(traces)
        anom_rate = len(anomalies) / total_signals if total_signals > 0 else 0.0
        error_traces = [t for t in traces if t.status == TraceStatus.ERROR]
        trace_err_rate = len(error_traces) / len(traces) if traces else 0.0

        assessment = ObservabilityAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_signals=total_signals,
            anomaly_rate=round(min(1.0, max(0.0, anom_rate)), 4),
            trace_error_rate=round(min(1.0, max(0.0, trace_err_rate)), 4),
            total_violations=len(violations), assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "observability_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # -- Violations ----------------------------------------------------------

    def detect_observability_violations(self, tenant_id: str) -> tuple[ObservabilityViolation, ...]:
        now = _now_iso()
        new_violations: list[ObservabilityViolation] = []

        # Traces stuck in OPEN state with spans
        for trace in self._traces.values():
            if trace.tenant_id != tenant_id:
                continue
            if trace.status == TraceStatus.OPEN and trace.span_count > 0:
                all_spans_closed = all(
                    s.status in _TRACE_TERMINAL
                    for s in self._spans.values()
                    if s.trace_id == trace.trace_id
                )
                if all_spans_closed:
                    vid = stable_identifier("viol-obs", {"op": "stale_open_trace", "trace_id": trace.trace_id})
                    if vid not in self._violations:
                        v = ObservabilityViolation(
                            violation_id=vid, tenant_id=tenant_id,
                            operation="stale_open_trace",
                            reason="trace is open but all spans are closed",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # Critical anomalies without debug sessions
        for anomaly in self._anomalies.values():
            if anomaly.tenant_id != tenant_id:
                continue
            if anomaly.severity == AnomalySeverity.CRITICAL:
                has_session = any(
                    s.trace_id == anomaly.trace_id and s.trace_id != "none"
                    for s in self._debug_sessions.values()
                )
                if not has_session:
                    vid = stable_identifier("viol-obs", {"op": "critical_no_debug", "anomaly_id": anomaly.anomaly_id})
                    if vid not in self._violations:
                        v = ObservabilityViolation(
                            violation_id=vid, tenant_id=tenant_id,
                            operation="critical_no_debug",
                            reason="critical anomaly has no debug session",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # High error trace rate
        traces = self.traces_for_tenant(tenant_id)
        if len(traces) >= 5:
            errors = [t for t in traces if t.status == TraceStatus.ERROR]
            if len(errors) / len(traces) > 0.5:
                vid = stable_identifier("viol-obs", {"op": "high_trace_error_rate", "tenant": tenant_id})
                if vid not in self._violations:
                    v = ObservabilityViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="high_trace_error_rate",
                        reason="trace error rate above threshold",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_observability_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id)
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[ObservabilityViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # -- Closure report ------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> ObservabilityClosureReport:
        now = _now_iso()
        report = ObservabilityClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_metrics=len(self.metrics_for_tenant(tenant_id)),
            total_logs=len(self.logs_for_tenant(tenant_id)),
            total_traces=len(self.traces_for_tenant(tenant_id)),
            total_spans=len([s for s in self._spans.values() if s.tenant_id == tenant_id]),
            total_anomalies=len(self.anomalies_for_tenant(tenant_id)),
            total_debug_sessions=len(self.debug_sessions_for_tenant(tenant_id)),
            created_at=now,
        )
        _emit(self._events, "closure_report", {"report_id": report_id}, report_id)
        return report

    # -- State hash ----------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._metrics):
            parts.append(f"metric:{k}:{self._metrics[k].value}")
        for k in sorted(self._logs):
            parts.append(f"log:{k}:{self._logs[k].level}")
        for k in sorted(self._traces):
            parts.append(f"trace:{k}:{self._traces[k].status.value}")
        for k in sorted(self._spans):
            parts.append(f"span:{k}:{self._spans[k].status.value}")
        for k in sorted(self._anomalies):
            parts.append(f"anomaly:{k}:{self._anomalies[k].severity.value}")
        for k in sorted(self._debug_sessions):
            parts.append(f"debug:{k}:{self._debug_sessions[k].disposition.value}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
