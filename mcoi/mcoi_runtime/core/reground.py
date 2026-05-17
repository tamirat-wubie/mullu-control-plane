"""Purpose: OP_reground freshness checks for reused execution nodes.
Governance scope: stale-dependency prevention before execution reuse.
Dependencies: runtime invariant helpers and Python standard library datetime.
Invariants:
  - Freshness checks are explicit and deterministic against caller-provided time.
  - Stale or unbounded node ages block reuse before effectful execution.
  - No external sensing is performed implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from .invariants import RuntimeCoreInvariantError, ensure_iso_timestamp, ensure_non_empty_text


class RegroundStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RegroundNode:
    node_id: str
    observed_at: str
    max_age_seconds: int
    domain: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", ensure_non_empty_text("node_id", self.node_id))
        object.__setattr__(self, "observed_at", ensure_iso_timestamp("observed_at", self.observed_at))
        if not isinstance(self.max_age_seconds, int) or self.max_age_seconds < 0:
            raise RuntimeCoreInvariantError("max_age_seconds must be a non-negative integer")
        object.__setattr__(self, "domain", ensure_non_empty_text("domain", self.domain))


@dataclass(frozen=True, slots=True)
class RegroundDecision:
    status: RegroundStatus
    node_id: str
    age_seconds: int
    reasons: tuple[str, ...]


def op_reground(node: RegroundNode, *, now: str) -> RegroundDecision:
    """Check whether an old node is fresh enough for reuse."""
    ensure_iso_timestamp("now", now)
    observed = _parse_timestamp(node.observed_at)
    current = _parse_timestamp(now)
    age_seconds = int((current - observed).total_seconds())
    if age_seconds < 0:
        return RegroundDecision(
            status=RegroundStatus.UNKNOWN,
            node_id=node.node_id,
            age_seconds=age_seconds,
            reasons=("node_observed_in_future",),
        )
    if node.max_age_seconds == 0:
        return RegroundDecision(
            status=RegroundStatus.UNKNOWN,
            node_id=node.node_id,
            age_seconds=age_seconds,
            reasons=("freshness_window_unbounded",),
        )
    if age_seconds > node.max_age_seconds:
        return RegroundDecision(
            status=RegroundStatus.STALE,
            node_id=node.node_id,
            age_seconds=age_seconds,
            reasons=("node_exceeds_freshness_window",),
        )
    return RegroundDecision(
        status=RegroundStatus.FRESH,
        node_id=node.node_id,
        age_seconds=age_seconds,
        reasons=("node_within_freshness_window",),
    )


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
