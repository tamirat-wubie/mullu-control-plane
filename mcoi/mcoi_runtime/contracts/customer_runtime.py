"""Purpose: product / customer / account runtime contracts.
Governance scope: typed descriptors for customers, accounts, products,
    subscriptions, entitlements, account health, decisions, violations,
    snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every customer/account/product references a tenant.
  - Entitlements bind accounts to services.
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
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CustomerStatus(Enum):
    """Status of a customer."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CHURNED = "churned"
    PROSPECT = "prospect"


class AccountStatus(Enum):
    """Status of an account."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    DELINQUENT = "delinquent"
    PENDING = "pending"


class ProductStatus(Enum):
    """Status of a product or service offering."""
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class EntitlementStatus(Enum):
    """Status of an entitlement."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class AccountHealthStatus(Enum):
    """Health status of a customer account."""
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class CustomerDisposition(Enum):
    """Disposition for customer-related decisions."""
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CustomerRecord(ContractRecord):
    """A customer in the platform."""

    customer_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: CustomerStatus = CustomerStatus.ACTIVE
    tier: str = ""
    account_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "customer_id", require_non_empty_text(self.customer_id, "customer_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, CustomerStatus):
            raise ValueError("status must be a CustomerStatus")
        object.__setattr__(self, "account_count", require_non_negative_int(self.account_count, "account_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AccountRecord(ContractRecord):
    """An account under a customer."""

    account_id: str = ""
    customer_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: AccountStatus = AccountStatus.ACTIVE
    contract_ref: str = ""
    entitlement_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "customer_id", require_non_empty_text(self.customer_id, "customer_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, AccountStatus):
            raise ValueError("status must be an AccountStatus")
        object.__setattr__(self, "entitlement_count", require_non_negative_int(self.entitlement_count, "entitlement_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProductRecord(ContractRecord):
    """A product or service offering."""

    product_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: ProductStatus = ProductStatus.ACTIVE
    category: str = ""
    base_price: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "product_id", require_non_empty_text(self.product_id, "product_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, ProductStatus):
            raise ValueError("status must be a ProductStatus")
        object.__setattr__(self, "base_price", require_non_negative_float(self.base_price, "base_price"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SubscriptionRecord(ContractRecord):
    """A subscription linking an account to a product."""

    subscription_id: str = ""
    account_id: str = ""
    product_id: str = ""
    tenant_id: str = ""
    status: AccountStatus = AccountStatus.ACTIVE
    quantity: int = 1
    start_at: str = ""
    end_at: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "subscription_id", require_non_empty_text(self.subscription_id, "subscription_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "product_id", require_non_empty_text(self.product_id, "product_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.status, AccountStatus):
            raise ValueError("status must be an AccountStatus")
        object.__setattr__(self, "quantity", require_positive_int(self.quantity, "quantity"))
        require_datetime_text(self.start_at, "start_at")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EntitlementRecord(ContractRecord):
    """An entitlement granting account access to a service or capability."""

    entitlement_id: str = ""
    account_id: str = ""
    tenant_id: str = ""
    service_ref: str = ""
    status: EntitlementStatus = EntitlementStatus.ACTIVE
    granted_at: str = ""
    expires_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entitlement_id", require_non_empty_text(self.entitlement_id, "entitlement_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "service_ref", require_non_empty_text(self.service_ref, "service_ref"))
        if not isinstance(self.status, EntitlementStatus):
            raise ValueError("status must be an EntitlementStatus")
        require_datetime_text(self.granted_at, "granted_at")
        require_datetime_text(self.created_at if hasattr(self, "created_at") else self.granted_at, "granted_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AccountHealthSnapshot(ContractRecord):
    """Point-in-time health snapshot for a customer account."""

    snapshot_id: str = ""
    account_id: str = ""
    tenant_id: str = ""
    health_status: AccountHealthStatus = AccountHealthStatus.HEALTHY
    health_score: float = 1.0
    sla_breaches: int = 0
    open_cases: int = 0
    billing_issues: int = 0
    entitlement_count: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "account_id", require_non_empty_text(self.account_id, "account_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.health_status, AccountHealthStatus):
            raise ValueError("health_status must be an AccountHealthStatus")
        object.__setattr__(self, "health_score", require_unit_float(self.health_score, "health_score"))
        object.__setattr__(self, "sla_breaches", require_non_negative_int(self.sla_breaches, "sla_breaches"))
        object.__setattr__(self, "open_cases", require_non_negative_int(self.open_cases, "open_cases"))
        object.__setattr__(self, "billing_issues", require_non_negative_int(self.billing_issues, "billing_issues"))
        object.__setattr__(self, "entitlement_count", require_non_negative_int(self.entitlement_count, "entitlement_count"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CustomerDecision(ContractRecord):
    """A decision related to customer/account operations."""

    decision_id: str = ""
    tenant_id: str = ""
    customer_id: str = ""
    account_id: str = ""
    disposition: CustomerDisposition = CustomerDisposition.APPROVED
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "customer_id", require_non_empty_text(self.customer_id, "customer_id"))
        if not isinstance(self.disposition, CustomerDisposition):
            raise ValueError("disposition must be a CustomerDisposition")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CustomerViolation(ContractRecord):
    """A violation detected in customer/account operations."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CustomerSnapshot(ContractRecord):
    """Point-in-time customer runtime state snapshot."""

    snapshot_id: str = ""
    total_customers: int = 0
    total_accounts: int = 0
    total_products: int = 0
    total_subscriptions: int = 0
    total_entitlements: int = 0
    total_health_snapshots: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_customers", require_non_negative_int(self.total_customers, "total_customers"))
        object.__setattr__(self, "total_accounts", require_non_negative_int(self.total_accounts, "total_accounts"))
        object.__setattr__(self, "total_products", require_non_negative_int(self.total_products, "total_products"))
        object.__setattr__(self, "total_subscriptions", require_non_negative_int(self.total_subscriptions, "total_subscriptions"))
        object.__setattr__(self, "total_entitlements", require_non_negative_int(self.total_entitlements, "total_entitlements"))
        object.__setattr__(self, "total_health_snapshots", require_non_negative_int(self.total_health_snapshots, "total_health_snapshots"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CustomerClosureReport(ContractRecord):
    """Summary report for customer runtime lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_customers: int = 0
    total_accounts: int = 0
    total_products: int = 0
    total_subscriptions: int = 0
    total_entitlements: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_customers", require_non_negative_int(self.total_customers, "total_customers"))
        object.__setattr__(self, "total_accounts", require_non_negative_int(self.total_accounts, "total_accounts"))
        object.__setattr__(self, "total_products", require_non_negative_int(self.total_products, "total_products"))
        object.__setattr__(self, "total_subscriptions", require_non_negative_int(self.total_subscriptions, "total_subscriptions"))
        object.__setattr__(self, "total_entitlements", require_non_negative_int(self.total_entitlements, "total_entitlements"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
