"""Tests for incident playbooks, pattern matching, execution, and deployment packaging."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.incident import (
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
)
from mcoi_runtime.contracts.playbook import (
    IncidentMatchRecord,
    IncidentPattern,
    IncidentPlaybookDescriptor,
    PatternMatchResult,
    PlaybookExecutionRecord,
    PlaybookOutcome,
    PlaybookStatus,
)
from mcoi_runtime.core.playbook import PlaybookEngine
from mcoi_runtime.app.packaging import (
    get_package_info,
    validate_environment,
    validate_profile,
    ValidationStatus,
)


T0 = "2025-01-15T10:00:00+00:00"


def _engine():
    return PlaybookEngine(clock=lambda: T0)


def _pattern(pattern_id="pat-1", failure_family="ExecutionError", **kw):
    return IncidentPattern(pattern_id=pattern_id, failure_family=failure_family, **kw)


def _playbook(playbook_id="pb-1", status=PlaybookStatus.ACTIVE, **kw):
    defaults = dict(
        playbook_id=playbook_id,
        name="test playbook",
        description="handles test incidents",
        pattern=_pattern(),
        status=status,
        steps=("diagnose", "escalate", "verify"),
        recovery_action="escalate",
    )
    defaults.update(kw)
    return IncidentPlaybookDescriptor(**defaults)


def _incident(incident_id="inc-1", failure_family="ExecutionError", **kw):
    defaults = dict(
        incident_id=incident_id,
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.OPEN,
        source_type="skill",
        source_id="sk-1",
        failure_family=failure_family,
        message="skill execution failed",
        occurred_at=T0,
    )
    defaults.update(kw)
    return IncidentRecord(**defaults)


# --- Contracts ---


class TestPlaybookContracts:
    def test_pattern_valid(self):
        p = _pattern()
        assert p.failure_family == "ExecutionError"

    def test_playbook_executable(self):
        pb = _playbook(status=PlaybookStatus.ACTIVE)
        assert pb.is_executable

    def test_playbook_draft_not_executable(self):
        pb = _playbook(status=PlaybookStatus.DRAFT)
        assert not pb.is_executable

    def test_execution_record_succeeded(self):
        r = PlaybookExecutionRecord(
            record_id="r-1", playbook_id="pb-1", incident_id="inc-1",
            outcome=PlaybookOutcome.RESOLVED,
            steps_completed=3, steps_total=3,
            review_satisfied=True, approval_satisfied=True,
            started_at=T0, finished_at=T0,
        )
        assert r.succeeded

    def test_execution_record_failed(self):
        r = PlaybookExecutionRecord(
            record_id="r-1", playbook_id="pb-1", incident_id="inc-1",
            outcome=PlaybookOutcome.FAILED,
            steps_completed=1, steps_total=3,
            review_satisfied=True, approval_satisfied=True,
            started_at=T0, finished_at=T0,
        )
        assert not r.succeeded


# --- Pattern matching ---


class TestPatternMatching:
    def test_exact_family_match(self):
        engine = _engine()
        engine.register(_playbook())
        match = engine.match_incident(_incident())
        assert match.result is PatternMatchResult.MATCHED or match.result is PatternMatchResult.PARTIAL
        assert match.matched_playbook_id == "pb-1"
        assert match.match_score > 0

    def test_no_match(self):
        engine = _engine()
        engine.register(_playbook())
        match = engine.match_incident(_incident(failure_family="ConfigurationError"))
        assert match.result is PatternMatchResult.NO_MATCH

    def test_source_type_improves_score(self):
        engine = _engine()
        engine.register(_playbook(pattern=_pattern(source_type="skill")))
        match = engine.match_incident(_incident(source_type="skill"))
        assert match.match_score >= 0.8  # family(0.5) + source(0.3)

    def test_keyword_matching(self):
        engine = _engine()
        engine.register(_playbook(pattern=_pattern(keyword_match=("failed", "execution"))))
        match = engine.match_incident(_incident(message="skill execution failed badly"))
        assert match.match_score > 0.5  # family + keywords

    def test_draft_playbooks_not_matched(self):
        engine = _engine()
        engine.register(_playbook(status=PlaybookStatus.DRAFT))
        match = engine.match_incident(_incident())
        assert match.result is PatternMatchResult.NO_MATCH

    def test_best_match_selected(self):
        engine = _engine()
        engine.register(_playbook("pb-generic", pattern=_pattern("pat-gen")))
        engine.register(_playbook("pb-specific", pattern=_pattern("pat-spec", source_type="skill")))
        match = engine.match_incident(_incident(source_type="skill"))
        assert match.matched_playbook_id == "pb-specific"


# --- Execution ---


class TestPlaybookExecution:
    def test_successful_execution(self):
        engine = _engine()
        engine.register(_playbook(requires_review=False, requires_approval=False))
        result = engine.execute("pb-1", "inc-1")
        assert result.outcome is PlaybookOutcome.RESOLVED
        assert result.steps_completed == 3
        assert result.succeeded

    def test_blocked_review_not_satisfied(self):
        engine = _engine()
        engine.register(_playbook(requires_review=True))
        result = engine.execute("pb-1", "inc-1", review_satisfied=False)
        assert result.outcome is PlaybookOutcome.BLOCKED
        assert "review required" in result.error_message

    def test_blocked_approval_not_satisfied(self):
        engine = _engine()
        engine.register(_playbook(requires_review=False, requires_approval=True))
        result = engine.execute("pb-1", "inc-1", approval_satisfied=False)
        assert result.outcome is PlaybookOutcome.BLOCKED
        assert "approval required" in result.error_message

    def test_review_and_approval_satisfied(self):
        engine = _engine()
        engine.register(_playbook(requires_review=True, requires_approval=True))
        result = engine.execute("pb-1", "inc-1", review_satisfied=True, approval_satisfied=True)
        assert result.outcome is PlaybookOutcome.RESOLVED

    def test_step_failure(self):
        engine = _engine()
        engine.register(_playbook(requires_review=False))
        call_count = 0

        def fail_second(step: str) -> bool:
            nonlocal call_count
            call_count += 1
            return call_count != 2

        result = engine.execute("pb-1", "inc-1", step_executor=fail_second)
        assert result.outcome is PlaybookOutcome.FAILED
        assert result.steps_completed == 1

    def test_playbook_not_found(self):
        engine = _engine()
        result = engine.execute("missing", "inc-1")
        assert result.outcome is PlaybookOutcome.BLOCKED
        assert "not found" in result.error_message

    def test_draft_playbook_blocked(self):
        engine = _engine()
        engine.register(_playbook(status=PlaybookStatus.DRAFT, requires_review=False))
        result = engine.execute("pb-1", "inc-1")
        assert result.outcome is PlaybookOutcome.BLOCKED

    def test_execution_history_recorded(self):
        engine = _engine()
        engine.register(_playbook(requires_review=False))
        engine.execute("pb-1", "inc-1")
        assert len(engine.list_executions()) == 1


# --- Deployment packaging ---


class TestDeploymentPackaging:
    def test_validate_local_dev(self):
        result = validate_profile("local-dev")
        assert result.is_valid

    def test_validate_safe_readonly(self):
        result = validate_profile("safe-readonly")
        assert result.is_valid

    def test_validate_nonexistent_profile(self):
        result = validate_profile("nonexistent")
        assert not result.is_valid

    def test_validate_environment(self):
        result = validate_environment()
        assert result.is_valid

    def test_package_info(self):
        info = get_package_info()
        assert info.name == "Mullu Platform MCOI Runtime"
        assert info.version == "0.1.0"
        assert info.profile_count == 5


# --- Golden scenarios ---


class TestPlaybookGoldenScenarios:
    def test_provider_unavailable_escalate(self):
        """Pattern: provider failure -> match escalation playbook -> execute."""
        engine = _engine()
        engine.register(_playbook(
            "pb-prov-esc",
            pattern=_pattern("pat-prov", failure_family="IntegrationError", source_type="provider"),
            steps=("check_health", "escalate_oncall"),
            recovery_action="escalate",
            requires_review=False,
        ))
        incident = _incident(failure_family="IntegrationError", source_type="provider", message="provider timeout")
        match = engine.match_incident(incident)
        assert match.matched_playbook_id == "pb-prov-esc"
        result = engine.execute("pb-prov-esc", incident.incident_id)
        assert result.succeeded

    def test_verification_mismatch_hold_review(self):
        """Pattern: verification mismatch -> match -> blocked pending review."""
        engine = _engine()
        engine.register(_playbook(
            "pb-verify",
            pattern=_pattern("pat-verify", failure_family="VerificationError"),
            steps=("hold", "review"),
            recovery_action="hold",
            requires_review=True,
        ))
        incident = _incident(failure_family="VerificationError", message="verification mismatch")
        match = engine.match_incident(incident)
        assert match.matched_playbook_id == "pb-verify"
        result = engine.execute("pb-verify", incident.incident_id, review_satisfied=False)
        assert result.outcome is PlaybookOutcome.BLOCKED

    def test_drifted_runbook_review(self):
        """Pattern: runbook drift -> match -> needs review before re-execution."""
        engine = _engine()
        engine.register(_playbook(
            "pb-drift",
            pattern=_pattern("pat-drift", failure_family="DriftError", source_type="runbook"),
            steps=("compare_baseline", "open_review"),
            recovery_action="review",
            requires_review=True,
        ))
        incident = _incident(failure_family="DriftError", source_type="runbook", message="autonomy mismatch drift")
        match = engine.match_incident(incident)
        assert match.matched_playbook_id == "pb-drift"
        # Blocked without review
        result = engine.execute("pb-drift", incident.incident_id, review_satisfied=False)
        assert result.outcome is PlaybookOutcome.BLOCKED
        # Succeeds with review
        result = engine.execute("pb-drift", incident.incident_id, review_satisfied=True)
        assert result.succeeded
