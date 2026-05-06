"""Purpose: deterministic state transitions for finance approval packets.
Governance scope: packet lifecycle movement with cause, actor, timestamp,
evidence references, and violation reasons.
Dependencies: finance approval packet contracts and runtime invariant helpers.
Invariants: invalid transitions fail closed; state movement always records a
cause and preserves prior immutable case data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from mcoi_runtime.contracts.finance_approval_packet import FinancePacketState, InvoiceCase
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_iso_timestamp, ensure_non_empty_text


_ALLOWED_TRANSITIONS: dict[FinancePacketState, frozenset[FinancePacketState]] = {
    FinancePacketState.RECEIVED: frozenset({FinancePacketState.EXTRACTED, FinancePacketState.REQUIRES_REVIEW}),
    FinancePacketState.EXTRACTED: frozenset({FinancePacketState.EVIDENCE_CHECKED, FinancePacketState.REQUIRES_REVIEW}),
    FinancePacketState.EVIDENCE_CHECKED: frozenset({FinancePacketState.BUDGET_CHECKED, FinancePacketState.REQUIRES_REVIEW}),
    FinancePacketState.BUDGET_CHECKED: frozenset(
        {
            FinancePacketState.APPROVAL_REQUIRED,
            FinancePacketState.APPROVED,
            FinancePacketState.REQUIRES_REVIEW,
            FinancePacketState.CLOSED_DUPLICATE,
        }
    ),
    FinancePacketState.APPROVAL_REQUIRED: frozenset(
        {
            FinancePacketState.APPROVED,
            FinancePacketState.CLOSED_REJECTED,
            FinancePacketState.REQUIRES_REVIEW,
        }
    ),
    FinancePacketState.APPROVED: frozenset({FinancePacketState.EFFECT_DISPATCHED, FinancePacketState.CLOSED_PREPARED}),
    FinancePacketState.EFFECT_DISPATCHED: frozenset(
        {FinancePacketState.RECONCILED, FinancePacketState.FAILED_WITH_RECOVERY}
    ),
    FinancePacketState.RECONCILED: frozenset({FinancePacketState.CLOSED_SENT, FinancePacketState.CLOSED_PREPARED}),
}
_TERMINAL_STATES = frozenset(
    {
        FinancePacketState.CLOSED_PREPARED,
        FinancePacketState.CLOSED_SENT,
        FinancePacketState.CLOSED_REJECTED,
        FinancePacketState.CLOSED_DUPLICATE,
        FinancePacketState.CLOSED_ACCEPTED_RISK,
        FinancePacketState.REQUIRES_REVIEW,
        FinancePacketState.FAILED_WITH_RECOVERY,
    }
)


@dataclass(frozen=True, slots=True)
class FinancePacketTransition:
    """Causal request to move a packet between lifecycle states."""

    next_state: FinancePacketState
    cause: str
    actor_id: str
    occurred_at: str
    evidence_refs: tuple[str, ...] = ()
    violation_reasons: tuple[str, ...] = ()
    policy_decision_ref: str | None = None
    approval_ref: str | None = None
    effect_ref: str | None = None
    closure_certificate_id: str | None = None


def transition_invoice_case(invoice_case: InvoiceCase, transition: FinancePacketTransition) -> InvoiceCase:
    """Return a new case snapshot after a governed state transition."""
    if not isinstance(invoice_case, InvoiceCase):
        raise RuntimeCoreInvariantError("invoice_case must be an InvoiceCase")
    if not isinstance(transition, FinancePacketTransition):
        raise RuntimeCoreInvariantError("transition must be a FinancePacketTransition")
    _validate_transition_shape(transition)
    if invoice_case.state in _TERMINAL_STATES:
        raise RuntimeCoreInvariantError("terminal packet state cannot transition")
    allowed_next = _ALLOWED_TRANSITIONS.get(invoice_case.state, frozenset())
    if transition.next_state not in allowed_next:
        raise RuntimeCoreInvariantError("invalid finance packet state transition")

    metadata = dict(invoice_case.metadata)
    metadata["last_transition"] = {
        "from_state": invoice_case.state.value,
        "to_state": transition.next_state.value,
        "cause": transition.cause,
        "actor_id": transition.actor_id,
        "occurred_at": transition.occurred_at,
        "evidence_refs": list(transition.evidence_refs),
        "violation_reasons": list(transition.violation_reasons),
    }
    policy_decision_refs = _append_ref(invoice_case.policy_decision_refs, transition.policy_decision_ref)
    approval_refs = _append_ref(invoice_case.approval_refs, transition.approval_ref)
    effect_refs = _append_ref(invoice_case.effect_refs, transition.effect_ref)
    closure_certificate_id = transition.closure_certificate_id or invoice_case.closure_certificate_id

    return replace(
        invoice_case,
        state=transition.next_state,
        updated_at=transition.occurred_at,
        policy_decision_refs=policy_decision_refs,
        approval_refs=approval_refs,
        effect_refs=effect_refs,
        closure_certificate_id=closure_certificate_id,
        metadata=metadata,
    )


def _validate_transition_shape(transition: FinancePacketTransition) -> None:
    if not isinstance(transition.next_state, FinancePacketState):
        raise RuntimeCoreInvariantError("next_state must be a FinancePacketState")
    ensure_non_empty_text("cause", transition.cause)
    ensure_non_empty_text("actor_id", transition.actor_id)
    ensure_iso_timestamp("occurred_at", transition.occurred_at)
    for evidence_ref in transition.evidence_refs:
        ensure_non_empty_text("evidence_ref", evidence_ref)
    for reason in transition.violation_reasons:
        ensure_non_empty_text("violation_reason", reason)
    for optional_ref in (
        transition.policy_decision_ref,
        transition.approval_ref,
        transition.effect_ref,
        transition.closure_certificate_id,
    ):
        if optional_ref is not None:
            ensure_non_empty_text("optional_ref", optional_ref)


def _append_ref(existing: tuple[str, ...], candidate: str | None) -> tuple[str, ...]:
    if candidate is None or candidate in existing:
        return existing
    return (*existing, candidate)
