"""Phase 147 — PLG Optimization Tests."""
import pytest
from mcoi_runtime.pilot.plg_optimization import (
    FunnelInstrumentation, FUNNEL_STAGES,
    ActivationEngine, ActivationScore, ACTIVATION_MILESTONES,
    NUDGES, recommend_nudge,
    TrialEconomics,
    pack_activation_ranking, growth_dashboard,
)

class TestFunnel:
    def test_record_and_query(self):
        f = FunnelInstrumentation()
        f.record("a1", "regulated_ops", "self_serve", "signup")
        f.record("a1", "regulated_ops", "self_serve", "qualify")
        f.record("a1", "regulated_ops", "self_serve", "first_workflow")
        assert f.total_entries == 3

    def test_conversion_rate(self):
        f = FunnelInstrumentation()
        for i in range(10):
            f.record(f"a{i}", "regulated_ops", "self_serve", "signup")
        for i in range(4):
            f.record(f"a{i}", "regulated_ops", "self_serve", "first_workflow")
        assert f.conversion_rate("regulated_ops", "self_serve", "signup", "first_workflow") == pytest.approx(0.4)

    def test_by_pack_channel(self):
        f = FunnelInstrumentation()
        f.record("a1", "regulated_ops", "direct", "signup")
        f.record("a2", "enterprise_service", "self_serve", "signup")
        result = f.by_pack_channel()
        assert len(result) == 2

class TestActivation:
    def test_scoring(self):
        s = ActivationScore("a1", milestones_hit=7)
        assert s.status == "activated"

    def test_stalled(self):
        s = ActivationScore("a1", milestones_hit=4)
        assert s.status == "partially_activated"

    def test_engine(self):
        eng = ActivationEngine()
        eng.track("a1", 8)
        eng.track("a2", 2)
        eng.track("a3", 0)
        assert len(eng.activated_accounts()) == 1
        assert len(eng.stalled_accounts()) == 1
        assert eng.summary()["activated"] == 1

class TestNudges:
    def test_8_nudges(self):
        assert len(NUDGES) == 8

    def test_stalled_nudge(self):
        score = ActivationScore("a1", 3)
        nudge = recommend_nudge(score, 10)
        assert nudge is not None
        assert nudge.route_to == "sales_assist"

    def test_low_likelihood_nudge(self):
        score = ActivationScore("a1", 0)
        nudge = recommend_nudge(score, 3)
        assert nudge.route_to == "disqualify"

class TestTrialEconomics:
    def test_high_return(self):
        e = TrialEconomics("a1", 100, 50, 200, 0.8, 30000, 0.7)
        assert e.trial_cost == 350
        assert e.expected_return > 5000
        assert e.flag == "high_return"

    def test_expensive_low(self):
        e = TrialEconomics("a2", 500, 300, 500, 0.1, 2500, 0.3)
        assert e.flag == "expensive_low_likelihood"

class TestGrowthDashboard:
    def test_dashboard(self):
        f = FunnelInstrumentation()
        for i in range(20):
            f.record(f"a{i}", "regulated_ops", "self_serve", "signup")
        for i in range(8):
            f.record(f"a{i}", "regulated_ops", "self_serve", "first_workflow")

        eng = ActivationEngine()
        eng.track("a0", 8)
        eng.track("a1", 5)
        eng.track("a2", 2)

        econ = [
            TrialEconomics("a0", 100, 50, 100, 0.9, 30000, 0.7),
            TrialEconomics("a2", 500, 300, 500, 0.05, 2500, 0.2),
        ]

        d = growth_dashboard(f, eng, econ)
        assert d["total_funnel_entries"] == 28
        assert d["activated"] == 1
        assert d["high_return_trials"] == 1
        assert d["expensive_trials"] == 1

class TestGoldenProof:
    def test_full_plg_optimization(self):
        # 1. Funnel by pack and channel
        f = FunnelInstrumentation()
        for pack in ["regulated_ops", "enterprise_service"]:
            for ch in ["direct", "self_serve"]:
                for i in range(5):
                    f.record(f"{pack}-{ch}-{i}", pack, ch, "signup")
                for i in range(2):
                    f.record(f"{pack}-{ch}-{i}", pack, ch, "first_workflow")
        assert f.total_entries == 28

        # 2. Activation milestones
        eng = ActivationEngine()
        eng.track("active-1", 8)
        eng.track("stalled-1", 2)
        eng.track("partial-1", 5)
        assert "activated" in eng.summary()

        # 3. Friction identified
        ranking = pack_activation_ranking(f)
        assert len(ranking) == 2

        # 4. Expensive trial flagged
        econ = [TrialEconomics("bad", 800, 400, 600, 0.05, 2500, 0.1)]
        assert econ[0].flag == "expensive_low_likelihood"

        # 5. Nudge routing
        nudge = recommend_nudge(ActivationScore("stalled-1", 2), 10)
        assert nudge is not None

        # 6. Executive dashboard
        d = growth_dashboard(f, eng, econ)
        assert d["total_tracked_accounts"] == 3
        assert d["nudges_available"] == 8
