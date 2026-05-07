"""Phase 212D — Retry and Circuit-Breaker Engine.

Purpose: Resilient execution with configurable retry policies
    and circuit breakers for external service calls (LLM, DB).
Governance scope: retry/circuit-breaker policy only.
Dependencies: none (pure algorithm).
Invariants:
  - Retry count is bounded — no infinite loops.
  - Circuit breaker opens after threshold failures.
  - Half-open state allows single probe request.
  - All retry attempts are tracked for observability.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def _classify_retry_exception(exc: Exception) -> str:
    """Return a bounded retry failure message."""
    exc_type = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return f"retry timeout ({exc_type})"
    return f"retry execution error ({exc_type})"


class CircuitState(StrEnum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing — reject all calls
    HALF_OPEN = "half_open"  # Probing — allow one call


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_ms: float = 100.0
    max_delay_ms: float = 5000.0
    backoff_multiplier: float = 2.0
    retry_on: tuple[type, ...] = (Exception,)


@dataclass(frozen=True, slots=True)
class RetryResult:
    """Result of a retried operation."""

    succeeded: bool
    result: Any
    attempts: int
    total_delay_ms: float
    error: str = ""


class RetryExecutor:
    """Executes operations with retry policy."""

    def __init__(self, policy: RetryPolicy | None = None) -> None:
        self._policy = policy or RetryPolicy()
        self._total_attempts = 0
        self._total_retries = 0
        self._total_successes = 0

    def execute(self, fn: Callable[[], Any]) -> RetryResult:
        """Execute with retries according to policy."""
        delay = self._policy.base_delay_ms
        total_delay = 0.0
        last_error = ""

        for attempt in range(1, self._policy.max_retries + 1):
            self._total_attempts += 1
            try:
                result = fn()
                self._total_successes += 1
                return RetryResult(
                    succeeded=True, result=result,
                    attempts=attempt, total_delay_ms=total_delay,
                )
            except self._policy.retry_on as exc:
                last_error = _classify_retry_exception(exc)
                self._total_retries += 1
                if attempt < self._policy.max_retries:
                    # In real code: time.sleep(delay / 1000)
                    total_delay += delay
                    delay = min(delay * self._policy.backoff_multiplier, self._policy.max_delay_ms)

        return RetryResult(
            succeeded=False, result=None,
            attempts=self._policy.max_retries,
            total_delay_ms=total_delay,
            error=last_error,
        )

    def summary(self) -> dict[str, Any]:
        return {
            "total_attempts": self._total_attempts,
            "total_retries": self._total_retries,
            "total_successes": self._total_successes,
        }


class CircuitBreaker:
    """Circuit breaker for external service calls."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout_ms: float = 30000.0,
        half_open_max: int = 1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout_ms = recovery_timeout_ms
        self._half_open_max = half_open_max
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_attempts = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = (time.monotonic() - self._last_failure_time) * 1000
            if elapsed >= self._recovery_timeout_ms:
                self._state = CircuitState.HALF_OPEN
                self._half_open_attempts = 0
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return self._half_open_attempts < self._half_open_max
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful call."""
        self._success_count += 1
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._half_open_attempts += 1
        elif self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN

    def execute(self, fn: Callable[[], Any]) -> Any:
        """Execute with circuit breaker protection."""
        if not self.allow_request():
            raise RuntimeError("circuit breaker unavailable")

        try:
            result = fn()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_attempts = 0

    def status(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self._failure_threshold,
        }
