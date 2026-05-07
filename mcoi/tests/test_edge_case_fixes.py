"""Tests for Round 2 audit edge case fixes."""
from __future__ import annotations
import pytest


class TestRateLimitConfigValidation:
    def test_zero_max_tokens_rejected(self):
        from mcoi_runtime.governance.guards.rate_limit import RateLimitConfig
        with pytest.raises(ValueError, match="max_tokens must be >= 1"):
            RateLimitConfig(max_tokens=0)

    def test_negative_refill_rate_rejected(self):
        from mcoi_runtime.governance.guards.rate_limit import RateLimitConfig
        with pytest.raises(ValueError, match="refill_rate must be > 0"):
            RateLimitConfig(refill_rate=-1.0)

    def test_zero_refill_rate_rejected(self):
        from mcoi_runtime.governance.guards.rate_limit import RateLimitConfig
        with pytest.raises(ValueError, match="refill_rate must be > 0"):
            RateLimitConfig(refill_rate=0.0)

    def test_zero_burst_limit_rejected(self):
        from mcoi_runtime.governance.guards.rate_limit import RateLimitConfig
        with pytest.raises(ValueError, match="burst_limit must be >= 1"):
            RateLimitConfig(burst_limit=0)

    def test_valid_config_passes(self):
        from mcoi_runtime.governance.guards.rate_limit import RateLimitConfig
        c = RateLimitConfig(max_tokens=10, refill_rate=0.5, burst_limit=5)
        assert c.max_tokens == 10


class TestRateLimiterBucketEviction:
    def test_bucket_eviction_at_max(self):
        from mcoi_runtime.governance.guards.rate_limit import RateLimiter
        rl = RateLimiter(max_buckets=3)
        rl.check("t1", "/a")
        rl.check("t2", "/b")
        rl.check("t3", "/c")
        assert len(rl._buckets) == 3
        rl.check("t4", "/d")  # should evict oldest
        assert len(rl._buckets) == 3


class TestAuditTrailPruning:
    def test_prunes_at_max_entries(self):
        from mcoi_runtime.governance.audit.trail import AuditTrail
        trail = AuditTrail(clock=lambda: "2026-01-01T00:00:00Z", max_entries=5)
        for i in range(10):
            trail.record(action="test", actor_id="a", tenant_id="t",
                         target="x", outcome="ok")
        assert trail.entry_count <= 5
        assert trail._pruned_count == 5


class TestTenantBudgetNegativeCost:
    def test_negative_cost_rejected(self):
        from mcoi_runtime.governance.guards.budget import TenantBudgetManager
        mgr = TenantBudgetManager(clock=lambda: "2026-01-01T00:00:00Z")
        mgr.ensure_budget("t1")
        with pytest.raises(ValueError, match="cost must be non-negative"):
            mgr.record_spend("t1", cost=-5.0)

    def test_negative_cost_error_is_bounded(self):
        from mcoi_runtime.governance.guards.budget import TenantBudgetManager
        mgr = TenantBudgetManager(clock=lambda: "2026-01-01T00:00:00Z")
        mgr.ensure_budget("t1")
        with pytest.raises(ValueError, match="cost must be non-negative") as excinfo:
            mgr.record_spend("t1", cost=-5.0)
        assert str(excinfo.value) == "cost must be non-negative"
        assert "-5.0" not in str(excinfo.value)

    def test_zero_cost_allowed(self):
        from mcoi_runtime.governance.guards.budget import TenantBudgetManager
        mgr = TenantBudgetManager(clock=lambda: "2026-01-01T00:00:00Z")
        mgr.ensure_budget("t1")
        budget = mgr.record_spend("t1", cost=0.0)
        assert budget.spent == 0.0


class TestBackpressureHysteresis:
    def test_no_oscillation_at_boundary(self):
        from mcoi_runtime.core.backpressure import BackpressureEngine, PressureLevel
        bp = BackpressureEngine(elevated_threshold=60.0, hysteresis_band=5.0)
        # Go above threshold
        bp.update_load(62.0)
        state = bp.evaluate()
        assert state.level == PressureLevel.ELEVATED
        # Drop slightly below threshold but within hysteresis band
        bp.update_load(57.0)
        state = bp.evaluate()
        assert state.level == PressureLevel.ELEVATED  # hysteresis keeps it elevated
        # Drop below hysteresis band
        bp.update_load(54.0)
        state = bp.evaluate()
        assert state.level == PressureLevel.NORMAL

    def test_escalation_still_works(self):
        from mcoi_runtime.core.backpressure import BackpressureEngine, PressureLevel
        bp = BackpressureEngine()
        bp.update_load(96.0)
        assert bp.evaluate().level == PressureLevel.CRITICAL
        bp.update_load(85.0)
        assert bp.evaluate().level in (PressureLevel.HIGH, PressureLevel.CRITICAL)
        bp.update_load(10.0)
        assert bp.evaluate().level == PressureLevel.NORMAL
