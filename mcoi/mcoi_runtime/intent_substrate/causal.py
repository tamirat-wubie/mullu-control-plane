"""Causal priority — derived from obligation lifecycle + deadline.

Operates directly on ObligationRecord (no parallel intent record).
Priority is NEVER a stored field; it's a computed view.

Formula:
    priority = (1 + #open_descendants) * urgency(deadline) * status_multiplier

Descendant linkage: this version uses correlation_id grouping rather
than a parent/child obligation graph (the obligation contract has no
parent field). Two obligations are "linked" if they share a
correlation_id; an obligation's "descendants" are other open
obligations sharing its correlation_id, excluding itself.

For richer dependency graphs, layer correlation hierarchies on top
(e.g., "child correlation X is parented to root correlation Y" in
metadata).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from mcoi_runtime.contracts.obligation import ObligationRecord, ObligationState
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_STATUS_MULTIPLIER: dict[ObligationState, float] = {
    ObligationState.PENDING: 1.0,
    ObligationState.ACTIVE: 1.0,
    ObligationState.ESCALATED: 5.0,
    ObligationState.TRANSFERRED: 1.0,
    ObligationState.COMPLETED: 0.0,
    ObligationState.EXPIRED: 0.0,
    ObligationState.CANCELLED: 0.0,
}


def deadline_urgency(
    deadline_iso: str | None, *, now: datetime | None = None
) -> float:
    """1.0 baseline, exponential ramp as deadline nears, capped at 10.0.

    24h out -> ~1.0,  1h out -> ~3.4,  1min out -> ~9.9,  past -> 10.0.
    """
    if deadline_iso is None or not deadline_iso:
        return 1.0
    try:
        deadline = datetime.fromisoformat(deadline_iso)
    except ValueError:
        return 1.0
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    now = now or _utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    seconds_left = (deadline - now).total_seconds()
    if seconds_left <= 0:
        return 10.0
    return min(10.0, 1.0 + 9.0 * math.exp(-seconds_left / 3600.0))


def causal_priority(
    obligation: ObligationRecord,
    obligations: ObligationRuntimeEngine,
    *,
    now: datetime | None = None,
) -> float:
    multiplier = _STATUS_MULTIPLIER.get(obligation.state, 1.0)
    urgency = deadline_urgency(obligation.deadline.due_at, now=now)
    sibling_count = sum(
        1
        for other in obligations.list_obligations()
        if other.obligation_id != obligation.obligation_id
        and other.correlation_id == obligation.correlation_id
        and other.state in _OPEN_STATES
    )
    base = 1 + sibling_count
    return base * urgency * multiplier


def rank(
    obligations_to_rank: list[ObligationRecord],
    obligations: ObligationRuntimeEngine,
    *,
    now: datetime | None = None,
) -> list[tuple[str, float]]:
    scored = [
        (o.obligation_id, causal_priority(o, obligations, now=now))
        for o in obligations_to_rank
    ]
    return sorted(scored, key=lambda t: t[1], reverse=True)


_OPEN_STATES = (
    ObligationState.PENDING,
    ObligationState.ACTIVE,
    ObligationState.ESCALATED,
    ObligationState.TRANSFERRED,
)
