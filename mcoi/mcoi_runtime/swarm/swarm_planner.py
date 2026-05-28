"""Supervisor-led swarm planner.

Purpose: create an S2 governed swarm plan from a compiled goal.
Governance scope: goal decomposition with deterministic task ordering.
Dependencies: task decomposer and swarm contracts.
Invariants: every plan has at least one bounded task.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import SwarmGoal, SwarmInvariantViolation, SwarmTask
from .task_decomposer import TaskDecomposer


@dataclass(frozen=True)
class SwarmPlan:
    """Deterministic task plan for one goal."""

    goal: SwarmGoal
    tasks: tuple[SwarmTask, ...]

    def __post_init__(self) -> None:
        if not self.tasks:
            raise SwarmInvariantViolation("swarm plan requires at least one task")


class SwarmPlanner:
    """Plan S2 supervisor-led specialist work."""

    def __init__(self, decomposer: TaskDecomposer | None = None) -> None:
        self._decomposer = decomposer or TaskDecomposer()

    def decompose(self, goal: SwarmGoal) -> SwarmPlan:
        """Return a deterministic plan for the supplied goal."""

        return SwarmPlan(goal=goal, tasks=self._decomposer.decompose(goal))
