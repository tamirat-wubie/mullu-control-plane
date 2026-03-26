"""Phase 205D — Governed Event Bus.

Purpose: Decoupled pub/sub for governed runtime events.
    All subsystems publish events; subscribers react without coupling.
    Events are typed, tenant-scoped, and auditable.
Governance scope: event routing only — never modifies source state.
Dependencies: none (pure pub/sub).
Invariants:
  - Events are immutable once published.
  - Subscriber errors don't affect other subscribers or publishers.
  - Event delivery is synchronous within the bus (no async queue).
  - All events carry tenant_id for scoping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from hashlib import sha256
import json


@dataclass(frozen=True, slots=True)
class GovernedEvent:
    """Typed, immutable event on the governed bus."""

    event_id: str
    event_type: str
    tenant_id: str
    source: str  # Subsystem that published the event
    payload: dict[str, Any]
    event_hash: str
    published_at: str


class EventBus:
    """Synchronous governed event bus.

    Publishers emit typed events; subscribers are called synchronously.
    Subscriber errors are isolated — one failing subscriber doesn't
    block others.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._subscribers: dict[str, list[Callable[[GovernedEvent], Any]]] = {}
        self._global_subscribers: list[Callable[[GovernedEvent], Any]] = []
        self._event_counter = 0
        self._history: list[GovernedEvent] = []
        self._errors: list[dict[str, Any]] = []

    def subscribe(self, event_type: str, handler: Callable[[GovernedEvent], Any]) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler: Callable[[GovernedEvent], Any]) -> None:
        """Subscribe to all events."""
        self._global_subscribers.append(handler)

    def publish(
        self,
        event_type: str,
        *,
        tenant_id: str = "",
        source: str = "",
        payload: dict[str, Any] | None = None,
    ) -> GovernedEvent:
        """Publish an event to the bus.

        Returns the published event. Subscriber errors are caught and recorded.
        """
        self._event_counter += 1
        payload = payload or {}
        now = self._clock()

        event_hash = sha256(
            json.dumps({"type": event_type, "payload": payload, "at": now}, sort_keys=True, default=str).encode()
        ).hexdigest()

        event = GovernedEvent(
            event_id=f"evt-{self._event_counter}",
            event_type=event_type,
            tenant_id=tenant_id,
            source=source,
            payload=payload,
            event_hash=event_hash,
            published_at=now,
        )
        self._history.append(event)

        # Deliver to type-specific subscribers
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception as exc:
                self._errors.append({
                    "event_id": event.event_id,
                    "event_type": event_type,
                    "error": str(exc),
                    "at": now,
                })

        # Deliver to global subscribers
        for handler in self._global_subscribers:
            try:
                handler(event)
            except Exception as exc:
                self._errors.append({
                    "event_id": event.event_id,
                    "event_type": event_type,
                    "error": str(exc),
                    "at": now,
                })

        return event

    def history(self, event_type: str | None = None, limit: int = 50) -> list[GovernedEvent]:
        """Query event history."""
        events = self._history
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    @property
    def event_count(self) -> int:
        return len(self._history)

    @property
    def error_count(self) -> int:
        return len(self._errors)

    @property
    def subscriber_count(self) -> int:
        return sum(len(subs) for subs in self._subscribers.values()) + len(self._global_subscribers)

    def subscribed_types(self) -> list[str]:
        return sorted(self._subscribers.keys())

    def summary(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        for event in self._history:
            type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
        return {
            "total_events": self.event_count,
            "total_errors": self.error_count,
            "subscribers": self.subscriber_count,
            "event_types": type_counts,
        }
