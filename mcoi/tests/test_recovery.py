"""Tests for incident records, recovery decisions, and governed recovery."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.incident import (
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryAttempt,
    RecoveryDecision,
    RecoveryDecisionStatus,
)
from mcoi_runtime.core.recovery import MAX_RETRY_ATTEMPTS, RecoveryEngine


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


def _engine():
    return RecoveryEngine(clock=lambda: FIXED_CLOCK)


def _incident(incident_id="inc-1", severity=IncidentSeverity.MEDIUM, **kw):
    defaults = dict(
        incident_id=incident_id,
        severity=severity,
        status=IncidentStatus.OPEN,
        source_type="skill",
        source_id="sk-1",
        failure_family="ExecutionError",
        message="skill execution failed",
        occurred_at=FIXED_CLOCK,
    )
    defaults.update(kw)
    return IncidentRecord(**defaults)


# --- Contracts ---


class TestIncidentContracts:
    def test_valid_incident(self):
        inc = _incident()
        assert inc.severity is IncidentSeverity.MEDIUM
        assert inc.status is IncidentStatus.OPEN

    def test_empty_id_rejected(self):
        with pytest.raises(ValueError):
            _incident(incident_id="")

    def test_recovery_decision_approved(self):
        d = RecoveryDecision(
            decision_id="d-1", incident_id="inc-1",
            action=RecoveryAction.RETRY,
            status=RecoveryDecisionStatus.APPROVED,
            reason="retry permitted",
        )
        assert d.is_approved

    def test_recovery_decision_blocked(self):
        d = RecoveryDecision(
            decision_id="d-1", incident_id="inc-1",
            action=RecoveryAction.RETRY,
            status=RecoveryDecisionStatus.BLOCKED_AUTONOMY,
            reason="not permitted",
        )
        assert not d.is_approved

    def test_recovery_attempt(self):
        a = RecoveryAttempt(
            attempt_id="a-1", incident_id="inc-1", decision_id="d-1",
            action=RecoveryAction.RETRY, succeeded=True,
            started_at=FIXED_CLOCK, finished_at=FIXED_CLOCK,
        )
        assert a.succeeded


# --- Recovery engine ---


class TestRecoveryEngine:
    def test_register_and_get(self):
        engine = _engine()
        inc = _incident()
        engine.register_incident(inc)
        assert engine.get_incident("inc-1") is inc

    def test_list_open_incidents(self):
        engine = _engine()
        engine.register_incident(_incident("inc-1", status=IncidentStatus.OPEN))
        engine.register_incident(_incident("inc-2", status=IncidentStatus.RESOLVED))
        engine.register_incident(_incident("inc-3", status=IncidentStatus.RECOVERING))
        open_incs = engine.list_open_incidents()
        assert len(open_incs) == 2

    def test_incident_not_found(self):
        engine = _engine()
        decision = engine.decide("missing", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
        assert decision.status is RecoveryDecisionStatus.NOT_APPLICABLE


# --- Autonomy mode governance ---


class TestRecoveryAutonomyGovernance:
    def test_observe_only_allows_reobserve(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.REOBSERVE, autonomy_mode="observe_only")
        assert d.is_approved

    def test_observe_only_allows_escalate(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.ESCALATE, autonomy_mode="observe_only")
        assert d.is_approved

    def test_observe_only_blocks_retry(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="observe_only")
        assert not d.is_approved
        assert d.status is RecoveryDecisionStatus.BLOCKED_AUTONOMY

    def test_suggest_only_blocks_retry(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="suggest_only")
        assert not d.is_approved

    def test_approval_required_blocks_retry_without_approval(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="approval_required")
        assert d.status is RecoveryDecisionStatus.BLOCKED_AUTONOMY

    def test_approval_required_allows_retry_with_approval(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="approval_required", has_approval=True)
        assert d.is_approved

    def test_bounded_autonomous_allows_retry(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
        assert d.is_approved

    def test_bounded_autonomous_allows_replan(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.REPLAN, autonomy_mode="bounded_autonomous")
        assert d.is_approved

    def test_rollback_always_needs_approval(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.ROLLBACK, autonomy_mode="bounded_autonomous")
        assert not d.is_approved  # Even in autonomous mode

    def test_rollback_approved_with_flag(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.ROLLBACK, autonomy_mode="bounded_autonomous", has_approval=True)
        assert d.is_approved


# --- Retry limits ---


class TestRetryLimits:
    def test_retry_within_limit(self):
        engine = _engine()
        engine.register_incident(_incident())
        for _ in range(MAX_RETRY_ATTEMPTS):
            d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
            assert d.is_approved
            engine.record_attempt(d, succeeded=False)

    def test_retry_exceeds_limit(self):
        engine = _engine()
        engine.register_incident(_incident())
        for _ in range(MAX_RETRY_ATTEMPTS):
            d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
            engine.record_attempt(d, succeeded=False)

        # Next retry should be blocked
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
        assert not d.is_approved
        assert d.status is RecoveryDecisionStatus.BLOCKED_POLICY
        assert "retry limit" in d.reason

    def test_escalation_always_available_after_limit(self):
        engine = _engine()
        engine.register_incident(_incident())
        for _ in range(MAX_RETRY_ATTEMPTS):
            d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
            engine.record_attempt(d, succeeded=False)

        d = engine.decide("inc-1", RecoveryAction.ESCALATE, autonomy_mode="bounded_autonomous")
        assert d.is_approved


# --- Attempt recording ---


class TestAttemptRecording:
    def test_successful_attempt(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
        a = engine.record_attempt(d, succeeded=True, result_run_id="run-42")
        assert a.succeeded
        assert a.result_run_id == "run-42"

    def test_failed_attempt(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
        a = engine.record_attempt(d, succeeded=False, error_message="still failing")
        assert not a.succeeded
        assert a.error_message == "still failing"

    def test_list_decisions_and_attempts(self):
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.ESCALATE, autonomy_mode="observe_only")
        engine.record_attempt(d, succeeded=True)
        assert len(engine.list_decisions()) == 1
        assert len(engine.list_attempts()) == 1


# --- Golden recovery scenarios ---


class TestRecoveryGoldenScenarios:
    def test_provider_failure_recovery_blocked_by_profile(self):
        """In observe-only mode, retry is blocked — only escalate/reobserve allowed."""
        engine = _engine()
        engine.register_incident(_incident(
            source_type="provider", source_id="prov-http",
            failure_family="IntegrationError",
        ))
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="observe_only")
        assert not d.is_approved
        # But escalation works
        d2 = engine.decide("inc-1", RecoveryAction.ESCALATE, autonomy_mode="observe_only")
        assert d2.is_approved

    def test_retry_variant_allowed_in_autonomous(self):
        """Bounded-autonomous allows retry-variant for alternative approaches."""
        engine = _engine()
        engine.register_incident(_incident())
        d = engine.decide("inc-1", RecoveryAction.RETRY_VARIANT, autonomy_mode="bounded_autonomous")
        assert d.is_approved

    def test_replay_mismatch_no_auto_recovery(self):
        """Replay mismatch incident — reobserve is allowed, retry is not in observe mode."""
        engine = _engine()
        engine.register_incident(_incident(
            source_type="replay", source_id="replay-1",
            failure_family="ReplayError", message="state mismatch",
        ))
        d = engine.decide("inc-1", RecoveryAction.REOBSERVE, autonomy_mode="observe_only")
        assert d.is_approved
        d2 = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="observe_only")
        assert not d2.is_approved

    def test_runbook_drift_escalation(self):
        """Runbook drift incident — escalate in approval-required mode."""
        engine = _engine()
        engine.register_incident(_incident(
            source_type="runbook", source_id="rb-1",
            failure_family="DriftError", message="autonomy mismatch",
        ))
        d = engine.decide("inc-1", RecoveryAction.ESCALATE, autonomy_mode="approval_required")
        assert d.is_approved

    def test_bounded_rollback_with_approval(self):
        """Rollback only succeeds with explicit approval."""
        engine = _engine()
        engine.register_incident(_incident())
        # Without approval
        d1 = engine.decide("inc-1", RecoveryAction.ROLLBACK, autonomy_mode="bounded_autonomous")
        assert not d1.is_approved
        # With approval
        d2 = engine.decide("inc-1", RecoveryAction.ROLLBACK, autonomy_mode="bounded_autonomous", has_approval=True)
        assert d2.is_approved

    def test_full_recovery_lifecycle(self):
        """Incident -> decide -> attempt -> retry limit -> escalate."""
        engine = _engine()
        engine.register_incident(_incident())

        # 3 failed retries
        for _ in range(MAX_RETRY_ATTEMPTS):
            d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
            assert d.is_approved
            engine.record_attempt(d, succeeded=False)

        # Retry blocked
        d = engine.decide("inc-1", RecoveryAction.RETRY, autonomy_mode="bounded_autonomous")
        assert not d.is_approved

        # Escalate
        d = engine.decide("inc-1", RecoveryAction.ESCALATE, autonomy_mode="bounded_autonomous")
        assert d.is_approved
        engine.record_attempt(d, succeeded=True)

        assert len(engine.list_decisions()) == 5  # 3 retries + 1 blocked + 1 escalate
        assert len(engine.list_attempts()) == 4  # 3 failed retries + 1 escalation
