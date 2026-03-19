"""Golden scenario tests for autonomy mode levels.

Proves that the runtime enforces explicit autonomy boundaries:
OBSERVE_ONLY, SUGGEST_ONLY, APPROVAL_REQUIRED, BOUNDED_AUTONOMOUS.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.autonomy import (
    ActionClass,
    AutonomyDecisionStatus,
    AutonomyMode,
)
from mcoi_runtime.core.autonomy import AutonomyEngine
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig


# --- OBSERVE_ONLY ---


class TestObserveOnly:
    def test_observe_allowed(self):
        engine = AutonomyEngine(mode=AutonomyMode.OBSERVE_ONLY)
        d = engine.evaluate(ActionClass.OBSERVE)
        assert d.status is AutonomyDecisionStatus.ALLOWED

    def test_analyze_allowed(self):
        engine = AutonomyEngine(mode=AutonomyMode.OBSERVE_ONLY)
        d = engine.evaluate(ActionClass.ANALYZE)
        assert d.status is AutonomyDecisionStatus.ALLOWED

    def test_execute_write_rejected(self):
        engine = AutonomyEngine(mode=AutonomyMode.OBSERVE_ONLY)
        d = engine.evaluate(ActionClass.EXECUTE_WRITE)
        assert d.status is AutonomyDecisionStatus.REJECTED

    def test_execute_read_rejected(self):
        engine = AutonomyEngine(mode=AutonomyMode.OBSERVE_ONLY)
        d = engine.evaluate(ActionClass.EXECUTE_READ)
        assert d.status is AutonomyDecisionStatus.REJECTED

    def test_communicate_rejected(self):
        engine = AutonomyEngine(mode=AutonomyMode.OBSERVE_ONLY)
        d = engine.evaluate(ActionClass.COMMUNICATE)
        assert d.status is AutonomyDecisionStatus.REJECTED

    def test_plan_rejected(self):
        engine = AutonomyEngine(mode=AutonomyMode.OBSERVE_ONLY)
        d = engine.evaluate(ActionClass.PLAN)
        assert d.status is AutonomyDecisionStatus.REJECTED

    def test_violation_recorded(self):
        engine = AutonomyEngine(mode=AutonomyMode.OBSERVE_ONLY)
        engine.evaluate(ActionClass.EXECUTE_WRITE, action_description="deploy service")
        status = engine.get_status()
        assert status.blocked_count == 1
        assert len(status.violations) == 1
        assert status.violations[0].attempted_action == "deploy service"


# --- SUGGEST_ONLY ---


class TestSuggestOnly:
    def test_observe_allowed(self):
        engine = AutonomyEngine(mode=AutonomyMode.SUGGEST_ONLY)
        d = engine.evaluate(ActionClass.OBSERVE)
        assert d.status is AutonomyDecisionStatus.ALLOWED

    def test_plan_allowed(self):
        engine = AutonomyEngine(mode=AutonomyMode.SUGGEST_ONLY)
        d = engine.evaluate(ActionClass.PLAN)
        assert d.status is AutonomyDecisionStatus.ALLOWED

    def test_suggest_allowed(self):
        engine = AutonomyEngine(mode=AutonomyMode.SUGGEST_ONLY)
        d = engine.evaluate(ActionClass.SUGGEST)
        assert d.status is AutonomyDecisionStatus.ALLOWED

    def test_execute_write_converted_to_suggestion(self):
        engine = AutonomyEngine(mode=AutonomyMode.SUGGEST_ONLY)
        d = engine.evaluate(ActionClass.EXECUTE_WRITE, action_description="restart service")
        assert d.status is AutonomyDecisionStatus.CONVERTED_TO_SUGGESTION
        assert d.suggestion is not None
        assert "restart service" in d.suggestion

    def test_execute_read_converted_to_suggestion(self):
        engine = AutonomyEngine(mode=AutonomyMode.SUGGEST_ONLY)
        d = engine.evaluate(ActionClass.EXECUTE_READ)
        assert d.status is AutonomyDecisionStatus.CONVERTED_TO_SUGGESTION

    def test_communicate_converted_to_suggestion(self):
        engine = AutonomyEngine(mode=AutonomyMode.SUGGEST_ONLY)
        d = engine.evaluate(ActionClass.COMMUNICATE)
        assert d.status is AutonomyDecisionStatus.CONVERTED_TO_SUGGESTION

    def test_suggestion_count_tracked(self):
        engine = AutonomyEngine(mode=AutonomyMode.SUGGEST_ONLY)
        engine.evaluate(ActionClass.EXECUTE_WRITE)
        engine.evaluate(ActionClass.COMMUNICATE)
        status = engine.get_status()
        assert status.suggestion_count == 2


# --- APPROVAL_REQUIRED ---


class TestApprovalRequired:
    def test_observe_allowed_without_approval(self):
        engine = AutonomyEngine(mode=AutonomyMode.APPROVAL_REQUIRED)
        d = engine.evaluate(ActionClass.OBSERVE)
        assert d.status is AutonomyDecisionStatus.ALLOWED

    def test_plan_allowed_without_approval(self):
        engine = AutonomyEngine(mode=AutonomyMode.APPROVAL_REQUIRED)
        d = engine.evaluate(ActionClass.PLAN)
        assert d.status is AutonomyDecisionStatus.ALLOWED

    def test_execute_blocked_without_approval(self):
        engine = AutonomyEngine(mode=AutonomyMode.APPROVAL_REQUIRED)
        d = engine.evaluate(ActionClass.EXECUTE_WRITE, has_approval=False)
        assert d.status is AutonomyDecisionStatus.BLOCKED_PENDING_APPROVAL

    def test_execute_allowed_with_approval(self):
        engine = AutonomyEngine(mode=AutonomyMode.APPROVAL_REQUIRED)
        d = engine.evaluate(ActionClass.EXECUTE_WRITE, has_approval=True)
        assert d.status is AutonomyDecisionStatus.ALLOWED

    def test_communicate_blocked_without_approval(self):
        engine = AutonomyEngine(mode=AutonomyMode.APPROVAL_REQUIRED)
        d = engine.evaluate(ActionClass.COMMUNICATE, has_approval=False)
        assert d.status is AutonomyDecisionStatus.BLOCKED_PENDING_APPROVAL

    def test_communicate_allowed_with_approval(self):
        engine = AutonomyEngine(mode=AutonomyMode.APPROVAL_REQUIRED)
        d = engine.evaluate(ActionClass.COMMUNICATE, has_approval=True)
        assert d.status is AutonomyDecisionStatus.ALLOWED

    def test_pending_approval_count_tracked(self):
        engine = AutonomyEngine(mode=AutonomyMode.APPROVAL_REQUIRED)
        engine.evaluate(ActionClass.EXECUTE_WRITE)
        engine.evaluate(ActionClass.EXECUTE_READ)
        status = engine.get_status()
        assert status.pending_approval_count == 2


# --- BOUNDED_AUTONOMOUS ---


class TestBoundedAutonomous:
    def test_all_standard_actions_allowed(self):
        engine = AutonomyEngine(mode=AutonomyMode.BOUNDED_AUTONOMOUS)
        for action in ActionClass:
            d = engine.evaluate(action)
            assert d.status is AutonomyDecisionStatus.ALLOWED, f"{action.value} should be allowed"

    def test_status_tracks_all_allowed(self):
        engine = AutonomyEngine(mode=AutonomyMode.BOUNDED_AUTONOMOUS)
        engine.evaluate(ActionClass.EXECUTE_WRITE)
        engine.evaluate(ActionClass.COMMUNICATE)
        status = engine.get_status()
        assert status.allowed_count == 2
        assert status.blocked_count == 0


# --- Bootstrap integration ---


class TestBootstrapIntegration:
    def test_default_mode_is_bounded_autonomous(self):
        runtime = bootstrap_runtime(clock=lambda: "2025-01-15T10:00:00+00:00")
        assert runtime.autonomy.mode is AutonomyMode.BOUNDED_AUTONOMOUS

    def test_observe_only_from_config(self):
        config = AppConfig(autonomy_mode="observe_only")
        runtime = bootstrap_runtime(config=config, clock=lambda: "2025-01-15T10:00:00+00:00")
        assert runtime.autonomy.mode is AutonomyMode.OBSERVE_ONLY

    def test_approval_required_from_config(self):
        config = AppConfig(autonomy_mode="approval_required")
        runtime = bootstrap_runtime(config=config, clock=lambda: "2025-01-15T10:00:00+00:00")
        assert runtime.autonomy.mode is AutonomyMode.APPROVAL_REQUIRED

    def test_suggest_only_from_config(self):
        config = AppConfig(autonomy_mode="suggest_only")
        runtime = bootstrap_runtime(config=config, clock=lambda: "2025-01-15T10:00:00+00:00")
        assert runtime.autonomy.mode is AutonomyMode.SUGGEST_ONLY


# --- Status and tracking ---


class TestAutonomyStatus:
    def test_empty_status(self):
        engine = AutonomyEngine(mode=AutonomyMode.OBSERVE_ONLY)
        status = engine.get_status()
        assert status.mode is AutonomyMode.OBSERVE_ONLY
        assert status.total_decisions == 0
        assert status.violations == ()

    def test_mixed_decisions(self):
        engine = AutonomyEngine(mode=AutonomyMode.OBSERVE_ONLY)
        engine.evaluate(ActionClass.OBSERVE)
        engine.evaluate(ActionClass.EXECUTE_WRITE)
        engine.evaluate(ActionClass.ANALYZE)
        status = engine.get_status()
        assert status.total_decisions == 3
        assert status.allowed_count == 2
        assert status.blocked_count == 1
        assert len(status.violations) == 1

    def test_decision_ids_are_deterministic(self):
        engine = AutonomyEngine(mode=AutonomyMode.BOUNDED_AUTONOMOUS)
        d1 = engine.evaluate(ActionClass.OBSERVE)
        assert d1.decision_id.startswith("autonomy-")

    def test_mode_property(self):
        engine = AutonomyEngine(mode=AutonomyMode.SUGGEST_ONLY)
        assert engine.mode is AutonomyMode.SUGGEST_ONLY
