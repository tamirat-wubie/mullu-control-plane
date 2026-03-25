"""Purpose: service catalog / request fulfillment runtime contracts.
Governance scope: typed descriptors for catalog items, service requests,
    request assignments, entitlement rules, fulfillment tasks, fulfillment
    decisions, request snapshots, request violations, service closure reports,
    and catalog assessments.
Dependencies: _base contract utilities.
Invariants:
  - Every request references a valid catalog item.
  - Entitlement must be checked before fulfillment.
  - Fulfilled requests cannot be re-opened.
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


class ServiceStatus(Enum):
    """Status of a service catalog item."""
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class RequestStatus(Enum):
    """Status of a service request."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ENTITLED = "entitled"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    IN_FULFILLMENT = "in_fulfillment"
    FULFILLED = "fulfilled"
    DENIED = "denied"
    CANCELLED = "cancelled"


class RequestPriority(Enum):
    """Priority of a service request."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FulfillmentStatus(Enum):
    """Status of a fulfillment task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EntitlementDisposition(Enum):
    """Outcome of an entitlement check."""
    GRANTED = "granted"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"
    EXPIRED = "expired"


class CatalogItemKind(Enum):
    """Kind of service catalog item."""
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    ACCESS = "access"
    SUPPORT = "support"
    PROCUREMENT = "procurement"
    DATA = "data"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ServiceCatalogItem(ContractRecord):
    """A registered service in the catalog."""

    item_id: str = ""
    name: str = ""
    tenant_id: str = ""
    kind: CatalogItemKind = CatalogItemKind.INFRASTRUCTURE
    status: ServiceStatus = ServiceStatus.ACTIVE
    owner_ref: str = ""
    sla_ref: str = ""
    approval_required: bool = False
    estimated_cost: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", require_non_empty_text(self.item_id, "item_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, CatalogItemKind):
            raise ValueError("kind must be a CatalogItemKind")
        if not isinstance(self.status, ServiceStatus):
            raise ValueError("status must be a ServiceStatus")
        object.__setattr__(self, "estimated_cost", require_non_negative_float(self.estimated_cost, "estimated_cost"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ServiceRequest(ContractRecord):
    """A service request submitted by a user or system."""

    request_id: str = ""
    item_id: str = ""
    tenant_id: str = ""
    requester_ref: str = ""
    status: RequestStatus = RequestStatus.DRAFT
    priority: RequestPriority = RequestPriority.MEDIUM
    description: str = ""
    estimated_cost: float = 0.0
    submitted_at: str = ""
    due_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "item_id", require_non_empty_text(self.item_id, "item_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "requester_ref", require_non_empty_text(self.requester_ref, "requester_ref"))
        if not isinstance(self.status, RequestStatus):
            raise ValueError("status must be a RequestStatus")
        if not isinstance(self.priority, RequestPriority):
            raise ValueError("priority must be a RequestPriority")
        object.__setattr__(self, "estimated_cost", require_non_negative_float(self.estimated_cost, "estimated_cost"))
        require_datetime_text(self.submitted_at, "submitted_at")
        if self.due_at:
            require_datetime_text(self.due_at, "due_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RequestAssignment(ContractRecord):
    """Assignment of a request to an assignee."""

    assignment_id: str = ""
    request_id: str = ""
    assignee_ref: str = ""
    assigned_by: str = ""
    assigned_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignment_id", require_non_empty_text(self.assignment_id, "assignment_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "assignee_ref", require_non_empty_text(self.assignee_ref, "assignee_ref"))
        object.__setattr__(self, "assigned_by", require_non_empty_text(self.assigned_by, "assigned_by"))
        require_datetime_text(self.assigned_at, "assigned_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EntitlementRule(ContractRecord):
    """An entitlement rule that gates service access."""

    rule_id: str = ""
    item_id: str = ""
    tenant_id: str = ""
    disposition: EntitlementDisposition = EntitlementDisposition.GRANTED
    scope_ref: str = ""
    reason: str = ""
    evaluated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "item_id", require_non_empty_text(self.item_id, "item_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, EntitlementDisposition):
            raise ValueError("disposition must be an EntitlementDisposition")
        require_datetime_text(self.evaluated_at, "evaluated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FulfillmentTask(ContractRecord):
    """A task created to fulfill a service request."""

    task_id: str = ""
    request_id: str = ""
    assignee_ref: str = ""
    status: FulfillmentStatus = FulfillmentStatus.PENDING
    description: str = ""
    dependency_ref: str = ""
    created_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", require_non_empty_text(self.task_id, "task_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "assignee_ref", require_non_empty_text(self.assignee_ref, "assignee_ref"))
        if not isinstance(self.status, FulfillmentStatus):
            raise ValueError("status must be a FulfillmentStatus")
        require_datetime_text(self.created_at, "created_at")
        if self.completed_at:
            require_datetime_text(self.completed_at, "completed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FulfillmentDecision(ContractRecord):
    """A decision made during request fulfillment."""

    decision_id: str = ""
    request_id: str = ""
    disposition: str = ""
    decided_by: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "decided_by", require_non_empty_text(self.decided_by, "decided_by"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RequestSnapshot(ContractRecord):
    """Point-in-time request state snapshot."""

    snapshot_id: str = ""
    total_catalog_items: int = 0
    total_requests: int = 0
    total_submitted: int = 0
    total_in_fulfillment: int = 0
    total_fulfilled: int = 0
    total_denied: int = 0
    total_tasks: int = 0
    total_violations: int = 0
    total_estimated_cost: float = 0.0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_catalog_items", require_non_negative_int(self.total_catalog_items, "total_catalog_items"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_submitted", require_non_negative_int(self.total_submitted, "total_submitted"))
        object.__setattr__(self, "total_in_fulfillment", require_non_negative_int(self.total_in_fulfillment, "total_in_fulfillment"))
        object.__setattr__(self, "total_fulfilled", require_non_negative_int(self.total_fulfilled, "total_fulfilled"))
        object.__setattr__(self, "total_denied", require_non_negative_int(self.total_denied, "total_denied"))
        object.__setattr__(self, "total_tasks", require_non_negative_int(self.total_tasks, "total_tasks"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_estimated_cost", require_non_negative_float(self.total_estimated_cost, "total_estimated_cost"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RequestViolation(ContractRecord):
    """A detected request/fulfillment violation."""

    violation_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ServiceClosureReport(ContractRecord):
    """Summary report for service request lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_requests: int = 0
    total_fulfilled: int = 0
    total_denied: int = 0
    total_cancelled: int = 0
    total_tasks: int = 0
    total_violations: int = 0
    total_estimated_cost: float = 0.0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_fulfilled", require_non_negative_int(self.total_fulfilled, "total_fulfilled"))
        object.__setattr__(self, "total_denied", require_non_negative_int(self.total_denied, "total_denied"))
        object.__setattr__(self, "total_cancelled", require_non_negative_int(self.total_cancelled, "total_cancelled"))
        object.__setattr__(self, "total_tasks", require_non_negative_int(self.total_tasks, "total_tasks"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_estimated_cost", require_non_negative_float(self.total_estimated_cost, "total_estimated_cost"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CatalogAssessment(ContractRecord):
    """A health/quality assessment of a catalog item."""

    assessment_id: str = ""
    item_id: str = ""
    fulfillment_rate: float = 0.0
    satisfaction_score: float = 0.0
    assessed_by: str = ""
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "item_id", require_non_empty_text(self.item_id, "item_id"))
        object.__setattr__(self, "fulfillment_rate", require_unit_float(self.fulfillment_rate, "fulfillment_rate"))
        object.__setattr__(self, "satisfaction_score", require_unit_float(self.satisfaction_score, "satisfaction_score"))
        object.__setattr__(self, "assessed_by", require_non_empty_text(self.assessed_by, "assessed_by"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
