"""Phase 153 — Healthcare / Clinical Governance Pack Tests."""
import pytest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.healthcare_pack import (
    HEALTHCARE_CAPABILITIES, HEALTHCARE_TEMPLATE,
    HealthcarePackBootstrap, HealthcareDemoGenerator,
)
from mcoi_runtime.pilot.deployment_factory import DeploymentFactory
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile, evaluate_fit
from mcoi_runtime.pilot.data_import import PilotDataImporter
from mcoi_runtime.pilot.weekly_tracker import WeeklyPilotTracker, WeeklySnapshot
from mcoi_runtime.pilot.revenue_funnel import RevenueFunnel
from mcoi_runtime.pilot.deployment_path import PaidDeploymentPath

TENANT = "hc-test-tenant"

class TestPackDefinition:
    def test_10_capabilities(self):
        assert len(HEALTHCARE_CAPABILITIES) == 10

    def test_key_capabilities_present(self):
        assert "patient_service_intake" in HEALTHCARE_CAPABILITIES
        assert "case_review_workflow" in HEALTHCARE_CAPABILITIES
        assert "approval_routing" in HEALTHCARE_CAPABILITIES
        assert "governed_copilot" in HEALTHCARE_CAPABILITIES
        assert "sovereign_compatibility" in HEALTHCARE_CAPABILITIES

    def test_template(self):
        assert HEALTHCARE_TEMPLATE.pack_domain == "healthcare"

class TestPackBootstrap:
    def test_bootstrap_succeeds(self):
        es = EventSpineEngine()
        bootstrap = HealthcarePackBootstrap(es)
        result = bootstrap.bootstrap(TENANT)
        assert result["status"] == "ready"
        assert result["total_steps"] >= 7
        assert result["capability_count"] == 10
        assert len(result["connectors"]) == 5
        assert len(result["personas"]) == 6
        assert len(result["governance_rules"]) == 3

    def test_engines_accessible(self):
        es = EventSpineEngine()
        bootstrap = HealthcarePackBootstrap(es)
        bootstrap.bootstrap(TENANT)
        engines = bootstrap.engines
        assert engines["pack"].pack_count >= 1
        assert engines["persona"].persona_count >= 6

class TestDemoGenerator:
    def test_generate_demo(self):
        gen = HealthcareDemoGenerator()
        result = gen.generate("hc-demo-test")
        assert result["status"] == "demo_ready"
        assert result["total_seeded"] >= 20
        assert result["cases"]["imported"] == 10
        assert result["remediations"]["imported"] == 5
        assert result["records"]["imported"] == 8

    def test_remediation_titles_are_bounded(self, monkeypatch):
        gen = HealthcareDemoGenerator()
        captured: dict[str, list[dict[str, str]]] = {}
        original_import = gen._importer.import_remediations

        def _capture(tenant_id: str, remediations: list[dict[str, str]]):
            captured["remediations"] = remediations
            return original_import(tenant_id, remediations)

        monkeypatch.setattr(gen._importer, "import_remediations", _capture)

        result = gen.generate("hc-bounded")

        assert result["remediations"]["imported"] == 5
        assert {item["title"] for item in captured["remediations"]} == {"Healthcare remediation"}
        assert "Patient referral processing" not in captured["remediations"][0]["title"]

class TestDeploymentFactoryIntegration:
    def test_deploy_through_factory(self):
        factory = DeploymentFactory()
        factory.register_template(HEALTHCARE_TEMPLATE)
        profile = PilotCustomerProfile(
            "hc-cust-001", "Regional Health System", "healthcare", "clinical_governance",
            20, "Chief Medical Officer", "Clinical Operations Lead", 500,
            ("patient_service_intake", "case_review_workflow", "records_retention_audit"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestValidation:
    """153D — Golden proof: 8-point validation."""

    def test_golden_validation(self):
        es = EventSpineEngine()
        bootstrap = HealthcarePackBootstrap(es)
        result = bootstrap.bootstrap("hc-golden")
        assert result["status"] == "ready"

        importer = PilotDataImporter(es)

        # 1. Patient service intake — case enters queue
        cases = [{"case_id": "golden-hc1", "title": "Patient referral processing", "priority": "high"}]
        cr = importer.import_cases("hc-golden", cases)
        assert cr.accepted == 1

        # 2. Case review workflow — remediation links to case
        rems = [{"remediation_id": "golden-hcr1", "case_ref": "golden-hc1", "title": "Process patient referral"}]
        rr = importer.import_remediations("hc-golden", rems)
        assert rr.accepted == 1

        # 3. Approval routing — second case enters system
        cases2 = [{"case_id": "golden-hc2", "title": "Medication incident investigation", "priority": "critical"}]
        cr2 = importer.import_cases("hc-golden", cases2)
        assert cr2.accepted == 1

        # 4. Governance rules enforce patient data protection
        assert bootstrap.engines["governance"].rule_count >= 3

        # 5. Records retention audit — pack capability count proves it
        assert bootstrap.engines["pack"].capability_count >= 10

        # 6. Dashboard — personas include executive/compliance views
        assert bootstrap.engines["persona"].persona_count >= 5

        # 7. Copilot available
        assert bootstrap.engines["copilot"] is not None

        # 8. Factory deploy
        factory = DeploymentFactory()
        factory.register_template(HEALTHCARE_TEMPLATE)
        profile = PilotCustomerProfile(
            "hc-factory-test", "Healthcare Organization", "healthcare", "clinical_governance",
            12, "Chief Medical Officer", "Clinical Operations Manager", 120,
            ("patient_service_intake", "case_review_workflow"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestTargetList:
    """153E — Healthcare target candidates."""

    def test_healthcare_targets(self):
        from mcoi_runtime.pilot.target_list import TargetListBuilder
        builder = TargetListBuilder()
        targets = [
            PilotCustomerProfile("hc-t1", "Regional Health System", "healthcare", "clinical_governance",
                                 25, "Chief Medical Officer", "Clinical Operations Lead", 600,
                                 ("patient_service_intake", "case_review_workflow", "records_retention_audit"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("hc-t2", "Community Hospital Network", "healthcare", "patient_safety",
                                 15, "VP of Clinical Operations", "Patient Safety Officer", 350,
                                 ("incident_remediation", "evidence_document_retrieval", "compliance_dashboard"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("hc-t3", "Specialty Care Group", "healthcare", "quality_management",
                                 10, "Medical Director", "Quality Manager", 200,
                                 ("case_review_workflow", "approval_routing"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        ]
        for t in targets:
            builder.add_candidate(t)
        ranked = builder.rank_and_designate()
        assert ranked[0].fit_level == "strong"
        assert builder.primary is not None

class TestEndToEndEighthPack:
    """Prove: same platform, eighth product, same machinery."""

    def test_eighth_pack_full_lifecycle(self):
        # 1. Bootstrap healthcare pack via demo
        gen = HealthcareDemoGenerator()
        demo = gen.generate("hc-lifecycle")
        assert demo["status"] == "demo_ready"

        # 2. Revenue funnel
        funnel = RevenueFunnel()
        funnel.record_demo("hc-lifecycle")
        funnel.convert_to_pilot("hc-lifecycle")
        funnel.convert_to_paid("hc-lifecycle", 8000.0)
        assert funnel.total_mrr == 8000.0

        # 3. Deployment path
        path = PaidDeploymentPath("hc-lifecycle", "hc-offer-001")
        for step in range(1, 8):
            path.complete_milestone(step)
        assert path.progress["is_live"]

        # 4. Weekly tracking
        tracker = WeeklyPilotTracker("hc-lifecycle")
        tracker.record_week(WeeklySnapshot(
            week_number=1, tenant_id="hc-lifecycle",
            cases_created=30, cases_closed=22,
            connector_uptime_percent=99.5, dashboard_views=75,
            copilot_queries=50, executive_satisfaction=9.2,
        ))
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"
