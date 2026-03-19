"""Purpose: verify temporal contracts, engine scheduling, state transitions, and due evaluation.
Governance scope: temporal plane tests only.
Dependencies: temporal contracts, temporal engine.
Invariants: terminal states are irreversible; transitions are explicit; deadlines are deterministic.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.temporal import (
    ResumeCheckpoint,
    StateTransition,
    TemporalState,
    TemporalTask,
    TemporalTrigger,
    TriggerType,
    TERMINAL_STATES,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.temporal import TemporalEngine


_CLOCK = "2026-03-19T00:00:00+00:00"
_FUTURE = "2027-01-01T00:00:00+00:00"
_PAST = "2025-01-01T00:00:00+00:00"


def _trigger(trigger_type: TriggerType = TriggerType.AT_TIME, value: str = _FUTURE) -> TemporalTrigger:
    return TemporalTrigger(trigger_id="trig-1", trigger_type=trigger_type, value=value)


def _task(task_id: str = "task-1", trigger: TemporalTrigger | None = None, deadline: str | None = None) -> TemporalTask:
    return TemporalTask(
        task_id=task_id,
        goal_id="goal-1",
        description="test task",
        trigger=trigger or _trigger(),
        state=TemporalState.PENDING,
        created_at=_CLOCK,
        deadline=deadline,
    )


# --- Contract tests ---

def test_temporal_task_validates() -> None:
    task = _task()
    assert task.state is TemporalState.PENDING
    assert task.task_id == "task-1"


def test_state_transition_rejects_terminal_source() -> None:
    for state in TERMINAL_STATES:
        with pytest.raises(ValueError, match="terminal"):
            StateTransition(
                task_id="t-1",
                from_state=state,
                to_state=TemporalState.PENDING,
                reason="invalid",
                transitioned_at=_CLOCK,
            )


def test_state_transition_rejects_same_state() -> None:
    with pytest.raises(ValueError, match="must change"):
        StateTransition(
            task_id="t-1",
            from_state=TemporalState.PENDING,
            to_state=TemporalState.PENDING,
            reason="noop",
            transitioned_at=_CLOCK,
        )


def test_resume_checkpoint_validates() -> None:
    cp = ResumeCheckpoint(
        checkpoint_id="cp-1",
        task_id="task-1",
        last_completed_step="step-3",
        state_snapshot={"key": "value"},
        created_at=_CLOCK,
    )
    assert cp.checkpoint_id == "cp-1"


# --- Engine tests ---

def test_schedule_and_get() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    task = _task()
    engine.schedule(task)
    assert engine.get_task("task-1") is not None
    assert engine.size == 1


def test_schedule_duplicate_rejected() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    engine.schedule(_task())
    with pytest.raises(RuntimeCoreInvariantError, match="already scheduled"):
        engine.schedule(_task())


def test_schedule_non_pending_rejected() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    task = TemporalTask(
        task_id="t-1", goal_id="g-1", description="d",
        trigger=_trigger(), state=TemporalState.RUNNING,
        created_at=_CLOCK,
    )
    with pytest.raises(RuntimeCoreInvariantError, match="pending"):
        engine.schedule(task)


def test_transition_updates_state() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    engine.schedule(_task())

    transition = engine.transition("task-1", TemporalState.DUE, "trigger met")

    assert transition.from_state is TemporalState.PENDING
    assert transition.to_state is TemporalState.DUE
    assert engine.get_task("task-1").state is TemporalState.DUE


def test_transition_from_terminal_rejected() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    engine.schedule(_task())
    engine.transition("task-1", TemporalState.COMPLETED, "done")

    with pytest.raises(ValueError, match="terminal"):
        engine.transition("task-1", TemporalState.PENDING, "retry")


def test_evaluate_due_at_time_reached() -> None:
    engine = TemporalEngine(clock=lambda: _FUTURE)
    engine.schedule(_task(trigger=_trigger(value=_PAST)))

    result = engine.evaluate_due("task-1")
    assert result.is_due is True


def test_evaluate_due_at_time_not_reached() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    engine.schedule(_task(trigger=_trigger(value=_FUTURE)))

    result = engine.evaluate_due("task-1")
    assert result.is_due is False


def test_evaluate_due_deadline_breached() -> None:
    engine = TemporalEngine(clock=lambda: _FUTURE)
    engine.schedule(_task(deadline=_PAST))

    result = engine.evaluate_due("task-1")
    assert result.is_due is False
    assert "deadline_breached" in result.reason
    assert engine.get_task("task-1").state is TemporalState.EXPIRED


def test_evaluate_due_terminal_task() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    engine.schedule(_task())
    engine.transition("task-1", TemporalState.CANCELLED, "cancelled")

    result = engine.evaluate_due("task-1")
    assert result.is_due is False
    assert "terminal" in result.reason


def test_list_tasks_by_state() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    engine.schedule(_task("t-1"))
    engine.schedule(_task("t-2"))
    engine.transition("t-1", TemporalState.DUE, "ready")

    assert len(engine.list_tasks()) == 2
    assert len(engine.list_tasks(state=TemporalState.DUE)) == 1
    assert len(engine.list_tasks(state=TemporalState.PENDING)) == 1


def test_checkpoint_save_and_get() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    engine.schedule(_task())

    cp = ResumeCheckpoint(
        checkpoint_id="cp-1", task_id="task-1",
        last_completed_step="step-2",
        state_snapshot={"progress": 0.5},
        created_at=_CLOCK,
    )
    engine.save_checkpoint(cp)
    assert engine.get_checkpoint("cp-1") is not None


def test_get_transitions() -> None:
    engine = TemporalEngine(clock=lambda: _CLOCK)
    engine.schedule(_task())
    engine.transition("task-1", TemporalState.DUE, "trigger")
    engine.transition("task-1", TemporalState.RUNNING, "started")

    transitions = engine.get_transitions("task-1")
    assert len(transitions) == 2
    assert transitions[0].to_state is TemporalState.DUE
    assert transitions[1].to_state is TemporalState.RUNNING
