"""Purpose: goal reasoning engine — decomposition, prioritisation, execution, replanning.
Governance scope: goal lifecycle management, plan creation, sub-goal execution, and replanning only.
Dependencies: goal contracts, invariant helpers.
Invariants:
  - No sub-goal may execute without an accepted plan.
  - Failed sub-goals move the goal to failed or replanning.
  - Replanning always produces a GoalReplanRecord.
  - Priority sorting is deterministic.
  - Clock function is injected for testability.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Protocol

from mcoi_runtime.contracts.goal import (
    GOAL_PRIORITY_RANK,
    GoalDescriptor,
    GoalExecutionState,
    GoalPlan,
    GoalReplanRecord,
    GoalStatus,
    SubGoal,
    SubGoalStatus,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


class SubGoalExecutor(Protocol):
    """Protocol for executing a single sub-goal.

    Implementations provide the actual execution logic (skill dispatch, workflow trigger, etc.).
    Returns the sub-goal with an updated status (completed or failed).
    """

    def execute_sub_goal(self, sub_goal: SubGoal) -> SubGoal: ...


class GoalReasoningEngine:
    """Decomposes goals into plans, executes sub-goals, and supports replanning.

    All timestamps are produced by the injected clock function for determinism.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock

    # --- Goal acceptance ---

    def accept_goal(self, descriptor: GoalDescriptor) -> GoalExecutionState:
        """Accept a proposed goal and produce its initial execution state."""
        if not isinstance(descriptor, GoalDescriptor):
            raise RuntimeCoreInvariantError("descriptor must be a GoalDescriptor instance")
        return GoalExecutionState(
            goal_id=descriptor.goal_id,
            status=GoalStatus.ACCEPTED,
            updated_at=self._clock(),
        )

    # --- Plan creation ---

    def create_plan(
        self,
        goal: GoalDescriptor,
        sub_goals: tuple[SubGoal, ...],
        *,
        version: int = 1,
    ) -> GoalPlan:
        """Create a versioned plan for a goal from the given sub-goals.

        The GoalPlan constructor validates that sub_goals is non-empty and
        that predecessors form a DAG.
        """
        return self._build_plan(goal.goal_id, sub_goals, version=version)

    # --- Sub-goal execution ---

    def execute_next_sub_goal(
        self,
        state: GoalExecutionState,
        plan: GoalPlan,
        executor: SubGoalExecutor,
    ) -> GoalExecutionState:
        """Execute the next eligible sub-goal and return an updated execution state.

        A sub-goal is eligible when all its predecessors are in completed_sub_goals.
        If no sub-goal is eligible the state is returned unchanged.

        On failure the goal moves to FAILED. The caller may choose to replan.
        """
        if state.current_plan_id is None:
            raise RuntimeCoreInvariantError("no plan assigned; cannot execute sub-goals")

        if state.status not in (GoalStatus.EXECUTING, GoalStatus.ACCEPTED, GoalStatus.PLANNING):
            raise RuntimeCoreInvariantError(
                f"goal is in {state.status.value} state; cannot execute sub-goals"
            )

        completed = set(state.completed_sub_goals)
        failed = set(state.failed_sub_goals)

        # Find next eligible sub-goal (deterministic: first by sub_goal_id)
        eligible: SubGoal | None = None
        for sg in sorted(plan.sub_goals, key=lambda s: s.sub_goal_id):
            if sg.sub_goal_id in completed or sg.sub_goal_id in failed:
                continue
            if all(pred in completed for pred in sg.predecessors):
                eligible = sg
                break

        if eligible is None:
            # All sub-goals done or blocked — check if we're fully complete
            all_ids = {sg.sub_goal_id for sg in plan.sub_goals}
            if completed >= all_ids:
                return GoalExecutionState(
                    goal_id=state.goal_id,
                    status=GoalStatus.COMPLETED,
                    current_plan_id=state.current_plan_id,
                    completed_sub_goals=state.completed_sub_goals,
                    failed_sub_goals=state.failed_sub_goals,
                    updated_at=self._clock(),
                )
            return state

        result = executor.execute_sub_goal(eligible)

        if result.status is SubGoalStatus.COMPLETED:
            new_completed = state.completed_sub_goals + (eligible.sub_goal_id,)
            # Check if all sub-goals are now complete
            all_ids = {sg.sub_goal_id for sg in plan.sub_goals}
            new_status = GoalStatus.EXECUTING
            if set(new_completed) >= all_ids:
                new_status = GoalStatus.COMPLETED
            return GoalExecutionState(
                goal_id=state.goal_id,
                status=new_status,
                current_plan_id=state.current_plan_id,
                completed_sub_goals=new_completed,
                failed_sub_goals=state.failed_sub_goals,
                updated_at=self._clock(),
            )

        if result.status is SubGoalStatus.FAILED:
            new_failed = state.failed_sub_goals + (eligible.sub_goal_id,)
            return GoalExecutionState(
                goal_id=state.goal_id,
                status=GoalStatus.FAILED,
                current_plan_id=state.current_plan_id,
                completed_sub_goals=state.completed_sub_goals,
                failed_sub_goals=new_failed,
                updated_at=self._clock(),
            )

        # Any other status: return state unchanged
        return state

    # --- Replanning ---

    def replan(
        self,
        state: GoalExecutionState,
        old_plan: GoalPlan,
        new_sub_goals: tuple[SubGoal, ...],
        reason: str,
    ) -> tuple[GoalPlan, GoalReplanRecord]:
        """Create a new plan to replace the old one, with an audit record.

        Returns (new_plan, replan_record).
        """
        ensure_non_empty_text("reason", reason)
        new_version = old_plan.version + 1
        new_plan = self._build_plan(state.goal_id, new_sub_goals, version=new_version)
        record = GoalReplanRecord(
            goal_id=state.goal_id,
            previous_plan_id=old_plan.plan_id,
            new_plan_id=new_plan.plan_id,
            reason=reason,
            replanned_at=self._clock(),
        )
        return new_plan, record

    # --- Deadline checking ---

    def check_deadline(
        self,
        state: GoalExecutionState,
        goal: GoalDescriptor,
        now: str,
    ) -> bool:
        """Return True if the goal's deadline has expired relative to *now*.

        Returns False if the goal has no deadline.
        """
        if goal.deadline is None:
            return False
        deadline_dt = datetime.fromisoformat(goal.deadline.replace("Z", "+00:00"))
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
        return now_dt >= deadline_dt

    # --- Priority sorting ---

    def priority_sort(self, goals: list[GoalDescriptor]) -> list[GoalDescriptor]:
        """Sort goals by priority (critical first) then deadline (earliest first).

        Goals without deadlines sort after those with deadlines at the same priority.
        """
        _MAX_DEADLINE = "9999-12-31T23:59:59+00:00"

        def sort_key(g: GoalDescriptor) -> tuple[int, str]:
            rank = GOAL_PRIORITY_RANK.get(g.priority, 99)
            deadline = g.deadline if g.deadline is not None else _MAX_DEADLINE
            return (rank, deadline)

        return sorted(goals, key=sort_key)

    def _build_plan(
        self,
        goal_id: str,
        sub_goals: tuple[SubGoal, ...],
        *,
        version: int,
    ) -> GoalPlan:
        """Build a plan directly from explicit goal identity and sub-goals."""
        plan_created_at = self._clock()
        plan_id = stable_identifier("goal-plan", {
            "goal_id": goal_id,
            "version": version,
            "created_at": plan_created_at,
        })
        return GoalPlan(
            plan_id=plan_id,
            goal_id=goal_id,
            sub_goals=sub_goals,
            created_at=self._clock(),
            version=version,
        )
