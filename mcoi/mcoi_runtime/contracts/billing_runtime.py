"""Purpose: revenue / billing / credit runtime contracts.
Governance scope: typed descriptors for billing accounts, invoices, charges,
    credits, penalties, disputes, revenue snapshots, billing decisions,
    violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every charge has explicit kind and amount.
  - Credits require breach linkage.
  - Disputes pause revenue recognition.
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


class BillingStatus(Enum):
    """Status of a billing account."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    DELINQUENT = "delinquent"


class InvoiceStatus(Enum):
    """Status of an invoice."""
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    OVERDUE = "overdue"
    DISPUTED = "disputed"
    VOIDED = "voided"


class ChargeKind(Enum):
    """Kind of billable charge."""
    SERVICE = "service"
    USAGE = "usage"
    SUBSCRIPTION = "subscription"
    OVERAGE = "overage"
    SETUP = "setup"
    PROFESSIONAL_SERVICES = "professional_services"


class CreditDisposition(Enum):
    """Disposition of a credit."""
    PENDING = "pending"
    APPLIED = "applied"
    EXPIRED = "expired"
    VOIDED = "voided"


class DisputeStatus(Enum):
    """Status of an invoice dispute."""
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED_ACCEPTED = "resolved_accepted"
    RESOLVED_REJECTED = "resolved_rejected"
    WITHDRAWN = "withdrawn"


class RevenueRecognitionStatus(Enum):
    """Status of revenue recognition."""
    PENDING = "pending"
    RECOGNIZED = "recognized"
    DEFERRED = "deferred"
    DISPUTED = "disputed"
    WRITTEN_OFF = "written_off"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BillingAccount(ContractRecord):
    """A billing account for a tenant/counterparty."""

    account_id: str = ""
    tenant_id: str = ""
    counterparty: str = ""
    status: BillingStatus = BillingStatus.ACTIVE
    currency: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "counterparty", require_non_empty_text(self.counterparty, "counterparty"))
        if not isinstance(self.status, BillingStatus):
            raise ValueError("status must be a BillingStatus")
        object.__setattr__(self, "currency", require_non_empty_text(self.currency, "currency"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InvoiceRecord(ContractRecord):
    """An invoice issued to a billing account."""

    invoice_id: str = ""
    account_id: str = ""
    tenant_id: str = ""
    status: InvoiceStatus = InvoiceStatus.DRAFT
    total_amount: float = 0.0
    currency: str = ""
    issued_at: str = ""
    due_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "invoice_id", require_non_empty_text(self.invoice_id, "invoice_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.status, InvoiceStatus):
            raise ValueError("status must be an InvoiceStatus")
        object.__setattr__(self, "total_amount", require_non_negative_float(self.total_amount, "total_amount"))
        object.__setattr__(self, "currency", require_non_empty_text(self.currency, "currency"))
        require_datetime_text(self.issued_at, "issued_at")
        require_datetime_text(self.due_at, "due_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ChargeRecord(ContractRecord):
    """A billable charge on an invoice."""

    charge_id: str = ""
    invoice_id: str = ""
    kind: ChargeKind = ChargeKind.SERVICE
    description: str = ""
    amount: float = 0.0
    scope_ref_id: str = ""
    scope_ref_type: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "charge_id", require_non_empty_text(self.charge_id, "charge_id"))
        object.__setattr__(self, "invoice_id", require_non_empty_text(self.invoice_id, "invoice_id"))
        if not isinstance(self.kind, ChargeKind):
            raise ValueError("kind must be a ChargeKind")
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CreditRecord(ContractRecord):
    """A credit applied to an account."""

    credit_id: str = ""
    account_id: str = ""
    breach_id: str = ""
    disposition: CreditDisposition = CreditDisposition.PENDING
    amount: float = 0.0
    reason: str = ""
    applied_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "credit_id", require_non_empty_text(self.credit_id, "credit_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "breach_id", require_non_empty_text(self.breach_id, "breach_id"))
        if not isinstance(self.disposition, CreditDisposition):
            raise ValueError("disposition must be a CreditDisposition")
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        require_datetime_text(self.applied_at, "applied_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PenaltyRecord(ContractRecord):
    """A penalty assessed on an account."""

    penalty_id: str = ""
    account_id: str = ""
    breach_id: str = ""
    amount: float = 0.0
    reason: str = ""
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "penalty_id", require_non_empty_text(self.penalty_id, "penalty_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "breach_id", require_non_empty_text(self.breach_id, "breach_id"))
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DisputeRecord(ContractRecord):
    """A dispute raised against an invoice or charge."""

    dispute_id: str = ""
    invoice_id: str = ""
    account_id: str = ""
    status: DisputeStatus = DisputeStatus.OPEN
    reason: str = ""
    amount: float = 0.0
    opened_at: str = ""
    resolved_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dispute_id", require_non_empty_text(self.dispute_id, "dispute_id"))
        object.__setattr__(self, "invoice_id", require_non_empty_text(self.invoice_id, "invoice_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        if not isinstance(self.status, DisputeStatus):
            raise ValueError("status must be a DisputeStatus")
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        require_datetime_text(self.opened_at, "opened_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RevenueSnapshot(ContractRecord):
    """Point-in-time revenue and billing state snapshot."""

    snapshot_id: str = ""
    total_accounts: int = 0
    total_invoices: int = 0
    total_charges: int = 0
    total_credits: int = 0
    total_penalties: int = 0
    total_disputes: int = 0
    total_recognized_revenue: float = 0.0
    total_pending_revenue: float = 0.0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_accounts", require_non_negative_int(self.total_accounts, "total_accounts"))
        object.__setattr__(self, "total_invoices", require_non_negative_int(self.total_invoices, "total_invoices"))
        object.__setattr__(self, "total_charges", require_non_negative_int(self.total_charges, "total_charges"))
        object.__setattr__(self, "total_credits", require_non_negative_int(self.total_credits, "total_credits"))
        object.__setattr__(self, "total_penalties", require_non_negative_int(self.total_penalties, "total_penalties"))
        object.__setattr__(self, "total_disputes", require_non_negative_int(self.total_disputes, "total_disputes"))
        object.__setattr__(self, "total_recognized_revenue", require_non_negative_float(self.total_recognized_revenue, "total_recognized_revenue"))
        object.__setattr__(self, "total_pending_revenue", require_non_negative_float(self.total_pending_revenue, "total_pending_revenue"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BillingDecision(ContractRecord):
    """A formal billing decision."""

    decision_id: str = ""
    account_id: str = ""
    description: str = ""
    decided_by: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "decided_by", require_non_empty_text(self.decided_by, "decided_by"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BillingViolation(ContractRecord):
    """A detected billing violation."""

    violation_id: str = ""
    account_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BillingClosureReport(ContractRecord):
    """Summary report for billing cycle closure."""

    report_id: str = ""
    account_id: str = ""
    tenant_id: str = ""
    total_invoices: int = 0
    total_charges: int = 0
    total_credits: int = 0
    total_penalties: int = 0
    total_disputes: int = 0
    total_revenue: float = 0.0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_invoices", require_non_negative_int(self.total_invoices, "total_invoices"))
        object.__setattr__(self, "total_charges", require_non_negative_int(self.total_charges, "total_charges"))
        object.__setattr__(self, "total_credits", require_non_negative_int(self.total_credits, "total_credits"))
        object.__setattr__(self, "total_penalties", require_non_negative_int(self.total_penalties, "total_penalties"))
        object.__setattr__(self, "total_disputes", require_non_negative_int(self.total_disputes, "total_disputes"))
        object.__setattr__(self, "total_revenue", require_non_negative_float(self.total_revenue, "total_revenue"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
