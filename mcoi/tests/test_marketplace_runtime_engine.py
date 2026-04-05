"""Comprehensive tests for MarketplaceRuntimeEngine.

Covers: offerings, packages, bundles, listings, eligibility, pricing bindings,
assessments, violations, snapshots, closure reports, state hashes, and
golden end-to-end scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.marketplace_runtime import MarketplaceRuntimeEngine
from mcoi_runtime.contracts.marketplace_runtime import (
    BundleDisposition,
    EligibilityStatus,
    MarketplaceChannel,
    OfferingKind,
    OfferingStatus,
    PricingDisposition,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(spine: EventSpineEngine) -> MarketplaceRuntimeEngine:
    return MarketplaceRuntimeEngine(spine)


def _off(engine: MarketplaceRuntimeEngine, oid: str = "o1", pid: str = "p1",
         tid: str = "t1", name: str = "Offering-1",
         kind: OfferingKind = OfferingKind.STANDALONE,
         version_ref: str = "", status: OfferingStatus = OfferingStatus.DRAFT):
    return engine.register_offering(oid, pid, tid, name, kind, version_ref, status)


def _pkg(engine: MarketplaceRuntimeEngine, pkid: str = "pk1", tid: str = "t1",
         name: str = "Package-1", status: OfferingStatus = OfferingStatus.DRAFT):
    return engine.register_package(pkid, tid, name, status)


def _active_off(engine: MarketplaceRuntimeEngine, oid: str = "o1", pid: str = "p1",
                tid: str = "t1", name: str = "Offering-1"):
    _off(engine, oid, pid, tid, name)
    return engine.activate_offering(oid)


# ===========================================================================
# 1. CONSTRUCTOR
# ===========================================================================


class TestConstructor:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            MarketplaceRuntimeEngine("not_a_spine")

    def test_requires_event_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            MarketplaceRuntimeEngine(None)

    def test_valid_construction(self, spine):
        eng = MarketplaceRuntimeEngine(spine)
        assert eng.offering_count == 0

    def test_initial_counts_zero(self, engine):
        assert engine.offering_count == 0
        assert engine.package_count == 0
        assert engine.bundle_count == 0
        assert engine.listing_count == 0
        assert engine.eligibility_rule_count == 0
        assert engine.pricing_binding_count == 0
        assert engine.assessment_count == 0
        assert engine.violation_count == 0


# ===========================================================================
# 2. REGISTER OFFERING
# ===========================================================================


class TestRegisterOffering:
    def test_basic_registration(self, engine):
        rec = _off(engine)
        assert rec.offering_id == "o1"
        assert rec.product_id == "p1"
        assert rec.tenant_id == "t1"
        assert rec.display_name == "Offering-1"

    def test_default_kind_standalone(self, engine):
        rec = _off(engine)
        assert rec.kind == OfferingKind.STANDALONE

    def test_default_status_draft(self, engine):
        rec = _off(engine)
        assert rec.status == OfferingStatus.DRAFT

    def test_default_version_ref_latest(self, engine):
        rec = _off(engine)
        assert rec.version_ref == "latest"

    def test_explicit_version_ref(self, engine):
        rec = _off(engine, version_ref="2.0.0")
        assert rec.version_ref == "2.0.0"

    def test_explicit_kind(self, engine):
        rec = _off(engine, kind=OfferingKind.BUNDLE)
        assert rec.kind == OfferingKind.BUNDLE

    def test_explicit_kind_addon(self, engine):
        rec = _off(engine, kind=OfferingKind.ADD_ON)
        assert rec.kind == OfferingKind.ADD_ON

    def test_explicit_kind_trial(self, engine):
        rec = _off(engine, kind=OfferingKind.TRIAL)
        assert rec.kind == OfferingKind.TRIAL

    def test_explicit_kind_custom(self, engine):
        rec = _off(engine, kind=OfferingKind.CUSTOM)
        assert rec.kind == OfferingKind.CUSTOM

    def test_explicit_status_active(self, engine):
        rec = _off(engine, status=OfferingStatus.ACTIVE)
        assert rec.status == OfferingStatus.ACTIVE

    def test_duplicate_raises(self, engine):
        _off(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            _off(engine)

    def test_increments_count(self, engine):
        _off(engine, "o1")
        _off(engine, "o2")
        assert engine.offering_count == 2

    def test_has_created_at(self, engine):
        rec = _off(engine)
        assert rec.created_at != ""

    def test_records_are_frozen(self, engine):
        rec = _off(engine)
        with pytest.raises(AttributeError):
            rec.status = OfferingStatus.ACTIVE


# ===========================================================================
# 3. GET OFFERING
# ===========================================================================


class TestGetOffering:
    def test_get_existing(self, engine):
        _off(engine)
        rec = engine.get_offering("o1")
        assert rec.offering_id == "o1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown offering"):
            engine.get_offering("nope")

    def test_get_returns_same_data(self, engine):
        original = _off(engine)
        fetched = engine.get_offering("o1")
        assert original.offering_id == fetched.offering_id
        assert original.display_name == fetched.display_name


# ===========================================================================
# 4. ACTIVATE OFFERING
# ===========================================================================


class TestActivateOffering:
    def test_activate_draft(self, engine):
        _off(engine)
        rec = engine.activate_offering("o1")
        assert rec.status == OfferingStatus.ACTIVE

    def test_activate_suspended(self, engine):
        _off(engine)
        engine.suspend_offering("o1")
        rec = engine.activate_offering("o1")
        assert rec.status == OfferingStatus.ACTIVE

    def test_activate_retired_raises(self, engine):
        _off(engine)
        engine.retire_offering("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.activate_offering("o1")

    def test_activate_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown offering"):
            engine.activate_offering("nope")

    def test_activate_preserves_fields(self, engine):
        _off(engine, kind=OfferingKind.TRIAL, version_ref="3.0")
        rec = engine.activate_offering("o1")
        assert rec.kind == OfferingKind.TRIAL
        assert rec.version_ref == "3.0"

    def test_activate_already_active(self, engine):
        _off(engine, status=OfferingStatus.ACTIVE)
        rec = engine.activate_offering("o1")
        assert rec.status == OfferingStatus.ACTIVE


# ===========================================================================
# 5. SUSPEND OFFERING
# ===========================================================================


class TestSuspendOffering:
    def test_suspend_draft(self, engine):
        _off(engine)
        rec = engine.suspend_offering("o1")
        assert rec.status == OfferingStatus.SUSPENDED

    def test_suspend_active(self, engine):
        _active_off(engine)
        rec = engine.suspend_offering("o1")
        assert rec.status == OfferingStatus.SUSPENDED

    def test_suspend_retired_raises(self, engine):
        _off(engine)
        engine.retire_offering("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.suspend_offering("o1")

    def test_suspend_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown offering"):
            engine.suspend_offering("nope")

    def test_suspend_preserves_fields(self, engine):
        _off(engine, pid="p99", name="Special")
        rec = engine.suspend_offering("o1")
        assert rec.product_id == "p99"
        assert rec.display_name == "Special"


# ===========================================================================
# 6. RETIRE OFFERING
# ===========================================================================


class TestRetireOffering:
    def test_retire_draft(self, engine):
        _off(engine)
        rec = engine.retire_offering("o1")
        assert rec.status == OfferingStatus.RETIRED

    def test_retire_active(self, engine):
        _active_off(engine)
        rec = engine.retire_offering("o1")
        assert rec.status == OfferingStatus.RETIRED

    def test_retire_suspended(self, engine):
        _off(engine)
        engine.suspend_offering("o1")
        rec = engine.retire_offering("o1")
        assert rec.status == OfferingStatus.RETIRED

    def test_retire_already_retired_raises(self, engine):
        _off(engine)
        engine.retire_offering("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="already retired"):
            engine.retire_offering("o1")

    def test_retire_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown offering"):
            engine.retire_offering("nope")


# ===========================================================================
# 7. OFFERINGS FOR TENANT / PRODUCT
# ===========================================================================


class TestOfferingsForTenant:
    def test_empty(self, engine):
        assert engine.offerings_for_tenant("t1") == ()

    def test_single(self, engine):
        _off(engine)
        result = engine.offerings_for_tenant("t1")
        assert len(result) == 1
        assert result[0].offering_id == "o1"

    def test_filters_by_tenant(self, engine):
        _off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t2")
        assert len(engine.offerings_for_tenant("t1")) == 1
        assert len(engine.offerings_for_tenant("t2")) == 1

    def test_multiple_same_tenant(self, engine):
        _off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t1")
        _off(engine, "o3", tid="t1")
        assert len(engine.offerings_for_tenant("t1")) == 3

    def test_returns_tuple(self, engine):
        result = engine.offerings_for_tenant("t1")
        assert isinstance(result, tuple)


class TestOfferingsForProduct:
    def test_empty(self, engine):
        assert engine.offerings_for_product("p1") == ()

    def test_single(self, engine):
        _off(engine, pid="p1")
        result = engine.offerings_for_product("p1")
        assert len(result) == 1

    def test_filters_by_product(self, engine):
        _off(engine, "o1", pid="p1")
        _off(engine, "o2", pid="p2")
        assert len(engine.offerings_for_product("p1")) == 1
        assert len(engine.offerings_for_product("p2")) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.offerings_for_product("p1"), tuple)


# ===========================================================================
# 8. REGISTER PACKAGE
# ===========================================================================


class TestRegisterPackage:
    def test_basic_registration(self, engine):
        rec = _pkg(engine)
        assert rec.package_id == "pk1"
        assert rec.tenant_id == "t1"
        assert rec.display_name == "Package-1"

    def test_default_status_draft(self, engine):
        rec = _pkg(engine)
        assert rec.status == OfferingStatus.DRAFT

    def test_initial_offering_count_zero(self, engine):
        rec = _pkg(engine)
        assert rec.offering_count == 0

    def test_duplicate_raises(self, engine):
        _pkg(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            _pkg(engine)

    def test_increments_count(self, engine):
        _pkg(engine, "pk1")
        _pkg(engine, "pk2")
        assert engine.package_count == 2

    def test_has_created_at(self, engine):
        rec = _pkg(engine)
        assert rec.created_at != ""

    def test_explicit_status(self, engine):
        rec = _pkg(engine, status=OfferingStatus.ACTIVE)
        assert rec.status == OfferingStatus.ACTIVE

    def test_frozen(self, engine):
        rec = _pkg(engine)
        with pytest.raises(AttributeError):
            rec.status = OfferingStatus.ACTIVE


# ===========================================================================
# 9. GET PACKAGE
# ===========================================================================


class TestGetPackage:
    def test_get_existing(self, engine):
        _pkg(engine)
        rec = engine.get_package("pk1")
        assert rec.package_id == "pk1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown package"):
            engine.get_package("nope")


# ===========================================================================
# 10. PACKAGES FOR TENANT
# ===========================================================================


class TestPackagesForTenant:
    def test_empty(self, engine):
        assert engine.packages_for_tenant("t1") == ()

    def test_single(self, engine):
        _pkg(engine)
        assert len(engine.packages_for_tenant("t1")) == 1

    def test_filters_by_tenant(self, engine):
        _pkg(engine, "pk1", tid="t1")
        _pkg(engine, "pk2", tid="t2")
        assert len(engine.packages_for_tenant("t1")) == 1
        assert len(engine.packages_for_tenant("t2")) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.packages_for_tenant("t1"), tuple)


# ===========================================================================
# 11. ADD TO BUNDLE
# ===========================================================================


class TestAddToBundle:
    def test_basic_bundle(self, engine):
        _off(engine)
        _pkg(engine)
        rec = engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert rec.bundle_id == "b1"
        assert rec.package_id == "pk1"
        assert rec.offering_id == "o1"
        assert rec.tenant_id == "t1"

    def test_valid_disposition_for_active(self, engine):
        _active_off(engine)
        _pkg(engine)
        rec = engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert rec.disposition == BundleDisposition.VALID

    def test_valid_disposition_for_draft(self, engine):
        _off(engine)
        _pkg(engine)
        rec = engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert rec.disposition == BundleDisposition.VALID

    def test_expired_disposition_for_retired(self, engine):
        _off(engine)
        engine.retire_offering("o1")
        _pkg(engine)
        rec = engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert rec.disposition == BundleDisposition.EXPIRED

    def test_partial_disposition_for_suspended(self, engine):
        _off(engine)
        engine.suspend_offering("o1")
        _pkg(engine)
        rec = engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert rec.disposition == BundleDisposition.PARTIAL

    def test_duplicate_raises(self, engine):
        _off(engine)
        _pkg(engine)
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.add_to_bundle("b1", "pk1", "o1", "t1")

    def test_unknown_package_raises(self, engine):
        _off(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="unknown package"):
            engine.add_to_bundle("b1", "nope", "o1", "t1")

    def test_unknown_offering_raises(self, engine):
        _pkg(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="unknown offering"):
            engine.add_to_bundle("b1", "pk1", "nope", "t1")

    def test_increments_package_offering_count(self, engine):
        _off(engine, "o1")
        _off(engine, "o2")
        _pkg(engine)
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert engine.get_package("pk1").offering_count == 1
        engine.add_to_bundle("b2", "pk1", "o2", "t1")
        assert engine.get_package("pk1").offering_count == 2

    def test_increments_bundle_count(self, engine):
        _off(engine)
        _pkg(engine)
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert engine.bundle_count == 1

    def test_has_created_at(self, engine):
        _off(engine)
        _pkg(engine)
        rec = engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert rec.created_at != ""


# ===========================================================================
# 12. BUNDLES FOR PACKAGE
# ===========================================================================


class TestBundlesForPackage:
    def test_empty(self, engine):
        assert engine.bundles_for_package("pk1") == ()

    def test_single(self, engine):
        _off(engine)
        _pkg(engine)
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        result = engine.bundles_for_package("pk1")
        assert len(result) == 1

    def test_filters_by_package(self, engine):
        _off(engine, "o1")
        _off(engine, "o2")
        _pkg(engine, "pk1")
        _pkg(engine, "pk2")
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        engine.add_to_bundle("b2", "pk2", "o2", "t1")
        assert len(engine.bundles_for_package("pk1")) == 1
        assert len(engine.bundles_for_package("pk2")) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.bundles_for_package("pk1"), tuple)

    def test_multiple_in_same_package(self, engine):
        _off(engine, "o1")
        _off(engine, "o2")
        _off(engine, "o3")
        _pkg(engine)
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        engine.add_to_bundle("b2", "pk1", "o2", "t1")
        engine.add_to_bundle("b3", "pk1", "o3", "t1")
        assert len(engine.bundles_for_package("pk1")) == 3


# ===========================================================================
# 13. CREATE LISTING
# ===========================================================================


class TestCreateListing:
    def test_basic_listing(self, engine):
        _off(engine)
        rec = engine.create_listing("l1", "o1", "t1")
        assert rec.listing_id == "l1"
        assert rec.offering_id == "o1"
        assert rec.tenant_id == "t1"

    def test_default_channel_direct(self, engine):
        _off(engine)
        rec = engine.create_listing("l1", "o1", "t1")
        assert rec.channel == MarketplaceChannel.DIRECT

    def test_active_by_default(self, engine):
        _off(engine)
        rec = engine.create_listing("l1", "o1", "t1")
        assert rec.active is True

    def test_explicit_channel_partner(self, engine):
        _off(engine)
        rec = engine.create_listing("l1", "o1", "t1", MarketplaceChannel.PARTNER)
        assert rec.channel == MarketplaceChannel.PARTNER

    def test_explicit_channel_marketplace(self, engine):
        _off(engine)
        rec = engine.create_listing("l1", "o1", "t1", MarketplaceChannel.MARKETPLACE)
        assert rec.channel == MarketplaceChannel.MARKETPLACE

    def test_explicit_channel_internal(self, engine):
        _off(engine)
        rec = engine.create_listing("l1", "o1", "t1", MarketplaceChannel.INTERNAL)
        assert rec.channel == MarketplaceChannel.INTERNAL

    def test_explicit_channel_api(self, engine):
        _off(engine)
        rec = engine.create_listing("l1", "o1", "t1", MarketplaceChannel.API)
        assert rec.channel == MarketplaceChannel.API

    def test_duplicate_raises(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.create_listing("l1", "o1", "t1")

    def test_unknown_offering_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown offering"):
            engine.create_listing("l1", "nope", "t1")

    def test_retired_offering_raises(self, engine):
        _off(engine)
        engine.retire_offering("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="retired"):
            engine.create_listing("l1", "o1", "t1")

    def test_draft_offering_allowed(self, engine):
        _off(engine)
        rec = engine.create_listing("l1", "o1", "t1")
        assert rec.listing_id == "l1"

    def test_suspended_offering_allowed(self, engine):
        _off(engine)
        engine.suspend_offering("o1")
        rec = engine.create_listing("l1", "o1", "t1")
        assert rec.listing_id == "l1"

    def test_increments_count(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        assert engine.listing_count == 1

    def test_has_listed_at(self, engine):
        _off(engine)
        rec = engine.create_listing("l1", "o1", "t1")
        assert rec.listed_at != ""


# ===========================================================================
# 14. DEACTIVATE LISTING
# ===========================================================================


class TestDeactivateListing:
    def test_deactivate(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        rec = engine.deactivate_listing("l1")
        assert rec.active is False

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown listing"):
            engine.deactivate_listing("nope")

    def test_preserves_fields(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1", MarketplaceChannel.PARTNER)
        rec = engine.deactivate_listing("l1")
        assert rec.channel == MarketplaceChannel.PARTNER
        assert rec.offering_id == "o1"

    def test_idempotent_deactivation(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        engine.deactivate_listing("l1")
        rec = engine.deactivate_listing("l1")
        assert rec.active is False


# ===========================================================================
# 15. LISTINGS FOR OFFERING / ACTIVE LISTINGS
# ===========================================================================


class TestListingsForOffering:
    def test_empty(self, engine):
        assert engine.listings_for_offering("o1") == ()

    def test_single(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        result = engine.listings_for_offering("o1")
        assert len(result) == 1

    def test_filters_by_offering(self, engine):
        _off(engine, "o1")
        _off(engine, "o2")
        engine.create_listing("l1", "o1", "t1")
        engine.create_listing("l2", "o2", "t1")
        assert len(engine.listings_for_offering("o1")) == 1
        assert len(engine.listings_for_offering("o2")) == 1

    def test_includes_inactive(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        engine.deactivate_listing("l1")
        assert len(engine.listings_for_offering("o1")) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.listings_for_offering("o1"), tuple)


class TestActiveListings:
    def test_empty(self, engine):
        assert engine.active_listings("t1") == ()

    def test_includes_active(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        result = engine.active_listings("t1")
        assert len(result) == 1

    def test_excludes_inactive(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        engine.deactivate_listing("l1")
        assert len(engine.active_listings("t1")) == 0

    def test_filters_by_tenant(self, engine):
        _off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t2")
        engine.create_listing("l1", "o1", "t1")
        engine.create_listing("l2", "o2", "t2")
        assert len(engine.active_listings("t1")) == 1
        assert len(engine.active_listings("t2")) == 1

    def test_mixed_active_inactive(self, engine):
        _off(engine, "o1")
        _off(engine, "o2")
        engine.create_listing("l1", "o1", "t1")
        engine.create_listing("l2", "o2", "t1")
        engine.deactivate_listing("l1")
        result = engine.active_listings("t1")
        assert len(result) == 1
        assert result[0].listing_id == "l2"

    def test_returns_tuple(self, engine):
        assert isinstance(engine.active_listings("t1"), tuple)


# ===========================================================================
# 16. EVALUATE ELIGIBILITY
# ===========================================================================


class TestEvaluateEligibility:
    def test_eligible_with_entitlement(self, engine):
        _off(engine)
        rec = engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        assert rec.status == EligibilityStatus.ELIGIBLE
        assert rec.reason == "entitlement verified"

    def test_ineligible_without_entitlement(self, engine):
        _off(engine)
        rec = engine.evaluate_eligibility("e1", "o1", "t1", "enterprise", has_entitlement=False)
        assert rec.status == EligibilityStatus.INELIGIBLE
        assert rec.reason == "no entitlement"

    def test_default_has_entitlement_true(self, engine):
        _off(engine)
        rec = engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        assert rec.status == EligibilityStatus.ELIGIBLE

    def test_duplicate_raises(self, engine):
        _off(engine)
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")

    def test_unknown_offering_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown offering"):
            engine.evaluate_eligibility("e1", "nope", "t1", "enterprise")

    def test_fields_populated(self, engine):
        _off(engine)
        rec = engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        assert rec.rule_id == "e1"
        assert rec.offering_id == "o1"
        assert rec.tenant_id == "t1"
        assert rec.account_segment == "enterprise"
        assert rec.evaluated_at != ""

    def test_increments_count(self, engine):
        _off(engine)
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        assert engine.eligibility_rule_count == 1

    def test_different_segments(self, engine):
        _off(engine)
        r1 = engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        r2 = engine.evaluate_eligibility("e2", "o1", "t1", "startup")
        assert r1.account_segment == "enterprise"
        assert r2.account_segment == "startup"


# ===========================================================================
# 17. ELIGIBILITY FOR OFFERING
# ===========================================================================


class TestEligibilityForOffering:
    def test_empty(self, engine):
        assert engine.eligibility_for_offering("o1") == ()

    def test_single(self, engine):
        _off(engine)
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        result = engine.eligibility_for_offering("o1")
        assert len(result) == 1

    def test_filters_by_offering(self, engine):
        _off(engine, "o1")
        _off(engine, "o2")
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        engine.evaluate_eligibility("e2", "o2", "t1", "startup")
        assert len(engine.eligibility_for_offering("o1")) == 1
        assert len(engine.eligibility_for_offering("o2")) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.eligibility_for_offering("o1"), tuple)

    def test_multiple_rules_same_offering(self, engine):
        _off(engine)
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        engine.evaluate_eligibility("e2", "o1", "t1", "startup")
        assert len(engine.eligibility_for_offering("o1")) == 2


# ===========================================================================
# 18. BIND PRICING
# ===========================================================================


class TestBindPricing:
    def test_basic_binding(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0)
        assert rec.binding_id == "bp1"
        assert rec.offering_id == "o1"
        assert rec.tenant_id == "t1"
        assert rec.base_price == 100.0

    def test_effective_defaults_to_base(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0)
        assert rec.effective_price == 100.0

    def test_explicit_effective_price(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0, effective_price=80.0)
        assert rec.effective_price == 80.0

    def test_zero_effective_defaults_to_base(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 50.0, effective_price=0.0)
        assert rec.effective_price == 50.0

    def test_default_disposition_standard(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0)
        assert rec.disposition == PricingDisposition.STANDARD

    def test_explicit_disposition_discounted(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0,
                                   disposition=PricingDisposition.DISCOUNTED)
        assert rec.disposition == PricingDisposition.DISCOUNTED

    def test_explicit_disposition_promotional(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0,
                                   disposition=PricingDisposition.PROMOTIONAL)
        assert rec.disposition == PricingDisposition.PROMOTIONAL

    def test_explicit_disposition_negotiated(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0,
                                   disposition=PricingDisposition.NEGOTIATED)
        assert rec.disposition == PricingDisposition.NEGOTIATED

    def test_default_contract_ref_none(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0)
        assert rec.contract_ref == "none"

    def test_explicit_contract_ref(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0, contract_ref="CTR-001")
        assert rec.contract_ref == "CTR-001"

    def test_duplicate_raises(self, engine):
        _off(engine)
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.bind_pricing("bp1", "o1", "t1", 100.0)

    def test_unknown_offering_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown offering"):
            engine.bind_pricing("bp1", "nope", "t1", 100.0)

    def test_increments_count(self, engine):
        _off(engine)
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        assert engine.pricing_binding_count == 1

    def test_has_created_at(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 100.0)
        assert rec.created_at != ""


# ===========================================================================
# 19. PRICING FOR OFFERING
# ===========================================================================


class TestPricingForOffering:
    def test_empty(self, engine):
        assert engine.pricing_for_offering("o1") == ()

    def test_single(self, engine):
        _off(engine)
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        result = engine.pricing_for_offering("o1")
        assert len(result) == 1

    def test_filters_by_offering(self, engine):
        _off(engine, "o1")
        _off(engine, "o2")
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        engine.bind_pricing("bp2", "o2", "t1", 200.0)
        assert len(engine.pricing_for_offering("o1")) == 1
        assert len(engine.pricing_for_offering("o2")) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.pricing_for_offering("o1"), tuple)

    def test_multiple_bindings_same_offering(self, engine):
        _off(engine)
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        engine.bind_pricing("bp2", "o1", "t1", 200.0)
        assert len(engine.pricing_for_offering("o1")) == 2


# ===========================================================================
# 20. MARKETPLACE ASSESSMENT
# ===========================================================================


class TestMarketplaceAssessment:
    def test_empty_tenant(self, engine):
        a = engine.marketplace_assessment("a1", "t1")
        assert a.assessment_id == "a1"
        assert a.tenant_id == "t1"
        assert a.total_offerings == 0
        assert a.active_offerings == 0
        assert a.coverage_score == 0.0

    def test_duplicate_raises(self, engine):
        engine.marketplace_assessment("a1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.marketplace_assessment("a1", "t1")

    def test_coverage_all_active(self, engine):
        _active_off(engine, "o1", tid="t1")
        _active_off(engine, "o2", tid="t1")
        a = engine.marketplace_assessment("a1", "t1")
        assert a.total_offerings == 2
        assert a.active_offerings == 2
        assert a.coverage_score == 1.0

    def test_coverage_partial(self, engine):
        _active_off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t1")  # draft
        a = engine.marketplace_assessment("a1", "t1")
        assert a.total_offerings == 2
        assert a.active_offerings == 1
        assert a.coverage_score == 0.5

    def test_coverage_none_active(self, engine):
        _off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t1")
        a = engine.marketplace_assessment("a1", "t1")
        assert a.coverage_score == 0.0

    def test_counts_listings(self, engine):
        _off(engine, "o1", tid="t1")
        engine.create_listing("l1", "o1", "t1")
        engine.create_listing("l2", "o1", "t1")
        engine.deactivate_listing("l2")
        a = engine.marketplace_assessment("a1", "t1")
        assert a.total_listings == 2
        assert a.active_listings == 1

    def test_counts_packages(self, engine):
        _pkg(engine, "pk1", tid="t1")
        _pkg(engine, "pk2", tid="t1")
        a = engine.marketplace_assessment("a1", "t1")
        assert a.total_packages == 2

    def test_filters_by_tenant(self, engine):
        _active_off(engine, "o1", tid="t1")
        _active_off(engine, "o2", tid="t2")
        a = engine.marketplace_assessment("a1", "t1")
        assert a.total_offerings == 1

    def test_increments_count(self, engine):
        engine.marketplace_assessment("a1", "t1")
        assert engine.assessment_count == 1

    def test_has_assessed_at(self, engine):
        a = engine.marketplace_assessment("a1", "t1")
        assert a.assessed_at != ""


# ===========================================================================
# 21. MARKETPLACE SNAPSHOT
# ===========================================================================


class TestMarketplaceSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.marketplace_snapshot("s1")
        assert snap.snapshot_id == "s1"
        assert snap.total_offerings == 0
        assert snap.total_packages == 0
        assert snap.total_bundles == 0
        assert snap.total_listings == 0
        assert snap.total_eligibility_rules == 0
        assert snap.total_pricing_bindings == 0
        assert snap.total_assessments == 0
        assert snap.total_violations == 0

    def test_populated_snapshot(self, engine):
        _active_off(engine, "o1")
        _pkg(engine)
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        engine.create_listing("l1", "o1", "t1")
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        engine.marketplace_assessment("a1", "t1")
        snap = engine.marketplace_snapshot("s1")
        assert snap.total_offerings == 1
        assert snap.total_packages == 1
        assert snap.total_bundles == 1
        assert snap.total_listings == 1
        assert snap.total_eligibility_rules == 1
        assert snap.total_pricing_bindings == 1
        assert snap.total_assessments == 1

    def test_has_captured_at(self, engine):
        snap = engine.marketplace_snapshot("s1")
        assert snap.captured_at != ""

    def test_snapshot_is_frozen(self, engine):
        snap = engine.marketplace_snapshot("s1")
        with pytest.raises(AttributeError):
            snap.total_offerings = 99

    def test_multiple_snapshots_independent(self, engine):
        s1 = engine.marketplace_snapshot("s1")
        _off(engine)
        s2 = engine.marketplace_snapshot("s2")
        assert s1.total_offerings == 0
        assert s2.total_offerings == 1


# ===========================================================================
# 22. DETECT MARKETPLACE VIOLATIONS
# ===========================================================================


class TestDetectMarketplaceViolations:
    def test_no_violations(self, engine):
        _active_off(engine)
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        result = engine.detect_marketplace_violations("t1")
        assert len(result) == 0

    def test_no_pricing_violation(self, engine):
        _active_off(engine)
        result = engine.detect_marketplace_violations("t1")
        assert len(result) == 1
        assert result[0].operation == "no_pricing"

    def test_invalid_bundle_expired_violation(self, engine):
        _off(engine, "o1")
        engine.retire_offering("o1")
        _pkg(engine)
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        result = engine.detect_marketplace_violations("t1")
        violations = [v for v in result if v.operation == "invalid_bundle"]
        assert len(violations) == 1

    def test_listing_inactive_offering_violation(self, engine):
        _off(engine, "o1")
        engine.create_listing("l1", "o1", "t1")
        # offering is DRAFT, listing is active => violation
        result = engine.detect_marketplace_violations("t1")
        violations = [v for v in result if v.operation == "listing_inactive_offering"]
        assert len(violations) == 1

    def test_idempotent(self, engine):
        _active_off(engine)
        r1 = engine.detect_marketplace_violations("t1")
        assert len(r1) == 1
        # Second call returns empty — violations already stored
        r2 = engine.detect_marketplace_violations("t1")
        assert len(r2) == 0
        # But total stored count stays the same
        total = engine.violation_count
        engine.detect_marketplace_violations("t1")
        assert engine.violation_count == total

    def test_violation_has_fields(self, engine):
        _active_off(engine)
        result = engine.detect_marketplace_violations("t1")
        assert result[0].tenant_id == "t1"
        assert result[0].detected_at != ""
        assert result[0].reason != ""

    def test_no_violations_for_other_tenant(self, engine):
        _active_off(engine, "o1", tid="t1")
        result = engine.detect_marketplace_violations("t2")
        assert len(result) == 0

    def test_draft_offering_no_pricing_no_violation(self, engine):
        _off(engine, "o1")  # draft, not active
        result = engine.detect_marketplace_violations("t1")
        pricing_violations = [v for v in result if v.operation == "no_pricing"]
        assert len(pricing_violations) == 0

    def test_suspended_offering_no_pricing_no_violation(self, engine):
        _off(engine, "o1")
        engine.suspend_offering("o1")
        result = engine.detect_marketplace_violations("t1")
        pricing_violations = [v for v in result if v.operation == "no_pricing"]
        assert len(pricing_violations) == 0

    def test_listing_on_active_offering_no_violation(self, engine):
        _active_off(engine, "o1")
        engine.create_listing("l1", "o1", "t1")
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        result = engine.detect_marketplace_violations("t1")
        listing_violations = [v for v in result if v.operation == "listing_inactive_offering"]
        assert len(listing_violations) == 0

    def test_deactivated_listing_no_violation(self, engine):
        _off(engine, "o1")
        engine.create_listing("l1", "o1", "t1")
        engine.deactivate_listing("l1")
        result = engine.detect_marketplace_violations("t1")
        listing_violations = [v for v in result if v.operation == "listing_inactive_offering"]
        assert len(listing_violations) == 0

    def test_multiple_violation_types(self, engine):
        _active_off(engine, "o1")
        # no pricing on o1 => no_pricing
        _off(engine, "o2")
        engine.retire_offering("o2")
        _pkg(engine)
        engine.add_to_bundle("b1", "pk1", "o2", "t1")
        # expired bundle => invalid_bundle
        result = engine.detect_marketplace_violations("t1")
        operations = {v.operation for v in result}
        assert "no_pricing" in operations
        assert "invalid_bundle" in operations


# ===========================================================================
# 23. VIOLATIONS FOR TENANT
# ===========================================================================


class TestViolationsForTenant:
    def test_empty(self, engine):
        assert engine.violations_for_tenant("t1") == ()

    def test_after_detection(self, engine):
        _active_off(engine)
        engine.detect_marketplace_violations("t1")
        result = engine.violations_for_tenant("t1")
        assert len(result) >= 1

    def test_filters_by_tenant(self, engine):
        _active_off(engine, "o1", tid="t1")
        _active_off(engine, "o2", tid="t2")
        engine.detect_marketplace_violations("t1")
        engine.detect_marketplace_violations("t2")
        t1_violations = engine.violations_for_tenant("t1")
        t2_violations = engine.violations_for_tenant("t2")
        for v in t1_violations:
            assert v.tenant_id == "t1"
        for v in t2_violations:
            assert v.tenant_id == "t2"

    def test_returns_tuple(self, engine):
        assert isinstance(engine.violations_for_tenant("t1"), tuple)


# ===========================================================================
# 24. CLOSURE REPORT
# ===========================================================================


class TestClosureReport:
    def test_empty_tenant(self, engine):
        report = engine.closure_report("cr1", "t1")
        assert report.report_id == "cr1"
        assert report.tenant_id == "t1"
        assert report.total_offerings == 0
        assert report.total_packages == 0
        assert report.total_bundles == 0
        assert report.total_listings == 0
        assert report.total_eligibility_rules == 0
        assert report.total_pricing_bindings == 0
        assert report.total_violations == 0

    def test_populated_tenant(self, engine):
        _active_off(engine, "o1")
        _pkg(engine)
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        engine.create_listing("l1", "o1", "t1")
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        engine.detect_marketplace_violations("t1")
        report = engine.closure_report("cr1", "t1")
        assert report.total_offerings == 1
        assert report.total_packages == 1
        assert report.total_bundles == 1
        assert report.total_listings == 1
        assert report.total_eligibility_rules == 1
        assert report.total_pricing_bindings == 1

    def test_filters_by_tenant(self, engine):
        _off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t2")
        r1 = engine.closure_report("cr1", "t1")
        r2 = engine.closure_report("cr2", "t2")
        assert r1.total_offerings == 1
        assert r2.total_offerings == 1

    def test_has_closed_at(self, engine):
        report = engine.closure_report("cr1", "t1")
        assert report.closed_at != ""

    def test_frozen(self, engine):
        report = engine.closure_report("cr1", "t1")
        with pytest.raises(AttributeError):
            report.total_offerings = 99


# ===========================================================================
# 25. STATE HASH
# ===========================================================================


class TestStateHash:
    def test_empty_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA256 hex

    def test_changes_after_offering(self, engine):
        h1 = engine.state_hash()
        _off(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_package(self, engine):
        h1 = engine.state_hash()
        _pkg(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_bundle(self, engine):
        _off(engine)
        _pkg(engine)
        h1 = engine.state_hash()
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_listing(self, engine):
        _off(engine)
        h1 = engine.state_hash()
        engine.create_listing("l1", "o1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_eligibility(self, engine):
        _off(engine)
        h1 = engine.state_hash()
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_pricing(self, engine):
        _off(engine)
        h1 = engine.state_hash()
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_assessment(self, engine):
        h1 = engine.state_hash()
        engine.marketplace_assessment("a1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_violation(self, engine):
        _active_off(engine)
        h1 = engine.state_hash()
        engine.detect_marketplace_violations("t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_deterministic(self, engine):
        _off(engine)
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_same_data_same_hash(self, spine):
        e1 = MarketplaceRuntimeEngine(spine)
        e2 = MarketplaceRuntimeEngine(EventSpineEngine())
        _off(e1, "o1")
        _off(e2, "o1")
        assert e1.state_hash() == e2.state_hash()


# ===========================================================================
# 26. PROPERTIES
# ===========================================================================


class TestProperties:
    def test_offering_count(self, engine):
        assert engine.offering_count == 0
        _off(engine, "o1")
        assert engine.offering_count == 1
        _off(engine, "o2")
        assert engine.offering_count == 2

    def test_package_count(self, engine):
        assert engine.package_count == 0
        _pkg(engine, "pk1")
        assert engine.package_count == 1

    def test_bundle_count(self, engine):
        _off(engine)
        _pkg(engine)
        assert engine.bundle_count == 0
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert engine.bundle_count == 1

    def test_listing_count(self, engine):
        _off(engine)
        assert engine.listing_count == 0
        engine.create_listing("l1", "o1", "t1")
        assert engine.listing_count == 1

    def test_eligibility_rule_count(self, engine):
        _off(engine)
        assert engine.eligibility_rule_count == 0
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        assert engine.eligibility_rule_count == 1

    def test_pricing_binding_count(self, engine):
        _off(engine)
        assert engine.pricing_binding_count == 0
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        assert engine.pricing_binding_count == 1

    def test_assessment_count(self, engine):
        assert engine.assessment_count == 0
        engine.marketplace_assessment("a1", "t1")
        assert engine.assessment_count == 1

    def test_violation_count(self, engine):
        assert engine.violation_count == 0
        _active_off(engine)
        engine.detect_marketplace_violations("t1")
        assert engine.violation_count >= 1


# ===========================================================================
# 27. OFFERING LIFECYCLE TRANSITIONS
# ===========================================================================


class TestOfferingLifecycle:
    def test_draft_to_active(self, engine):
        _off(engine)
        rec = engine.activate_offering("o1")
        assert rec.status == OfferingStatus.ACTIVE

    def test_draft_to_suspended(self, engine):
        _off(engine)
        rec = engine.suspend_offering("o1")
        assert rec.status == OfferingStatus.SUSPENDED

    def test_draft_to_retired(self, engine):
        _off(engine)
        rec = engine.retire_offering("o1")
        assert rec.status == OfferingStatus.RETIRED

    def test_active_to_suspended(self, engine):
        _active_off(engine)
        rec = engine.suspend_offering("o1")
        assert rec.status == OfferingStatus.SUSPENDED

    def test_active_to_retired(self, engine):
        _active_off(engine)
        rec = engine.retire_offering("o1")
        assert rec.status == OfferingStatus.RETIRED

    def test_suspended_to_active(self, engine):
        _off(engine)
        engine.suspend_offering("o1")
        rec = engine.activate_offering("o1")
        assert rec.status == OfferingStatus.ACTIVE

    def test_suspended_to_retired(self, engine):
        _off(engine)
        engine.suspend_offering("o1")
        rec = engine.retire_offering("o1")
        assert rec.status == OfferingStatus.RETIRED

    def test_retired_to_active_blocked(self, engine):
        _off(engine)
        engine.retire_offering("o1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.activate_offering("o1")

    def test_retired_to_suspended_blocked(self, engine):
        _off(engine)
        engine.retire_offering("o1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.suspend_offering("o1")

    def test_retired_to_retired_blocked(self, engine):
        _off(engine)
        engine.retire_offering("o1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.retire_offering("o1")

    def test_full_lifecycle(self, engine):
        _off(engine)
        engine.activate_offering("o1")
        engine.suspend_offering("o1")
        engine.activate_offering("o1")
        rec = engine.retire_offering("o1")
        assert rec.status == OfferingStatus.RETIRED


# ===========================================================================
# GOLDEN SCENARIOS
# ===========================================================================


class TestGoldenProductRelease:
    """Golden 1: Product release creates eligible offering."""

    def test_product_release_full_flow(self, engine):
        # Register offering for a product
        rec = engine.register_offering("o1", "product-A", "tenant-1", "Product A Standard")
        assert rec.status == OfferingStatus.DRAFT

        # Activate the offering
        active = engine.activate_offering("o1")
        assert active.status == OfferingStatus.ACTIVE

        # Evaluate eligibility (entitled)
        elig = engine.evaluate_eligibility("e1", "o1", "tenant-1", "enterprise")
        assert elig.status == EligibilityStatus.ELIGIBLE

        # Bind pricing
        pricing = engine.bind_pricing("bp1", "o1", "tenant-1", 500.0)
        assert pricing.effective_price == 500.0

        # Create listing
        listing = engine.create_listing("l1", "o1", "tenant-1")
        assert listing.active is True

        # Assessment should show full coverage
        assessment = engine.marketplace_assessment("a1", "tenant-1")
        assert assessment.coverage_score == 1.0
        assert assessment.active_offerings == 1

        # No violations
        violations = engine.detect_marketplace_violations("tenant-1")
        assert len(violations) == 0

    def test_release_with_version_ref(self, engine):
        rec = engine.register_offering("o1", "product-A", "t1", "v2 Release",
                                        version_ref="2.0.0")
        assert rec.version_ref == "2.0.0"
        engine.activate_offering("o1")
        elig = engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        assert elig.status == EligibilityStatus.ELIGIBLE

    def test_multiple_offerings_same_product(self, engine):
        engine.register_offering("o1", "product-A", "t1", "Standard")
        engine.register_offering("o2", "product-A", "t1", "Premium",
                                  kind=OfferingKind.ADD_ON)
        result = engine.offerings_for_product("product-A")
        assert len(result) == 2


class TestGoldenNoEntitlement:
    """Golden 2: Account without entitlement is blocked."""

    def test_ineligible_account(self, engine):
        engine.register_offering("o1", "p1", "t1", "Premium Offering")
        engine.activate_offering("o1")
        elig = engine.evaluate_eligibility("e1", "o1", "t1", "free-tier",
                                            has_entitlement=False)
        assert elig.status == EligibilityStatus.INELIGIBLE
        assert elig.reason == "no entitlement"

    def test_mixed_entitlements(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        e1 = engine.evaluate_eligibility("e1", "o1", "t1", "enterprise",
                                          has_entitlement=True)
        e2 = engine.evaluate_eligibility("e2", "o1", "t1", "free-tier",
                                          has_entitlement=False)
        assert e1.status == EligibilityStatus.ELIGIBLE
        assert e2.status == EligibilityStatus.INELIGIBLE

    def test_segment_recorded(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        elig = engine.evaluate_eligibility("e1", "o1", "t1", "startup",
                                            has_entitlement=False)
        assert elig.account_segment == "startup"


class TestGoldenPartnerChannel:
    """Golden 3: Partner channel creates marketplace listing."""

    def test_partner_listing(self, engine):
        engine.register_offering("o1", "p1", "t1", "Partner Offering")
        engine.activate_offering("o1")
        listing = engine.create_listing("l1", "o1", "t1", MarketplaceChannel.PARTNER)
        assert listing.channel == MarketplaceChannel.PARTNER
        assert listing.active is True

    def test_multiple_channels_same_offering(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering")
        engine.create_listing("l1", "o1", "t1", MarketplaceChannel.DIRECT)
        engine.create_listing("l2", "o1", "t1", MarketplaceChannel.PARTNER)
        engine.create_listing("l3", "o1", "t1", MarketplaceChannel.MARKETPLACE)
        result = engine.listings_for_offering("o1")
        assert len(result) == 3
        channels = {r.channel for r in result}
        assert channels == {MarketplaceChannel.DIRECT, MarketplaceChannel.PARTNER,
                            MarketplaceChannel.MARKETPLACE}

    def test_deactivate_partner_listing(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering")
        engine.create_listing("l1", "o1", "t1", MarketplaceChannel.PARTNER)
        rec = engine.deactivate_listing("l1")
        assert rec.active is False
        assert len(engine.active_listings("t1")) == 0


class TestGoldenInvalidBundle:
    """Golden 4: Invalid bundle composition creates violation."""

    def test_retired_offering_bundle_violation(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        engine.retire_offering("o1")
        engine.register_package("pk1", "t1", "Package-1")
        bundle = engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert bundle.disposition == BundleDisposition.EXPIRED

        violations = engine.detect_marketplace_violations("t1")
        ops = {v.operation for v in violations}
        assert "invalid_bundle" in ops

    def test_suspended_offering_partial_bundle(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        engine.suspend_offering("o1")
        engine.register_package("pk1", "t1", "Package-1")
        bundle = engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert bundle.disposition == BundleDisposition.PARTIAL
        # PARTIAL is not EXPIRED or INVALID => no violation
        violations = engine.detect_marketplace_violations("t1")
        bundle_violations = [v for v in violations if v.operation == "invalid_bundle"]
        assert len(bundle_violations) == 0

    def test_mixed_bundle_composition(self, engine):
        engine.register_offering("o1", "p1", "t1", "Active Offering")
        engine.activate_offering("o1")
        engine.register_offering("o2", "p1", "t1", "Retired Offering")
        engine.retire_offering("o2")
        engine.register_package("pk1", "t1", "Mixed Package")
        b1 = engine.add_to_bundle("b1", "pk1", "o1", "t1")
        b2 = engine.add_to_bundle("b2", "pk1", "o2", "t1")
        assert b1.disposition == BundleDisposition.VALID
        assert b2.disposition == BundleDisposition.EXPIRED

    def test_bundle_violation_persists_in_tenant_violations(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        engine.retire_offering("o1")
        engine.register_package("pk1", "t1", "Package-1")
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        engine.detect_marketplace_violations("t1")
        tenant_violations = engine.violations_for_tenant("t1")
        ops = {v.operation for v in tenant_violations}
        assert "invalid_bundle" in ops


class TestGoldenPricingBinding:
    """Golden 5: Pricing binding links to billing contract terms."""

    def test_pricing_with_contract(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        binding = engine.bind_pricing("bp1", "o1", "t1", 1000.0,
                                       effective_price=800.0,
                                       disposition=PricingDisposition.NEGOTIATED,
                                       contract_ref="CTR-2026-001")
        assert binding.base_price == 1000.0
        assert binding.effective_price == 800.0
        assert binding.disposition == PricingDisposition.NEGOTIATED
        assert binding.contract_ref == "CTR-2026-001"

    def test_discounted_pricing(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        binding = engine.bind_pricing("bp1", "o1", "t1", 200.0,
                                       effective_price=150.0,
                                       disposition=PricingDisposition.DISCOUNTED)
        assert binding.base_price == 200.0
        assert binding.effective_price == 150.0

    def test_promotional_pricing(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        binding = engine.bind_pricing("bp1", "o1", "t1", 300.0,
                                       effective_price=0.01,
                                       disposition=PricingDisposition.PROMOTIONAL)
        assert binding.disposition == PricingDisposition.PROMOTIONAL
        assert binding.effective_price == 0.01

    def test_multiple_pricing_bindings(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        engine.bind_pricing("bp1", "o1", "t1", 100.0, contract_ref="CTR-A")
        engine.bind_pricing("bp2", "o1", "t1", 200.0, contract_ref="CTR-B")
        result = engine.pricing_for_offering("o1")
        assert len(result) == 2
        refs = {r.contract_ref for r in result}
        assert refs == {"CTR-A", "CTR-B"}


class TestGoldenReplayRestore:
    """Golden 6: Replay/restore preserves offering and listing state."""

    def test_state_hash_consistency(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        engine.activate_offering("o1")
        engine.create_listing("l1", "o1", "t1")
        h1 = engine.state_hash()

        # Rebuild in new engine
        spine2 = EventSpineEngine()
        engine2 = MarketplaceRuntimeEngine(spine2)
        engine2.register_offering("o1", "p1", "t1", "Offering-1")
        engine2.activate_offering("o1")
        engine2.create_listing("l1", "o1", "t1")
        h2 = engine2.state_hash()

        assert h1 == h2

    def test_snapshot_before_and_after(self, engine):
        s1 = engine.marketplace_snapshot("s1")
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        engine.activate_offering("o1")
        engine.create_listing("l1", "o1", "t1")
        s2 = engine.marketplace_snapshot("s2")
        assert s1.total_offerings == 0
        assert s2.total_offerings == 1
        assert s2.total_listings == 1

    def test_closure_report_captures_full_state(self, engine):
        engine.register_offering("o1", "p1", "t1", "Offering-1")
        engine.activate_offering("o1")
        engine.register_package("pk1", "t1", "Package-1")
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        engine.create_listing("l1", "o1", "t1")
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        report = engine.closure_report("cr1", "t1")
        assert report.total_offerings == 1
        assert report.total_packages == 1
        assert report.total_bundles == 1
        assert report.total_listings == 1
        assert report.total_eligibility_rules == 1
        assert report.total_pricing_bindings == 1

    def test_replay_hash_across_operations(self, engine):
        engine.register_offering("o1", "p1", "t1", "O1")
        engine.register_offering("o2", "p1", "t1", "O2")
        engine.activate_offering("o1")
        engine.register_package("pk1", "t1", "P1")
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        engine.marketplace_assessment("a1", "t1")
        h1 = engine.state_hash()

        spine2 = EventSpineEngine()
        e2 = MarketplaceRuntimeEngine(spine2)
        e2.register_offering("o1", "p1", "t1", "O1")
        e2.register_offering("o2", "p1", "t1", "O2")
        e2.activate_offering("o1")
        e2.register_package("pk1", "t1", "P1")
        e2.add_to_bundle("b1", "pk1", "o1", "t1")
        e2.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        e2.bind_pricing("bp1", "o1", "t1", 100.0)
        e2.marketplace_assessment("a1", "t1")
        h2 = e2.state_hash()

        assert h1 == h2


# ===========================================================================
# 28. EDGE CASES AND CROSS-CUTTING
# ===========================================================================


class TestEdgeCases:
    def test_listing_on_suspended_then_detect(self, engine):
        """Active listing on suspended offering => violation."""
        _off(engine, "o1")
        engine.create_listing("l1", "o1", "t1")
        engine.suspend_offering("o1")
        violations = engine.detect_marketplace_violations("t1")
        listing_violations = [v for v in violations if v.operation == "listing_inactive_offering"]
        assert len(listing_violations) == 1

    def test_many_offerings(self, engine):
        for i in range(50):
            _off(engine, f"o{i}", pid=f"p{i}")
        assert engine.offering_count == 50

    def test_many_packages(self, engine):
        for i in range(20):
            _pkg(engine, f"pk{i}")
        assert engine.package_count == 20

    def test_assessment_coverage_rounding(self, engine):
        _active_off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t1")
        _off(engine, "o3", tid="t1")
        a = engine.marketplace_assessment("a1", "t1")
        assert a.coverage_score == round(1 / 3, 4)

    def test_snapshot_includes_violations(self, engine):
        _active_off(engine)
        engine.detect_marketplace_violations("t1")
        snap = engine.marketplace_snapshot("s1")
        assert snap.total_violations >= 1

    def test_closure_report_includes_violations(self, engine):
        _active_off(engine)
        engine.detect_marketplace_violations("t1")
        report = engine.closure_report("cr1", "t1")
        assert report.total_violations >= 1

    def test_empty_version_ref_becomes_latest(self, engine):
        rec = engine.register_offering("o1", "p1", "t1", "Name", version_ref="")
        assert rec.version_ref == "latest"

    def test_empty_contract_ref_becomes_none(self, engine):
        _off(engine)
        rec = engine.bind_pricing("bp1", "o1", "t1", 10.0, contract_ref="")
        assert rec.contract_ref == "none"

    def test_listing_deactivated_not_in_active_listings(self, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        engine.create_listing("l2", "o1", "t1")
        engine.deactivate_listing("l1")
        active = engine.active_listings("t1")
        assert len(active) == 1
        assert active[0].listing_id == "l2"

    def test_bundle_increments_package_count_correctly(self, engine):
        _off(engine, "o1")
        _off(engine, "o2")
        _off(engine, "o3")
        _pkg(engine)
        for i, oid in enumerate(["o1", "o2", "o3"]):
            engine.add_to_bundle(f"b{i}", "pk1", oid, "t1")
        assert engine.get_package("pk1").offering_count == 3

    def test_offerings_for_tenant_after_status_changes(self, engine):
        _off(engine, "o1", tid="t1")
        engine.activate_offering("o1")
        engine.suspend_offering("o1")
        result = engine.offerings_for_tenant("t1")
        assert len(result) == 1
        assert result[0].status == OfferingStatus.SUSPENDED

    def test_detect_violations_listing_on_draft(self, engine):
        """Active listing on DRAFT offering is a violation."""
        _off(engine, "o1")
        engine.create_listing("l1", "o1", "t1")
        violations = engine.detect_marketplace_violations("t1")
        ops = {v.operation for v in violations}
        assert "listing_inactive_offering" in ops

    def test_no_pricing_violation_only_for_active(self, engine):
        """Only ACTIVE offerings trigger no_pricing violation."""
        _off(engine, "o1")  # DRAFT
        _off(engine, "o2")
        engine.suspend_offering("o2")
        violations = engine.detect_marketplace_violations("t1")
        no_pricing = [v for v in violations if v.operation == "no_pricing"]
        assert len(no_pricing) == 0

    def test_multiple_tenants_independent(self, engine):
        _active_off(engine, "o1", tid="t1")
        _active_off(engine, "o2", tid="t2")
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        # t1 has pricing, t2 does not
        v1 = engine.detect_marketplace_violations("t1")
        v2 = engine.detect_marketplace_violations("t2")
        no_pricing_t1 = [v for v in v1 if v.operation == "no_pricing"]
        no_pricing_t2 = [v for v in v2 if v.operation == "no_pricing"]
        assert len(no_pricing_t1) == 0
        assert len(no_pricing_t2) == 1


class TestEventEmission:
    """Verify that operations emit events to the spine."""

    def test_register_offering_emits(self, spine, engine):
        initial = len(spine._events)
        _off(engine)
        assert len(spine._events) > initial

    def test_activate_offering_emits(self, spine, engine):
        _off(engine)
        initial = len(spine._events)
        engine.activate_offering("o1")
        assert len(spine._events) > initial

    def test_suspend_offering_emits(self, spine, engine):
        _off(engine)
        initial = len(spine._events)
        engine.suspend_offering("o1")
        assert len(spine._events) > initial

    def test_retire_offering_emits(self, spine, engine):
        _off(engine)
        initial = len(spine._events)
        engine.retire_offering("o1")
        assert len(spine._events) > initial

    def test_register_package_emits(self, spine, engine):
        initial = len(spine._events)
        _pkg(engine)
        assert len(spine._events) > initial

    def test_add_to_bundle_emits(self, spine, engine):
        _off(engine)
        _pkg(engine)
        initial = len(spine._events)
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        assert len(spine._events) > initial

    def test_create_listing_emits(self, spine, engine):
        _off(engine)
        initial = len(spine._events)
        engine.create_listing("l1", "o1", "t1")
        assert len(spine._events) > initial

    def test_deactivate_listing_emits(self, spine, engine):
        _off(engine)
        engine.create_listing("l1", "o1", "t1")
        initial = len(spine._events)
        engine.deactivate_listing("l1")
        assert len(spine._events) > initial

    def test_evaluate_eligibility_emits(self, spine, engine):
        _off(engine)
        initial = len(spine._events)
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        assert len(spine._events) > initial

    def test_bind_pricing_emits(self, spine, engine):
        _off(engine)
        initial = len(spine._events)
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        assert len(spine._events) > initial

    def test_marketplace_assessment_emits(self, spine, engine):
        initial = len(spine._events)
        engine.marketplace_assessment("a1", "t1")
        assert len(spine._events) > initial

    def test_detect_violations_emits(self, spine, engine):
        initial = len(spine._events)
        engine.detect_marketplace_violations("t1")
        assert len(spine._events) > initial


# ===========================================================================
# 29. MULTI-TENANT SCENARIOS
# ===========================================================================


class TestMultiTenant:
    def test_offerings_isolated(self, engine):
        _off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t2")
        assert len(engine.offerings_for_tenant("t1")) == 1
        assert len(engine.offerings_for_tenant("t2")) == 1

    def test_packages_isolated(self, engine):
        _pkg(engine, "pk1", tid="t1")
        _pkg(engine, "pk2", tid="t2")
        assert len(engine.packages_for_tenant("t1")) == 1
        assert len(engine.packages_for_tenant("t2")) == 1

    def test_listings_isolated(self, engine):
        _off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t2")
        engine.create_listing("l1", "o1", "t1")
        engine.create_listing("l2", "o2", "t2")
        assert len(engine.active_listings("t1")) == 1
        assert len(engine.active_listings("t2")) == 1

    def test_assessments_isolated(self, engine):
        _active_off(engine, "o1", tid="t1")
        _active_off(engine, "o2", tid="t2")
        a1 = engine.marketplace_assessment("a1", "t1")
        a2 = engine.marketplace_assessment("a2", "t2")
        assert a1.total_offerings == 1
        assert a2.total_offerings == 1

    def test_violations_isolated(self, engine):
        _active_off(engine, "o1", tid="t1")
        _active_off(engine, "o2", tid="t2")
        engine.bind_pricing("bp1", "o1", "t1", 100.0)
        engine.detect_marketplace_violations("t1")
        engine.detect_marketplace_violations("t2")
        assert len(engine.violations_for_tenant("t1")) == 0
        assert len(engine.violations_for_tenant("t2")) >= 1

    def test_closure_reports_isolated(self, engine):
        _off(engine, "o1", tid="t1")
        _off(engine, "o2", tid="t2")
        _off(engine, "o3", tid="t2")
        r1 = engine.closure_report("cr1", "t1")
        r2 = engine.closure_report("cr2", "t2")
        assert r1.total_offerings == 1
        assert r2.total_offerings == 2


# ===========================================================================
# 30. COMPREHENSIVE END-TO-END
# ===========================================================================


class TestEndToEnd:
    def test_full_marketplace_lifecycle(self, engine):
        # 1. Register multiple offerings
        engine.register_offering("o1", "p1", "t1", "Standard Plan")
        engine.register_offering("o2", "p1", "t1", "Premium Plan", kind=OfferingKind.ADD_ON)
        engine.register_offering("o3", "p2", "t1", "Enterprise Plan", kind=OfferingKind.BUNDLE)
        assert engine.offering_count == 3

        # 2. Activate two, leave one draft
        engine.activate_offering("o1")
        engine.activate_offering("o2")

        # 3. Create packages and bundles
        engine.register_package("pk1", "t1", "Starter Bundle")
        engine.add_to_bundle("b1", "pk1", "o1", "t1")
        engine.add_to_bundle("b2", "pk1", "o2", "t1")
        assert engine.get_package("pk1").offering_count == 2

        # 4. Create listings
        engine.create_listing("l1", "o1", "t1", MarketplaceChannel.DIRECT)
        engine.create_listing("l2", "o2", "t1", MarketplaceChannel.PARTNER)
        assert len(engine.active_listings("t1")) == 2

        # 5. Evaluate eligibility
        engine.evaluate_eligibility("e1", "o1", "t1", "enterprise")
        engine.evaluate_eligibility("e2", "o2", "t1", "enterprise")
        engine.evaluate_eligibility("e3", "o1", "t1", "free-tier", has_entitlement=False)
        assert engine.eligibility_rule_count == 3

        # 6. Bind pricing
        engine.bind_pricing("bp1", "o1", "t1", 100.0, contract_ref="CTR-001")
        engine.bind_pricing("bp2", "o2", "t1", 500.0, effective_price=400.0,
                            disposition=PricingDisposition.NEGOTIATED,
                            contract_ref="CTR-002")
        assert engine.pricing_binding_count == 2

        # 7. Assessment
        assessment = engine.marketplace_assessment("a1", "t1")
        assert assessment.total_offerings == 3
        assert assessment.active_offerings == 2
        assert assessment.coverage_score == round(2 / 3, 4)

        # 8. Snapshot
        snap = engine.marketplace_snapshot("s1")
        assert snap.total_offerings == 3
        assert snap.total_packages == 1
        assert snap.total_bundles == 2
        assert snap.total_listings == 2
        assert snap.total_eligibility_rules == 3
        assert snap.total_pricing_bindings == 2

        # 9. Violations -- o3 is draft with listing? No listing on o3.
        # Active offerings o1, o2 both have pricing => no no_pricing violation
        violations = engine.detect_marketplace_violations("t1")
        no_pricing = [v for v in violations if v.operation == "no_pricing"]
        assert len(no_pricing) == 0

        # 10. Suspend o2, check violation for listing on inactive
        engine.suspend_offering("o2")
        violations2 = engine.detect_marketplace_violations("t1")
        listing_inactive = [v for v in violations2 if v.operation == "listing_inactive_offering"]
        assert len(listing_inactive) == 1

        # 11. Deactivate listing l2
        engine.deactivate_listing("l2")
        assert len(engine.active_listings("t1")) == 1

        # 12. Retire o2
        engine.retire_offering("o2")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.activate_offering("o2")

        # 13. Closure report
        report = engine.closure_report("cr1", "t1")
        assert report.total_offerings == 3
        assert report.total_packages == 1
        assert report.total_bundles == 2
        assert report.total_listings == 2
        assert report.total_eligibility_rules == 3
        assert report.total_pricing_bindings == 2

        # 14. State hash is deterministic
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_rapid_scaling(self, engine):
        """Scale test: 100 offerings, packages, bundles."""
        for i in range(100):
            engine.register_offering(f"o{i}", f"p{i}", "t1", f"Offering-{i}")
        assert engine.offering_count == 100

        for i in range(100):
            engine.activate_offering(f"o{i}")

        for i in range(50):
            engine.register_package(f"pk{i}", "t1", f"Package-{i}")

        for i in range(50):
            engine.add_to_bundle(f"b{i}", f"pk{i % 50}", f"o{i}", "t1")
        assert engine.bundle_count == 50

        snap = engine.marketplace_snapshot("s1")
        assert snap.total_offerings == 100
        assert snap.total_packages == 50
        assert snap.total_bundles == 50

        h = engine.state_hash()
        assert len(h) == 64


class TestBoundedContracts:
    def test_duplicate_offering_message_hides_offering_id(self, engine):
        _off(engine, "offering-secret")
        with pytest.raises(RuntimeCoreInvariantError, match="offering already registered") as exc_info:
            _off(engine, "offering-secret")
        assert "offering-secret" not in str(exc_info.value)

    def test_marketplace_violation_reasons_hide_ids_and_statuses(self, engine):
        _off(engine, "offering-noprice")
        engine.activate_offering("offering-noprice")
        _off(engine, "offering-secret")
        engine.activate_offering("offering-secret")
        _off(engine, "offering-bundle-secret")
        engine.retire_offering("offering-bundle-secret")
        _pkg(engine, "package-secret")
        engine.add_to_bundle("bundle-secret", "package-secret", "offering-bundle-secret", "t1")
        engine.create_listing("listing-secret", "offering-secret", "t1")
        engine.retire_offering("offering-secret")
        violations = engine.detect_marketplace_violations("t1")
        assert any(v.reason == "active offering has no pricing binding" for v in violations)
        assert any(v.reason == "bundle has invalid disposition" for v in violations)
        assert any(v.reason == "listing is active on non-active offering" for v in violations)
        for violation in violations:
            assert "offering-secret" not in violation.reason
            assert "bundle-secret" not in violation.reason
            assert "listing-secret" not in violation.reason
            assert "RETIRED" not in violation.reason
