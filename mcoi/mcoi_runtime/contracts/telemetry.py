"""Purpose: canonical telemetry and metrics contract mapping.
Governance scope: run metrics, skill metrics, provider metrics, and alert typing.
Dependencies: shared contract base helpers.
Invariants:
  - Metrics are derived from actual outcomes, never fabricated.
  - Counters are monotonically non-decreasing.
  - Alert thresholds are explicit and configurable.
  - All metrics carry explicit time attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
)


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class RunMetrics(ContractRecord):
    """Aggregate metrics for operator runs."""

    total_runs: int = 0
    succeeded: int = 0
    failed: int = 0
    policy_denied: int = 0
    verification_closed: int = 0
    verification_open: int = 0
    dispatched: int = 0
    not_dispatched: int = 0

    def __post_init__(self) -> None:
        for attr in ("total_runs", "succeeded", "failed", "policy_denied",
                      "verification_closed", "verification_open", "dispatched", "not_dispatched"):
            val = getattr(self, attr)
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"{attr} must be a non-negative integer")

    @property
    def success_rate(self) -> float:
        return self.succeeded / self.total_runs if self.total_runs > 0 else 0.0

    @property
    def verification_closure_rate(self) -> float:
        return self.verification_closed / self.total_runs if self.total_runs > 0 else 0.0


@dataclass(frozen=True, slots=True)
class SkillMetrics(ContractRecord):
    """Aggregate metrics for skill executions."""

    skill_id: str
    total_executions: int = 0
    succeeded: int = 0
    failed: int = 0
    precondition_failures: int = 0
    postcondition_failures: int = 0
    promotions: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_id", require_non_empty_text(self.skill_id, "skill_id"))
        for attr in ("total_executions", "succeeded", "failed",
                      "precondition_failures", "postcondition_failures", "promotions"):
            require_non_negative_int(getattr(self, attr), attr)

    @property
    def success_rate(self) -> float:
        return self.succeeded / self.total_executions if self.total_executions > 0 else 0.0


@dataclass(frozen=True, slots=True)
class ProviderMetrics(ContractRecord):
    """Aggregate metrics for provider invocations."""

    provider_id: str
    total_invocations: int = 0
    succeeded: int = 0
    failed: int = 0
    timeouts: int = 0
    scope_rejections: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", require_non_empty_text(self.provider_id, "provider_id"))
        for attr in ("total_invocations", "succeeded", "failed", "timeouts", "scope_rejections"):
            require_non_negative_int(getattr(self, attr), attr)

    @property
    def success_rate(self) -> float:
        return self.succeeded / self.total_invocations if self.total_invocations > 0 else 0.0

    @property
    def failure_rate(self) -> float:
        return self.failed / self.total_invocations if self.total_invocations > 0 else 0.0


@dataclass(frozen=True, slots=True)
class AutonomyMetrics(ContractRecord):
    """Aggregate metrics for autonomy mode decisions."""

    mode: str
    total_decisions: int = 0
    allowed: int = 0
    blocked: int = 0
    suggestions: int = 0
    pending_approval: int = 0
    violations: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", require_non_empty_text(self.mode, "mode"))
        for attr in ("total_decisions", "allowed", "blocked",
                      "suggestions", "pending_approval", "violations"):
            require_non_negative_int(getattr(self, attr), attr)


@dataclass(frozen=True, slots=True)
class TelemetryAlert(ContractRecord):
    """An alert triggered by threshold breach."""

    alert_id: str
    severity: AlertSeverity
    status: AlertStatus
    source: str
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    triggered_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "alert_id", require_non_empty_text(self.alert_id, "alert_id"))
        if not isinstance(self.severity, AlertSeverity):
            raise ValueError("severity must be an AlertSeverity value")
        if not isinstance(self.status, AlertStatus):
            raise ValueError("status must be an AlertStatus value")
        object.__setattr__(self, "source", require_non_empty_text(self.source, "source"))
        object.__setattr__(self, "message", require_non_empty_text(self.message, "message"))
        object.__setattr__(self, "metric_name", require_non_empty_text(self.metric_name, "metric_name"))
        require_non_negative_float(self.metric_value, "metric_value")
        require_non_negative_float(self.threshold, "threshold")
        object.__setattr__(self, "triggered_at", require_datetime_text(self.triggered_at, "triggered_at"))


@dataclass(frozen=True, slots=True)
class TelemetrySnapshot(ContractRecord):
    """Full telemetry snapshot for operator visibility."""

    snapshot_id: str
    captured_at: str
    run_metrics: RunMetrics
    skill_metrics: tuple[SkillMetrics, ...] = ()
    provider_metrics: tuple[ProviderMetrics, ...] = ()
    autonomy_metrics: AutonomyMetrics | None = None
    active_alerts: tuple[TelemetryAlert, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))
        if not isinstance(self.run_metrics, RunMetrics):
            raise ValueError("run_metrics must be a RunMetrics instance")
        object.__setattr__(self, "skill_metrics", freeze_value(list(self.skill_metrics)))
        object.__setattr__(self, "provider_metrics", freeze_value(list(self.provider_metrics)))
        object.__setattr__(self, "active_alerts", freeze_value(list(self.active_alerts)))
