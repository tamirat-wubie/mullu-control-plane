"""Phase 203B — Webhook Notification System.

Purpose: Event-driven webhook notifications for governance events.
    Allows external systems to subscribe to platform events
    (task completions, budget alerts, certification results).
Governance scope: webhook registration and dispatch only.
Dependencies: none (dispatch is dry-run / queue-based, no real HTTP).
Invariants:
  - Webhook payloads are deterministic for a given event.
  - Failed deliveries are recorded for retry/audit.
  - Subscriptions are tenant-scoped.
  - Webhook secrets are validated (HMAC signatures).
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable
import hmac
import json


class WebhookEvent(str):
    """Known webhook event types."""
    pass


# Well-known events
EVENTS = {
    "task.completed": "Fired when a task completes successfully",
    "task.failed": "Fired when a task fails",
    "budget.warning": "Fired when a tenant's budget exceeds 80% utilization",
    "budget.exhausted": "Fired when a tenant's budget is fully spent",
    "certification.passed": "Fired when live-path certification passes",
    "certification.failed": "Fired when live-path certification fails",
    "llm.completed": "Fired after each LLM completion",
    "session.created": "Fired when a new session is created",
    "health.degraded": "Fired when system health drops below threshold",
}


@dataclass(frozen=True, slots=True)
class WebhookSubscription:
    """A webhook subscription targeting a URL for specific events."""

    subscription_id: str
    tenant_id: str
    url: str
    events: tuple[str, ...]  # Event types to subscribe to
    secret: str = ""  # For HMAC signature validation
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class WebhookDelivery:
    """Record of a webhook delivery attempt."""

    delivery_id: str
    subscription_id: str
    event: str
    payload: dict[str, Any]
    signature: str
    status: str  # "queued", "delivered", "failed"
    created_at: str


# v4.29.0 (audit F9): SSRF policy unified with adapters/http_connector via
# core/ssrf_policy. Pre-v4.29 this module had a much weaker check —
# no DNS resolution, no IPv6 link-local, missing Azure / Alibaba / DO
# metadata hostnames. That gap is closed by importing from the shared
# module.
from mcoi_runtime.governance.network.ssrf import is_private_url as _is_private_url


class WebhookManager:
    """Manages webhook subscriptions and delivery queue.

    Does not perform actual HTTP delivery — instead queues deliveries
    for a background worker. This keeps the governance loop non-blocking.
    """

    _MAX_DELIVERIES = 100_000

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._subscriptions: dict[str, WebhookSubscription] = {}
        self._deliveries: list[WebhookDelivery] = []
        self._delivery_counter: int = 0

    def subscribe(self, sub: WebhookSubscription) -> WebhookSubscription:
        """Register a webhook subscription. Rejects private/internal URLs (SSRF prevention)."""
        if sub.subscription_id in self._subscriptions:
            raise ValueError("subscription already exists")
        if _is_private_url(sub.url):
            raise ValueError("webhook URL rejected: private/internal address not allowed")
        self._subscriptions[sub.subscription_id] = sub
        return sub

    def unsubscribe(self, subscription_id: str) -> bool:
        return self._subscriptions.pop(subscription_id, None) is not None

    def get_subscription(self, subscription_id: str) -> WebhookSubscription | None:
        return self._subscriptions.get(subscription_id)

    def list_subscriptions(self, tenant_id: str | None = None) -> list[WebhookSubscription]:
        subs = list(self._subscriptions.values())
        if tenant_id is not None:
            subs = [s for s in subs if s.tenant_id == tenant_id]
        return subs

    def emit(self, event: str, payload: dict[str, Any], tenant_id: str = "") -> list[WebhookDelivery]:
        """Emit an event — queues deliveries to all matching subscriptions."""
        deliveries: list[WebhookDelivery] = []

        for sub in self._subscriptions.values():
            if not sub.enabled:
                continue
            if event not in sub.events:
                continue
            if tenant_id and sub.tenant_id != tenant_id and sub.tenant_id != "*":
                continue

            # v4.29.0 (audit F9): re-check SSRF policy at delivery time,
            # not just at registration. A subscription's hostname could
            # have flipped to a private IP since registration (DNS
            # rebinding by an attacker controlling the operator's
            # subscribed domain). Skip the delivery when this happens —
            # the subscription stays registered (operators can audit
            # the failure pattern via delivery_history) but no actual
            # outbound request fires.
            if _is_private_url(sub.url):
                continue

            self._delivery_counter += 1
            delivery_id = f"wh-{self._delivery_counter}"

            # Compute HMAC signature
            signature = ""
            if sub.secret:
                payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
                signature = hmac.new(
                    sub.secret.encode(), payload_bytes, sha256
                ).hexdigest()

            delivery = WebhookDelivery(
                delivery_id=delivery_id,
                subscription_id=sub.subscription_id,
                event=event,
                payload=payload,
                signature=signature,
                status="queued",
                created_at=self._clock(),
            )
            self._deliveries.append(delivery)
            deliveries.append(delivery)

        if len(self._deliveries) > self._MAX_DELIVERIES:
            self._deliveries = self._deliveries[-self._MAX_DELIVERIES:]

        return deliveries

    def delivery_history(self, limit: int = 50) -> list[WebhookDelivery]:
        return self._deliveries[-limit:]

    @property
    def subscription_count(self) -> int:
        return len(self._subscriptions)

    @property
    def delivery_count(self) -> int:
        return len(self._deliveries)

    def summary(self) -> dict[str, Any]:
        return {
            "subscriptions": self.subscription_count,
            "deliveries": self.delivery_count,
            "events": list(EVENTS.keys()),
        }
