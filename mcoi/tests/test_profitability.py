"""Phase 137 — Multi-Pack Margin Optimization Tests."""
import pytest
from mcoi_runtime.pilot.profitability import (
    CustomerUnitEconomics, ProfitabilityEngine, PricingFitness, ExpansionRecommendation,
)

def _healthy_account(cid="c1", pack="regulated_ops"):
    return CustomerUnitEconomics(cid, pack, monthly_revenue=2500, implementation_cost=5000,
        monthly_support_cost=200, monthly_connector_cost=100, monthly_compute_cost=50, delivery_hours=40, hypercare_hours=20)

def _thin_account(cid="c2", pack="enterprise_service"):
    return CustomerUnitEconomics(cid, pack, monthly_revenue=2500, implementation_cost=8000,
        monthly_support_cost=800, monthly_connector_cost=300, monthly_compute_cost=200, delivery_hours=80, hypercare_hours=40)

def _factory_account(cid="c3", pack="factory_quality"):
    return CustomerUnitEconomics(cid, pack, monthly_revenue=4000, implementation_cost=12000,
        monthly_support_cost=400, monthly_connector_cost=200, monthly_compute_cost=150, delivery_hours=60, hypercare_hours=30)

class TestUnitEconomics:
    def test_healthy_margin(self):
        e = _healthy_account()
        assert e.gross_margin >= 0.7
        assert e.margin_status == "healthy"

    def test_thin_margin(self):
        e = _thin_account()
        assert e.gross_margin < 0.5
        assert e.margin_status in ("thin", "unprofitable")

    def test_total_cost(self):
        e = _healthy_account()
        assert e.total_monthly_cost == 350  # 200+100+50

class TestMarginDashboard:
    def test_margin_by_pack(self):
        engine = ProfitabilityEngine()
        engine.register_economics(_healthy_account())
        engine.register_economics(_thin_account())
        engine.register_economics(_factory_account())
        margins = engine.margin_by_pack()
        assert len(margins) == 3
        assert margins["regulated_ops"] > margins["enterprise_service"]

    def test_highest_lowest_pack(self):
        engine = ProfitabilityEngine()
        engine.register_economics(_healthy_account())
        engine.register_economics(_thin_account())
        assert engine.highest_margin_pack() == "regulated_ops"
        assert engine.lowest_margin_pack() == "enterprise_service"

    def test_below_target(self):
        engine = ProfitabilityEngine()
        engine.register_economics(_healthy_account())
        engine.register_economics(_thin_account())
        below = engine.below_margin_target(0.5)
        assert len(below) == 1
        assert below[0].customer_id == "c2"

    def test_support_heavy(self):
        engine = ProfitabilityEngine()
        engine.register_economics(_healthy_account())
        engine.register_economics(_thin_account())
        heavy = engine.support_heavy_accounts(500)
        assert len(heavy) == 1

class TestPricingFitness:
    def test_appropriate_pricing(self):
        engine = ProfitabilityEngine()
        engine.register_economics(_healthy_account())
        fitness = engine.assess_pricing("c1")
        assert fitness.usage_intensity == "light"

    def test_underpriced_detection(self):
        engine = ProfitabilityEngine()
        bad = CustomerUnitEconomics("c5", "enterprise_service", 2500, 8000, 1200, 500, 300, 80, 40)
        engine.register_economics(bad)
        fitness = engine.assess_pricing("c5")
        assert fitness.recommendation == "underpriced"

class TestExpansion:
    def test_profit_aware_expansion(self):
        engine = ProfitabilityEngine()
        engine.register_economics(_healthy_account())
        rec = engine.recommend_expansion("c1", "financial_control", 3000.0)
        assert rec.profit_aware is True
        assert rec.support_risk == "low"
        assert rec.reason == "supported expansion indicators present"
        assert "Current margin" not in rec.reason

    def test_high_risk_expansion(self):
        engine = ProfitabilityEngine()
        engine.register_economics(_thin_account())
        rec = engine.recommend_expansion("c2", "financial_control", 3000.0)
        assert rec.support_risk == "high"
        assert rec.profit_aware is False
        assert rec.reason == "supported expansion indicators present"
        assert "support risk" not in rec.reason

class TestDeliveryEfficiency:
    def test_efficiency_report(self):
        engine = ProfitabilityEngine()
        engine.register_economics(_healthy_account())
        engine.register_economics(_thin_account())
        engine.register_economics(_factory_account())
        report = engine.delivery_efficiency_report()
        assert report["accounts"] == 3
        assert report["avg_delivery_hours"] > 0

class TestGoldenProof:
    def test_complete_profitability_lifecycle(self):
        engine = ProfitabilityEngine()

        # Register 4 customers across packs
        engine.register_economics(_healthy_account("c1", "regulated_ops"))
        engine.register_economics(_thin_account("c2", "enterprise_service"))
        engine.register_economics(_factory_account("c3", "factory_quality"))
        engine.register_economics(CustomerUnitEconomics("c4", "financial_control", 3000, 6000, 300, 150, 100, 50, 25))

        # 1. Per-pack margin computed
        margins = engine.margin_by_pack()
        assert len(margins) == 4

        # 2. Least profitable identified
        assert engine.lowest_margin_pack() is not None

        # 3. Pricing mismatch detected — add truly underpriced account
        engine.register_economics(CustomerUnitEconomics("c5", "enterprise_service", 2000, 8000, 1200, 500, 300, 80, 40))
        fitness = engine.assess_pricing("c5")
        assert fitness.recommendation == "underpriced"

        # 4. Support-heavy surfaced
        heavy = engine.support_heavy_accounts(500)
        assert len(heavy) >= 1

        # 5. Expansion is profit-aware
        rec = engine.recommend_expansion("c1", "financial_control", 3000)
        assert rec.profit_aware is True
        bad_rec = engine.recommend_expansion("c2", "regulated_ops", 2500)
        assert bad_rec.profit_aware is False

        # 6. Executive dashboard usable
        dashboard = engine.profitability_dashboard()
        assert dashboard["total_accounts"] == 5
        assert dashboard["total_mrr"] == 14000  # 2500+2500+4000+3000+2000
        assert dashboard["blended_margin"] > 0
        assert dashboard["below_target_count"] >= 1
        assert dashboard["profit_aware_expansions"] >= 1
