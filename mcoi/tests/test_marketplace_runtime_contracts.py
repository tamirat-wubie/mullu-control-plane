"""Tests for marketplace runtime contracts."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.marketplace_runtime import (
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-07-01T09:00:00+00:00"
NOW_ISO = datetime.now(timezone.utc).isoformat()


def _offering(**ov) -> OfferingRecord:
    d = dict(
        offering_id="off-001",
        product_id="prod-001",
        tenant_id="t-001",
        display_name="Widget Pro",
        kind=OfferingKind.STANDALONE,
        status=OfferingStatus.DRAFT,
        version_ref="v1.0",
        created_at=TS,
    )
    d.update(ov)
    return OfferingRecord(**d)


def _package(**ov) -> PackageRecord:
    d = dict(
        package_id="pkg-001",
        tenant_id="t-001",
        display_name="Starter Pack",
        offering_count=3,
        status=OfferingStatus.ACTIVE,
        created_at=TS,
    )
    d.update(ov)
    return PackageRecord(**d)


def _bundle(**ov) -> BundleRecord:
    d = dict(
        bundle_id="bnd-001",
        package_id="pkg-001",
        offering_id="off-001",
        tenant_id="t-001",
        disposition=BundleDisposition.VALID,
        created_at=TS,
    )
    d.update(ov)
    return BundleRecord(**d)


def _listing(**ov) -> ListingRecord:
    d = dict(
        listing_id="lst-001",
        offering_id="off-001",
        tenant_id="t-001",
        channel=MarketplaceChannel.DIRECT,
        active=True,
        listed_at=TS,
    )
    d.update(ov)
    return ListingRecord(**d)


def _eligibility(**ov) -> EligibilityRule:
    d = dict(
        rule_id="rule-001",
        offering_id="off-001",
        tenant_id="t-001",
        account_segment="enterprise",
        status=EligibilityStatus.ELIGIBLE,
        reason="meets criteria",
        evaluated_at=TS,
    )
    d.update(ov)
    return EligibilityRule(**d)


def _pricing(**ov) -> PricingBinding:
    d = dict(
        binding_id="prc-001",
        offering_id="off-001",
        tenant_id="t-001",
        base_price=100.0,
        effective_price=80.0,
        disposition=PricingDisposition.STANDARD,
        contract_ref="ctr-001",
        created_at=TS,
    )
    d.update(ov)
    return PricingBinding(**d)


def _assessment(**ov) -> MarketplaceAssessment:
    d = dict(
        assessment_id="asmt-001",
        tenant_id="t-001",
        total_offerings=10,
        active_offerings=7,
        total_listings=15,
        active_listings=12,
        total_packages=3,
        coverage_score=0.85,
        assessed_at=TS,
    )
    d.update(ov)
    return MarketplaceAssessment(**d)


def _snapshot(**ov) -> MarketplaceSnapshot:
    d = dict(
        snapshot_id="snap-001",
        total_offerings=10,
        total_packages=3,
        total_bundles=5,
        total_listings=15,
        total_eligibility_rules=8,
        total_pricing_bindings=12,
        total_assessments=2,
        total_violations=1,
        captured_at=TS,
    )
    d.update(ov)
    return MarketplaceSnapshot(**d)


def _violation(**ov) -> MarketplaceViolation:
    d = dict(
        violation_id="vio-001",
        tenant_id="t-001",
        operation="publish",
        reason="missing approval",
        detected_at=TS,
    )
    d.update(ov)
    return MarketplaceViolation(**d)


def _closure(**ov) -> MarketplaceClosureReport:
    d = dict(
        report_id="rpt-001",
        tenant_id="t-001",
        total_offerings=10,
        total_packages=3,
        total_bundles=5,
        total_listings=15,
        total_eligibility_rules=8,
        total_pricing_bindings=12,
        total_violations=1,
        closed_at=TS,
    )
    d.update(ov)
    return MarketplaceClosureReport(**d)


# ===================================================================
# Enum tests
# ===================================================================


class TestOfferingStatus:
    def test_members(self):
        assert [e.name for e in OfferingStatus] == [
            "DRAFT", "ACTIVE", "SUSPENDED", "RETIRED",
        ]

    def test_values(self):
        assert [e.value for e in OfferingStatus] == [
            "draft", "active", "suspended", "retired",
        ]

    def test_count(self):
        assert len(OfferingStatus) == 4

    def test_lookup_by_value(self):
        assert OfferingStatus("draft") is OfferingStatus.DRAFT

    def test_lookup_by_name(self):
        assert OfferingStatus["ACTIVE"] is OfferingStatus.ACTIVE


class TestOfferingKind:
    def test_members(self):
        assert [e.name for e in OfferingKind] == [
            "STANDALONE", "BUNDLE", "ADD_ON", "TRIAL", "CUSTOM",
        ]

    def test_values(self):
        assert [e.value for e in OfferingKind] == [
            "standalone", "bundle", "add_on", "trial", "custom",
        ]

    def test_count(self):
        assert len(OfferingKind) == 5

    def test_lookup_by_value(self):
        assert OfferingKind("add_on") is OfferingKind.ADD_ON

    def test_lookup_by_name(self):
        assert OfferingKind["TRIAL"] is OfferingKind.TRIAL


class TestBundleDisposition:
    def test_members(self):
        assert [e.name for e in BundleDisposition] == [
            "VALID", "INVALID", "PARTIAL", "EXPIRED",
        ]

    def test_values(self):
        assert [e.value for e in BundleDisposition] == [
            "valid", "invalid", "partial", "expired",
        ]

    def test_count(self):
        assert len(BundleDisposition) == 4

    def test_lookup_by_value(self):
        assert BundleDisposition("partial") is BundleDisposition.PARTIAL

    def test_lookup_by_name(self):
        assert BundleDisposition["EXPIRED"] is BundleDisposition.EXPIRED


class TestEligibilityStatus:
    def test_members(self):
        assert [e.name for e in EligibilityStatus] == [
            "ELIGIBLE", "INELIGIBLE", "REQUIRES_APPROVAL", "EXPIRED",
        ]

    def test_values(self):
        assert [e.value for e in EligibilityStatus] == [
            "eligible", "ineligible", "requires_approval", "expired",
        ]

    def test_count(self):
        assert len(EligibilityStatus) == 4

    def test_lookup_by_value(self):
        assert EligibilityStatus("requires_approval") is EligibilityStatus.REQUIRES_APPROVAL

    def test_lookup_by_name(self):
        assert EligibilityStatus["INELIGIBLE"] is EligibilityStatus.INELIGIBLE


class TestMarketplaceChannel:
    def test_members(self):
        assert [e.name for e in MarketplaceChannel] == [
            "DIRECT", "PARTNER", "MARKETPLACE", "INTERNAL", "API",
        ]

    def test_values(self):
        assert [e.value for e in MarketplaceChannel] == [
            "direct", "partner", "marketplace", "internal", "api",
        ]

    def test_count(self):
        assert len(MarketplaceChannel) == 5

    def test_lookup_by_value(self):
        assert MarketplaceChannel("api") is MarketplaceChannel.API

    def test_lookup_by_name(self):
        assert MarketplaceChannel["INTERNAL"] is MarketplaceChannel.INTERNAL


class TestPricingDisposition:
    def test_members(self):
        assert [e.name for e in PricingDisposition] == [
            "STANDARD", "DISCOUNTED", "PROMOTIONAL", "NEGOTIATED",
        ]

    def test_values(self):
        assert [e.value for e in PricingDisposition] == [
            "standard", "discounted", "promotional", "negotiated",
        ]

    def test_count(self):
        assert len(PricingDisposition) == 4

    def test_lookup_by_value(self):
        assert PricingDisposition("negotiated") is PricingDisposition.NEGOTIATED

    def test_lookup_by_name(self):
        assert PricingDisposition["PROMOTIONAL"] is PricingDisposition.PROMOTIONAL


# ===================================================================
# OfferingRecord
# ===================================================================


class TestOfferingRecord:
    def test_valid_construction(self):
        rec = _offering()
        assert rec.offering_id == "off-001"
        assert rec.product_id == "prod-001"
        assert rec.tenant_id == "t-001"
        assert rec.display_name == "Widget Pro"
        assert rec.kind is OfferingKind.STANDALONE
        assert rec.status is OfferingStatus.DRAFT
        assert rec.version_ref == "v1.0"
        assert rec.created_at == TS

    def test_frozen(self):
        rec = _offering()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.offering_id = "x"

    def test_metadata_frozen(self):
        rec = _offering(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["k"] == "v"
        with pytest.raises(TypeError):
            rec.metadata["k2"] = "v2"

    def test_empty_metadata(self):
        rec = _offering()
        assert isinstance(rec.metadata, MappingProxyType)
        assert len(rec.metadata) == 0

    def test_to_dict_preserves_enums(self):
        rec = _offering()
        d = rec.to_dict()
        assert d["kind"] is OfferingKind.STANDALONE
        assert d["status"] is OfferingStatus.DRAFT

    def test_to_dict_metadata_thawed(self):
        rec = _offering(metadata={"a": 1})
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field", [
        "offering_id", "product_id", "tenant_id", "display_name",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _offering(**{field: ""})

    @pytest.mark.parametrize("field", [
        "offering_id", "product_id", "tenant_id", "display_name",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _offering(**{field: "   "})

    def test_invalid_kind_type(self):
        with pytest.raises(ValueError):
            _offering(kind="standalone")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            _offering(status="draft")

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _offering(created_at="not-a-date")

    def test_empty_datetime(self):
        with pytest.raises(ValueError):
            _offering(created_at="")

    def test_date_only_accepted(self):
        rec = _offering(created_at="2025-06-01")
        assert rec.created_at == "2025-06-01"

    def test_utc_z_suffix_accepted(self):
        rec = _offering(created_at="2025-06-01T12:00:00Z")
        assert rec.created_at == "2025-06-01T12:00:00Z"

    def test_now_iso_accepted(self):
        rec = _offering(created_at=NOW_ISO)
        assert rec.created_at == NOW_ISO

    def test_all_offering_kinds(self):
        for kind in OfferingKind:
            rec = _offering(kind=kind)
            assert rec.kind is kind

    def test_all_offering_statuses(self):
        for status in OfferingStatus:
            rec = _offering(status=status)
            assert rec.status is status

    def test_version_ref_empty_allowed(self):
        rec = _offering(version_ref="")
        assert rec.version_ref == ""

    def test_nested_metadata_frozen(self):
        rec = _offering(metadata={"nested": {"a": 1}})
        assert isinstance(rec.metadata["nested"], MappingProxyType)

    def test_equality(self):
        a = _offering()
        b = _offering()
        assert a == b

    def test_inequality(self):
        a = _offering()
        b = _offering(offering_id="off-002")
        assert a != b


# ===================================================================
# PackageRecord
# ===================================================================


class TestPackageRecord:
    def test_valid_construction(self):
        rec = _package()
        assert rec.package_id == "pkg-001"
        assert rec.tenant_id == "t-001"
        assert rec.display_name == "Starter Pack"
        assert rec.offering_count == 3
        assert rec.status is OfferingStatus.ACTIVE
        assert rec.created_at == TS

    def test_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _package().package_id = "x"

    def test_metadata_frozen(self):
        rec = _package(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _package().to_dict()
        assert d["status"] is OfferingStatus.ACTIVE

    @pytest.mark.parametrize("field", ["package_id", "tenant_id", "display_name"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _package(**{field: ""})

    @pytest.mark.parametrize("field", ["package_id", "tenant_id", "display_name"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _package(**{field: "  "})

    def test_offering_count_zero_ok(self):
        rec = _package(offering_count=0)
        assert rec.offering_count == 0

    def test_offering_count_negative_rejected(self):
        with pytest.raises(ValueError):
            _package(offering_count=-1)

    def test_offering_count_bool_rejected(self):
        with pytest.raises(ValueError):
            _package(offering_count=True)

    def test_offering_count_float_rejected(self):
        with pytest.raises(ValueError):
            _package(offering_count=1.5)

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            _package(status="active")

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _package(created_at="nope")

    def test_all_statuses(self):
        for st in OfferingStatus:
            rec = _package(status=st)
            assert rec.status is st

    def test_equality(self):
        assert _package() == _package()


# ===================================================================
# BundleRecord
# ===================================================================


class TestBundleRecord:
    def test_valid_construction(self):
        rec = _bundle()
        assert rec.bundle_id == "bnd-001"
        assert rec.package_id == "pkg-001"
        assert rec.offering_id == "off-001"
        assert rec.tenant_id == "t-001"
        assert rec.disposition is BundleDisposition.VALID

    def test_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _bundle().bundle_id = "x"

    def test_metadata_frozen(self):
        rec = _bundle(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _bundle().to_dict()
        assert d["disposition"] is BundleDisposition.VALID

    @pytest.mark.parametrize("field", [
        "bundle_id", "package_id", "offering_id", "tenant_id",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _bundle(**{field: ""})

    @pytest.mark.parametrize("field", [
        "bundle_id", "package_id", "offering_id", "tenant_id",
    ])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _bundle(**{field: "  "})

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            _bundle(disposition="valid")

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _bundle(created_at="bad")

    def test_all_dispositions(self):
        for disp in BundleDisposition:
            rec = _bundle(disposition=disp)
            assert rec.disposition is disp

    def test_equality(self):
        assert _bundle() == _bundle()

    def test_inequality(self):
        assert _bundle() != _bundle(bundle_id="bnd-002")


# ===================================================================
# ListingRecord
# ===================================================================


class TestListingRecord:
    def test_valid_construction(self):
        rec = _listing()
        assert rec.listing_id == "lst-001"
        assert rec.offering_id == "off-001"
        assert rec.tenant_id == "t-001"
        assert rec.channel is MarketplaceChannel.DIRECT
        assert rec.active is True
        assert rec.listed_at == TS

    def test_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _listing().listing_id = "x"

    def test_metadata_frozen(self):
        rec = _listing(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _listing().to_dict()
        assert d["channel"] is MarketplaceChannel.DIRECT

    @pytest.mark.parametrize("field", ["listing_id", "offering_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _listing(**{field: ""})

    @pytest.mark.parametrize("field", ["listing_id", "offering_id", "tenant_id"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _listing(**{field: "  "})

    def test_invalid_channel_type(self):
        with pytest.raises(ValueError):
            _listing(channel="direct")

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _listing(listed_at="nope")

    def test_active_false(self):
        rec = _listing(active=False)
        assert rec.active is False

    def test_all_channels(self):
        for ch in MarketplaceChannel:
            rec = _listing(channel=ch)
            assert rec.channel is ch

    def test_equality(self):
        assert _listing() == _listing()

    def test_inequality(self):
        assert _listing() != _listing(listing_id="lst-002")


# ===================================================================
# EligibilityRule
# ===================================================================


class TestEligibilityRule:
    def test_valid_construction(self):
        rec = _eligibility()
        assert rec.rule_id == "rule-001"
        assert rec.offering_id == "off-001"
        assert rec.tenant_id == "t-001"
        assert rec.account_segment == "enterprise"
        assert rec.status is EligibilityStatus.ELIGIBLE
        assert rec.reason == "meets criteria"
        assert rec.evaluated_at == TS

    def test_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _eligibility().rule_id = "x"

    def test_metadata_frozen(self):
        rec = _eligibility(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _eligibility().to_dict()
        assert d["status"] is EligibilityStatus.ELIGIBLE

    @pytest.mark.parametrize("field", [
        "rule_id", "offering_id", "tenant_id", "account_segment",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _eligibility(**{field: ""})

    @pytest.mark.parametrize("field", [
        "rule_id", "offering_id", "tenant_id", "account_segment",
    ])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _eligibility(**{field: "  "})

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            _eligibility(status="eligible")

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _eligibility(evaluated_at="nope")

    def test_reason_empty_string_allowed(self):
        # reason is a plain str, no non-empty validation
        rec = _eligibility(reason="")
        assert rec.reason == ""

    def test_all_statuses(self):
        for st in EligibilityStatus:
            rec = _eligibility(status=st)
            assert rec.status is st

    def test_equality(self):
        assert _eligibility() == _eligibility()

    def test_inequality(self):
        assert _eligibility() != _eligibility(rule_id="rule-002")


# ===================================================================
# PricingBinding
# ===================================================================


class TestPricingBinding:
    def test_valid_construction(self):
        rec = _pricing()
        assert rec.binding_id == "prc-001"
        assert rec.offering_id == "off-001"
        assert rec.tenant_id == "t-001"
        assert rec.base_price == 100.0
        assert rec.effective_price == 80.0
        assert rec.disposition is PricingDisposition.STANDARD
        assert rec.contract_ref == "ctr-001"
        assert rec.created_at == TS

    def test_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _pricing().binding_id = "x"

    def test_metadata_frozen(self):
        rec = _pricing(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _pricing().to_dict()
        assert d["disposition"] is PricingDisposition.STANDARD

    @pytest.mark.parametrize("field", ["binding_id", "offering_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _pricing(**{field: ""})

    @pytest.mark.parametrize("field", ["binding_id", "offering_id", "tenant_id"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _pricing(**{field: "  "})

    def test_base_price_zero_ok(self):
        rec = _pricing(base_price=0.0)
        assert rec.base_price == 0.0

    def test_base_price_negative_rejected(self):
        with pytest.raises(ValueError):
            _pricing(base_price=-1.0)

    def test_effective_price_zero_ok(self):
        rec = _pricing(effective_price=0.0)
        assert rec.effective_price == 0.0

    def test_effective_price_negative_rejected(self):
        with pytest.raises(ValueError):
            _pricing(effective_price=-0.01)

    def test_base_price_int_coerced(self):
        rec = _pricing(base_price=50)
        assert rec.base_price == 50.0
        assert isinstance(rec.base_price, float)

    def test_effective_price_int_coerced(self):
        rec = _pricing(effective_price=40)
        assert rec.effective_price == 40.0

    def test_base_price_bool_rejected(self):
        with pytest.raises(ValueError):
            _pricing(base_price=True)

    def test_effective_price_bool_rejected(self):
        with pytest.raises(ValueError):
            _pricing(effective_price=False)

    def test_base_price_inf_rejected(self):
        with pytest.raises(ValueError):
            _pricing(base_price=float("inf"))

    def test_effective_price_nan_rejected(self):
        with pytest.raises(ValueError):
            _pricing(effective_price=float("nan"))

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            _pricing(disposition="standard")

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _pricing(created_at="bad")

    def test_contract_ref_empty_allowed(self):
        rec = _pricing(contract_ref="")
        assert rec.contract_ref == ""

    def test_all_dispositions(self):
        for disp in PricingDisposition:
            rec = _pricing(disposition=disp)
            assert rec.disposition is disp

    def test_equality(self):
        assert _pricing() == _pricing()

    def test_inequality(self):
        assert _pricing() != _pricing(binding_id="prc-002")

    def test_large_price(self):
        rec = _pricing(base_price=999999.99, effective_price=888888.88)
        assert rec.base_price == 999999.99


# ===================================================================
# MarketplaceAssessment
# ===================================================================


class TestMarketplaceAssessment:
    def test_valid_construction(self):
        rec = _assessment()
        assert rec.assessment_id == "asmt-001"
        assert rec.tenant_id == "t-001"
        assert rec.total_offerings == 10
        assert rec.active_offerings == 7
        assert rec.total_listings == 15
        assert rec.active_listings == 12
        assert rec.total_packages == 3
        assert rec.coverage_score == 0.85
        assert rec.assessed_at == TS

    def test_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _assessment().assessment_id = "x"

    def test_metadata_frozen(self):
        rec = _assessment(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    @pytest.mark.parametrize("field", ["assessment_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: ""})

    @pytest.mark.parametrize("field", ["assessment_id", "tenant_id"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: "  "})

    @pytest.mark.parametrize("field", [
        "total_offerings", "active_offerings", "total_listings",
        "active_listings", "total_packages",
    ])
    def test_non_neg_int_zero_ok(self, field):
        rec = _assessment(**{field: 0})
        assert getattr(rec, field) == 0

    @pytest.mark.parametrize("field", [
        "total_offerings", "active_offerings", "total_listings",
        "active_listings", "total_packages",
    ])
    def test_non_neg_int_negative_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_offerings", "active_offerings", "total_listings",
        "active_listings", "total_packages",
    ])
    def test_non_neg_int_bool_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: True})

    def test_coverage_score_zero(self):
        rec = _assessment(coverage_score=0.0)
        assert rec.coverage_score == 0.0

    def test_coverage_score_one(self):
        rec = _assessment(coverage_score=1.0)
        assert rec.coverage_score == 1.0

    def test_coverage_score_negative_rejected(self):
        with pytest.raises(ValueError):
            _assessment(coverage_score=-0.01)

    def test_coverage_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            _assessment(coverage_score=1.01)

    def test_coverage_score_bool_rejected(self):
        with pytest.raises(ValueError):
            _assessment(coverage_score=True)

    def test_coverage_score_inf_rejected(self):
        with pytest.raises(ValueError):
            _assessment(coverage_score=float("inf"))

    def test_coverage_score_nan_rejected(self):
        with pytest.raises(ValueError):
            _assessment(coverage_score=float("nan"))

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _assessment(assessed_at="bad")

    def test_to_dict_keys(self):
        d = _assessment().to_dict()
        expected_keys = {
            "assessment_id", "tenant_id", "total_offerings",
            "active_offerings", "total_listings", "active_listings",
            "total_packages", "coverage_score", "assessed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_equality(self):
        assert _assessment() == _assessment()

    def test_inequality(self):
        assert _assessment() != _assessment(assessment_id="asmt-002")


# ===================================================================
# MarketplaceSnapshot
# ===================================================================


class TestMarketplaceSnapshot:
    def test_valid_construction(self):
        rec = _snapshot()
        assert rec.snapshot_id == "snap-001"
        assert rec.total_offerings == 10
        assert rec.total_packages == 3
        assert rec.total_bundles == 5
        assert rec.total_listings == 15
        assert rec.total_eligibility_rules == 8
        assert rec.total_pricing_bindings == 12
        assert rec.total_assessments == 2
        assert rec.total_violations == 1
        assert rec.captured_at == TS

    def test_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _snapshot().snapshot_id = "x"

    def test_metadata_frozen(self):
        rec = _snapshot(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="  ")

    INT_FIELDS = [
        "total_offerings", "total_packages", "total_bundles",
        "total_listings", "total_eligibility_rules",
        "total_pricing_bindings", "total_assessments", "total_violations",
    ]

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_non_neg_int_zero_ok(self, field):
        rec = _snapshot(**{field: 0})
        assert getattr(rec, field) == 0

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_non_neg_int_negative_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_non_neg_int_bool_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: True})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad")

    def test_to_dict_keys(self):
        d = _snapshot().to_dict()
        expected = {
            "snapshot_id", "total_offerings", "total_packages",
            "total_bundles", "total_listings", "total_eligibility_rules",
            "total_pricing_bindings", "total_assessments",
            "total_violations", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_json_roundtrip(self):
        rec = _snapshot()
        j = rec.to_json()
        assert '"snap-001"' in j
        assert isinstance(j, str)

    def test_equality(self):
        assert _snapshot() == _snapshot()

    def test_inequality(self):
        assert _snapshot() != _snapshot(snapshot_id="snap-002")

    def test_all_zeros(self):
        rec = _snapshot(
            total_offerings=0, total_packages=0, total_bundles=0,
            total_listings=0, total_eligibility_rules=0,
            total_pricing_bindings=0, total_assessments=0,
            total_violations=0,
        )
        assert rec.total_offerings == 0


# ===================================================================
# MarketplaceViolation
# ===================================================================


class TestMarketplaceViolation:
    def test_valid_construction(self):
        rec = _violation()
        assert rec.violation_id == "vio-001"
        assert rec.tenant_id == "t-001"
        assert rec.operation == "publish"
        assert rec.reason == "missing approval"
        assert rec.detected_at == TS

    def test_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _violation().violation_id = "x"

    def test_metadata_frozen(self):
        rec = _violation(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _violation(**{field: ""})

    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _violation(**{field: "  "})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _violation(detected_at="bad")

    def test_to_json_roundtrip(self):
        rec = _violation()
        j = rec.to_json()
        assert '"vio-001"' in j

    def test_to_dict_keys(self):
        d = _violation().to_dict()
        expected = {
            "violation_id", "tenant_id", "operation",
            "reason", "detected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_equality(self):
        assert _violation() == _violation()

    def test_inequality(self):
        assert _violation() != _violation(violation_id="vio-002")

    def test_different_timestamps(self):
        a = _violation(detected_at=TS)
        b = _violation(detected_at=TS2)
        assert a != b


# ===================================================================
# MarketplaceClosureReport
# ===================================================================


class TestMarketplaceClosureReport:
    def test_valid_construction(self):
        rec = _closure()
        assert rec.report_id == "rpt-001"
        assert rec.tenant_id == "t-001"
        assert rec.total_offerings == 10
        assert rec.total_packages == 3
        assert rec.total_bundles == 5
        assert rec.total_listings == 15
        assert rec.total_eligibility_rules == 8
        assert rec.total_pricing_bindings == 12
        assert rec.total_violations == 1
        assert rec.closed_at == TS

    def test_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _closure().report_id = "x"

    def test_metadata_frozen(self):
        rec = _closure(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: ""})

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: "  "})

    INT_FIELDS = [
        "total_offerings", "total_packages", "total_bundles",
        "total_listings", "total_eligibility_rules",
        "total_pricing_bindings", "total_violations",
    ]

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_non_neg_int_zero_ok(self, field):
        rec = _closure(**{field: 0})
        assert getattr(rec, field) == 0

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_non_neg_int_negative_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_non_neg_int_bool_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: True})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _closure(closed_at="bad")

    def test_to_json_roundtrip(self):
        rec = _closure()
        j = rec.to_json()
        assert '"rpt-001"' in j

    def test_to_dict_keys(self):
        d = _closure().to_dict()
        expected = {
            "report_id", "tenant_id", "total_offerings", "total_packages",
            "total_bundles", "total_listings", "total_eligibility_rules",
            "total_pricing_bindings", "total_violations",
            "closed_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_equality(self):
        assert _closure() == _closure()

    def test_inequality(self):
        assert _closure() != _closure(report_id="rpt-002")

    def test_all_zeros(self):
        rec = _closure(
            total_offerings=0, total_packages=0, total_bundles=0,
            total_listings=0, total_eligibility_rules=0,
            total_pricing_bindings=0, total_violations=0,
        )
        assert rec.total_offerings == 0


# ===================================================================
# Cross-cutting / integration-style tests
# ===================================================================


class TestCrossCutting:
    """Tests spanning multiple record types or validating shared behaviour."""

    def test_offering_with_ts2(self):
        rec = _offering(created_at=TS2)
        assert rec.created_at == TS2

    def test_package_with_ts2(self):
        rec = _package(created_at=TS2)
        assert rec.created_at == TS2

    def test_bundle_with_ts2(self):
        rec = _bundle(created_at=TS2)
        assert rec.created_at == TS2

    def test_listing_with_ts2(self):
        rec = _listing(listed_at=TS2)
        assert rec.listed_at == TS2

    def test_eligibility_with_ts2(self):
        rec = _eligibility(evaluated_at=TS2)
        assert rec.evaluated_at == TS2

    def test_pricing_with_ts2(self):
        rec = _pricing(created_at=TS2)
        assert rec.created_at == TS2

    def test_assessment_with_ts2(self):
        rec = _assessment(assessed_at=TS2)
        assert rec.assessed_at == TS2

    def test_snapshot_with_ts2(self):
        rec = _snapshot(captured_at=TS2)
        assert rec.captured_at == TS2

    def test_violation_with_ts2(self):
        rec = _violation(detected_at=TS2)
        assert rec.detected_at == TS2

    def test_closure_with_ts2(self):
        rec = _closure(closed_at=TS2)
        assert rec.closed_at == TS2

    def test_all_records_have_to_dict(self):
        records = [
            _offering(), _package(), _bundle(), _listing(),
            _eligibility(), _pricing(), _assessment(),
            _snapshot(), _violation(), _closure(),
        ]
        for rec in records:
            d = rec.to_dict()
            assert isinstance(d, dict)
            assert "metadata" in d

    def test_all_records_frozen(self):
        records = [
            _offering(), _package(), _bundle(), _listing(),
            _eligibility(), _pricing(), _assessment(),
            _snapshot(), _violation(), _closure(),
        ]
        for rec in records:
            with pytest.raises(dataclasses.FrozenInstanceError):
                rec.metadata = {}

    def test_all_records_metadata_mapping_proxy(self):
        records = [
            _offering(), _package(), _bundle(), _listing(),
            _eligibility(), _pricing(), _assessment(),
            _snapshot(), _violation(), _closure(),
        ]
        for rec in records:
            assert isinstance(rec.metadata, MappingProxyType)

    def test_all_records_to_dict_thaws_metadata(self):
        records = [
            _offering(metadata={"x": 1}),
            _package(metadata={"x": 1}),
            _bundle(metadata={"x": 1}),
            _listing(metadata={"x": 1}),
            _eligibility(metadata={"x": 1}),
            _pricing(metadata={"x": 1}),
            _assessment(metadata={"x": 1}),
            _snapshot(metadata={"x": 1}),
            _violation(metadata={"x": 1}),
            _closure(metadata={"x": 1}),
        ]
        for rec in records:
            d = rec.to_dict()
            assert isinstance(d["metadata"], dict)

    def test_snapshot_no_enums_to_json(self):
        """Snapshot has no enum fields, so to_json should work."""
        rec = _snapshot()
        j = rec.to_json()
        assert isinstance(j, str)
        assert "snap-001" in j

    def test_violation_no_enums_to_json(self):
        """Violation has no enum fields, so to_json should work."""
        rec = _violation()
        j = rec.to_json()
        assert isinstance(j, str)

    def test_closure_no_enums_to_json(self):
        """ClosureReport has no enum fields, so to_json should work."""
        rec = _closure()
        j = rec.to_json()
        assert isinstance(j, str)

    def test_offering_all_kind_status_combos(self):
        for kind in OfferingKind:
            for status in OfferingStatus:
                rec = _offering(kind=kind, status=status)
                assert rec.kind is kind
                assert rec.status is status

    def test_listing_all_channel_active_combos(self):
        for ch in MarketplaceChannel:
            for active in (True, False):
                rec = _listing(channel=ch, active=active)
                assert rec.channel is ch
                assert rec.active is active

    def test_deeply_nested_metadata(self):
        meta = {"a": {"b": {"c": [1, 2, 3]}}}
        rec = _offering(metadata=meta)
        assert isinstance(rec.metadata["a"], MappingProxyType)
        assert isinstance(rec.metadata["a"]["b"], MappingProxyType)
        # lists become tuples
        assert rec.metadata["a"]["b"]["c"] == (1, 2, 3)

    def test_metadata_with_list_becomes_tuple(self):
        rec = _package(metadata={"items": [10, 20]})
        assert rec.metadata["items"] == (10, 20)

    def test_coverage_score_int_zero_coerced(self):
        rec = _assessment(coverage_score=0)
        assert rec.coverage_score == 0.0
        assert isinstance(rec.coverage_score, float)

    def test_coverage_score_int_one_coerced(self):
        rec = _assessment(coverage_score=1)
        assert rec.coverage_score == 1.0

    def test_pricing_base_and_effective_equal(self):
        rec = _pricing(base_price=50.0, effective_price=50.0)
        assert rec.base_price == rec.effective_price

    def test_offering_to_dict_field_count(self):
        d = _offering().to_dict()
        assert len(d) == 9

    def test_package_to_dict_field_count(self):
        d = _package().to_dict()
        assert len(d) == 7

    def test_bundle_to_dict_field_count(self):
        d = _bundle().to_dict()
        assert len(d) == 7

    def test_listing_to_dict_field_count(self):
        d = _listing().to_dict()
        assert len(d) == 7

    def test_eligibility_to_dict_field_count(self):
        d = _eligibility().to_dict()
        assert len(d) == 8

    def test_pricing_to_dict_field_count(self):
        d = _pricing().to_dict()
        assert len(d) == 9

    def test_assessment_to_dict_field_count(self):
        d = _assessment().to_dict()
        assert len(d) == 10

    def test_snapshot_to_dict_field_count(self):
        d = _snapshot().to_dict()
        assert len(d) == 11

    def test_violation_to_dict_field_count(self):
        d = _violation().to_dict()
        assert len(d) == 6

    def test_closure_to_dict_field_count(self):
        d = _closure().to_dict()
        assert len(d) == 11

    def test_now_iso_accepted_everywhere(self):
        ts = NOW_ISO
        _offering(created_at=ts)
        _package(created_at=ts)
        _bundle(created_at=ts)
        _listing(listed_at=ts)
        _eligibility(evaluated_at=ts)
        _pricing(created_at=ts)
        _assessment(assessed_at=ts)
        _snapshot(captured_at=ts)
        _violation(detected_at=ts)
        _closure(closed_at=ts)

    def test_date_only_accepted_everywhere(self):
        ts = "2025-06-01"
        _offering(created_at=ts)
        _package(created_at=ts)
        _bundle(created_at=ts)
        _listing(listed_at=ts)
        _eligibility(evaluated_at=ts)
        _pricing(created_at=ts)
        _assessment(assessed_at=ts)
        _snapshot(captured_at=ts)
        _violation(detected_at=ts)
        _closure(closed_at=ts)

    def test_z_suffix_accepted_everywhere(self):
        ts = "2025-06-01T00:00:00Z"
        _offering(created_at=ts)
        _package(created_at=ts)
        _bundle(created_at=ts)
        _listing(listed_at=ts)
        _eligibility(evaluated_at=ts)
        _pricing(created_at=ts)
        _assessment(assessed_at=ts)
        _snapshot(captured_at=ts)
        _violation(detected_at=ts)
        _closure(closed_at=ts)
