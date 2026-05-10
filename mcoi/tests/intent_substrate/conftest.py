"""Shared fixtures and helpers for intent_substrate tests."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from mcoi_runtime.contracts.event import (
    EventRecord,
    EventSource,
    EventType,
)
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
)


class MutableState:
    """In-memory `StateView` implementation. Tests drive mutations via
    `set` / `unset` / `update`; the resolver consumes it through __call__.

    Thread-safe — the adversarial test mutates concurrently.
    """

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def __call__(self, entity_id: str) -> "Mapping[str, Any] | None":
        with self._lock:
            attrs = self._state.get(entity_id)
            if attrs is None:
                return None
            return dict(attrs)  # immutable copy for the caller

    def set(self, entity_id: str, attrs: Mapping[str, Any]) -> None:
        with self._lock:
            self._state[entity_id] = dict(attrs)

    def update(self, entity_id: str, **changes: Any) -> None:
        with self._lock:
            cur = dict(self._state.get(entity_id, {}))
            cur.update(changes)
            self._state[entity_id] = cur

    def unset(self, entity_id: str) -> None:
        with self._lock:
            self._state.pop(entity_id, None)


class FakeClock:
    """Deterministic clock for tests. Advance manually with `advance`."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def make_owner(name: str = "alice") -> ObligationOwner:
    return ObligationOwner(
        owner_id=name, owner_type="user", display_name=name.capitalize()
    )


def make_deadline(due_iso: str = "2099-12-31T00:00:00+00:00") -> ObligationDeadline:
    return ObligationDeadline(deadline_id=f"dl-{uuid.uuid4().hex[:8]}", due_at=due_iso)


def make_event(
    event_type: EventType = EventType.WORLD_STATE_CHANGED,
    *,
    correlation_id: str = "corr-1",
    source: EventSource = EventSource.WORLD_STATE_ENGINE,
    payload: Mapping[str, Any] | None = None,
) -> EventRecord:
    return EventRecord(
        event_id=f"evt-{uuid.uuid4().hex[:12]}",
        event_type=event_type,
        source=source,
        correlation_id=correlation_id,
        payload=payload or {},
        emitted_at=datetime.now(timezone.utc).isoformat(),
    )
