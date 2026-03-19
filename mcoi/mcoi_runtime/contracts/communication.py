"""Purpose: canonical communication message and delivery result contracts.
Governance scope: communication plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Every message carries explicit sender, recipient, channel, and correlation identity.
  - Every delivery attempt produces a typed result.
  - Message attribution MUST NOT be fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class CommunicationChannel(StrEnum):
    """Canonical communication channels per docs/11_communication_plane.md."""

    APPROVAL = "approval"
    ESCALATION = "escalation"
    NOTIFICATION = "notification"
    EXPLANATION = "explanation"


class DeliveryStatus(StrEnum):
    """Delivery outcome for a communication message."""

    DELIVERED = "delivered"
    FAILED = "failed"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class CommunicationMessage(ContractRecord):
    """A structured message in the communication plane."""

    message_id: str
    sender_id: str
    recipient_id: str
    channel: CommunicationChannel
    message_type: str
    payload: Mapping[str, Any]
    correlation_id: str
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("message_id", "sender_id", "recipient_id", "message_type", "correlation_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.channel, CommunicationChannel):
            raise ValueError("channel must be a CommunicationChannel value")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "payload", freeze_value(self.payload))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class DeliveryResult(ContractRecord):
    """Result of attempting to deliver a communication message."""

    delivery_id: str
    message_id: str
    status: DeliveryStatus
    channel: CommunicationChannel
    delivered_at: str | None = None
    error_code: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "delivery_id", require_non_empty_text(self.delivery_id, "delivery_id"))
        object.__setattr__(self, "message_id", require_non_empty_text(self.message_id, "message_id"))
        if not isinstance(self.status, DeliveryStatus):
            raise ValueError("status must be a DeliveryStatus value")
        if not isinstance(self.channel, CommunicationChannel):
            raise ValueError("channel must be a CommunicationChannel value")
        if self.delivered_at is not None:
            object.__setattr__(self, "delivered_at", require_datetime_text(self.delivered_at, "delivered_at"))
        if self.error_code is not None:
            object.__setattr__(self, "error_code", require_non_empty_text(self.error_code, "error_code"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
