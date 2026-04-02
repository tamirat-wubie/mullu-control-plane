"""Transaction State Machine — Lifecycle for every financial action.

Invariants:
  - No skipped states.
  - No backwards transitions except settlement → refund flow.
  - Terminal states are immutable.
  - Every transition is auditable.
  - Every transition is idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TxState(StrEnum):
    """Transaction lifecycle states."""

    CREATED = "created"
    PENDING_APPROVAL = "pending_approval"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    SETTLED = "settled"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"


# Terminal states — no further transitions allowed
_TERMINAL = frozenset({TxState.REFUNDED, TxState.FAILED, TxState.REJECTED, TxState.EXPIRED})

# Valid transitions: current → allowed next states
_TRANSITIONS: dict[TxState, frozenset[TxState]] = {
    TxState.CREATED: frozenset({TxState.PENDING_APPROVAL, TxState.AUTHORIZED, TxState.REJECTED, TxState.EXPIRED}),
    TxState.PENDING_APPROVAL: frozenset({TxState.AUTHORIZED, TxState.REJECTED, TxState.EXPIRED}),
    TxState.AUTHORIZED: frozenset({TxState.CAPTURED, TxState.FAILED, TxState.EXPIRED}),
    TxState.CAPTURED: frozenset({TxState.SETTLED, TxState.FAILED}),
    TxState.SETTLED: frozenset({TxState.REFUND_PENDING}),
    TxState.REFUND_PENDING: frozenset({TxState.REFUNDED, TxState.FAILED}),
    TxState.REFUNDED: frozenset(),
    TxState.FAILED: frozenset(),
    TxState.REJECTED: frozenset(),
    TxState.EXPIRED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class TxTransition:
    """Record of a state transition."""

    from_state: TxState
    to_state: TxState
    reason: str = ""
    actor_id: str = ""
    transitioned_at: str = ""


def is_terminal(state: TxState) -> bool:
    """Check if a state is terminal (no further transitions)."""
    return state in _TERMINAL


def validate_transition(from_state: TxState, to_state: TxState) -> bool:
    """Check if a transition is legal."""
    allowed = _TRANSITIONS.get(from_state, frozenset())
    return to_state in allowed


def transition(
    from_state: TxState,
    to_state: TxState,
    *,
    reason: str = "",
    actor_id: str = "",
    timestamp: str = "",
) -> TxTransition:
    """Execute a state transition. Raises ValueError if illegal."""
    if is_terminal(from_state):
        raise ValueError(f"cannot transition from terminal state {from_state.value}")
    if not validate_transition(from_state, to_state):
        raise ValueError(
            f"illegal transition: {from_state.value} → {to_state.value}"
        )
    return TxTransition(
        from_state=from_state,
        to_state=to_state,
        reason=reason,
        actor_id=actor_id,
        transitioned_at=timestamp,
    )


def legal_next_states(state: TxState) -> tuple[TxState, ...]:
    """Return all legal next states from current state."""
    return tuple(sorted(_TRANSITIONS.get(state, frozenset())))
