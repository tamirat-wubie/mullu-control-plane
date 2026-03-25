"""Purpose: settlement / payments / collections runtime contracts.
Governance scope: typed descriptors for payments, settlements, collections,
    dunning notices, cash applications, refunds, writeoffs, aging snapshots,
    settlement decisions, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every payment has explicit amount and method.
  - Collections require invoice linkage.
  - Disputes pause collection progression.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PaymentStatus(Enum):
    """Status of a payment."""
    PENDING = "pending"
    CLEARED = "cleared"
    FAILED = "failed"
    REVERSED = "reversed"


class SettlementStatus(Enum):
    """Status of a settlement."""
    OPEN = "open"
    PARTIAL = "partial"
    SETTLED = "settled"
    DISPUTED = "disputed"
    WRITTEN_OFF = "written_off"


class CollectionStatus(Enum):
    """Status of a collection case."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class WriteoffDisposition(Enum):
    """Disposition of a writeoff."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVERSED = "reversed"


class PaymentMethodKind(Enum):
    """Kind of payment method."""
    BANK_TRANSFER = "bank_transfer"
    CREDIT_CARD = "credit_card"
    CHECK = "check"
    WIRE = "wire"
    ACH = "ach"
    CRYPTO = "crypto"


class DunningSeverity(Enum):
    """Severity of a dunning notice."""
    REMINDER = "reminder"
    WARNING = "warning"
    FINAL_NOTICE = "final_notice"
    ESCALATION = "escalation"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PaymentRecord(ContractRecord):
    """A payment received against an invoice."""

    payment_id: str = ""
    invoice_id: str = ""
    account_id: str = ""
    amount: float = 0.0
    currency: str = ""
    method: PaymentMethodKind = PaymentMethodKind.BANK_TRANSFER
    status: PaymentStatus = PaymentStatus.PENDING
    reference: str = ""
    received_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payment_id", require_non_empty_text(self.payment_id, "payment_id"))
        object.__setattr__(self, "invoice_id", require_non_empty_text(self.invoice_id, "invoice_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        object.__setattr__(self, "currency", require_non_empty_text(self.currency, "currency"))
        if not isinstance(self.method, PaymentMethodKind):
            raise ValueError("method must be a PaymentMethodKind")
        if not isinstance(self.status, PaymentStatus):
            raise ValueError("status must be a PaymentStatus")
        require_datetime_text(self.received_at, "received_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SettlementRecord(ContractRecord):
    """A settlement tracking the balance state of an invoice."""

    settlement_id: str = ""
    invoice_id: str = ""
    account_id: str = ""
    total_amount: float = 0.0
    paid_amount: float = 0.0
    credit_applied: float = 0.0
    outstanding: float = 0.0
    status: SettlementStatus = SettlementStatus.OPEN
    currency: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "settlement_id", require_non_empty_text(self.settlement_id, "settlement_id"))
        object.__setattr__(self, "invoice_id", require_non_empty_text(self.invoice_id, "invoice_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "total_amount", require_non_negative_float(self.total_amount, "total_amount"))
        object.__setattr__(self, "paid_amount", require_non_negative_float(self.paid_amount, "paid_amount"))
        object.__setattr__(self, "credit_applied", require_non_negative_float(self.credit_applied, "credit_applied"))
        object.__setattr__(self, "outstanding", require_non_negative_float(self.outstanding, "outstanding"))
        if not isinstance(self.status, SettlementStatus):
            raise ValueError("status must be a SettlementStatus")
        object.__setattr__(self, "currency", require_non_empty_text(self.currency, "currency"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CollectionCase(ContractRecord):
    """A collection case for an unpaid invoice."""

    case_id: str = ""
    invoice_id: str = ""
    account_id: str = ""
    status: CollectionStatus = CollectionStatus.OPEN
    outstanding_amount: float = 0.0
    dunning_count: int = 0
    opened_at: str = ""
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "invoice_id", require_non_empty_text(self.invoice_id, "invoice_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        if not isinstance(self.status, CollectionStatus):
            raise ValueError("status must be a CollectionStatus")
        object.__setattr__(self, "outstanding_amount", require_non_negative_float(self.outstanding_amount, "outstanding_amount"))
        object.__setattr__(self, "dunning_count", require_non_negative_int(self.dunning_count, "dunning_count"))
        require_datetime_text(self.opened_at, "opened_at")
        # closed_at is optional — only validate if non-empty
        if self.closed_at:
            require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DunningNotice(ContractRecord):
    """A dunning notice sent for a collection case."""

    notice_id: str = ""
    case_id: str = ""
    account_id: str = ""
    severity: DunningSeverity = DunningSeverity.REMINDER
    message: str = ""
    sent_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "notice_id", require_non_empty_text(self.notice_id, "notice_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        if not isinstance(self.severity, DunningSeverity):
            raise ValueError("severity must be a DunningSeverity")
        require_datetime_text(self.sent_at, "sent_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CashApplication(ContractRecord):
    """Application of a payment or credit to an invoice settlement."""

    application_id: str = ""
    settlement_id: str = ""
    payment_id: str = ""
    amount: float = 0.0
    applied_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "application_id", require_non_empty_text(self.application_id, "application_id"))
        object.__setattr__(self, "settlement_id", require_non_empty_text(self.settlement_id, "settlement_id"))
        object.__setattr__(self, "payment_id", require_non_empty_text(self.payment_id, "payment_id"))
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        require_datetime_text(self.applied_at, "applied_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RefundRecord(ContractRecord):
    """A refund issued against a payment."""

    refund_id: str = ""
    payment_id: str = ""
    account_id: str = ""
    amount: float = 0.0
    reason: str = ""
    refunded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "refund_id", require_non_empty_text(self.refund_id, "refund_id"))
        object.__setattr__(self, "payment_id", require_non_empty_text(self.payment_id, "payment_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        require_datetime_text(self.refunded_at, "refunded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WriteoffRecord(ContractRecord):
    """A writeoff of uncollectable balance."""

    writeoff_id: str = ""
    settlement_id: str = ""
    account_id: str = ""
    amount: float = 0.0
    disposition: WriteoffDisposition = WriteoffDisposition.PENDING
    reason: str = ""
    written_off_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "writeoff_id", require_non_empty_text(self.writeoff_id, "writeoff_id"))
        object.__setattr__(self, "settlement_id", require_non_empty_text(self.settlement_id, "settlement_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        if not isinstance(self.disposition, WriteoffDisposition):
            raise ValueError("disposition must be a WriteoffDisposition")
        require_datetime_text(self.written_off_at, "written_off_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AgingSnapshot(ContractRecord):
    """Point-in-time aging snapshot of outstanding balances."""

    snapshot_id: str = ""
    total_settlements: int = 0
    total_open: int = 0
    total_partial: int = 0
    total_settled: int = 0
    total_disputed: int = 0
    total_written_off: int = 0
    total_outstanding: float = 0.0
    total_collected: float = 0.0
    total_refunded: float = 0.0
    total_collection_cases: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_settlements", require_non_negative_int(self.total_settlements, "total_settlements"))
        object.__setattr__(self, "total_open", require_non_negative_int(self.total_open, "total_open"))
        object.__setattr__(self, "total_partial", require_non_negative_int(self.total_partial, "total_partial"))
        object.__setattr__(self, "total_settled", require_non_negative_int(self.total_settled, "total_settled"))
        object.__setattr__(self, "total_disputed", require_non_negative_int(self.total_disputed, "total_disputed"))
        object.__setattr__(self, "total_written_off", require_non_negative_int(self.total_written_off, "total_written_off"))
        object.__setattr__(self, "total_outstanding", require_non_negative_float(self.total_outstanding, "total_outstanding"))
        object.__setattr__(self, "total_collected", require_non_negative_float(self.total_collected, "total_collected"))
        object.__setattr__(self, "total_refunded", require_non_negative_float(self.total_refunded, "total_refunded"))
        object.__setattr__(self, "total_collection_cases", require_non_negative_int(self.total_collection_cases, "total_collection_cases"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SettlementDecision(ContractRecord):
    """A formal settlement decision."""

    decision_id: str = ""
    settlement_id: str = ""
    description: str = ""
    decided_by: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "settlement_id", require_non_empty_text(self.settlement_id, "settlement_id"))
        object.__setattr__(self, "decided_by", require_non_empty_text(self.decided_by, "decided_by"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SettlementClosureReport(ContractRecord):
    """Summary report for settlement cycle closure."""

    report_id: str = ""
    account_id: str = ""
    total_settlements: int = 0
    total_payments: int = 0
    total_refunds: int = 0
    total_writeoffs: int = 0
    total_collection_cases: int = 0
    total_collected: float = 0.0
    total_outstanding: float = 0.0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "total_settlements", require_non_negative_int(self.total_settlements, "total_settlements"))
        object.__setattr__(self, "total_payments", require_non_negative_int(self.total_payments, "total_payments"))
        object.__setattr__(self, "total_refunds", require_non_negative_int(self.total_refunds, "total_refunds"))
        object.__setattr__(self, "total_writeoffs", require_non_negative_int(self.total_writeoffs, "total_writeoffs"))
        object.__setattr__(self, "total_collection_cases", require_non_negative_int(self.total_collection_cases, "total_collection_cases"))
        object.__setattr__(self, "total_collected", require_non_negative_float(self.total_collected, "total_collected"))
        object.__setattr__(self, "total_outstanding", require_non_negative_float(self.total_outstanding, "total_outstanding"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
