"""Purpose: canonical goal reasoning contract mapping.
Governance scope: goal descriptor, dependency, sub-goal, plan, execution state, and replan typing.
Dependencies: docs/22_goal_reasoning.md, shared contract base helpers.
Invariants:
  - Every goal carries explicit identity, priority, and lifecycle state.
  - Plans MUST NOT have circular sub-goal dependencies.
  - Empty plans (no sub-goals) are rejected.
  - Replanning always produces a typed audit record.
  - No goal may bypass policy/autonomy constraints.
  - No silent goal mutation; no untracked replanning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, cast

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
)


# --- Classification enums ---


class GoalStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLANNING = "replanning"
    ARCHIVED = "archived"


class GoalPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


# Numeric rank for sorting (lower number = higher priority)
GOAL_PRIORITY_RANK: dict[GoalPriority, int] = {
    GoalPriority.CRITICAL: 0,
    GoalPriority.HIGH: 1,
    GoalPriority.NORMAL: 2,
    GoalPriority.LOW: 3,
    GoalPriority.BACKGROUND: 4,
}


class SubGoalStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# --- Contract types ---


def _freeze_text_array(values: tuple[str, ...] | list[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[str, ...], freeze_value(list(values)))
    for idx, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{idx}]")
    return frozen


@dataclass(frozen=True, slots=True)
class GoalDescriptor(ContractRecord):
    """Identity and metadata for a single goal."""

    goal_id: str
    description: str
    priority: GoalPriority
    created_at: str
    deadline: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.priority, GoalPriority):
            raise ValueError("priority must be a GoalPriority value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if self.deadline is not None:
            object.__setattr__(self, "deadline", require_datetime_text(self.deadline, "deadline"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class GoalDependency(ContractRecord):
    """Typed edge between two goals."""

    goal_id: str
    depends_on_goal_id: str
    dependency_type: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        object.__setattr__(
            self, "depends_on_goal_id",
            require_non_empty_text(self.depends_on_goal_id, "depends_on_goal_id"),
        )
        object.__setattr__(
            self, "dependency_type",
            require_non_empty_text(self.dependency_type, "dependency_type"),
        )


@dataclass(frozen=True, slots=True)
class SubGoal(ContractRecord):
    """One actionable unit within a goal plan."""

    sub_goal_id: str
    goal_id: str
    description: str
    status: SubGoalStatus = SubGoalStatus.PENDING
    skill_id: str | None = None
    workflow_id: str | None = None
    predecessors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "sub_goal_id", require_non_empty_text(self.sub_goal_id, "sub_goal_id"))
        object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.status, SubGoalStatus):
            raise ValueError("status must be a SubGoalStatus value")
        if self.skill_id is not None:
            object.__setattr__(self, "skill_id", require_non_empty_text(self.skill_id, "skill_id"))
        if self.workflow_id is not None:
            object.__setattr__(self, "workflow_id", require_non_empty_text(self.workflow_id, "workflow_id"))
        object.__setattr__(self, "predecessors", _freeze_text_array(self.predecessors, "predecessors"))


@dataclass(frozen=True, slots=True)
class GoalPlan(ContractRecord):
    """Versioned collection of sub-goals for a goal."""

    plan_id: str
    goal_id: str
    sub_goals: tuple[SubGoal, ...]
    created_at: str
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        object.__setattr__(self, "sub_goals", require_non_empty_tuple(self.sub_goals, "sub_goals"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version must be a positive integer")
        for idx, sub_goal in enumerate(self.sub_goals):
            if not isinstance(sub_goal, SubGoal):
                raise ValueError(f"sub_goals[{idx}] must be a SubGoal")
        # Validate no circular sub-goal dependencies
        self._check_no_circular_deps()

    def _check_no_circular_deps(self) -> None:
        sg_ids: set[str] = set()
        for sg in self.sub_goals:
            if sg.sub_goal_id in sg_ids:
                raise ValueError("sub_goals must declare unique sub_goal_id values")
            sg_ids.add(sg.sub_goal_id)
        for sg in self.sub_goals:
            for pred in sg.predecessors:
                if pred not in sg_ids:
                    raise ValueError("sub-goal dependency references an unknown sub-goal")
        # Topological check via DFS
        visited: set[str] = set()
        in_stack: set[str] = set()
        deps_map = {sg.sub_goal_id: sg.predecessors for sg in self.sub_goals}

        def visit(sid: str) -> None:
            if sid in in_stack:
                raise ValueError("circular sub-goal dependency detected")
            if sid in visited:
                return
            in_stack.add(sid)
            for dep in deps_map.get(sid, ()):
                visit(dep)
            in_stack.discard(sid)
            visited.add(sid)

        for sg in self.sub_goals:
            visit(sg.sub_goal_id)


@dataclass(frozen=True, slots=True)
class GoalExecutionState(ContractRecord):
    """Mutable progress tracker for a goal (rebuilt as frozen instances)."""

    goal_id: str
    status: GoalStatus
    updated_at: str
    current_plan_id: str | None = None
    completed_sub_goals: tuple[str, ...] = ()
    failed_sub_goals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        if not isinstance(self.status, GoalStatus):
            raise ValueError("status must be a GoalStatus value")
        object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        object.__setattr__(
            self,
            "completed_sub_goals",
            _freeze_text_array(self.completed_sub_goals, "completed_sub_goals"),
        )
        object.__setattr__(
            self,
            "failed_sub_goals",
            _freeze_text_array(self.failed_sub_goals, "failed_sub_goals"),
        )
        # Detect duplicate sub-goal IDs
        if len(set(self.completed_sub_goals)) != len(self.completed_sub_goals):
            raise ValueError("completed_sub_goals must not contain duplicates")
        if len(set(self.failed_sub_goals)) != len(self.failed_sub_goals):
            raise ValueError("failed_sub_goals must not contain duplicates")
        # A sub-goal cannot appear in both completed and failed
        overlap = set(self.completed_sub_goals) & set(self.failed_sub_goals)
        if overlap:
            raise ValueError("sub-goal IDs appear in both completed and failed")


@dataclass(frozen=True, slots=True)
class GoalReplanRecord(ContractRecord):
    """Audit record when a plan is replaced."""

    goal_id: str
    previous_plan_id: str
    new_plan_id: str
    reason: str
    replanned_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        object.__setattr__(self, "previous_plan_id", require_non_empty_text(self.previous_plan_id, "previous_plan_id"))
        object.__setattr__(self, "new_plan_id", require_non_empty_text(self.new_plan_id, "new_plan_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "replanned_at", require_datetime_text(self.replanned_at, "replanned_at"))
