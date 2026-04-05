"""Golden scenario tests for skill runtime integration.

Proves that skills are first-class in the live operator runtime path.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.console import render_skill_summary
from mcoi_runtime.app.operator_loop import OperatorLoop, SkillRequest, SkillRunReport
from mcoi_runtime.app.view_models import SkillSummaryView
from mcoi_runtime.contracts.skill import (
    DeterminismClass,
    EffectClass,
    SkillClass,
    SkillDescriptor,
    SkillLifecycle,
    SkillOutcomeStatus,
    SkillStep,
    TrustClass,
    VerificationStrength,
)


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


def _make_loop():
    runtime = bootstrap_runtime(clock=lambda: FIXED_CLOCK)
    return OperatorLoop(runtime=runtime)


def _register_skill(loop: OperatorLoop, skill_id="sk-1", lifecycle=SkillLifecycle.CANDIDATE, **kw):
    defaults = dict(
        skill_id=skill_id,
        name=f"skill-{skill_id}",
        skill_class=SkillClass.PRIMITIVE,
        effect_class=EffectClass.INTERNAL_PURE,
        determinism_class=DeterminismClass.DETERMINISTIC,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.STRONG,
        lifecycle=lifecycle,
    )
    defaults.update(kw)
    descriptor = SkillDescriptor(**defaults)
    loop.runtime.skill_registry.register(descriptor)
    return descriptor


class TestSkillRuntimeGoldenScenarios:
    """7 golden scenarios proving skills are live in the runtime."""

    def test_01_primitive_skill_success_through_runtime(self):
        """A registered primitive skill executes through the governed path."""
        loop = _make_loop()
        _register_skill(loop, "sk-obs", name="shell_command")

        report = loop.run_skill(SkillRequest(
            request_id="req-1",
            subject_id="operator-1",
            goal_id="goal-1",
            skill_id="sk-obs",
        ))

        assert isinstance(report, SkillRunReport)
        assert report.skill_id == "sk-obs"
        assert report.execution_record is not None
        # Execution went through the governed step executor
        assert report.execution_record.outcome is not None

    def test_02_skill_not_found_returns_structured_error(self):
        """Requesting a non-existent skill returns a typed error."""
        loop = _make_loop()

        report = loop.run_skill(SkillRequest(
            request_id="req-2",
            subject_id="operator-1",
            goal_id="goal-2",
            skill_id="missing-skill",
        ))

        assert report.status is SkillOutcomeStatus.FAILED
        assert report.completed is False
        assert len(report.structured_errors) == 1
        assert report.structured_errors[0].error_code == "skill_not_found"
        assert report.structured_errors[0].message == "skill not found"
        assert "missing-skill" not in report.structured_errors[0].message

    def test_03_blocked_skill_cannot_execute(self):
        """A blocked skill is rejected with a policy error."""
        loop = _make_loop()
        _register_skill(loop, "sk-blocked", lifecycle=SkillLifecycle.BLOCKED)

        report = loop.run_skill(SkillRequest(
            request_id="req-3",
            subject_id="operator-1",
            goal_id="goal-3",
            skill_id="sk-blocked",
        ))

        assert report.status is SkillOutcomeStatus.POLICY_DENIED
        assert report.completed is False
        assert report.structured_errors[0].error_code == "skill_blocked"
        assert report.structured_errors[0].message == "skill is blocked"
        assert "sk-blocked" not in report.structured_errors[0].message

    def test_04_skill_selection_deterministic(self):
        """When no skill_id given, selection picks deterministically from registry."""
        loop = _make_loop()
        _register_skill(loop, "sk-a", confidence=0.3)
        _register_skill(loop, "sk-b", confidence=0.8)

        report = loop.run_skill(SkillRequest(
            request_id="req-4",
            subject_id="operator-1",
            goal_id="goal-4",
        ))

        assert report.selection is not None
        assert report.selection.selected_skill_id == "sk-b"  # Higher confidence wins

    def test_05_confidence_and_lifecycle_update_after_execution(self):
        """Skill confidence and lifecycle are updated after execution attempt."""
        loop = _make_loop()
        _register_skill(loop, "sk-promote", name="shell_command", confidence=0.5)

        skill = loop.runtime.skill_registry.get("sk-promote")
        assert skill.lifecycle is SkillLifecycle.CANDIDATE
        assert skill.confidence == 0.5

        report = loop.run_skill(SkillRequest(
            request_id="req-5",
            subject_id="operator-1",
            goal_id="goal-5",
            skill_id="sk-promote",
        ))

        updated = loop.runtime.skill_registry.get("sk-promote")
        # Confidence should have changed (up on success, down on failure)
        assert updated.confidence != 0.5
        # If it succeeded, lifecycle should be provisional; if failed, stays candidate
        if report.succeeded:
            assert updated.lifecycle is SkillLifecycle.PROVISIONAL
        else:
            assert updated.lifecycle is SkillLifecycle.CANDIDATE
            assert updated.confidence < 0.5  # Decreased on failure

    def test_06_skill_confidence_updates_from_outcome(self):
        """Skill confidence is updated after execution."""
        loop = _make_loop()
        _register_skill(loop, "sk-conf", confidence=0.5)

        loop.run_skill(SkillRequest(
            request_id="req-6",
            subject_id="operator-1",
            goal_id="goal-6",
            skill_id="sk-conf",
        ))

        updated = loop.runtime.skill_registry.get("sk-conf")
        # Confidence changed (up on success, down on failure)
        assert updated.confidence != 0.5

    def test_07_skill_view_model_and_console_render(self):
        """Skill run report renders cleanly through view model and console."""
        loop = _make_loop()
        _register_skill(loop, "sk-view")

        report = loop.run_skill(SkillRequest(
            request_id="req-7",
            subject_id="operator-1",
            goal_id="goal-7",
            skill_id="sk-view",
        ))

        view = SkillSummaryView.from_report(report)
        assert view.skill_id == "sk-view"
        assert view.request_id == "req-7"

        rendered = render_skill_summary(view)
        assert "=== Skill Summary ===" in rendered
        assert "sk-view" in rendered
        assert "goal-7" in rendered


class TestSkillRuntimeEdgeCases:
    def test_no_skills_registered_returns_no_skill_available(self):
        """Selection with empty registry returns structured error."""
        loop = _make_loop()

        report = loop.run_skill(SkillRequest(
            request_id="req-e1",
            subject_id="operator-1",
            goal_id="goal-e1",
        ))

        assert report.status is SkillOutcomeStatus.FAILED
        assert report.structured_errors[0].error_code == "no_skill_available"

    def test_composite_skill_through_runtime(self):
        """Composite skill executes steps in order."""
        loop = _make_loop()
        steps = (
            SkillStep(step_id="s1", name="first", action_type="shell_command"),
            SkillStep(step_id="s2", name="second", action_type="shell_command", depends_on=("s1",)),
        )
        _register_skill(loop, "sk-comp", skill_class=SkillClass.COMPOSITE, steps=steps)

        report = loop.run_skill(SkillRequest(
            request_id="req-e2",
            subject_id="operator-1",
            goal_id="goal-e2",
            skill_id="sk-comp",
        ))

        assert report.execution_record is not None
        assert len(report.execution_record.outcome.step_outcomes) >= 1

    def test_skill_run_report_succeeded_property(self):
        """SkillRunReport.succeeded reflects status correctly."""
        loop = _make_loop()

        report = loop.run_skill(SkillRequest(
            request_id="req-e3",
            subject_id="operator-1",
            goal_id="goal-e3",
            skill_id="nonexistent",
        ))

        assert report.succeeded is False


def _make_loop_with_autonomy(mode: str):
    """Build an operator loop with a specific autonomy mode."""
    config = AppConfig(autonomy_mode=mode)
    runtime = bootstrap_runtime(config=config, clock=lambda: FIXED_CLOCK)
    return OperatorLoop(runtime=runtime)


class TestSkillGovernanceChecks:
    """Verify that run_skill enforces autonomy mode and policy evaluation."""

    def test_skill_blocked_in_observe_only_mode(self):
        """Skill execution is blocked when autonomy mode is OBSERVE_ONLY."""
        loop = _make_loop_with_autonomy("observe_only")
        _register_skill(loop, "sk-obs-block", name="shell_command")

        report = loop.run_skill(SkillRequest(
            request_id="req-gov-1",
            subject_id="operator-1",
            goal_id="goal-gov-1",
            skill_id="sk-obs-block",
        ))

        assert report.status is SkillOutcomeStatus.POLICY_DENIED
        assert report.completed is False
        assert report.execution_record is None
        assert len(report.structured_errors) == 1
        assert report.structured_errors[0].error_code == "autonomy_blocked"
        assert report.structured_errors[0].message == "autonomy blocked skill execution"
        assert "observe_only" not in report.structured_errors[0].message
        status = loop.runtime.autonomy.get_status()
        assert len(status.violations) == 1
        assert status.violations[0].attempted_action == "skill execution"
        assert "sk-obs-block" not in status.violations[0].attempted_action

    def test_skill_blocked_in_suggest_only_mode(self):
        """Skill execution is blocked when autonomy mode is SUGGEST_ONLY."""
        loop = _make_loop_with_autonomy("suggest_only")
        _register_skill(loop, "sk-sug-block", name="shell_command")

        report = loop.run_skill(SkillRequest(
            request_id="req-gov-2",
            subject_id="operator-1",
            goal_id="goal-gov-2",
            skill_id="sk-sug-block",
        ))

        assert report.status is SkillOutcomeStatus.POLICY_DENIED
        assert report.completed is False
        assert report.execution_record is None
        assert len(report.structured_errors) == 1
        assert report.structured_errors[0].error_code == "autonomy_blocked"
        assert report.structured_errors[0].message == "autonomy blocked skill execution"
        assert "suggest_only" not in report.structured_errors[0].message

    def test_skill_blocked_when_policy_denies(self):
        """Skill execution is blocked when the policy engine returns deny."""
        loop = _make_loop()
        _register_skill(loop, "sk-pol-deny", name="shell_command")

        # Monkey-patch the policy engine to always deny
        original_evaluate = loop.runtime.policy_engine.evaluate

        def deny_evaluate(policy_input, decision_factory):
            return decision_factory(
                decision_id="deny-decision-1",
                subject_id=policy_input.subject_id,
                goal_id=policy_input.goal_id,
                status="deny",
                reasons=(type("R", (), {"code": "test_deny", "message": "test policy denial"}),),
                issued_at=policy_input.issued_at,
            )

        loop.runtime.policy_engine.evaluate = deny_evaluate

        report = loop.run_skill(SkillRequest(
            request_id="req-gov-3",
            subject_id="operator-1",
            goal_id="goal-gov-3",
            skill_id="sk-pol-deny",
        ))

        assert report.status is SkillOutcomeStatus.POLICY_DENIED
        assert report.completed is False
        assert report.execution_record is None
        assert len(report.structured_errors) == 1
        assert "policy_deny" in report.structured_errors[0].error_code
        assert report.structured_errors[0].message == "policy gate blocked skill execution"
        assert "deny" not in report.structured_errors[0].message

        # Restore
        loop.runtime.policy_engine.evaluate = original_evaluate

    def test_skill_blocked_by_strict_approval_policy_pack(self):
        """Strict-approval pack escalates the skill path before execution."""
        runtime = bootstrap_runtime(
            config=AppConfig(
                autonomy_mode="bounded_autonomous",
                policy_pack_id="strict-approval",
                policy_pack_version="v0.1",
            ),
            clock=lambda: FIXED_CLOCK,
        )
        loop = OperatorLoop(runtime=runtime)
        _register_skill(loop, "sk-pack-block", name="shell_command")

        report = loop.run_skill(SkillRequest(
            request_id="req-gov-pack-1",
            subject_id="operator-1",
            goal_id="goal-gov-pack-1",
            skill_id="sk-pack-block",
        ))

        assert report.status is SkillOutcomeStatus.POLICY_DENIED
        assert report.completed is False
        assert report.execution_record is None
        assert len(report.structured_errors) == 1
        assert report.structured_errors[0].error_code == "policy_escalate"
        assert report.structured_errors[0].message == "policy gate blocked skill execution"
        assert "escalate" not in report.structured_errors[0].message

    def test_skill_proceeds_when_autonomy_and_policy_allow(self):
        """Skill execution proceeds when both autonomy and policy permit it."""
        loop = _make_loop()  # Default is bounded_autonomous — allows execution
        _register_skill(loop, "sk-gov-allow", name="shell_command")

        report = loop.run_skill(SkillRequest(
            request_id="req-gov-4",
            subject_id="operator-1",
            goal_id="goal-gov-4",
            skill_id="sk-gov-allow",
        ))

        # Should not be POLICY_DENIED
        assert report.status is not SkillOutcomeStatus.POLICY_DENIED
        # Execution record should exist (skill was actually attempted)
        assert report.execution_record is not None
        assert report.skill_id == "sk-gov-allow"
