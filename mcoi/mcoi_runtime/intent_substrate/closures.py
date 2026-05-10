"""IntentClosure — application-supplied adapter that performs the actual
state-machine transition when the resolver decides an intent has
fulfilled or failed.

Why an adapter:
    The resolver only computes verdicts. It does not know what
    "closing" an intent means in your domain — closing an obligation,
    fulfilling a service request, completing an orchestration step,
    advancing a recovery, etc., are all valid mappings. By taking a
    `IntentClosure` instead of binding to one engine, the substrate
    works against any state machine the application names.

Provided implementations:
    ObligationClosureAdapter
        Closes ObligationRuntimeEngine obligations to COMPLETED on
        success, CANCELLED on precondition failure.

    Roll your own for other state machines (request status, recovery
    status, orchestration status, etc.) — the protocol has just three
    methods.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from mcoi_runtime.contracts.obligation import (
    ObligationClosure,
    ObligationState,
)
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

from .primitives import IntentId


@runtime_checkable
class IntentClosure(Protocol):
    """Adapter the resolver uses to ask "is this intent still open?"
    and to perform the success / failure transition.
    """

    def is_open(self, intent_id: IntentId) -> bool:
        """Return True if the intent should still be evaluated.

        Intents not open are skipped and self-cleaned by the resolver.
        Lets external code paths (manual close, deadline expiry,
        reactions, ...) terminate intents the resolver doesn't know
        about, without leaking memory in the resolver's index.
        """
        ...

    def close_success(self, intent_id: IntentId, reason: str) -> Any:
        """Transition the intent to its success terminal state.

        Called once per intent, after the two-confirmation rule
        verified the success predicates held stably across the confirm
        window. Return value is opaque to the resolver — typically the
        closure record produced by the underlying state machine.
        """
        ...

    def close_precondition_failed(self, intent_id: IntentId, reason: str) -> Any:
        """Transition the intent to a failure terminal state.

        Called once when a precondition predicate evaluates false. The
        application chooses what "failure" maps to in its state machine
        (CANCELLED, FAILED, REJECTED, etc.).
        """
        ...


_TERMINAL_OBLIGATION_STATES = (
    ObligationState.COMPLETED,
    ObligationState.EXPIRED,
    ObligationState.CANCELLED,
)


class ObligationClosureAdapter:
    """IntentClosure backed by ObligationRuntimeEngine.

    Maps intent_id directly to obligation_id. Success closes the
    obligation to COMPLETED; precondition failure closes it to
    CANCELLED. closed_by is fixed as 'intent_substrate' so closures
    driven by this adapter are auditable as substrate-driven.
    """

    def __init__(self, obligations: ObligationRuntimeEngine) -> None:
        self._obligations = obligations

    def is_open(self, obligation_id: IntentId) -> bool:
        obl = self._obligations.get_obligation(obligation_id)
        if obl is None:
            return False
        return obl.state not in _TERMINAL_OBLIGATION_STATES

    def close_success(
        self, obligation_id: IntentId, reason: str
    ) -> ObligationClosure:
        return self._obligations.close(
            obligation_id,
            final_state=ObligationState.COMPLETED,
            reason=reason,
            closed_by="intent_substrate",
        )

    def close_precondition_failed(
        self, obligation_id: IntentId, reason: str
    ) -> ObligationClosure:
        return self._obligations.close(
            obligation_id,
            final_state=ObligationState.CANCELLED,
            reason=reason,
            closed_by="intent_substrate",
        )
