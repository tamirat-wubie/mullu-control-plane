"""Tests for goal persistence: round-trip, listing, and error handling.

Proves that goal execution state, plans, and replan records survive
save/load cycles.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.contracts.goal import (
    GoalExecutionState,
    GoalPlan,
    GoalReplanRecord,
    GoalStatus,
    SubGoal,
    SubGoalStatus,
)
from mcoi_runtime.persistence.goal_store import GoalStore
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


# --- Helpers ---


def _make_sub_goal(sub_goal_id="sg-1", goal_id="goal-1", **kw):
    defaults = dict(
        sub_goal_id=sub_goal_id,
        goal_id=goal_id,
        description=f"sub-goal {sub_goal_id}",
    )
    defaults.update(kw)
    return SubGoal(**defaults)


def _make_plan(plan_id="plan-1", goal_id="goal-1", sub_goals=None):
    return GoalPlan(
        plan_id=plan_id,
        goal_id=goal_id,
        sub_goals=sub_goals or (_make_sub_goal(),),
        created_at=FIXED_CLOCK,
    )


def _make_state(goal_id="goal-1", status=GoalStatus.EXECUTING, **kw):
    defaults = dict(
        goal_id=goal_id,
        status=status,
        updated_at=FIXED_CLOCK,
    )
    defaults.update(kw)
    return GoalExecutionState(**defaults)


def _make_replan_record(goal_id="goal-1"):
    return GoalReplanRecord(
        goal_id=goal_id,
        previous_plan_id="plan-1",
        new_plan_id="plan-2",
        reason="sub-goal failed",
        replanned_at=FIXED_CLOCK,
    )


# --- GoalStore: goal state ---


class TestGoalStoreState:
    def test_save_and_load_round_trip(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        state = _make_state()
        store.save_goal_state(state)
        loaded = store.load_goal_state("goal-1")

        assert loaded.goal_id == state.goal_id
        assert loaded.status is GoalStatus.EXECUTING
        assert loaded.updated_at == FIXED_CLOCK

    def test_completed_sub_goals_preserved(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        state = _make_state(
            completed_sub_goals=("sg-1", "sg-2"),
            current_plan_id="plan-1",
        )
        store.save_goal_state(state)
        loaded = store.load_goal_state("goal-1")

        assert loaded.completed_sub_goals == ("sg-1", "sg-2")
        assert loaded.current_plan_id == "plan-1"

    def test_failed_sub_goals_preserved(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        state = _make_state(
            status=GoalStatus.FAILED,
            failed_sub_goals=("sg-3",),
        )
        store.save_goal_state(state)
        loaded = store.load_goal_state("goal-1")

        assert loaded.status is GoalStatus.FAILED
        assert loaded.failed_sub_goals == ("sg-3",)

    def test_load_nonexistent_raises(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        with pytest.raises(PersistenceError, match=r"^goal state not found$") as excinfo:
            store.load_goal_state("missing")
        assert "missing" not in str(excinfo.value)

    def test_invalid_type_rejected(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        with pytest.raises(PersistenceError, match="GoalExecutionState"):
            store.save_goal_state("not a state")

    def test_malformed_file_fails_closed(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        goals_dir = tmp_path / "goal-data" / "goals"
        goals_dir.mkdir(parents=True)
        (goals_dir / "bad.json").write_text("not json!!")
        with pytest.raises(CorruptedDataError, match=r"^malformed JSON \(JSONDecodeError\)$"):
            store.load_goal_state("bad")

    def test_overwrite_same_id(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        state1 = _make_state(status=GoalStatus.EXECUTING)
        state2 = _make_state(status=GoalStatus.COMPLETED)
        store.save_goal_state(state1)
        store.save_goal_state(state2)
        loaded = store.load_goal_state("goal-1")
        assert loaded.status is GoalStatus.COMPLETED


# --- GoalStore: plans ---


class TestGoalStorePlan:
    def test_save_and_load_plan_round_trip(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        plan = _make_plan()
        store.save_plan(plan)
        loaded = store.load_plan("plan-1")

        assert loaded.plan_id == plan.plan_id
        assert loaded.goal_id == plan.goal_id
        assert len(loaded.sub_goals) == 1
        assert loaded.sub_goals[0].sub_goal_id == "sg-1"

    def test_plan_with_predecessors_preserved(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        sub_goals = (
            _make_sub_goal("sg-a"),
            _make_sub_goal("sg-b", predecessors=("sg-a",)),
        )
        plan = _make_plan(sub_goals=sub_goals)
        store.save_plan(plan)
        loaded = store.load_plan("plan-1")

        assert len(loaded.sub_goals) == 2
        assert loaded.sub_goals[1].predecessors == ("sg-a",)

    def test_plan_version_preserved(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        plan = _make_plan()
        store.save_plan(plan)
        loaded = store.load_plan("plan-1")
        assert loaded.version == 1

    def test_load_nonexistent_plan_raises(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        with pytest.raises(PersistenceError, match=r"^plan not found$") as excinfo:
            store.load_plan("missing")
        assert "missing" not in str(excinfo.value)

    def test_invalid_type_rejected(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        with pytest.raises(PersistenceError, match="GoalPlan"):
            store.save_plan("not a plan")


# --- GoalStore: replan records ---


class TestGoalStoreReplan:
    def test_save_replan_record(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        record = _make_replan_record()
        # Should not raise
        store.save_replan_record(record)

    def test_invalid_type_rejected(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        with pytest.raises(PersistenceError, match="GoalReplanRecord"):
            store.save_replan_record("not a record")


# --- GoalStore: listing ---


class TestGoalStoreListing:
    def test_list_goals(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        store.save_goal_state(_make_state("goal-b"))
        store.save_goal_state(_make_state("goal-a"))
        store.save_goal_state(_make_state("goal-c"))

        ids = store.list_goals()
        assert ids == ("goal-a", "goal-b", "goal-c")

    def test_list_goals_empty(self, tmp_path: Path):
        store = GoalStore(tmp_path / "goal-data")
        assert store.list_goals() == ()
