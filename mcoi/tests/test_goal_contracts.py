"""Tests for goal reasoning contracts."""

import pytest

from mcoi_runtime.contracts.goal import (
    GOAL_PRIORITY_RANK,
    GoalDependency,
    GoalDescriptor,
    GoalExecutionState,
    GoalPlan,
    GoalPriority,
    GoalReplanRecord,
    GoalStatus,
    SubGoal,
    SubGoalStatus,
)


# --- Helpers ---

_NOW = "2025-06-01T12:00:00+00:00"
_DEADLINE = "2025-06-15T12:00:00+00:00"


def _descriptor(**overrides) -> GoalDescriptor:
    defaults = dict(
        goal_id="goal-001",
        description="Test goal",
        priority=GoalPriority.NORMAL,
        created_at=_NOW,
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


def _plan(**overrides) -> GoalPlan:
    sg = overrides.pop("sub_goals", (_sub_goal(),))
    defaults = dict(
        plan_id="plan-001",
        goal_id="goal-001",
        sub_goals=sg,
        created_at=_NOW,
    )
    defaults.update(overrides)
    return GoalPlan(**defaults)


# --- GoalDescriptor ---


class TestGoalDescriptor:
    def test_valid(self):
        g = _descriptor()
        assert g.goal_id == "goal-001"
        assert g.priority is GoalPriority.NORMAL
        assert g.deadline is None

    def test_with_deadline(self):
        g = _descriptor(deadline=_DEADLINE)
        assert g.deadline == _DEADLINE

    def test_empty_goal_id_rejected(self):
        with pytest.raises(ValueError, match="goal_id"):
            _descriptor(goal_id="")

    def test_whitespace_goal_id_rejected(self):
        with pytest.raises(ValueError, match="goal_id"):
            _descriptor(goal_id="   ")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError, match="description"):
            _descriptor(description="")

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValueError, match="priority"):
            _descriptor(priority="ultra")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _descriptor(created_at="not-a-date")

    def test_invalid_deadline_rejected(self):
        with pytest.raises(ValueError, match="deadline"):
            _descriptor(deadline="not-a-date")

    def test_frozen(self):
        g = _descriptor()
        with pytest.raises(AttributeError):
            g.goal_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        g = _descriptor(metadata={"key": "value"})
        assert g.metadata["key"] == "value"
        with pytest.raises(TypeError):
            g.metadata["new"] = "x"  # type: ignore[index]

    def test_serialization_roundtrip(self):
        g = _descriptor(deadline=_DEADLINE, metadata={"k": 1})
        d = g.to_dict()
        assert d["goal_id"] == "goal-001"
        assert d["deadline"] == _DEADLINE
        assert d["metadata"] == {"k": 1}

        j = g.to_json()
        assert '"goal_id":"goal-001"' in j


# --- GoalDependency ---


class TestGoalDependency:
    def test_valid(self):
        dep = GoalDependency(
            goal_id="goal-001",
            depends_on_goal_id="goal-002",
            dependency_type="blocks",
        )
        assert dep.dependency_type == "blocks"

    def test_empty_goal_id_rejected(self):
        with pytest.raises(ValueError, match="goal_id"):
            GoalDependency(goal_id="", depends_on_goal_id="g2", dependency_type="blocks")

    def test_empty_depends_on_rejected(self):
        with pytest.raises(ValueError, match="depends_on_goal_id"):
            GoalDependency(goal_id="g1", depends_on_goal_id="", dependency_type="blocks")

    def test_empty_type_rejected(self):
        with pytest.raises(ValueError, match="dependency_type"):
            GoalDependency(goal_id="g1", depends_on_goal_id="g2", dependency_type="")


# --- SubGoal ---


class TestSubGoal:
    def test_valid(self):
        sg = _sub_goal()
        assert sg.sub_goal_id == "sg-1"
        assert sg.status is SubGoalStatus.PENDING
        assert sg.predecessors == ()

    def test_with_skill(self):
        sg = _sub_goal(skill_id="skill-001")
        assert sg.skill_id == "skill-001"

    def test_with_workflow(self):
        sg = _sub_goal(workflow_id="wf-001")
        assert sg.workflow_id == "wf-001"

    def test_with_predecessors(self):
        sg = _sub_goal(predecessors=("sg-0",))
        assert sg.predecessors == ("sg-0",)

    def test_empty_sub_goal_id_rejected(self):
        with pytest.raises(ValueError, match="sub_goal_id"):
            _sub_goal(sub_goal_id="")

    def test_empty_predecessor_rejected(self):
        with pytest.raises(ValueError) as exc_info:
            _sub_goal(predecessors=("",))
        message = str(exc_info.value)
        assert message == "value must be a non-empty string"
        assert "predecessors" not in message

    def test_frozen(self):
        sg = _sub_goal()
        with pytest.raises(AttributeError):
            sg.status = SubGoalStatus.COMPLETED  # type: ignore[misc]


# --- GoalPlan ---


class TestGoalPlan:
    def test_valid(self):
        p = _plan()
        assert p.plan_id == "plan-001"
        assert len(p.sub_goals) == 1
        assert p.version == 1

    def test_empty_sub_goals_rejected(self):
        with pytest.raises(ValueError, match="sub_goals"):
            _plan(sub_goals=())

    def test_empty_plan_id_rejected(self):
        with pytest.raises(ValueError, match="plan_id"):
            _plan(plan_id="")

    def test_invalid_version_rejected(self):
        with pytest.raises(ValueError, match="version"):
            _plan(version=0)

    def test_negative_version_rejected(self):
        with pytest.raises(ValueError, match="version"):
            _plan(version=-1)

    def test_circular_dependency_rejected(self):
        sg1 = _sub_goal(sub_goal_id="sg-secret-a", predecessors=("sg-secret-b",))
        sg2 = _sub_goal(sub_goal_id="sg-secret-b", predecessors=("sg-secret-a",))
        with pytest.raises(ValueError) as exc_info:
            _plan(sub_goals=(sg1, sg2))
        message = str(exc_info.value)
        assert message == "circular sub-goal dependency detected"
        assert "sg-secret-a" not in message
        assert "sg-secret-b" not in message

    def test_unknown_predecessor_rejected(self):
        sg = _sub_goal(sub_goal_id="sg-secret-a", predecessors=("sg-secret-missing",))
        with pytest.raises(ValueError) as exc_info:
            _plan(sub_goals=(sg,))
        message = str(exc_info.value)
        assert message == "sub-goal dependency references an unknown sub-goal"
        assert "sg-secret-a" not in message
        assert "sg-secret-missing" not in message

    def test_valid_dag(self):
        sg1 = _sub_goal(sub_goal_id="sg-a")
        sg2 = _sub_goal(sub_goal_id="sg-b", predecessors=("sg-a",))
        sg3 = _sub_goal(sub_goal_id="sg-c", predecessors=("sg-a", "sg-b"))
        p = _plan(sub_goals=(sg1, sg2, sg3))
        assert len(p.sub_goals) == 3

    def test_frozen(self):
        p = _plan()
        with pytest.raises(AttributeError):
            p.version = 2  # type: ignore[misc]

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _plan(created_at="bad-date")


# --- GoalExecutionState ---


class TestGoalExecutionState:
    def test_valid(self):
        s = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.ACCEPTED,
            updated_at=_NOW,
        )
        assert s.status is GoalStatus.ACCEPTED
        assert s.current_plan_id is None
        assert s.completed_sub_goals == ()
        assert s.failed_sub_goals == ()

    def test_with_plan(self):
        s = GoalExecutionState(
            goal_id="goal-001",
            status=GoalStatus.EXECUTING,
            current_plan_id="plan-001",
            updated_at=_NOW,
        )
        assert s.current_plan_id == "plan-001"

    def test_empty_goal_id_rejected(self):
        with pytest.raises(ValueError, match="goal_id"):
            GoalExecutionState(goal_id="", status=GoalStatus.ACCEPTED, updated_at=_NOW)

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            GoalExecutionState(goal_id="g1", status="bogus", updated_at=_NOW)

    def test_invalid_updated_at_rejected(self):
        with pytest.raises(ValueError, match="updated_at"):
            GoalExecutionState(goal_id="g1", status=GoalStatus.ACCEPTED, updated_at="nope")


# --- GoalReplanRecord ---


class TestGoalReplanRecord:
    def test_valid(self):
        r = GoalReplanRecord(
            goal_id="goal-001",
            previous_plan_id="plan-001",
            new_plan_id="plan-002",
            reason="sub-goal sg-2 failed",
            replanned_at=_NOW,
        )
        assert r.previous_plan_id == "plan-001"
        assert r.new_plan_id == "plan-002"

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            GoalReplanRecord(
                goal_id="g1",
                previous_plan_id="p1",
                new_plan_id="p2",
                reason="",
                replanned_at=_NOW,
            )

    def test_invalid_replanned_at_rejected(self):
        with pytest.raises(ValueError, match="replanned_at"):
            GoalReplanRecord(
                goal_id="g1",
                previous_plan_id="p1",
                new_plan_id="p2",
                reason="oops",
                replanned_at="bad",
            )


# --- GoalPriority ordering ---


class TestGoalPriorityOrdering:
    def test_rank_ordering(self):
        assert GOAL_PRIORITY_RANK[GoalPriority.CRITICAL] < GOAL_PRIORITY_RANK[GoalPriority.HIGH]
        assert GOAL_PRIORITY_RANK[GoalPriority.HIGH] < GOAL_PRIORITY_RANK[GoalPriority.NORMAL]
        assert GOAL_PRIORITY_RANK[GoalPriority.NORMAL] < GOAL_PRIORITY_RANK[GoalPriority.LOW]
        assert GOAL_PRIORITY_RANK[GoalPriority.LOW] < GOAL_PRIORITY_RANK[GoalPriority.BACKGROUND]

    def test_all_priorities_have_ranks(self):
        for p in GoalPriority:
            assert p in GOAL_PRIORITY_RANK
