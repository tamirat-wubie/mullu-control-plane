"""Golden scenario tests for goal runtime integration.

Proves that goals are first-class in the live operator runtime path.
"""

from __future__ import annotations

import sys

import pytest

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.console import render_goal_summary
from mcoi_runtime.app.operator_loop import GoalRunReport, OperatorLoop, SkillRequest
from mcoi_runtime.app.view_models import GoalSummaryView
from mcoi_runtime.contracts.goal import (
    GoalDescriptor,
    GoalPriority,
    GoalStatus,
    SubGoal,
    SubGoalStatus,
)
from mcoi_runtime.contracts.autonomy import AutonomyMode
from mcoi_runtime.contracts.policy import PolicyDecisionStatus
from mcoi_runtime.contracts.skill import (
    DeterminismClass,
    EffectClass,
    SkillClass,
    SkillDescriptor,
    SkillLifecycle,
    TrustClass,
    VerificationStrength,
)


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


def _make_loop():
    runtime = bootstrap_runtime(clock=lambda: FIXED_CLOCK)
    return OperatorLoop(runtime=runtime)


def _make_loop_with_autonomy(mode: str):
    config = AppConfig(autonomy_mode=mode)
    runtime = bootstrap_runtime(config=config, clock=lambda: FIXED_CLOCK)
    return OperatorLoop(runtime=runtime)


def _register_skill(loop: OperatorLoop, skill_id="sk-1", **kw):
    defaults = dict(
        skill_id=skill_id,
        name=f"skill-{skill_id}",
        skill_class=SkillClass.PRIMITIVE,
        effect_class=EffectClass.INTERNAL_PURE,
        determinism_class=DeterminismClass.DETERMINISTIC,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.STRONG,
        lifecycle=SkillLifecycle.CANDIDATE,
    )
    defaults.update(kw)
    descriptor = SkillDescriptor(**defaults)
    loop.runtime.skill_registry.register(descriptor)
    return descriptor


def _make_goal(goal_id="goal-1", sub_goals=None):
    metadata = {}
    if sub_goals is not None:
        metadata["sub_goals"] = sub_goals
    return GoalDescriptor(
        goal_id=goal_id,
        description=f"test goal {goal_id}",
        priority=GoalPriority.NORMAL,
        created_at=FIXED_CLOCK,
        metadata=metadata,
    )


def _make_request(request_id="req-g1", goal_id="goal-1", input_context=None):
    return SkillRequest(
        request_id=request_id,
        subject_id="operator-1",
        goal_id=goal_id,
        input_context=input_context,
    )


def _goal_input_context(label: str) -> dict[str, object]:
    return {
        "template_id": f"tpl-{label}",
        "command_argv": [sys.executable, "-c", f"print('{label}')"],
    }


class TestGoalRuntimeGoldenScenarios:
    """Prove that goals are live in the runtime."""

    def test_goal_with_skill_backed_sub_goal_creates_plan_and_completes(self):
        """A goal with an executable sub-goal creates a plan and completes."""
        loop = _make_loop()
        _register_skill(loop, "sk-goal", name="shell_command")
        sub_goals = (
            SubGoal(
                sub_goal_id="sg-1",
                goal_id="goal-1",
                description="sub-goal 1",
                skill_id="sk-goal",
            ),
        )
        goal = _make_goal("goal-1", sub_goals=sub_goals)
        request = _make_request(input_context=_goal_input_context("goal-1"))

        report = loop.run_goal(request, goal)

        assert isinstance(report, GoalRunReport)
        assert report.goal_id == "goal-1"
        assert report.plan_id is not None
        assert report.status is GoalStatus.COMPLETED
        assert "sg-1" in report.completed_sub_goals

    def test_sub_goal_execution_through_runtime(self):
        """Sub-goals with skill references execute through run_skill."""
        loop = _make_loop()
        _register_skill(loop, "sk-sub", name="shell_command")

        sub_goals = (
            SubGoal(
                sub_goal_id="sg-skill",
                goal_id="goal-2",
                description="skill-backed sub-goal",
                skill_id="sk-sub",
            ),
        )
        goal = _make_goal("goal-2", sub_goals=sub_goals)
        request = _make_request("req-g2", "goal-2")

        report = loop.run_goal(request, goal)

        assert report.goal_id == "goal-2"
        assert report.plan_id is not None
        # The sub-goal was attempted — it either completed or failed depending on executor
        assert len(report.completed_sub_goals) + len(report.failed_sub_goals) == 1

    def test_bare_sub_goal_fails_closed_without_handler(self):
        """Bare sub-goals must not claim completion without execution semantics."""
        loop = _make_loop()
        sub_goals = (
            SubGoal(
                sub_goal_id="sg-bare",
                goal_id="goal-bare",
                description="bare sub-goal",
            ),
        )
        goal = _make_goal("goal-bare", sub_goals=sub_goals)
        request = _make_request("req-goal-bare", "goal-bare")

        report = loop.run_goal(request, goal)

        assert report.status is GoalStatus.FAILED
        assert report.completed_sub_goals == ()
        assert report.failed_sub_goals == ("sg-bare",)
        assert len(report.errors) >= 1
        assert report.errors[0].error_code == "goal_sub_goal_failed"

    def test_workflow_backed_sub_goal_fails_closed_without_descriptor_lookup(self):
        """Workflow-backed sub-goals must not claim completion without execution."""
        loop = _make_loop()
        sub_goals = (
            SubGoal(
                sub_goal_id="sg-workflow",
                goal_id="goal-workflow",
                description="workflow-backed sub-goal",
                workflow_id="wf-missing",
            ),
        )
        goal = _make_goal("goal-workflow", sub_goals=sub_goals)
        request = _make_request("req-goal-workflow", "goal-workflow")

        report = loop.run_goal(request, goal)

        assert report.status is GoalStatus.FAILED
        assert report.completed_sub_goals == ()
        assert report.failed_sub_goals == ("sg-workflow",)
        assert len(report.errors) >= 1
        assert report.errors[0].error_code == "goal_sub_goal_failed"

    def test_failed_sub_goal_marks_goal_as_failed(self):
        """A failed sub-goal marks the goal as failed."""
        loop = _make_loop()
        # Use a skill that doesn't exist — will fail
        sub_goals = (
            SubGoal(
                sub_goal_id="sg-fail",
                goal_id="goal-3",
                description="will fail",
                skill_id="nonexistent-skill",
            ),
        )
        goal = _make_goal("goal-3", sub_goals=sub_goals)
        request = _make_request("req-g3", "goal-3")

        report = loop.run_goal(request, goal)

        assert report.status is GoalStatus.FAILED
        assert "sg-fail" in report.failed_sub_goals
        assert len(report.errors) >= 1
        assert report.errors[0].error_code == "goal_sub_goal_failed"

    def test_goal_blocked_by_autonomy_mode(self):
        """Goal execution is blocked in observe_only mode."""
        loop = _make_loop_with_autonomy("observe_only")
        goal = _make_goal("goal-4")
        request = _make_request("req-g4", "goal-4")

        report = loop.run_goal(request, goal)

        assert report.status is GoalStatus.FAILED
        assert report.plan_id is None
        assert len(report.errors) == 1
        assert report.errors[0].error_code == "autonomy_blocked"
        assert "observe_only" in report.errors[0].message

    def test_goal_blocked_by_policy(self):
        """Goal execution is blocked when the policy engine denies."""
        loop = _make_loop()
        goal = _make_goal("goal-5")
        request = _make_request("req-g5", "goal-5")

        # Monkey-patch policy to deny
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

        report = loop.run_goal(request, goal)

        assert report.status is GoalStatus.FAILED
        assert report.plan_id is None
        assert len(report.errors) == 1
        assert "policy_deny" in report.errors[0].error_code

        loop.runtime.policy_engine.evaluate = original_evaluate


    def test_sub_goal_blocked_by_autonomy_mode_mid_execution(self):
        """Autonomy mode change mid-execution blocks remaining sub-goals."""
        loop = _make_loop_with_autonomy("bounded_autonomous")
        _register_skill(loop, "sk-a", name="skill_a")
        _register_skill(loop, "sk-b", name="skill_b")

        sub_goals = (
            SubGoal(
                sub_goal_id="sg-first",
                goal_id="goal-mid",
                description="first sub-goal (should succeed)",
                skill_id="sk-a",
            ),
            SubGoal(
                sub_goal_id="sg-second",
                goal_id="goal-mid",
                description="second sub-goal (should be blocked)",
                skill_id="sk-b",
            ),
        )
        goal = _make_goal("goal-mid", sub_goals=sub_goals)
        request = _make_request("req-mid", "goal-mid")

        # Monkey-patch: after the first sub-goal executes, switch autonomy to observe_only
        original_evaluate = loop.runtime.autonomy.evaluate
        call_count = [0]

        def switching_evaluate(action_class, *, has_approval=False, action_description=""):
            call_count[0] += 1
            result = original_evaluate(
                action_class,
                has_approval=has_approval,
                action_description=action_description,
            )
            # After the goal-level autonomy check passes (call 1),
            # switch to observe_only so sub-goal execution is blocked
            if call_count[0] == 1:
                loop.runtime.autonomy._mode = AutonomyMode.OBSERVE_ONLY
            return result

        loop.runtime.autonomy.evaluate = switching_evaluate

        report = loop.run_goal(request, goal)

        assert report.status is GoalStatus.FAILED
        # Sub-goals should be blocked by observe_only mode
        assert len(report.failed_sub_goals) > 0

        # Restore
        loop.runtime.autonomy.evaluate = original_evaluate


class TestGoalViewModelAndConsole:
    """Verify view model and console rendering for goals."""

    def test_goal_view_model_and_render(self):
        loop = _make_loop()
        _register_skill(loop, "sk-view", name="shell_command")
        sub_goals = (
            SubGoal(
                sub_goal_id="sg-v1",
                goal_id="goal-v",
                description="view sub-goal",
                skill_id="sk-view",
            ),
        )
        goal = _make_goal("goal-v", sub_goals=sub_goals)
        request = _make_request("req-gv", "goal-v", input_context=_goal_input_context("goal-v"))

        report = loop.run_goal(request, goal)
        view = GoalSummaryView.from_report(report, priority="normal")

        assert view.goal_id == "goal-v"
        assert view.status == report.status.value

        rendered = render_goal_summary(view)
        assert "=== Goal Summary ===" in rendered
        assert "goal-v" in rendered


class TestGoalEdgeCaseBugs:
    """Regression tests for operator-loop goal bugs (F5, F15)."""

    def test_empty_sub_goals_after_filtering_returns_error_report(self):
        """F5: When all metadata sub-goals are invalid (not SubGoal), return
        a validation error report instead of crashing with ValueError."""
        loop = _make_loop()
        # Provide non-SubGoal items in metadata — they will all be filtered out
        goal = GoalDescriptor(
            goal_id="goal-f5",
            description="goal with invalid sub-goals",
            priority=GoalPriority.NORMAL,
            created_at=FIXED_CLOCK,
            metadata={"sub_goals": ("not-a-subgoal", 42, None)},
        )
        request = _make_request("req-f5", "goal-f5")

        # Must not raise — should return a report with validation error
        report = loop.run_goal(request, goal)

        assert isinstance(report, GoalRunReport)
        assert report.status is GoalStatus.FAILED
        assert report.plan_id is None
        assert len(report.errors) == 1
        assert report.errors[0].error_code == "goal_empty_sub_goals"

    def test_stuck_goal_returns_failed_status(self):
        """F15: When goal execution detects no progress (stuck), status must
        be FAILED — not left as EXECUTING."""
        loop = _make_loop()
        sub_goals = (
            SubGoal(
                sub_goal_id="sg-stuck",
                goal_id="goal-f15",
                description="will get stuck",
            ),
        )
        goal = _make_goal("goal-f15", sub_goals=sub_goals)
        request = _make_request("req-f15", "goal-f15")

        # Monkey-patch execute_next_sub_goal to return state unchanged (stuck)
        engine = loop.runtime.goal_reasoning_engine
        original_execute = engine.execute_next_sub_goal

        def stuck_execute(state, plan, executor):
            return state  # no progress — same identity

        engine.execute_next_sub_goal = stuck_execute

        report = loop.run_goal(request, goal)

        assert report.status is GoalStatus.FAILED
        assert len(report.errors) >= 1
        assert report.errors[0].error_code == "goal_stuck_no_progress"
        assert "blocked" in report.errors[0].message

        engine.execute_next_sub_goal = original_execute
