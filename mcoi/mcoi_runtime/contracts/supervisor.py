"""Purpose: canonical continuous supervisor runtime contracts.
Governance scope: supervisor state, tick, policy, checkpoint, health, decision,
heartbeat, and livelock typing.
Dependencies: shared contract base helpers.
Invariants:
  - The supervisor advances one deterministic tick at a time.
  - Every tick produces an immutable record of what was evaluated and decided.
  - Checkpoints are serializable for resume; no hidden state.
  - Heartbeats are periodic health signals emitted into the event spine.
  - Livelock detection is explicit — stall loops are surfaced, never silent.
  - Governance is never bypassed; every action passes through policy evaluation.
  - Backpressure and pacing are policy-driven, not hardcoded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SupervisorPhase(StrEnum):
    """What the supervisor is currently doing within a tick."""

    IDLE = "idle"
    POLLING = "polling"
    EVALUATING_OBLIGATIONS = "evaluating_obligations"
    EVALUATING_DEADLINES = "evaluating_deadlines"
    WAKING_WORK = "waking_work"
    RUNNING_REACTIONS = "running_reactions"
    REASONING = "reasoning"
    ACTING = "acting"
    CHECKPOINTING = "checkpointing"
    EMITTING_HEARTBEAT = "emitting_heartbeat"
    PAUSED = "paused"
    DEGRADED = "degraded"
    HALTED = "halted"


class TickOutcome(StrEnum):
    """Summary outcome of a single supervisor tick."""

    HEALTHY = "healthy"
    WORK_DONE = "work_done"
    IDLE_TICK = "idle_tick"
    BACKPRESSURE_APPLIED = "backpressure_applied"
    LIVELOCK_DETECTED = "livelock_detected"
    GOVERNANCE_BLOCKED = "governance_blocked"
    ERROR = "error"
    HALTED = "halted"


class LivelockStrategy(StrEnum):
    """How to respond when livelock is detected."""

    ESCALATE = "escalate"
    PAUSE = "pause"
    HALT = "halt"
    SKIP_AND_LOG = "skip_and_log"


class CheckpointStatus(StrEnum):
    """Status of a supervisor checkpoint."""

    VALID = "valid"
    STALE = "stale"
    CORRUPTED = "corrupted"


# ---------------------------------------------------------------------------
# Policy contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SupervisorPolicy(ContractRecord):
    """Configuration governing supervisor tick behavior.

    Defines pacing, backpressure thresholds, livelock detection,
    and heartbeat intervals.  All values are bounded and validated.
    """

    policy_id: str
    tick_interval_ms: int
    max_events_per_tick: int
    max_actions_per_tick: int
    backpressure_threshold: int
    livelock_repeat_threshold: int
    livelock_strategy: LivelockStrategy
    heartbeat_every_n_ticks: int
    checkpoint_every_n_ticks: int
    max_consecutive_errors: int
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "tick_interval_ms", require_positive_int(self.tick_interval_ms, "tick_interval_ms"))
        object.__setattr__(self, "max_events_per_tick", require_positive_int(self.max_events_per_tick, "max_events_per_tick"))
        object.__setattr__(self, "max_actions_per_tick", require_positive_int(self.max_actions_per_tick, "max_actions_per_tick"))
        object.__setattr__(self, "backpressure_threshold", require_positive_int(self.backpressure_threshold, "backpressure_threshold"))
        object.__setattr__(self, "livelock_repeat_threshold", require_positive_int(self.livelock_repeat_threshold, "livelock_repeat_threshold"))
        if not isinstance(self.livelock_strategy, LivelockStrategy):
            raise ValueError("livelock_strategy must be a LivelockStrategy value")
        object.__setattr__(self, "heartbeat_every_n_ticks", require_positive_int(self.heartbeat_every_n_ticks, "heartbeat_every_n_ticks"))
        object.__setattr__(self, "checkpoint_every_n_ticks", require_positive_int(self.checkpoint_every_n_ticks, "checkpoint_every_n_ticks"))
        object.__setattr__(self, "max_consecutive_errors", require_positive_int(self.max_consecutive_errors, "max_consecutive_errors"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Tick records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SupervisorDecision(ContractRecord):
    """One action decided during a supervisor tick.

    Records what was decided, why, and whether governance approved it.
    """

    decision_id: str
    action_type: str
    target_id: str
    reason: str
    governance_approved: bool
    decided_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "action_type", require_non_empty_text(self.action_type, "action_type"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        if not isinstance(self.governance_approved, bool):
            raise ValueError("governance_approved must be a boolean")
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class SupervisorTick(ContractRecord):
    """Immutable record of one supervisor tick cycle.

    Captures what was polled, evaluated, decided, and the resulting outcome.
    """

    tick_id: str
    tick_number: int
    phase_sequence: tuple[SupervisorPhase, ...]
    events_polled: int
    obligations_evaluated: int
    deadlines_checked: int
    reactions_fired: int
    decisions: tuple[SupervisorDecision, ...]
    outcome: TickOutcome
    errors: tuple[str, ...] = ()
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick_id", require_non_empty_text(self.tick_id, "tick_id"))
        object.__setattr__(self, "tick_number", require_non_negative_int(self.tick_number, "tick_number"))
        object.__setattr__(self, "phase_sequence", freeze_value(list(self.phase_sequence)))
        for p in self.phase_sequence:
            if not isinstance(p, SupervisorPhase):
                raise ValueError("each phase must be a SupervisorPhase value")
        object.__setattr__(self, "events_polled", require_non_negative_int(self.events_polled, "events_polled"))
        object.__setattr__(self, "obligations_evaluated", require_non_negative_int(self.obligations_evaluated, "obligations_evaluated"))
        object.__setattr__(self, "deadlines_checked", require_non_negative_int(self.deadlines_checked, "deadlines_checked"))
        object.__setattr__(self, "reactions_fired", require_non_negative_int(self.reactions_fired, "reactions_fired"))
        object.__setattr__(self, "decisions", freeze_value(list(self.decisions)))
        for d in self.decisions:
            if not isinstance(d, SupervisorDecision):
                raise ValueError("each decision must be a SupervisorDecision instance")
        if not isinstance(self.outcome, TickOutcome):
            raise ValueError("outcome must be a TickOutcome value")
        object.__setattr__(self, "errors", freeze_value(list(self.errors)))
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "completed_at", require_datetime_text(self.completed_at, "completed_at"))
        object.__setattr__(self, "duration_ms", require_non_negative_int(self.duration_ms, "duration_ms"))


# ---------------------------------------------------------------------------
# Health and heartbeat
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SupervisorHealth(ContractRecord):
    """Health assessment of the supervisor at a point in time."""

    health_id: str
    tick_number: int
    phase: SupervisorPhase
    consecutive_errors: int
    consecutive_idle_ticks: int
    backpressure_active: bool
    livelock_detected: bool
    open_obligations: int
    pending_events: int
    overall_confidence: float
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "health_id", require_non_empty_text(self.health_id, "health_id"))
        object.__setattr__(self, "tick_number", require_non_negative_int(self.tick_number, "tick_number"))
        if not isinstance(self.phase, SupervisorPhase):
            raise ValueError("phase must be a SupervisorPhase value")
        object.__setattr__(self, "consecutive_errors", require_non_negative_int(self.consecutive_errors, "consecutive_errors"))
        object.__setattr__(self, "consecutive_idle_ticks", require_non_negative_int(self.consecutive_idle_ticks, "consecutive_idle_ticks"))
        if not isinstance(self.backpressure_active, bool):
            raise ValueError("backpressure_active must be a boolean")
        if not isinstance(self.livelock_detected, bool):
            raise ValueError("livelock_detected must be a boolean")
        object.__setattr__(self, "open_obligations", require_non_negative_int(self.open_obligations, "open_obligations"))
        object.__setattr__(self, "pending_events", require_non_negative_int(self.pending_events, "pending_events"))
        object.__setattr__(self, "overall_confidence", require_unit_float(self.overall_confidence, "overall_confidence"))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class RuntimeHeartbeat(ContractRecord):
    """Periodic health signal emitted into the event spine."""

    heartbeat_id: str
    tick_number: int
    phase: SupervisorPhase
    outcome_of_last_tick: TickOutcome
    open_obligations: int
    pending_events: int
    uptime_ticks: int
    emitted_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "heartbeat_id", require_non_empty_text(self.heartbeat_id, "heartbeat_id"))
        object.__setattr__(self, "tick_number", require_non_negative_int(self.tick_number, "tick_number"))
        if not isinstance(self.phase, SupervisorPhase):
            raise ValueError("phase must be a SupervisorPhase value")
        if not isinstance(self.outcome_of_last_tick, TickOutcome):
            raise ValueError("outcome_of_last_tick must be a TickOutcome value")
        object.__setattr__(self, "open_obligations", require_non_negative_int(self.open_obligations, "open_obligations"))
        object.__setattr__(self, "pending_events", require_non_negative_int(self.pending_events, "pending_events"))
        object.__setattr__(self, "uptime_ticks", require_non_negative_int(self.uptime_ticks, "uptime_ticks"))
        object.__setattr__(self, "emitted_at", require_datetime_text(self.emitted_at, "emitted_at"))


# ---------------------------------------------------------------------------
# Checkpoint and livelock
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SupervisorCheckpoint(ContractRecord):
    """Serializable snapshot for supervisor resume.

    Contains enough state to restart the supervisor from this point
    without replaying the full event history.
    """

    checkpoint_id: str
    tick_number: int
    phase: SupervisorPhase
    status: CheckpointStatus
    open_obligation_ids: tuple[str, ...]
    pending_event_count: int
    consecutive_errors: int
    consecutive_idle_ticks: int
    recent_tick_outcomes: tuple[TickOutcome, ...]
    state_hash: str
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "checkpoint_id", require_non_empty_text(self.checkpoint_id, "checkpoint_id"))
        object.__setattr__(self, "tick_number", require_non_negative_int(self.tick_number, "tick_number"))
        if not isinstance(self.phase, SupervisorPhase):
            raise ValueError("phase must be a SupervisorPhase value")
        if not isinstance(self.status, CheckpointStatus):
            raise ValueError("status must be a CheckpointStatus value")
        object.__setattr__(self, "open_obligation_ids", freeze_value(list(self.open_obligation_ids)))
        for oid in self.open_obligation_ids:
            require_non_empty_text(oid, "open_obligation_id")
        object.__setattr__(self, "pending_event_count", require_non_negative_int(self.pending_event_count, "pending_event_count"))
        object.__setattr__(self, "consecutive_errors", require_non_negative_int(self.consecutive_errors, "consecutive_errors"))
        object.__setattr__(self, "consecutive_idle_ticks", require_non_negative_int(self.consecutive_idle_ticks, "consecutive_idle_ticks"))
        object.__setattr__(self, "recent_tick_outcomes", freeze_value(list(self.recent_tick_outcomes)))
        for o in self.recent_tick_outcomes:
            if not isinstance(o, TickOutcome):
                raise ValueError("each recent_tick_outcome must be a TickOutcome value")
        object.__setattr__(self, "state_hash", require_non_empty_text(self.state_hash, "state_hash"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class LivelockRecord(ContractRecord):
    """Explicit record of a detected stall/loop condition.

    Livelock is surfaced, never silent.  The record includes the
    repeated pattern and the strategy applied to break it.
    """

    livelock_id: str
    tick_number: int
    repeated_pattern: str
    repeat_count: int
    strategy_applied: LivelockStrategy
    resolved: bool
    detected_at: str
    resolution_detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "livelock_id", require_non_empty_text(self.livelock_id, "livelock_id"))
        object.__setattr__(self, "tick_number", require_non_negative_int(self.tick_number, "tick_number"))
        object.__setattr__(self, "repeated_pattern", require_non_empty_text(self.repeated_pattern, "repeated_pattern"))
        object.__setattr__(self, "repeat_count", require_positive_int(self.repeat_count, "repeat_count"))
        if not isinstance(self.strategy_applied, LivelockStrategy):
            raise ValueError("strategy_applied must be a LivelockStrategy value")
        if not isinstance(self.resolved, bool):
            raise ValueError("resolved must be a boolean")
        object.__setattr__(self, "detected_at", require_datetime_text(self.detected_at, "detected_at"))
