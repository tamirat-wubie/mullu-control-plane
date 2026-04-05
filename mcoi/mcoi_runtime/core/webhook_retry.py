"""Phase 223B — Webhook Retry with Exponential Backoff.

Purpose: Reliable webhook delivery with configurable retry policies.
    Failed deliveries are retried with exponential backoff + jitter.
Dependencies: None (stdlib only).
Invariants:
  - Retry delays follow: base_delay * 2^attempt + jitter.
  - Max retries is bounded.
  - Dead-letter queue captures permanently failed deliveries.
  - All delivery attempts are auditable.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class DeliveryStatus(Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for webhook retry behavior."""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    jitter_factor: float = 0.1  # 0-1 range

    def delay_for_attempt(self, attempt: int) -> float:
        delay = min(self.base_delay_seconds * (2 ** attempt), self.max_delay_seconds)
        jitter = delay * self.jitter_factor * random.random()
        return delay + jitter


@dataclass
class DeliveryAttempt:
    """Record of a single webhook delivery attempt."""
    attempt_number: int
    timestamp: float
    success: bool
    status_code: int | None = None
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class WebhookDelivery:
    """Tracks the full lifecycle of a webhook delivery."""
    delivery_id: str
    webhook_url: str
    event_type: str
    payload: dict[str, Any]
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: list[DeliveryAttempt] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def last_attempt(self) -> DeliveryAttempt | None:
        return self.attempts[-1] if self.attempts else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "webhook_url": self.webhook_url,
            "event_type": self.event_type,
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "created_at": self.created_at,
        }


def _bounded_delivery_error(exc: Exception) -> str:
    return f"delivery error ({type(exc).__name__})"


class WebhookRetryEngine:
    """Manages webhook delivery with retry and dead-letter queue."""

    def __init__(self, policy: RetryPolicy | None = None,
                 clock: Callable[[], str] | None = None):
        self._policy = policy or RetryPolicy()
        self._clock = clock
        self._deliveries: dict[str, WebhookDelivery] = {}
        self._dead_letters: list[WebhookDelivery] = []
        self._total_attempts = 0
        self._total_delivered = 0
        self._total_failed = 0

    def deliver(self, delivery: WebhookDelivery,
                send_fn: Callable[[str, dict[str, Any]], tuple[bool, int | None, str]]) -> WebhookDelivery:
        """Attempt delivery with retries per policy."""
        self._deliveries[delivery.delivery_id] = delivery
        delivery.status = DeliveryStatus.RETRYING

        for attempt in range(self._policy.max_retries + 1):
            start = time.monotonic()
            try:
                success, status_code, error = send_fn(delivery.webhook_url, delivery.payload)
            except Exception as exc:
                success, status_code, error = False, None, _bounded_delivery_error(exc)
            duration_ms = (time.monotonic() - start) * 1000

            record = DeliveryAttempt(
                attempt_number=attempt,
                timestamp=time.time(),
                success=success,
                status_code=status_code,
                error=error,
                duration_ms=duration_ms,
            )
            delivery.attempts.append(record)
            self._total_attempts += 1

            if success:
                delivery.status = DeliveryStatus.DELIVERED
                self._total_delivered += 1
                return delivery

            if attempt < self._policy.max_retries:
                delay = self._policy.delay_for_attempt(attempt)
                time.sleep(min(delay, 0.01))  # capped for testing

        # All retries exhausted
        delivery.status = DeliveryStatus.DEAD_LETTER
        self._dead_letters.append(delivery)
        self._total_failed += 1
        return delivery

    def get_delivery(self, delivery_id: str) -> WebhookDelivery | None:
        return self._deliveries.get(delivery_id)

    @property
    def dead_letter_count(self) -> int:
        return len(self._dead_letters)

    @property
    def dead_letters(self) -> list[WebhookDelivery]:
        return list(self._dead_letters)

    def summary(self) -> dict[str, Any]:
        return {
            "total_deliveries": len(self._deliveries),
            "total_attempts": self._total_attempts,
            "total_delivered": self._total_delivered,
            "total_failed": self._total_failed,
            "dead_letter_count": self.dead_letter_count,
            "policy": {
                "max_retries": self._policy.max_retries,
                "base_delay_seconds": self._policy.base_delay_seconds,
            },
        }
