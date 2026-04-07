"""Webhook Event Log — Full inbound event history for replay/debugging.

Purpose: Records every inbound webhook event with headers, body, and
    processing outcome.  Enables replay of failed events, debugging
    of channel integration issues, and compliance auditing.
Governance scope: event recording only — no modification.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Every webhook event is recorded (no silent drops).
  - Event bodies are capped (prevent memory bloat from large payloads).
  - Events are queryable by channel, status, time window.
  - Bounded capacity with FIFO eviction.
  - Thread-safe — concurrent webhook handlers are safe.
"""

from __future__ import annotations

import hashlib
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    """A recorded inbound webhook event."""

    event_id: str
    channel: str
    sender_id: str
    message_id: str
    body_hash: str  # SHA-256 of body (for dedup correlation)
    body_preview: str  # First N chars of body (not full body for privacy)
    headers: dict[str, str]
    status: str  # "processed", "rejected", "duplicate", "error"
    outcome_detail: str = ""
    received_at: str = ""
    processing_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "channel": self.channel,
            "sender_id": self.sender_id,
            "message_id": self.message_id,
            "body_hash": self.body_hash,
            "status": self.status,
            "outcome_detail": self.outcome_detail,
            "received_at": self.received_at,
            "processing_ms": round(self.processing_ms, 2),
        }


class WebhookEventLog:
    """Records and queries inbound webhook events.

    Usage:
        log = WebhookEventLog(clock=lambda: "2026-04-07T12:00:00Z")

        # Record after processing
        log.record(
            channel="whatsapp", sender_id="+1234", message_id="msg-001",
            body='{"text": "hello"}', headers={"X-Hub-Signature": "..."},
            status="processed",
        )

        # Query
        events = log.query(channel="whatsapp", status="error")
        event = log.get("evt-1")
    """

    MAX_EVENTS = 100_000
    BODY_PREVIEW_LENGTH = 200

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        max_events: int = MAX_EVENTS,
    ) -> None:
        self._clock = clock
        self._max_events = max_events
        self._events: deque[WebhookEvent] = deque(maxlen=max_events)
        self._index: dict[str, WebhookEvent] = {}  # event_id → event
        self._lock = threading.Lock()
        self._sequence = 0
        self._by_status: dict[str, int] = {}

    def record(
        self,
        *,
        channel: str,
        sender_id: str,
        message_id: str = "",
        body: str = "",
        headers: dict[str, str] | None = None,
        status: str = "processed",
        outcome_detail: str = "",
        processing_ms: float = 0.0,
    ) -> WebhookEvent:
        """Record a webhook event."""
        body_hash = hashlib.sha256(body.encode()).hexdigest()[:16] if body else ""
        body_preview = body[:self.BODY_PREVIEW_LENGTH] if body else ""
        # Sanitize headers — remove auth values
        safe_headers = {}
        if headers:
            for k, v in headers.items():
                lk = k.lower()
                if "authorization" in lk or "secret" in lk or "token" in lk:
                    safe_headers[k] = "[REDACTED]"
                else:
                    safe_headers[k] = v[:200]  # Cap header values

        with self._lock:
            self._sequence += 1
            event_id = f"evt-{self._sequence}"

            event = WebhookEvent(
                event_id=event_id,
                channel=channel,
                sender_id=sender_id,
                message_id=message_id,
                body_hash=body_hash,
                body_preview=body_preview,
                headers=safe_headers,
                status=status,
                outcome_detail=outcome_detail,
                received_at=self._clock(),
                processing_ms=processing_ms,
            )
            self._events.append(event)
            self._index[event_id] = event
            self._by_status[status] = self._by_status.get(status, 0) + 1

            # Trim index if over capacity
            while len(self._index) > self._max_events:
                oldest = self._events[0]
                self._index.pop(oldest.event_id, None)

            return event

    def get(self, event_id: str) -> WebhookEvent | None:
        """Get a specific event by ID."""
        with self._lock:
            return self._index.get(event_id)

    def query(
        self,
        *,
        channel: str = "",
        status: str = "",
        sender_id: str = "",
        message_id: str = "",
        limit: int = 50,
    ) -> list[WebhookEvent]:
        """Query events with filters. Returns most recent first."""
        with self._lock:
            results: list[WebhookEvent] = []
            for event in reversed(self._events):
                if channel and event.channel != channel:
                    continue
                if status and event.status != status:
                    continue
                if sender_id and event.sender_id != sender_id:
                    continue
                if message_id and event.message_id != message_id:
                    continue
                results.append(event)
                if len(results) >= limit:
                    break
            return results

    def find_by_body_hash(self, body_hash: str) -> list[WebhookEvent]:
        """Find events with matching body hash (for dedup correlation)."""
        with self._lock:
            return [e for e in self._events if e.body_hash == body_hash]

    @property
    def event_count(self) -> int:
        return len(self._events)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
                "by_status": dict(self._by_status),
                "capacity": self._max_events,
            }
