"""Purpose: marketplace / packaging / offering runtime engine.
Governance scope: registering offerings, packages, bundles, listings,
    evaluating eligibility, managing pricing bindings, detecting violations,
    producing immutable snapshots.
Dependencies: marketplace_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Retired offerings cannot be modified.
  - Bundle composition validates offering exists.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.marketplace_runtime import (
    BundleDisposition,
    BundleRecord,
    EligibilityRule,
    EligibilityStatus,
    ListingRecord,
    MarketplaceAssessment,
    MarketplaceChannel,
    MarketplaceClosureReport,
    MarketplaceSnapshot,
    MarketplaceViolation,
    OfferingKind,
    OfferingRecord,
    OfferingStatus,
    PackageRecord,
    PricingBinding,
    PricingDisposition,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-mkt", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_OFFERING_TERMINAL = frozenset({OfferingStatus.RETIRED})


class MarketplaceRuntimeEngine:
    """Marketplace / packaging / offering runtime engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._offerings: dict[str, OfferingRecord] = {}
        self._packages: dict[str, PackageRecord] = {}
        self._bundles: dict[str, BundleRecord] = {}
        self._listings: dict[str, ListingRecord] = {}
        self._eligibility_rules: dict[str, EligibilityRule] = {}
        self._pricing_bindings: dict[str, PricingBinding] = {}
        self._assessments: dict[str, MarketplaceAssessment] = {}
        self._violations: dict[str, MarketplaceViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def offering_count(self) -> int:
        return len(self._offerings)

    @property
    def package_count(self) -> int:
        return len(self._packages)

    @property
    def bundle_count(self) -> int:
        return len(self._bundles)

    @property
    def listing_count(self) -> int:
        return len(self._listings)

    @property
    def eligibility_rule_count(self) -> int:
        return len(self._eligibility_rules)

    @property
    def pricing_binding_count(self) -> int:
        return len(self._pricing_bindings)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Offerings
    # ------------------------------------------------------------------

    def register_offering(
        self,
        offering_id: str,
        product_id: str,
        tenant_id: str,
        display_name: str,
        kind: OfferingKind = OfferingKind.STANDALONE,
        version_ref: str = "",
        status: OfferingStatus = OfferingStatus.DRAFT,
    ) -> OfferingRecord:
        if offering_id in self._offerings:
            raise RuntimeCoreInvariantError(f"offering already registered: {offering_id}")
        now = self._now()
        record = OfferingRecord(
            offering_id=offering_id, product_id=product_id, tenant_id=tenant_id,
            display_name=display_name, kind=kind, status=status,
            version_ref=version_ref if version_ref else "latest",
            created_at=now,
        )
        self._offerings[offering_id] = record
        _emit(self._events, "register_offering", {"offering_id": offering_id, "product_id": product_id}, offering_id, self._now())
        return record

    def get_offering(self, offering_id: str) -> OfferingRecord:
        if offering_id not in self._offerings:
            raise RuntimeCoreInvariantError(f"unknown offering: {offering_id}")
        return self._offerings[offering_id]

    def activate_offering(self, offering_id: str) -> OfferingRecord:
        if offering_id not in self._offerings:
            raise RuntimeCoreInvariantError(f"unknown offering: {offering_id}")
        old = self._offerings[offering_id]
        if old.status in _OFFERING_TERMINAL:
            raise RuntimeCoreInvariantError(f"offering is in terminal state: {old.status.value}")
        updated = OfferingRecord(
            offering_id=old.offering_id, product_id=old.product_id, tenant_id=old.tenant_id,
            display_name=old.display_name, kind=old.kind, status=OfferingStatus.ACTIVE,
            version_ref=old.version_ref, created_at=old.created_at,
        )
        self._offerings[offering_id] = updated
        _emit(self._events, "activate_offering", {"offering_id": offering_id}, offering_id, self._now())
        return updated

    def suspend_offering(self, offering_id: str) -> OfferingRecord:
        if offering_id not in self._offerings:
            raise RuntimeCoreInvariantError(f"unknown offering: {offering_id}")
        old = self._offerings[offering_id]
        if old.status in _OFFERING_TERMINAL:
            raise RuntimeCoreInvariantError(f"offering is in terminal state: {old.status.value}")
        updated = OfferingRecord(
            offering_id=old.offering_id, product_id=old.product_id, tenant_id=old.tenant_id,
            display_name=old.display_name, kind=old.kind, status=OfferingStatus.SUSPENDED,
            version_ref=old.version_ref, created_at=old.created_at,
        )
        self._offerings[offering_id] = updated
        _emit(self._events, "suspend_offering", {"offering_id": offering_id}, offering_id, self._now())
        return updated

    def retire_offering(self, offering_id: str) -> OfferingRecord:
        if offering_id not in self._offerings:
            raise RuntimeCoreInvariantError(f"unknown offering: {offering_id}")
        old = self._offerings[offering_id]
        if old.status in _OFFERING_TERMINAL:
            raise RuntimeCoreInvariantError(f"offering already retired: {offering_id}")
        updated = OfferingRecord(
            offering_id=old.offering_id, product_id=old.product_id, tenant_id=old.tenant_id,
            display_name=old.display_name, kind=old.kind, status=OfferingStatus.RETIRED,
            version_ref=old.version_ref, created_at=old.created_at,
        )
        self._offerings[offering_id] = updated
        _emit(self._events, "retire_offering", {"offering_id": offering_id}, offering_id, self._now())
        return updated

    def offerings_for_tenant(self, tenant_id: str) -> tuple[OfferingRecord, ...]:
        return tuple(o for o in self._offerings.values() if o.tenant_id == tenant_id)

    def offerings_for_product(self, product_id: str) -> tuple[OfferingRecord, ...]:
        return tuple(o for o in self._offerings.values() if o.product_id == product_id)

    # ------------------------------------------------------------------
    # Packages
    # ------------------------------------------------------------------

    def register_package(
        self,
        package_id: str,
        tenant_id: str,
        display_name: str,
        status: OfferingStatus = OfferingStatus.DRAFT,
    ) -> PackageRecord:
        if package_id in self._packages:
            raise RuntimeCoreInvariantError(f"package already registered: {package_id}")
        now = self._now()
        record = PackageRecord(
            package_id=package_id, tenant_id=tenant_id, display_name=display_name,
            offering_count=0, status=status, created_at=now,
        )
        self._packages[package_id] = record
        _emit(self._events, "register_package", {"package_id": package_id}, package_id, self._now())
        return record

    def get_package(self, package_id: str) -> PackageRecord:
        if package_id not in self._packages:
            raise RuntimeCoreInvariantError(f"unknown package: {package_id}")
        return self._packages[package_id]

    def packages_for_tenant(self, tenant_id: str) -> tuple[PackageRecord, ...]:
        return tuple(p for p in self._packages.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Bundles
    # ------------------------------------------------------------------

    def add_to_bundle(
        self,
        bundle_id: str,
        package_id: str,
        offering_id: str,
        tenant_id: str,
    ) -> BundleRecord:
        if bundle_id in self._bundles:
            raise RuntimeCoreInvariantError(f"bundle entry already exists: {bundle_id}")
        if package_id not in self._packages:
            raise RuntimeCoreInvariantError(f"unknown package: {package_id}")
        if offering_id not in self._offerings:
            raise RuntimeCoreInvariantError(f"unknown offering: {offering_id}")
        offering = self._offerings[offering_id]
        now = self._now()
        # Determine disposition
        disposition = BundleDisposition.VALID
        if offering.status == OfferingStatus.RETIRED:
            disposition = BundleDisposition.EXPIRED
        elif offering.status == OfferingStatus.SUSPENDED:
            disposition = BundleDisposition.PARTIAL
        bundle = BundleRecord(
            bundle_id=bundle_id, package_id=package_id, offering_id=offering_id,
            tenant_id=tenant_id, disposition=disposition, created_at=now,
        )
        self._bundles[bundle_id] = bundle
        # Increment package offering_count
        pkg = self._packages[package_id]
        updated_pkg = PackageRecord(
            package_id=pkg.package_id, tenant_id=pkg.tenant_id, display_name=pkg.display_name,
            offering_count=pkg.offering_count + 1, status=pkg.status, created_at=pkg.created_at,
        )
        self._packages[package_id] = updated_pkg
        _emit(self._events, "add_to_bundle", {"bundle_id": bundle_id, "package_id": package_id, "offering_id": offering_id}, bundle_id, self._now())
        return bundle

    def bundles_for_package(self, package_id: str) -> tuple[BundleRecord, ...]:
        return tuple(b for b in self._bundles.values() if b.package_id == package_id)

    # ------------------------------------------------------------------
    # Listings
    # ------------------------------------------------------------------

    def create_listing(
        self,
        listing_id: str,
        offering_id: str,
        tenant_id: str,
        channel: MarketplaceChannel = MarketplaceChannel.DIRECT,
    ) -> ListingRecord:
        if listing_id in self._listings:
            raise RuntimeCoreInvariantError(f"listing already exists: {listing_id}")
        if offering_id not in self._offerings:
            raise RuntimeCoreInvariantError(f"unknown offering: {offering_id}")
        offering = self._offerings[offering_id]
        if offering.status in _OFFERING_TERMINAL:
            raise RuntimeCoreInvariantError(f"offering is retired: {offering_id}")
        now = self._now()
        listing = ListingRecord(
            listing_id=listing_id, offering_id=offering_id, tenant_id=tenant_id,
            channel=channel, active=True, listed_at=now,
        )
        self._listings[listing_id] = listing
        _emit(self._events, "create_listing", {"listing_id": listing_id, "offering_id": offering_id, "channel": channel.value}, listing_id, self._now())
        return listing

    def deactivate_listing(self, listing_id: str) -> ListingRecord:
        if listing_id not in self._listings:
            raise RuntimeCoreInvariantError(f"unknown listing: {listing_id}")
        old = self._listings[listing_id]
        updated = ListingRecord(
            listing_id=old.listing_id, offering_id=old.offering_id, tenant_id=old.tenant_id,
            channel=old.channel, active=False, listed_at=old.listed_at,
        )
        self._listings[listing_id] = updated
        _emit(self._events, "deactivate_listing", {"listing_id": listing_id}, listing_id, self._now())
        return updated

    def listings_for_offering(self, offering_id: str) -> tuple[ListingRecord, ...]:
        return tuple(l for l in self._listings.values() if l.offering_id == offering_id)

    def active_listings(self, tenant_id: str) -> tuple[ListingRecord, ...]:
        return tuple(l for l in self._listings.values() if l.tenant_id == tenant_id and l.active)

    # ------------------------------------------------------------------
    # Eligibility
    # ------------------------------------------------------------------

    def evaluate_eligibility(
        self,
        rule_id: str,
        offering_id: str,
        tenant_id: str,
        account_segment: str,
        has_entitlement: bool = True,
    ) -> EligibilityRule:
        if rule_id in self._eligibility_rules:
            raise RuntimeCoreInvariantError(f"eligibility rule already exists: {rule_id}")
        if offering_id not in self._offerings:
            raise RuntimeCoreInvariantError(f"unknown offering: {offering_id}")
        now = self._now()
        if has_entitlement:
            status = EligibilityStatus.ELIGIBLE
            reason = "entitlement verified"
        else:
            status = EligibilityStatus.INELIGIBLE
            reason = "no entitlement"
        rule = EligibilityRule(
            rule_id=rule_id, offering_id=offering_id, tenant_id=tenant_id,
            account_segment=account_segment, status=status, reason=reason,
            evaluated_at=now,
        )
        self._eligibility_rules[rule_id] = rule
        _emit(self._events, "evaluate_eligibility", {"rule_id": rule_id, "status": status.value}, rule_id, self._now())
        return rule

    def eligibility_for_offering(self, offering_id: str) -> tuple[EligibilityRule, ...]:
        return tuple(r for r in self._eligibility_rules.values() if r.offering_id == offering_id)

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    def bind_pricing(
        self,
        binding_id: str,
        offering_id: str,
        tenant_id: str,
        base_price: float,
        effective_price: float = 0.0,
        disposition: PricingDisposition = PricingDisposition.STANDARD,
        contract_ref: str = "",
    ) -> PricingBinding:
        if binding_id in self._pricing_bindings:
            raise RuntimeCoreInvariantError(f"pricing binding already exists: {binding_id}")
        if offering_id not in self._offerings:
            raise RuntimeCoreInvariantError(f"unknown offering: {offering_id}")
        now = self._now()
        eff = effective_price if effective_price > 0 else base_price
        binding = PricingBinding(
            binding_id=binding_id, offering_id=offering_id, tenant_id=tenant_id,
            base_price=base_price, effective_price=eff, disposition=disposition,
            contract_ref=contract_ref if contract_ref else "none",
            created_at=now,
        )
        self._pricing_bindings[binding_id] = binding
        _emit(self._events, "bind_pricing", {"binding_id": binding_id, "base": base_price, "effective": eff}, binding_id, self._now())
        return binding

    def pricing_for_offering(self, offering_id: str) -> tuple[PricingBinding, ...]:
        return tuple(p for p in self._pricing_bindings.values() if p.offering_id == offering_id)

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def marketplace_assessment(self, assessment_id: str, tenant_id: str) -> MarketplaceAssessment:
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError(f"assessment already exists: {assessment_id}")
        now = self._now()
        tenant_offerings = [o for o in self._offerings.values() if o.tenant_id == tenant_id]
        active_offerings = [o for o in tenant_offerings if o.status == OfferingStatus.ACTIVE]
        tenant_listings = [l for l in self._listings.values() if l.tenant_id == tenant_id]
        active_list = [l for l in tenant_listings if l.active]
        tenant_packages = [p for p in self._packages.values() if p.tenant_id == tenant_id]
        coverage = len(active_offerings) / len(tenant_offerings) if tenant_offerings else 0.0
        assessment = MarketplaceAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_offerings=len(tenant_offerings), active_offerings=len(active_offerings),
            total_listings=len(tenant_listings), active_listings=len(active_list),
            total_packages=len(tenant_packages),
            coverage_score=round(coverage, 4),
            assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "marketplace_assessment", {"assessment_id": assessment_id}, assessment_id, self._now())
        return assessment

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def marketplace_snapshot(self, snapshot_id: str) -> MarketplaceSnapshot:
        now = self._now()
        return MarketplaceSnapshot(
            snapshot_id=snapshot_id,
            total_offerings=len(self._offerings),
            total_packages=len(self._packages),
            total_bundles=len(self._bundles),
            total_listings=len(self._listings),
            total_eligibility_rules=len(self._eligibility_rules),
            total_pricing_bindings=len(self._pricing_bindings),
            total_assessments=len(self._assessments),
            total_violations=len(self._violations),
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------

    def detect_marketplace_violations(self, tenant_id: str) -> tuple[MarketplaceViolation, ...]:
        """Detect marketplace violations. Idempotent."""
        now = self._now()
        new_violations: list[MarketplaceViolation] = []

        # 1. Active offerings with no pricing
        for o in self._offerings.values():
            if o.tenant_id == tenant_id and o.status == OfferingStatus.ACTIVE:
                pricing = self.pricing_for_offering(o.offering_id)
                if not pricing:
                    vid = stable_identifier("viol-mkt", {"type": "no_pricing", "offering_id": o.offering_id})
                    if vid not in self._violations:
                        v = MarketplaceViolation(
                            violation_id=vid, tenant_id=tenant_id,
                            operation="no_pricing",
                            reason=f"active offering {o.offering_id} has no pricing binding",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2. Bundles with expired/invalid disposition
        for b in self._bundles.values():
            if b.tenant_id == tenant_id and b.disposition in (BundleDisposition.EXPIRED, BundleDisposition.INVALID):
                vid = stable_identifier("viol-mkt", {"type": "invalid_bundle", "bundle_id": b.bundle_id})
                if vid not in self._violations:
                    v = MarketplaceViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="invalid_bundle",
                        reason=f"bundle {b.bundle_id} has disposition {b.disposition.value}",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. Listings on non-active offerings
        for l in self._listings.values():
            if l.tenant_id == tenant_id and l.active:
                offering = self._offerings.get(l.offering_id)
                if offering and offering.status != OfferingStatus.ACTIVE:
                    vid = stable_identifier("viol-mkt", {"type": "listing_inactive_offering", "listing_id": l.listing_id})
                    if vid not in self._violations:
                        v = MarketplaceViolation(
                            violation_id=vid, tenant_id=tenant_id,
                            operation="listing_inactive_offering",
                            reason=f"listing {l.listing_id} is active but offering {l.offering_id} is {offering.status.value}",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        _emit(self._events, "detect_marketplace_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id, self._now())
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[MarketplaceViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> MarketplaceClosureReport:
        now = self._now()
        return MarketplaceClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_offerings=len([o for o in self._offerings.values() if o.tenant_id == tenant_id]),
            total_packages=len([p for p in self._packages.values() if p.tenant_id == tenant_id]),
            total_bundles=len([b for b in self._bundles.values() if b.tenant_id == tenant_id]),
            total_listings=len([l for l in self._listings.values() if l.tenant_id == tenant_id]),
            total_eligibility_rules=len([r for r in self._eligibility_rules.values() if r.tenant_id == tenant_id]),
            total_pricing_bindings=len([p for p in self._pricing_bindings.values() if p.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            closed_at=now,
        )

    # ------------------------------------------------------------------
    # Snapshot / restore
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "offerings": self._offerings,
            "packages": self._packages,
            "bundles": self._bundles,
            "listings": self._listings,
            "eligibility_rules": self._eligibility_rules,
            "pricing_bindings": self._pricing_bindings,
            "assessments": self._assessments,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._offerings):
            parts.append(f"o:{k}")
        for k in sorted(self._packages):
            parts.append(f"pk:{k}")
        for k in sorted(self._bundles):
            parts.append(f"b:{k}")
        for k in sorted(self._listings):
            parts.append(f"l:{k}")
        for k in sorted(self._eligibility_rules):
            parts.append(f"e:{k}")
        for k in sorted(self._pricing_bindings):
            parts.append(f"pb:{k}")
        for k in sorted(self._assessments):
            parts.append(f"a:{k}")
        for k in sorted(self._violations):
            parts.append(f"v:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
