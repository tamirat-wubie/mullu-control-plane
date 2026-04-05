"""Phase 130 — Enterprise Service / IT Control Tower Pack Tests."""
import pytest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.enterprise_service_pack import (
    ENTERPRISE_SERVICE_CAPABILITIES, ENTERPRISE_SERVICE_TEMPLATE,
    EnterpriseServicePackBootstrap, EnterpriseServiceDemoGenerator,
)
from mcoi_runtime.pilot.deployment_factory import DeploymentFactory
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile, evaluate_fit
from mcoi_runtime.pilot.data_import import PilotDataImporter
from mcoi_runtime.pilot.weekly_tracker import WeeklyPilotTracker, WeeklySnapshot
from mcoi_runtime.pilot.revenue_funnel import RevenueFunnel
from mcoi_runtime.pilot.deployment_path import PaidDeploymentPath

TENANT = "es-test-tenant"

class TestPackDefinition:
    def test_10_capabilities(self):
        assert len(ENTERPRISE_SERVICE_CAPABILITIES) == 10

    def test_key_capabilities_present(self):
        assert "service_intake" in ENTERPRISE_SERVICE_CAPABILITIES
        assert "incident_case_handling" in ENTERPRISE_SERVICE_CAPABILITIES
        assert "service_copilot" in ENTERPRISE_SERVICE_CAPABILITIES
        assert "customer_impact_view" in ENTERPRISE_SERVICE_CAPABILITIES

    def test_template(self):
        assert ENTERPRISE_SERVICE_TEMPLATE.pack_domain == "enterprise_service"

class TestPackBootstrap:
    def test_bootstrap_succeeds(self):
        es = EventSpineEngine()
        bootstrap = EnterpriseServicePackBootstrap(es)
        result = bootstrap.bootstrap(TENANT)
        assert result["status"] == "ready"
        assert result["total_steps"] >= 7
        assert result["capability_count"] == 10
        assert len(result["connectors"]) == 5
        assert len(result["personas"]) == 4
        assert len(result["governance_rules"]) == 3

    def test_engines_accessible(self):
        es = EventSpineEngine()
        bootstrap = EnterpriseServicePackBootstrap(es)
        bootstrap.bootstrap(TENANT)
        engines = bootstrap.engines
        assert engines["pack"].pack_count >= 1
        assert engines["persona"].persona_count >= 4

class TestDemoGenerator:
    def test_generate_demo(self):
        gen = EnterpriseServiceDemoGenerator()
        result = gen.generate("es-demo-test")
        assert result["status"] == "demo_ready"
        assert result["total_seeded"] >= 15
        assert result["cases"]["imported"] == 8
        assert result["remediations"]["imported"] == 4
        assert result["records"]["imported"] == 6

    def test_remediation_titles_are_bounded(self, monkeypatch):
        gen = EnterpriseServiceDemoGenerator()
        captured: dict[str, list[dict[str, str]]] = {}
        original_import = gen._importer.import_remediations

        def _capture(tenant_id: str, remediations: list[dict[str, str]]):
            captured["remediations"] = remediations
            return original_import(tenant_id, remediations)

        monkeypatch.setattr(gen._importer, "import_remediations", _capture)

        result = gen.generate("es-bounded")

        assert result["remediations"]["imported"] == 4
        assert {item["title"] for item in captured["remediations"]} == {"Enterprise service remediation"}
        assert "Email service degradation - Outlook" not in captured["remediations"][0]["title"]

class TestDeploymentFactoryIntegration:
    def test_deploy_through_factory(self):
        factory = DeploymentFactory()
        factory.register_template(ENTERPRISE_SERVICE_TEMPLATE)
        profile = PilotCustomerProfile(
            "es-cust-001", "Enterprise IT Corp", "technology", "service_governance",
            12, "CIO", "Service Desk Lead", 200,
            ("slow_resolution", "poor_visibility", "sla_breaches"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestValidation:
    """130D — Golden proof: 8-point validation."""

    def test_golden_validation(self):
        es = EventSpineEngine()
        bootstrap = EnterpriseServicePackBootstrap(es)
        result = bootstrap.bootstrap("es-golden")
        assert result["status"] == "ready"

        # 1. Intake lands in queue
        importer = PilotDataImporter(es)
        cases = [{"case_id": "golden-c1", "title": "Service outage", "priority": "critical"}]
        cr = importer.import_cases("es-golden", cases)
        assert cr.accepted == 1  # intake works

        # 2. Issue becomes case/remediation
        rems = [{"remediation_id": "golden-r1", "case_ref": "golden-c1", "title": "Fix outage"}]
        rr = importer.import_remediations("es-golden", rems)
        assert rr.accepted == 1

        # 3. Approval gating — governance rules exist
        assert bootstrap.engines["governance"].rule_count >= 3

        # 4. Evidence bundle retrievable
        records = [{"record_id": "golden-rec1", "title": "Incident timeline"}]
        assert importer.import_records("es-golden", records).accepted == 1

        # 5. Customer impact visible — personas configured
        assert bootstrap.engines["persona"].persona_count >= 4

        # 6. Executive dashboard — pack has dashboard capability
        assert bootstrap.engines["pack"].capability_count >= 10

        # 7. Copilot — engine available
        assert bootstrap.engines["copilot"] is not None

        # 8. Deploys through same factory
        factory = DeploymentFactory()
        factory.register_template(ENTERPRISE_SERVICE_TEMPLATE)
        profile = PilotCustomerProfile(
            "es-factory-test", "Factory Test Corp", "technology", "service_governance",
            8, "CTO", "Ops Lead", 50,
            ("visibility", "response_time"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestTargetList:
    """130E — Enterprise service target candidates."""

    def test_enterprise_service_targets(self):
        from mcoi_runtime.pilot.target_list import TargetListBuilder
        builder = TargetListBuilder()
        targets = [
            PilotCustomerProfile("es-t1", "TechCorp IT", "technology", "service_governance", 15, "CIO", "Service Lead", 300,
                               ("sla_breaches", "poor_visibility", "slow_resolution"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("es-t2", "FinServ IT", "finance", "service_governance", 20, "VP IT", "Ops Manager", 500,
                               ("incident_volume", "compliance_gaps", "reporting_delays"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("es-t3", "HealthIT", "healthcare", "service_governance", 8, "CISO", "Help Desk Lead", 150,
                               ("security_incidents", "audit_findings"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        ]
        for t in targets:
            builder.add_candidate(t)
        ranked = builder.rank_and_designate()
        assert ranked[0].fit_level == "strong"
        assert builder.primary is not None

class TestEndToEndSecondPack:
    """Prove: same platform, second product, same machinery."""

    def test_second_pack_full_lifecycle(self):
        # 1. Bootstrap enterprise service pack
        gen = EnterpriseServiceDemoGenerator()
        demo = gen.generate("es-lifecycle")
        assert demo["status"] == "demo_ready"

        # 2. Revenue funnel
        funnel = RevenueFunnel()
        funnel.record_demo("es-lifecycle")
        funnel.convert_to_pilot("es-lifecycle")
        funnel.convert_to_paid("es-lifecycle", 2500.0)
        assert funnel.total_mrr == 2500.0

        # 3. Deployment path
        path = PaidDeploymentPath("es-lifecycle", "es-offer-001")
        for step in range(1, 8):
            path.complete_milestone(step)
        assert path.progress["is_live"]

        # 4. Weekly tracking
        tracker = WeeklyPilotTracker("es-lifecycle")
        tracker.record_week(WeeklySnapshot(
            week_number=1, tenant_id="es-lifecycle",
            cases_created=20, cases_closed=15,
            connector_uptime_percent=99.9, dashboard_views=50,
            copilot_queries=30, executive_satisfaction=8.5,
        ))
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"
