"""Purpose: marketplace / packaging / offering runtime contracts.
Governance scope: typed descriptors for offerings, packages, bundles,
    listings, eligibility rules, pricing bindings, assessments, snapshots,
    violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every offering references a tenant and product.
  - Pricing bindings are non-negative.
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


class OfferingStatus(Enum):
    """Status of an offering."""
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class OfferingKind(Enum):
    """Kind of offering."""
    STANDALONE = "standalone"
    BUNDLE = "bundle"
    ADD_ON = "add_on"
    TRIAL = "trial"
    CUSTOM = "custom"


class BundleDisposition(Enum):
    """Disposition of a bundle."""
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"
    EXPIRED = "expired"


class EligibilityStatus(Enum):
    """Status of eligibility evaluation."""
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    REQUIRES_APPROVAL = "requires_approval"
    EXPIRED = "expired"


class MarketplaceChannel(Enum):
    """Channel through which an offering is listed."""
    DIRECT = "direct"
    PARTNER = "partner"
    MARKETPLACE = "marketplace"
    INTERNAL = "internal"
    API = "api"


class PricingDisposition(Enum):
    """Disposition of a pricing binding."""
    STANDARD = "standard"
    DISCOUNTED = "discounted"
    PROMOTIONAL = "promotional"
    NEGOTIATED = "negotiated"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OfferingRecord(ContractRecord):
    """A sellable offering."""

    offering_id: str = ""
    product_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: OfferingKind = OfferingKind.STANDALONE
    status: OfferingStatus = OfferingStatus.DRAFT
    version_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "offering_id", require_non_empty_text(self.offering_id, "offering_id"))
        object.__setattr__(self, "product_id", require_non_empty_text(self.product_id, "product_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, OfferingKind):
            raise ValueError("kind must be an OfferingKind")
        if not isinstance(self.status, OfferingStatus):
            raise ValueError("status must be an OfferingStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PackageRecord(ContractRecord):
    """A package composing multiple offerings."""

    package_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    offering_count: int = 0
    status: OfferingStatus = OfferingStatus.DRAFT
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_id", require_non_empty_text(self.package_id, "package_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "offering_count", require_non_negative_int(self.offering_count, "offering_count"))
        if not isinstance(self.status, OfferingStatus):
            raise ValueError("status must be an OfferingStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BundleRecord(ContractRecord):
    """A bundle linking an offering to a package."""

    bundle_id: str = ""
    package_id: str = ""
    offering_id: str = ""
    tenant_id: str = ""
    disposition: BundleDisposition = BundleDisposition.VALID
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_id", require_non_empty_text(self.bundle_id, "bundle_id"))
        object.__setattr__(self, "package_id", require_non_empty_text(self.package_id, "package_id"))
        object.__setattr__(self, "offering_id", require_non_empty_text(self.offering_id, "offering_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, BundleDisposition):
            raise ValueError("disposition must be a BundleDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ListingRecord(ContractRecord):
    """A marketplace listing for an offering."""

    listing_id: str = ""
    offering_id: str = ""
    tenant_id: str = ""
    channel: MarketplaceChannel = MarketplaceChannel.DIRECT
    active: bool = True
    listed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "listing_id", require_non_empty_text(self.listing_id, "listing_id"))
        object.__setattr__(self, "offering_id", require_non_empty_text(self.offering_id, "offering_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.channel, MarketplaceChannel):
            raise ValueError("channel must be a MarketplaceChannel")
        require_datetime_text(self.listed_at, "listed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EligibilityRule(ContractRecord):
    """A rule governing offering eligibility."""

    rule_id: str = ""
    offering_id: str = ""
    tenant_id: str = ""
    account_segment: str = ""
    status: EligibilityStatus = EligibilityStatus.ELIGIBLE
    reason: str = ""
    evaluated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "offering_id", require_non_empty_text(self.offering_id, "offering_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "account_segment", require_non_empty_text(self.account_segment, "account_segment"))
        if not isinstance(self.status, EligibilityStatus):
            raise ValueError("status must be an EligibilityStatus")
        require_datetime_text(self.evaluated_at, "evaluated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PricingBinding(ContractRecord):
    """A pricing binding for an offering."""

    binding_id: str = ""
    offering_id: str = ""
    tenant_id: str = ""
    base_price: float = 0.0
    effective_price: float = 0.0
    disposition: PricingDisposition = PricingDisposition.STANDARD
    contract_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "offering_id", require_non_empty_text(self.offering_id, "offering_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "base_price", require_non_negative_float(self.base_price, "base_price"))
        object.__setattr__(self, "effective_price", require_non_negative_float(self.effective_price, "effective_price"))
        if not isinstance(self.disposition, PricingDisposition):
            raise ValueError("disposition must be a PricingDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MarketplaceAssessment(ContractRecord):
    """An assessment of marketplace health."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_offerings: int = 0
    active_offerings: int = 0
    total_listings: int = 0
    active_listings: int = 0
    total_packages: int = 0
    coverage_score: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_offerings", require_non_negative_int(self.total_offerings, "total_offerings"))
        object.__setattr__(self, "active_offerings", require_non_negative_int(self.active_offerings, "active_offerings"))
        object.__setattr__(self, "total_listings", require_non_negative_int(self.total_listings, "total_listings"))
        object.__setattr__(self, "active_listings", require_non_negative_int(self.active_listings, "active_listings"))
        object.__setattr__(self, "total_packages", require_non_negative_int(self.total_packages, "total_packages"))
        object.__setattr__(self, "coverage_score", require_unit_float(self.coverage_score, "coverage_score"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MarketplaceSnapshot(ContractRecord):
    """Point-in-time marketplace runtime state snapshot."""

    snapshot_id: str = ""
    total_offerings: int = 0
    total_packages: int = 0
    total_bundles: int = 0
    total_listings: int = 0
    total_eligibility_rules: int = 0
    total_pricing_bindings: int = 0
    total_assessments: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_offerings", require_non_negative_int(self.total_offerings, "total_offerings"))
        object.__setattr__(self, "total_packages", require_non_negative_int(self.total_packages, "total_packages"))
        object.__setattr__(self, "total_bundles", require_non_negative_int(self.total_bundles, "total_bundles"))
        object.__setattr__(self, "total_listings", require_non_negative_int(self.total_listings, "total_listings"))
        object.__setattr__(self, "total_eligibility_rules", require_non_negative_int(self.total_eligibility_rules, "total_eligibility_rules"))
        object.__setattr__(self, "total_pricing_bindings", require_non_negative_int(self.total_pricing_bindings, "total_pricing_bindings"))
        object.__setattr__(self, "total_assessments", require_non_negative_int(self.total_assessments, "total_assessments"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MarketplaceViolation(ContractRecord):
    """A violation detected in marketplace operations."""

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
class MarketplaceClosureReport(ContractRecord):
    """Summary report for marketplace runtime lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_offerings: int = 0
    total_packages: int = 0
    total_bundles: int = 0
    total_listings: int = 0
    total_eligibility_rules: int = 0
    total_pricing_bindings: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_offerings", require_non_negative_int(self.total_offerings, "total_offerings"))
        object.__setattr__(self, "total_packages", require_non_negative_int(self.total_packages, "total_packages"))
        object.__setattr__(self, "total_bundles", require_non_negative_int(self.total_bundles, "total_bundles"))
        object.__setattr__(self, "total_listings", require_non_negative_int(self.total_listings, "total_listings"))
        object.__setattr__(self, "total_eligibility_rules", require_non_negative_int(self.total_eligibility_rules, "total_eligibility_rules"))
        object.__setattr__(self, "total_pricing_bindings", require_non_negative_int(self.total_pricing_bindings, "total_pricing_bindings"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
