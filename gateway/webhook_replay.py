"""Webhook Replay — Re-process failed events from the event log.

Purpose: Replays failed or errored webhook events through the gateway
    router, enabling recovery from transient failures and debugging
    of integration issues.
Governance scope: replay orchestration only.
Dependencies: WebhookEventLog, GatewayRouter.
Invariants:
  - Replay is explicit (never automatic — requires operator action).
  - Replayed events are recorded in the event log with "replayed" status.
  - Replay respects dedup (if message_id already processed, returns cached).
  - Replay results are tracked for audit trail.
  - Thread-safe — concurrent replays are safe.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Result of a single event replay."""

    event_id: str
    original_status: str
    replay_status: str  # "success", "failed", "skipped"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ReplayBatchResult:
    """Result of a batch replay operation."""

    total: int
    succeeded: int
    failed: int
    skipped: int
    results: tuple[ReplayResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
        }


class WebhookReplayEngine:
    """Replays failed webhook events through the gateway.

    Usage:
        engine = WebhookReplayEngine(event_log=log, router=router)

        # Replay a single event
        result = engine.replay_event("evt-42")

        # Replay all failed events for a channel
        batch = engine.replay_failed(channel="whatsapp", limit=10)
    """

    def __init__(
        self,
        *,
        event_log: Any,  # WebhookEventLog
        router: Any | None = None,  # GatewayRouter (optional for testing)
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._event_log = event_log
        self._router = router
        self._clock = clock or (lambda: "")
        self._lock = threading.Lock()
        self._replay_count = 0
        self._success_count = 0
        self._failure_count = 0

    def replay_event(
        self,
        event_id: str,
        *,
        processor: Callable[[str, str, str], str] | None = None,
    ) -> ReplayResult:
        """Replay a single event by ID.

        Args:
            event_id: The event to replay.
            processor: Optional callback(channel, sender_id, body) -> outcome.
                If not provided, uses self._router.
        """
        event = self._event_log.get(event_id)
        if event is None:
            return ReplayResult(
                event_id=event_id, original_status="unknown",
                replay_status="skipped", detail="event not found",
            )

        # Skip if already successfully processed
        if event.status == "processed":
            return ReplayResult(
                event_id=event_id, original_status=event.status,
                replay_status="skipped", detail="already processed",
            )

        with self._lock:
            self._replay_count += 1

        try:
            if processor is not None:
                outcome = processor(event.channel, event.sender_id, event.body_preview)
            elif self._router is not None:
                from gateway.router import GatewayMessage
                msg = GatewayMessage(
                    message_id=event.message_id or f"replay-{event.event_id}",
                    channel=event.channel,
                    sender_id=event.sender_id,
                    body=event.body_preview,
                )
                response = self._router.handle_message(msg)
                outcome = "processed" if response.governed else "failed"
            else:
                outcome = "no_processor"

            # Record replay in event log
            self._event_log.record(
                channel=event.channel,
                sender_id=event.sender_id,
                message_id=event.message_id,
                status=f"replayed:{outcome}",
                outcome_detail=f"replay of {event_id}",
            )

            success = outcome in ("processed", "success")
            with self._lock:
                if success:
                    self._success_count += 1
                else:
                    self._failure_count += 1

            return ReplayResult(
                event_id=event_id,
                original_status=event.status,
                replay_status="success" if success else "failed",
                detail=outcome,
            )

        except Exception as exc:
            with self._lock:
                self._failure_count += 1
            return ReplayResult(
                event_id=event_id,
                original_status=event.status,
                replay_status="failed",
                detail=f"replay error ({type(exc).__name__})",
            )

    def replay_failed(
        self,
        *,
        channel: str = "",
        limit: int = 50,
        processor: Callable[[str, str, str], str] | None = None,
    ) -> ReplayBatchResult:
        """Replay all failed/errored events, optionally filtered by channel."""
        events = self._event_log.query(status="error", channel=channel, limit=limit)
        results: list[ReplayResult] = []
        succeeded = 0
        failed = 0
        skipped = 0

        for event in events:
            result = self.replay_event(event.event_id, processor=processor)
            results.append(result)
            if result.replay_status == "success":
                succeeded += 1
            elif result.replay_status == "failed":
                failed += 1
            else:
                skipped += 1

        return ReplayBatchResult(
            total=len(results),
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            results=tuple(results),
        )

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_replays": self._replay_count,
                "succeeded": self._success_count,
                "failed": self._failure_count,
            }
