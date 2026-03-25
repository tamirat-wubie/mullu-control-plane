"""Phase 150 — International / Multi-Region Expansion Tests."""
import pytest
from mcoi_runtime.pilot.international import (
    REGIONS, LOCALES, COMPLIANCE_BUNDLES, REGIONAL_DEPLOYMENTS, REGIONAL_GTM,
    GlobalOperatingDashboard,
)

class TestRegions:
    def test_7_regions(self):
        assert len(REGIONS) == 7

    def test_each_has_residency(self):
        for r in REGIONS.values():
            assert r.data_residency
            assert r.currency
            assert r.jurisdiction

class TestLocales:
    def test_7_locales(self):
        assert len(LOCALES) == 7

    def test_us_format(self):
        assert LOCALES["en_US"].date_format == "MM/DD/YYYY"
        assert LOCALES["en_US"].currency_symbol == "$"

    def test_eu_format(self):
        assert LOCALES["de_DE"].date_format == "DD.MM.YYYY"
        assert LOCALES["de_DE"].currency_position == "suffix"

class TestCompliance:
    def test_7_bundles(self):
        assert len(COMPLIANCE_BUNDLES) == 7

    def test_gdpr_enforced(self):
        gdpr = COMPLIANCE_BUNDLES["eu_gdpr"]
        assert gdpr.data_residency_enforced
        assert "right_to_erasure" in gdpr.additional_rules

    def test_us_relaxed(self):
        us = COMPLIANCE_BUNDLES["us"]
        assert not us.data_residency_enforced

class TestDeployment:
    def test_5_configs(self):
        assert len(REGIONAL_DEPLOYMENTS) == 5

    def test_eu_has_tax(self):
        assert REGIONAL_DEPLOYMENTS["eu"].tax_rate_pct == 20.0

    def test_ae_sovereign(self):
        assert REGIONAL_DEPLOYMENTS["ae"].support_routing == "local"

class TestGTM:
    def test_5_regional_gtm(self):
        assert len(REGIONAL_GTM) == 5

    def test_eu_partner_first(self):
        assert REGIONAL_GTM["eu"].partner_model == "partner_first"

    def test_priority_packs(self):
        for r in REGIONAL_GTM.values():
            assert len(r.priority_packs) >= 2

class TestGlobalDashboard:
    def test_multi_region(self):
        dash = GlobalOperatingDashboard()
        dash.register_tenant("us", "t1")
        dash.register_tenant("us", "t2")
        dash.register_tenant("eu", "t3")
        dash.register_tenant("sg", "t4")
        d = dash.dashboard()
        assert d["total_regions"] == 3
        assert d["total_tenants"] == 4
        assert d["tenants_by_region"]["us"] == 2

class TestGoldenProof:
    def test_same_pack_two_regions(self):
        # 1. Same pack, different regions
        us = REGIONS["us"]
        eu = REGIONS["eu"]
        assert us.currency == "USD"
        assert eu.currency == "EUR"

        # 2. Different compliance
        us_comp = COMPLIANCE_BUNDLES["us"]
        eu_comp = COMPLIANCE_BUNDLES["eu_gdpr"]
        assert not us_comp.data_residency_enforced
        assert eu_comp.data_residency_enforced

        # 3. Different pricing
        us_gtm = REGIONAL_GTM["us"]
        eu_gtm = REGIONAL_GTM["eu"]
        assert eu_gtm.pricing_multiplier > us_gtm.pricing_multiplier

        # 4. Different connectors/tax
        us_dep = REGIONAL_DEPLOYMENTS["us"]
        eu_dep = REGIONAL_DEPLOYMENTS["eu"]
        assert eu_dep.tax_rate_pct > us_dep.tax_rate_pct

        # 5. Data boundary rules
        assert eu_comp.privacy_framework == "gdpr"
        assert "right_to_erasure" in eu_comp.additional_rules

        # 6. Global dashboard
        dash = GlobalOperatingDashboard()
        dash.register_tenant("us", "cust-us-1")
        dash.register_tenant("eu", "cust-eu-1")
        d = dash.dashboard()
        assert d["total_regions"] == 2
        assert d["regions_available"] == 7
