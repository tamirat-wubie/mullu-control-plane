"""Phase 225B — Notification Dispatcher (Multi-Channel).

Purpose: Send governed notifications through multiple channels (webhook,
    email-like, in-app) with priority, deduplication, and delivery tracking.
Dependencies: None (stdlib only).
Invariants:
  - Notifications are immutable once created.
  - Each notification has a unique ID.
  - Duplicate notifications (same hash within window) are suppressed.
  - All deliveries are tracked.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class NotificationChannel(Enum):
    WEBHOOK = "webhook"
    EMAIL = "email"
    IN_APP = "in_app"
    SLACK = "slack"


@unique
class NotificationPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Notification:
    """A governed notification."""
    notification_id: str
    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    tenant_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def dedup_hash(self) -> str:
        return hashlib.sha256(
            f"{self.channel.value}:{self.recipient}:{self.subject}".encode()
        ).hexdigest()[:16]


@dataclass
class DeliveryRecord:
    """Tracks delivery of a notification."""
    notification_id: str
    channel: NotificationChannel
    recipient: str
    delivered: bool
    timestamp: float
    error: str = ""


class NotificationDispatcher:
    """Multi-channel notification dispatcher with deduplication."""

    def __init__(self, dedup_window_seconds: float = 300.0,
                 clock: Callable[[], str] | None = None):
        self._dedup_window = dedup_window_seconds
        self._clock = clock
        self._handlers: dict[NotificationChannel, Callable[[Notification], bool]] = {}
        self._deliveries: list[DeliveryRecord] = []
        self._recent_hashes: dict[str, float] = {}
        self._total_sent = 0
        self._total_suppressed = 0
        self._total_failed = 0

    def register_channel(self, channel: NotificationChannel,
                         handler: Callable[[Notification], bool]) -> None:
        self._handlers[channel] = handler

    def send(self, notification: Notification) -> DeliveryRecord:
        # Deduplication check
        now = time.time()
        self._clean_dedup_cache(now)
        dedup_key = notification.dedup_hash
        if dedup_key in self._recent_hashes:
            self._total_suppressed += 1
            return DeliveryRecord(
                notification_id=notification.notification_id,
                channel=notification.channel,
                recipient=notification.recipient,
                delivered=False, timestamp=now, error="Deduplicated",
            )
        self._recent_hashes[dedup_key] = now

        handler = self._handlers.get(notification.channel)
        if not handler:
            self._total_failed += 1
            record = DeliveryRecord(
                notification_id=notification.notification_id,
                channel=notification.channel,
                recipient=notification.recipient,
                delivered=False, timestamp=now,
                error=f"No handler for {notification.channel.value}",
            )
            self._deliveries.append(record)
            return record

        try:
            success = handler(notification)
        except Exception as e:
            success = False
            record = DeliveryRecord(
                notification_id=notification.notification_id,
                channel=notification.channel,
                recipient=notification.recipient,
                delivered=False, timestamp=now, error=str(e),
            )
            self._deliveries.append(record)
            self._total_failed += 1
            return record

        if success:
            self._total_sent += 1
        else:
            self._total_failed += 1

        record = DeliveryRecord(
            notification_id=notification.notification_id,
            channel=notification.channel,
            recipient=notification.recipient,
            delivered=success, timestamp=now,
        )
        self._deliveries.append(record)
        return record

    def _clean_dedup_cache(self, now: float) -> None:
        expired = [k for k, t in self._recent_hashes.items()
                   if now - t > self._dedup_window]
        for k in expired:
            del self._recent_hashes[k]

    @property
    def channel_count(self) -> int:
        return len(self._handlers)

    def summary(self) -> dict[str, Any]:
        return {
            "registered_channels": self.channel_count,
            "total_sent": self._total_sent,
            "total_suppressed": self._total_suppressed,
            "total_failed": self._total_failed,
            "total_deliveries": len(self._deliveries),
        }
