"""Purpose: finance approval packet contracts for governed invoice review.
Governance scope: invoice case identity, policy decision, approval/effect
receipts, terminal packet proof, and deterministic serialization.
Dependencies: shared contract base helpers.
Invariants:
  - Currency amounts use integer minor units, never floats.
  - Packet state and policy verdicts are explicit enums.
  - Approvals and effects are first-class evidence references.
  - Proof artifacts bind final state, policy, evidence, closure, and audit root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
    require_non_negative_int,
)


class FinancePacketState(StrEnum):
    RECEIVED = "received"
    EXTRACTED = "extracted"
    EVIDENCE_CHECKED = "evidence_checked"
    BUDGET_CHECKED = "budget_checked"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    EFFECT_DISPATCHED = "effect_dispatched"
    RECONCILED = "reconciled"
    CLOSED_PREPARED = "closed_prepared"
    CLOSED_SENT = "closed_sent"
    CLOSED_REJECTED = "closed_rejected"
    CLOSED_DUPLICATE = "closed_duplicate"
    CLOSED_ACCEPTED_RISK = "closed_accepted_risk"
    REQUIRES_REVIEW = "requires_review"
    FAILED_WITH_RECOVERY = "failed_with_recovery"


class FinancePacketRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FinancePolicyVerdict(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_REVIEW = "require_review"
    BLOCK = "block"


class VendorEvidenceStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"


class ApprovalStatus(StrEnum):
    ABSENT = "absent"
    GRANTED = "granted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class EffectReceiptType(StrEnum):
    EMAIL_HANDOFF_CREATED = "email_handoff_created"
    EMAIL_SENT_WITH_APPROVAL = "email_sent_with_approval"
    PAYMENT_HANDOFF_CREATED = "payment_handoff_created"


@dataclass(frozen=True, slots=True)
class InvoiceMoney(ContractRecord):
    """Decimal-safe invoice amount."""

    currency: str
    minor_units: int

    def __post_init__(self) -> None:
        currency = require_non_empty_text(self.currency, "currency").upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter ISO 4217 code")
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "minor_units", require_non_negative_int(self.minor_units, "minor_units"))


@dataclass(frozen=True, slots=True)
class InvoiceCase(ContractRecord):
    """Governed finance approval packet case."""

    case_id: str
    tenant_id: str
    actor_id: str
    vendor_id: str
    invoice_id: str
    amount: InvoiceMoney
    source_evidence_ref: str
    state: FinancePacketState
    risk: FinancePacketRisk
    created_at: str
    updated_at: str
    policy_decision_refs: tuple[str, ...] = ()
    approval_refs: tuple[str, ...] = ()
    effect_refs: tuple[str, ...] = ()
    closure_certificate_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "case_id",
            "tenant_id",
            "actor_id",
            "vendor_id",
            "invoice_id",
            "source_evidence_ref",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.amount, InvoiceMoney):
            raise ValueError("amount must be an InvoiceMoney instance")
        if not isinstance(self.state, FinancePacketState):
            raise ValueError("state must be a FinancePacketState value")
        if not isinstance(self.risk, FinancePacketRisk):
            raise ValueError("risk must be a FinancePacketRisk value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        object.__setattr__(self, "policy_decision_refs", _freeze_text_tuple(self.policy_decision_refs, "policy_decision_refs"))
        object.__setattr__(self, "approval_refs", _freeze_text_tuple(self.approval_refs, "approval_refs"))
        object.__setattr__(self, "effect_refs", _freeze_text_tuple(self.effect_refs, "effect_refs"))
        if self.closure_certificate_id is not None:
            object.__setattr__(
                self,
                "closure_certificate_id",
                require_non_empty_text(self.closure_certificate_id, "closure_certificate_id"),
            )
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class FinancePolicyDecision(ContractRecord):
    """Deterministic policy evaluation for one invoice case."""

    decision_id: str
    case_id: str
    tenant_id: str
    verdict: FinancePolicyVerdict
    reasons: tuple[str, ...]
    required_controls: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "case_id", "tenant_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.verdict, FinancePolicyVerdict):
            raise ValueError("verdict must be a FinancePolicyVerdict value")
        object.__setattr__(self, "reasons", require_non_empty_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "required_controls", _freeze_text_tuple(self.required_controls, "required_controls"))
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class FinanceApprovalReceipt(ContractRecord):
    """Human approval receipt bound to a finance packet."""

    approval_id: str
    case_id: str
    tenant_id: str
    approver_id: str
    approver_role: str
    status: ApprovalStatus
    decided_at: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("approval_id", "case_id", "tenant_id", "approver_id", "approver_role"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, ApprovalStatus):
            raise ValueError("status must be an ApprovalStatus value")
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(self.evidence_refs, "evidence_refs"))


@dataclass(frozen=True, slots=True)
class FinanceEffectReceipt(ContractRecord):
    """Effect receipt for a bounded finance packet action."""

    effect_id: str
    case_id: str
    tenant_id: str
    effect_type: EffectReceiptType
    capability_id: str
    dispatched_at: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("effect_id", "case_id", "tenant_id", "capability_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.effect_type, EffectReceiptType):
            raise ValueError("effect_type must be an EffectReceiptType value")
        object.__setattr__(self, "dispatched_at", require_datetime_text(self.dispatched_at, "dispatched_at"))
        object.__setattr__(self, "evidence_refs", require_non_empty_tuple(self.evidence_refs, "evidence_refs"))


@dataclass(frozen=True, slots=True)
class FinanceApprovalPacketProof(ContractRecord):
    """Exportable proof for a completed or review-bound finance packet."""

    proof_id: str
    case_id: str
    tenant_id: str
    final_state: FinancePacketState
    policy_decisions: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    audit_root_hash: str
    generated_at: str
    approval_refs: tuple[str, ...] = ()
    effect_refs: tuple[str, ...] = ()
    closure_certificate_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("proof_id", "case_id", "tenant_id", "audit_root_hash"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.final_state, FinancePacketState):
            raise ValueError("final_state must be a FinancePacketState value")
        object.__setattr__(self, "policy_decisions", require_non_empty_tuple(self.policy_decisions, "policy_decisions"))
        object.__setattr__(self, "evidence_refs", require_non_empty_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "approval_refs", _freeze_text_tuple(self.approval_refs, "approval_refs"))
        object.__setattr__(self, "effect_refs", _freeze_text_tuple(self.effect_refs, "effect_refs"))
        if self.closure_certificate_id is not None:
            object.__setattr__(
                self,
                "closure_certificate_id",
                require_non_empty_text(self.closure_certificate_id, "closure_certificate_id"),
            )
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


def _freeze_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    frozen = freeze_value(list(values))
    if not isinstance(frozen, tuple):
        raise ValueError(f"{field_name} must be a tuple")
    for index, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{index}]")
    return frozen
