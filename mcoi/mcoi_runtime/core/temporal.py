"""Purpose: temporal core engine — task scheduling, due-time evaluation, state transitions.
Governance scope: temporal plane core logic only.
Dependencies: temporal contracts, invariant helpers.
Invariants:
  - Temporal tasks are explicit and persisted, not in-memory-only timers.
  - State transitions are deterministic and recorded.
  - Terminal states are irreversible.
  - Deadline evaluation is deterministic given the same clock input.
"""

from __future__ import annotations

from typing import Callable

from dataclasses import dataclass
from datetime import datetime, timezone

from mcoi_runtime.contracts.temporal import (
    ResumeCheckpoint,
    StateTransition,
    TemporalState,
    TemporalTask,
    TemporalTrigger,
    TriggerType,
    TERMINAL_STATES,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


@dataclass(frozen=True, slots=True)
class DueEvaluation:
    """Result of evaluating whether a task is due."""

    task_id: str
    is_due: bool
    reason: str


class TemporalEngine:
    """Task scheduling, due-time evaluation, and state transition management.

    This engine:
    - Maintains a typed task registry
    - Evaluates trigger conditions against a clock
    - Manages explicit state transitions
    - Enforces terminal state irreversibility
    - Does NOT execute tasks — that is the Execution Plane's role
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._tasks: dict[str, TemporalTask] = {}
        self._transitions: list[StateTransition] = []
        self._checkpoints: dict[str, ResumeCheckpoint] = {}

    def schedule(self, task: TemporalTask) -> TemporalTask:
        if task.task_id in self._tasks:
            raise RuntimeCoreInvariantError(f"task already scheduled: {task.task_id}")
        if task.state is not TemporalState.PENDING:
            raise RuntimeCoreInvariantError("new tasks must start in pending state")
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> TemporalTask | None:
        ensure_non_empty_text("task_id", task_id)
        return self._tasks.get(task_id)

    def list_tasks(self, *, state: TemporalState | None = None) -> tuple[TemporalTask, ...]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.task_id)
        if state is not None:
            tasks = [t for t in tasks if t.state == state]
        return tuple(tasks)

    def transition(self, task_id: str, to_state: TemporalState, reason: str) -> StateTransition:
        """Explicitly transition a task to a new state."""
        ensure_non_empty_text("task_id", task_id)
        ensure_non_empty_text("reason", reason)

        task = self._tasks.get(task_id)
        if task is None:
            raise RuntimeCoreInvariantError(f"task not found: {task_id}")

        transition = StateTransition(
            task_id=task_id,
            from_state=task.state,
            to_state=to_state,
            reason=reason,
            transitioned_at=self._clock(),
        )

        # Re-create task with new state
        updated = TemporalTask(
            task_id=task.task_id,
            goal_id=task.goal_id,
            description=task.description,
            trigger=task.trigger,
            state=to_state,
            created_at=task.created_at,
            deadline=task.deadline,
            updated_at=self._clock(),
            metadata=task.metadata,
        )
        self._tasks[task_id] = updated
        self._transitions.append(transition)
        return transition

    def evaluate_due(self, task_id: str) -> DueEvaluation:
        """Evaluate whether a task's trigger condition is met.

        Clock is sampled once for deterministic evaluation within a single call.
        """
        ensure_non_empty_text("task_id", task_id)

        task = self._tasks.get(task_id)
        if task is None:
            return DueEvaluation(task_id=task_id, is_due=False, reason="task_not_found")

        if task.state in TERMINAL_STATES:
            return DueEvaluation(task_id=task_id, is_due=False, reason=f"terminal_state:{task.state}")

        if task.state not in (TemporalState.PENDING, TemporalState.WAITING):
            return DueEvaluation(task_id=task_id, is_due=False, reason=f"not_evaluable:{task.state}")

        # Sample clock once for deterministic evaluation
        now = self._clock()

        # Check deadline first
        if task.deadline is not None:
            if now > task.deadline:
                self.transition(task_id, TemporalState.EXPIRED, "deadline_breached")
                return DueEvaluation(task_id=task_id, is_due=False, reason="deadline_breached")

        # Evaluate trigger
        if task.trigger.trigger_type is TriggerType.AT_TIME:
            if now >= task.trigger.value:
                return DueEvaluation(task_id=task_id, is_due=True, reason="at_time_reached")
            return DueEvaluation(task_id=task_id, is_due=False, reason="at_time_not_reached")

        if task.trigger.trigger_type is TriggerType.ON_EVENT:
            return DueEvaluation(task_id=task_id, is_due=False, reason="awaiting_event")

        if task.trigger.trigger_type is TriggerType.RECURRING:
            return DueEvaluation(task_id=task_id, is_due=True, reason="recurring_due")

        if task.trigger.trigger_type is TriggerType.AFTER_DELAY:
            return DueEvaluation(task_id=task_id, is_due=False, reason="delay_evaluation_requires_reference")

        return DueEvaluation(task_id=task_id, is_due=False, reason="unknown_trigger_type")

    def save_checkpoint(self, checkpoint: ResumeCheckpoint) -> ResumeCheckpoint:
        if checkpoint.task_id not in self._tasks:
            raise RuntimeCoreInvariantError(f"cannot checkpoint unknown task: {checkpoint.task_id}")
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> ResumeCheckpoint | None:
        ensure_non_empty_text("checkpoint_id", checkpoint_id)
        return self._checkpoints.get(checkpoint_id)

    def get_transitions(self, task_id: str) -> tuple[StateTransition, ...]:
        ensure_non_empty_text("task_id", task_id)
        return tuple(t for t in self._transitions if t.task_id == task_id)

    @property
    def size(self) -> int:
        return len(self._tasks)
