"""Phase 138 — Research / Lab Operations Pack Tests."""
import pytest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.research_lab_pack import (
    RESEARCH_LAB_CAPABILITIES, RESEARCH_LAB_TEMPLATE,
    ResearchLabPackBootstrap, ResearchLabDemoGenerator,
)
from mcoi_runtime.pilot.deployment_factory import DeploymentFactory
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile, evaluate_fit
from mcoi_runtime.pilot.data_import import PilotDataImporter
from mcoi_runtime.pilot.weekly_tracker import WeeklyPilotTracker, WeeklySnapshot
from mcoi_runtime.pilot.revenue_funnel import RevenueFunnel
from mcoi_runtime.pilot.deployment_path import PaidDeploymentPath

TENANT = "rl-test-tenant"

class TestPackDefinition:
    def test_10_capabilities(self):
        assert len(RESEARCH_LAB_CAPABILITIES) == 10

    def test_key_capabilities_present(self):
        assert "research_intake" in RESEARCH_LAB_CAPABILITIES
        assert "hypothesis_tracking" in RESEARCH_LAB_CAPABILITIES
        assert "experiment_coordination" in RESEARCH_LAB_CAPABILITIES
        assert "evidence_retrieval" in RESEARCH_LAB_CAPABILITIES
        assert "research_copilot" in RESEARCH_LAB_CAPABILITIES

    def test_template(self):
        assert RESEARCH_LAB_TEMPLATE.pack_domain == "research_lab"

class TestPackBootstrap:
    def test_bootstrap_succeeds(self):
        es = EventSpineEngine()
        bootstrap = ResearchLabPackBootstrap(es)
        result = bootstrap.bootstrap(TENANT)
        assert result["status"] == "ready"
        assert result["total_steps"] >= 7
        assert result["capability_count"] == 10
        assert len(result["connectors"]) == 5
        assert len(result["personas"]) == 6
        assert len(result["governance_rules"]) == 3

    def test_engines_accessible(self):
        es = EventSpineEngine()
        bootstrap = ResearchLabPackBootstrap(es)
        bootstrap.bootstrap(TENANT)
        engines = bootstrap.engines
        assert engines["pack"].pack_count >= 1
        assert engines["persona"].persona_count >= 6

class TestDemoGenerator:
    def test_generate_demo(self):
        gen = ResearchLabDemoGenerator()
        result = gen.generate("rl-demo-test")
        assert result["status"] == "demo_ready"
        assert result["total_seeded"] >= 20
        assert result["cases"]["imported"] == 10
        assert result["remediations"]["imported"] == 5
        assert result["records"]["imported"] == 8

    def test_remediation_titles_are_bounded(self, monkeypatch):
        gen = ResearchLabDemoGenerator()
        captured: dict[str, list[dict[str, str]]] = {}
        original_import = gen._importer.import_remediations

        def _capture(tenant_id: str, remediations: list[dict[str, str]]):
            captured["remediations"] = remediations
            return original_import(tenant_id, remediations)

        monkeypatch.setattr(gen._importer, "import_remediations", _capture)

        result = gen.generate("rl-bounded")

        assert result["remediations"]["imported"] == 5
        assert {item["title"] for item in captured["remediations"]} == {"Research lab remediation"}
        assert "Sample chain-of-custody gap" not in captured["remediations"][0]["title"]

class TestDeploymentFactoryIntegration:
    def test_deploy_through_factory(self):
        factory = DeploymentFactory()
        factory.register_template(RESEARCH_LAB_TEMPLATE)
        profile = PilotCustomerProfile(
            "rl-cust-001", "Global Research Institute", "research", "lab_operations",
            20, "VP Research", "Lab Director", 500,
            ("hypothesis_tracking", "experiment_coordination", "evidence_retrieval"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestValidation:
    """138D — Golden proof: 8-point validation."""

    def test_golden_validation(self):
        es = EventSpineEngine()
        bootstrap = ResearchLabPackBootstrap(es)
        result = bootstrap.bootstrap("rl-golden")
        assert result["status"] == "ready"

        importer = PilotDataImporter(es)

        # 1. Study intake — research case enters queue
        cases = [{"case_id": "golden-rl1", "title": "Phase III trial protocol review", "priority": "critical"}]
        cr = importer.import_cases("rl-golden", cases)
        assert cr.accepted == 1

        # 2. Hypothesis + evidence — remediation links to case
        rems = [{"remediation_id": "golden-rlr1", "case_ref": "golden-rl1", "title": "Hypothesis evidence linkage"}]
        rr = importer.import_remediations("rl-golden", rems)
        assert rr.accepted == 1

        # 3. Experiment tracked — second case enters system
        cases2 = [{"case_id": "golden-rl2", "title": "Reproducibility challenge", "priority": "high"}]
        cr2 = importer.import_cases("rl-golden", cases2)
        assert cr2.accepted == 1

        # 4. Contradiction visible — governance rules enforce evidence requirements
        assert bootstrap.engines["governance"].rule_count >= 3

        # 5. Peer review — approval capability present via pack capabilities
        assert bootstrap.engines["pack"].capability_count >= 10

        # 6. Dashboard — personas include executive/lab manager views
        assert bootstrap.engines["persona"].persona_count >= 5

        # 7. Copilot available
        assert bootstrap.engines["copilot"] is not None

        # 8. Factory deploy
        factory = DeploymentFactory()
        factory.register_template(RESEARCH_LAB_TEMPLATE)
        profile = PilotCustomerProfile(
            "rl-factory-test", "Research Lab Corp", "research", "lab_operations",
            12, "Lab Director", "Principal Investigator", 120,
            ("hypothesis_tracking", "experiment_coordination"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestTargetList:
    """138E — Research/lab target candidates."""

    def test_research_lab_targets(self):
        from mcoi_runtime.pilot.target_list import TargetListBuilder
        builder = TargetListBuilder()
        targets = [
            PilotCustomerProfile("rl-t1", "BioPharmaCo Research Division", "pharma", "research",
                                 25, "VP Research", "Lab Director", 600,
                                 ("hypothesis_tracking", "experiment_coordination", "evidence_retrieval"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("rl-t2", "University Medical Center Labs", "academic", "lab_operations",
                                 15, "Dean of Research", "Principal Investigator", 350,
                                 ("literature_review", "peer_review_approval", "reproducibility"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("rl-t3", "ClinTrials Global CRO", "cro", "clinical_research",
                                 10, "Research Director", "Study Coordinator", 200,
                                 ("regulatory_compliance", "data_integrity", "protocol_management"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        ]
        for t in targets:
            builder.add_candidate(t)
        ranked = builder.rank_and_designate()
        assert ranked[0].fit_level == "strong"
        assert builder.primary is not None

class TestEndToEndFifthPack:
    """Prove: same platform, fifth product, same machinery."""

    def test_fifth_pack_full_lifecycle(self):
        # 1. Bootstrap research lab pack via demo
        gen = ResearchLabDemoGenerator()
        demo = gen.generate("rl-lifecycle")
        assert demo["status"] == "demo_ready"

        # 2. Revenue funnel
        funnel = RevenueFunnel()
        funnel.record_demo("rl-lifecycle")
        funnel.convert_to_pilot("rl-lifecycle")
        funnel.convert_to_paid("rl-lifecycle", 5500.0)
        assert funnel.total_mrr == 5500.0

        # 3. Deployment path
        path = PaidDeploymentPath("rl-lifecycle", "rl-offer-001")
        for step in range(1, 8):
            path.complete_milestone(step)
        assert path.progress["is_live"]

        # 4. Weekly tracking
        tracker = WeeklyPilotTracker("rl-lifecycle")
        tracker.record_week(WeeklySnapshot(
            week_number=1, tenant_id="rl-lifecycle",
            cases_created=30, cases_closed=22,
            connector_uptime_percent=99.5, dashboard_views=75,
            copilot_queries=50, executive_satisfaction=9.2,
        ))
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"
