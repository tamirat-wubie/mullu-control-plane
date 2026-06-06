"""Phase 217 — Usage reporter and rate limit headers tests."""

import math

import pytest

from mcoi_runtime.core.rate_limit_middleware import rate_limit_headers
from mcoi_runtime.core.usage_reporter import UsageReporter


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

    @pytest.mark.parametrize(("source_name", "bad_value", "field_name"), [
        ("llm_calls", "secret-count", "llm_calls"),
        ("conversations", True, "conversations"),
        ("workflows", -1, "workflows"),
        ("tool_invocations", 1.5, "tool_invocations"),
        ("events_published", math.inf, "events_published"),
        ("total_cost", float("nan"), "total_cost"),
        ("budget_remaining", -0.01, "budget_remaining"),
    ])
    def test_invalid_source_values_fail_closed_bounded(
        self,
        source_name,
        bad_value,
        field_name,
    ):
        reporter = UsageReporter(clock=FIXED_CLOCK)
        reporter.register_source(source_name, lambda _tid: bad_value)

        report = reporter.generate("t1")
        summary = reporter.summary()

        assert getattr(report, field_name) == 0
        assert summary["source_error_count"] == 1
        assert summary["source_errors"] == {source_name: "usage source error (ValueError)"}
        assert str(bad_value) not in str(summary)
        assert "secret-count" not in str(summary)

    def test_valid_numeric_source_values_are_normalized(self):
        reporter = UsageReporter(clock=FIXED_CLOCK)
        reporter.register_source("llm_calls", lambda _tid: 42.0)
        reporter.register_source("total_cost", lambda _tid: 3)
        reporter.register_source("budget_remaining", lambda _tid: 0.25)

        report = reporter.generate("t1")
        summary = reporter.summary()

        assert report.llm_calls == 42
        assert isinstance(report.llm_calls, int)
        assert report.total_cost == 3.0
        assert report.budget_remaining == 0.25
        assert summary["source_error_count"] == 0
        assert summary["source_errors"] == {}

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
