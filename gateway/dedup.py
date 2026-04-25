"""Gateway Message Deduplication — Idempotent message processing.

Purpose: Prevent duplicate processing when webhooks are retried by
    messaging platforms (WhatsApp, Slack, Telegram, Discord).
    Every message is checked against a TTL-bounded seen set before
    processing.  Duplicate messages return the cached response.
Governance scope: message ingress only — no business logic here.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Dedup key is (channel, sender_id, message_id) — never from body.
  - Seen set is TTL-bounded — old entries expire automatically.
  - Bounded capacity — evicts oldest under memory pressure.
  - Thread-safe — concurrent webhook threads are safe.
  - Cached responses are returned verbatim for duplicates.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class DedupEntry:
    """A cached response for a previously processed message."""

    dedup_key: str
    response: Any  # Cached GatewayResponse
    processed_at: float  # monotonic time
    ttl_seconds: float


@dataclass(frozen=True, slots=True)
class DedupResult:
    """Result of a dedup check."""

    is_duplicate: bool
    cached_response: Any | None = None
    dedup_key: str = ""


class MessageDeduplicator:
    """TTL-bounded message deduplication store.

    Usage in GatewayRouter:
        dedup = MessageDeduplicator()

        # Before processing:
        result = dedup.check(message.channel, message.sender_id, message.message_id)
        if result.is_duplicate:
            return result.cached_response

        # After processing:
        response = process_message(message)
        dedup.record(message.channel, message.sender_id, message.message_id, response)
        return response
    """

    MAX_ENTRIES = 100_000
    DEFAULT_TTL = 300.0  # 5 minutes — covers most webhook retry windows

    def __init__(
        self,
        *,
        default_ttl: float = DEFAULT_TTL,
        max_entries: int = MAX_ENTRIES,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if default_ttl <= 0:
            raise ValueError("default_ttl must be > 0")
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._default_ttl = default_ttl
        self._max_entries = max_entries
        self._clock = clock or time.monotonic
        self._entries: OrderedDict[str, DedupEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hit_count = 0
        self._miss_count = 0
        self._miss_reasons: dict[str, int] = {}
        self._evicted_count = 0
        self._eviction_reasons: dict[str, int] = {}

    def _record_miss(self, reason_code: str) -> None:
        """Record a bounded miss reason for operator summaries."""
        self._miss_count += 1
        self._miss_reasons[reason_code] = self._miss_reasons.get(reason_code, 0) + 1

    def _record_eviction(self, reason_code: str) -> None:
        """Record a bounded eviction reason for operator summaries."""
        self._evicted_count += 1
        self._eviction_reasons[reason_code] = self._eviction_reasons.get(reason_code, 0) + 1

    @staticmethod
    def _make_key(channel: str, sender_id: str, message_id: str) -> str:
        """Build dedup key from message identity (never from body content)."""
        return f"{channel}:{sender_id}:{message_id}"

    def _reap_expired(self) -> int:
        """Remove expired entries. Caller must hold self._lock."""
        now = self._clock()
        reaped = 0
        # OrderedDict preserves insertion order — oldest first
        while self._entries:
            key, entry = next(iter(self._entries.items()))
            if (now - entry.processed_at) > entry.ttl_seconds:
                del self._entries[key]
                reaped += 1
                self._record_eviction("ttl_expired")
            else:
                break  # Remaining entries are newer
        return reaped

    def check(
        self,
        channel: str,
        sender_id: str,
        message_id: str,
    ) -> DedupResult:
        """Check if a message has already been processed.

        Returns DedupResult with is_duplicate=True and cached response
        if the message was previously seen and the TTL hasn't expired.
        """
        if not message_id:
            # No message ID — cannot deduplicate, treat as new
            self._record_miss("missing_message_id")
            return DedupResult(is_duplicate=False)

        key = self._make_key(channel, sender_id, message_id)

        with self._lock:
            self._reap_expired()
            entry = self._entries.get(key)
            if entry is not None:
                now = self._clock()
                if (now - entry.processed_at) <= entry.ttl_seconds:
                    self._hit_count += 1
                    return DedupResult(
                        is_duplicate=True,
                        cached_response=entry.response,
                        dedup_key=key,
                    )
                # Expired — remove it
                del self._entries[key]
                self._record_eviction("ttl_expired")

        self._record_miss("new_message")
        return DedupResult(is_duplicate=False, dedup_key=key)

    def record(
        self,
        channel: str,
        sender_id: str,
        message_id: str,
        response: Any,
        *,
        ttl: float = 0.0,
    ) -> None:
        """Record a processed message and its response for dedup.

        Args:
            channel: Channel name.
            sender_id: Sender identity.
            message_id: Platform message ID.
            response: The response to cache.
            ttl: Custom TTL (0 = use default).
        """
        if not message_id:
            return  # Cannot deduplicate without message ID

        key = self._make_key(channel, sender_id, message_id)
        effective_ttl = ttl if ttl > 0 else self._default_ttl

        with self._lock:
            # Capacity enforcement
            if len(self._entries) >= self._max_entries and key not in self._entries:
                self._reap_expired()
                # If still at capacity after reaping, evict oldest
                while len(self._entries) >= self._max_entries:
                    self._entries.popitem(last=False)
                    self._record_eviction("capacity_pressure")

            self._entries[key] = DedupEntry(
                dedup_key=key,
                response=response,
                processed_at=self._clock(),
                ttl_seconds=effective_ttl,
            )
            # Move to end (most recent)
            self._entries.move_to_end(key)

    def is_seen(self, channel: str, sender_id: str, message_id: str) -> bool:
        """Quick check without returning cached response."""
        return self.check(channel, sender_id, message_id).is_duplicate

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def hit_count(self) -> int:
        return self._hit_count

    @property
    def miss_count(self) -> int:
        return self._miss_count

    def hit_rate(self) -> float:
        total = self._hit_count + self._miss_count
        return round(self._hit_count / total, 4) if total > 0 else 0.0

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._reap_expired()
            return {
                "active_entries": len(self._entries),
                "total_hits": self._hit_count,
                "total_misses": self._miss_count,
                "miss_reasons": dict(sorted(self._miss_reasons.items())),
                "hit_rate": self.hit_rate(),
                "total_evicted": self._evicted_count,
                "eviction_reasons": dict(sorted(self._eviction_reasons.items())),
                "capacity": self._max_entries,
                "default_ttl": self._default_ttl,
            }
