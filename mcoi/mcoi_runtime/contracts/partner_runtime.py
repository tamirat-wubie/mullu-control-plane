"""Purpose: partner / ecosystem / marketplace runtime contracts.
Governance scope: typed descriptors for partners, account links, ecosystem
    agreements, revenue shares, commitments, health snapshots, decisions,
    violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every partner references a tenant.
  - Revenue shares are non-negative.
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
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PartnerStatus(Enum):
    """Status of a partner."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    PROSPECT = "prospect"


class PartnerKind(Enum):
    """Kind of partner relationship."""
    RESELLER = "reseller"
    DISTRIBUTOR = "distributor"
    SERVICE_PARTNER = "service_partner"
    TECHNOLOGY_PARTNER = "technology_partner"
    REFERRAL = "referral"
    MANAGED_SERVICE = "managed_service"


class EcosystemRole(Enum):
    """Role within the ecosystem."""
    PROVIDER = "provider"
    CONSUMER = "consumer"
    INTERMEDIARY = "intermediary"
    INTEGRATOR = "integrator"


class RevenueShareStatus(Enum):
    """Status of a revenue share record."""
    PENDING = "pending"
    ACTIVE = "active"
    SETTLED = "settled"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


class PartnerHealthStatus(Enum):
    """Health status of a partner."""
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class PartnerDisposition(Enum):
    """Disposition for partner-related decisions."""
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PartnerRecord(ContractRecord):
    """A partner in the ecosystem."""

    partner_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: PartnerKind = PartnerKind.RESELLER
    status: PartnerStatus = PartnerStatus.ACTIVE
    tier: str = ""
    account_link_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "partner_id", require_non_empty_text(self.partner_id, "partner_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, PartnerKind):
            raise ValueError("kind must be a PartnerKind")
        if not isinstance(self.status, PartnerStatus):
            raise ValueError("status must be a PartnerStatus")
        object.__setattr__(self, "account_link_count", require_non_negative_int(self.account_link_count, "account_link_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PartnerAccountLink(ContractRecord):
    """A link between a partner and a customer account."""

    link_id: str = ""
    partner_id: str = ""
    account_id: str = ""
    tenant_id: str = ""
    role: EcosystemRole = EcosystemRole.INTERMEDIARY
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "link_id", require_non_empty_text(self.link_id, "link_id"))
        object.__setattr__(self, "partner_id", require_non_empty_text(self.partner_id, "partner_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.role, EcosystemRole):
            raise ValueError("role must be an EcosystemRole")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EcosystemAgreement(ContractRecord):
    """An agreement governing ecosystem participation."""

    agreement_id: str = ""
    partner_id: str = ""
    tenant_id: str = ""
    title: str = ""
    contract_ref: str = ""
    revenue_share_pct: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "agreement_id", require_non_empty_text(self.agreement_id, "agreement_id"))
        object.__setattr__(self, "partner_id", require_non_empty_text(self.partner_id, "partner_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "revenue_share_pct", require_unit_float(self.revenue_share_pct, "revenue_share_pct"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RevenueShareRecord(ContractRecord):
    """A revenue share record for a partner."""

    share_id: str = ""
    partner_id: str = ""
    agreement_id: str = ""
    tenant_id: str = ""
    gross_amount: float = 0.0
    share_amount: float = 0.0
    share_pct: float = 0.0
    status: RevenueShareStatus = RevenueShareStatus.PENDING
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "share_id", require_non_empty_text(self.share_id, "share_id"))
        object.__setattr__(self, "partner_id", require_non_empty_text(self.partner_id, "partner_id"))
        object.__setattr__(self, "agreement_id", require_non_empty_text(self.agreement_id, "agreement_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "gross_amount", require_non_negative_float(self.gross_amount, "gross_amount"))
        object.__setattr__(self, "share_amount", require_non_negative_float(self.share_amount, "share_amount"))
        object.__setattr__(self, "share_pct", require_unit_float(self.share_pct, "share_pct"))
        if not isinstance(self.status, RevenueShareStatus):
            raise ValueError("status must be a RevenueShareStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PartnerCommitment(ContractRecord):
    """A commitment made by or to a partner."""

    commitment_id: str = ""
    partner_id: str = ""
    tenant_id: str = ""
    description: str = ""
    target_value: float = 0.0
    actual_value: float = 0.0
    met: bool = False
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "commitment_id", require_non_empty_text(self.commitment_id, "commitment_id"))
        object.__setattr__(self, "partner_id", require_non_empty_text(self.partner_id, "partner_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "target_value", require_non_negative_float(self.target_value, "target_value"))
        object.__setattr__(self, "actual_value", require_non_negative_float(self.actual_value, "actual_value"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PartnerHealthSnapshot(ContractRecord):
    """Point-in-time health snapshot for a partner."""

    snapshot_id: str = ""
    partner_id: str = ""
    tenant_id: str = ""
    health_status: PartnerHealthStatus = PartnerHealthStatus.HEALTHY
    health_score: float = 1.0
    sla_breaches: int = 0
    open_cases: int = 0
    billing_issues: int = 0
    commitment_failures: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "partner_id", require_non_empty_text(self.partner_id, "partner_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.health_status, PartnerHealthStatus):
            raise ValueError("health_status must be a PartnerHealthStatus")
        object.__setattr__(self, "health_score", require_unit_float(self.health_score, "health_score"))
        object.__setattr__(self, "sla_breaches", require_non_negative_int(self.sla_breaches, "sla_breaches"))
        object.__setattr__(self, "open_cases", require_non_negative_int(self.open_cases, "open_cases"))
        object.__setattr__(self, "billing_issues", require_non_negative_int(self.billing_issues, "billing_issues"))
        object.__setattr__(self, "commitment_failures", require_non_negative_int(self.commitment_failures, "commitment_failures"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PartnerDecision(ContractRecord):
    """A decision related to partner operations."""

    decision_id: str = ""
    tenant_id: str = ""
    partner_id: str = ""
    disposition: PartnerDisposition = PartnerDisposition.APPROVED
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "partner_id", require_non_empty_text(self.partner_id, "partner_id"))
        if not isinstance(self.disposition, PartnerDisposition):
            raise ValueError("disposition must be a PartnerDisposition")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PartnerViolation(ContractRecord):
    """A violation detected in partner operations."""

    violation_id: str = ""
    tenant_id: str = ""
    partner_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "partner_id", require_non_empty_text(self.partner_id, "partner_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PartnerSnapshot(ContractRecord):
    """Point-in-time partner runtime state snapshot."""

    snapshot_id: str = ""
    total_partners: int = 0
    total_links: int = 0
    total_agreements: int = 0
    total_revenue_shares: int = 0
    total_commitments: int = 0
    total_health_snapshots: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_partners", require_non_negative_int(self.total_partners, "total_partners"))
        object.__setattr__(self, "total_links", require_non_negative_int(self.total_links, "total_links"))
        object.__setattr__(self, "total_agreements", require_non_negative_int(self.total_agreements, "total_agreements"))
        object.__setattr__(self, "total_revenue_shares", require_non_negative_int(self.total_revenue_shares, "total_revenue_shares"))
        object.__setattr__(self, "total_commitments", require_non_negative_int(self.total_commitments, "total_commitments"))
        object.__setattr__(self, "total_health_snapshots", require_non_negative_int(self.total_health_snapshots, "total_health_snapshots"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PartnerClosureReport(ContractRecord):
    """Summary report for partner runtime lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_partners: int = 0
    total_links: int = 0
    total_agreements: int = 0
    total_revenue_shares: int = 0
    total_commitments: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_partners", require_non_negative_int(self.total_partners, "total_partners"))
        object.__setattr__(self, "total_links", require_non_negative_int(self.total_links, "total_links"))
        object.__setattr__(self, "total_agreements", require_non_negative_int(self.total_agreements, "total_agreements"))
        object.__setattr__(self, "total_revenue_shares", require_non_negative_int(self.total_revenue_shares, "total_revenue_shares"))
        object.__setattr__(self, "total_commitments", require_non_negative_int(self.total_commitments, "total_commitments"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
