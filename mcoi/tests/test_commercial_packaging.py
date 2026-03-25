"""Phase 125 — Commercial Packaging Tests."""
import pytest
from mcoi_runtime.pilot.product_definition import (
    PRODUCT_NAME, PRODUCT_VERSION, V1_CAPABILITIES, IN_SCOPE, OUT_OF_SCOPE,
    DEPLOYMENT_PREREQUISITES, INTEGRATION_PREREQUISITES,
)
from mcoi_runtime.pilot.demo_generator import DemoTenantGenerator
from mcoi_runtime.pilot.pricing_model import ALL_TIERS, PILOT_TIER, STANDARD_TIER, ENTERPRISE_TIER, ADD_ONS
from mcoi_runtime.pilot.onboarding import ONBOARDING_FLOW, TOTAL_ESTIMATED_MINUTES, onboarding_summary
from mcoi_runtime.pilot.pilot_metrics import PilotMetrics

class TestProductDefinition:
    def test_product_name(self):
        assert PRODUCT_NAME == "Regulated Operations Control Tower"
    def test_version(self):
        assert PRODUCT_VERSION == "1.0.0"
    def test_in_scope_count(self):
        assert len(IN_SCOPE) == 10
    def test_out_of_scope_count(self):
        assert len(OUT_OF_SCOPE) == 5
    def test_all_in_scope_are_core(self):
        for c in IN_SCOPE:
            assert c.in_scope is True
    def test_deployment_prerequisites(self):
        assert len(DEPLOYMENT_PREREQUISITES) >= 3
    def test_integration_prerequisites(self):
        assert len(INTEGRATION_PREREQUISITES) == 5

class TestDemoGenerator:
    def test_generate_demo(self):
        gen = DemoTenantGenerator()
        result = gen.generate("demo-test")
        assert result["status"] == "demo_ready"
        assert result["total_seeded_items"] >= 20
        assert "bootstrap" in result["sections"]
        assert "cases" in result["sections"]
    def test_demo_has_cases(self):
        gen = DemoTenantGenerator()
        result = gen.generate("demo-test-2")
        assert result["cases"]["imported"] == 10
    def test_demo_has_remediations(self):
        gen = DemoTenantGenerator()
        result = gen.generate("demo-test-3")
        assert result["remediations"]["imported"] == 5
    def test_demo_has_records(self):
        gen = DemoTenantGenerator()
        result = gen.generate("demo-test-4")
        assert result["records"]["imported"] == 8

class TestPricingModel:
    def test_three_tiers(self):
        assert len(ALL_TIERS) == 3
    def test_pilot_is_free(self):
        assert PILOT_TIER.base_price_monthly == 0.0
    def test_standard_price(self):
        assert STANDARD_TIER.base_price_monthly > 0
    def test_enterprise_has_all_features(self):
        assert ENTERPRISE_TIER.copilot_included
        assert ENTERPRISE_TIER.multimodal_included
        assert ENTERPRISE_TIER.self_tuning_included
    def test_add_ons_exist(self):
        assert len(ADD_ONS) >= 4
    def test_pilot_includes_copilot(self):
        assert PILOT_TIER.copilot_included is True
    def test_pilot_no_multimodal(self):
        assert PILOT_TIER.multimodal_included is False

class TestOnboarding:
    def test_14_steps(self):
        assert len(ONBOARDING_FLOW) == 14
    def test_total_time_reasonable(self):
        assert 120 <= TOTAL_ESTIMATED_MINUTES <= 300
    def test_summary(self):
        s = onboarding_summary()
        assert s["total_steps"] == 14
        assert s["categories"]["setup"] >= 2
        assert s["categories"]["connect"] >= 4
        assert s["categories"]["verify"] >= 2

class TestPilotMetrics:
    def test_create_metrics(self):
        m = PilotMetrics(tenant_id="t1")
        assert m.tenant_id == "t1"
        assert m.setup_time_minutes == 0.0
    def test_health_summary_healthy(self):
        m = PilotMetrics(tenant_id="t1", import_success_rate=0.95, evidence_completeness_rate=0.9, operator_satisfaction_score=8.0)
        assert m.health_summary == "healthy"
    def test_health_summary_issues(self):
        m = PilotMetrics(tenant_id="t1", import_success_rate=0.5, evidence_completeness_rate=0.5, operator_satisfaction_score=3.0)
        assert "attention_needed" in m.health_summary
    def test_to_dict(self):
        m = PilotMetrics(tenant_id="t1", setup_time_minutes=45.0)
        d = m.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["setup_time_minutes"] == 45.0
