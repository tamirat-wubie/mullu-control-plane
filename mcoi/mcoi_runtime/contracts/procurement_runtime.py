"""Purpose: vendor / procurement / third-party runtime contracts.
Governance scope: typed descriptors for vendors, procurement requests,
    purchase orders, vendor assessments, vendor commitments, procurement
    decisions, renewal windows, vendor violations, procurement snapshots,
    and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every purchase order has explicit vendor and amount.
  - Procurement requests require approval before PO issuance.
  - Vendor risk blocks renewal.
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


class VendorStatus(Enum):
    """Status of a vendor."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"
    TERMINATED = "terminated"
    UNDER_REVIEW = "under_review"


class ProcurementRequestStatus(Enum):
    """Status of a procurement request."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"
    FULFILLED = "fulfilled"


class PurchaseOrderStatus(Enum):
    """Status of a purchase order."""
    DRAFT = "draft"
    ISSUED = "issued"
    ACKNOWLEDGED = "acknowledged"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class VendorRiskLevel(Enum):
    """Risk level of a vendor."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RenewalDisposition(Enum):
    """Disposition of a vendor renewal."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    DEFERRED = "deferred"
    AUTO_RENEWED = "auto_renewed"


class ProcurementDecisionStatus(Enum):
    """Status of a procurement decision."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VendorRecord(ContractRecord):
    """A registered vendor / third-party supplier."""

    vendor_id: str = ""
    name: str = ""
    tenant_id: str = ""
    status: VendorStatus = VendorStatus.ACTIVE
    risk_level: VendorRiskLevel = VendorRiskLevel.LOW
    category: str = ""
    registered_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", require_non_empty_text(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.status, VendorStatus):
            raise ValueError("status must be a VendorStatus")
        if not isinstance(self.risk_level, VendorRiskLevel):
            raise ValueError("risk_level must be a VendorRiskLevel")
        require_datetime_text(self.registered_at, "registered_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcurementRequest(ContractRecord):
    """A request to procure goods or services."""

    request_id: str = ""
    vendor_id: str = ""
    tenant_id: str = ""
    status: ProcurementRequestStatus = ProcurementRequestStatus.DRAFT
    description: str = ""
    estimated_amount: float = 0.0
    currency: str = ""
    requested_by: str = ""
    requested_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "vendor_id", require_non_empty_text(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.status, ProcurementRequestStatus):
            raise ValueError("status must be a ProcurementRequestStatus")
        object.__setattr__(self, "estimated_amount", require_non_negative_float(self.estimated_amount, "estimated_amount"))
        object.__setattr__(self, "currency", require_non_empty_text(self.currency, "currency"))
        object.__setattr__(self, "requested_by", require_non_empty_text(self.requested_by, "requested_by"))
        require_datetime_text(self.requested_at, "requested_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PurchaseOrder(ContractRecord):
    """A purchase order issued to a vendor."""

    po_id: str = ""
    request_id: str = ""
    vendor_id: str = ""
    tenant_id: str = ""
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT
    amount: float = 0.0
    currency: str = ""
    issued_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "po_id", require_non_empty_text(self.po_id, "po_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "vendor_id", require_non_empty_text(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.status, PurchaseOrderStatus):
            raise ValueError("status must be a PurchaseOrderStatus")
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        object.__setattr__(self, "currency", require_non_empty_text(self.currency, "currency"))
        require_datetime_text(self.issued_at, "issued_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VendorAssessment(ContractRecord):
    """A risk/performance assessment of a vendor."""

    assessment_id: str = ""
    vendor_id: str = ""
    risk_level: VendorRiskLevel = VendorRiskLevel.LOW
    performance_score: float = 0.0
    fault_count: int = 0
    assessed_by: str = ""
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "vendor_id", require_non_empty_text(self.vendor_id, "vendor_id"))
        if not isinstance(self.risk_level, VendorRiskLevel):
            raise ValueError("risk_level must be a VendorRiskLevel")
        object.__setattr__(self, "performance_score", require_unit_float(self.performance_score, "performance_score"))
        object.__setattr__(self, "fault_count", require_non_negative_int(self.fault_count, "fault_count"))
        object.__setattr__(self, "assessed_by", require_non_empty_text(self.assessed_by, "assessed_by"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VendorCommitment(ContractRecord):
    """A commitment binding a vendor to a contract or SLA."""

    commitment_id: str = ""
    vendor_id: str = ""
    contract_ref: str = ""
    description: str = ""
    target_value: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "commitment_id", require_non_empty_text(self.commitment_id, "commitment_id"))
        object.__setattr__(self, "vendor_id", require_non_empty_text(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "contract_ref", require_non_empty_text(self.contract_ref, "contract_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcurementDecision(ContractRecord):
    """A formal procurement approval/denial decision."""

    decision_id: str = ""
    request_id: str = ""
    status: ProcurementDecisionStatus = ProcurementDecisionStatus.PENDING
    decided_by: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        if not isinstance(self.status, ProcurementDecisionStatus):
            raise ValueError("status must be a ProcurementDecisionStatus")
        object.__setattr__(self, "decided_by", require_non_empty_text(self.decided_by, "decided_by"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcurementRenewalWindow(ContractRecord):
    """A renewal window for a vendor contract."""

    renewal_id: str = ""
    vendor_id: str = ""
    contract_ref: str = ""
    disposition: RenewalDisposition = RenewalDisposition.PENDING
    opens_at: str = ""
    closes_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "renewal_id", require_non_empty_text(self.renewal_id, "renewal_id"))
        object.__setattr__(self, "vendor_id", require_non_empty_text(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "contract_ref", require_non_empty_text(self.contract_ref, "contract_ref"))
        if not isinstance(self.disposition, RenewalDisposition):
            raise ValueError("disposition must be a RenewalDisposition")
        require_datetime_text(self.opens_at, "opens_at")
        require_datetime_text(self.closes_at, "closes_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VendorViolation(ContractRecord):
    """A detected vendor/procurement violation."""

    violation_id: str = ""
    vendor_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "vendor_id", require_non_empty_text(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcurementSnapshot(ContractRecord):
    """Point-in-time procurement state snapshot."""

    snapshot_id: str = ""
    total_vendors: int = 0
    total_requests: int = 0
    total_purchase_orders: int = 0
    total_assessments: int = 0
    total_commitments: int = 0
    total_renewals: int = 0
    total_violations: int = 0
    total_procurement_value: float = 0.0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_vendors", require_non_negative_int(self.total_vendors, "total_vendors"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_purchase_orders", require_non_negative_int(self.total_purchase_orders, "total_purchase_orders"))
        object.__setattr__(self, "total_assessments", require_non_negative_int(self.total_assessments, "total_assessments"))
        object.__setattr__(self, "total_commitments", require_non_negative_int(self.total_commitments, "total_commitments"))
        object.__setattr__(self, "total_renewals", require_non_negative_int(self.total_renewals, "total_renewals"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_procurement_value", require_non_negative_float(self.total_procurement_value, "total_procurement_value"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcurementClosureReport(ContractRecord):
    """Summary report for procurement cycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_vendors: int = 0
    total_requests: int = 0
    total_purchase_orders: int = 0
    total_fulfilled: int = 0
    total_cancelled: int = 0
    total_procurement_value: float = 0.0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_vendors", require_non_negative_int(self.total_vendors, "total_vendors"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_purchase_orders", require_non_negative_int(self.total_purchase_orders, "total_purchase_orders"))
        object.__setattr__(self, "total_fulfilled", require_non_negative_int(self.total_fulfilled, "total_fulfilled"))
        object.__setattr__(self, "total_cancelled", require_non_negative_int(self.total_cancelled, "total_cancelled"))
        object.__setattr__(self, "total_procurement_value", require_non_negative_float(self.total_procurement_value, "total_procurement_value"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
