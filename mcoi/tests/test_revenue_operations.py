"""Phase 134 — Revenue Operations / Live Sales Execution Tests."""
import pytest
from mcoi_runtime.pilot.target_accounts import TargetAccount, TargetAccountEngine, ICP_DEFINITIONS
from mcoi_runtime.pilot.sales_motion import PLAYBOOKS, DemoToPilotEngine
from mcoi_runtime.pilot.revenue_forecast import REFERENCE_TEMPLATES, RevenueForecastEngine

class TestTargetAccounts:
    def test_icp_definitions(self):
        assert len(ICP_DEFINITIONS) == 4
        for pack, icp in ICP_DEFINITIONS.items():
            assert len(icp["pain_signals"]) >= 4
            assert len(icp["decision_makers"]) >= 3

    def test_scoring(self):
        a = TargetAccount("a1", "Acme", "finance", "regulated_ops", 5000, pain_score=9.0, urgency_score=8.0, connector_fit=0.9, sponsor_identified=True, expansion_packs=("financial_control",))
        assert a.tier == "tier_1"
        assert a.composite_score >= 0.7

    def test_ranking(self):
        engine = TargetAccountEngine()
        engine.add_account(TargetAccount("a1", "Strong", "finance", "regulated_ops", pain_score=9.0, urgency_score=9.0, connector_fit=1.0, sponsor_identified=True))
        engine.add_account(TargetAccount("a2", "Weak", "retail", "enterprise_service", pain_score=3.0, urgency_score=2.0, connector_fit=0.3))
        ranked = engine.rank()
        assert ranked[0].company_name == "Strong"

    def test_by_pack(self):
        engine = TargetAccountEngine()
        engine.add_account(TargetAccount("a1", "A", "fin", "regulated_ops"))
        engine.add_account(TargetAccount("a2", "B", "tech", "enterprise_service"))
        engine.add_account(TargetAccount("a3", "C", "fin", "regulated_ops"))
        assert len(engine.by_pack("regulated_ops")) == 2

    def test_summary(self):
        engine = TargetAccountEngine()
        for i in range(10):
            engine.add_account(TargetAccount(f"a{i}", f"Corp{i}", "fin", "regulated_ops", pain_score=float(i)))
        s = engine.summary()
        assert s["total"] == 10

class TestSalesMotion:
    def test_4_playbooks(self):
        assert len(PLAYBOOKS) == 4

    def test_each_has_content(self):
        for pack, pb in PLAYBOOKS.items():
            assert pb.outbound_narrative
            assert len(pb.discovery_questions) >= 4
            assert len(pb.demo_script_steps) >= 4
            assert len(pb.objections) >= 2
            assert len(pb.roi_levers) >= 3

    def test_funnel_tracking(self):
        engine = DemoToPilotEngine()
        engine.record("a1", "regulated_ops", "outreach")
        engine.record("a1", "regulated_ops", "meeting")
        engine.record("a1", "regulated_ops", "demo")
        engine.record("a1", "regulated_ops", "pilot_proposed")
        engine.record("a1", "regulated_ops", "pilot_accepted")
        engine.record("a1", "regulated_ops", "pilot_completed")
        engine.record("a1", "regulated_ops", "converted")
        assert engine.total_entries == 7
        assert engine.stage_counts()["converted"] == 1

    def test_conversion_rates(self):
        engine = DemoToPilotEngine()
        for i in range(10):
            engine.record(f"a{i}", "regulated_ops", "demo")
        for i in range(4):
            engine.record(f"a{i}", "regulated_ops", "pilot_proposed")
        s = engine.summary()
        assert s["demo_to_pilot"] == pytest.approx(0.4, abs=0.01)

class TestRevenueForecasting:
    def test_reference_templates(self):
        assert len(REFERENCE_TEMPLATES) == 4
        for pack, ref in REFERENCE_TEMPLATES.items():
            assert ref.roi_highlight
            assert ref.before_metrics
            assert ref.after_metrics

    def test_forecast(self):
        engine = RevenueForecastEngine()
        engine.add_forecast("regulated_ops", "pilot", 5, 2500.0, 0.6)
        engine.add_forecast("enterprise_service", "demo", 10, 2500.0, 0.2)
        engine.add_forecast("financial_control", "paid", 2, 3000.0, 1.0)
        engine.add_forecast("factory_quality", "pilot", 3, 4000.0, 0.5)

        assert engine.total_pipeline > 0
        assert engine.weighted_pipeline > 0
        assert engine.expected_arr > 0
        s = engine.summary()
        assert s["entries"] == 4

    def test_by_pack_forecast(self):
        engine = RevenueForecastEngine()
        engine.add_forecast("regulated_ops", "paid", 3, 2500.0, 1.0)
        engine.add_forecast("financial_control", "paid", 2, 3000.0, 1.0)
        assert engine.by_pack("regulated_ops") == 7500.0
        assert engine.by_pack("financial_control") == 6000.0

class TestEndToEndRevOps:
    """Golden: Full revenue operations lifecycle."""

    def test_complete_revops_cycle(self):
        # 1. Build target list
        engine = TargetAccountEngine()
        accounts = [
            TargetAccount("t1", "BigBank", "finance", "regulated_ops", 5000, 9.0, 8.0, 0.9, True, ("financial_control",)),
            TargetAccount("t2", "TechCorp", "tech", "enterprise_service", 3000, 7.0, 7.0, 0.8, True, ("regulated_ops",)),
            TargetAccount("t3", "MfgInc", "manufacturing", "factory_quality", 8000, 8.0, 9.0, 0.7, True, ("financial_control",)),
            TargetAccount("t4", "FinServ", "fintech", "financial_control", 1000, 8.0, 6.0, 0.9, True, ()),
        ]
        for a in accounts:
            engine.add_account(a)
        assert len(engine.tier_1_accounts()) >= 2

        # 2. Run sales funnel
        funnel = DemoToPilotEngine()
        for a in accounts:
            funnel.record(a.account_id, a.primary_pack, "demo")
        for a in accounts[:3]:
            funnel.record(a.account_id, a.primary_pack, "pilot_proposed")
        for a in accounts[:2]:
            funnel.record(a.account_id, a.primary_pack, "pilot_completed")
            funnel.record(a.account_id, a.primary_pack, "converted")

        assert funnel.stage_counts()["converted"] == 2

        # 3. Revenue forecast
        forecast = RevenueForecastEngine()
        forecast.add_forecast("regulated_ops", "paid", 1, 2500.0, 1.0)
        forecast.add_forecast("enterprise_service", "paid", 1, 2500.0, 1.0)
        forecast.add_forecast("factory_quality", "pilot", 1, 4000.0, 0.5)
        forecast.add_forecast("financial_control", "demo", 1, 3000.0, 0.2)

        s = forecast.summary()
        assert s["weighted_pipeline_mrr"] > 5000  # at least 2 paid + weighted pipeline
        assert s["expected_arr"] > 60000

        # 4. Reference customers exist
        assert len(REFERENCE_TEMPLATES) == 4

        # 5. Playbooks exist for all packs
        assert len(PLAYBOOKS) == 4
