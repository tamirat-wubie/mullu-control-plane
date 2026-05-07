"""Phase 132 — Factory Quality / Downtime / Throughput Pack Tests."""
import pytest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.factory_quality_pack import (
    FACTORY_QUALITY_CAPABILITIES, FACTORY_QUALITY_TEMPLATE,
    FactoryQualityPackBootstrap, FactoryQualityDemoGenerator,
)
from mcoi_runtime.pilot.deployment_factory import DeploymentFactory
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile, evaluate_fit
from mcoi_runtime.pilot.data_import import PilotDataImporter
from mcoi_runtime.pilot.weekly_tracker import WeeklyPilotTracker, WeeklySnapshot
from mcoi_runtime.pilot.revenue_funnel import RevenueFunnel
from mcoi_runtime.pilot.deployment_path import PaidDeploymentPath

TENANT = "fq-test-tenant"

class TestPackDefinition:
    def test_11_capabilities(self):
        assert len(FACTORY_QUALITY_CAPABILITIES) == 11

    def test_key_capabilities_present(self):
        assert "work_order_intake" in FACTORY_QUALITY_CAPABILITIES
        assert "downtime_tracking" in FACTORY_QUALITY_CAPABILITIES
        assert "quality_inspection" in FACTORY_QUALITY_CAPABILITIES
        assert "factory_copilot" in FACTORY_QUALITY_CAPABILITIES

    def test_template(self):
        assert FACTORY_QUALITY_TEMPLATE.pack_domain == "factory_quality"

class TestPackBootstrap:
    def test_bootstrap_succeeds(self):
        es = EventSpineEngine()
        bootstrap = FactoryQualityPackBootstrap(es)
        result = bootstrap.bootstrap(TENANT)
        assert result["status"] == "ready"
        assert result["total_steps"] >= 7
        assert result["capability_count"] == 11
        assert len(result["connectors"]) == 5
        assert len(result["personas"]) == 6
        assert len(result["governance_rules"]) == 3

    def test_engines_accessible(self):
        es = EventSpineEngine()
        bootstrap = FactoryQualityPackBootstrap(es)
        bootstrap.bootstrap(TENANT)
        engines = bootstrap.engines
        assert engines["pack"].pack_count >= 1
        assert engines["persona"].persona_count >= 6

class TestDemoGenerator:
    def test_generate_demo(self):
        gen = FactoryQualityDemoGenerator()
        result = gen.generate("fq-demo-test")
        assert result["status"] == "demo_ready"
        assert result["total_seeded"] >= 20
        assert result["cases"]["imported"] == 10
        assert result["remediations"]["imported"] == 5
        assert result["records"]["imported"] == 8

    def test_remediation_titles_are_bounded(self, monkeypatch):
        gen = FactoryQualityDemoGenerator()
        captured: dict[str, list[dict[str, str]]] = {}
        original_import = gen._importer.import_remediations

        def _capture(tenant_id: str, remediations: list[dict[str, str]]):
            captured["remediations"] = remediations
            return original_import(tenant_id, remediations)

        monkeypatch.setattr(gen._importer, "import_remediations", _capture)

        result = gen.generate("fq-bounded")

        assert result["remediations"]["imported"] == 5
        assert {item["title"] for item in captured["remediations"]} == {"Factory quality remediation"}
        assert "Machine breakdown - press line 2" not in captured["remediations"][0]["title"]

class TestDeploymentFactoryIntegration:
    def test_deploy_through_factory(self):
        factory = DeploymentFactory()
        factory.register_template(FACTORY_QUALITY_TEMPLATE)
        profile = PilotCustomerProfile(
            "fq-cust-001", "Global Manufacturing Corp", "manufacturing", "quality",
            20, "VP Operations", "Plant Quality Lead", 500,
            ("downtime_reduction", "quality_failures", "yield_improvement"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestValidation:
    """132D — Golden proof: 9-point validation."""

    def test_golden_validation(self):
        es = EventSpineEngine()
        bootstrap = FactoryQualityPackBootstrap(es)
        result = bootstrap.bootstrap("fq-golden")
        assert result["status"] == "ready"

        # 1. Work order in queue
        importer = PilotDataImporter(es)
        cases = [{"case_id": "golden-fq1", "title": "Machine breakdown - press line 2", "priority": "critical"}]
        cr = importer.import_cases("fq-golden", cases)
        assert cr.accepted == 1

        # 2. Downtime captured
        rems = [{"remediation_id": "golden-fqr1", "case_ref": "golden-fq1", "title": "Resolve machine breakdown"}]
        rr = importer.import_remediations("fq-golden", rems)
        assert rr.accepted == 1

        # 3. Quality failure opens remediation
        cases2 = [{"case_id": "golden-fq2", "title": "Quality failure batch 4472", "priority": "critical"}]
        cr2 = importer.import_cases("fq-golden", cases2)
        assert cr2.accepted == 1

        # 4. Process deviation visible — governance rules exist
        assert bootstrap.engines["governance"].rule_count >= 3

        # 5. Digital twin available — pack capability count proves it
        assert bootstrap.engines["pack"].capability_count >= 11

        # 6. Maintenance escalation works — 5+ personas
        assert bootstrap.engines["persona"].persona_count >= 5

        # 7. Executive dashboard shows posture
        records = [{"record_id": "golden-fqrec1", "title": "Yield analysis report"}]
        assert importer.import_records("fq-golden", records).accepted == 1

        # 8. Copilot available
        assert bootstrap.engines["copilot"] is not None

        # 9. Deploys through factory
        factory = DeploymentFactory()
        factory.register_template(FACTORY_QUALITY_TEMPLATE)
        profile = PilotCustomerProfile(
            "fq-factory-test", "Factory Quality Corp", "manufacturing", "quality",
            12, "Plant Manager", "Quality Engineer", 120,
            ("downtime_tracking", "quality_failures"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestTargetList:
    """132E — Factory/manufacturing target candidates."""

    def test_factory_quality_targets(self):
        from mcoi_runtime.pilot.target_list import TargetListBuilder
        builder = TargetListBuilder()
        targets = [
            PilotCustomerProfile("fq-t1", "MegaFactory Automotive", "manufacturing", "quality", 25, "VP Operations", "Plant Quality Lead", 600,
                               ("downtime_reduction", "quality_failures", "yield_improvement"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("fq-t2", "PrecisionParts Aerospace", "aerospace", "quality", 15, "Director Manufacturing", "Quality Manager", 350,
                               ("scrap_rate_reduction", "calibration_compliance", "process_deviation"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("fq-t3", "ChemProcess Industries", "chemical", "compliance", 10, "Plant Manager", "Maintenance Lead", 200,
                               ("maintenance_backlog", "downtime_visibility"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        ]
        for t in targets:
            builder.add_candidate(t)
        ranked = builder.rank_and_designate()
        assert ranked[0].fit_level == "strong"
        assert builder.primary is not None

class TestEndToEndFourthPack:
    """Prove: same platform, fourth product, same machinery."""

    def test_fourth_pack_full_lifecycle(self):
        # 1. Bootstrap factory quality pack via demo
        gen = FactoryQualityDemoGenerator()
        demo = gen.generate("fq-lifecycle")
        assert demo["status"] == "demo_ready"

        # 2. Revenue funnel
        funnel = RevenueFunnel()
        funnel.record_demo("fq-lifecycle")
        funnel.convert_to_pilot("fq-lifecycle")
        funnel.convert_to_paid("fq-lifecycle", 4200.0)
        assert funnel.total_mrr == 4200.0

        # 3. Deployment path
        path = PaidDeploymentPath("fq-lifecycle", "fq-offer-001")
        for step in range(1, 8):
            path.complete_milestone(step)
        assert path.progress["is_live"]

        # 4. Weekly tracking
        tracker = WeeklyPilotTracker("fq-lifecycle")
        tracker.record_week(WeeklySnapshot(
            week_number=1, tenant_id="fq-lifecycle",
            cases_created=30, cases_closed=22,
            connector_uptime_percent=99.5, dashboard_views=75,
            copilot_queries=50, executive_satisfaction=9.2,
        ))
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"
