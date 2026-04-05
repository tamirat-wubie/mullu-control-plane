"""Tests for telemetry contracts, collector, aggregation, alerting, and run history."""

from __future__ import annotations

import pytest

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
from mcoi_runtime.core.telemetry import (
    AlertThreshold,
    RunHistoryEntry,
    TelemetryCollector,
)


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


def _collector():
    return TelemetryCollector(clock=lambda: FIXED_CLOCK)


# --- RunMetrics contracts ---


class TestRunMetrics:
    def test_basic_metrics(self):
        m = RunMetrics(total_runs=10, succeeded=7, failed=3)
        assert m.success_rate == 0.7

    def test_zero_runs(self):
        m = RunMetrics()
        assert m.success_rate == 0.0
        assert m.verification_closure_rate == 0.0

    def test_negative_rejected(self):
        with pytest.raises(ValueError, match="^run metric count must be a non-negative integer$") as exc_info:
            RunMetrics(total_runs=-1)
        assert "total_runs" not in str(exc_info.value)


class TestSkillMetrics:
    def test_success_rate(self):
        m = SkillMetrics(skill_id="sk-1", total_executions=4, succeeded=3, failed=1)
        assert m.success_rate == 0.75


class TestProviderMetrics:
    def test_failure_rate(self):
        m = ProviderMetrics(provider_id="p-1", total_invocations=10, succeeded=8, failed=2)
        assert m.failure_rate == 0.2


# --- TelemetryCollector ---


class TestTelemetryCollector:
    def test_record_run_success(self):
        c = _collector()
        c.record_run(succeeded=True, dispatched=True, verification_closed=True)
        snap = c.snapshot()
        assert snap.run_metrics.total_runs == 1
        assert snap.run_metrics.succeeded == 1
        assert snap.run_metrics.dispatched == 1

    def test_record_run_failure(self):
        c = _collector()
        c.record_run(succeeded=False, dispatched=True, verification_closed=False)
        snap = c.snapshot()
        assert snap.run_metrics.failed == 1
        assert snap.run_metrics.verification_open == 1

    def test_record_policy_denied(self):
        c = _collector()
        c.record_run(succeeded=False, dispatched=False, verification_closed=False, policy_denied=True)
        snap = c.snapshot()
        assert snap.run_metrics.policy_denied == 1
        assert snap.run_metrics.not_dispatched == 1

    def test_multiple_runs_aggregate(self):
        c = _collector()
        for _ in range(3):
            c.record_run(succeeded=True, dispatched=True, verification_closed=True)
        c.record_run(succeeded=False, dispatched=True, verification_closed=False)
        snap = c.snapshot()
        assert snap.run_metrics.total_runs == 4
        assert snap.run_metrics.succeeded == 3
        assert snap.run_metrics.failed == 1

    def test_record_skill_execution(self):
        c = _collector()
        c.record_skill_execution("sk-a", succeeded=True)
        c.record_skill_execution("sk-a", succeeded=False)
        c.record_skill_execution("sk-b", succeeded=True, promoted=True)
        snap = c.snapshot()
        assert len(snap.skill_metrics) == 2
        sk_a = next(s for s in snap.skill_metrics if s.skill_id == "sk-a")
        assert sk_a.total_executions == 2
        assert sk_a.succeeded == 1
        assert sk_a.success_rate == 0.5
        sk_b = next(s for s in snap.skill_metrics if s.skill_id == "sk-b")
        assert sk_b.promotions == 1

    def test_record_provider_invocation(self):
        c = _collector()
        c.record_provider_invocation("p-1", succeeded=True)
        c.record_provider_invocation("p-1", succeeded=False, timeout=True)
        snap = c.snapshot()
        assert len(snap.provider_metrics) == 1
        p = snap.provider_metrics[0]
        assert p.total_invocations == 2
        assert p.timeouts == 1

    def test_record_autonomy_decisions(self):
        c = _collector()
        c.record_autonomy_decision(allowed=True)
        c.record_autonomy_decision(blocked=True, violation=True)
        c.record_autonomy_decision(suggestion=True)
        snap = c.snapshot()
        assert snap.autonomy_metrics is not None
        assert snap.autonomy_metrics.total_decisions == 3
        assert snap.autonomy_metrics.allowed == 1
        assert snap.autonomy_metrics.blocked == 1
        assert snap.autonomy_metrics.violations == 1

    def test_no_autonomy_metrics_when_empty(self):
        c = _collector()
        c.record_run(succeeded=True, dispatched=True, verification_closed=True)
        snap = c.snapshot()
        assert snap.autonomy_metrics is None


# --- Alerting ---


class TestAlerting:
    def test_alert_triggers_on_threshold(self):
        c = _collector()
        c.add_threshold(AlertThreshold(
            metric_name="failure_rate",
            source="runs",
            threshold=0.5,
            severity=AlertSeverity.WARNING,
            message_template="run failure rate {value:.0%} exceeds {threshold:.0%}",
        ))
        # 2 failures out of 3 runs = 66% > 50%
        c.record_run(succeeded=False, dispatched=True, verification_closed=False)
        c.record_run(succeeded=False, dispatched=True, verification_closed=False)
        c.record_run(succeeded=True, dispatched=True, verification_closed=True)

        snap = c.snapshot()
        assert len(snap.active_alerts) == 1
        assert snap.active_alerts[0].severity is AlertSeverity.WARNING
        # Alert triggers after first failure (100% at that point)
        assert "exceeds" in snap.active_alerts[0].message

    def test_no_alert_below_threshold(self):
        c = _collector()
        c.add_threshold(AlertThreshold(
            metric_name="failure_rate",
            source="runs",
            threshold=0.8,
            severity=AlertSeverity.CRITICAL,
            message_template="high failure rate",
        ))
        c.record_run(succeeded=True, dispatched=True, verification_closed=True)
        c.record_run(succeeded=False, dispatched=True, verification_closed=False)
        assert c.active_alert_count == 0

    def test_no_duplicate_alerts(self):
        c = _collector()
        c.add_threshold(AlertThreshold(
            metric_name="failure_rate",
            source="runs",
            threshold=0.0,
            severity=AlertSeverity.INFO,
            message_template="any failure",
        ))
        c.record_run(succeeded=False, dispatched=False, verification_closed=False)
        c.record_run(succeeded=False, dispatched=False, verification_closed=False)
        assert c.active_alert_count == 1

    def test_skill_failure_alert(self):
        c = _collector()
        c.add_threshold(AlertThreshold(
            metric_name="failure_rate",
            source="sk-fragile",
            threshold=0.5,
            severity=AlertSeverity.WARNING,
            message_template="skill failing",
        ))
        c.record_skill_execution("sk-fragile", succeeded=False)
        c.record_skill_execution("sk-fragile", succeeded=False)
        c.record_skill_execution("sk-fragile", succeeded=True)
        assert c.active_alert_count == 1

    def test_provider_failure_alert(self):
        c = _collector()
        c.add_threshold(AlertThreshold(
            metric_name="failure_rate",
            source="prov-flaky",
            threshold=0.3,
            severity=AlertSeverity.CRITICAL,
            message_template="provider degraded",
        ))
        c.record_provider_invocation("prov-flaky", succeeded=False)
        c.record_provider_invocation("prov-flaky", succeeded=True)
        assert c.active_alert_count == 1  # 50% > 30%


# --- Run history ---


class TestRunHistory:
    def test_history_records_runs(self):
        c = _collector()
        c.record_run(succeeded=True, dispatched=True, verification_closed=True,
                      request_id="r1", goal_id="g1")
        c.record_run(succeeded=False, dispatched=False, verification_closed=False,
                      request_id="r2", goal_id="g2")
        history = c.get_run_history()
        assert len(history) == 2
        assert history[0].request_id == "r1"
        assert history[1].request_id == "r2"

    def test_filter_succeeded(self):
        c = _collector()
        c.record_run(succeeded=True, dispatched=True, verification_closed=True, request_id="ok")
        c.record_run(succeeded=False, dispatched=False, verification_closed=False, request_id="fail")
        history = c.get_run_history(succeeded_only=True)
        assert len(history) == 1
        assert history[0].request_id == "ok"

    def test_filter_failed(self):
        c = _collector()
        c.record_run(succeeded=True, dispatched=True, verification_closed=True, request_id="ok")
        c.record_run(succeeded=False, dispatched=False, verification_closed=False, request_id="fail")
        history = c.get_run_history(failed_only=True)
        assert len(history) == 1
        assert history[0].request_id == "fail"

    def test_filter_by_skill(self):
        c = _collector()
        c.record_run(succeeded=True, dispatched=True, verification_closed=True, skill_id="sk-a")
        c.record_run(succeeded=True, dispatched=True, verification_closed=True, skill_id="sk-b")
        history = c.get_run_history(skill_id="sk-a")
        assert len(history) == 1

    def test_filter_by_autonomy_mode(self):
        c = _collector()
        c.record_run(succeeded=True, dispatched=True, verification_closed=True, autonomy_mode="observe_only")
        c.record_run(succeeded=True, dispatched=True, verification_closed=True, autonomy_mode="bounded_autonomous")
        history = c.get_run_history(autonomy_mode="observe_only")
        assert len(history) == 1

    def test_limit(self):
        c = _collector()
        for i in range(10):
            c.record_run(succeeded=True, dispatched=True, verification_closed=True, request_id=f"r{i}")
        history = c.get_run_history(limit=3)
        assert len(history) == 3
        assert history[0].request_id == "r7"  # Last 3

    def test_history_entry_fields(self):
        c = _collector()
        c.record_run(
            succeeded=True, dispatched=True, verification_closed=True,
            request_id="r1", goal_id="g1", autonomy_mode="approval_required", skill_id="sk-x",
        )
        entry = c.get_run_history()[0]
        assert entry.request_id == "r1"
        assert entry.goal_id == "g1"
        assert entry.autonomy_mode == "approval_required"
        assert entry.skill_id == "sk-x"
        assert entry.recorded_at == FIXED_CLOCK


# --- Snapshot completeness ---


class TestSnapshot:
    def test_snapshot_has_all_sections(self):
        c = _collector()
        c.record_run(succeeded=True, dispatched=True, verification_closed=True)
        c.record_skill_execution("sk-1", succeeded=True)
        c.record_provider_invocation("p-1", succeeded=True)
        c.record_autonomy_decision(allowed=True)

        snap = c.snapshot()
        assert snap.run_metrics.total_runs == 1
        assert len(snap.skill_metrics) == 1
        assert len(snap.provider_metrics) == 1
        assert snap.autonomy_metrics is not None
        assert snap.snapshot_id.startswith("telemetry-")
        assert snap.captured_at == FIXED_CLOCK
