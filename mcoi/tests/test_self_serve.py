"""Phase 146 — Self-Serve Onboarding Tests."""
import pytest
from mcoi_runtime.pilot.self_serve import (
    SignupRecord, qualify_signup, TRIAL_CONFIGS, TrialTenantManager,
    ONBOARDING_STEPS, OnboardingProgress,
    TrialMetrics, recommend_conversion,
    FrictionTracker,
)

class TestSignupQualification:
    def test_strong_signup(self):
        s = SignupRecord("a1", "BigCorp", "cfo@big.com", "financial_services", 20, ("slow_approvals", "missing_evidence", "late_reports"), "regulated_ops")
        q = qualify_signup(s)
        assert q.recommended_path == "pilot"
        assert q.fit_score >= 0.7

    def test_weak_signup(self):
        s = SignupRecord("a2", "TinyCo", "info@tiny.com", "other", 2, ())
        q = qualify_signup(s)
        assert q.recommended_path in ("demo_only", "sales_assisted")

    def test_medium_signup(self):
        s = SignupRecord("a3", "MidCorp", "ops@mid.com", "technology", 8, ("visibility",), "enterprise_service")
        q = qualify_signup(s)
        assert q.recommended_path in ("trial", "pilot")

class TestTrialTenant:
    def test_create_trial(self):
        mgr = TrialTenantManager()
        t = mgr.create_trial("a1", "regulated_ops", "trial")
        assert t["status"] == "active"
        assert t["seeded"]
        assert mgr.active_trials == 1

    def test_trial_configs(self):
        assert TRIAL_CONFIGS["demo"].max_users == 1
        assert TRIAL_CONFIGS["trial"].trial_days == 14
        assert TRIAL_CONFIGS["pilot_ready"].auto_expire is False

class TestOnboarding:
    def test_8_steps(self):
        assert len(ONBOARDING_STEPS) == 8

    def test_progress(self):
        p = OnboardingProgress("a1")
        p.complete_step(1)
        p.complete_step(2)
        p.complete_step(3)
        assert p.completion_rate == pytest.approx(0.375, abs=0.01)
        assert not p.first_value_reached

    def test_first_value(self):
        p = OnboardingProgress("a1")
        for i in range(1, 8):
            p.complete_step(i)
        assert p.first_value_reached
        assert p.next_step == "try_copilot"

class TestConversion:
    def test_strong_conversion(self):
        m = TrialMetrics("a1", onboarding_completion=0.9, workflows_completed=5, dashboard_views=20, copilot_queries=10, connectors_activated=3, days_active=10)
        r = recommend_conversion(m)
        assert r["action"] == "convert_to_paid"
        assert r["score"] >= 0.7

    def test_weak_conversion(self):
        m = TrialMetrics("a2", onboarding_completion=0.2, workflows_completed=0, dashboard_views=1, copilot_queries=0, connectors_activated=0, days_active=2)
        r = recommend_conversion(m)
        assert r["action"] == "route_to_sales"

class TestFriction:
    def test_tracking(self):
        ft = FrictionTracker()
        ft.record("a1", "connect_first_system", "drop_off")
        ft.record("a2", "connect_first_system", "failure")
        ft.record("a3", "load_sample_data", "drop_off")
        s = ft.summary()
        assert s["total_events"] == 3
        assert s["drop_offs"] == 2

    def test_worst_step(self):
        ft = FrictionTracker()
        ft.record("a1", "connect", "drop_off")
        ft.record("a2", "connect", "drop_off")
        ft.record("a3", "import", "failure")
        assert ft.worst_step() == "connect"

class TestGoldenProof:
    def test_full_self_serve_lifecycle(self):
        # 1. Signup
        signup = SignupRecord("ss-1", "ProspectCorp", "ops@prospect.com", "financial_services", 15, ("compliance_gaps", "slow_reporting", "evidence_manual"), "regulated_ops")
        qualified = qualify_signup(signup)
        assert qualified.recommended_path == "pilot"

        # 2. Trial tenant
        mgr = TrialTenantManager()
        tenant = mgr.create_trial("ss-1", "regulated_ops", "trial")
        assert tenant["status"] == "active"

        # 3. Onboarding
        progress = OnboardingProgress("ss-1")
        for step in range(1, 9):
            progress.complete_step(step)
        assert progress.completion_rate == 1.0
        assert progress.first_value_reached

        # 4. Trial metrics
        metrics = TrialMetrics("ss-1", 1.0, 8, 25, 12, 3, 5, 2, 12)

        # 5. Conversion
        rec = recommend_conversion(metrics)
        assert rec["action"] == "convert_to_paid"
        assert rec["score"] >= 0.7

        # 6. No major friction
        ft = FrictionTracker()
        ft.record("ss-1", "connect_first_system", "slow")
        assert ft.summary()["drop_offs"] == 0
