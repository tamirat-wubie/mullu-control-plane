"""Phase 148 — Low-Touch Revenue Engine Tests."""
import pytest
from mcoi_runtime.pilot.low_touch_revenue import (
    evaluate_upgrade, SELF_SERVE_OFFERS,
    recommend_expansion, route_account,
    check_self_serve_margin, low_touch_dashboard,
    UpgradeDecision, ExpansionRecommendation, MarginFlag,
)

class TestUpgrade:
    def test_auto_upgrade(self):
        d = evaluate_upgrade("a1", 5, 0.9, 0.8, 10)
        assert d.action == "auto_upgrade"
        assert d.auto_eligible

    def test_prompt_upgrade(self):
        d = evaluate_upgrade("a2", 10, 0.6, 0.6, 3)
        assert d.action == "prompt_upgrade"

    def test_sales_handoff(self):
        d = evaluate_upgrade("a3", 2, 0.3, 0.4, 1)
        assert d.action == "sales_handoff"

    def test_expire(self):
        d = evaluate_upgrade("a4", 0, 0.1, 0.2, 0)
        assert d.action == "expire"

class TestOffers:
    def test_5_offers(self):
        assert len(SELF_SERVE_OFFERS) == 5

    def test_starter_price(self):
        assert SELF_SERVE_OFFERS["starter_regulated"].monthly_price == 999.0

    def test_bundle_price(self):
        assert SELF_SERVE_OFFERS["bundle_regulated_financial"].monthly_price == 4500.0

class TestExpansion:
    def test_pack_upgrade(self):
        recs = recommend_expansion("a1", "regulated_ops_starter", 25, 2, 10, 7.0)
        assert any(r.recommendation == "pack_upgrade" for r in recs)

    def test_bundle_upgrade(self):
        recs = recommend_expansion("a1", "regulated_ops", 10, 5, 10, 8.0)
        assert any(r.recommendation == "bundle_upgrade" for r in recs)

    def test_low_satisfaction(self):
        recs = recommend_expansion("a1", "regulated_ops", 5, 2, 5, 4.0)
        assert any(r.recommendation == "partner_onboarding" for r in recs)

class TestRouting:
    def test_self_serve(self):
        assert route_account(0.9, 0.8, 0, 100, 0.8) == "self_serve"

    def test_sales_assisted(self):
        assert route_account(0.5, 0.7, 2, 200, 0.5) == "sales_assisted"

    def test_disqualify(self):
        assert route_account(0.1, 0.1, 0, 50, 0.05) == "disqualify"

class TestMarginGuard:
    def test_clean(self):
        flags = check_self_serve_margin("a1", 1, 3, 2500, 100)
        assert len(flags) == 0

    def test_high_support(self):
        flags = check_self_serve_margin("a1", 8, 3, 2500, 100)
        assert any(f.flag_type == "high_support" for f in flags)

    def test_underpriced(self):
        flags = check_self_serve_margin("a1", 0, 3, 500, 300)
        assert any(f.flag_type == "underpriced" for f in flags)

class TestGoldenProof:
    def test_full_low_touch_lifecycle(self):
        # 1. Auto-upgrade
        u1 = evaluate_upgrade("g1", 5, 0.9, 0.8, 10)
        assert u1.action == "auto_upgrade"

        # 2. Low-fit routed away
        assert route_account(0.1, 0.15, 0, 50, 0.05) == "disqualify"

        # 3. High-fit gets recommendation
        recs = recommend_expansion("g1", "regulated_ops", 10, 5, 60, 9.0)
        assert len(recs) >= 2

        # 4. In-product expansion triggered
        assert any(r.recommendation == "bundle_upgrade" for r in recs)

        # 5. Expensive flagged
        flags = check_self_serve_margin("g2", 10, 8, 500, 400)
        assert len(flags) >= 2

        # 6. Dashboard
        u2 = evaluate_upgrade("g2", 0, 0.1, 0.2, 0)
        d = low_touch_dashboard([u1, u2], recs, flags)
        assert d["auto_upgrades"] == 1
        assert d["expired_trials"] == 1
        assert d["expansion_acv_potential"] > 0
        assert d["margin_flags_high"] >= 1
