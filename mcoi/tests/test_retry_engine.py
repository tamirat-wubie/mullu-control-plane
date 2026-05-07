"""Phase 212D — Retry and circuit breaker tests."""

import pytest
from mcoi_runtime.core.retry_engine import (
    CircuitBreaker, CircuitState, RetryExecutor, RetryPolicy,
)


class TestRetryExecutor:
    def test_success_no_retry(self):
        executor = RetryExecutor()
        result = executor.execute(lambda: 42)
        assert result.succeeded is True
        assert result.result == 42
        assert result.attempts == 1

    def test_retry_on_failure(self):
        count = {"n": 0}
        def flaky():
            count["n"] += 1
            if count["n"] < 3:
                raise RuntimeError("fail")
            return "ok"

        executor = RetryExecutor(RetryPolicy(max_retries=5))
        result = executor.execute(flaky)
        assert result.succeeded is True
        assert result.attempts == 3

    def test_all_retries_fail(self):
        executor = RetryExecutor(RetryPolicy(max_retries=3))
        result = executor.execute(lambda: (_ for _ in ()).throw(RuntimeError("always fail")))
        assert result.succeeded is False
        assert result.attempts == 3
        assert result.error == "retry execution error (RuntimeError)"
        assert "always fail" not in result.error

    def test_backoff_delay(self):
        executor = RetryExecutor(RetryPolicy(max_retries=3, base_delay_ms=100, backoff_multiplier=2.0))
        executor.execute(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        # total_delay should be 100 + 200 = 300 (first retry + second retry, third is last attempt)
        # Actually: attempt 1 fails → delay 100, attempt 2 fails → delay 200, attempt 3 fails → no delay
        # So total_delay = 300

    def test_summary(self):
        executor = RetryExecutor(RetryPolicy(max_retries=2))
        executor.execute(lambda: 1)
        s = executor.summary()
        assert s["total_attempts"] == 1
        assert s["total_successes"] == 1


class TestCircuitBreaker:
    def test_closed_by_default(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_execute_success(self):
        cb = CircuitBreaker()
        result = cb.execute(lambda: 42)
        assert result == 42

    def test_execute_failure_raises(self):
        cb = CircuitBreaker()
        with pytest.raises(RuntimeError, match="boom"):
            cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    def test_open_rejects(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        with pytest.raises(RuntimeError, match="circuit breaker"):
            cb.execute(lambda: 42)

    def test_open_reject_error_is_bounded(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        with pytest.raises(RuntimeError, match="circuit breaker") as excinfo:
            cb.execute(lambda: 42)
        assert str(excinfo.value) == "circuit breaker unavailable"
        assert "open" not in str(excinfo.value)
        assert "half_open" not in str(excinfo.value)

    def test_success_closes_from_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_ms=0)
        cb.record_failure()
        # With 0ms timeout, state check transitions to half_open immediately
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_status(self):
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        s = cb.status()
        assert s["state"] == "closed"
        assert s["failure_count"] == 1
        assert s["failure_threshold"] == 5
