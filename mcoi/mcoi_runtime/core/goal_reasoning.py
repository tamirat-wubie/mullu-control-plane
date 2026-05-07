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
        self._descriptors: dict[str, GoalDescriptor] = {}
        self._states: dict[str, GoalExecutionState] = {}
        self._plans: dict[str, GoalPlan] = {}
        self._replan_records: dict[str, GoalReplanRecord] = {}

    def restore_goal(
        self,
        descriptor: GoalDescriptor,
        state: GoalExecutionState,
    ) -> tuple[GoalDescriptor, GoalExecutionState]:
        """Restore an exact persisted goal descriptor and state without replay."""
        if not isinstance(descriptor, GoalDescriptor):
            raise RuntimeCoreInvariantError("descriptor must be a GoalDescriptor instance")
        if not isinstance(state, GoalExecutionState):
            raise RuntimeCoreInvariantError("state must be a GoalExecutionState instance")
        if descriptor.goal_id != state.goal_id:
            raise RuntimeCoreInvariantError("descriptor and state goal_id must match")
        if descriptor.goal_id in self._descriptors or descriptor.goal_id in self._states:
            raise RuntimeCoreInvariantError(f"goal already restored: {descriptor.goal_id}")
        self._descriptors[descriptor.goal_id] = descriptor
        self._states[state.goal_id] = state
        return descriptor, state

    def restore_plan(self, plan: GoalPlan) -> GoalPlan:
        """Restore an exact persisted goal plan without replay."""
        if not isinstance(plan, GoalPlan):
            raise RuntimeCoreInvariantError("plan must be a GoalPlan instance")
        if plan.goal_id not in self._descriptors:
            raise RuntimeCoreInvariantError(
                "goal descriptor must be restored before plan"
            )
        if plan.plan_id in self._plans:
            raise RuntimeCoreInvariantError(f"goal plan already restored: {plan.plan_id}")
        self._plans[plan.plan_id] = plan
        return plan

    def restore_replan_record(self, record: GoalReplanRecord) -> GoalReplanRecord:
        """Restore an exact persisted goal replan record without replay."""
        if not isinstance(record, GoalReplanRecord):
            raise RuntimeCoreInvariantError("record must be a GoalReplanRecord instance")
        if record.goal_id not in self._descriptors:
            raise RuntimeCoreInvariantError(
                "goal descriptor must be restored before replan record"
            )
        if record.previous_plan_id not in self._plans or record.new_plan_id not in self._plans:
            raise RuntimeCoreInvariantError(
                "replan record must reference restored plans"
            )
        record_key = f"{record.goal_id}:{record.new_plan_id}"
        if record_key in self._replan_records:
            raise RuntimeCoreInvariantError(
                f"goal replan record already restored: {record_key}"
            )
        self._replan_records[record_key] = record
        return record

    def get_goal_descriptor(self, goal_id: str) -> GoalDescriptor | None:
        """Return a goal descriptor by identifier without mutating engine state."""
        return self._descriptors.get(goal_id)

    def get_goal_state(self, goal_id: str) -> GoalExecutionState | None:
        """Return a goal execution state by identifier without mutating engine state."""
        return self._states.get(goal_id)

    def get_plan(self, plan_id: str) -> GoalPlan | None:
        """Return a goal plan by identifier without mutating engine state."""
        return self._plans.get(plan_id)

    def list_goal_descriptors(self) -> tuple[GoalDescriptor, ...]:
        """Return all goal descriptors in deterministic identifier order."""
        return tuple(self._descriptors[goal_id] for goal_id in sorted(self._descriptors))

    def list_goal_states(self) -> tuple[GoalExecutionState, ...]:
        """Return all goal execution states in deterministic identifier order."""
        return tuple(self._states[goal_id] for goal_id in sorted(self._states))

    def list_plans(self) -> tuple[GoalPlan, ...]:
        """Return all goal plans in deterministic identifier order."""
        return tuple(self._plans[plan_id] for plan_id in sorted(self._plans))

    def list_replan_records(self) -> tuple[GoalReplanRecord, ...]:
        """Return all goal replan records in deterministic identifier order."""
        return tuple(
            self._replan_records[record_key]
            for record_key in sorted(self._replan_records)
        )

    # --- Goal acceptance ---

    def accept_goal(self, descriptor: GoalDescriptor) -> GoalExecutionState:
        """Accept a proposed goal and produce its initial execution state."""
        if not isinstance(descriptor, GoalDescriptor):
            raise RuntimeCoreInvariantError("descriptor must be a GoalDescriptor instance")
        state = GoalExecutionState(
            goal_id=descriptor.goal_id,
            status=GoalStatus.ACCEPTED,
            updated_at=self._clock(),
        )
        self._descriptors[descriptor.goal_id] = descriptor
        self._states[state.goal_id] = state
        return state

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
        plan = self._build_plan(goal.goal_id, sub_goals, version=version)
        self._descriptors[goal.goal_id] = goal
        self._plans[plan.plan_id] = plan
        return plan

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
                "goal is not executable in current state; cannot execute sub-goals"
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
                result_state = GoalExecutionState(
                    goal_id=state.goal_id,
                    status=GoalStatus.COMPLETED,
                    current_plan_id=state.current_plan_id,
                    completed_sub_goals=state.completed_sub_goals,
                    failed_sub_goals=state.failed_sub_goals,
                    updated_at=self._clock(),
                )
                self._states[result_state.goal_id] = result_state
                return result_state
            return state

        result = executor.execute_sub_goal(eligible)

        if result.status is SubGoalStatus.COMPLETED:
            new_completed = state.completed_sub_goals + (eligible.sub_goal_id,)
            # Check if all sub-goals are now complete
            all_ids = {sg.sub_goal_id for sg in plan.sub_goals}
            new_status = GoalStatus.EXECUTING
            if set(new_completed) >= all_ids:
                new_status = GoalStatus.COMPLETED
            result_state = GoalExecutionState(
                goal_id=state.goal_id,
                status=new_status,
                current_plan_id=state.current_plan_id,
                completed_sub_goals=new_completed,
                failed_sub_goals=state.failed_sub_goals,
                updated_at=self._clock(),
            )
            self._states[result_state.goal_id] = result_state
            return result_state

        if result.status is SubGoalStatus.FAILED:
            new_failed = state.failed_sub_goals + (eligible.sub_goal_id,)
            result_state = GoalExecutionState(
                goal_id=state.goal_id,
                status=GoalStatus.FAILED,
                current_plan_id=state.current_plan_id,
                completed_sub_goals=state.completed_sub_goals,
                failed_sub_goals=new_failed,
                updated_at=self._clock(),
            )
            self._states[result_state.goal_id] = result_state
            return result_state

        # Any other status: return state unchanged
        self._states[state.goal_id] = state
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
        self._plans[new_plan.plan_id] = new_plan
        self._replan_records[f"{record.goal_id}:{record.new_plan_id}"] = record
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
