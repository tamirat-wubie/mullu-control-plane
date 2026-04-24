"""Purpose: verify communication-core — message building, routing, and delivery.
Governance scope: communication plane tests only.
Dependencies: communication engine, contracts, delivery adapter protocol.
Invariants: messages are typed, attribution is explicit, delivery is tracked.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.communication import (
    CommunicationChannel,
    CommunicationMessage,
    DeliveryResult,
    DeliveryStatus,
)
from mcoi_runtime.contracts.effect_assurance import EffectReconciliation, ReconciliationStatus
from mcoi_runtime.core.communication import (
    ApprovalRequest,
    CommunicationEngine,
    EscalationRequest,
    NotificationRequest,
)
from mcoi_runtime.core.case_runtime import CaseRuntimeEngine
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.event_spine import EventSpineEngine
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


class ReceiptDeliveryAdapter(FakeDeliveryAdapter):
    def deliver(self, message: CommunicationMessage) -> DeliveryResult:
        result = super().deliver(message)
        return DeliveryResult(
            delivery_id=result.delivery_id,
            message_id=result.message_id,
            status=result.status,
            channel=result.channel,
            delivered_at=result.delivered_at,
            metadata={
                "delivery_receipt": {
                    "receipt_id": "delivery-receipt-1",
                    "evidence_ref": f"communication-delivery:{message.message_id}:receipt-1",
                    "attempted_at": _CLOCK,
                    "delivered_at": _CLOCK,
                    "status": "delivered",
                }
            },
        )


class MismatchEffectAssuranceGate(EffectAssuranceGate):
    def reconcile(self, **kwargs) -> EffectReconciliation:
        base = super().reconcile(**kwargs)
        return EffectReconciliation(
            reconciliation_id=base.reconciliation_id,
            command_id=base.command_id,
            effect_plan_id=base.effect_plan_id,
            status=ReconciliationStatus.MISMATCH,
            matched_effects=base.matched_effects,
            missing_effects=("forced_missing_effect",),
            unexpected_effects=base.unexpected_effects,
            verification_result_id=base.verification_result_id,
            case_id=kwargs.get("case_id"),
            decided_at=base.decided_at,
        )


def _make_engine(
    adapters: dict[CommunicationChannel, FakeDeliveryAdapter] | None = None,
    effect_assurance: EffectAssuranceGate | None = None,
    case_runtime: CaseRuntimeEngine | None = None,
) -> CommunicationEngine:
    return CommunicationEngine(
        sender_id="agent-1",
        clock=lambda: _CLOCK,
        adapters=adapters,
        effect_assurance=effect_assurance,
        case_runtime=case_runtime,
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


def test_delivery_with_effect_assurance_reconciles_receipt() -> None:
    adapter = ReceiptDeliveryAdapter()
    engine = _make_engine(
        {CommunicationChannel.NOTIFICATION: adapter},
        effect_assurance=EffectAssuranceGate(clock=lambda: _CLOCK),
    )

    result = engine.notify(
        NotificationRequest(
            subject_id="subject-1",
            goal_id="goal-1",
            event_type="execution_complete",
            summary="done",
        ),
        recipient_id="operator-1",
    )

    assurance = result.metadata["effect_assurance"]
    assert result.status is DeliveryStatus.DELIVERED
    assert assurance["reconciliation_status"] == "match"
    assert assurance["effect_plan_id"].startswith("effect-plan-")
    assert assurance["verification_result_id"].startswith("effect-verification-")


def test_delivery_with_effect_assurance_fails_without_receipt() -> None:
    adapter = FakeDeliveryAdapter()
    engine = _make_engine(
        {CommunicationChannel.NOTIFICATION: adapter},
        effect_assurance=EffectAssuranceGate(clock=lambda: _CLOCK),
    )

    result = engine.notify(
        NotificationRequest(
            subject_id="subject-1",
            goal_id="goal-1",
            event_type="execution_complete",
            summary="done",
        ),
        recipient_id="operator-1",
    )

    assert result.status is DeliveryStatus.FAILED
    assert result.error_code == "effect_assurance_failed"
    assert "required for effect observation" in result.metadata["effect_assurance_error"]


def test_delivery_effect_mismatch_opens_case() -> None:
    case_runtime = CaseRuntimeEngine(EventSpineEngine(clock=lambda: _CLOCK))
    engine = _make_engine(
        {CommunicationChannel.NOTIFICATION: ReceiptDeliveryAdapter()},
        effect_assurance=MismatchEffectAssuranceGate(clock=lambda: _CLOCK),
        case_runtime=case_runtime,
    )

    result = engine.notify(
        NotificationRequest(
            subject_id="subject-1",
            goal_id="goal-1",
            event_type="execution_complete",
            summary="done",
        ),
        recipient_id="operator-1",
    )

    assurance = result.metadata["effect_assurance"]
    assert result.status is DeliveryStatus.FAILED
    assert result.error_code == "effect_reconciliation_mismatch"
    assert assurance["reconciliation_status"] == "mismatch"
    assert assurance["case_id"].startswith("case-delivery-")
    assert case_runtime.open_case_count == 1
    assert case_runtime.evidence_count == 1
    assert case_runtime.finding_count == 1
