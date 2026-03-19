"""Purpose: communication-core — build and route governed messages for approvals, escalations, and notifications.
Governance scope: communication plane core logic only.
Dependencies: communication contracts, invariant helpers.
Invariants:
  - Outbound messages require explicit channel declaration.
  - Message attribution is never fabricated.
  - Delivery is tracked with typed results.
  - No free-form communication — only structured channels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any, Mapping, Protocol

from mcoi_runtime.contracts.communication import (
    CommunicationChannel,
    CommunicationMessage,
    DeliveryResult,
    DeliveryStatus,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from .provider_registry import ProviderRegistry


class DeliveryAdapter(Protocol):
    """Protocol for channel-specific delivery adapters."""

    def deliver(self, message: CommunicationMessage) -> DeliveryResult: ...


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """Request for operator/human approval."""

    subject_id: str
    goal_id: str
    action_description: str
    reason: str
    urgency: str = "normal"

    def __post_init__(self) -> None:
        for field_name in ("subject_id", "goal_id", "action_description", "reason"):
            object.__setattr__(self, field_name, ensure_non_empty_text(field_name, getattr(self, field_name)))
        if self.urgency not in ("low", "normal", "high", "critical"):
            raise RuntimeCoreInvariantError("urgency must be one of: low, normal, high, critical")


@dataclass(frozen=True, slots=True)
class EscalationRequest:
    """Request to escalate a failure or blocked action."""

    subject_id: str
    goal_id: str
    error_code: str
    error_message: str
    context: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("subject_id", "goal_id", "error_code", "error_message"):
            object.__setattr__(self, field_name, ensure_non_empty_text(field_name, getattr(self, field_name)))
        if not isinstance(self.context, Mapping):
            raise RuntimeCoreInvariantError("context must be a mapping")


@dataclass(frozen=True, slots=True)
class NotificationRequest:
    """Notification of completion, status change, or informational event."""

    subject_id: str
    goal_id: str
    event_type: str
    summary: str

    def __post_init__(self) -> None:
        for field_name in ("subject_id", "goal_id", "event_type", "summary"):
            object.__setattr__(self, field_name, ensure_non_empty_text(field_name, getattr(self, field_name)))


class CommunicationEngine:
    """Build and route governed communication messages.

    This engine:
    - Builds typed messages from approval/escalation/notification requests
    - Routes to registered delivery adapters by channel
    - Returns typed delivery results
    - Never fabricates attribution
    - Fails closed on missing channels
    """

    def __init__(
        self,
        *,
        sender_id: str,
        clock: Callable[[], str],
        adapters: Mapping[CommunicationChannel, DeliveryAdapter] | None = None,
        provider_registry: ProviderRegistry | None = None,
        channel_provider_map: Mapping[CommunicationChannel, str] | None = None,
    ) -> None:
        self._sender_id = ensure_non_empty_text("sender_id", sender_id)
        self._clock = clock
        self._adapters: dict[CommunicationChannel, DeliveryAdapter] = dict(adapters or {})
        self._provider_registry = provider_registry
        self._channel_provider_map: dict[CommunicationChannel, str] = dict(channel_provider_map or {})

    def request_approval(
        self,
        request: ApprovalRequest,
        recipient_id: str,
    ) -> DeliveryResult:
        """Send an approval request message."""
        ensure_non_empty_text("recipient_id", recipient_id)
        message = self._build_message(
            channel=CommunicationChannel.APPROVAL,
            recipient_id=recipient_id,
            message_type="approval_request",
            correlation_id=stable_identifier("approval", {
                "subject_id": request.subject_id,
                "goal_id": request.goal_id,
            }),
            payload={
                "subject_id": request.subject_id,
                "goal_id": request.goal_id,
                "action_description": request.action_description,
                "reason": request.reason,
                "urgency": request.urgency,
            },
        )
        return self._deliver(message)

    def escalate(
        self,
        request: EscalationRequest,
        recipient_id: str,
    ) -> DeliveryResult:
        """Send an escalation message."""
        ensure_non_empty_text("recipient_id", recipient_id)
        message = self._build_message(
            channel=CommunicationChannel.ESCALATION,
            recipient_id=recipient_id,
            message_type="escalation",
            correlation_id=stable_identifier("escalation", {
                "subject_id": request.subject_id,
                "goal_id": request.goal_id,
                "error_code": request.error_code,
            }),
            payload={
                "subject_id": request.subject_id,
                "goal_id": request.goal_id,
                "error_code": request.error_code,
                "error_message": request.error_message,
                "context": dict(request.context),
            },
        )
        return self._deliver(message)

    def notify(
        self,
        request: NotificationRequest,
        recipient_id: str,
    ) -> DeliveryResult:
        """Send a notification message."""
        ensure_non_empty_text("recipient_id", recipient_id)
        message = self._build_message(
            channel=CommunicationChannel.NOTIFICATION,
            recipient_id=recipient_id,
            message_type="notification",
            correlation_id=stable_identifier("notification", {
                "subject_id": request.subject_id,
                "goal_id": request.goal_id,
                "event_type": request.event_type,
            }),
            payload={
                "subject_id": request.subject_id,
                "goal_id": request.goal_id,
                "event_type": request.event_type,
                "summary": request.summary,
            },
        )
        return self._deliver(message)

    def _build_message(
        self,
        *,
        channel: CommunicationChannel,
        recipient_id: str,
        message_type: str,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> CommunicationMessage:
        message_id = stable_identifier("msg", {
            "sender_id": self._sender_id,
            "recipient_id": recipient_id,
            "channel": channel.value,
            "message_type": message_type,
            "correlation_id": correlation_id,
        })
        return CommunicationMessage(
            message_id=message_id,
            sender_id=self._sender_id,
            recipient_id=recipient_id,
            channel=channel,
            message_type=message_type,
            payload=payload,
            correlation_id=correlation_id,
            created_at=self._clock(),
        )

    def _deliver(self, message: CommunicationMessage) -> DeliveryResult:
        adapter = self._adapters.get(message.channel)
        if adapter is None:
            delivery_id = stable_identifier("delivery", {
                "message_id": message.message_id,
                "status": "failed",
            })
            return DeliveryResult(
                delivery_id=delivery_id,
                message_id=message.message_id,
                status=DeliveryStatus.FAILED,
                channel=message.channel,
                error_code="channel_not_registered",
            )

        # Provider registry check
        provider_id = self._channel_provider_map.get(message.channel)
        if self._provider_registry is not None and provider_id is not None:
            ok, reason = self._provider_registry.check_invocable(provider_id)
            if not ok:
                delivery_id = stable_identifier("delivery", {
                    "message_id": message.message_id,
                    "status": "failed",
                    "reason": reason,
                })
                return DeliveryResult(
                    delivery_id=delivery_id,
                    message_id=message.message_id,
                    status=DeliveryStatus.FAILED,
                    channel=message.channel,
                    error_code=f"provider:{reason}",
                )

        result = adapter.deliver(message)

        # Update provider health
        if self._provider_registry is not None and provider_id is not None:
            if result.status is DeliveryStatus.DELIVERED:
                self._provider_registry.record_success(provider_id)
            elif result.status is DeliveryStatus.FAILED:
                self._provider_registry.record_failure(provider_id, result.error_code or "delivery_failed")

        return result
