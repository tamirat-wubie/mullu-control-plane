"""Phase 155 — Healthcare Financial Governance Suite Tests."""
import pytest
from mcoi_runtime.pilot.healthcare_financial_bundle import (
    BUNDLE_NAME, BUNDLE_PACKS, HEALTHCARE_FINANCIAL_PRICING, STITCHED_WORKFLOWS,
    HealthcareFinancialBundle,
)

class TestBundleDefinition:
    def test_bundle_name(self):
        assert BUNDLE_NAME == "Healthcare Financial Governance Suite"

    def test_two_packs(self):
        assert len(BUNDLE_PACKS) == 2
        assert "healthcare" in BUNDLE_PACKS
        assert "financial_control" in BUNDLE_PACKS

    def test_bundle_discount(self):
        assert HEALTHCARE_FINANCIAL_PRICING.monthly_bundled < HEALTHCARE_FINANCIAL_PRICING.monthly_individual
        assert HEALTHCARE_FINANCIAL_PRICING.annual_savings == 15000.0

    def test_6_stitched_workflows(self):
        assert len(STITCHED_WORKFLOWS) == 6

class TestBundleDeployment:
    def test_deploy_bundle(self):
        bundle = HealthcareFinancialBundle()
        result = bundle.deploy_bundle("hcfin-test-001")
        assert result["status"] == "bundle_ready"
        assert len(result["packs_deployed"]) == 2
        assert result["total_capabilities"] >= 20
        assert result["stitched_workflows"] == 6
        assert result["cross_pack_active"]

    def test_seed_demo(self):
        bundle = HealthcareFinancialBundle()
        bundle.deploy_bundle("hcfin-demo")
        demo = bundle.seed_bundle_demo("hcfin-demo")
        assert demo["status"] == "demo_ready"
        assert demo["healthcare_cases"] == 5
        assert demo["financial_cases"] == 5
        assert demo["evidence_records"] == 6
        assert demo["total_seeded"] == 16

class TestUpgradePath:
    def test_upgrade_healthcare_customer(self):
        bundle = HealthcareFinancialBundle()
        bundle.deploy_bundle("hcfin-upgrade")
        upgrade = bundle.upgrade_healthcare_customer("hcfin-upgrade")
        assert upgrade["status"] == "upgraded"
        assert upgrade["financial_pack_added"]
        assert upgrade["new_monthly_price"] == HEALTHCARE_FINANCIAL_PRICING.monthly_bundled
        assert upgrade["stitched_workflows"] == 6

class TestStitchedWorkflows:
    def test_healthcare_triggers_financial(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "healthcare_triggers_financial_review")
        assert wf.trigger_pack == "healthcare"
        assert wf.target_pack == "financial_control"

    def test_settlement_impacts_care(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "settlement_impacts_care_operations")
        assert wf.trigger_pack == "financial_control"
        assert wf.target_pack == "healthcare"

    def test_all_cross_pack(self):
        for wf in STITCHED_WORKFLOWS:
            assert wf.trigger_pack != wf.target_pack

class TestGoldenProof:
    def test_healthcare_financial_lifecycle(self):
        bundle = HealthcareFinancialBundle()

        # 1. Deploy bundle
        deploy = bundle.deploy_bundle("golden-hcfin")
        assert deploy["status"] == "bundle_ready"
        assert deploy["total_capabilities"] >= 20

        # 2. Seed cross-pack demo
        demo = bundle.seed_bundle_demo("golden-hcfin")
        assert demo["total_seeded"] >= 16

        # 3. Stitched workflows
        assert len(STITCHED_WORKFLOWS) == 6

        # 4. Upgrade path
        upgrade = bundle.upgrade_healthcare_customer("golden-hcfin")
        assert upgrade["status"] == "upgraded"
        assert upgrade["new_monthly_price"] == 5750.0

        # 5. Pricing saves money
        assert HEALTHCARE_FINANCIAL_PRICING.annual_savings == 15000.0

        # 6. Both packs active
        assert len(deploy["packs_deployed"]) == 2
