"""Governance Decision Log — Queryable record of every guard chain evaluation.

Purpose: Captures every governance decision (allowed/denied/error) with
    full guard chain results for compliance dashboards, audit review,
    and incident investigation.  Unlike the generic audit trail, this
    is specifically designed for governance decision queries.
Governance scope: decision recording and query only.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Every decision is immutable once recorded.
  - Decisions are bounded (configurable max, FIFO eviction).
  - Query supports multi-dimensional filtering (tenant, outcome, guard, time).
  - Thread-safe — concurrent guard evaluations + readers are safe.
  - Hash-chained for tamper evidence.
"""

from __future__ import annotations

import hashlib
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class GuardDecisionDetail:
    """Result of a single guard within a chain evaluation."""

    guard_name: str
    allowed: bool
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GovernanceDecision:
    """Immutable record of a governance decision."""

    decision_id: str
    sequence: int
    tenant_id: str
    identity_id: str
    endpoint: str
    method: str
    allowed: bool
    blocking_guard: str  # Empty if allowed
    blocking_reason: str  # Empty if allowed
    guards_evaluated: tuple[GuardDecisionDetail, ...]
    evaluated_at: str
    decision_hash: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "sequence": self.sequence,
            "tenant_id": self.tenant_id,
            "identity_id": self.identity_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "allowed": self.allowed,
            "blocking_guard": self.blocking_guard,
            "blocking_reason": self.blocking_reason,
            "guards_evaluated": [
                {
                    "guard_name": g.guard_name,
                    "allowed": g.allowed,
                    "reason": g.reason,
                    "detail": g.detail,
                }
                for g in self.guards_evaluated
            ],
            "evaluated_at": self.evaluated_at,
            "decision_hash": self.decision_hash,
        }


class GovernanceDecisionLog:
    """Bounded, queryable log of governance decisions.

    Usage:
        log = GovernanceDecisionLog(clock=lambda: "2026-04-07T12:00:00Z")

        # Record after guard chain evaluation
        log.record(
            tenant_id="t1",
            identity_id="user1",
            endpoint="/api/v1/llm",
            method="POST",
            allowed=True,
            guards=[
                GuardDecisionDetail("auth", True),
                GuardDecisionDetail("rbac", True),
                GuardDecisionDetail("rate_limit", True),
            ],
        )

        # Query
        denials = log.query(allowed=False, tenant_id="t1")
        recent = log.query(limit=10)
    """

    MAX_DECISIONS = 50_000

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        max_decisions: int = MAX_DECISIONS,
    ) -> None:
        self._clock = clock
        self._max_decisions = max_decisions
        self._decisions: deque[GovernanceDecision] = deque(maxlen=max_decisions)
        self._sequence = 0
        self._lock = threading.Lock()
        self._allowed_count = 0
        self._denied_count = 0
        self._previous_hash = "genesis"

    def record(
        self,
        *,
        tenant_id: str,
        identity_id: str = "",
        endpoint: str = "",
        method: str = "",
        allowed: bool,
        blocking_guard: str = "",
        blocking_reason: str = "",
        guards: list[GuardDecisionDetail] | None = None,
        detail: dict[str, Any] | None = None,
    ) -> GovernanceDecision:
        """Record a governance decision."""
        with self._lock:
            self._sequence += 1
            seq = self._sequence

            decision_id = f"govdec-{seq}"

            # Hash chain
            hash_input = f"{self._previous_hash}:{decision_id}:{tenant_id}:{allowed}:{endpoint}"
            decision_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

            decision = GovernanceDecision(
                decision_id=decision_id,
                sequence=seq,
                tenant_id=tenant_id,
                identity_id=identity_id,
                endpoint=endpoint,
                method=method,
                allowed=allowed,
                blocking_guard=blocking_guard,
                blocking_reason=blocking_reason,
                guards_evaluated=tuple(guards or []),
                evaluated_at=self._clock(),
                decision_hash=decision_hash,
                detail=detail or {},
            )

            self._decisions.append(decision)
            self._previous_hash = decision_hash

            if allowed:
                self._allowed_count += 1
            else:
                self._denied_count += 1

            return decision

    def query(
        self,
        *,
        tenant_id: str = "",
        identity_id: str = "",
        allowed: bool | None = None,
        blocking_guard: str = "",
        endpoint: str = "",
        limit: int = 50,
    ) -> list[GovernanceDecision]:
        """Query governance decisions with multi-dimensional filtering.

        All filters are AND-combined.  Empty string means "any".
        Returns most recent first (reverse chronological).
        """
        with self._lock:
            results: list[GovernanceDecision] = []
            for decision in reversed(self._decisions):
                if tenant_id and decision.tenant_id != tenant_id:
                    continue
                if identity_id and decision.identity_id != identity_id:
                    continue
                if allowed is not None and decision.allowed != allowed:
                    continue
                if blocking_guard and decision.blocking_guard != blocking_guard:
                    continue
                if endpoint and decision.endpoint != endpoint:
                    continue
                results.append(decision)
                if len(results) >= limit:
                    break
            return results

    def get(self, decision_id: str) -> GovernanceDecision | None:
        """Get a specific decision by ID."""
        with self._lock:
            for decision in reversed(self._decisions):
                if decision.decision_id == decision_id:
                    return decision
        return None

    def denial_summary(self, *, tenant_id: str = "", limit: int = 100) -> dict[str, Any]:
        """Summary of recent denials grouped by blocking guard."""
        denials = self.query(allowed=False, tenant_id=tenant_id, limit=limit)
        by_guard: dict[str, int] = {}
        by_endpoint: dict[str, int] = {}
        for d in denials:
            by_guard[d.blocking_guard] = by_guard.get(d.blocking_guard, 0) + 1
            if d.endpoint:
                by_endpoint[d.endpoint] = by_endpoint.get(d.endpoint, 0) + 1
        return {
            "total_denials": len(denials),
            "by_guard": by_guard,
            "by_endpoint": by_endpoint,
        }

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def allowed_count(self) -> int:
        return self._allowed_count

    @property
    def denied_count(self) -> int:
        return self._denied_count

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_decisions": self._allowed_count + self._denied_count,
                "allowed": self._allowed_count,
                "denied": self._denied_count,
                "active_entries": len(self._decisions),
                "capacity": self._max_decisions,
                "denial_rate": round(
                    self._denied_count / (self._allowed_count + self._denied_count), 4
                ) if (self._allowed_count + self._denied_count) > 0 else 0.0,
            }
