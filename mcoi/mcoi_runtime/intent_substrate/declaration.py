"""declare_intent — single entry point for creating an intent.

Creates an obligation in PENDING state via ObligationRuntimeEngine and
registers its predicates with the IntentResolver in one call. Returns
the obligation record so callers can use its ID for further wiring.

The substrate stores no parallel "intent" record — the obligation IS
the intent's durable identity, lifecycle, audit trail, owner,
deadline, and metadata. Predicates live in resolver memory only; if
the resolver is restarted, intents must be re-registered. (For
durable predicates, persist them in obligation metadata and reload on
startup — out of scope for the first integrated cut.)
"""

from __future__ import annotations

from typing import Sequence

from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationRecord,
    ObligationTrigger,
)
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

from .primitives import IntentPredicate
from .resolver import IntentResolver


def declare_intent(
    *,
    resolver: IntentResolver,
    obligation_engine: ObligationRuntimeEngine,
    owner: ObligationOwner,
    deadline: ObligationDeadline,
    description: str,
    correlation_id: str,
    preconditions: Sequence[IntentPredicate] = (),
    success: Sequence[IntentPredicate] = (),
    trigger: ObligationTrigger = ObligationTrigger.CUSTOM,
    trigger_ref_id: str | None = None,
    extra_metadata: dict[str, str] | None = None,
) -> ObligationRecord:
    """Declare an intent.

    Creates the obligation, registers the predicates, returns the
    obligation. The obligation_id is the intent's identity — pass it
    to resolver.evaluate, resolver.deregister_intent, and the
    obligation engine for lifecycle queries.
    """
    metadata: dict[str, object] = {
        "intent_substrate": "true",
        "predicate_count": str(len(preconditions) + len(success)),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    obligation = obligation_engine.create_obligation(
        trigger=trigger,
        trigger_ref_id=trigger_ref_id or correlation_id,
        owner=owner,
        deadline=deadline,
        description=description,
        correlation_id=correlation_id,
        metadata=metadata,
    )
    resolver.register_intent(
        obligation.obligation_id,
        preconditions=preconditions,
        success=success,
    )
    return obligation
