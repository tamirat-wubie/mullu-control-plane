"""Phase 142 — Regulated Financial Control Suite Bundle Tests."""
import pytest
from mcoi_runtime.pilot.regulated_financial_bundle import (
    BUNDLE_NAME, BUNDLE_PACKS, BUNDLE_PRICING, STITCHED_WORKFLOWS,
    RegulatedFinancialBundle,
)

class TestBundleDefinition:
    def test_bundle_name(self):
        assert BUNDLE_NAME == "Regulated Financial Control Suite"

    def test_two_packs(self):
        assert len(BUNDLE_PACKS) == 2
        assert "regulated_ops" in BUNDLE_PACKS
        assert "financial_control" in BUNDLE_PACKS

    def test_bundle_discount(self):
        assert BUNDLE_PRICING.monthly_bundled < BUNDLE_PRICING.monthly_individual
        assert BUNDLE_PRICING.annual_savings > 0

    def test_5_stitched_workflows(self):
        assert len(STITCHED_WORKFLOWS) == 5

class TestBundleDeployment:
    def test_deploy_bundle(self):
        bundle = RegulatedFinancialBundle()
        result = bundle.deploy_bundle("bundle-test-001")
        assert result["status"] == "bundle_ready"
        assert len(result["packs_deployed"]) == 2
        assert result["total_capabilities"] >= 20
        assert result["stitched_workflows"] == 5
        assert result["cross_pack_active"]

    def test_seed_demo(self):
        bundle = RegulatedFinancialBundle()
        bundle.deploy_bundle("bundle-demo")
        demo = bundle.seed_bundle_demo("bundle-demo")
        assert demo["status"] == "demo_ready"
        assert demo["regulatory_cases"] == 5
        assert demo["financial_cases"] == 5
        assert demo["evidence_records"] == 5
        assert demo["total_seeded"] == 15

class TestUpgradePath:
    def test_upgrade_existing(self):
        bundle = RegulatedFinancialBundle()
        bundle.deploy_bundle("upgrade-test")
        upgrade = bundle.upgrade_existing_customer("upgrade-test")
        assert upgrade["status"] == "upgraded"
        assert upgrade["financial_pack_added"]
        assert upgrade["new_monthly_price"] == BUNDLE_PRICING.monthly_bundled
        assert upgrade["stitched_workflows"] == 5

class TestStitchedWorkflows:
    def test_case_triggers_financial(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "case_triggers_financial_review")
        assert wf.trigger_pack == "regulated_ops"
        assert wf.target_pack == "financial_control"

    def test_dispute_triggers_remediation(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "dispute_triggers_remediation")
        assert wf.trigger_pack == "financial_control"
        assert wf.target_pack == "regulated_ops"

    def test_all_cross_pack(self):
        for wf in STITCHED_WORKFLOWS:
            assert wf.trigger_pack != wf.target_pack

class TestGoldenProof:
    def test_flagship_to_bundle_lifecycle(self):
        bundle = RegulatedFinancialBundle()

        # 1. Deploy bundle
        deploy = bundle.deploy_bundle("golden-bundle")
        assert deploy["status"] == "bundle_ready"
        assert deploy["total_capabilities"] >= 20

        # 2. Seed cross-pack demo
        demo = bundle.seed_bundle_demo("golden-bundle")
        assert demo["total_seeded"] >= 15

        # 3. Verify stitched workflows defined
        assert len(STITCHED_WORKFLOWS) == 5

        # 4. Upgrade path works
        upgrade = bundle.upgrade_existing_customer("golden-bundle")
        assert upgrade["status"] == "upgraded"
        assert upgrade["new_monthly_price"] == 4500.0

        # 5. Bundle pricing saves money
        assert BUNDLE_PRICING.annual_savings == 12000.0

        # 6. Both packs active
        assert len(deploy["packs_deployed"]) == 2
