"""Phase 135 — Customer Delivery Scale / Support Organization Tests."""
import pytest
from mcoi_runtime.pilot.delivery_org import DELIVERY_ROLES, HANDOFF_CHAIN, SUPPORT_TIERS, ISSUE_CLASSIFICATION
from mcoi_runtime.pilot.customer_success_ops import CustomerSuccessEngine, CustomerHealthRecord
from mcoi_runtime.pilot.delivery_playbooks import PLAYBOOKS
from mcoi_runtime.pilot.support_analytics import SupportAnalyticsEngine

class TestDeliveryOrg:
    def test_7_roles(self):
        assert len(DELIVERY_ROLES) == 7
    def test_handoff_chain(self):
        assert len(HANDOFF_CHAIN) == 6
    def test_4_support_tiers(self):
        assert len(SUPPORT_TIERS) == 4
        assert SUPPORT_TIERS["enterprise"].dedicated_csm is True
    def test_issue_classification(self):
        assert len(ISSUE_CLASSIFICATION) >= 6

class TestCustomerSuccess:
    def test_register_and_health(self):
        engine = CustomerSuccessEngine()
        engine.register_customer("c1", "regulated_ops")
        engine.update_health("c1", onboarding_complete=True, adoption_score=9.0, stakeholder_engaged=True, expansion_ready=True)
        rec = engine._customers["c1"]
        assert rec.health_status == "champion"
        assert rec.renewal_risk == "low"

    def test_unknown_customer_error_is_bounded(self):
        engine = CustomerSuccessEngine()
        with pytest.raises(ValueError, match="unknown customer") as excinfo:
            engine.update_health("cust-404", adoption_score=5.0)
        assert str(excinfo.value) == "unknown customer"
        assert "cust-404" not in str(excinfo.value)

    def test_at_risk(self):
        engine = CustomerSuccessEngine()
        engine.register_customer("c1", "regulated_ops")
        engine.update_health("c1", adoption_score=3.0, unresolved_blockers=5)
        assert engine._customers["c1"].health_status == "critical"
        assert len(engine.at_risk_customers()) == 1

    def test_expansion_candidates(self):
        engine = CustomerSuccessEngine()
        engine.register_customer("c1", "regulated_ops")
        engine.update_health("c1", onboarding_complete=True, adoption_score=9.0, expansion_ready=True)
        assert len(engine.expansion_candidates()) == 1

    def test_dashboard(self):
        engine = CustomerSuccessEngine()
        engine.register_customer("c1", "regulated_ops")
        engine.register_customer("c2", "enterprise_service")
        engine.update_health("c1", onboarding_complete=True, adoption_score=8.5)
        d = engine.dashboard()
        assert d["total_customers"] == 2

class TestDeliveryPlaybooks:
    def test_4_playbooks(self):
        assert len(PLAYBOOKS) == 4
    def test_each_has_6_phases(self):
        for pack, pb in PLAYBOOKS.items():
            assert pb.total_phases == 6
            assert len(pb.phases) == 6
    def test_factory_has_shift_training(self):
        fb = PLAYBOOKS["factory_quality"]
        training = [p for p in fb.phases if p.phase == "training"][0]
        assert any("shift" in item.lower() for item in training.items)

class TestSupportAnalytics:
    def test_create_and_resolve(self):
        engine = SupportAnalyticsEngine()
        engine.create_ticket("t1", "c1", "regulated_ops", "break_fix", "high")
        assert engine.open_count() == 1
        engine.resolve_ticket("t1")
        assert engine.open_count() == 0

    def test_unknown_ticket_error_is_bounded(self):
        engine = SupportAnalyticsEngine()
        with pytest.raises(ValueError, match="unknown ticket") as excinfo:
            engine.resolve_ticket("ticket-404")
        assert str(excinfo.value) == "unknown ticket"
        assert "ticket-404" not in str(excinfo.value)

    def test_by_category(self):
        engine = SupportAnalyticsEngine()
        engine.create_ticket("t1", "c1", "regulated_ops", "connector", "high")
        engine.create_ticket("t2", "c1", "regulated_ops", "connector", "medium")
        engine.create_ticket("t3", "c2", "enterprise_service", "training", "low")
        cats = engine.by_category()
        assert cats["connector"] == 2
        assert cats["training"] == 1

    def test_repeat_issues(self):
        engine = SupportAnalyticsEngine()
        for i in range(5):
            engine.create_ticket(f"t{i}", "c1", "regulated_ops", "break_fix", "medium")
        engine.create_ticket("t5", "c2", "enterprise_service", "training", "low")
        repeats = engine.repeat_issues()
        assert "c1" in repeats
        assert "c2" not in repeats

    def test_dashboard(self):
        engine = SupportAnalyticsEngine()
        engine.create_ticket("t1", "c1", "regulated_ops", "connector", "critical")
        d = engine.dashboard()
        assert d["total_tickets"] == 1
        assert d["by_severity"]["critical"] == 1

class TestEndToEndDeliveryScale:
    def test_full_delivery_lifecycle(self):
        # 1. Roles defined
        assert len(DELIVERY_ROLES) == 7

        # 2. Register customers
        success = CustomerSuccessEngine()
        for cid, pack in [("c1", "regulated_ops"), ("c2", "enterprise_service"), ("c3", "financial_control"), ("c4", "factory_quality")]:
            success.register_customer(cid, pack)

        # 3. Playbooks exist for all packs
        assert all(p in PLAYBOOKS for p in ["regulated_ops", "enterprise_service", "financial_control", "factory_quality"])

        # 4. Support analytics
        support = SupportAnalyticsEngine()
        support.create_ticket("t1", "c1", "regulated_ops", "connector", "high")
        support.create_ticket("t2", "c2", "enterprise_service", "training", "low")
        assert support.dashboard()["total_tickets"] == 2

        # 5. Customer health tracking
        success.update_health("c1", onboarding_complete=True, adoption_score=9.0, expansion_ready=True)
        success.update_health("c2", onboarding_complete=True, adoption_score=7.0)
        success.update_health("c3", adoption_score=3.0, unresolved_blockers=4)
        success.update_health("c4", onboarding_complete=True, adoption_score=8.0)

        d = success.dashboard()
        assert d["total_customers"] == 4
        assert d["at_risk"] >= 1
        assert d["expansion_candidates"] >= 1

        # 6. Renewal actions
        success.record_action("c1", "expansion_proposed", "Financial Control cross-sell")
        success.record_action("c3", "risk_intervention", "Adoption support escalated")
        assert success.dashboard()["total_actions"] == 2
