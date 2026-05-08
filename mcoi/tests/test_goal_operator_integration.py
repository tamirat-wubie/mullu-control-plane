"""Purpose: verify governed operator-surface goal-runtime reconciliation and restore flows.
Governance scope: goal operator integration only.
Dependencies: app bootstrap/operator facade, goal persistence, and autonomy enforcement.
Invariants:
  - goal restore is explicit and never automatic.
  - read-only goal assessment remains available under analyze-permitted autonomy modes.
  - invalid persisted goal witnesses fail closed before mutation.
"""

from __future__ import annotations

from pathlib import Path

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.operator_loop import GoalReconcileRequest, OperatorLoop
from mcoi_runtime.contracts.goal import (
    GoalDescriptor,
    GoalExecutionState,
    GoalPriority,
    GoalStatus,
    SubGoal,
)
from mcoi_runtime.persistence.goal_store import GoalStore


FIXED_CLOCK = "2026-03-18T12:00:00+00:00"


def _goal_runtime_bundle(
    goal_id: str,
    *,
    status: GoalStatus,
    completed_sub_goals: tuple[str, ...] = (),
    failed_sub_goals: tuple[str, ...] = (),
) -> tuple[GoalDescriptor, object, GoalExecutionState]:
    sub_goals = (
        SubGoal(
            sub_goal_id=f"{goal_id}-sg-1",
            goal_id=goal_id,
            description=f"sub-goal for {goal_id}",
            skill_id="sk-goal",
        ),
    )
    descriptor = GoalDescriptor(
        goal_id=goal_id,
        description=f"Goal {goal_id}",
        priority=GoalPriority.NORMAL,
        created_at=FIXED_CLOCK,
        metadata={"sub_goals": sub_goals},
    )
    runtime = bootstrap_runtime(clock=lambda: FIXED_CLOCK)
    plan = runtime.goal_reasoning_engine.create_plan(descriptor, sub_goals)
    state = GoalExecutionState(
        goal_id=goal_id,
        status=status,
        current_plan_id=plan.plan_id,
        updated_at=FIXED_CLOCK,
        completed_sub_goals=completed_sub_goals,
        failed_sub_goals=failed_sub_goals,
    )
    return descriptor, plan, state


def _seed_goal_store(base_path: Path) -> GoalStore:
    store = GoalStore(base_path)
    runtime = bootstrap_runtime(clock=lambda: FIXED_CLOCK)
    for descriptor, plan, state in (
        _goal_runtime_bundle("goal-active", status=GoalStatus.EXECUTING),
        _goal_runtime_bundle(
            "goal-complete",
            status=GoalStatus.COMPLETED,
            completed_sub_goals=("goal-complete-sg-1",),
        ),
        _goal_runtime_bundle(
            "goal-failed",
            status=GoalStatus.FAILED,
            failed_sub_goals=("goal-failed-sg-1",),
        ),
    ):
        runtime.goal_reasoning_engine.restore_goal(descriptor, state)
        runtime.goal_reasoning_engine.restore_plan(plan)
    store.save_state(runtime.goal_reasoning_engine)
    return store


def test_reconcile_goals_assesses_in_memory_state_under_observe_only() -> None:
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="observe_only"),
        clock=lambda: FIXED_CLOCK,
    )
    for descriptor, plan, state in (
        _goal_runtime_bundle("goal-live-active", status=GoalStatus.EXECUTING),
        _goal_runtime_bundle(
            "goal-live-complete",
            status=GoalStatus.COMPLETED,
            completed_sub_goals=("goal-live-complete-sg-1",),
        ),
    ):
        runtime.goal_reasoning_engine.restore_goal(descriptor, state)
        runtime.goal_reasoning_engine.restore_plan(plan)
    loop = OperatorLoop(runtime)

    report = loop.reconcile_goals(
        GoalReconcileRequest(
            request_id="goal-reconcile-1",
            subject_id="subject-1",
        )
    )

    assert report.restored is False
    assert report.autonomy_decision == "allowed"
    assert report.policy_status == "allow"
    assert report.goal_count == 2
    assert report.active_goal_count == 1
    assert report.completed_goal_count == 1
    assert report.failed_goal_count == 0
    assert report.plan_count == 2
    assert report.replan_count == 0
    assert report.errors == ()


def test_reconcile_goals_restores_and_filters_selected_goals(tmp_path: Path) -> None:
    store = _seed_goal_store(tmp_path / "goals")
    runtime = bootstrap_runtime(
        clock=lambda: FIXED_CLOCK,
        goal_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_goals(
        GoalReconcileRequest(
            request_id="goal-reconcile-2",
            subject_id="subject-1",
            goal_ids=("goal-complete",),
            restore_from_store=True,
        )
    )

    assert report.restored is True
    assert report.policy_status == "allow"
    assert report.goal_count == 1
    assert report.goal_ids == ("goal-complete",)
    assert report.active_goal_count == 0
    assert report.completed_goal_count == 1
    assert report.failed_goal_count == 0
    assert report.plan_count == 1
    assert report.replan_count == 0
    assert len(runtime.goal_reasoning_engine.list_goal_descriptors()) == 3
    assert report.errors == ()


def test_reconcile_goals_fails_closed_without_configured_store() -> None:
    runtime = bootstrap_runtime(clock=lambda: FIXED_CLOCK)
    loop = OperatorLoop(runtime)

    report = loop.reconcile_goals(
        GoalReconcileRequest(
            request_id="goal-reconcile-3",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.goal_count == 0
    assert report.active_goal_count == 0
    assert report.errors[0].error_code == "goal_store_not_configured"


def test_reconcile_goals_fails_closed_on_invalid_persisted_state(tmp_path: Path) -> None:
    store = _seed_goal_store(tmp_path / "goals")
    plan_path = tmp_path / "goals" / "plans" / f"{store.list_plans()[0]}.json"
    plan_path.unlink()

    runtime = bootstrap_runtime(
        clock=lambda: FIXED_CLOCK,
        goal_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_goals(
        GoalReconcileRequest(
            request_id="goal-reconcile-4",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.goal_count == 0
    assert report.active_goal_count == 0
    assert report.errors[0].error_code == "goal_restore_failed"
    assert runtime.goal_reasoning_engine.list_goal_descriptors() == ()


def test_reconcile_goals_fails_closed_on_missing_requested_goal(tmp_path: Path) -> None:
    store = _seed_goal_store(tmp_path / "goals")
    runtime = bootstrap_runtime(
        clock=lambda: FIXED_CLOCK,
        goal_store=store,
        restore_goals=True,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_goals(
        GoalReconcileRequest(
            request_id="goal-reconcile-5",
            subject_id="subject-1",
            goal_ids=("missing-goal",),
        )
    )

    assert report.restored is False
    assert report.goal_count == 0
    assert report.completed_goal_count == 0
    assert report.errors[0].error_code == "goal_runtime_missing"


def test_reconcile_goals_restore_is_blocked_when_approval_is_required(tmp_path: Path) -> None:
    store = _seed_goal_store(tmp_path / "goals")
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="approval_required"),
        clock=lambda: FIXED_CLOCK,
        goal_store=store,
    )
    loop = OperatorLoop(runtime)

    report = loop.reconcile_goals(
        GoalReconcileRequest(
            request_id="goal-reconcile-6",
            subject_id="subject-1",
            restore_from_store=True,
        )
    )

    assert report.restored is False
    assert report.goal_count == 0
    assert report.policy_decision_id is None
    assert report.autonomy_decision == "blocked_pending_approval"
    assert report.errors[0].error_code == "autonomy_blocked"
    assert runtime.goal_reasoning_engine.list_goal_descriptors() == ()
