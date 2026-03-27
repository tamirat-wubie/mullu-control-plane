"""Phase 230C — Governed Retry Policy Engine.

Purpose: Configurable retry policies with exponential backoff, jitter,
    budget limits, and per-operation tracking.
Dependencies: None (stdlib only).
Invariants:
  - Retry budget prevents infinite loops.
  - Backoff is exponential with optional jitter.
  - All retries are auditable.
  - Policies are per-operation configurable.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable, TypeVar

T = TypeVar("T")


@unique
class RetryOutcome(Enum):
    SUCCESS = "success"
    EXHAUSTED = "exhausted"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass(frozen=True)
class RetryPolicy:
    """A retry policy with backoff configuration."""
    max_retries: int = 3
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_budget_per_minute: int = 100


@dataclass
class RetryResult:
    """Result of a retry execution."""
    outcome: RetryOutcome
    attempts: int
    total_delay_seconds: float
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "attempts": self.attempts,
            "total_delay_seconds": round(self.total_delay_seconds, 4),
            "last_error": self.last_error,
        }


class RetryPolicyEngine:
    """Executes operations with governed retry policies."""

    def __init__(self, default_policy: RetryPolicy | None = None):
        self._default_policy = default_policy or RetryPolicy()
        self._policies: dict[str, RetryPolicy] = {}
        self._budget_tracker: dict[str, list[float]] = {}  # op -> timestamps
        self._total_retries = 0
        self._total_successes = 0
        self._total_exhausted = 0

    def set_policy(self, operation: str, policy: RetryPolicy) -> None:
        self._policies[operation] = policy

    def _get_delay(self, attempt: int, policy: RetryPolicy) -> float:
        delay = min(
            policy.base_delay_seconds * (policy.exponential_base ** attempt),
            policy.max_delay_seconds,
        )
        if policy.jitter:
            delay *= random.uniform(0.5, 1.5)
        return delay

    def _check_budget(self, operation: str, policy: RetryPolicy) -> bool:
        now = time.time()
        cutoff = now - 60.0
        timestamps = self._budget_tracker.get(operation, [])
        timestamps = [t for t in timestamps if t > cutoff]
        self._budget_tracker[operation] = timestamps
        return len(timestamps) < policy.retry_budget_per_minute

    def execute(self, operation: str,
                fn: Callable[[], T],
                policy: RetryPolicy | None = None) -> tuple[RetryResult, T | None]:
        """Execute fn with retry policy. Returns (result, value_or_none)."""
        pol = policy or self._policies.get(operation, self._default_policy)

        if not self._check_budget(operation, pol):
            return RetryResult(
                outcome=RetryOutcome.BUDGET_EXCEEDED,
                attempts=0, total_delay_seconds=0.0,
            ), None

        total_delay = 0.0
        last_error = ""

        for attempt in range(pol.max_retries + 1):
            try:
                result = fn()
                self._total_successes += 1
                return RetryResult(
                    outcome=RetryOutcome.SUCCESS,
                    attempts=attempt + 1,
                    total_delay_seconds=total_delay,
                ), result
            except Exception as e:
                last_error = str(e)
                self._total_retries += 1
                if operation not in self._budget_tracker:
                    self._budget_tracker[operation] = []
                self._budget_tracker[operation].append(time.time())

                if attempt < pol.max_retries:
                    delay = self._get_delay(attempt, pol)
                    time.sleep(delay)
                    total_delay += delay

        self._total_exhausted += 1
        return RetryResult(
            outcome=RetryOutcome.EXHAUSTED,
            attempts=pol.max_retries + 1,
            total_delay_seconds=total_delay,
            last_error=last_error,
        ), None

    def summary(self) -> dict[str, Any]:
        return {
            "total_retries": self._total_retries,
            "total_successes": self._total_successes,
            "total_exhausted": self._total_exhausted,
            "policies_registered": len(self._policies),
        }
