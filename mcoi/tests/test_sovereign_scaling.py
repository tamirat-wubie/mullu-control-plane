"""Tests for Phase 156 — Sovereign Multi-Region Channel Scaling."""
from __future__ import annotations

import pytest

from mcoi_runtime.pilot.sovereign_scaling import (
    REGION_BUNDLE_MATRIX,
    REGIONAL_PARTNER_PLAYBOOKS,
    SovereignGlobalDashboard,
    compute_sovereign_economics,
    golden_proof_sovereign_scaling,
    route_sovereign_opportunity,
)


# ---- 156A: Region Bundle Matrix -------------------------------------------

class TestRegionBundleMatrix:
    def test_five_regions_present(self):
        assert set(REGION_BUNDLE_MATRIX.keys()) == {"us", "eu", "uk", "sg", "ae"}

    def test_each_region_has_required_keys(self):
        required = {"allowed_bundles", "sovereign_profiles", "partner_types", "compliance_bundle", "connector_set"}
        for region, entry in REGION_BUNDLE_MATRIX.items():
            assert required.issubset(entry.keys()), f"{region} missing keys"

    def test_us_allows_all_four_bundles(self):
        assert len(REGION_BUNDLE_MATRIX["us"]["allowed_bundles"]) == 4

    def test_ae_restricted_to_regulated_ops(self):
        assert REGION_BUNDLE_MATRIX["ae"]["allowed_bundles"] == ("regulated_ops",)


# ---- 156B: Routing ---------------------------------------------------------

class TestRouting:
    def test_unknown_region_returns_restricted(self):
        assert route_sovereign_opportunity("xx", "enterprise", "none", "regulated_ops") == "restricted_specialist"

    def test_bundle_not_allowed_returns_restricted(self):
        assert route_sovereign_opportunity("ae", "enterprise", "uae_ias", "factory_quality") == "restricted_specialist"

    def test_high_trust_returns_managed_sovereign(self):
        assert route_sovereign_opportunity("us", "enterprise", "fedramp_high", "regulated_ops") == "managed_sovereign"

    def test_government_buyer_returns_partner_led(self):
        assert route_sovereign_opportunity("eu", "government", "gdpr_standard", "regulated_ops") == "partner_led"

    def test_enterprise_cosell_region(self):
        assert route_sovereign_opportunity("us", "enterprise", "fedramp_moderate", "regulated_ops") == "co_sell"

    def test_smb_returns_direct(self):
        assert route_sovereign_opportunity("eu", "smb", "gdpr_standard", "regulated_ops") == "direct"


# ---- 156C: Regional Partner Playbooks -------------------------------------

class TestPlaybooks:
    def test_four_bundle_playbooks(self):
        assert len(REGIONAL_PARTNER_PLAYBOOKS) == 4

    def test_playbook_entry_has_required_fields(self):
        required = {"deployment_model", "trust_bundle", "pricing_multiplier", "estimated_days"}
        for bundle, regions in REGIONAL_PARTNER_PLAYBOOKS.items():
            for region, entry in regions.items():
                assert required.issubset(entry.keys()), f"{bundle}/{region} missing fields"

    def test_ae_regulated_ops_highest_multiplier_among_regulated(self):
        ae = REGIONAL_PARTNER_PLAYBOOKS["regulated_ops"]["ae"]["pricing_multiplier"]
        us = REGIONAL_PARTNER_PLAYBOOKS["regulated_ops"]["us"]["pricing_multiplier"]
        assert ae > us


# ---- 156D: Sovereign Economics ---------------------------------------------

class TestEconomics:
    def test_basic_economics_keys(self):
        result = compute_sovereign_economics(10000.0, "us", "fedramp_moderate", "regulated_ops", "var")
        assert set(result.keys()) == {"adjusted_revenue", "partner_share", "sovereign_premium", "margin_after_share", "total_cost"}

    def test_partner_share_proportional(self):
        r = compute_sovereign_economics(10000.0, "us", "fedramp_moderate", "regulated_ops", "var")
        # var share is 20% of adjusted revenue
        assert r["partner_share"] == round(r["adjusted_revenue"] * 0.20, 2)

    def test_sovereign_premium_positive(self):
        r = compute_sovereign_economics(10000.0, "eu", "gdpr_standard", "regulated_ops", "msp")
        assert r["sovereign_premium"] > 0


# ---- 156E: Dashboard -------------------------------------------------------

class TestDashboard:
    def test_add_opportunity_tracked(self):
        d = SovereignGlobalDashboard()
        d.add_opportunity("us", "regulated_ops", "var", 10000.0, "fedramp_moderate")
        assert d.summary()["total_opportunities"] == 1

    def test_margin_accumulates(self):
        d = SovereignGlobalDashboard()
        d.add_opportunity("us", "regulated_ops", "var", 10000.0, "fedramp_moderate")
        d.add_opportunity("us", "regulated_ops", "msp", 5000.0, "fedramp_moderate")
        assert d.margin_by_region["us"] > 0

    def test_deployment_mix_counted(self):
        d = SovereignGlobalDashboard()
        d.add_opportunity("us", "regulated_ops", "var", 10000.0, "fedramp_moderate")
        assert "private_cloud" in d.deployment_mix


# ---- 156F: Golden Proof ----------------------------------------------------

class TestGoldenProof:
    def test_golden_proof_passes(self):
        proof = golden_proof_sovereign_scaling()
        assert proof["status"] == "pass"

    def test_golden_proof_dashboard_five_regions(self):
        proof = golden_proof_sovereign_scaling()
        assert len(proof["dashboard_summary"]["regions_active"]) == 5
