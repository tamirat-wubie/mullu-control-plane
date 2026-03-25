"""Phase 157 — Public Sector Governance Suite Tests."""
import pytest
from mcoi_runtime.pilot.public_sector_bundle import (
    BUNDLE_NAME, BUNDLE_PACKS, PUBLIC_SECTOR_BUNDLE_PRICING, STITCHED_WORKFLOWS,
    SOVEREIGN_BUNDLE_CONFIG, PublicSectorGovernanceBundle,
)


class TestBundleDefinition:
    def test_bundle_name(self):
        assert BUNDLE_NAME == "Public Sector Governance Suite"

    def test_two_packs(self):
        assert len(BUNDLE_PACKS) == 2
        assert "public_sector" in BUNDLE_PACKS
        assert "regulated_ops" in BUNDLE_PACKS

    def test_bundle_discount(self):
        assert PUBLIC_SECTOR_BUNDLE_PRICING.monthly_bundled < PUBLIC_SECTOR_BUNDLE_PRICING.monthly_individual
        assert PUBLIC_SECTOR_BUNDLE_PRICING.annual_savings == 12000.0
        assert PUBLIC_SECTOR_BUNDLE_PRICING.discount_percent == 20.0

    def test_6_stitched_workflows(self):
        assert len(STITCHED_WORKFLOWS) == 6


class TestBundleDeployment:
    def test_deploy_bundle(self):
        bundle = PublicSectorGovernanceBundle()
        result = bundle.deploy_bundle("psgov-test-001")
        assert result["status"] == "bundle_ready"
        assert len(result["packs_deployed"]) == 2
        assert result["total_capabilities"] >= 20
        assert result["stitched_workflows"] == 6
        assert result["cross_pack_active"]

    def test_seed_demo(self):
        bundle = PublicSectorGovernanceBundle()
        bundle.deploy_bundle("psgov-demo")
        demo = bundle.seed_bundle_demo("psgov-demo")
        assert demo["status"] == "demo_ready"
        assert demo["public_sector_cases"] == 5
        assert demo["regulated_cases"] == 5
        assert demo["evidence_records"] == 6
        assert demo["total_seeded"] == 16


class TestUpgradePath:
    def test_upgrade_public_sector_customer(self):
        bundle = PublicSectorGovernanceBundle()
        bundle.deploy_bundle("psgov-upgrade")
        upgrade = bundle.upgrade_public_sector_customer("psgov-upgrade")
        assert upgrade["status"] == "upgraded"
        assert upgrade["regulated_ops_added"]
        assert upgrade["new_monthly_price"] == PUBLIC_SECTOR_BUNDLE_PRICING.monthly_bundled
        assert upgrade["stitched_workflows"] == 6


class TestStitchedWorkflows:
    def test_case_escalates_to_regulated(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "case_escalates_to_regulated_remediation")
        assert wf.trigger_pack == "public_sector"
        assert wf.target_pack == "regulated_ops"

    def test_copilot_cross_evidence(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "copilot_cross_evidence")
        assert wf.trigger_pack == "public_sector"
        assert wf.target_pack == "regulated_ops"

    def test_all_cross_pack(self):
        for wf in STITCHED_WORKFLOWS:
            assert wf.trigger_pack != wf.target_pack


class TestSovereignPackaging:
    def test_all_four_profiles_compatible(self):
        profiles = SOVEREIGN_BUNDLE_CONFIG["profile_compatibility"]
        assert len(profiles) == 4
        assert "sovereign_cloud" in profiles
        assert "restricted_network" in profiles
        assert "on_prem" in profiles
        assert "partner_operated" in profiles

    def test_copilot_explain_only_for_restricted_classified(self):
        modes = SOVEREIGN_BUNDLE_CONFIG["copilot_mode_defaults"]
        assert modes["restricted_network"] == "explain_only"
        assert modes["restricted"] == "explain_only"
        assert modes["classified"] == "explain_only"
        assert SOVEREIGN_BUNDLE_CONFIG["procurement_package_included"] is True


class TestGoldenProof:
    def test_public_sector_governance_lifecycle(self):
        bundle = PublicSectorGovernanceBundle()

        # 1. Deploy bundle
        deploy = bundle.deploy_bundle("golden-psgov")
        assert deploy["status"] == "bundle_ready"
        assert deploy["total_capabilities"] >= 20

        # 2. Seed cross-pack demo
        demo = bundle.seed_bundle_demo("golden-psgov")
        assert demo["total_seeded"] >= 16

        # 3. Stitched workflows
        assert len(STITCHED_WORKFLOWS) == 6

        # 4. Upgrade path
        upgrade = bundle.upgrade_public_sector_customer("golden-psgov")
        assert upgrade["status"] == "upgraded"
        assert upgrade["new_monthly_price"] == 4000.0

        # 5. Pricing saves money
        assert PUBLIC_SECTOR_BUNDLE_PRICING.annual_savings == 12000.0

        # 6. Both packs active
        assert len(deploy["packs_deployed"]) == 2
