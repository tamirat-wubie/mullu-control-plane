"""Purpose: canonical temporal task and trigger contracts for the temporal plane.
Governance scope: temporal plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Every temporal task carries explicit lifecycle state and trigger.
  - State transitions are explicit and recorded.
  - Temporal artifacts MUST be persisted, not in-memory-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class TemporalState(StrEnum):
    """Lifecycle state of a temporal task."""

    PENDING = "pending"
    WAITING = "waiting"
    DUE = "due"
    RUNNING = "running"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# Terminal states — no transitions out of these
TERMINAL_STATES = frozenset({TemporalState.COMPLETED, TemporalState.EXPIRED, TemporalState.CANCELLED})


class TriggerType(StrEnum):
    """How a temporal task becomes due."""

    AT_TIME = "at_time"
    AFTER_DELAY = "after_delay"
    ON_EVENT = "on_event"
    RECURRING = "recurring"


@dataclass(frozen=True, slots=True)
class TemporalTrigger(ContractRecord):
    """Condition that activates a temporal task."""

    trigger_id: str
    trigger_type: TriggerType
    value: str
    reference_time: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "trigger_id", require_non_empty_text(self.trigger_id, "trigger_id"))
        if not isinstance(self.trigger_type, TriggerType):
            raise ValueError("trigger_type must be a TriggerType value")
        object.__setattr__(self, "value", require_non_empty_text(self.value, "value"))
        if self.reference_time is not None:
            object.__setattr__(self, "reference_time", require_datetime_text(self.reference_time, "reference_time"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalTask(ContractRecord):
    """A unit of work with an explicit time boundary."""

    task_id: str
    goal_id: str
    description: str
    trigger: TemporalTrigger
    state: TemporalState
    created_at: str
    deadline: str | None = None
    updated_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("task_id", "goal_id", "description"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.state, TemporalState):
            raise ValueError("state must be a TemporalState value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if self.deadline is not None:
            object.__setattr__(self, "deadline", require_datetime_text(self.deadline, "deadline"))
        if self.updated_at is not None:
            object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class StateTransition(ContractRecord):
    """Record of a temporal task state transition."""

    task_id: str
    from_state: TemporalState
    to_state: TemporalState
    reason: str
    transitioned_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", require_non_empty_text(self.task_id, "task_id"))
        if not isinstance(self.from_state, TemporalState):
            raise ValueError("from_state must be a TemporalState value")
        if not isinstance(self.to_state, TemporalState):
            raise ValueError("to_state must be a TemporalState value")
        if self.from_state in TERMINAL_STATES:
            raise ValueError("cannot transition from terminal state")
        if self.from_state == self.to_state:
            raise ValueError("state transition must change state")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "transitioned_at", require_datetime_text(self.transitioned_at, "transitioned_at"))


@dataclass(frozen=True, slots=True)
class ResumeCheckpoint(ContractRecord):
    """Persisted point from which interrupted work can resume."""

    checkpoint_id: str
    task_id: str
    last_completed_step: str
    state_snapshot: Mapping[str, Any]
    created_at: str

    def __post_init__(self) -> None:
        for field_name in ("checkpoint_id", "task_id", "last_completed_step"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.state_snapshot, Mapping):
            raise ValueError("state_snapshot must be a mapping")
        object.__setattr__(self, "state_snapshot", freeze_value(self.state_snapshot))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
