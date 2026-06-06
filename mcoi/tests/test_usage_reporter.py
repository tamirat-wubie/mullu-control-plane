"""Phase 217 — Usage reporter and rate limit headers tests."""

from mcoi_runtime.core.usage_reporter import UsageReporter
from mcoi_runtime.core.rate_limit_middleware import rate_limit_headers


def FIXED_CLOCK() -> str:
    return "2026-03-26T12:00:00Z"


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
        reporter.register_source(
            "llm_calls",
            lambda tid: (_ for _ in ()).throw(RuntimeError("secret failure detail")),
        )
        report = reporter.generate("t1")
        summary = reporter.summary()
        assert report.llm_calls == 0
        assert summary["source_error_count"] == 1
        assert summary["source_errors"] == {"llm_calls": "usage source error (RuntimeError)"}
        assert "secret failure detail" not in str(summary)

    def test_successful_source_clears_last_error_but_keeps_count(self):
        reporter = UsageReporter(clock=FIXED_CLOCK)
        calls = {"count": 0}

        def source(_: str) -> int:
            calls["count"] += 1
            if calls["count"] == 1:
                raise ValueError("private collector path")
            return 7

        reporter.register_source("tool_invocations", source)
        first_report = reporter.generate("t1")
        second_report = reporter.generate("t1")
        summary = reporter.summary()

        assert first_report.tool_invocations == 0
        assert second_report.tool_invocations == 7
        assert summary["source_error_count"] == 1
        assert summary["source_errors"] == {}
        assert "private collector path" not in str(summary)

    def test_summary(self):
        reporter = UsageReporter(clock=FIXED_CLOCK)
        reporter.register_source("a", lambda tid: 0)
        summary = reporter.summary()
        assert "a" in summary["sources"]
        assert summary["source_error_count"] == 0
        assert summary["source_errors"] == {}


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
