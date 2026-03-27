"""Tests for Phase 230C — Governed Retry Policy Engine."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.retry_policy import (
    RetryPolicyEngine, RetryPolicy, RetryOutcome,
)


class TestRetryPolicyEngine:
    def test_success_first_try(self):
        engine = RetryPolicyEngine()
        result, value = engine.execute("op", lambda: 42)
        assert result.outcome == RetryOutcome.SUCCESS
        assert result.attempts == 1
        assert value == 42

    def test_retry_then_success(self):
        counter = {"n": 0}
        def flaky():
            counter["n"] += 1
            if counter["n"] < 3:
                raise ValueError("not yet")
            return "ok"
        engine = RetryPolicyEngine(RetryPolicy(
            max_retries=5, base_delay_seconds=0.001, jitter=False,
        ))
        result, value = engine.execute("op", flaky)
        assert result.outcome == RetryOutcome.SUCCESS
        assert result.attempts == 3
        assert value == "ok"

    def test_exhausted(self):
        engine = RetryPolicyEngine(RetryPolicy(
            max_retries=2, base_delay_seconds=0.001, jitter=False,
        ))
        def always_fail():
            raise RuntimeError("fail")
        result, value = engine.execute("op", always_fail)
        assert result.outcome == RetryOutcome.EXHAUSTED
        assert result.attempts == 3  # 1 + 2 retries
        assert value is None
        assert "fail" in result.last_error

    def test_budget_exceeded(self):
        engine = RetryPolicyEngine(RetryPolicy(
            max_retries=1, base_delay_seconds=0.001,
            retry_budget_per_minute=2, jitter=False,
        ))
        # Exhaust budget
        for _ in range(3):
            engine.execute("op", lambda: (_ for _ in ()).throw(ValueError("x")))
        result, _ = engine.execute("op", lambda: 1)
        assert result.outcome == RetryOutcome.BUDGET_EXCEEDED

    def test_custom_policy_per_operation(self):
        engine = RetryPolicyEngine()
        engine.set_policy("critical", RetryPolicy(max_retries=5))
        engine.set_policy("best-effort", RetryPolicy(max_retries=1))
        s = engine.summary()
        assert s["policies_registered"] == 2

    def test_exponential_backoff(self):
        engine = RetryPolicyEngine(RetryPolicy(
            max_retries=3, base_delay_seconds=0.001,
            exponential_base=2.0, jitter=False,
        ))
        result, _ = engine.execute("op", lambda: (_ for _ in ()).throw(ValueError()))
        assert result.total_delay_seconds > 0

    def test_to_dict(self):
        engine = RetryPolicyEngine()
        result, _ = engine.execute("op", lambda: 1)
        d = result.to_dict()
        assert d["outcome"] == "success"
        assert d["attempts"] == 1

    def test_summary(self):
        engine = RetryPolicyEngine()
        engine.execute("op", lambda: 1)
        s = engine.summary()
        assert s["total_successes"] == 1
