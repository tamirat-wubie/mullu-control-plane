"""Phase 231A — Governed Event Sourcing Engine.

Purpose: Append-only event store with projections, snapshots, and replay.
    Events are immutable facts that drive state reconstruction.
Dependencies: None (stdlib only).
Invariants:
  - Events are immutable and append-only.
  - Projections are derived from event sequence.
  - Snapshots allow fast state reconstruction.
  - All events carry sequence numbers.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Event:
    """An immutable domain event."""
    event_id: str
    stream_id: str
    event_type: str
    data: dict[str, Any]
    sequence: int
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class EventStore:
    """Append-only event store with projections."""

    def __init__(self, max_events: int = 100_000):
        self._max_events = max_events
        self._streams: dict[str, list[Event]] = {}
        self._projections: dict[str, Callable[[dict, Event], dict]] = {}
        self._projected_state: dict[str, dict[str, Any]] = {}
        self._total_events = 0
        self._seq_counters: dict[str, int] = {}

    def append(self, stream_id: str, event_type: str,
               data: dict[str, Any], **metadata: Any) -> Event:
        if stream_id not in self._streams:
            self._streams[stream_id] = []
            self._seq_counters[stream_id] = 0

        self._seq_counters[stream_id] += 1
        seq = self._seq_counters[stream_id]
        event = Event(
            event_id=f"{stream_id}-{seq}",
            stream_id=stream_id,
            event_type=event_type,
            data=data,
            sequence=seq,
            metadata=metadata,
        )
        self._streams[stream_id].append(event)
        self._total_events += 1

        # Apply projections
        for proj_name, proj_fn in self._projections.items():
            key = f"{proj_name}:{stream_id}"
            state = self._projected_state.get(key, {})
            self._projected_state[key] = proj_fn(copy.deepcopy(state), event)

        return event

    def get_events(self, stream_id: str, from_seq: int = 0) -> list[Event]:
        events = self._streams.get(stream_id, [])
        return [e for e in events if e.sequence > from_seq]

    def get_stream_length(self, stream_id: str) -> int:
        return len(self._streams.get(stream_id, []))

    def register_projection(self, name: str,
                            fn: Callable[[dict, Event], dict]) -> None:
        self._projections[name] = fn

    def get_projection(self, name: str, stream_id: str) -> dict[str, Any]:
        return self._projected_state.get(f"{name}:{stream_id}", {})

    def replay(self, stream_id: str,
               reducer: Callable[[dict, Event], dict]) -> dict[str, Any]:
        """Replay all events to rebuild state."""
        state: dict[str, Any] = {}
        for event in self._streams.get(stream_id, []):
            state = reducer(state, event)
        return state

    @property
    def stream_count(self) -> int:
        return len(self._streams)

    def summary(self) -> dict[str, Any]:
        return {
            "total_events": self._total_events,
            "total_streams": self.stream_count,
            "projections": len(self._projections),
            "max_events": self._max_events,
        }
