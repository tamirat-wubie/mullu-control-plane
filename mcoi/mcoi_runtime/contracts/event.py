"""Purpose: canonical event spine contracts for typed, correlated, durable events.
Governance scope: event plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Events are append-only and immutable once emitted.
  - Every event has a source, type, and correlation ID.
  - Event envelopes wrap payloads with metadata for routing.
  - Subscriptions are deterministic — same event, same reactions.
  - Event windows bound temporal correlation.
  - Correlations link causally related events.
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
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventType(StrEnum):
    """Classification of events emitted into the spine."""

    JOB_STATE_TRANSITION = "job_state_transition"
    WORKFLOW_STAGE_TRANSITION = "workflow_stage_transition"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DECIDED = "approval_decided"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_DECIDED = "review_decided"
    INCIDENT_OPENED = "incident_opened"
    INCIDENT_ESCALATED = "incident_escalated"
    INCIDENT_RESOLVED = "incident_resolved"
    COMMUNICATION_SENT = "communication_sent"
    COMMUNICATION_REPLIED = "communication_replied"
    COMMUNICATION_TIMED_OUT = "communication_timed_out"
    OBLIGATION_CREATED = "obligation_created"
    OBLIGATION_CLOSED = "obligation_closed"
    OBLIGATION_ESCALATED = "obligation_escalated"
    OBLIGATION_TRANSFERRED = "obligation_transferred"
    OBLIGATION_EXPIRED = "obligation_expired"
    WORLD_STATE_CHANGED = "world_state_changed"
    REACTION_EXECUTED = "reaction_executed"
    REACTION_DEFERRED = "reaction_deferred"
    REACTION_REJECTED = "reaction_rejected"
    SUPERVISOR_HEARTBEAT = "supervisor_heartbeat"
    SUPERVISOR_LIVELOCK = "supervisor_livelock"
    SUPERVISOR_CHECKPOINT = "supervisor_checkpoint"
    SUPERVISOR_HALTED = "supervisor_halted"
    CUSTOM = "custom"


class EventSource(StrEnum):
    """Origin plane or subsystem that emitted the event."""

    JOB_RUNTIME = "job_runtime"
    WORKFLOW_RUNTIME = "workflow_runtime"
    TEAM_RUNTIME = "team_runtime"
    FUNCTION_RUNTIME = "function_runtime"
    APPROVAL_SYSTEM = "approval_system"
    REVIEW_SYSTEM = "review_system"
    INCIDENT_SYSTEM = "incident_system"
    COMMUNICATION_SYSTEM = "communication_system"
    OBLIGATION_RUNTIME = "obligation_runtime"
    WORLD_STATE_ENGINE = "world_state_engine"
    SIMULATION_ENGINE = "simulation_engine"
    REACTION_ENGINE = "reaction_engine"
    SUPERVISOR = "supervisor"
    DASHBOARD = "dashboard"
    EXTERNAL = "external"


# ---------------------------------------------------------------------------
# Event records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EventRecord(ContractRecord):
    """A single typed event emitted into the spine.

    Events are immutable once created.  The correlation_id links
    this event to a causal chain (e.g. all events for one job).
    """

    event_id: str
    event_type: EventType
    source: EventSource
    correlation_id: str
    payload: Mapping[str, Any]
    emitted_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", require_non_empty_text(self.event_id, "event_id"))
        if not isinstance(self.event_type, EventType):
            raise ValueError("event_type must be an EventType value")
        if not isinstance(self.source, EventSource):
            raise ValueError("source must be an EventSource value")
        object.__setattr__(
            self, "correlation_id",
            require_non_empty_text(self.correlation_id, "correlation_id"),
        )
        object.__setattr__(self, "payload", freeze_value(dict(self.payload)))
        object.__setattr__(self, "emitted_at", require_datetime_text(self.emitted_at, "emitted_at"))


@dataclass(frozen=True, slots=True)
class EventEnvelope(ContractRecord):
    """Routing wrapper around an EventRecord with delivery metadata."""

    envelope_id: str
    event: EventRecord
    target_subsystems: tuple[str, ...]
    priority: int
    delivered: bool = False
    delivered_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "envelope_id",
            require_non_empty_text(self.envelope_id, "envelope_id"),
        )
        if not isinstance(self.event, EventRecord):
            raise ValueError("event must be an EventRecord instance")
        object.__setattr__(self, "target_subsystems", freeze_value(list(self.target_subsystems)))
        if not self.target_subsystems:
            raise ValueError("target_subsystems must contain at least one item")
        for ts in self.target_subsystems:
            require_non_empty_text(ts, "target_subsystem")
        object.__setattr__(
            self, "priority",
            require_non_negative_int(self.priority, "priority"),
        )
        if self.delivered_at is not None:
            object.__setattr__(
                self, "delivered_at",
                require_datetime_text(self.delivered_at, "delivered_at"),
            )


@dataclass(frozen=True, slots=True)
class EventSubscription(ContractRecord):
    """A deterministic subscription binding an event type to a reaction."""

    subscription_id: str
    event_type: EventType
    subscriber_id: str
    reaction_id: str
    filter_source: EventSource | None = None
    active: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "subscription_id",
            require_non_empty_text(self.subscription_id, "subscription_id"),
        )
        if not isinstance(self.event_type, EventType):
            raise ValueError("event_type must be an EventType value")
        object.__setattr__(
            self, "subscriber_id",
            require_non_empty_text(self.subscriber_id, "subscriber_id"),
        )
        object.__setattr__(
            self, "reaction_id",
            require_non_empty_text(self.reaction_id, "reaction_id"),
        )
        if self.filter_source is not None and not isinstance(self.filter_source, EventSource):
            raise ValueError("filter_source must be an EventSource value or None")
        object.__setattr__(
            self, "created_at",
                require_datetime_text(self.created_at, "created_at"),
            )


@dataclass(frozen=True, slots=True)
class EventReaction(ContractRecord):
    """A reaction triggered by an event — records what was done and why."""

    reaction_id: str
    event_id: str
    subscription_id: str
    action_taken: str
    result: str
    reacted_at: str

    def __post_init__(self) -> None:
        for f in ("reaction_id", "event_id", "subscription_id", "action_taken", "result"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(
            self, "reacted_at",
            require_datetime_text(self.reacted_at, "reacted_at"),
        )


@dataclass(frozen=True, slots=True)
class EventWindow(ContractRecord):
    """A bounded temporal window for event correlation."""

    window_id: str
    correlation_id: str
    window_start: str
    window_end: str
    event_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "window_id",
            require_non_empty_text(self.window_id, "window_id"),
        )
        object.__setattr__(
            self, "correlation_id",
            require_non_empty_text(self.correlation_id, "correlation_id"),
        )
        object.__setattr__(
            self, "window_start",
            require_datetime_text(self.window_start, "window_start"),
        )
        object.__setattr__(
            self, "window_end",
            require_datetime_text(self.window_end, "window_end"),
        )
        object.__setattr__(
            self, "event_count",
            require_non_negative_int(self.event_count, "event_count"),
        )


@dataclass(frozen=True, slots=True)
class EventCorrelation(ContractRecord):
    """Links causally related events under a shared correlation ID."""

    correlation_id: str
    event_ids: tuple[str, ...]
    root_event_id: str
    description: str
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "correlation_id",
            require_non_empty_text(self.correlation_id, "correlation_id"),
        )
        object.__setattr__(self, "event_ids", freeze_value(list(self.event_ids)))
        if not self.event_ids:
            raise ValueError("event_ids must contain at least one item")
        for eid in self.event_ids:
            require_non_empty_text(eid, "event_id")
        object.__setattr__(
            self, "root_event_id",
            require_non_empty_text(self.root_event_id, "root_event_id"),
        )
        object.__setattr__(
            self, "description",
            require_non_empty_text(self.description, "description"),
        )
        object.__setattr__(
            self, "created_at",
            require_datetime_text(self.created_at, "created_at"),
        )
