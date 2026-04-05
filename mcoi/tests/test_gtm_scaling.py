"""Phase 133 — GTM Expansion / Product-Line Scaling Tests."""
import pytest
from mcoi_runtime.pilot.portfolio import PORTFOLIO, capabilities_to_buyer_map, comparison_sheet
from mcoi_runtime.pilot.demo_catalog import DemoCatalog, DEMO_FLOWS
from mcoi_runtime.pilot.pipeline_ops import PackPipeline, EXPANSION_PATHS, score_expansion
from mcoi_runtime.pilot.delivery_scaling import DEPLOYMENT_PROFILES, CONNECTOR_BUNDLES, SUPPORT_RUNBOOKS, PACK_PRICING, ADDON_PRICING

class TestPortfolio:
    def test_4_products(self):
        assert len(PORTFOLIO) == 4

    def test_each_has_buyers(self):
        for p in PORTFOLIO:
            assert len(p.buyer_personas) >= 3

    def test_each_has_capabilities(self):
        for p in PORTFOLIO:
            assert len(p.core_capabilities) >= 10

    def test_each_has_upsell(self):
        for p in PORTFOLIO:
            assert len(p.adjacent_upsell) >= 2

    def test_capability_map(self):
        m = capabilities_to_buyer_map()
        assert "copilot" in m
        assert len(m["copilot"]) >= 3  # copilot in 3+ packs

    def test_comparison_sheet(self):
        sheet = comparison_sheet()
        assert len(sheet) == 4
        for row in sheet:
            assert row["capabilities"] >= 10

class TestDemoCatalog:
    def test_4_demo_flows(self):
        assert len(DEMO_FLOWS) == 4

    def test_generate_single(self):
        catalog = DemoCatalog()
        result = catalog.generate_demo("regulated_ops")
        assert result["status"] == "demo_ready"

    def test_generate_all(self):
        catalog = DemoCatalog()
        all_demos = catalog.generate_all()
        assert len(all_demos) == 4
        for domain, result in all_demos.items():
            assert result["status"] == "demo_ready"

    def test_unknown_pack_raises(self):
        catalog = DemoCatalog()
        with pytest.raises(ValueError):
            catalog.generate_demo("nonexistent")

    def test_unknown_pack_error_is_bounded(self):
        catalog = DemoCatalog()
        with pytest.raises(ValueError, match="unknown pack") as excinfo:
            catalog.generate_demo("nonexistent")
        assert str(excinfo.value) == "unknown pack"
        assert "nonexistent" not in str(excinfo.value)
        assert "regulated_ops" not in str(excinfo.value)

class TestPipelineOps:
    def test_per_pack_funnel(self):
        pipeline = PackPipeline()
        f = pipeline.get_funnel("regulated_ops")
        f.record_demo("c1")
        f.convert_to_pilot("c1")
        f.convert_to_paid("c1", 2500.0)

        f2 = pipeline.get_funnel("financial_control")
        f2.record_demo("c2")
        f2.convert_to_pilot("c2")
        f2.convert_to_paid("c2", 3000.0)

        assert pipeline.total_mrr() == 5500.0
        assert pipeline.total_arr() == 66000.0

    def test_conversion_report(self):
        pipeline = PackPipeline()
        pipeline.get_funnel("regulated_ops").record_demo("c1")
        report = pipeline.conversion_report()
        assert "regulated_ops" in report

    def test_expansion_scoring(self):
        scores = score_expansion("c1", "regulated_ops", satisfaction=9.0, months_active=6)
        assert len(scores) == 2
        assert scores[0].score > 0.5
        assert scores[0].reason == "expansion opportunity indicators present"
        assert "9.0" not in scores[0].reason

    def test_expansion_paths(self):
        assert len(EXPANSION_PATHS) == 4
        for pack, paths in EXPANSION_PATHS.items():
            assert len(paths) >= 2

class TestDeliveryScaling:
    def test_4_deployment_profiles(self):
        assert len(DEPLOYMENT_PROFILES) == 4

    def test_4_connector_bundles(self):
        assert len(CONNECTOR_BUNDLES) == 4
        for pack, bundle in CONNECTOR_BUNDLES.items():
            assert len(bundle) == 5

    def test_support_runbooks(self):
        assert len(SUPPORT_RUNBOOKS) == 4
        assert len(SUPPORT_RUNBOOKS["factory_quality"]) >= 7  # extra runbooks

    def test_pricing(self):
        assert len(PACK_PRICING) == 4
        assert PACK_PRICING["factory_quality"].industrial_premium == 2000.0
        assert PACK_PRICING["financial_control"].standard_monthly == 3000.0

    def test_addons(self):
        assert len(ADDON_PRICING) >= 6
        assert ADDON_PRICING["robotics_control"] == 1500.0

class TestEndToEndGTM:
    """Golden: Full GTM lifecycle across all 4 packs."""

    def test_portfolio_to_revenue(self):
        # 1. Portfolio exists
        assert len(PORTFOLIO) == 4

        # 2. All demos generate
        catalog = DemoCatalog()
        all_demos = catalog.generate_all()
        assert all(r["status"] == "demo_ready" for r in all_demos.values())

        # 3. Pipeline tracks per pack
        pipeline = PackPipeline()
        for domain in ["regulated_ops", "enterprise_service", "financial_control", "factory_quality"]:
            f = pipeline.get_funnel(domain)
            f.record_demo(f"{domain}-lead-1")
            f.convert_to_pilot(f"{domain}-lead-1")
            price = PACK_PRICING[domain].standard_monthly
            f.convert_to_paid(f"{domain}-lead-1", price)

        assert pipeline.total_mrr() == 12000.0  # 2500+2500+3000+4000
        assert pipeline.total_arr() == 144000.0

        # 4. Expansion scoring
        scores = score_expansion("reg-c1", "regulated_ops", 9.0, 6)
        assert scores[0].recommended_next in ("financial_control", "enterprise_service")
        assert scores[0].reason == "expansion opportunity indicators present"
        assert "months active" not in scores[0].reason

        # 5. Delivery profiles all exist
        assert all(d in DEPLOYMENT_PROFILES for d in ["regulated_ops", "enterprise_service", "financial_control", "factory_quality"])
