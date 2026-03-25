"""Phase 144 — Delivery Automation / Implementation Orchestrator Tests."""
import pytest
from mcoi_runtime.pilot.delivery_orchestrator import (
    BUNDLE_DEPLOYMENT_PLANS, DeploymentOrchestrator,
    CapacitySnapshot, BUNDLE_INCIDENT_TEMPLATES,
    MarginProtector, delivery_dashboard,
)

class TestDeploymentPlans:
    def test_3_plan_types(self):
        assert len(BUNDLE_DEPLOYMENT_PLANS) == 3

    def test_single_pack_steps(self):
        assert len(BUNDLE_DEPLOYMENT_PLANS["single_pack"]) == 8

    def test_digital_bundle_steps(self):
        assert len(BUNDLE_DEPLOYMENT_PLANS["regulated_financial_bundle"]) == 12

    def test_industrial_bundle_steps(self):
        assert len(BUNDLE_DEPLOYMENT_PLANS["industrial_suite_bundle"]) == 13

class TestOrchestrator:
    def test_start_deployment(self):
        orch = DeploymentOrchestrator()
        steps = orch.start_deployment("c1", "regulated_financial_bundle")
        assert len(steps) == 12
        assert orch.active_deployments == 1

    def test_complete_steps(self):
        orch = DeploymentOrchestrator()
        orch.start_deployment("c1", "single_pack")
        for i in range(1, 9):
            orch.complete_step("c1", i)
        p = orch.progress("c1")
        assert p["is_live"]
        assert p["percent"] == 100.0

    def test_progress_tracking(self):
        orch = DeploymentOrchestrator()
        orch.start_deployment("c1", "industrial_suite_bundle")
        orch.complete_step("c1", 1)
        orch.complete_step("c1", 2)
        p = orch.progress("c1")
        assert p["steps_completed"] == 2
        assert p["steps_total"] == 13
        assert p["hours_remaining"] > 0

class TestCapacity:
    def test_healthy(self):
        cap = CapacitySnapshot(5, 3, 120.0, 200.0)
        assert cap.status == "healthy"

    def test_overloaded(self):
        cap = CapacitySnapshot(5, 8, 190.0, 200.0)
        assert cap.status == "overloaded"

class TestMarginProtection:
    def test_underpriced_flagged(self):
        mp = MarginProtector()
        risks = mp.evaluate("c1", "regulated_financial_bundle", 3000.0, 40, 5, 2)
        assert any(r.risk_type == "underpriced" for r in risks)

    def test_clean_deal(self):
        mp = MarginProtector()
        risks = mp.evaluate("c1", "regulated_financial_bundle", 4500.0, 40, 5, 2)
        assert len(risks) == 0

    def test_over_customized(self):
        mp = MarginProtector()
        risks = mp.evaluate("c1", "single_pack", 2500.0, 40, 5, 12)
        assert any(r.risk_type == "over_customized" for r in risks)

class TestIncidentTemplates:
    def test_templates_exist(self):
        assert len(BUNDLE_INCIDENT_TEMPLATES) == 2
        assert "regulated_financial_bundle" in BUNDLE_INCIDENT_TEMPLATES
        assert "industrial_suite_bundle" in BUNDLE_INCIDENT_TEMPLATES

class TestGoldenProof:
    def test_full_delivery_automation(self):
        # 1. Digital bundle deploys from template
        orch = DeploymentOrchestrator()
        steps = orch.start_deployment("digital-1", "regulated_financial_bundle")
        assert len(steps) == 12
        for s in steps:
            orch.complete_step("digital-1", s.step)
        assert orch.progress("digital-1")["is_live"]

        # 2. Industrial bundle deploys from template
        orch.start_deployment("industrial-1", "industrial_suite_bundle")
        for i in range(1, 14):
            orch.complete_step("industrial-1", i)
        assert orch.progress("industrial-1")["is_live"]

        # 3. Capacity visible
        cap = CapacitySnapshot(5, 2, 100.0, 200.0, ["digital_twin_specialist"])
        assert cap.status == "healthy"

        # 4. Support templates exist
        assert len(BUNDLE_INCIDENT_TEMPLATES["industrial_suite_bundle"]) >= 3

        # 5. Margin risk flagged
        mp = MarginProtector()
        mp.evaluate("risky-1", "industrial_suite_bundle", 4000.0, 90, 9, 8)
        assert len(mp.high_risks()) >= 1

        # 6. Executive dashboard
        d = delivery_dashboard(orch, cap, mp)
        assert d["active_deployments"] == 2
        assert d["capacity_status"] == "healthy"
        assert d["margin_risks_high"] >= 1
        assert d["bundle_templates_available"] == 3
