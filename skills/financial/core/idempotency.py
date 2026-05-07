"""Idempotency Layer — Replay-safe financial execution.

Invariants:
  - Same request must not create duplicate transactions.
  - Idempotency key derived from: tenant + action + destination + amount + currency.
  - Completed keys return cached result.
  - In-flight keys return CONFLICT.
  - Keys expire after configurable TTL.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class IdempotencyStatus(StrEnum):
    """Status of an idempotency check."""

    NEW = "new"  # First time seeing this key — proceed
    COMPLETED = "completed"  # Already executed successfully — return cached result
    IN_FLIGHT = "in_flight"  # Currently executing — return conflict
    EXPIRED = "expired"  # Key expired — treat as new


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    """Record of an idempotent operation."""

    key: str
    status: IdempotencyStatus
    result: dict[str, Any] | None = None
    created_at: str = ""
    completed_at: str = ""


def compute_key(
    tenant_id: str,
    action: str,
    destination: str,
    amount: str,
    currency: str,
    reference: str = "",
) -> str:
    """Compute deterministic idempotency key from request parameters."""
    content = f"{tenant_id}:{action}:{destination}:{amount}:{currency}:{reference}"
    return f"idem-{hashlib.sha256(content.encode()).hexdigest()[:24]}"


class IdempotencyStore:
    """In-memory idempotency store.

    Production should use Redis or PostgreSQL with TTL.
    """

    MAX_RECORDS = 100_000

    def __init__(self) -> None:
        self._records: dict[str, IdempotencyRecord] = {}

    def check(self, key: str) -> IdempotencyRecord | None:
        """Check if a key has been seen before."""
        return self._records.get(key)

    def mark_in_flight(self, key: str, created_at: str = "") -> IdempotencyRecord:
        """Mark a key as in-flight (execution started).

        Raises ValueError if key is already IN_FLIGHT or COMPLETED.
        """
        existing = self._records.get(key)
        if existing is not None:
            if existing.status == IdempotencyStatus.IN_FLIGHT:
                raise ValueError(f"idempotency key {key} already in-flight")
            if existing.status == IdempotencyStatus.COMPLETED:
                raise ValueError(f"idempotency key {key} already completed")

        if len(self._records) >= self.MAX_RECORDS:
            oldest_key = next(iter(self._records))
            del self._records[oldest_key]

        record = IdempotencyRecord(
            key=key,
            status=IdempotencyStatus.IN_FLIGHT,
            created_at=created_at,
        )
        self._records[key] = record
        return record

    def mark_completed(self, key: str, result: dict[str, Any], completed_at: str = "") -> IdempotencyRecord:
        """Mark a key as completed with cached result."""
        existing = self._records.get(key)
        record = IdempotencyRecord(
            key=key,
            status=IdempotencyStatus.COMPLETED,
            result=result,
            created_at=existing.created_at if existing else completed_at,
            completed_at=completed_at,
        )
        self._records[key] = record
        return record

    def mark_failed(self, key: str) -> None:
        """Remove a key on failure (allow retry)."""
        self._records.pop(key, None)

    @property
    def record_count(self) -> int:
        return len(self._records)
