"""Tests for Phase 164 — Customer Success Automation 2.0."""
import pytest
from mcoi_runtime.pilot.cs_automation import (
    MATURITY_STAGES,
    SIGNAL_TYPES,
    CSAutomationEngine,
    CustomerHealthSignal,
)


class TestCustomerHealthSignal:
    def test_valid_signal(self):
        s = CustomerHealthSignal("acct1", "adoption_weak", "high", "test")
        assert s.signal_type == "adoption_weak"

    def test_invalid_signal_type(self):
        with pytest.raises(ValueError, match="Invalid signal_type"):
            CustomerHealthSignal("acct1", "bad_type", "low", "x")

    def test_invalid_severity(self):
        with pytest.raises(ValueError, match="Invalid severity"):
            CustomerHealthSignal("acct1", "adoption_weak", "extreme", "x")


class TestCSAutomationEngine:
    def test_detect_weak_adoption_fires(self):
        eng = CSAutomationEngine()
        sig = eng.detect_weak_adoption("a1", dashboard_views=1, workflow_completions=0, copilot_queries=2)
        assert sig is not None
        assert sig.signal_type == "adoption_weak"
        assert sig.severity == "critical"

    def test_detect_weak_adoption_healthy(self):
        eng = CSAutomationEngine()
        sig = eng.detect_weak_adoption("a1", 20, 10, 5)
        assert sig is None

    def test_detect_renewal_risk_fires(self):
        eng = CSAutomationEngine()
        sig = eng.detect_renewal_risk("a1", satisfaction=3.0, support_tickets=15, days_to_renewal=50)
        assert sig is not None
        assert sig.signal_type == "renewal_risk"
        assert sig.severity == "critical"

    def test_detect_renewal_risk_safe(self):
        eng = CSAutomationEngine()
        sig = eng.detect_renewal_risk("a1", satisfaction=9.0, support_tickets=1, days_to_renewal=200)
        assert sig is None

    def test_suggest_expansion(self):
        eng = CSAutomationEngine()
        sig = eng.suggest_expansion("a1", activation_rate=0.92, months_active=6, current_pack="core")
        assert sig is not None
        assert sig.signal_type == "expansion_ready"
        assert sig.severity == "medium"

    def test_suggest_expansion_too_early(self):
        eng = CSAutomationEngine()
        sig = eng.suggest_expansion("a1", activation_rate=0.5, months_active=1, current_pack="core")
        assert sig is None

    def test_detect_stakeholder_risk(self):
        eng = CSAutomationEngine()
        sig = eng.detect_stakeholder_risk("a1", executive_logins_30d=0, last_review_days_ago=90)
        assert sig is not None
        assert sig.severity == "critical"

    def test_track_maturity_stages(self):
        eng = CSAutomationEngine()
        assert eng.track_maturity("a1", months_active=0, workflows_completed=0, packs_active=0) == "onboarding"
        assert eng.track_maturity("a1", months_active=3, workflows_completed=20, packs_active=1) == "adopting"
        assert eng.track_maturity("a1", months_active=8, workflows_completed=60, packs_active=2) == "mature"
        assert eng.track_maturity("a1", months_active=14, workflows_completed=250, packs_active=4) == "champion"

    def test_all_signals_golden(self):
        """Golden proof: an unhealthy account triggers multiple signals."""
        eng = CSAutomationEngine()
        metrics = {
            "dashboard_views": 2,
            "workflow_completions": 1,
            "copilot_queries": 0,
            "satisfaction": 3.5,
            "support_tickets": 12,
            "days_to_renewal": 45,
            "activation_rate": 0.3,
            "months_active": 1,
            "current_pack": "core",
            "executive_logins_30d": 0,
            "last_review_days_ago": 70,
        }
        signals = eng.all_signals("acct_unhealthy", metrics)
        types = {s.signal_type for s in signals}
        assert "adoption_weak" in types
        assert "renewal_risk" in types
        assert "stakeholder_disengaged" in types
        # expansion should NOT fire (low activation + early)
        assert "expansion_ready" not in types

    def test_summary_counts(self):
        eng = CSAutomationEngine()
        eng.detect_weak_adoption("a1", 1, 0, 0)
        eng.detect_weak_adoption("a2", 2, 1, 0)
        eng.detect_renewal_risk("a1", 3.0, 15, 30)
        s = eng.summary()
        assert s["adoption_weak"] == 2
        assert s["renewal_risk"] == 1
