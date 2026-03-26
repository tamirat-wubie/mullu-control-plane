"""Phase 217 — Usage reporter and rate limit headers tests."""

import pytest
from mcoi_runtime.core.usage_reporter import UsageReporter
from mcoi_runtime.core.rate_limit_middleware import rate_limit_headers

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestUsageReporter:
    def test_generate(self):
        reporter = UsageReporter(clock=FIXED_CLOCK)
        reporter.register_source("llm_calls", lambda tid: 42)
        reporter.register_source("total_cost", lambda tid: 1.5)
        report = reporter.generate("t1")
        assert report.tenant_id == "t1"
        assert report.llm_calls == 42
        assert report.total_cost == 1.5

    def test_missing_source(self):
        reporter = UsageReporter(clock=FIXED_CLOCK)
        report = reporter.generate("t1")
        assert report.llm_calls == 0

    def test_error_source(self):
        reporter = UsageReporter(clock=FIXED_CLOCK)
        reporter.register_source("llm_calls", lambda tid: (_ for _ in ()).throw(RuntimeError("fail")))
        report = reporter.generate("t1")
        assert report.llm_calls == 0

    def test_summary(self):
        reporter = UsageReporter(clock=FIXED_CLOCK)
        reporter.register_source("a", lambda tid: 0)
        assert "a" in reporter.summary()["sources"]


class TestRateLimitHeaders:
    def test_basic(self):
        headers = rate_limit_headers(remaining=50, limit=60)
        assert headers["X-RateLimit-Limit"] == "60"
        assert headers["X-RateLimit-Remaining"] == "50"

    def test_with_retry(self):
        headers = rate_limit_headers(remaining=0, limit=60, retry_after=5.0)
        assert headers["Retry-After"] == "5"

    def test_no_retry(self):
        headers = rate_limit_headers(remaining=10, limit=60)
        assert "Retry-After" not in headers

    def test_negative_remaining(self):
        headers = rate_limit_headers(remaining=-5, limit=60)
        assert headers["X-RateLimit-Remaining"] == "0"
