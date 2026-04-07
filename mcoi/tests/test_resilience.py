"""Production Resilience Tests — Retry, circuit breaker, fallback, DLQ."""

import pytest
from mcoi_runtime.core.resilience import (
    CircuitBreaker, CircuitState,
    DeadLetterEntry, DeadLetterQueue,
    FallbackResult, ProviderFallbackChain,
    RetryConfig, RetryResult, retry_with_backoff,
)


# ═══ Retry with Backoff ═══


class TestRetryWithBackoff:
    def test_success_first_try(self):
        result = retry_with_backoff(lambda: 42)
        assert result.success
        assert result.result == 42
        assert result.attempts == 1

    def test_retry_on_failure_then_succeed(self):
        call_count = [0]
        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("transient")
            return "ok"
        result = retry_with_backoff(flaky, config=RetryConfig(max_retries=3, base_delay_seconds=0.01))
        assert result.success
        assert result.attempts == 3

    def test_exhaust_retries(self):
        result = retry_with_backoff(
            lambda: (_ for _ in ()).throw(RuntimeError("always fails")),
            config=RetryConfig(max_retries=2, base_delay_seconds=0.01),
        )
        assert not result.success
        assert result.attempts == 3
        assert result.last_error == "RuntimeError"

    def test_non_retryable_exception(self):
        result = retry_with_backoff(
            lambda: (_ for _ in ()).throw(ValueError("not retryable")),
            config=RetryConfig(max_retries=3, base_delay_seconds=0.01),
            retryable_exceptions=(RuntimeError,),
        )
        assert not result.success
        assert result.attempts == 1

    def test_no_jitter(self):
        result = retry_with_backoff(
            lambda: 1,
            config=RetryConfig(jitter=False),
        )
        assert result.success


# ═══ Circuit Breaker ═══


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request()

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, name="test")
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.allow_request()

    def test_recovers_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.01, name="test")
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        import time
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request()

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.01, name="test")
        cb.record_failure()
        import time
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1, name="test")
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_summary(self):
        cb = CircuitBreaker(name="provider-a")
        cb.record_success()
        summary = cb.summary()
        assert summary["name"] == "provider-a"
        assert summary["state"] == "closed"


# ═══ Provider Fallback Chain ═══


class TestProviderFallbackChain:
    def test_first_provider_succeeds(self):
        chain = ProviderFallbackChain()
        chain.add_provider("a", lambda: "from-a")
        chain.add_provider("b", lambda: "from-b")
        result = chain.execute()
        assert result.success
        assert result.provider_used == "a"
        assert result.result == "from-a"

    def test_fallback_to_second(self):
        chain = ProviderFallbackChain()
        chain.add_provider("a", lambda: (_ for _ in ()).throw(RuntimeError("down")))
        chain.add_provider("b", lambda: "from-b")
        result = chain.execute()
        assert result.success
        assert result.provider_used == "b"
        assert result.providers_tried == 2

    def test_all_fail(self):
        chain = ProviderFallbackChain()
        chain.add_provider("a", lambda: (_ for _ in ()).throw(RuntimeError("down")))
        chain.add_provider("b", lambda: (_ for _ in ()).throw(RuntimeError("down")))
        result = chain.execute()
        assert not result.success
        assert result.providers_tried == 2

    def test_circuit_breaker_skips_open_provider(self):
        chain = ProviderFallbackChain()
        chain.add_provider("a", lambda: (_ for _ in ()).throw(RuntimeError("down")), failure_threshold=1)
        chain.add_provider("b", lambda: "from-b")
        # Trip circuit on A
        chain.execute()  # A fails, falls back to B
        # Now A's circuit is open — should skip directly to B
        result = chain.execute()
        assert result.success
        assert result.provider_used == "b"
        assert result.providers_tried == 1  # Skipped A

    def test_no_providers(self):
        chain = ProviderFallbackChain()
        result = chain.execute()
        assert not result.success
        assert "no providers" in result.error

    def test_health(self):
        chain = ProviderFallbackChain()
        chain.add_provider("a", lambda: None)
        chain.add_provider("b", lambda: None)
        health = chain.health()
        assert len(health) == 2
        assert health[0]["name"] == "a"


# ═══ Dead Letter Queue ═══


class TestDeadLetterQueue:
    def test_push_and_pop(self):
        dlq = DeadLetterQueue()
        dlq.push(DeadLetterEntry(
            entry_id="e1", payload={"msg": "hello"}, error="timeout",
            attempts=3, created_at="2026-01-01",
        ))
        assert dlq.size == 1
        entry = dlq.pop()
        assert entry.entry_id == "e1"
        assert dlq.size == 0

    def test_pop_empty_returns_none(self):
        dlq = DeadLetterQueue()
        assert dlq.pop() is None

    def test_peek(self):
        dlq = DeadLetterQueue()
        dlq.push(DeadLetterEntry(entry_id="e1", payload={}, error="err", attempts=1, created_at="2026-01-01"))
        dlq.push(DeadLetterEntry(entry_id="e2", payload={}, error="err", attempts=1, created_at="2026-01-02"))
        peeked = dlq.peek(1)
        assert len(peeked) == 1
        assert dlq.size == 2  # Not removed

    def test_bounded(self):
        dlq = DeadLetterQueue()
        for i in range(dlq.MAX_ENTRIES + 100):
            dlq.push(DeadLetterEntry(entry_id=f"e{i}", payload={}, error="err", attempts=1, created_at=f"t{i}"))
        assert dlq.size <= dlq.MAX_ENTRIES

    def test_clear(self):
        dlq = DeadLetterQueue()
        dlq.push(DeadLetterEntry(entry_id="e1", payload={}, error="err", attempts=1, created_at="t"))
        count = dlq.clear()
        assert count == 1
        assert dlq.size == 0

    def test_summary(self):
        dlq = DeadLetterQueue()
        summary = dlq.summary()
        assert summary["size"] == 0
        assert summary["oldest"] is None
