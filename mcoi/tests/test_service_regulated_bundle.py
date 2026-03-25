"""Phase 158 — Enterprise Service Governance Suite Tests."""
import pytest
from mcoi_runtime.pilot.service_regulated_bundle import (
    BUNDLE_NAME, BUNDLE_PACKS, SERVICE_REGULATED_BUNDLE_PRICING, STITCHED_WORKFLOWS,
    ServiceRegulatedBundle,
)


class TestBundleDefinition:
    def test_bundle_name(self):
        assert BUNDLE_NAME == "Enterprise Service Governance Suite"

    def test_two_packs(self):
        assert len(BUNDLE_PACKS) == 2
        assert "enterprise_service" in BUNDLE_PACKS
        assert "regulated_ops" in BUNDLE_PACKS

    def test_bundle_discount(self):
        assert SERVICE_REGULATED_BUNDLE_PRICING.monthly_bundled < SERVICE_REGULATED_BUNDLE_PRICING.monthly_individual
        assert SERVICE_REGULATED_BUNDLE_PRICING.annual_savings == 12000.0
        assert SERVICE_REGULATED_BUNDLE_PRICING.discount_percent == 20.0

    def test_6_stitched_workflows(self):
        assert len(STITCHED_WORKFLOWS) == 6


class TestBundleDeployment:
    def test_deploy_bundle(self):
        bundle = ServiceRegulatedBundle()
        result = bundle.deploy_bundle("srg-test-001")
        assert result["status"] == "bundle_ready"
        assert len(result["packs_deployed"]) == 2
        assert result["total_capabilities"] >= 20
        assert result["stitched_workflows"] == 6
        assert result["cross_pack_active"]

    def test_seed_demo(self):
        bundle = ServiceRegulatedBundle()
        bundle.deploy_bundle("srg-demo")
        demo = bundle.seed_bundle_demo("srg-demo")
        assert demo["status"] == "demo_ready"
        assert demo["service_cases"] == 5
        assert demo["regulated_cases"] == 5
        assert demo["evidence_records"] == 6
        assert demo["total_seeded"] == 16


class TestUpgradePath:
    def test_upgrade_service_customer(self):
        bundle = ServiceRegulatedBundle()
        bundle.deploy_bundle("srg-upgrade")
        upgrade = bundle.upgrade_service_customer("srg-upgrade")
        assert upgrade["status"] == "upgraded"
        assert upgrade["regulated_ops_added"]
        assert upgrade["new_monthly_price"] == SERVICE_REGULATED_BUNDLE_PRICING.monthly_bundled
        assert upgrade["stitched_workflows"] == 6


class TestStitchedWorkflows:
    def test_service_incident_escalates_to_compliance(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "service_incident_escalates_to_compliance")
        assert wf.trigger_pack == "enterprise_service"
        assert wf.target_pack == "regulated_ops"

    def test_copilot_cross_domain_evidence(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "copilot_cross_domain_evidence")
        assert wf.trigger_pack == "enterprise_service"
        assert wf.target_pack == "regulated_ops"


class TestGoldenProof:
    def test_service_regulated_lifecycle(self):
        bundle = ServiceRegulatedBundle()

        # 1. Deploy bundle
        deploy = bundle.deploy_bundle("golden-srg")
        assert deploy["status"] == "bundle_ready"
        assert deploy["total_capabilities"] >= 20

        # 2. Seed cross-pack demo
        demo = bundle.seed_bundle_demo("golden-srg")
        assert demo["total_seeded"] >= 16

        # 3. Stitched workflows
        assert len(STITCHED_WORKFLOWS) == 6

        # 4. Upgrade path
        upgrade = bundle.upgrade_service_customer("golden-srg")
        assert upgrade["status"] == "upgraded"
        assert upgrade["new_monthly_price"] == 4000.0

        # 5. Pricing saves money
        assert SERVICE_REGULATED_BUNDLE_PRICING.annual_savings == 12000.0

        # 6. Both packs active
        assert len(deploy["packs_deployed"]) == 2
