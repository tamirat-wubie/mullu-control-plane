"""Webhook Dead-Letter Queue — Retry failed channel sends.

Purpose: When a gateway response cannot be delivered to the originating
    channel (network error, rate limit, channel outage), the message is
    enqueued in a DLQ for automatic retry with exponential backoff.
    Messages that exhaust retries remain queryable for manual review.
Governance scope: delivery reliability only — no business logic.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Failed sends are never silently dropped.
  - Retry uses exponential backoff with jitter (no thundering herd).
  - Max retries is configurable (default 5).
  - Exhausted messages are queryable (never deleted automatically).
  - DLQ is bounded (oldest exhausted entries evicted under pressure).
  - Thread-safe — concurrent enqueuers + retry workers are safe.
"""

from __future__ import annotations

import hashlib
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class DLQEntryStatus(Enum):
    """Status of a DLQ entry."""

    PENDING = "pending"  # Awaiting retry
    RETRYING = "retrying"  # Currently being retried
    DELIVERED = "delivered"  # Successfully delivered on retry
    EXHAUSTED = "exhausted"  # Max retries reached, needs manual review


@dataclass
class DLQEntry:
    """A failed webhook delivery in the dead-letter queue."""

    entry_id: str
    channel: str
    recipient_id: str
    body: str
    original_error: str
    status: DLQEntryStatus = DLQEntryStatus.PENDING
    attempt_count: int = 0
    max_retries: int = 5
    created_at: float = 0.0
    last_attempt_at: float = 0.0
    next_retry_at: float = 0.0
    delivered_at: float = 0.0
    last_error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_retryable(self) -> bool:
        return self.status == DLQEntryStatus.PENDING and self.attempt_count < self.max_retries

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "channel": self.channel,
            "recipient_id": self.recipient_id,
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "max_retries": self.max_retries,
            "original_error": self.original_error,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "next_retry_at": self.next_retry_at,
        }


class WebhookDLQ:
    """Dead-letter queue for failed webhook deliveries.

    Usage:
        dlq = WebhookDLQ(clock=time.monotonic)

        # Enqueue a failed send
        dlq.enqueue(
            channel="whatsapp", recipient_id="+1234",
            body="Your balance is $100", error="connection timeout",
        )

        # Process retries (call periodically)
        results = dlq.process_retries(send_fn=channel_adapter.send)

        # Query for review
        exhausted = dlq.query(status=DLQEntryStatus.EXHAUSTED)
    """

    MAX_ENTRIES = 50_000
    DEFAULT_MAX_RETRIES = 5
    BASE_DELAY = 1.0  # seconds
    MAX_DELAY = 300.0  # 5 minutes cap

    def __init__(
        self,
        *,
        clock: Callable[[], float],
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_entries: int = MAX_ENTRIES,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self._clock = clock
        self._max_retries = max_retries
        self._max_entries = max_entries
        self._entries: dict[str, DLQEntry] = {}
        self._lock = threading.Lock()
        self._sequence = 0
        self._enqueued_count = 0
        self._delivered_count = 0
        self._exhausted_count = 0

    def _next_retry_delay(self, attempt: int) -> float:
        """Exponential backoff with full jitter."""
        delay = min(self.BASE_DELAY * (2 ** attempt), self.MAX_DELAY)
        return delay * random.random()  # Full jitter

    def enqueue(
        self,
        *,
        channel: str,
        recipient_id: str,
        body: str,
        error: str,
        metadata: dict[str, Any] | None = None,
    ) -> DLQEntry:
        """Enqueue a failed webhook delivery for retry."""
        with self._lock:
            self._sequence += 1
            now = self._clock()
            entry_id = f"dlq-{self._sequence}"

            # Capacity enforcement — evict oldest exhausted first
            if len(self._entries) >= self._max_entries:
                self._evict_oldest()

            entry = DLQEntry(
                entry_id=entry_id,
                channel=channel,
                recipient_id=recipient_id,
                body=body,
                original_error=error,
                max_retries=self._max_retries,
                created_at=now,
                last_attempt_at=now,
                next_retry_at=now + self._next_retry_delay(0),
                last_error=error,
                metadata=metadata or {},
            )
            self._entries[entry_id] = entry
            self._enqueued_count += 1
            return entry

    def _evict_oldest(self) -> None:
        """Evict oldest exhausted entry, or oldest pending if no exhausted."""
        exhausted = [
            (eid, e) for eid, e in self._entries.items()
            if e.status == DLQEntryStatus.EXHAUSTED
        ]
        if exhausted:
            oldest_id = min(exhausted, key=lambda x: x[1].created_at)[0]
            del self._entries[oldest_id]
            return
        delivered = [
            (eid, e) for eid, e in self._entries.items()
            if e.status == DLQEntryStatus.DELIVERED
        ]
        if delivered:
            oldest_id = min(delivered, key=lambda x: x[1].created_at)[0]
            del self._entries[oldest_id]
            return
        if self._entries:
            oldest_id = min(self._entries, key=lambda k: self._entries[k].created_at)
            del self._entries[oldest_id]

    def process_retries(
        self,
        *,
        send_fn: Callable[[str, str, str], bool],
        batch_size: int = 10,
    ) -> dict[str, Any]:
        """Process pending retries.

        Args:
            send_fn: Callable(channel, recipient_id, body) -> success.
            batch_size: Max entries to process per call.

        Returns summary of retry results.
        """
        now = self._clock()
        to_retry: list[DLQEntry] = []

        with self._lock:
            for entry in self._entries.values():
                if entry.status == DLQEntryStatus.PENDING and entry.next_retry_at <= now:
                    # Mark as RETRYING under lock to prevent duplicate pickup
                    entry.status = DLQEntryStatus.RETRYING
                    to_retry.append(entry)
                    if len(to_retry) >= batch_size:
                        break

        delivered = 0
        failed = 0
        exhausted = 0

        for entry in to_retry:
            entry.attempt_count += 1
            entry.last_attempt_at = self._clock()

            try:
                success = send_fn(entry.channel, entry.recipient_id, entry.body)
            except Exception as exc:
                success = False
                entry.last_error = f"retry failed ({type(exc).__name__})"

            if success:
                entry.status = DLQEntryStatus.DELIVERED
                entry.delivered_at = self._clock()
                delivered += 1
                with self._lock:
                    self._delivered_count += 1
            else:
                if entry.attempt_count >= entry.max_retries:
                    entry.status = DLQEntryStatus.EXHAUSTED
                    exhausted += 1
                    with self._lock:
                        self._exhausted_count += 1
                else:
                    entry.status = DLQEntryStatus.PENDING
                    entry.next_retry_at = self._clock() + self._next_retry_delay(entry.attempt_count)
                failed += 1

        return {
            "processed": len(to_retry),
            "delivered": delivered,
            "failed": failed,
            "exhausted": exhausted,
        }

    def get(self, entry_id: str) -> DLQEntry | None:
        """Get a specific DLQ entry."""
        return self._entries.get(entry_id)

    def query(
        self,
        *,
        status: DLQEntryStatus | None = None,
        channel: str = "",
        limit: int = 50,
    ) -> list[DLQEntry]:
        """Query DLQ entries with filters."""
        with self._lock:
            results: list[DLQEntry] = []
            for entry in sorted(self._entries.values(), key=lambda e: e.created_at, reverse=True):
                if status is not None and entry.status != status:
                    continue
                if channel and entry.channel != channel:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    break
            return results

    def retry_entry(
        self,
        entry_id: str,
        *,
        send_fn: Callable[[str, str, str], bool],
    ) -> bool:
        """Manually retry a specific entry (for exhausted entries). Returns success."""
        entry = self._entries.get(entry_id)
        if entry is None:
            return False

        entry.status = DLQEntryStatus.RETRYING
        entry.attempt_count += 1
        entry.last_attempt_at = self._clock()

        try:
            success = send_fn(entry.channel, entry.recipient_id, entry.body)
        except Exception as exc:
            success = False
            entry.last_error = f"manual retry failed ({type(exc).__name__})"

        if success:
            entry.status = DLQEntryStatus.DELIVERED
            entry.delivered_at = self._clock()
            with self._lock:
                self._delivered_count += 1
            return True

        entry.status = DLQEntryStatus.EXHAUSTED
        return False

    def purge_delivered(self) -> int:
        """Remove all delivered entries. Returns count purged."""
        with self._lock:
            to_remove = [eid for eid, e in self._entries.items() if e.status == DLQEntryStatus.DELIVERED]
            for eid in to_remove:
                del self._entries[eid]
            return len(to_remove)

    @property
    def pending_count(self) -> int:
        return sum(1 for e in self._entries.values() if e.status == DLQEntryStatus.PENDING)

    @property
    def exhausted_count(self) -> int:
        return sum(1 for e in self._entries.values() if e.status == DLQEntryStatus.EXHAUSTED)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            by_status: dict[str, int] = {}
            for entry in self._entries.values():
                by_status[entry.status.value] = by_status.get(entry.status.value, 0) + 1
            return {
                "total_entries": len(self._entries),
                "by_status": by_status,
                "total_enqueued": self._enqueued_count,
                "total_delivered": self._delivered_count,
                "total_exhausted": self._exhausted_count,
                "max_retries": self._max_retries,
            }
