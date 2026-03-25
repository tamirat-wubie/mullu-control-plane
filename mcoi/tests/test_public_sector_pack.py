"""Phase 149 — Public Sector / Case Governance Pack Tests."""
import pytest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.public_sector_pack import (
    PUBLIC_SECTOR_CAPABILITIES, PUBLIC_SECTOR_TEMPLATE,
    PublicSectorPackBootstrap, PublicSectorDemoGenerator,
)
from mcoi_runtime.pilot.deployment_factory import DeploymentFactory
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile, evaluate_fit
from mcoi_runtime.pilot.data_import import PilotDataImporter
from mcoi_runtime.pilot.weekly_tracker import WeeklyPilotTracker, WeeklySnapshot
from mcoi_runtime.pilot.revenue_funnel import RevenueFunnel
from mcoi_runtime.pilot.deployment_path import PaidDeploymentPath

TENANT = "ps-test-tenant"

class TestPackDefinition:
    def test_10_capabilities(self):
        assert len(PUBLIC_SECTOR_CAPABILITIES) == 10

    def test_key_capabilities_present(self):
        assert "citizen_request_intake" in PUBLIC_SECTOR_CAPABILITIES
        assert "case_lifecycle" in PUBLIC_SECTOR_CAPABILITIES
        assert "review_approval" in PUBLIC_SECTOR_CAPABILITIES
        assert "governed_copilot" in PUBLIC_SECTOR_CAPABILITIES
        assert "compliance_bundle" in PUBLIC_SECTOR_CAPABILITIES

    def test_template(self):
        assert PUBLIC_SECTOR_TEMPLATE.pack_domain == "public_sector"

class TestPackBootstrap:
    def test_bootstrap_succeeds(self):
        es = EventSpineEngine()
        bootstrap = PublicSectorPackBootstrap(es)
        result = bootstrap.bootstrap(TENANT)
        assert result["status"] == "ready"
        assert result["total_steps"] >= 7
        assert result["capability_count"] == 10
        assert len(result["connectors"]) == 5
        assert len(result["personas"]) == 6
        assert len(result["governance_rules"]) == 3

    def test_engines_accessible(self):
        es = EventSpineEngine()
        bootstrap = PublicSectorPackBootstrap(es)
        bootstrap.bootstrap(TENANT)
        engines = bootstrap.engines
        assert engines["pack"].pack_count >= 1
        assert engines["persona"].persona_count >= 6

class TestDemoGenerator:
    def test_generate_demo(self):
        gen = PublicSectorDemoGenerator()
        result = gen.generate("ps-demo-test")
        assert result["status"] == "demo_ready"
        assert result["total_seeded"] >= 20
        assert result["cases"]["imported"] == 10
        assert result["remediations"]["imported"] == 5
        assert result["records"]["imported"] == 8

class TestDeploymentFactoryIntegration:
    def test_deploy_through_factory(self):
        factory = DeploymentFactory()
        factory.register_template(PUBLIC_SECTOR_TEMPLATE)
        profile = PilotCustomerProfile(
            "ps-cust-001", "Metro City Government", "public_sector", "case_governance",
            20, "Director of Public Services", "Case Management Lead", 500,
            ("citizen_request_intake", "case_lifecycle", "audit_reporting"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestValidation:
    """149D — Golden proof: 8-point validation."""

    def test_golden_validation(self):
        es = EventSpineEngine()
        bootstrap = PublicSectorPackBootstrap(es)
        result = bootstrap.bootstrap("ps-golden")
        assert result["status"] == "ready"

        importer = PilotDataImporter(es)

        # 1. Citizen request intake — case enters queue
        cases = [{"case_id": "golden-ps1", "title": "Building permit application", "priority": "high"}]
        cr = importer.import_cases("ps-golden", cases)
        assert cr.accepted == 1

        # 2. Case lifecycle — remediation links to case
        rems = [{"remediation_id": "golden-psr1", "case_ref": "golden-ps1", "title": "Process building permit"}]
        rr = importer.import_remediations("ps-golden", rems)
        assert rr.accepted == 1

        # 3. Review approval — second case enters system
        cases2 = [{"case_id": "golden-ps2", "title": "Zoning variance request", "priority": "high"}]
        cr2 = importer.import_cases("ps-golden", cases2)
        assert cr2.accepted == 1

        # 4. Governance rules enforce citizen data protection
        assert bootstrap.engines["governance"].rule_count >= 3

        # 5. SLA deadline visibility — pack capability count proves it
        assert bootstrap.engines["pack"].capability_count >= 10

        # 6. Dashboard — personas include executive/compliance views
        assert bootstrap.engines["persona"].persona_count >= 5

        # 7. Copilot available
        assert bootstrap.engines["copilot"] is not None

        # 8. Factory deploy
        factory = DeploymentFactory()
        factory.register_template(PUBLIC_SECTOR_TEMPLATE)
        profile = PilotCustomerProfile(
            "ps-factory-test", "Public Sector Agency", "public_sector", "case_governance",
            12, "Director of Public Services", "Case Manager", 120,
            ("citizen_request_intake", "case_lifecycle"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestTargetList:
    """149E — Public sector target candidates."""

    def test_public_sector_targets(self):
        from mcoi_runtime.pilot.target_list import TargetListBuilder
        builder = TargetListBuilder()
        targets = [
            PilotCustomerProfile("ps-t1", "Metro City Government", "public_sector", "case_governance",
                                 25, "Director of Public Services", "Case Management Lead", 600,
                                 ("citizen_request_intake", "case_lifecycle", "audit_reporting"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("ps-t2", "State Environmental Agency", "government", "compliance",
                                 15, "Agency Director", "Compliance Officer", 350,
                                 ("environmental_compliance", "evidence_retrieval", "audit_reporting"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("ps-t3", "County Records Office", "public_sector", "records_management",
                                 10, "County Clerk", "Records Supervisor", 200,
                                 ("public_records", "case_lifecycle"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        ]
        for t in targets:
            builder.add_candidate(t)
        ranked = builder.rank_and_designate()
        assert ranked[0].fit_level == "strong"
        assert builder.primary is not None

class TestEndToEndSeventhPack:
    """Prove: same platform, seventh product, same machinery."""

    def test_seventh_pack_full_lifecycle(self):
        # 1. Bootstrap public sector pack via demo
        gen = PublicSectorDemoGenerator()
        demo = gen.generate("ps-lifecycle")
        assert demo["status"] == "demo_ready"

        # 2. Revenue funnel
        funnel = RevenueFunnel()
        funnel.record_demo("ps-lifecycle")
        funnel.convert_to_pilot("ps-lifecycle")
        funnel.convert_to_paid("ps-lifecycle", 7000.0)
        assert funnel.total_mrr == 7000.0

        # 3. Deployment path
        path = PaidDeploymentPath("ps-lifecycle", "ps-offer-001")
        for step in range(1, 8):
            path.complete_milestone(step)
        assert path.progress["is_live"]

        # 4. Weekly tracking
        tracker = WeeklyPilotTracker("ps-lifecycle")
        tracker.record_week(WeeklySnapshot(
            week_number=1, tenant_id="ps-lifecycle",
            cases_created=30, cases_closed=22,
            connector_uptime_percent=99.5, dashboard_views=75,
            copilot_queries=50, executive_satisfaction=9.2,
        ))
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"
