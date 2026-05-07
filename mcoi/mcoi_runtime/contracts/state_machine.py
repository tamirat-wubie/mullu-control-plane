"""Purpose: canonical state machine contracts for formalizing lifecycle semantics.
Governance scope: state machine definition, transition legality, and audit typing.
Dependencies: shared contract base helpers.
Invariants:
  - Every state machine has an explicit, exhaustive transition table.
  - No implicit transitions — only declared edges are legal.
  - Terminal states have no outgoing transitions.
  - Every transition produces an immutable audit record.
  - State machines are named, versioned, and deterministic.
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
    require_non_empty_tuple,
    require_non_negative_int,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TransitionVerdict(StrEnum):
    """Outcome of a transition legality check."""

    ALLOWED = "allowed"
    DENIED_ILLEGAL_EDGE = "denied_illegal_edge"
    DENIED_TERMINAL_STATE = "denied_terminal_state"
    DENIED_GUARD_FAILED = "denied_guard_failed"


# ---------------------------------------------------------------------------
# Transition rule (one legal edge in a state machine)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TransitionRule(ContractRecord):
    """A single legal state transition with optional guard label.

    from_state and to_state are string representations of enum values.
    action is the method/event name that triggers this transition.
    guard_label optionally describes a precondition for the transition.
    emits describes the event type produced when this transition fires.
    """

    from_state: str
    to_state: str
    action: str
    guard_label: str = ""
    emits: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_state", require_non_empty_text(self.from_state, "from_state"))
        object.__setattr__(self, "to_state", require_non_empty_text(self.to_state, "to_state"))
        object.__setattr__(self, "action", require_non_empty_text(self.action, "action"))


# ---------------------------------------------------------------------------
# State machine specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StateMachineSpec(ContractRecord):
    """A formal, versioned specification of a lifecycle state machine.

    Captures the complete set of legal states, terminal states,
    initial state, and the exhaustive transition table.
    """

    machine_id: str
    name: str
    version: str
    states: tuple[str, ...]
    initial_state: str
    terminal_states: tuple[str, ...]
    transitions: tuple[TransitionRule, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "machine_id", require_non_empty_text(self.machine_id, "machine_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "version", require_non_empty_text(self.version, "version"))
        object.__setattr__(self, "states", require_non_empty_tuple(self.states, "states"))
        object.__setattr__(self, "initial_state", require_non_empty_text(self.initial_state, "initial_state"))
        # initial_state must be in states
        if self.initial_state not in self.states:
            raise ValueError("initial state must be declared in states")
        # terminal_states must be subset of states
        object.__setattr__(self, "terminal_states", freeze_value(list(self.terminal_states)))
        for ts in self.terminal_states:
            if ts not in self.states:
                raise ValueError("terminal state must be declared in states")
        # transitions must reference declared states
        object.__setattr__(self, "transitions", freeze_value(list(self.transitions)))
        for tr in self.transitions:
            if not isinstance(tr, TransitionRule):
                raise ValueError("each transition must be a TransitionRule instance")
            if tr.from_state not in self.states:
                raise ValueError("transition source state must be declared in states")
            if tr.to_state not in self.states:
                raise ValueError("transition target state must be declared in states")
        # terminal states must have no outgoing transitions
        for ts in self.terminal_states:
            outgoing = [t for t in self.transitions if t.from_state == ts]
            if outgoing:
                raise ValueError("terminal state cannot have outgoing transitions")

    @property
    def transition_count(self) -> int:
        return len(self.transitions)

    def legal_actions(self, current_state: str) -> tuple[TransitionRule, ...]:
        """Return all transitions legal from current_state."""
        return tuple(t for t in self.transitions if t.from_state == current_state)

    def is_legal(self, from_state: str, to_state: str, action: str) -> TransitionVerdict:
        """Check whether a specific transition is legal."""
        if from_state in self.terminal_states:
            return TransitionVerdict.DENIED_TERMINAL_STATE
        for t in self.transitions:
            if t.from_state == from_state and t.to_state == to_state and t.action == action:
                return TransitionVerdict.ALLOWED
        return TransitionVerdict.DENIED_ILLEGAL_EDGE

    def reachable_from(self, state: str) -> tuple[str, ...]:
        """Return all states directly reachable from the given state."""
        return tuple(sorted({t.to_state for t in self.transitions if t.from_state == state}))


# ---------------------------------------------------------------------------
# Transition audit record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TransitionAuditRecord(ContractRecord):
    """Immutable record of a state transition that occurred at runtime.

    Links back to the state machine spec version, records the verdict,
    and captures the actor/reason.
    """

    audit_id: str
    machine_id: str
    entity_id: str
    from_state: str
    to_state: str
    action: str
    verdict: TransitionVerdict
    actor_id: str
    reason: str
    transitioned_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for f in ("audit_id", "machine_id", "entity_id", "from_state", "to_state", "action", "actor_id"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        if not isinstance(self.verdict, TransitionVerdict):
            raise ValueError("verdict must be a TransitionVerdict value")
        object.__setattr__(self, "transitioned_at", require_datetime_text(self.transitioned_at, "transitioned_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))

    @property
    def succeeded(self) -> bool:
        return self.verdict == TransitionVerdict.ALLOWED


# ---------------------------------------------------------------------------
# Checkpoint journal contracts
# ---------------------------------------------------------------------------


class JournalEntryKind(StrEnum):
    """What kind of event a journal entry records."""

    TICK = "tick"
    TRANSITION = "transition"
    CHECKPOINT = "checkpoint"
    EVENT_EMITTED = "event_emitted"
    OBLIGATION_CHANGED = "obligation_changed"
    REACTION_DECIDED = "reaction_decided"
    HEARTBEAT = "heartbeat"
    LIVELOCK = "livelock"
    HALT = "halt"
    RESUME = "resume"


@dataclass(frozen=True, slots=True)
class JournalEntry(ContractRecord):
    """A single append-only journal entry for deterministic replay.

    Journal entries are totally ordered within an epoch by sequence number.
    """

    entry_id: str
    epoch_id: str
    sequence: int
    kind: JournalEntryKind
    subject_id: str
    payload: Mapping[str, Any]
    recorded_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", require_non_empty_text(self.entry_id, "entry_id"))
        object.__setattr__(self, "epoch_id", require_non_empty_text(self.epoch_id, "epoch_id"))
        object.__setattr__(self, "sequence", require_non_negative_int(self.sequence, "sequence"))
        if not isinstance(self.kind, JournalEntryKind):
            raise ValueError("kind must be a JournalEntryKind value")
        object.__setattr__(self, "subject_id", require_non_empty_text(self.subject_id, "subject_id"))
        object.__setattr__(self, "payload", freeze_value(self.payload))
        object.__setattr__(self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at"))


class CheckpointScope(StrEnum):
    """What subsystems a checkpoint covers."""

    SUPERVISOR = "supervisor"
    EVENT_SPINE = "event_spine"
    OBLIGATION_RUNTIME = "obligation_runtime"
    REACTION_ENGINE = "reaction_engine"
    COMPOSITE = "composite"


@dataclass(frozen=True, slots=True)
class SubsystemSnapshot(ContractRecord):
    """Snapshot of a single subsystem's state at a checkpoint boundary."""

    snapshot_id: str
    scope: CheckpointScope
    state_hash: str
    record_count: int
    captured_at: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        if not isinstance(self.scope, CheckpointScope):
            raise ValueError("scope must be a CheckpointScope value")
        object.__setattr__(self, "state_hash", require_non_empty_text(self.state_hash, "state_hash"))
        object.__setattr__(self, "record_count", require_non_negative_int(self.record_count, "record_count"))
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))
        object.__setattr__(self, "payload", freeze_value(self.payload))


@dataclass(frozen=True, slots=True)
class CompositeCheckpoint(ContractRecord):
    """A unified checkpoint spanning all subsystems at a single boundary.

    The composite_hash is computed over all subsystem hashes to detect
    cross-subsystem state divergence.
    """

    checkpoint_id: str
    epoch_id: str
    tick_number: int
    snapshots: tuple[SubsystemSnapshot, ...]
    journal_sequence: int
    composite_hash: str
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "checkpoint_id", require_non_empty_text(self.checkpoint_id, "checkpoint_id"))
        object.__setattr__(self, "epoch_id", require_non_empty_text(self.epoch_id, "epoch_id"))
        object.__setattr__(self, "tick_number", require_non_negative_int(self.tick_number, "tick_number"))
        object.__setattr__(self, "snapshots", require_non_empty_tuple(self.snapshots, "snapshots"))
        for s in self.snapshots:
            if not isinstance(s, SubsystemSnapshot):
                raise ValueError("each snapshot must be a SubsystemSnapshot instance")
        # Ensure no duplicate scopes
        scopes = [s.scope for s in self.snapshots]
        if len(scopes) != len(set(scopes)):
            raise ValueError("snapshots must not contain duplicate scopes")
        object.__setattr__(self, "journal_sequence", require_non_negative_int(self.journal_sequence, "journal_sequence"))
        object.__setattr__(self, "composite_hash", require_non_empty_text(self.composite_hash, "composite_hash"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))

    @property
    def scope_names(self) -> tuple[str, ...]:
        return tuple(s.scope.value for s in self.snapshots)

    def snapshot_for(self, scope: CheckpointScope) -> SubsystemSnapshot | None:
        """Return the snapshot for a specific subsystem, or None."""
        for s in self.snapshots:
            if s.scope == scope:
                return s
        return None


# ---------------------------------------------------------------------------
# Restore verification contracts
# ---------------------------------------------------------------------------


class RestoreVerdict(StrEnum):
    """Outcome of a checkpoint restoration verification."""

    VERIFIED = "verified"
    HASH_MISMATCH = "hash_mismatch"
    SUBSYSTEM_MISSING = "subsystem_missing"
    ROLLBACK_TRIGGERED = "rollback_triggered"


@dataclass(frozen=True, slots=True)
class RestoreVerification(ContractRecord):
    """Immutable record of a checkpoint restore and its verification outcome.

    Captures pre-restore and post-restore hashes for each subsystem,
    the composite hash check, and the final verdict.
    """

    verification_id: str
    checkpoint_id: str
    epoch_id: str
    tick_number: int
    verdict: RestoreVerdict
    expected_composite_hash: str
    actual_composite_hash: str
    verified_at: str
    subsystem_results: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "verification_id", require_non_empty_text(self.verification_id, "verification_id"))
        object.__setattr__(self, "checkpoint_id", require_non_empty_text(self.checkpoint_id, "checkpoint_id"))
        object.__setattr__(self, "epoch_id", require_non_empty_text(self.epoch_id, "epoch_id"))
        object.__setattr__(self, "tick_number", require_non_negative_int(self.tick_number, "tick_number"))
        if not isinstance(self.verdict, RestoreVerdict):
            raise ValueError("verdict must be a RestoreVerdict value")
        object.__setattr__(self, "expected_composite_hash", require_non_empty_text(self.expected_composite_hash, "expected_composite_hash"))
        object.__setattr__(self, "actual_composite_hash", require_non_empty_text(self.actual_composite_hash, "actual_composite_hash"))
        object.__setattr__(self, "verified_at", require_datetime_text(self.verified_at, "verified_at"))
        object.__setattr__(self, "subsystem_results", freeze_value(self.subsystem_results))


class JournalValidationVerdict(StrEnum):
    """Outcome of journal integrity validation."""

    VALID = "valid"
    SEQUENCE_GAP = "sequence_gap"
    EPOCH_MISMATCH = "epoch_mismatch"
    ORDERING_VIOLATION = "ordering_violation"
    EMPTY_JOURNAL = "empty_journal"


@dataclass(frozen=True, slots=True)
class JournalValidationResult(ContractRecord):
    """Result of validating a journal segment's integrity.

    Checks monotonic sequence, epoch coherence, and gap-freedom.
    """

    validation_id: str
    epoch_id: str
    entry_count: int
    first_sequence: int
    last_sequence: int
    verdict: JournalValidationVerdict
    gap_positions: tuple[int, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "validation_id", require_non_empty_text(self.validation_id, "validation_id"))
        object.__setattr__(self, "epoch_id", require_non_empty_text(self.epoch_id, "epoch_id"))
        object.__setattr__(self, "entry_count", require_non_negative_int(self.entry_count, "entry_count"))
        object.__setattr__(self, "first_sequence", require_non_negative_int(self.first_sequence, "first_sequence"))
        object.__setattr__(self, "last_sequence", require_non_negative_int(self.last_sequence, "last_sequence"))
        if not isinstance(self.verdict, JournalValidationVerdict):
            raise ValueError("verdict must be a JournalValidationVerdict value")
        object.__setattr__(self, "gap_positions", freeze_value(list(self.gap_positions)))
