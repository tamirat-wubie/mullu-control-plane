"""Phase 165 — Scientific Governance Suite Tests."""
import pytest
from mcoi_runtime.pilot.research_regulated_bundle import (
    BUNDLE_NAME, BUNDLE_PACKS, SCIENTIFIC_GOVERNANCE_PRICING, STITCHED_WORKFLOWS,
    ScientificGovernanceBundle,
)


class TestBundleDefinition:
    def test_bundle_name(self):
        assert BUNDLE_NAME == "Scientific Governance Suite"

    def test_two_packs(self):
        assert len(BUNDLE_PACKS) == 2
        assert "research_lab" in BUNDLE_PACKS
        assert "regulated_ops" in BUNDLE_PACKS

    def test_bundle_discount(self):
        assert SCIENTIFIC_GOVERNANCE_PRICING.monthly_bundled < SCIENTIFIC_GOVERNANCE_PRICING.monthly_individual
        assert SCIENTIFIC_GOVERNANCE_PRICING.annual_savings == 9000.0
        assert SCIENTIFIC_GOVERNANCE_PRICING.discount_percent == 15.0

    def test_5_stitched_workflows(self):
        assert len(STITCHED_WORKFLOWS) == 5


class TestBundleDeployment:
    def test_deploy_bundle(self):
        bundle = ScientificGovernanceBundle()
        result = bundle.deploy_bundle("scg-test-001")
        assert result["status"] == "bundle_ready"
        assert len(result["packs_deployed"]) == 2
        assert result["total_capabilities"] >= 20
        assert result["stitched_workflows"] == 5
        assert result["cross_pack_active"]

    def test_seed_demo(self):
        bundle = ScientificGovernanceBundle()
        bundle.deploy_bundle("scg-demo")
        demo = bundle.seed_bundle_demo("scg-demo")
        assert demo["status"] == "demo_ready"
        assert demo["research_cases"] == 5
        assert demo["regulated_cases"] == 5
        assert demo["evidence_records"] == 5
        assert demo["total_seeded"] == 15


class TestUpgradePath:
    def test_upgrade_research_customer(self):
        bundle = ScientificGovernanceBundle()
        bundle.deploy_bundle("scg-upgrade")
        upgrade = bundle.upgrade_research_customer("scg-upgrade")
        assert upgrade["status"] == "upgraded"
        assert upgrade["regulated_ops_added"]
        assert upgrade["new_monthly_price"] == SCIENTIFIC_GOVERNANCE_PRICING.monthly_bundled
        assert upgrade["stitched_workflows"] == 5


class TestStitchedWorkflows:
    def test_research_finding_triggers_compliance_review(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "research_finding_triggers_compliance_review")
        assert wf.trigger_pack == "research_lab"
        assert wf.target_pack == "regulated_ops"

    def test_regulatory_requirement_opens_study(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "regulatory_requirement_opens_study")
        assert wf.trigger_pack == "regulated_ops"
        assert wf.target_pack == "research_lab"

    def test_copilot_cross_scientific_regulatory(self):
        wf = next(w for w in STITCHED_WORKFLOWS if w.name == "copilot_cross_scientific_regulatory")
        assert wf.trigger_pack == "research_lab"
        assert wf.target_pack == "regulated_ops"


class TestGoldenProof:
    def test_scientific_governance_lifecycle(self):
        bundle = ScientificGovernanceBundle()

        # 1. Deploy bundle
        deploy = bundle.deploy_bundle("golden-scg")
        assert deploy["status"] == "bundle_ready"
        assert deploy["total_capabilities"] >= 20

        # 2. Seed cross-pack demo
        demo = bundle.seed_bundle_demo("golden-scg")
        assert demo["total_seeded"] >= 15

        # 3. Stitched workflows
        assert len(STITCHED_WORKFLOWS) == 5

        # 4. Upgrade path
        upgrade = bundle.upgrade_research_customer("golden-scg")
        assert upgrade["status"] == "upgraded"
        assert upgrade["new_monthly_price"] == 4250.0

        # 5. Pricing saves money
        assert SCIENTIFIC_GOVERNANCE_PRICING.annual_savings == 9000.0

        # 6. Both packs active
        assert len(deploy["packs_deployed"]) == 2
