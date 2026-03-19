"""Purpose: telemetry collection, aggregation, alerting thresholds.
Governance scope: telemetry and observability logic only.
Dependencies: telemetry contracts, invariant helpers.
Invariants:
  - Metrics derive from actual reported outcomes only.
  - Counters are monotonically non-decreasing.
  - Alerts trigger deterministically from explicit thresholds.
  - No telemetry operation mutates runtime execution state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mcoi_runtime.contracts.telemetry import (
    AlertSeverity,
    AlertStatus,
    AutonomyMetrics,
    ProviderMetrics,
    RunMetrics,
    SkillMetrics,
    TelemetryAlert,
    TelemetrySnapshot,
)
from .invariants import ensure_non_empty_text, stable_identifier


@dataclass
class AlertThreshold:
    """Configurable threshold for triggering alerts."""

    metric_name: str
    source: str
    threshold: float
    severity: AlertSeverity
    message_template: str  # {value} and {threshold} will be substituted


class TelemetryCollector:
    """Collects and aggregates telemetry from runtime outcomes.

    Thread-unsafe — intended for single-threaded operator loop use.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        # Run counters
        self._total_runs = 0
        self._succeeded = 0
        self._failed = 0
        self._policy_denied = 0
        self._verification_closed = 0
        self._verification_open = 0
        self._dispatched = 0
        self._not_dispatched = 0
        # Skill counters
        self._skill_counters: dict[str, dict[str, int]] = {}
        # Provider counters
        self._provider_counters: dict[str, dict[str, int]] = {}
        # Autonomy counters
        self._autonomy_mode: str = "unknown"
        self._autonomy_decisions = 0
        self._autonomy_allowed = 0
        self._autonomy_blocked = 0
        self._autonomy_suggestions = 0
        self._autonomy_pending = 0
        self._autonomy_violations = 0
        # Alerts
        self._thresholds: list[AlertThreshold] = []
        self._alerts: list[TelemetryAlert] = []
        # Run history
        self._run_history: list[RunHistoryEntry] = []

    # --- Run recording ---

    def record_run(
        self,
        *,
        succeeded: bool,
        dispatched: bool,
        verification_closed: bool,
        policy_denied: bool = False,
        request_id: str = "",
        goal_id: str = "",
        autonomy_mode: str = "",
        skill_id: str | None = None,
    ) -> None:
        self._total_runs += 1
        if succeeded:
            self._succeeded += 1
        else:
            self._failed += 1
        if policy_denied:
            self._policy_denied += 1
        if dispatched:
            self._dispatched += 1
        else:
            self._not_dispatched += 1
        if verification_closed:
            self._verification_closed += 1
        else:
            self._verification_open += 1
        if autonomy_mode:
            self._autonomy_mode = autonomy_mode

        self._run_history.append(RunHistoryEntry(
            request_id=request_id,
            goal_id=goal_id,
            succeeded=succeeded,
            dispatched=dispatched,
            verification_closed=verification_closed,
            policy_denied=policy_denied,
            autonomy_mode=autonomy_mode,
            skill_id=skill_id,
            recorded_at=self._clock(),
        ))

        self._check_thresholds()

    # --- Skill recording ---

    def record_skill_execution(
        self,
        skill_id: str,
        *,
        succeeded: bool,
        precondition_failed: bool = False,
        postcondition_failed: bool = False,
        promoted: bool = False,
    ) -> None:
        ensure_non_empty_text("skill_id", skill_id)
        if skill_id not in self._skill_counters:
            self._skill_counters[skill_id] = {
                "total": 0, "succeeded": 0, "failed": 0,
                "precondition_failures": 0, "postcondition_failures": 0, "promotions": 0,
            }
        c = self._skill_counters[skill_id]
        c["total"] += 1
        if succeeded:
            c["succeeded"] += 1
        else:
            c["failed"] += 1
        if precondition_failed:
            c["precondition_failures"] += 1
        if postcondition_failed:
            c["postcondition_failures"] += 1
        if promoted:
            c["promotions"] += 1
        self._check_thresholds()

    # --- Provider recording ---

    def record_provider_invocation(
        self,
        provider_id: str,
        *,
        succeeded: bool,
        timeout: bool = False,
        scope_rejected: bool = False,
    ) -> None:
        ensure_non_empty_text("provider_id", provider_id)
        if provider_id not in self._provider_counters:
            self._provider_counters[provider_id] = {
                "total": 0, "succeeded": 0, "failed": 0, "timeouts": 0, "scope_rejections": 0,
            }
        c = self._provider_counters[provider_id]
        c["total"] += 1
        if succeeded:
            c["succeeded"] += 1
        else:
            c["failed"] += 1
        if timeout:
            c["timeouts"] += 1
        if scope_rejected:
            c["scope_rejections"] += 1
        self._check_thresholds()

    # --- Autonomy recording ---

    def record_autonomy_decision(
        self,
        *,
        allowed: bool = False,
        blocked: bool = False,
        suggestion: bool = False,
        pending_approval: bool = False,
        violation: bool = False,
    ) -> None:
        self._autonomy_decisions += 1
        if allowed:
            self._autonomy_allowed += 1
        if blocked:
            self._autonomy_blocked += 1
        if suggestion:
            self._autonomy_suggestions += 1
        if pending_approval:
            self._autonomy_pending += 1
        if violation:
            self._autonomy_violations += 1

    # --- Thresholds ---

    def add_threshold(self, threshold: AlertThreshold) -> None:
        self._thresholds.append(threshold)

    def _check_thresholds(self) -> None:
        for t in self._thresholds:
            value = self._get_metric_value(t.metric_name, t.source)
            if value is not None and value >= t.threshold:
                # Check if already alerted for this threshold
                already = any(
                    a.metric_name == t.metric_name and a.source == t.source
                    and a.status is AlertStatus.ACTIVE
                    for a in self._alerts
                )
                if not already:
                    alert_id = stable_identifier("alert", {
                        "metric": t.metric_name,
                        "source": t.source,
                        "count": len(self._alerts),
                    })
                    self._alerts.append(TelemetryAlert(
                        alert_id=alert_id,
                        severity=t.severity,
                        status=AlertStatus.ACTIVE,
                        source=t.source,
                        message=t.message_template.format(value=value, threshold=t.threshold),
                        metric_name=t.metric_name,
                        metric_value=value,
                        threshold=t.threshold,
                        triggered_at=self._clock(),
                    ))

    def _get_metric_value(self, metric_name: str, source: str) -> float | None:
        if metric_name == "failure_rate" and source == "runs":
            return self._failed / self._total_runs if self._total_runs > 0 else None
        if metric_name == "failure_rate" and source in self._provider_counters:
            c = self._provider_counters[source]
            return c["failed"] / c["total"] if c["total"] > 0 else None
        if metric_name == "failure_rate" and source in self._skill_counters:
            c = self._skill_counters[source]
            return c["failed"] / c["total"] if c["total"] > 0 else None
        if metric_name == "violation_rate" and source == "autonomy":
            return self._autonomy_violations / self._autonomy_decisions if self._autonomy_decisions > 0 else None
        return None

    # --- Snapshots ---

    def snapshot(self) -> TelemetrySnapshot:
        snapshot_id = stable_identifier("telemetry", {"total_runs": self._total_runs})
        return TelemetrySnapshot(
            snapshot_id=snapshot_id,
            captured_at=self._clock(),
            run_metrics=RunMetrics(
                total_runs=self._total_runs,
                succeeded=self._succeeded,
                failed=self._failed,
                policy_denied=self._policy_denied,
                verification_closed=self._verification_closed,
                verification_open=self._verification_open,
                dispatched=self._dispatched,
                not_dispatched=self._not_dispatched,
            ),
            skill_metrics=tuple(
                SkillMetrics(
                    skill_id=sid,
                    total_executions=c["total"],
                    succeeded=c["succeeded"],
                    failed=c["failed"],
                    precondition_failures=c["precondition_failures"],
                    postcondition_failures=c["postcondition_failures"],
                    promotions=c["promotions"],
                )
                for sid, c in sorted(self._skill_counters.items())
            ),
            provider_metrics=tuple(
                ProviderMetrics(
                    provider_id=pid,
                    total_invocations=c["total"],
                    succeeded=c["succeeded"],
                    failed=c["failed"],
                    timeouts=c["timeouts"],
                    scope_rejections=c["scope_rejections"],
                )
                for pid, c in sorted(self._provider_counters.items())
            ),
            autonomy_metrics=AutonomyMetrics(
                mode=self._autonomy_mode,
                total_decisions=self._autonomy_decisions,
                allowed=self._autonomy_allowed,
                blocked=self._autonomy_blocked,
                suggestions=self._autonomy_suggestions,
                pending_approval=self._autonomy_pending,
                violations=self._autonomy_violations,
            ) if self._autonomy_decisions > 0 else None,
            active_alerts=tuple(a for a in self._alerts if a.status is AlertStatus.ACTIVE),
        )

    # --- Run history ---

    def get_run_history(
        self,
        *,
        limit: int = 50,
        succeeded_only: bool = False,
        failed_only: bool = False,
        skill_id: str | None = None,
        autonomy_mode: str | None = None,
    ) -> tuple[RunHistoryEntry, ...]:
        """Query run history with optional filters."""
        entries = list(self._run_history)
        if succeeded_only:
            entries = [e for e in entries if e.succeeded]
        if failed_only:
            entries = [e for e in entries if not e.succeeded]
        if skill_id:
            entries = [e for e in entries if e.skill_id == skill_id]
        if autonomy_mode:
            entries = [e for e in entries if e.autonomy_mode == autonomy_mode]
        return tuple(entries[-limit:])

    @property
    def active_alert_count(self) -> int:
        return sum(1 for a in self._alerts if a.status is AlertStatus.ACTIVE)


@dataclass(frozen=True, slots=True)
class RunHistoryEntry:
    """One entry in the run history ledger."""

    request_id: str
    goal_id: str
    succeeded: bool
    dispatched: bool
    verification_closed: bool
    policy_denied: bool
    autonomy_mode: str
    skill_id: str | None
    recorded_at: str
