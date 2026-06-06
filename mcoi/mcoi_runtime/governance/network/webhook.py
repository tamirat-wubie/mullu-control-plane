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
import threading
from urllib.parse import urlparse

from mcoi_runtime.governance.network.ssrf import is_private_url as _is_private_url


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


@dataclass(frozen=True, slots=True)
class WebhookMutationReceipt:
    """Evidence record for webhook subscription and delivery state mutations."""

    receipt_id: str
    mutation_type: str
    effect_name: str
    tenant_id: str
    subject_ref: str
    evidence_ref: str
    before_count: int
    after_count: int
    recorded_at: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "mutation_type": self.mutation_type,
            "effect_name": self.effect_name,
            "tenant_id": self.tenant_id,
            "subject_ref": self.subject_ref,
            "evidence_ref": self.evidence_ref,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "recorded_at": self.recorded_at,
            "metadata": dict(self.metadata),
        }

    def to_effect_record(self) -> Any:
        from mcoi_runtime.contracts.execution import EffectRecord

        return EffectRecord(
            name=self.effect_name,
            details={
                "effect_id": self.effect_name,
                "source": "webhook_manager",
                "evidence_ref": self.evidence_ref,
                "observed_value": self.to_dict(),
            },
        )


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
        self._mutation_receipts: list[WebhookMutationReceipt] = []
        self._delivery_counter: int = 0
        # FastAPI runs sync handlers in a threadpool, so subscribe / unsubscribe /
        # emit can run concurrently. This lock guards the racy mutations: the
        # delivery-id counter (an unlocked ``+= 1`` would emit duplicate wh-N
        # ids), the check-then-set in subscribe, and -- crucially -- it lets emit
        # snapshot the subscriptions before iterating, so a concurrent
        # subscribe/unsubscribe cannot raise "dictionary changed size during
        # iteration". Slow work (DNS-based SSRF checks, HMAC) stays OUTSIDE it.
        self._lock = threading.Lock()

    def subscribe(self, sub: WebhookSubscription) -> WebhookSubscription:
        """Register a webhook subscription. Rejects private/internal URLs (SSRF prevention)."""
        # SSRF check is a DNS lookup -- keep it OUTSIDE the lock. (A private URL
        # paired with a duplicate id now reports the URL rejection first; both
        # are rejections, so the precedence is immaterial.)
        rejection_reason = _webhook_url_rejection_reason(sub.url)
        if rejection_reason == "private_internal_address":
            raise ValueError("webhook URL rejected: private/internal address not allowed")
        if rejection_reason is not None:
            raise ValueError("webhook URL rejected: unsupported scheme or missing host")
        with self._lock:
            if sub.subscription_id in self._subscriptions:
                raise ValueError("subscription already exists")
            before_count = len(self._subscriptions)
            self._subscriptions[sub.subscription_id] = sub
            self._record_mutation(
                mutation_type="subscribe",
                effect_name="webhook_subscription_registered",
                tenant_id=sub.tenant_id,
                subject_ref=f"webhook-subscription:{sub.subscription_id}",
                before_count=before_count,
                after_count=len(self._subscriptions),
                metadata={
                    "event_count": len(sub.events),
                    "enabled": sub.enabled,
                    "target_url_hash": _sha256_text(sub.url),
                    "secret_present": bool(sub.secret),
                },
            )
        return sub

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            before_count = len(self._subscriptions)
            removed = self._subscriptions.pop(subscription_id, None)
            if removed is None:
                return False
            self._record_mutation(
                mutation_type="unsubscribe",
                effect_name="webhook_subscription_removed",
                tenant_id=removed.tenant_id,
                subject_ref=f"webhook-subscription:{subscription_id}",
                before_count=before_count,
                after_count=len(self._subscriptions),
                metadata={
                    "event_count": len(removed.events),
                    "enabled": removed.enabled,
                    "target_url_hash": _sha256_text(removed.url),
                },
            )
        return True

    def get_subscription(self, subscription_id: str) -> WebhookSubscription | None:
        return self._subscriptions.get(subscription_id)

    def list_subscriptions(self, tenant_id: str | None = None) -> list[WebhookSubscription]:
        with self._lock:
            subs = list(self._subscriptions.values())
        if tenant_id is not None:
            subs = [s for s in subs if s.tenant_id == tenant_id]
        return subs

    def emit(self, event: str, payload: dict[str, Any], tenant_id: str = "") -> list[WebhookDelivery]:
        """Emit an event — queues deliveries to all matching subscriptions."""
        deliveries: list[WebhookDelivery] = []

        # Snapshot the matching subscriptions UNDER the lock, then iterate the
        # snapshot. Iterating self._subscriptions directly would raise
        # "dictionary changed size during iteration" if another thread
        # subscribes/unsubscribes mid-emit.
        with self._lock:
            candidates = [
                sub
                for sub in self._subscriptions.values()
                if sub.enabled
                and event in sub.events
                and not (tenant_id and sub.tenant_id != tenant_id and sub.tenant_id != "*")
            ]

        for sub in candidates:
            # v4.29.0 (audit F9): re-check SSRF policy at delivery time,
            # not just at registration. A subscription's hostname could
            # have flipped to a private IP since registration (DNS
            # rebinding by an attacker controlling the operator's
            # subscribed domain). Block the outbound delivery when this happens:
            # the subscription stays registered while delivery_history and
            # mutation receipts retain the blocked attempt. No outbound
            # request fires. DNS lookup -- stays OUTSIDE the lock.
            rejection_reason = _webhook_url_rejection_reason(sub.url)
            if rejection_reason is not None:
                block_reason = (
                    "delivery_url_private"
                    if rejection_reason == "private_internal_address"
                    else "delivery_url_invalid"
                )
                with self._lock:
                    self._delivery_counter += 1
                    delivery_id = f"wh-{self._delivery_counter}"
                    delivery = WebhookDelivery(
                        delivery_id=delivery_id,
                        subscription_id=sub.subscription_id,
                        event=event,
                        payload=payload,
                        signature="",
                        status="failed",
                        created_at=self._clock(),
                    )
                    self._deliveries.append(delivery)
                    self._record_mutation(
                        mutation_type="emit_blocked",
                        effect_name="webhook_delivery_blocked",
                        tenant_id=sub.tenant_id,
                        subject_ref=f"webhook-delivery:{delivery_id}",
                        before_count=len(self._deliveries) - 1,
                        after_count=len(self._deliveries),
                        metadata={
                            "subscription_id_hash": _sha256_text(sub.subscription_id),
                            "event": event,
                            "payload_hash": _sha256_json(payload),
                            "block_reason": block_reason,
                            "target_url_hash": _sha256_text(sub.url),
                        },
                    )
                continue

            # Compute HMAC signature OUTSIDE the lock (per-delivery CPU work).
            signature = ""
            if sub.secret:
                payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
                signature = hmac.new(
                    sub.secret.encode(), payload_bytes, sha256
                ).hexdigest()

            # Lock only the racy section: id counter + delivery append + receipt.
            with self._lock:
                self._delivery_counter += 1
                delivery_id = f"wh-{self._delivery_counter}"
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
                self._record_mutation(
                    mutation_type="emit",
                    effect_name="webhook_delivery_queued",
                    tenant_id=sub.tenant_id,
                    subject_ref=f"webhook-delivery:{delivery_id}",
                    before_count=len(self._deliveries) - 1,
                    after_count=len(self._deliveries),
                    metadata={
                        "subscription_id_hash": _sha256_text(sub.subscription_id),
                        "event": event,
                        "payload_hash": _sha256_json(payload),
                        "signature_present": bool(signature),
                    },
                )
            deliveries.append(delivery)

        with self._lock:
            if len(self._deliveries) > self._MAX_DELIVERIES:
                self._deliveries = self._deliveries[-self._MAX_DELIVERIES:]
            if len(self._mutation_receipts) > self._MAX_DELIVERIES:
                self._mutation_receipts = self._mutation_receipts[-self._MAX_DELIVERIES:]

        return deliveries

    def delivery_history(self, limit: int = 50) -> list[WebhookDelivery]:
        if limit <= 0:
            return []
        return self._deliveries[-limit:]

    def mutation_receipts(self, limit: int = 50) -> tuple[WebhookMutationReceipt, ...]:
        if limit <= 0:
            return ()
        return tuple(self._mutation_receipts[-limit:])

    def effect_records(self, limit: int = 50) -> tuple[Any, ...]:
        return tuple(receipt.to_effect_record() for receipt in self.mutation_receipts(limit=limit))

    @property
    def subscription_count(self) -> int:
        return len(self._subscriptions)

    @property
    def delivery_count(self) -> int:
        return len(self._deliveries)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            subscriptions = len(self._subscriptions)
            deliveries = len(self._deliveries)
            mutation_receipts = len(self._mutation_receipts)
            failed_deliveries = sum(
                1 for delivery in self._deliveries if delivery.status == "failed"
            )
        return {
            "subscriptions": subscriptions,
            "deliveries": deliveries,
            "failed_deliveries": failed_deliveries,
            "mutation_receipts": mutation_receipts,
            "events": list(EVENTS.keys()),
        }

    def _record_mutation(
        self,
        *,
        mutation_type: str,
        effect_name: str,
        tenant_id: str,
        subject_ref: str,
        before_count: int,
        after_count: int,
        metadata: dict[str, Any],
    ) -> WebhookMutationReceipt:
        recorded_at = self._clock()
        material = {
            "mutation_type": mutation_type,
            "effect_name": effect_name,
            "tenant_id": tenant_id,
            "subject_ref": subject_ref,
            "before_count": before_count,
            "after_count": after_count,
            "metadata": metadata,
            "recorded_at": recorded_at,
        }
        receipt_hash = _sha256_json(material)
        receipt = WebhookMutationReceipt(
            receipt_id=f"webhook-mutation-receipt-{receipt_hash[:16]}",
            mutation_type=mutation_type,
            effect_name=effect_name,
            tenant_id=tenant_id,
            subject_ref=subject_ref,
            evidence_ref=f"webhook-mutation:{receipt_hash[:16]}",
            before_count=before_count,
            after_count=after_count,
            recorded_at=recorded_at,
            metadata=metadata,
        )
        self._mutation_receipts.append(receipt)
        return receipt


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")))


def _webhook_url_rejection_reason(url: str) -> str | None:
    """Return a bounded rejection reason for webhook target URLs."""
    try:
        parsed = urlparse(url)
    except Exception:
        return "invalid"
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return "invalid"
    if _is_private_url(url):
        return "private_internal_address"
    return None
