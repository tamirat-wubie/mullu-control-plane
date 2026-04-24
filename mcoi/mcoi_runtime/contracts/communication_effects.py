"""Purpose: typed communication delivery receipts for observed effect assurance.
Governance scope: outbound communication evidence contracts only.
Dependencies: communication contracts, contract base helpers, and Python dataclasses.
Invariants: receipts expose hashed message evidence and provider route metadata without credentials or raw body content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text
from .communication import CommunicationChannel, DeliveryStatus


@dataclass(frozen=True, slots=True)
class CommunicationDeliveryReceipt(ContractRecord):
    """Observed outbound communication delivery evidence."""

    receipt_id: str
    delivery_id: str
    message_id: str
    channel: CommunicationChannel
    status: DeliveryStatus
    provider: str
    recipient_hash: str
    subject_hash: str
    body_hash: str
    evidence_ref: str
    attempted_at: str
    delivered_at: str | None = None
    error_code: str | None = None
    transport_security: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "delivery_id",
            "message_id",
            "provider",
            "recipient_hash",
            "subject_hash",
            "body_hash",
            "evidence_ref",
        ):
            if not isinstance(getattr(self, field_name), str) or not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must be a non-empty string")
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.channel, CommunicationChannel):
            raise ValueError("channel must be a CommunicationChannel value")
        if not isinstance(self.status, DeliveryStatus):
            raise ValueError("status must be a DeliveryStatus value")
        object.__setattr__(self, "attempted_at", require_datetime_text(self.attempted_at, "attempted_at"))
        if self.delivered_at is not None:
            object.__setattr__(self, "delivered_at", require_datetime_text(self.delivered_at, "delivered_at"))
        for optional_text in ("error_code", "transport_security"):
            value = getattr(self, optional_text)
            if value is not None:
                object.__setattr__(self, optional_text, require_non_empty_text(value, optional_text))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
