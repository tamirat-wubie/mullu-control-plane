"""Tests for the goal reasoning engine."""

import pytest

from mcoi_runtime.contracts.goal import (
    GoalDescriptor,
    GoalExecutionState,
    GoalPlan,
    GoalPriority,
    GoalReplanRecord,
    GoalStatus,
    SubGoal,
    SubGoalStatus,
)
from mcoi_runtime.core.goal_reasoning import GoalReasoningEngine, SubGoalExecutor
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# --- Helpers ---

_T0 = "2025-06-01T12:00:00+00:00"
_T1 = "2025-06-01T12:00:01+00:00"
_T2 = "2025-06-01T12:00:02+00:00"
_T3 = "2025-06-01T12:00:03+00:00"
_DEADLINE_FUTURE = "2025-07-01T00:00:00+00:00"
_DEADLINE_PAST = "2025-05-01T00:00:00+00:00"


def _make_clock(times: list[str]):
    """Return a clock function that yields successive timestamps."""
    it = iter(times)

    def clock() -> str:
        return next(it)

    return clock


def _descriptor(**overrides) -> GoalDescriptor:
    defaults = dict(
        goal_id="goal-001",
        description="Test goal",
        priority=GoalPriority.NORMAL,
        created_at=_T0,
    )
    defaults.update(overrides)
    return GoalDescriptor(**defaults)


def _sub_goal(**overrides) -> SubGoal:
    defaults = dict(
        sub_goal_id="sg-1",
        goal_id="goal-001",
        description="Sub-goal one",
    )
    defaults.update(overrides)
    return SubGoal(**defaults)


class _SuccessExecutor:
    """Always completes sub-goals."""

    def execute_sub_goal(self, sub_goal: SubGoal) -> SubGoal:
        return SubGoal(
            sub_goal_id=sub_goal.sub_goal_id,
            goal_id=sub_goal.goal_id,
            description=sub_goal.description,
            status=SubGoalStatus.COMPLETED,
            skill_id=sub_goal.skill_id,
            workflow_id=sub_goal.workflow_id,
            predecessors=sub_goal.predecessors,
        )


class _FailExecutor:
    """Always fails sub-goals."""

    def execute_sub_goal(self, sub_goal: SubGoal) -> SubGoal:
        return SubGoal(
            sub_goal_id=sub_goal.sub_goal_id,
            goal_id=sub_goal.goal_id,
            description=sub_goal.description,
            status=SubGoalStatus.FAILED,
            skill_id=sub_goal.skill_id,
            workflow_id=sub_goal.workflow_id,
            predecessors=sub_goal.predecessors,
        )


class _SelectiveExecutor:
    """Fails a specific sub-goal, succeeds the rest."""

    def __init__(self, fail_ids: set[str]) -> None:
        self._fail_ids = fail_ids

    def execute_sub_goal(self, sub_goal: SubGoal) -> SubGoal:
        status = SubGoalStatus.FAILED if sub_goal.sub_goal_id in self._fail_ids else SubGoalStatus.COMPLETED
        return SubGoal(
            sub_goal_id=sub_goal.sub_goal_id,
            goal_id=sub_goal.goal_id,
            description=sub_goal.description,
            status=status,
            skill_id=sub_goal.skill_id,
            workflow_id=sub_goal.workflow_id,
            predecessors=sub_goal.predecessors,
        )


# --- Accept goal ---


class TestAcceptGoal:
    def test_produces_accepted_state(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0]))
        goal = _descriptor()
        state = engine.accept_goal(goal)
        assert state.goal_id == "goal-001"
        assert state.status is GoalStatus.ACCEPTED
        assert state.updated_at == _T0
        assert state.current_plan_id is None
        assert state.completed_sub_goals == ()
        assert state.failed_sub_goals == ()

    def test_rejects_non_descriptor(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0]))
        with pytest.raises(RuntimeCoreInvariantError, match="GoalDescriptor"):
            engine.accept_goal("not-a-descriptor")  # type: ignore[arg-type]


# --- Plan creation ---


class TestCreatePlan:
    def test_creates_plan_with_sub_goals(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0, _T0]))
        goal = _descriptor()
        sg1 = _sub_goal(sub_goal_id="sg-a")
        sg2 = _sub_goal(sub_goal_id="sg-b", predecessors=("sg-a",))
        plan = engine.create_plan(goal, (sg1, sg2))
        assert plan.goal_id == "goal-001"
        assert len(plan.sub_goals) == 2
        assert plan.version == 1
        assert plan.plan_id.startswith("goal-plan-")

    def test_version_propagated(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0, _T0]))
        goal = _descriptor()
        plan = engine.create_plan(goal, (_sub_goal(),), version=3)
        assert plan.version == 3

    def test_empty_sub_goals_rejected(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0, _T0]))
        goal = _descriptor()
        with pytest.raises(ValueError, match="sub_goals"):
            engine.create_plan(goal, ())


# --- Sequential sub-goal execution ---


class TestExecuteNextSubGoal:
    def test_single_sub_goal_completes(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0, _T1]))
        sg = _sub_goal(sub_goal_id="sg-a")
        plan = GoalPlan(
            plan_id="plan-001",
            goal_id="goal-001",
            sub_goals=(sg,),
            created_at=_T0,
        )
        state = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.EXECUTING,
            current_plan_id="plan-001",
            updated_at=_T0,
        )
        new_state = engine.execute_next_sub_goal(state, plan, _SuccessExecutor())
        assert new_state.status is GoalStatus.COMPLETED
        assert "sg-a" in new_state.completed_sub_goals

    def test_sequential_execution(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0, _T1, _T2, _T3]))
        sg1 = _sub_goal(sub_goal_id="sg-a")
        sg2 = _sub_goal(sub_goal_id="sg-b", predecessors=("sg-a",))
        plan = GoalPlan(
            plan_id="plan-001",
            goal_id="goal-001",
            sub_goals=(sg1, sg2),
            created_at=_T0,
        )
        state = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.EXECUTING,
            current_plan_id="plan-001",
            updated_at=_T0,
        )
        # Execute first
        state = engine.execute_next_sub_goal(state, plan, _SuccessExecutor())
        assert state.status is GoalStatus.EXECUTING
        assert "sg-a" in state.completed_sub_goals

        # Execute second
        state = engine.execute_next_sub_goal(state, plan, _SuccessExecutor())
        assert state.status is GoalStatus.COMPLETED
        assert "sg-b" in state.completed_sub_goals

    def test_no_execution_without_plan(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0]))
        plan = GoalPlan(
            plan_id="plan-001",
            goal_id="goal-001",
            sub_goals=(_sub_goal(),),
            created_at=_T0,
        )
        state = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.EXECUTING,
            current_plan_id=None,
            updated_at=_T0,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="no plan assigned"):
            engine.execute_next_sub_goal(state, plan, _SuccessExecutor())

    def test_non_executable_state_is_bounded(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0]))
        plan = GoalPlan(
            plan_id="plan-001",
            goal_id="goal-001",
            sub_goals=(_sub_goal(),),
            created_at=_T0,
        )
        state = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.FAILED,
            current_plan_id="plan-001",
            updated_at=_T0,
        )
        with pytest.raises(
            RuntimeCoreInvariantError,
            match="^goal is not executable in current state; cannot execute sub-goals$",
        ) as exc_info:
            engine.execute_next_sub_goal(state, plan, _SuccessExecutor())
        assert "failed" not in str(exc_info.value).lower()


# --- Failed sub-goal triggers replanning path ---


class TestFailedSubGoal:
    def test_failed_sub_goal_moves_to_failed(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0, _T1]))
        sg = _sub_goal(sub_goal_id="sg-a")
        plan = GoalPlan(
            plan_id="plan-001",
            goal_id="goal-001",
            sub_goals=(sg,),
            created_at=_T0,
        )
        state = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.EXECUTING,
            current_plan_id="plan-001",
            updated_at=_T0,
        )
        new_state = engine.execute_next_sub_goal(state, plan, _FailExecutor())
        assert new_state.status is GoalStatus.FAILED
        assert "sg-a" in new_state.failed_sub_goals

    def test_selective_failure(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0, _T1, _T2]))
        sg1 = _sub_goal(sub_goal_id="sg-a")
        sg2 = _sub_goal(sub_goal_id="sg-b")
        plan = GoalPlan(
            plan_id="plan-001",
            goal_id="goal-001",
            sub_goals=(sg1, sg2),
            created_at=_T0,
        )
        state = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.EXECUTING,
            current_plan_id="plan-001",
            updated_at=_T0,
        )
        executor = _SelectiveExecutor(fail_ids={"sg-a"})
        new_state = engine.execute_next_sub_goal(state, plan, executor)
        assert new_state.status is GoalStatus.FAILED
        assert "sg-a" in new_state.failed_sub_goals


# --- Deadline expiry detection ---


class TestCheckDeadline:
    def test_no_deadline_returns_false(self):
        engine = GoalReasoningEngine(clock=_make_clock([]))
        goal = _descriptor()
        state = GoalExecutionState(
            goal_id="goal-001", status=GoalStatus.EXECUTING, updated_at=_T0,
        )
        assert engine.check_deadline(state, goal, _T0) is False

    def test_future_deadline_not_expired(self):
        engine = GoalReasoningEngine(clock=_make_clock([]))
        goal = _descriptor(deadline=_DEADLINE_FUTURE)
        state = GoalExecutionState(
            goal_id="goal-001", status=GoalStatus.EXECUTING, updated_at=_T0,
        )
        assert engine.check_deadline(state, goal, _T0) is False

    def test_past_deadline_expired(self):
        engine = GoalReasoningEngine(clock=_make_clock([]))
        goal = _descriptor(deadline=_DEADLINE_PAST)
        state = GoalExecutionState(
            goal_id="goal-001", status=GoalStatus.EXECUTING, updated_at=_T0,
        )
        assert engine.check_deadline(state, goal, _T0) is True

    def test_exact_deadline_expired(self):
        engine = GoalReasoningEngine(clock=_make_clock([]))
        goal = _descriptor(deadline=_T0)
        state = GoalExecutionState(
            goal_id="goal-001", status=GoalStatus.EXECUTING, updated_at=_T0,
        )
        # now == deadline => expired
        assert engine.check_deadline(state, goal, _T0) is True


# --- Priority sorting ---


class TestPrioritySort:
    def test_basic_priority_order(self):
        engine = GoalReasoningEngine(clock=_make_clock([]))
        goals = [
            _descriptor(goal_id="g-bg", priority=GoalPriority.BACKGROUND),
            _descriptor(goal_id="g-crit", priority=GoalPriority.CRITICAL),
            _descriptor(goal_id="g-norm", priority=GoalPriority.NORMAL),
            _descriptor(goal_id="g-high", priority=GoalPriority.HIGH),
            _descriptor(goal_id="g-low", priority=GoalPriority.LOW),
        ]
        sorted_goals = engine.priority_sort(goals)
        ids = [g.goal_id for g in sorted_goals]
        assert ids == ["g-crit", "g-high", "g-norm", "g-low", "g-bg"]

    def test_deadline_tiebreak(self):
        engine = GoalReasoningEngine(clock=_make_clock([]))
        early = "2025-06-10T00:00:00+00:00"
        late = "2025-06-20T00:00:00+00:00"
        goals = [
            _descriptor(goal_id="g-late", priority=GoalPriority.NORMAL, deadline=late),
            _descriptor(goal_id="g-early", priority=GoalPriority.NORMAL, deadline=early),
        ]
        sorted_goals = engine.priority_sort(goals)
        assert sorted_goals[0].goal_id == "g-early"
        assert sorted_goals[1].goal_id == "g-late"

    def test_no_deadline_sorts_after_deadline(self):
        engine = GoalReasoningEngine(clock=_make_clock([]))
        goals = [
            _descriptor(goal_id="g-none", priority=GoalPriority.NORMAL, deadline=None),
            _descriptor(goal_id="g-dl", priority=GoalPriority.NORMAL, deadline=_DEADLINE_FUTURE),
        ]
        sorted_goals = engine.priority_sort(goals)
        assert sorted_goals[0].goal_id == "g-dl"
        assert sorted_goals[1].goal_id == "g-none"

    def test_empty_list(self):
        engine = GoalReasoningEngine(clock=_make_clock([]))
        assert engine.priority_sort([]) == []


# --- Replanning ---


class TestReplan:
    def test_produces_new_plan_and_record(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0, _T0, _T1]))
        old_plan = GoalPlan(
            plan_id="plan-001",
            goal_id="goal-001",
            sub_goals=(_sub_goal(sub_goal_id="sg-old"),),
            created_at=_T0,
            version=1,
        )
        state = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.REPLANNING,
            current_plan_id="plan-001",
            updated_at=_T0,
        )
        new_sg = _sub_goal(sub_goal_id="sg-new")
        new_plan, record = engine.replan(state, old_plan, (new_sg,), "sg-old failed")

        assert new_plan.version == 2
        assert new_plan.goal_id == "goal-001"
        assert len(new_plan.sub_goals) == 1
        assert new_plan.sub_goals[0].sub_goal_id == "sg-new"

        assert isinstance(record, GoalReplanRecord)
        assert record.previous_plan_id == "plan-001"
        assert record.new_plan_id == new_plan.plan_id
        assert record.reason == "sg-old failed"
        assert new_plan.created_at == _T0
        assert record.replanned_at == _T1

    def test_replan_empty_reason_rejected(self):
        engine = GoalReasoningEngine(clock=_make_clock([_T0]))
        old_plan = GoalPlan(
            plan_id="plan-001",
            goal_id="goal-001",
            sub_goals=(_sub_goal(),),
            created_at=_T0,
        )
        state = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.REPLANNING,
            current_plan_id="plan-001",
            updated_at=_T0,
        )
        with pytest.raises(
            RuntimeCoreInvariantError,
            match="^reason must be a non-empty string$",
        ) as exc_info:
            engine.replan(state, old_plan, (_sub_goal(sub_goal_id="sg-x"),), "")
        assert str(exc_info.value) == "reason must be a non-empty string"


# --- Clock injection determinism ---


class TestClockDeterminism:
    def test_timestamps_come_from_clock(self):
        clock = _make_clock([_T0, _T1, _T2])
        engine = GoalReasoningEngine(clock=clock)
        goal = _descriptor()

        state = engine.accept_goal(goal)
        assert state.updated_at == _T0

        plan = engine.create_plan(goal, (_sub_goal(),))
        # create_plan calls clock twice (stable_identifier + created_at)
        assert plan.created_at == _T2
