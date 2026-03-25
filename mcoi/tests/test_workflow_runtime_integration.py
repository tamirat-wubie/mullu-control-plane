"""Golden scenario tests for workflow runtime integration.

Proves that workflows are first-class in the live operator runtime path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.console import render_workflow_summary
from mcoi_runtime.app.operator_loop import OperatorLoop, SkillRequest, WorkflowRunReport
from mcoi_runtime.app.view_models import WorkflowSummaryView
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
from mcoi_runtime.contracts.workflow import (
    StageType,
    WorkflowDescriptor,
    WorkflowStage,
    WorkflowStatus,
)
from mcoi_runtime.persistence.workflow_store import WorkflowStore


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


def _make_loop():
    runtime = bootstrap_runtime(clock=lambda: FIXED_CLOCK)
    return OperatorLoop(runtime=runtime)


def _make_loop_with_autonomy(mode: str):
    config = AppConfig(autonomy_mode=mode)
    runtime = bootstrap_runtime(config=config, clock=lambda: FIXED_CLOCK)
    return OperatorLoop(runtime=runtime)


def _make_loop_with_store(tmp_path: Path):
    store = WorkflowStore(tmp_path / "workflows")
    runtime = bootstrap_runtime(clock=lambda: FIXED_CLOCK, workflow_store=store)
    return OperatorLoop(runtime=runtime), store


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


def _make_request(request_id="req-w1", goal_id="goal-1"):
    return SkillRequest(
        request_id=request_id,
        subject_id="operator-1",
        goal_id=goal_id,
    )


def _make_linear_workflow(workflow_id="wf-1"):
    """Create a simple 2-stage linear workflow (no skill references)."""
    return WorkflowDescriptor(
        workflow_id=workflow_id,
        name="linear-test",
        stages=(
            WorkflowStage(stage_id="s1", stage_type=StageType.OBSERVATION),
            WorkflowStage(
                stage_id="s2",
                stage_type=StageType.OBSERVATION,
                predecessors=("s1",),
            ),
        ),
        created_at=FIXED_CLOCK,
    )


class TestWorkflowRuntimeGoldenScenarios:
    """Prove that workflows are live in the runtime."""

    def test_linear_workflow_executes_stages_in_order(self):
        """A linear workflow executes stages in topological order."""
        loop = _make_loop()
        wf = _make_linear_workflow()
        request = _make_request()

        report = loop.run_workflow(request, wf)

        assert isinstance(report, WorkflowRunReport)
        assert report.workflow_id == "wf-1"
        assert report.status is WorkflowStatus.COMPLETED
        assert len(report.stage_summaries) == 2
        # s1 should be first
        assert report.stage_summaries[0].stage_id == "s1"
        assert report.stage_summaries[1].stage_id == "s2"

    def test_failed_stage_stops_workflow(self):
        """A failed stage stops the workflow and marks it failed."""
        loop = _make_loop()
        # Use a skill that doesn't exist — will fail
        wf = WorkflowDescriptor(
            workflow_id="wf-fail",
            name="fail-test",
            stages=(
                WorkflowStage(
                    stage_id="s1",
                    stage_type=StageType.SKILL_EXECUTION,
                    skill_id="nonexistent-skill",
                ),
                WorkflowStage(
                    stage_id="s2",
                    stage_type=StageType.OBSERVATION,
                    predecessors=("s1",),
                ),
            ),
            created_at=FIXED_CLOCK,
        )
        request = _make_request("req-w2", "goal-2")

        report = loop.run_workflow(request, wf)

        assert report.status is WorkflowStatus.FAILED
        assert len(report.stage_summaries) >= 1
        assert report.stage_summaries[0].stage_id == "s1"
        assert report.stage_summaries[0].status.value == "failed"

    def test_workflow_blocked_by_autonomy_mode(self):
        """Workflow execution is blocked in observe_only mode."""
        loop = _make_loop_with_autonomy("observe_only")
        wf = _make_linear_workflow()
        request = _make_request("req-w3", "goal-3")

        report = loop.run_workflow(request, wf)

        assert report.status is WorkflowStatus.FAILED
        assert len(report.errors) == 1
        assert report.errors[0].error_code == "autonomy_blocked"
        assert "observe_only" in report.errors[0].message

    def test_workflow_persistence_round_trip(self, tmp_path: Path):
        """Workflow execution record survives save/load cycle."""
        loop, store = _make_loop_with_store(tmp_path)
        wf = _make_linear_workflow("wf-persist")
        request = _make_request("req-w4", "goal-4")

        report = loop.run_workflow(request, wf)

        assert report.status is WorkflowStatus.COMPLETED
        assert report.execution_id != ""

        # Verify the record was persisted
        loaded = store.load_execution_record(report.execution_id)
        assert loaded.workflow_id == "wf-persist"
        assert loaded.status is WorkflowStatus.COMPLETED
        assert len(loaded.stage_results) == 2


class TestWorkflowGovernanceChecks:
    """Verify governance checks on workflow execution."""

    def test_workflow_blocked_in_suggest_only_mode(self):
        """Workflow execution is blocked in suggest_only mode."""
        loop = _make_loop_with_autonomy("suggest_only")
        wf = _make_linear_workflow()
        request = _make_request("req-wg1", "goal-g1")

        report = loop.run_workflow(request, wf)

        assert report.status is WorkflowStatus.FAILED
        assert report.errors[0].error_code == "autonomy_blocked"

    def test_workflow_blocked_when_policy_denies(self):
        """Workflow blocked when policy engine denies."""
        loop = _make_loop()
        wf = _make_linear_workflow()
        request = _make_request("req-wg2", "goal-g2")

        original_evaluate = loop.runtime.policy_engine.evaluate

        def deny_evaluate(policy_input, decision_factory):
            return decision_factory(
                decision_id="deny-decision-1",
                subject_id=policy_input.subject_id,
                goal_id=policy_input.goal_id,
                status="deny",
                reasons=(type("R", (), {"code": "test_deny", "message": "test deny"}),),
                issued_at=policy_input.issued_at,
            )

        loop.runtime.policy_engine.evaluate = deny_evaluate

        report = loop.run_workflow(request, wf)

        assert report.status is WorkflowStatus.FAILED
        assert "policy_deny" in report.errors[0].error_code

        loop.runtime.policy_engine.evaluate = original_evaluate


class TestWorkflowViewModelAndConsole:
    """Verify view model and console rendering for workflows."""

    def test_workflow_view_model_and_render(self):
        loop = _make_loop()
        wf = _make_linear_workflow("wf-view")
        request = _make_request("req-wv", "goal-v")

        report = loop.run_workflow(request, wf)
        view = WorkflowSummaryView.from_report(report)

        assert view.workflow_id == "wf-view"
        assert view.status == report.status.value

        rendered = render_workflow_summary(view)
        assert "=== Workflow Summary ===" in rendered
        assert "wf-view" in rendered


class TestWorkflowEdgeCaseBugs:
    """Regression tests for operator-loop workflow bugs (F14)."""

    def test_stuck_workflow_returns_failed_status(self):
        """F14: When workflow execution detects no progress (stuck), status
        must be FAILED — not left as RUNNING."""
        loop = _make_loop()
        wf = _make_linear_workflow("wf-stuck")
        request = _make_request("req-stuck", "goal-stuck")

        # Monkey-patch execute_next_stage to return record unchanged (stuck)
        engine = loop.runtime.workflow_engine
        original_execute = engine.execute_next_stage

        def stuck_execute(descriptor, record, stage_executor, context=None):
            return record  # no progress — same identity

        engine.execute_next_stage = stuck_execute

        report = loop.run_workflow(request, wf)

        assert report.status is WorkflowStatus.FAILED
        assert len(report.errors) >= 1
        assert report.errors[0].error_code == "workflow_stuck_no_progress"
        assert "blocked" in report.errors[0].message

        engine.execute_next_stage = original_execute
