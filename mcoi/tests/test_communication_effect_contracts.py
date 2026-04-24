"""Purpose: verify communication delivery receipt contract invariants.
Governance scope: outbound communication effect evidence typing only.
Dependencies: pytest and communication effect contracts.
Invariants: receipts bind provider, hashed message fields, status, and evidence references without raw message bodies.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.communication import CommunicationChannel, DeliveryStatus
from mcoi_runtime.contracts.communication_effects import CommunicationDeliveryReceipt


def _receipt(**overrides: object) -> CommunicationDeliveryReceipt:
    defaults = {
        "receipt_id": "comm-receipt-1",
        "delivery_id": "delivery-1",
        "message_id": "message-1",
        "channel": CommunicationChannel.NOTIFICATION,
        "status": DeliveryStatus.DELIVERED,
        "provider": "smtp",
        "recipient_hash": "recipient-hash",
        "subject_hash": "subject-hash",
        "body_hash": "body-hash",
        "evidence_ref": "communication-delivery:message-1:comm-receipt-1",
        "attempted_at": "2026-03-19T00:00:00+00:00",
        "delivered_at": "2026-03-19T00:00:01+00:00",
        "transport_security": "starttls",
    }
    defaults.update(overrides)
    return CommunicationDeliveryReceipt(**defaults)


def test_communication_delivery_receipt_accepts_hashed_evidence() -> None:
    receipt = _receipt(metadata={"message_type": "notification"})

    assert receipt.status is DeliveryStatus.DELIVERED
    assert receipt.channel is CommunicationChannel.NOTIFICATION
    assert receipt.provider == "smtp"
    assert receipt.metadata["message_type"] == "notification"


def test_communication_delivery_receipt_rejects_missing_body_hash() -> None:
    with pytest.raises(ValueError, match="^body_hash must be a non-empty string$") as exc_info:
        _receipt(body_hash="")

    message = str(exc_info.value)
    assert "body_hash" in message
    assert "body-hash" not in message
    assert "non-empty" in message


def test_communication_delivery_receipt_accepts_failed_status_with_error() -> None:
    receipt = _receipt(
        status=DeliveryStatus.FAILED,
        delivered_at=None,
        error_code="smtp_error:SMTPException",
    )

    assert receipt.status is DeliveryStatus.FAILED
    assert receipt.delivered_at is None
    assert receipt.error_code == "smtp_error:SMTPException"
    assert receipt.evidence_ref.startswith("communication-delivery:")
