"""Purpose: contract / SLA / commitment governance runtime contracts.
Governance scope: typed descriptors for contracts, clauses, commitments,
    SLA windows, breaches, remedies, renewal windows, assessments,
    snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every commitment has explicit kind and status.
  - Breaches require explicit severity.
  - Renewal windows enforce deadlines.
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
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ContractStatus(Enum):
    """Status of a governance contract."""
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    RENEWED = "renewed"


class CommitmentKind(Enum):
    """Kind of contractual commitment."""
    SLA = "sla"
    OLA = "ola"
    AVAILABILITY = "availability"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    COMPLIANCE = "compliance"


class SLAStatus(Enum):
    """Status of an SLA window."""
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    WAIVED = "waived"
    CLOSED = "closed"


class BreachSeverity(Enum):
    """Severity of a contract breach."""
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class RenewalStatus(Enum):
    """Status of a renewal window."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    DECLINED = "declined"


class RemedyDisposition(Enum):
    """Disposition of a remedy."""
    PENDING = "pending"
    CREDIT_ISSUED = "credit_issued"
    PENALTY_APPLIED = "penalty_applied"
    WAIVED = "waived"
    ESCALATED = "escalated"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GovernanceContractRecord(ContractRecord):
    """A governance contract with a counterparty."""

    contract_id: str = ""
    tenant_id: str = ""
    counterparty: str = ""
    status: ContractStatus = ContractStatus.DRAFT
    title: str = ""
    description: str = ""
    effective_at: str = ""
    expires_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", require_non_empty_text(self.contract_id, "contract_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "counterparty", require_non_empty_text(self.counterparty, "counterparty"))
        if not isinstance(self.status, ContractStatus):
            raise ValueError("status must be a ContractStatus")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        require_datetime_text(self.effective_at, "effective_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContractClause(ContractRecord):
    """A clause within a governance contract."""

    clause_id: str = ""
    contract_id: str = ""
    title: str = ""
    description: str = ""
    commitment_kind: CommitmentKind = CommitmentKind.SLA
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "clause_id", require_non_empty_text(self.clause_id, "clause_id"))
        object.__setattr__(self, "contract_id", require_non_empty_text(self.contract_id, "contract_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.commitment_kind, CommitmentKind):
            raise ValueError("commitment_kind must be a CommitmentKind")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CommitmentRecord(ContractRecord):
    """A specific contractual commitment (SLA, OLA, etc.)."""

    commitment_id: str = ""
    contract_id: str = ""
    clause_id: str = ""
    tenant_id: str = ""
    kind: CommitmentKind = CommitmentKind.SLA
    target_value: str = ""
    scope_ref_id: str = ""
    scope_ref_type: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "commitment_id", require_non_empty_text(self.commitment_id, "commitment_id"))
        object.__setattr__(self, "contract_id", require_non_empty_text(self.contract_id, "contract_id"))
        object.__setattr__(self, "clause_id", require_non_empty_text(self.clause_id, "clause_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, CommitmentKind):
            raise ValueError("kind must be a CommitmentKind")
        object.__setattr__(self, "target_value", require_non_empty_text(self.target_value, "target_value"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SLAWindow(ContractRecord):
    """An SLA measurement window."""

    window_id: str = ""
    commitment_id: str = ""
    status: SLAStatus = SLAStatus.HEALTHY
    opens_at: str = ""
    closes_at: str = ""
    actual_value: str = ""
    compliance: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", require_non_empty_text(self.window_id, "window_id"))
        object.__setattr__(self, "commitment_id", require_non_empty_text(self.commitment_id, "commitment_id"))
        if not isinstance(self.status, SLAStatus):
            raise ValueError("status must be an SLAStatus")
        require_datetime_text(self.opens_at, "opens_at")
        require_datetime_text(self.closes_at, "closes_at")
        object.__setattr__(self, "compliance", require_unit_float(self.compliance, "compliance"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BreachRecord(ContractRecord):
    """A recorded contract breach."""

    breach_id: str = ""
    commitment_id: str = ""
    contract_id: str = ""
    tenant_id: str = ""
    severity: BreachSeverity = BreachSeverity.MINOR
    description: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "breach_id", require_non_empty_text(self.breach_id, "breach_id"))
        object.__setattr__(self, "commitment_id", require_non_empty_text(self.commitment_id, "commitment_id"))
        object.__setattr__(self, "contract_id", require_non_empty_text(self.contract_id, "contract_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.severity, BreachSeverity):
            raise ValueError("severity must be a BreachSeverity")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RemedyRecord(ContractRecord):
    """A remedy applied for a contract breach."""

    remedy_id: str = ""
    breach_id: str = ""
    tenant_id: str = ""
    disposition: RemedyDisposition = RemedyDisposition.PENDING
    amount: str = ""
    description: str = ""
    applied_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "remedy_id", require_non_empty_text(self.remedy_id, "remedy_id"))
        object.__setattr__(self, "breach_id", require_non_empty_text(self.breach_id, "breach_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, RemedyDisposition):
            raise ValueError("disposition must be a RemedyDisposition")
        require_datetime_text(self.applied_at, "applied_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RenewalWindow(ContractRecord):
    """A scheduled contract renewal window."""

    window_id: str = ""
    contract_id: str = ""
    status: RenewalStatus = RenewalStatus.SCHEDULED
    opens_at: str = ""
    closes_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", require_non_empty_text(self.window_id, "window_id"))
        object.__setattr__(self, "contract_id", require_non_empty_text(self.contract_id, "contract_id"))
        if not isinstance(self.status, RenewalStatus):
            raise ValueError("status must be a RenewalStatus")
        require_datetime_text(self.opens_at, "opens_at")
        require_datetime_text(self.closes_at, "closes_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContractAssessment(ContractRecord):
    """An assessment of contract compliance."""

    assessment_id: str = ""
    contract_id: str = ""
    tenant_id: str = ""
    total_commitments: int = 0
    healthy_commitments: int = 0
    at_risk_commitments: int = 0
    breached_commitments: int = 0
    overall_compliance: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "contract_id", require_non_empty_text(self.contract_id, "contract_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_commitments", require_non_negative_int(self.total_commitments, "total_commitments"))
        object.__setattr__(self, "healthy_commitments", require_non_negative_int(self.healthy_commitments, "healthy_commitments"))
        object.__setattr__(self, "at_risk_commitments", require_non_negative_int(self.at_risk_commitments, "at_risk_commitments"))
        object.__setattr__(self, "breached_commitments", require_non_negative_int(self.breached_commitments, "breached_commitments"))
        object.__setattr__(self, "overall_compliance", require_unit_float(self.overall_compliance, "overall_compliance"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContractSnapshot(ContractRecord):
    """Point-in-time contract governance state snapshot."""

    snapshot_id: str = ""
    total_contracts: int = 0
    active_contracts: int = 0
    total_commitments: int = 0
    total_sla_windows: int = 0
    total_breaches: int = 0
    total_remedies: int = 0
    total_renewals: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_contracts", require_non_negative_int(self.total_contracts, "total_contracts"))
        object.__setattr__(self, "active_contracts", require_non_negative_int(self.active_contracts, "active_contracts"))
        object.__setattr__(self, "total_commitments", require_non_negative_int(self.total_commitments, "total_commitments"))
        object.__setattr__(self, "total_sla_windows", require_non_negative_int(self.total_sla_windows, "total_sla_windows"))
        object.__setattr__(self, "total_breaches", require_non_negative_int(self.total_breaches, "total_breaches"))
        object.__setattr__(self, "total_remedies", require_non_negative_int(self.total_remedies, "total_remedies"))
        object.__setattr__(self, "total_renewals", require_non_negative_int(self.total_renewals, "total_renewals"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContractClosureReport(ContractRecord):
    """Summary report for contract governance closure."""

    report_id: str = ""
    contract_id: str = ""
    tenant_id: str = ""
    final_status: ContractStatus = ContractStatus.TERMINATED
    total_commitments: int = 0
    total_breaches: int = 0
    total_remedies: int = 0
    total_renewals: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "contract_id", require_non_empty_text(self.contract_id, "contract_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.final_status, ContractStatus):
            raise ValueError("final_status must be a ContractStatus")
        object.__setattr__(self, "total_commitments", require_non_negative_int(self.total_commitments, "total_commitments"))
        object.__setattr__(self, "total_breaches", require_non_negative_int(self.total_breaches, "total_breaches"))
        object.__setattr__(self, "total_remedies", require_non_negative_int(self.total_remedies, "total_remedies"))
        object.__setattr__(self, "total_renewals", require_non_negative_int(self.total_renewals, "total_renewals"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
