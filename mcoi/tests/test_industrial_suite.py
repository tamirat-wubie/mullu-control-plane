"""Phase 143 — Industrial Operations Suite Tests."""
import pytest
from mcoi_runtime.pilot.industrial_suite import (
    BUNDLE_NAME, BUNDLE_PACKS, INDUSTRIAL_PRICING, STITCHED_WORKFLOWS,
    IndustrialSuiteBundle,
)

class TestBundleDefinition:
    def test_bundle_name(self):
        assert BUNDLE_NAME == "Industrial Operations Suite"

    def test_two_packs(self):
        assert len(BUNDLE_PACKS) == 2
        assert "factory_quality" in BUNDLE_PACKS
        assert "supply_chain" in BUNDLE_PACKS

    def test_bundle_discount(self):
        assert INDUSTRIAL_PRICING.monthly_bundled < INDUSTRIAL_PRICING.monthly_individual
        assert INDUSTRIAL_PRICING.annual_savings == 18000.0

    def test_6_stitched_workflows(self):
        assert len(STITCHED_WORKFLOWS) == 6

class TestBundleDeployment:
    def test_deploy_bundle(self):
        bundle = IndustrialSuiteBundle()
        result = bundle.deploy_bundle("ind-test-001")
        assert result["status"] == "bundle_ready"
        assert len(result["packs_deployed"]) == 2
        assert result["total_capabilities"] >= 20
        assert result["stitched_workflows"] == 6

    def test_seed_demo(self):
        bundle = IndustrialSuiteBundle()
        bundle.deploy_bundle("ind-demo")
        demo = bundle.seed_bundle_demo("ind-demo")
        assert demo["status"] == "demo_ready"
        assert demo["factory_cases"] == 5
        assert demo["supply_chain_cases"] == 5
        assert demo["evidence_records"] == 8
        assert demo["total_seeded"] == 18

class TestUpgradePath:
    def test_upgrade_factory_customer(self):
        bundle = IndustrialSuiteBundle()
        bundle.deploy_bundle("upgrade-ind")
        upgrade = bundle.upgrade_factory_customer("upgrade-ind")
        assert upgrade["status"] == "upgraded"
        assert upgrade["supply_chain_added"]
        assert upgrade["new_monthly_price"] == INDUSTRIAL_PRICING.monthly_bundled

class TestStitchedWorkflows:
    def test_downtime_triggers_procurement(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "downtime_triggers_procurement")
        assert wf.trigger_pack == "factory_quality"
        assert wf.target_pack == "supply_chain"

    def test_supplier_delay_impacts_production(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "supplier_delay_impacts_production")
        assert wf.trigger_pack == "supply_chain"
        assert wf.target_pack == "factory_quality"

    def test_all_cross_pack(self):
        for wf in STITCHED_WORKFLOWS:
            assert wf.trigger_pack != wf.target_pack

class TestGoldenProof:
    def test_industrial_suite_lifecycle(self):
        bundle = IndustrialSuiteBundle()

        # 1. Deploy
        deploy = bundle.deploy_bundle("golden-ind")
        assert deploy["status"] == "bundle_ready"
        assert deploy["total_capabilities"] >= 20

        # 2. Seed demo
        demo = bundle.seed_bundle_demo("golden-ind")
        assert demo["total_seeded"] >= 15

        # 3. Stitched workflows
        assert len(STITCHED_WORKFLOWS) == 6

        # 4. Upgrade path
        upgrade = bundle.upgrade_factory_customer("golden-ind")
        assert upgrade["status"] == "upgraded"
        assert upgrade["new_monthly_price"] == 6500.0

        # 5. Pricing saves money
        assert INDUSTRIAL_PRICING.annual_savings == 18000.0

        # 6. Both packs active
        assert len(deploy["packs_deployed"]) == 2
