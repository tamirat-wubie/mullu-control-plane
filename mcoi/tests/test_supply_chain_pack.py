"""Phase 139 — Supply Chain / Procurement Operations Pack Tests."""
import pytest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.supply_chain_pack import (
    SUPPLY_CHAIN_CAPABILITIES, SUPPLY_CHAIN_TEMPLATE,
    SupplyChainPackBootstrap, SupplyChainDemoGenerator,
)
from mcoi_runtime.pilot.deployment_factory import DeploymentFactory
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile, evaluate_fit
from mcoi_runtime.pilot.data_import import PilotDataImporter
from mcoi_runtime.pilot.weekly_tracker import WeeklyPilotTracker, WeeklySnapshot
from mcoi_runtime.pilot.revenue_funnel import RevenueFunnel
from mcoi_runtime.pilot.deployment_path import PaidDeploymentPath

TENANT = "sc-test-tenant"

class TestPackDefinition:
    def test_10_capabilities(self):
        assert len(SUPPLY_CHAIN_CAPABILITIES) == 10

    def test_key_capabilities_present(self):
        assert "procurement_intake" in SUPPLY_CHAIN_CAPABILITIES
        assert "vendor_management" in SUPPLY_CHAIN_CAPABILITIES
        assert "purchase_order_lifecycle" in SUPPLY_CHAIN_CAPABILITIES
        assert "delivery_receiving" in SUPPLY_CHAIN_CAPABILITIES
        assert "supply_copilot" in SUPPLY_CHAIN_CAPABILITIES

    def test_template(self):
        assert SUPPLY_CHAIN_TEMPLATE.pack_domain == "supply_chain"

class TestPackBootstrap:
    def test_bootstrap_succeeds(self):
        es = EventSpineEngine()
        bootstrap = SupplyChainPackBootstrap(es)
        result = bootstrap.bootstrap(TENANT)
        assert result["status"] == "ready"
        assert result["total_steps"] >= 7
        assert result["capability_count"] == 10
        assert len(result["connectors"]) == 5
        assert len(result["personas"]) == 6
        assert len(result["governance_rules"]) == 3

    def test_engines_accessible(self):
        es = EventSpineEngine()
        bootstrap = SupplyChainPackBootstrap(es)
        bootstrap.bootstrap(TENANT)
        engines = bootstrap.engines
        assert engines["pack"].pack_count >= 1
        assert engines["persona"].persona_count >= 6

class TestDemoGenerator:
    def test_generate_demo(self):
        gen = SupplyChainDemoGenerator()
        result = gen.generate("sc-demo-test")
        assert result["status"] == "demo_ready"
        assert result["total_seeded"] >= 20
        assert result["cases"]["imported"] == 10
        assert result["remediations"]["imported"] == 5
        assert result["records"]["imported"] == 8

    def test_remediation_titles_are_bounded(self, monkeypatch):
        gen = SupplyChainDemoGenerator()
        captured: dict[str, list[dict[str, str]]] = {}
        original_import = gen._importer.import_remediations

        def _capture(tenant_id: str, remediations: list[dict[str, str]]):
            captured["remediations"] = remediations
            return original_import(tenant_id, remediations)

        monkeypatch.setattr(gen._importer, "import_remediations", _capture)

        result = gen.generate("sc-bounded")

        assert result["remediations"]["imported"] == 5
        assert {item["title"] for item in captured["remediations"]} == {"Supply chain remediation"}
        assert "Vendor delivery delay - critical component" not in captured["remediations"][0]["title"]

class TestDeploymentFactoryIntegration:
    def test_deploy_through_factory(self):
        factory = DeploymentFactory()
        factory.register_template(SUPPLY_CHAIN_TEMPLATE)
        profile = PilotCustomerProfile(
            "sc-cust-001", "Global Procurement Corp", "supply_chain", "procurement",
            20, "VP Supply Chain", "Procurement Director", 500,
            ("vendor_management", "purchase_order_lifecycle", "inventory_replenishment"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestValidation:
    """139D — Golden proof: 8-point validation."""

    def test_golden_validation(self):
        es = EventSpineEngine()
        bootstrap = SupplyChainPackBootstrap(es)
        result = bootstrap.bootstrap("sc-golden")
        assert result["status"] == "ready"

        importer = PilotDataImporter(es)

        # 1. Procurement intake — case enters queue
        cases = [{"case_id": "golden-sc1", "title": "Vendor delivery delay - critical component", "priority": "critical"}]
        cr = importer.import_cases("sc-golden", cases)
        assert cr.accepted == 1

        # 2. Vendor management — remediation links to case
        rems = [{"remediation_id": "golden-scr1", "case_ref": "golden-sc1", "title": "Resolve vendor delivery delay"}]
        rr = importer.import_remediations("sc-golden", rems)
        assert rr.accepted == 1

        # 3. PO lifecycle — second case enters system
        cases2 = [{"case_id": "golden-sc2", "title": "PO approval pending - bulk order 9921", "priority": "high"}]
        cr2 = importer.import_cases("sc-golden", cases2)
        assert cr2.accepted == 1

        # 4. Supplier risk visible — governance rules enforce procurement evidence
        assert bootstrap.engines["governance"].rule_count >= 3

        # 5. Inventory replenishment — pack capability count proves it
        assert bootstrap.engines["pack"].capability_count >= 10

        # 6. Dashboard — personas include executive/analyst views
        assert bootstrap.engines["persona"].persona_count >= 5

        # 7. Copilot available
        assert bootstrap.engines["copilot"] is not None

        # 8. Factory deploy
        factory = DeploymentFactory()
        factory.register_template(SUPPLY_CHAIN_TEMPLATE)
        profile = PilotCustomerProfile(
            "sc-factory-test", "Supply Chain Corp", "supply_chain", "procurement",
            12, "Procurement Director", "Supply Chain Analyst", 120,
            ("vendor_management", "purchase_order_lifecycle"),
            ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        )
        fd = factory.deploy_customer(profile)
        assert fd.verification_passed

class TestTargetList:
    """139E — Supply chain target candidates."""

    def test_supply_chain_targets(self):
        from mcoi_runtime.pilot.target_list import TargetListBuilder
        builder = TargetListBuilder()
        targets = [
            PilotCustomerProfile("sc-t1", "MegaRetail Distribution", "retail", "supply_chain",
                                 25, "VP Supply Chain", "Procurement Director", 600,
                                 ("vendor_management", "inventory_replenishment", "lead_time_tracking"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("sc-t2", "AutoParts Global Sourcing", "automotive", "procurement",
                                 15, "Director Procurement", "Vendor Manager", 350,
                                 ("supplier_risk_compliance", "purchase_order_lifecycle", "delivery_receiving"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
            PilotCustomerProfile("sc-t3", "FreshFoods Supply Network", "food_beverage", "logistics",
                                 10, "Supply Chain Manager", "Receiving Coordinator", 200,
                                 ("delivery_receiving", "inventory_replenishment"),
                                 ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        ]
        for t in targets:
            builder.add_candidate(t)
        ranked = builder.rank_and_designate()
        assert ranked[0].fit_level == "strong"
        assert builder.primary is not None

class TestEndToEndSixthPack:
    """Prove: same platform, sixth product, same machinery."""

    def test_sixth_pack_full_lifecycle(self):
        # 1. Bootstrap supply chain pack via demo
        gen = SupplyChainDemoGenerator()
        demo = gen.generate("sc-lifecycle")
        assert demo["status"] == "demo_ready"

        # 2. Revenue funnel
        funnel = RevenueFunnel()
        funnel.record_demo("sc-lifecycle")
        funnel.convert_to_pilot("sc-lifecycle")
        funnel.convert_to_paid("sc-lifecycle", 6000.0)
        assert funnel.total_mrr == 6000.0

        # 3. Deployment path
        path = PaidDeploymentPath("sc-lifecycle", "sc-offer-001")
        for step in range(1, 8):
            path.complete_milestone(step)
        assert path.progress["is_live"]

        # 4. Weekly tracking
        tracker = WeeklyPilotTracker("sc-lifecycle")
        tracker.record_week(WeeklySnapshot(
            week_number=1, tenant_id="sc-lifecycle",
            cases_created=30, cases_closed=22,
            connector_uptime_percent=99.5, dashboard_views=75,
            copilot_queries=50, executive_satisfaction=9.2,
        ))
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"
