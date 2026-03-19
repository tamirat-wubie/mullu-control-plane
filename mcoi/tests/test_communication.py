"""Purpose: verify communication-core — message building, routing, and delivery.
Governance scope: communication plane tests only.
Dependencies: communication engine, contracts, delivery adapter protocol.
Invariants: messages are typed, attribution is explicit, delivery is tracked.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.contracts.communication import (
    CommunicationChannel,
    CommunicationMessage,
    DeliveryResult,
    DeliveryStatus,
)
from mcoi_runtime.core.communication import (
    ApprovalRequest,
    CommunicationEngine,
    EscalationRequest,
    NotificationRequest,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


_CLOCK = "2026-03-19T00:00:00+00:00"


class FakeDeliveryAdapter:
    """Test adapter that records delivered messages."""

    def __init__(self) -> None:
        self.delivered: list[CommunicationMessage] = []

    def deliver(self, message: CommunicationMessage) -> DeliveryResult:
        self.delivered.append(message)
        delivery_id = stable_identifier("delivery", {"message_id": message.message_id})
        return DeliveryResult(
            delivery_id=delivery_id,
            message_id=message.message_id,
            status=DeliveryStatus.DELIVERED,
            channel=message.channel,
            delivered_at=_CLOCK,
        )


def _make_engine(
    adapters: dict[CommunicationChannel, FakeDeliveryAdapter] | None = None,
) -> CommunicationEngine:
    return CommunicationEngine(
        sender_id="agent-1",
        clock=lambda: _CLOCK,
        adapters=adapters,
    )


# --- Contract tests ---


def test_communication_message_validates_fields() -> None:
    msg = CommunicationMessage(
        message_id="msg-1",
        sender_id="sender-1",
        recipient_id="recipient-1",
        channel=CommunicationChannel.APPROVAL,
        message_type="approval_request",
        payload={"key": "value"},
        correlation_id="corr-1",
        created_at=_CLOCK,
    )
    assert msg.message_id == "msg-1"
    assert msg.channel is CommunicationChannel.APPROVAL


def test_communication_message_rejects_empty_fields() -> None:
    with pytest.raises(ValueError, match="message_id"):
        CommunicationMessage(
            message_id="",
            sender_id="s",
            recipient_id="r",
            channel=CommunicationChannel.APPROVAL,
            message_type="t",
            payload={},
            correlation_id="c",
            created_at=_CLOCK,
        )


def test_delivery_result_validates() -> None:
    result = DeliveryResult(
        delivery_id="del-1",
        message_id="msg-1",
        status=DeliveryStatus.DELIVERED,
        channel=CommunicationChannel.NOTIFICATION,
        delivered_at=_CLOCK,
    )
    assert result.status is DeliveryStatus.DELIVERED


# --- Approval request tests ---


def test_approval_request_builds_and_delivers() -> None:
    adapter = FakeDeliveryAdapter()
    engine = _make_engine({CommunicationChannel.APPROVAL: adapter})

    result = engine.request_approval(
        ApprovalRequest(
            subject_id="subject-1",
            goal_id="goal-1",
            action_description="delete /tmp/old",
            reason="cleanup needed",
        ),
        recipient_id="operator-1",
    )

    assert result.status is DeliveryStatus.DELIVERED
    assert len(adapter.delivered) == 1
    msg = adapter.delivered[0]
    assert msg.channel is CommunicationChannel.APPROVAL
    assert msg.sender_id == "agent-1"
    assert msg.recipient_id == "operator-1"
    assert msg.payload["action_description"] == "delete /tmp/old"


# --- Escalation request tests ---


def test_escalation_builds_and_delivers() -> None:
    adapter = FakeDeliveryAdapter()
    engine = _make_engine({CommunicationChannel.ESCALATION: adapter})

    result = engine.escalate(
        EscalationRequest(
            subject_id="subject-1",
            goal_id="goal-1",
            error_code="policy_deny",
            error_message="blocked by policy",
            context={"reason": "blocked knowledge"},
        ),
        recipient_id="operator-1",
    )

    assert result.status is DeliveryStatus.DELIVERED
    msg = adapter.delivered[0]
    assert msg.channel is CommunicationChannel.ESCALATION
    assert msg.payload["error_code"] == "policy_deny"


# --- Notification request tests ---


def test_notification_builds_and_delivers() -> None:
    adapter = FakeDeliveryAdapter()
    engine = _make_engine({CommunicationChannel.NOTIFICATION: adapter})

    result = engine.notify(
        NotificationRequest(
            subject_id="subject-1",
            goal_id="goal-1",
            event_type="execution_complete",
            summary="command finished successfully",
        ),
        recipient_id="operator-1",
    )

    assert result.status is DeliveryStatus.DELIVERED
    msg = adapter.delivered[0]
    assert msg.channel is CommunicationChannel.NOTIFICATION
    assert msg.payload["event_type"] == "execution_complete"


# --- Channel routing tests ---


def test_missing_channel_returns_failed_delivery() -> None:
    engine = _make_engine()  # no adapters registered

    result = engine.request_approval(
        ApprovalRequest(
            subject_id="s-1",
            goal_id="g-1",
            action_description="do something",
            reason="reason",
        ),
        recipient_id="operator-1",
    )

    assert result.status is DeliveryStatus.FAILED
    assert result.error_code == "channel_not_registered"


def test_messages_carry_stable_ids() -> None:
    adapter = FakeDeliveryAdapter()
    engine = _make_engine({CommunicationChannel.APPROVAL: adapter})

    engine.request_approval(
        ApprovalRequest(
            subject_id="s-1",
            goal_id="g-1",
            action_description="act",
            reason="why",
        ),
        recipient_id="op-1",
    )

    msg = adapter.delivered[0]
    assert msg.message_id.startswith("msg-")
    assert msg.correlation_id.startswith("approval-")


def test_approval_request_validates_urgency() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="urgency"):
        ApprovalRequest(
            subject_id="s",
            goal_id="g",
            action_description="a",
            reason="r",
            urgency="invalid",
        )


def test_approval_request_accepts_valid_urgency() -> None:
    for urgency in ("low", "normal", "high", "critical"):
        req = ApprovalRequest(
            subject_id="s",
            goal_id="g",
            action_description="a",
            reason="r",
            urgency=urgency,
        )
        assert req.urgency == urgency
