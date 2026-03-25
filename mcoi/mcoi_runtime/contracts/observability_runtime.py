"""Purpose: observability / telemetry / debug runtime contracts.
Governance scope: typed descriptors for metrics, logs, traces, spans,
    anomalies, debug sessions, snapshots, violations, assessments,
    and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every signal references a tenant.
  - Traces are scoped to runtime boundaries.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TelemetryStatus(Enum):
    """Status of a telemetry signal."""
    ACTIVE = "active"
    BUFFERED = "buffered"
    FLUSHED = "flushed"
    DROPPED = "dropped"


class SignalKind(Enum):
    """Kind of observability signal."""
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    SPAN = "span"
    ANOMALY = "anomaly"


class TraceStatus(Enum):
    """Status of a trace or span."""
    OPEN = "open"
    CLOSED = "closed"
    ERROR = "error"
    TIMEOUT = "timeout"


class AnomalySeverity(Enum):
    """Severity of an anomaly."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DebugDisposition(Enum):
    """Disposition of a debug session."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class ObservabilityScope(Enum):
    """Scope of observability collection."""
    TENANT = "tenant"
    WORKSPACE = "workspace"
    RUNTIME = "runtime"
    SERVICE = "service"
    GLOBAL = "global"
    ENDPOINT = "endpoint"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetricRecord(ContractRecord):
    """A metric data point."""

    metric_id: str = ""
    tenant_id: str = ""
    metric_name: str = ""
    value: float = 0.0
    source_runtime: str = ""
    scope: ObservabilityScope = ObservabilityScope.RUNTIME
    recorded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", require_non_empty_text(self.metric_id, "metric_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "metric_name", require_non_empty_text(self.metric_name, "metric_name"))
        object.__setattr__(self, "value", require_non_negative_float(self.value, "value"))
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        if not isinstance(self.scope, ObservabilityScope):
            raise ValueError("scope must be an ObservabilityScope")
        require_datetime_text(self.recorded_at, "recorded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LogRecord(ContractRecord):
    """A structured log entry."""

    log_id: str = ""
    tenant_id: str = ""
    level: str = ""
    message: str = ""
    source_runtime: str = ""
    trace_id: str = ""
    logged_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "log_id", require_non_empty_text(self.log_id, "log_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "level", require_non_empty_text(self.level, "level"))
        object.__setattr__(self, "message", require_non_empty_text(self.message, "message"))
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        object.__setattr__(self, "trace_id", require_non_empty_text(self.trace_id, "trace_id"))
        require_datetime_text(self.logged_at, "logged_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TraceRecord(ContractRecord):
    """A distributed trace record."""

    trace_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    source_runtime: str = ""
    status: TraceStatus = TraceStatus.OPEN
    span_count: int = 0
    duration_ms: float = 0.0
    started_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", require_non_empty_text(self.trace_id, "trace_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        if not isinstance(self.status, TraceStatus):
            raise ValueError("status must be a TraceStatus")
        object.__setattr__(self, "span_count", require_non_negative_int(self.span_count, "span_count"))
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        require_datetime_text(self.started_at, "started_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpanRecord(ContractRecord):
    """A span within a trace."""

    span_id: str = ""
    trace_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    source_runtime: str = ""
    parent_span_id: str = ""
    status: TraceStatus = TraceStatus.OPEN
    duration_ms: float = 0.0
    started_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "span_id", require_non_empty_text(self.span_id, "span_id"))
        object.__setattr__(self, "trace_id", require_non_empty_text(self.trace_id, "trace_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        object.__setattr__(self, "parent_span_id", require_non_empty_text(self.parent_span_id, "parent_span_id"))
        if not isinstance(self.status, TraceStatus):
            raise ValueError("status must be a TraceStatus")
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        require_datetime_text(self.started_at, "started_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AnomalyRecord(ContractRecord):
    """An anomaly detection record."""

    anomaly_id: str = ""
    tenant_id: str = ""
    source_runtime: str = ""
    description: str = ""
    severity: AnomalySeverity = AnomalySeverity.WARNING
    trace_id: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "anomaly_id", require_non_empty_text(self.anomaly_id, "anomaly_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.severity, AnomalySeverity):
            raise ValueError("severity must be an AnomalySeverity")
        object.__setattr__(self, "trace_id", require_non_empty_text(self.trace_id, "trace_id"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DebugSession(ContractRecord):
    """A debug/investigation session."""

    session_id: str = ""
    tenant_id: str = ""
    operator_ref: str = ""
    target_runtime: str = ""
    disposition: DebugDisposition = DebugDisposition.OPEN
    trace_id: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operator_ref", require_non_empty_text(self.operator_ref, "operator_ref"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        if not isinstance(self.disposition, DebugDisposition):
            raise ValueError("disposition must be a DebugDisposition")
        object.__setattr__(self, "trace_id", require_non_empty_text(self.trace_id, "trace_id"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ObservabilitySnapshot(ContractRecord):
    """Point-in-time snapshot of observability state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_metrics: int = 0
    total_logs: int = 0
    total_traces: int = 0
    total_spans: int = 0
    total_anomalies: int = 0
    total_debug_sessions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_metrics", require_non_negative_int(self.total_metrics, "total_metrics"))
        object.__setattr__(self, "total_logs", require_non_negative_int(self.total_logs, "total_logs"))
        object.__setattr__(self, "total_traces", require_non_negative_int(self.total_traces, "total_traces"))
        object.__setattr__(self, "total_spans", require_non_negative_int(self.total_spans, "total_spans"))
        object.__setattr__(self, "total_anomalies", require_non_negative_int(self.total_anomalies, "total_anomalies"))
        object.__setattr__(self, "total_debug_sessions", require_non_negative_int(self.total_debug_sessions, "total_debug_sessions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ObservabilityViolation(ContractRecord):
    """An observability violation."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ObservabilityAssessment(ContractRecord):
    """An assessment of observability health."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_signals: int = 0
    anomaly_rate: float = 0.0
    trace_error_rate: float = 0.0
    total_violations: int = 0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_signals", require_non_negative_int(self.total_signals, "total_signals"))
        object.__setattr__(self, "anomaly_rate", require_unit_float(self.anomaly_rate, "anomaly_rate"))
        object.__setattr__(self, "trace_error_rate", require_unit_float(self.trace_error_rate, "trace_error_rate"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ObservabilityClosureReport(ContractRecord):
    """Closure report for observability."""

    report_id: str = ""
    tenant_id: str = ""
    total_metrics: int = 0
    total_logs: int = 0
    total_traces: int = 0
    total_spans: int = 0
    total_anomalies: int = 0
    total_debug_sessions: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_metrics", require_non_negative_int(self.total_metrics, "total_metrics"))
        object.__setattr__(self, "total_logs", require_non_negative_int(self.total_logs, "total_logs"))
        object.__setattr__(self, "total_traces", require_non_negative_int(self.total_traces, "total_traces"))
        object.__setattr__(self, "total_spans", require_non_negative_int(self.total_spans, "total_spans"))
        object.__setattr__(self, "total_anomalies", require_non_negative_int(self.total_anomalies, "total_anomalies"))
        object.__setattr__(self, "total_debug_sessions", require_non_negative_int(self.total_debug_sessions, "total_debug_sessions"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
