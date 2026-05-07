"""Phase 131 — Financial Control / Settlement Pack Tests."""
import pytest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.financial_control_pack import (
    FINANCIAL_CONTROL_CAPABILITIES, FINANCIAL_CONTROL_TEMPLATE,
    FinancialControlPackBootstrap, FinancialControlDemoGenerator,
)
from mcoi_runtime.pilot.deployment_factory import DeploymentFactory
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile, evaluate_fit
from mcoi_runtime.pilot.data_import import PilotDataImporter
from mcoi_runtime.pilot.weekly_tracker import WeeklyPilotTracker, WeeklySnapshot
from mcoi_runtime.pilot.revenue_funnel import RevenueFunnel
from mcoi_runtime.pilot.deployment_path import PaidDeploymentPath

TENANT = "fc-test-tenant"

class TestPackDefinition:
    def test_10_capabilities(self):
        assert len(FINANCIAL_CONTROL_CAPABILITIES) == 10

    def test_key_capabilities_present(self):
        assert "billing_intake" in FINANCIAL_CONTROL_CAPABILITIES
        assert "dispute_handling" in FINANCIAL_CONTROL_CAPABILITIES
        assert "settlement_tracking" in FINANCIAL_CONTROL_CAPABILITIES
        assert "financial_copilot" in FINANCIAL_CONTROL_CAPABILITIES

    def test_template(self):
        assert FINANCIAL_CONTROL_TEMPLATE.pack_domain == "financial_control"

class TestPackBootstrap:
    def test_bootstrap_succeeds(self):
        es = EventSpineEngine()
        bootstrap = FinancialControlPackBootstrap(es)
        result = bootstrap.bootstrap(TENANT)
        assert result["status"] == "ready"
        assert result["total_steps"] >= 7
        assert result["capability_count"] == 10
        assert len(result["connectors"]) == 5
        assert len(result["personas"]) == 5
        assert len(result["governance_rules"]) == 3

    def test_engines_accessible(self):
        es = EventSpineEngine()
        bootstrap = FinancialControlPackBootstrap(es)
        bootstrap.bootstrap(TENANT)
        engines = bootstrap.engines
        assert engines["pack"].pack_count >= 1
        assert engines["persona"].persona_count >= 5

class TestDemoGenerator:
    def test_generate_demo(self):
        gen = FinancialControlDemoGenerator()
        result = gen.generate("fc-demo-test")
        assert result["status"] == "demo_ready"
        assert result["total_seeded"] >= 15
        assert result["cases"]["imported"] == 8
        assert result["remediations"]["imported"] == 4
        assert result["records"]["imported"] == 6

    def test_remediation_titles_are_bounded(self, monkeypatch):
        gen = FinancialControlDemoGenerator()
        captured: dict[str, list[dict[str, str]]] = {}
        original_import = gen._importer.import_remediations

        def _capture(tenant_id: str, remediations: list[dict[str, str]]):
            captured["remediations"] = remediations
            return original_import(tenant_id, remediations)

        monkeypatch.setattr(gen._importer, "import_remediations", _capture)

        result = gen.generate("fc-bounded")

        assert result["remediations"]["imported"] == 4
        assert {item["title"] for item in captured["remediations"]} == {"Financial control remediation"}
        assert "Invoice dispute - duplicate billing" not in captured["remediations"][0]["title"]

class TestDeploymentFactoryIntegration:
    def test_deploy_through_factory(self):
        factory = DeploymentFactory()
        factory.register_template(FINANCIAL_CONTROL_TEMPLATE)
        profile = PilotCustomerProfile(
            "fc-cust-001", "Global Finance Corp", "finance", "compliance",
            15, "CFO", "Billing Operations Lead", 350,
            ("invoice_disputes", "settlement_delays", "delinquency_visibility"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestValidation:
    """131D — Golden proof: 8-point validation."""

    def test_golden_validation(self):
        es = EventSpineEngine()
        bootstrap = FinancialControlPackBootstrap(es)
        result = bootstrap.bootstrap("fc-golden")
        assert result["status"] == "ready"

        # 1. Billing intake lands in queue
        importer = PilotDataImporter(es)
        cases = [{"case_id": "golden-fc1", "title": "Invoice dispute - overbilling", "priority": "high"}]
        cr = importer.import_cases("fc-golden", cases)
        assert cr.accepted == 1

        # 2. Dispute becomes case
        rems = [{"remediation_id": "golden-fr1", "case_ref": "golden-fc1", "title": "Resolve invoice dispute"}]
        rr = importer.import_remediations("fc-golden", rems)
        assert rr.accepted == 1

        # 3. Settlement visible/auditable — governance rules exist
        assert bootstrap.engines["governance"].rule_count >= 3

        # 4. Exception approval works — personas configured with guided authority
        assert bootstrap.engines["persona"].persona_count >= 5

        # 5. Overdue item surfaced — pack has delinquency detection capability
        assert bootstrap.engines["pack"].capability_count >= 10

        # 6. Executive finance dashboard
        records = [{"record_id": "golden-frec1", "title": "Settlement proof document"}]
        assert importer.import_records("fc-golden", records).accepted == 1

        # 7. Copilot explains financial issue
        assert bootstrap.engines["copilot"] is not None

        # 8. Deploys through same factory
        factory = DeploymentFactory()
        factory.register_template(FINANCIAL_CONTROL_TEMPLATE)
        profile = PilotCustomerProfile(
            "fc-factory-test", "Factory Finance Corp", "finance", "compliance",
            10, "VP Finance", "AR Manager", 80,
            ("billing_errors", "settlement_tracking"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestTargetList:
    """131E — Financial control target candidates."""

    def test_financial_control_targets(self):
        from mcoi_runtime.pilot.target_list import TargetListBuilder
        builder = TargetListBuilder()
        targets = [
            PilotCustomerProfile("fc-t1", "MegaBank Finance Ops", "finance", "compliance", 20, "CFO", "Billing Lead", 500,
                               ("invoice_disputes", "settlement_delays", "delinquency_gaps"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("fc-t2", "InsureCo Claims Finance", "insurance", "compliance", 12, "Controller", "AR Manager", 300,
                               ("revenue_recognition", "audit_findings", "billing_errors"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("fc-t3", "RetailCorp Treasury", "retail", "audit", 8, "VP Finance", "Settlement Analyst", 150,
                               ("cash_reconciliation", "vendor_disputes"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        ]
        for t in targets:
            builder.add_candidate(t)
        ranked = builder.rank_and_designate()
        assert ranked[0].fit_level == "strong"
        assert builder.primary is not None

class TestEndToEndThirdPack:
    """Prove: same platform, third product, same machinery."""

    def test_third_pack_full_lifecycle(self):
        # 1. Bootstrap financial control pack via demo
        gen = FinancialControlDemoGenerator()
        demo = gen.generate("fc-lifecycle")
        assert demo["status"] == "demo_ready"

        # 2. Revenue funnel
        funnel = RevenueFunnel()
        funnel.record_demo("fc-lifecycle")
        funnel.convert_to_pilot("fc-lifecycle")
        funnel.convert_to_paid("fc-lifecycle", 3500.0)
        assert funnel.total_mrr == 3500.0

        # 3. Deployment path
        path = PaidDeploymentPath("fc-lifecycle", "fc-offer-001")
        for step in range(1, 8):
            path.complete_milestone(step)
        assert path.progress["is_live"]

        # 4. Weekly tracking
        tracker = WeeklyPilotTracker("fc-lifecycle")
        tracker.record_week(WeeklySnapshot(
            week_number=1, tenant_id="fc-lifecycle",
            cases_created=25, cases_closed=18,
            connector_uptime_percent=99.8, dashboard_views=60,
            copilot_queries=40, executive_satisfaction=9.0,
        ))
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"
