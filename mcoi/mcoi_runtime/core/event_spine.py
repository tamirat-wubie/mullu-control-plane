"""Purpose: append-only event spine — accepts typed events from all planes,
correlates related events, supports deterministic subscriptions/reactions,
and produces durable event history.
Governance scope: event plane core logic only.
Dependencies: event contracts, invariant helpers.
Invariants:
  - Events are append-only — no mutation, no deletion.
  - Subscriptions are deterministic — same event, same reactions.
  - Correlation groups are computed, not fabricated.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.event import (
    EventCorrelation,
    EventEnvelope,
    EventReaction,
    EventRecord,
    EventSource,
    EventSubscription,
    EventType,
    EventWindow,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


class EventSpineEngine:
    """Append-only event spine with subscription-based reactions and correlation.

    This engine:
    - Accepts typed events from all planes (append-only)
    - Manages deterministic subscriptions
    - Fires reactions when subscribed events arrive
    - Correlates related events by correlation_id
    - Produces event windows for temporal analysis
    - Wraps events in envelopes for routing
    """

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._events: dict[str, EventRecord] = {}
        self._envelopes: dict[str, EventEnvelope] = {}
        self._subscriptions: dict[str, EventSubscription] = {}
        self._reactions: dict[str, EventReaction] = {}
        self._clock = clock or self._default_clock

    @staticmethod
    def _default_clock() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _now(self) -> str:
        return self._clock()

    # --- Event ingestion ---

    def emit(self, event: EventRecord) -> EventRecord:
        """Append an event to the spine. Duplicate event_ids are rejected."""
        if event.event_id in self._events:
            raise RuntimeCoreInvariantError(f"event already exists: {event.event_id}")
        self._events[event.event_id] = event
        return event

    def emit_and_envelope(
        self,
        event: EventRecord,
        target_subsystems: tuple[str, ...],
        priority: int = 0,
    ) -> EventEnvelope:
        """Emit an event and wrap it in a delivery envelope."""
        # Construct envelope BEFORE emitting (construct-then-commit)
        env_id = stable_identifier("env", {
            "event_id": event.event_id,
        })
        envelope = EventEnvelope(
            envelope_id=env_id,
            event=event,
            target_subsystems=target_subsystems,
            priority=priority,
        )
        # Both constructed — commit atomically
        self.emit(event)
        self._envelopes[envelope.envelope_id] = envelope
        return envelope

    def get_event(self, event_id: str) -> EventRecord | None:
        ensure_non_empty_text("event_id", event_id)
        return self._events.get(event_id)

    def list_events(
        self,
        *,
        event_type: EventType | None = None,
        correlation_id: str | None = None,
        source: EventSource | None = None,
    ) -> tuple[EventRecord, ...]:
        """List events with optional filters."""
        events = sorted(self._events.values(), key=lambda e: (e.emitted_at, e.event_id))
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        if correlation_id is not None:
            ensure_non_empty_text("correlation_id", correlation_id)
            events = [e for e in events if e.correlation_id == correlation_id]
        if source is not None:
            events = [e for e in events if e.source == source]
        return tuple(events)

    # --- Subscriptions ---

    def subscribe(self, subscription: EventSubscription) -> EventSubscription:
        """Register a subscription. Duplicate subscription_ids are rejected."""
        if subscription.subscription_id in self._subscriptions:
            raise RuntimeCoreInvariantError(
                f"subscription already exists: {subscription.subscription_id}"
            )
        self._subscriptions[subscription.subscription_id] = subscription
        return subscription

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription."""
        ensure_non_empty_text("subscription_id", subscription_id)
        if subscription_id not in self._subscriptions:
            raise RuntimeCoreInvariantError(
                f"subscription not found: {subscription_id}"
            )
        del self._subscriptions[subscription_id]

    def list_subscriptions(
        self,
        *,
        event_type: EventType | None = None,
        active_only: bool = True,
    ) -> tuple[EventSubscription, ...]:
        subs = sorted(self._subscriptions.values(), key=lambda s: s.subscription_id)
        if active_only:
            subs = [s for s in subs if s.active]
        if event_type is not None:
            subs = [s for s in subs if s.event_type == event_type]
        return tuple(subs)

    def matching_subscriptions(self, event: EventRecord) -> tuple[EventSubscription, ...]:
        """Find all active subscriptions that match a given event."""
        matches: list[EventSubscription] = []
        for sub in self._subscriptions.values():
            if not sub.active:
                continue
            if sub.event_type != event.event_type:
                continue
            if sub.filter_source is not None and sub.filter_source != event.source:
                continue
            matches.append(sub)
        return tuple(sorted(matches, key=lambda s: s.subscription_id))

    # --- Reactions ---

    def record_reaction(self, reaction: EventReaction) -> EventReaction:
        """Record that a reaction was triggered by an event."""
        if reaction.reaction_id in self._reactions:
            raise RuntimeCoreInvariantError(
                f"reaction already exists: {reaction.reaction_id}"
            )
        if reaction.event_id not in self._events:
            raise RuntimeCoreInvariantError(
                f"event not found: {reaction.event_id}"
            )
        self._reactions[reaction.reaction_id] = reaction
        return reaction

    def list_reactions(
        self,
        *,
        event_id: str | None = None,
    ) -> tuple[EventReaction, ...]:
        reactions = sorted(self._reactions.values(), key=lambda r: r.reaction_id)
        if event_id is not None:
            ensure_non_empty_text("event_id", event_id)
            reactions = [r for r in reactions if r.event_id == event_id]
        return tuple(reactions)

    # --- Correlation ---

    def correlate(self, correlation_id: str) -> EventCorrelation | None:
        """Build a correlation record for all events sharing a correlation_id."""
        ensure_non_empty_text("correlation_id", correlation_id)
        events = self.list_events(correlation_id=correlation_id)
        if not events:
            return None
        event_ids = tuple(e.event_id for e in events)
        root_event_id = events[0].event_id  # earliest by emitted_at
        return EventCorrelation(
            correlation_id=correlation_id,
            event_ids=event_ids,
            root_event_id=root_event_id,
            description=f"correlated {len(events)} events for {correlation_id}",
            created_at=self._now(),
        )

    # --- Event windows ---

    def build_window(self, correlation_id: str) -> EventWindow | None:
        """Build a temporal window for all events in a correlation group."""
        ensure_non_empty_text("correlation_id", correlation_id)
        events = self.list_events(correlation_id=correlation_id)
        if not events:
            return None
        win_id = stable_identifier("win", {"correlation_id": correlation_id})
        return EventWindow(
            window_id=win_id,
            correlation_id=correlation_id,
            window_start=events[0].emitted_at,
            window_end=events[-1].emitted_at,
            event_count=len(events),
        )

    # --- Properties ---

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def subscription_count(self) -> int:
        return len(self._subscriptions)

    @property
    def reaction_count(self) -> int:
        return len(self._reactions)

    # --- Snapshot / restore ---

    def state_hash(self) -> str:
        """Compute a deterministic SHA-256 hash of all spine state.

        Includes events, subscriptions, reactions, and envelopes so that
        checkpoint verification detects divergence in any collection.
        """
        digest_input = json.dumps(
            {
                "events": sorted(self._events.keys()),
                "subscriptions": sorted(self._subscriptions.keys()),
                "reactions": sorted(self._reactions.keys()),
                "envelopes": sorted(self._envelopes.keys()),
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(digest_input).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        """Capture the complete spine state as a serializable dictionary.

        Returns a dict with events, subscriptions, reactions, and envelopes
        in a form suitable for deterministic restoration.
        """
        return {
            "events": {eid: e.to_dict() for eid, e in self._events.items()},
            "subscriptions": {sid: s.to_dict() for sid, s in self._subscriptions.items()},
            "reactions": {rid: r.to_dict() for rid, r in self._reactions.items()},
            "envelopes": {eid: e.to_dict() for eid, e in self._envelopes.items()},
            "state_hash": self.state_hash(),
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        """Restore spine state from a snapshot dictionary.

        Clears all current state and rebuilds from the snapshot.
        Events, subscriptions, reactions, and envelopes are reconstructed
        from their dict representations.

        Atomic: on any reconstruction error, pre-restore state is rolled back.
        """
        # Capture pre-restore state for rollback
        pre_events = dict(self._events)
        pre_subscriptions = dict(self._subscriptions)
        pre_reactions = dict(self._reactions)
        pre_envelopes = dict(self._envelopes)

        self._events.clear()
        self._subscriptions.clear()
        self._reactions.clear()
        self._envelopes.clear()

        try:
            for eid, edict in snapshot.get("events", {}).items():
                self._events[eid] = EventRecord(**edict)

            for sid, sdict in snapshot.get("subscriptions", {}).items():
                self._subscriptions[sid] = EventSubscription(**sdict)

            for rid, rdict in snapshot.get("reactions", {}).items():
                self._reactions[rid] = EventReaction(**rdict)

            for eid, edict in snapshot.get("envelopes", {}).items():
                self._envelopes[eid] = EventEnvelope(**edict)
        except Exception:
            # Rollback to pre-restore state
            self._events.clear()
            self._events.update(pre_events)
            self._subscriptions.clear()
            self._subscriptions.update(pre_subscriptions)
            self._reactions.clear()
            self._reactions.update(pre_reactions)
            self._envelopes.clear()
            self._envelopes.update(pre_envelopes)
            raise
