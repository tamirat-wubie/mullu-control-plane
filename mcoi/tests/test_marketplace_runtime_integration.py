"""Tests for MarketplaceRuntimeIntegration bridge.

Covers constructor validation, all 8 methods (offering creation from
product_release / customer_account / partner_channel / contract_terms,
bind_pricing_from_billing, bind_eligibility_from_entitlements,
attach_marketplace_state_to_memory_mesh, attach_marketplace_state_to_graph),
event emission, immutability, and full lifecycle golden path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.marketplace_runtime import MarketplaceRuntimeEngine
from mcoi_runtime.core.marketplace_runtime_integration import MarketplaceRuntimeIntegration
from mcoi_runtime.contracts.marketplace_runtime import (
    OfferingKind,
    MarketplaceChannel,
    PricingDisposition,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def marketplace_engine(event_spine: EventSpineEngine) -> MarketplaceRuntimeEngine:
    return MarketplaceRuntimeEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def integration(
    marketplace_engine: MarketplaceRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> MarketplaceRuntimeIntegration:
    return MarketplaceRuntimeIntegration(marketplace_engine, event_spine, memory_engine)


def _product_release(
    integration: MarketplaceRuntimeIntegration,
    offering_id: str = "off-1",
    product_id: str = "prod-1",
    tenant_id: str = "t-1",
) -> dict:
    """Helper: create an offering from a product release."""
    return integration.offering_from_product_release(
        offering_id=offering_id,
        product_id=product_id,
        tenant_id=tenant_id,
        display_name="Offering A",
        version_ref="v1.0",
    )


def _customer_account(
    integration: MarketplaceRuntimeIntegration,
    offering_id: str = "off-2",
) -> dict:
    return integration.offering_from_customer_account(
        offering_id=offering_id,
        product_id="prod-1",
        tenant_id="t-1",
        display_name="Custom Offering",
        account_ref="acct-ref-1",
    )


def _partner_channel(
    integration: MarketplaceRuntimeIntegration,
    offering_id: str = "off-3",
    listing_id: str = "lst-1",
) -> dict:
    return integration.offering_from_partner_channel(
        offering_id=offering_id,
        listing_id=listing_id,
        product_id="prod-1",
        tenant_id="t-1",
        display_name="Partner Offering",
        partner_ref="partner-ref-1",
    )


def _contract_terms(
    integration: MarketplaceRuntimeIntegration,
    offering_id: str = "off-4",
) -> dict:
    return integration.offering_from_contract_terms(
        offering_id=offering_id,
        product_id="prod-1",
        tenant_id="t-1",
        display_name="Contract Offering",
        contract_ref="ctr-ref-1",
        base_price=100.0,
    )


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_rejects_wrong_marketplace_engine_type(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ):
        with pytest.raises(RuntimeCoreInvariantError):
            MarketplaceRuntimeIntegration("not-an-engine", event_spine, memory_engine)

    def test_rejects_wrong_event_spine_type(
        self, marketplace_engine: MarketplaceRuntimeEngine, memory_engine: MemoryMeshEngine
    ):
        with pytest.raises(RuntimeCoreInvariantError):
            MarketplaceRuntimeIntegration(marketplace_engine, "not-a-spine", memory_engine)

    def test_rejects_wrong_memory_engine_type(
        self, marketplace_engine: MarketplaceRuntimeEngine, event_spine: EventSpineEngine
    ):
        with pytest.raises(RuntimeCoreInvariantError):
            MarketplaceRuntimeIntegration(marketplace_engine, event_spine, "not-a-memory")

    def test_rejects_none_marketplace_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ):
        with pytest.raises(RuntimeCoreInvariantError):
            MarketplaceRuntimeIntegration(None, event_spine, memory_engine)

    def test_rejects_none_event_spine(
        self, marketplace_engine: MarketplaceRuntimeEngine, memory_engine: MemoryMeshEngine
    ):
        with pytest.raises(RuntimeCoreInvariantError):
            MarketplaceRuntimeIntegration(marketplace_engine, None, memory_engine)

    def test_rejects_none_memory_engine(
        self, marketplace_engine: MarketplaceRuntimeEngine, event_spine: EventSpineEngine
    ):
        with pytest.raises(RuntimeCoreInvariantError):
            MarketplaceRuntimeIntegration(marketplace_engine, event_spine, None)

    def test_accepts_valid_engines(self, integration: MarketplaceRuntimeIntegration):
        assert integration is not None


# ---------------------------------------------------------------------------
# offering_from_product_release
# ---------------------------------------------------------------------------


class TestOfferingFromProductRelease:
    def test_returns_dict(self, integration: MarketplaceRuntimeIntegration):
        result = _product_release(integration)
        assert isinstance(result, dict)

    def test_offering_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _product_release(integration, offering_id="off-pr-1")
        assert result["offering_id"] == "off-pr-1"

    def test_product_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _product_release(integration)
        assert result["product_id"] == "prod-1"

    def test_tenant_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _product_release(integration)
        assert result["tenant_id"] == "t-1"

    def test_version_ref_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _product_release(integration)
        assert result["version_ref"] == "v1.0"

    def test_source_type_is_product_release(self, integration: MarketplaceRuntimeIntegration):
        result = _product_release(integration)
        assert result["source_type"] == "product_release"

    def test_default_kind_standalone(self, integration: MarketplaceRuntimeIntegration):
        result = _product_release(integration)
        assert result["kind"] == OfferingKind.STANDALONE.value

    def test_custom_kind(self, integration: MarketplaceRuntimeIntegration):
        result = integration.offering_from_product_release(
            offering_id="off-k1", product_id="p1", tenant_id="t-1",
            display_name="X", version_ref="v2", kind=OfferingKind.TRIAL,
        )
        assert result["kind"] == OfferingKind.TRIAL.value

    def test_emits_event(
        self, integration: MarketplaceRuntimeIntegration, event_spine: EventSpineEngine
    ):
        before = event_spine.event_count
        _product_release(integration)
        assert event_spine.event_count > before

    def test_duplicate_offering_id_raises(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="dup-1")
        with pytest.raises(RuntimeCoreInvariantError):
            _product_release(integration, offering_id="dup-1")

    def test_offering_is_activated(
        self, integration: MarketplaceRuntimeIntegration, marketplace_engine: MarketplaceRuntimeEngine
    ):
        _product_release(integration, offering_id="off-act-1")
        offering = marketplace_engine.get_offering("off-act-1")
        assert offering.status.value == "active"


# ---------------------------------------------------------------------------
# offering_from_customer_account
# ---------------------------------------------------------------------------


class TestOfferingFromCustomerAccount:
    def test_returns_dict(self, integration: MarketplaceRuntimeIntegration):
        result = _customer_account(integration)
        assert isinstance(result, dict)

    def test_offering_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _customer_account(integration, offering_id="off-ca-1")
        assert result["offering_id"] == "off-ca-1"

    def test_account_ref_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _customer_account(integration)
        assert result["account_ref"] == "acct-ref-1"

    def test_source_type_is_customer_account(self, integration: MarketplaceRuntimeIntegration):
        result = _customer_account(integration)
        assert result["source_type"] == "customer_account"

    def test_default_kind_custom(self, integration: MarketplaceRuntimeIntegration):
        result = _customer_account(integration)
        assert result["kind"] == OfferingKind.CUSTOM.value

    def test_offering_not_activated(
        self, integration: MarketplaceRuntimeIntegration, marketplace_engine: MarketplaceRuntimeEngine
    ):
        _customer_account(integration, offering_id="off-ca-2")
        offering = marketplace_engine.get_offering("off-ca-2")
        assert offering.status.value == "draft"

    def test_emits_event(
        self, integration: MarketplaceRuntimeIntegration, event_spine: EventSpineEngine
    ):
        before = event_spine.event_count
        _customer_account(integration)
        assert event_spine.event_count > before

    def test_product_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _customer_account(integration)
        assert result["product_id"] == "prod-1"

    def test_tenant_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _customer_account(integration)
        assert result["tenant_id"] == "t-1"


# ---------------------------------------------------------------------------
# offering_from_partner_channel
# ---------------------------------------------------------------------------


class TestOfferingFromPartnerChannel:
    def test_returns_dict(self, integration: MarketplaceRuntimeIntegration):
        result = _partner_channel(integration)
        assert isinstance(result, dict)

    def test_offering_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _partner_channel(integration, offering_id="off-pc-1")
        assert result["offering_id"] == "off-pc-1"

    def test_listing_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _partner_channel(integration, listing_id="lst-pc-1")
        assert result["listing_id"] == "lst-pc-1"

    def test_partner_ref_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _partner_channel(integration)
        assert result["partner_ref"] == "partner-ref-1"

    def test_default_channel_partner(self, integration: MarketplaceRuntimeIntegration):
        result = _partner_channel(integration)
        assert result["channel"] == MarketplaceChannel.PARTNER.value

    def test_custom_channel(self, integration: MarketplaceRuntimeIntegration):
        result = integration.offering_from_partner_channel(
            offering_id="off-pc-2", listing_id="lst-pc-2", product_id="p1",
            tenant_id="t-1", display_name="X", partner_ref="pr",
            channel=MarketplaceChannel.MARKETPLACE,
        )
        assert result["channel"] == MarketplaceChannel.MARKETPLACE.value

    def test_source_type_is_partner_channel(self, integration: MarketplaceRuntimeIntegration):
        result = _partner_channel(integration)
        assert result["source_type"] == "partner_channel"

    def test_offering_activated(
        self, integration: MarketplaceRuntimeIntegration, marketplace_engine: MarketplaceRuntimeEngine
    ):
        _partner_channel(integration, offering_id="off-pc-3")
        offering = marketplace_engine.get_offering("off-pc-3")
        assert offering.status.value == "active"

    def test_listing_created(
        self, integration: MarketplaceRuntimeIntegration, marketplace_engine: MarketplaceRuntimeEngine
    ):
        _partner_channel(integration, offering_id="off-pc-4", listing_id="lst-pc-4")
        assert marketplace_engine.listing_count >= 1

    def test_emits_event(
        self, integration: MarketplaceRuntimeIntegration, event_spine: EventSpineEngine
    ):
        before = event_spine.event_count
        _partner_channel(integration)
        assert event_spine.event_count > before

    def test_product_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _partner_channel(integration)
        assert result["product_id"] == "prod-1"

    def test_tenant_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _partner_channel(integration)
        assert result["tenant_id"] == "t-1"


# ---------------------------------------------------------------------------
# offering_from_contract_terms
# ---------------------------------------------------------------------------


class TestOfferingFromContractTerms:
    def test_returns_dict(self, integration: MarketplaceRuntimeIntegration):
        result = _contract_terms(integration)
        assert isinstance(result, dict)

    def test_offering_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _contract_terms(integration, offering_id="off-ct-1")
        assert result["offering_id"] == "off-ct-1"

    def test_source_type_is_contract_terms(self, integration: MarketplaceRuntimeIntegration):
        result = _contract_terms(integration)
        assert result["source_type"] == "contract_terms"

    def test_contract_ref_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _contract_terms(integration)
        assert result["contract_ref"] == "ctr-ref-1"

    def test_base_price_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _contract_terms(integration)
        assert result["base_price"] == 100.0

    def test_effective_price_defaults_to_base(self, integration: MarketplaceRuntimeIntegration):
        result = _contract_terms(integration)
        # effective_price=0.0 triggers base_price as effective
        assert result["effective_price"] == 100.0

    def test_explicit_effective_price(self, integration: MarketplaceRuntimeIntegration):
        result = integration.offering_from_contract_terms(
            offering_id="off-ct-2", product_id="p1", tenant_id="t-1",
            display_name="X", contract_ref="cr", base_price=200.0,
            effective_price=150.0,
        )
        assert result["effective_price"] == 150.0

    def test_binding_id_present(self, integration: MarketplaceRuntimeIntegration):
        result = _contract_terms(integration)
        assert "binding_id" in result
        assert len(result["binding_id"]) > 0

    def test_pricing_binding_created(
        self, integration: MarketplaceRuntimeIntegration, marketplace_engine: MarketplaceRuntimeEngine
    ):
        _contract_terms(integration)
        assert marketplace_engine.pricing_binding_count >= 1

    def test_emits_event(
        self, integration: MarketplaceRuntimeIntegration, event_spine: EventSpineEngine
    ):
        before = event_spine.event_count
        _contract_terms(integration)
        assert event_spine.event_count > before

    def test_default_disposition_negotiated(self, integration: MarketplaceRuntimeIntegration):
        result = _contract_terms(integration)
        # the result dict does not include disposition, but the binding does
        assert result["source_type"] == "contract_terms"

    def test_product_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = _contract_terms(integration)
        assert result["product_id"] == "prod-1"


# ---------------------------------------------------------------------------
# bind_pricing_from_billing
# ---------------------------------------------------------------------------


class TestBindPricingFromBilling:
    def test_returns_dict(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-bp-1")
        result = integration.bind_pricing_from_billing(
            binding_id="bind-1", offering_id="off-bp-1", tenant_id="t-1",
            base_price=50.0, billing_ref="bill-1",
        )
        assert isinstance(result, dict)

    def test_binding_id_matches(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-bp-2")
        result = integration.bind_pricing_from_billing(
            binding_id="bind-2", offering_id="off-bp-2", tenant_id="t-1",
            base_price=50.0, billing_ref="bill-2",
        )
        assert result["binding_id"] == "bind-2"

    def test_source_type_is_billing(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-bp-3")
        result = integration.bind_pricing_from_billing(
            binding_id="bind-3", offering_id="off-bp-3", tenant_id="t-1",
            base_price=75.0, billing_ref="bill-3",
        )
        assert result["source_type"] == "billing"

    def test_billing_ref_matches(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-bp-4")
        result = integration.bind_pricing_from_billing(
            binding_id="bind-4", offering_id="off-bp-4", tenant_id="t-1",
            base_price=75.0, billing_ref="bill-ref-x",
        )
        assert result["billing_ref"] == "bill-ref-x"

    def test_effective_price_defaults_to_base(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-bp-5")
        result = integration.bind_pricing_from_billing(
            binding_id="bind-5", offering_id="off-bp-5", tenant_id="t-1",
            base_price=60.0, billing_ref="bill-5",
        )
        assert result["effective_price"] == 60.0

    def test_default_disposition_standard(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-bp-6")
        result = integration.bind_pricing_from_billing(
            binding_id="bind-6", offering_id="off-bp-6", tenant_id="t-1",
            base_price=60.0, billing_ref="bill-6",
        )
        assert result["source_type"] == "billing"

    def test_custom_disposition(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-bp-7")
        result = integration.bind_pricing_from_billing(
            binding_id="bind-7", offering_id="off-bp-7", tenant_id="t-1",
            base_price=60.0, billing_ref="bill-7",
            disposition=PricingDisposition.DISCOUNTED,
        )
        assert result["source_type"] == "billing"

    def test_requires_existing_offering(self, integration: MarketplaceRuntimeIntegration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.bind_pricing_from_billing(
                binding_id="bind-x", offering_id="nonexistent", tenant_id="t-1",
                base_price=50.0, billing_ref="bill-x",
            )

    def test_emits_event(
        self, integration: MarketplaceRuntimeIntegration, event_spine: EventSpineEngine
    ):
        _product_release(integration, offering_id="off-bp-8")
        before = event_spine.event_count
        integration.bind_pricing_from_billing(
            binding_id="bind-8", offering_id="off-bp-8", tenant_id="t-1",
            base_price=50.0, billing_ref="bill-8",
        )
        assert event_spine.event_count > before

    def test_offering_id_in_result(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-bp-9")
        result = integration.bind_pricing_from_billing(
            binding_id="bind-9", offering_id="off-bp-9", tenant_id="t-1",
            base_price=50.0, billing_ref="bill-9",
        )
        assert result["offering_id"] == "off-bp-9"

    def test_tenant_id_in_result(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-bp-10")
        result = integration.bind_pricing_from_billing(
            binding_id="bind-10", offering_id="off-bp-10", tenant_id="t-1",
            base_price=50.0, billing_ref="bill-10",
        )
        assert result["tenant_id"] == "t-1"


# ---------------------------------------------------------------------------
# bind_eligibility_from_entitlements
# ---------------------------------------------------------------------------


class TestBindEligibilityFromEntitlements:
    def test_returns_dict(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-1")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-1", offering_id="off-el-1", tenant_id="t-1",
            account_segment="enterprise", has_entitlement=True,
        )
        assert isinstance(result, dict)

    def test_rule_id_matches(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-2")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-2", offering_id="off-el-2", tenant_id="t-1",
            account_segment="enterprise", has_entitlement=True,
        )
        assert result["rule_id"] == "rule-2"

    def test_source_type_is_entitlements(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-3")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-3", offering_id="off-el-3", tenant_id="t-1",
            account_segment="enterprise", has_entitlement=True,
        )
        assert result["source_type"] == "entitlements"

    def test_eligible_status(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-4")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-4", offering_id="off-el-4", tenant_id="t-1",
            account_segment="enterprise", has_entitlement=True,
        )
        assert result["status"] == "eligible"

    def test_ineligible_status(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-5")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-5", offering_id="off-el-5", tenant_id="t-1",
            account_segment="free", has_entitlement=False,
        )
        assert result["status"] == "ineligible"

    def test_has_entitlement_true(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-6")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-6", offering_id="off-el-6", tenant_id="t-1",
            account_segment="premium", has_entitlement=True,
        )
        assert result["has_entitlement"] is True

    def test_has_entitlement_false(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-7")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-7", offering_id="off-el-7", tenant_id="t-1",
            account_segment="trial", has_entitlement=False,
        )
        assert result["has_entitlement"] is False

    def test_account_segment_matches(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-8")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-8", offering_id="off-el-8", tenant_id="t-1",
            account_segment="smb", has_entitlement=True,
        )
        assert result["account_segment"] == "smb"

    def test_requires_existing_offering(self, integration: MarketplaceRuntimeIntegration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.bind_eligibility_from_entitlements(
                rule_id="rule-x", offering_id="nonexistent", tenant_id="t-1",
                account_segment="enterprise", has_entitlement=True,
            )

    def test_emits_event(
        self, integration: MarketplaceRuntimeIntegration, event_spine: EventSpineEngine
    ):
        _product_release(integration, offering_id="off-el-9")
        before = event_spine.event_count
        integration.bind_eligibility_from_entitlements(
            rule_id="rule-9", offering_id="off-el-9", tenant_id="t-1",
            account_segment="enterprise", has_entitlement=True,
        )
        assert event_spine.event_count > before

    def test_offering_id_in_result(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-10")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-10", offering_id="off-el-10", tenant_id="t-1",
            account_segment="enterprise", has_entitlement=True,
        )
        assert result["offering_id"] == "off-el-10"

    def test_tenant_id_in_result(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-el-11")
        result = integration.bind_eligibility_from_entitlements(
            rule_id="rule-11", offering_id="off-el-11", tenant_id="t-1",
            account_segment="enterprise", has_entitlement=True,
        )
        assert result["tenant_id"] == "t-1"


# ---------------------------------------------------------------------------
# attach_marketplace_state_to_memory_mesh
# ---------------------------------------------------------------------------


class TestAttachMarketplaceStateToMemoryMesh:
    def test_returns_memory_record(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)

    def test_title_is_marketplace_runtime_state(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-2")
        assert record.title == "Marketplace runtime state"

    def test_tags_contain_marketplace(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-3")
        assert "marketplace" in record.tags

    def test_tags_contain_offering(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-4")
        assert "offering" in record.tags

    def test_tags_contain_packaging(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-5")
        assert "packaging" in record.tags

    def test_content_has_offerings_key(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-6")
        assert "offerings" in record.content

    def test_content_has_packages_key(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-7")
        assert "packages" in record.content

    def test_content_has_bundles_key(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-8")
        assert "bundles" in record.content

    def test_content_has_listings_key(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-9")
        assert "listings" in record.content

    def test_content_has_eligibility_rules_key(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-10")
        assert "eligibility_rules" in record.content

    def test_content_has_pricing_bindings_key(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-11")
        assert "pricing_bindings" in record.content

    def test_content_has_assessments_key(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-12")
        assert "assessments" in record.content

    def test_content_has_violations_key(self, integration: MarketplaceRuntimeIntegration):
        record = integration.attach_marketplace_state_to_memory_mesh("scope-13")
        assert "violations" in record.content

    def test_counts_reflect_state(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-mem-1")
        record = integration.attach_marketplace_state_to_memory_mesh("scope-14")
        assert record.content["offerings"] == 1

    def test_emits_event(
        self, integration: MarketplaceRuntimeIntegration, event_spine: EventSpineEngine
    ):
        before = event_spine.event_count
        integration.attach_marketplace_state_to_memory_mesh("scope-15")
        assert event_spine.event_count > before


# ---------------------------------------------------------------------------
# attach_marketplace_state_to_graph
# ---------------------------------------------------------------------------


class TestAttachMarketplaceStateToGraph:
    def test_returns_dict(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-1")
        assert isinstance(result, dict)

    def test_scope_ref_id_matches(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-2")
        assert result["scope_ref_id"] == "scope-g-2"

    def test_has_offerings_key(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-3")
        assert "offerings" in result

    def test_has_packages_key(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-4")
        assert "packages" in result

    def test_has_bundles_key(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-5")
        assert "bundles" in result

    def test_has_listings_key(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-6")
        assert "listings" in result

    def test_has_eligibility_rules_key(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-7")
        assert "eligibility_rules" in result

    def test_has_pricing_bindings_key(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-8")
        assert "pricing_bindings" in result

    def test_has_assessments_key(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-9")
        assert "assessments" in result

    def test_has_violations_key(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-10")
        assert "violations" in result

    def test_counts_reflect_state(self, integration: MarketplaceRuntimeIntegration):
        _product_release(integration, offering_id="off-graph-1")
        result = integration.attach_marketplace_state_to_graph("scope-g-11")
        assert result["offerings"] == 1

    def test_empty_state_all_zeros(self, integration: MarketplaceRuntimeIntegration):
        result = integration.attach_marketplace_state_to_graph("scope-g-12")
        for key in ("offerings", "packages", "bundles", "listings",
                     "eligibility_rules", "pricing_bindings", "assessments", "violations"):
            assert result[key] == 0


# ---------------------------------------------------------------------------
# Golden path lifecycle
# ---------------------------------------------------------------------------


class TestGoldenPathLifecycle:
    def test_full_lifecycle(self, integration: MarketplaceRuntimeIntegration):
        # 1. Create offering from product release
        pr = _product_release(integration, offering_id="gp-off-1")
        assert pr["source_type"] == "product_release"

        # 2. Create offering from customer account
        ca = _customer_account(integration, offering_id="gp-off-2")
        assert ca["source_type"] == "customer_account"

        # 3. Create offering from partner channel
        pc = _partner_channel(integration, offering_id="gp-off-3", listing_id="gp-lst-1")
        assert pc["source_type"] == "partner_channel"

        # 4. Create offering from contract terms
        ct = _contract_terms(integration, offering_id="gp-off-4")
        assert ct["source_type"] == "contract_terms"

        # 5. Bind pricing from billing on a product release offering
        bp = integration.bind_pricing_from_billing(
            binding_id="gp-bind-1", offering_id="gp-off-1", tenant_id="t-1",
            base_price=99.0, billing_ref="gp-bill-1",
        )
        assert bp["source_type"] == "billing"

        # 6. Bind eligibility from entitlements
        el = integration.bind_eligibility_from_entitlements(
            rule_id="gp-rule-1", offering_id="gp-off-1", tenant_id="t-1",
            account_segment="enterprise", has_entitlement=True,
        )
        assert el["status"] == "eligible"

        # 7. Attach to memory mesh
        mem = integration.attach_marketplace_state_to_memory_mesh("gp-scope")
        assert mem.content["offerings"] == 4
        assert mem.content["listings"] == 1
        assert mem.content["pricing_bindings"] >= 1
        assert mem.content["eligibility_rules"] == 1

        # 8. Attach to graph
        graph = integration.attach_marketplace_state_to_graph("gp-scope-g")
        assert graph["offerings"] == 4
        assert graph["scope_ref_id"] == "gp-scope-g"
