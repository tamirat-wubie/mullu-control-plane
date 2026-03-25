"""Purpose: Blockchain / ledger / verifiable settlement runtime contracts.
Governance scope: typed descriptors for ledger accounts, transactions,
    settlement proofs, anchor records, wallets, decisions, snapshots,
    violations, assessments, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Ledger state is immutable and traceable.
  - Every record references a tenant.
  - All outputs are frozen.
  - Settlement proofs require cryptographic hashes.
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
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LedgerStatus(Enum):
    """Status of a ledger account."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    ARCHIVED = "archived"


class LedgerNetworkKind(Enum):
    """Kind of ledger network."""
    PRIVATE = "private"
    CONSORTIUM = "consortium"
    PUBLIC = "public"
    HYBRID = "hybrid"


class SettlementProofStatus(Enum):
    """Status of a settlement proof."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    DISPUTED = "disputed"


class AnchorDisposition(Enum):
    """Disposition of an anchor record."""
    ANCHORED = "anchored"
    PENDING = "pending"
    FAILED = "failed"
    REVOKED = "revoked"


class WalletStatus(Enum):
    """Status of a wallet."""
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"
    COMPROMISED = "compromised"


class LedgerViolationKind(Enum):
    """Kind of ledger violation."""
    PROOF_FAILED = "proof_failed"
    ANCHOR_EXPIRED = "anchor_expired"
    WALLET_COMPROMISED = "wallet_compromised"
    SETTLEMENT_DISPUTED = "settlement_disputed"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LedgerAccount(ContractRecord):
    """A ledger account."""

    account_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: LedgerStatus = LedgerStatus.ACTIVE
    network: LedgerNetworkKind = LedgerNetworkKind.PRIVATE
    balance: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, LedgerStatus):
            raise ValueError("status must be a LedgerStatus")
        if not isinstance(self.network, LedgerNetworkKind):
            raise ValueError("network must be a LedgerNetworkKind")
        object.__setattr__(self, "balance", require_non_negative_float(self.balance, "balance"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LedgerTransaction(ContractRecord):
    """A ledger transaction between accounts."""

    transaction_id: str = ""
    tenant_id: str = ""
    from_account: str = ""
    to_account: str = ""
    amount: float = 0.0
    reference_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "transaction_id", require_non_empty_text(self.transaction_id, "transaction_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "from_account", require_non_empty_text(self.from_account, "from_account"))
        object.__setattr__(self, "to_account", require_non_empty_text(self.to_account, "to_account"))
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        object.__setattr__(self, "reference_ref", require_non_empty_text(self.reference_ref, "reference_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SettlementProof(ContractRecord):
    """A settlement proof with cryptographic hash."""

    proof_id: str = ""
    tenant_id: str = ""
    transaction_ref: str = ""
    status: SettlementProofStatus = SettlementProofStatus.PENDING
    proof_hash: str = ""
    verified_at: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "proof_id", require_non_empty_text(self.proof_id, "proof_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "transaction_ref", require_non_empty_text(self.transaction_ref, "transaction_ref"))
        if not isinstance(self.status, SettlementProofStatus):
            raise ValueError("status must be a SettlementProofStatus")
        object.__setattr__(self, "proof_hash", require_non_empty_text(self.proof_hash, "proof_hash"))
        if self.verified_at:
            require_datetime_text(self.verified_at, "verified_at")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AnchorRecord(ContractRecord):
    """An anchor record linking content to a chain transaction."""

    anchor_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    content_hash: str = ""
    disposition: AnchorDisposition = AnchorDisposition.PENDING
    anchor_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchor_id", require_non_empty_text(self.anchor_id, "anchor_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "content_hash", require_non_empty_text(self.content_hash, "content_hash"))
        if not isinstance(self.disposition, AnchorDisposition):
            raise ValueError("disposition must be an AnchorDisposition")
        object.__setattr__(self, "anchor_ref", require_non_empty_text(self.anchor_ref, "anchor_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WalletRecord(ContractRecord):
    """A wallet record."""

    wallet_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    status: WalletStatus = WalletStatus.ACTIVE
    public_key_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "wallet_id", require_non_empty_text(self.wallet_id, "wallet_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        if not isinstance(self.status, WalletStatus):
            raise ValueError("status must be a WalletStatus")
        object.__setattr__(self, "public_key_ref", require_non_empty_text(self.public_key_ref, "public_key_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LedgerDecision(ContractRecord):
    """A ledger decision record."""

    decision_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LedgerSnapshot(ContractRecord):
    """Point-in-time snapshot of ledger runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_accounts: int = 0
    total_transactions: int = 0
    total_proofs: int = 0
    total_anchors: int = 0
    total_wallets: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_accounts", require_non_negative_int(self.total_accounts, "total_accounts"))
        object.__setattr__(self, "total_transactions", require_non_negative_int(self.total_transactions, "total_transactions"))
        object.__setattr__(self, "total_proofs", require_non_negative_int(self.total_proofs, "total_proofs"))
        object.__setattr__(self, "total_anchors", require_non_negative_int(self.total_anchors, "total_anchors"))
        object.__setattr__(self, "total_wallets", require_non_negative_int(self.total_wallets, "total_wallets"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LedgerViolation(ContractRecord):
    """A ledger violation record."""

    violation_id: str = ""
    tenant_id: str = ""
    kind: LedgerViolationKind = LedgerViolationKind.PROOF_FAILED
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, LedgerViolationKind):
            raise ValueError("kind must be a LedgerViolationKind")
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LedgerAssessment(ContractRecord):
    """Assessment of ledger proof integrity."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_confirmed: int = 0
    total_failed: int = 0
    total_disputed: int = 0
    integrity_score: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_confirmed", require_non_negative_int(self.total_confirmed, "total_confirmed"))
        object.__setattr__(self, "total_failed", require_non_negative_int(self.total_failed, "total_failed"))
        object.__setattr__(self, "total_disputed", require_non_negative_int(self.total_disputed, "total_disputed"))
        object.__setattr__(self, "integrity_score", require_unit_float(self.integrity_score, "integrity_score"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LedgerClosureReport(ContractRecord):
    """Closure report for ledger runtime state."""

    report_id: str = ""
    tenant_id: str = ""
    total_accounts: int = 0
    total_transactions: int = 0
    total_proofs: int = 0
    total_anchors: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_accounts", require_non_negative_int(self.total_accounts, "total_accounts"))
        object.__setattr__(self, "total_transactions", require_non_negative_int(self.total_transactions, "total_transactions"))
        object.__setattr__(self, "total_proofs", require_non_negative_int(self.total_proofs, "total_proofs"))
        object.__setattr__(self, "total_anchors", require_non_negative_int(self.total_anchors, "total_anchors"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
