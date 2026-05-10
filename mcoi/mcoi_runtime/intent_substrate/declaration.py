"""declare_intent — convenience for the obligation-backed case.

Creates an obligation in PENDING state via ObligationRuntimeEngine and
registers its predicates with the IntentResolver in one call. Returns
the obligation record so callers can use its ID for further wiring.

Assumes the resolver was constructed with an `ObligationClosureAdapter`
backing the same `obligation_engine` — the resolver will then close
the obligation on success / failure. If the resolver uses a different
IntentClosure backend (e.g. a service-catalog request adapter), don't
use this helper; create the lifecycle record yourself and call
resolver.register_intent directly.

The substrate stores no parallel "intent" record — the obligation IS
the intent's durable identity, lifecycle, audit trail, owner,
deadline, and metadata. Predicates live in resolver memory only;
restart loses them. For durable predicates, persist them in obligation
metadata and reload on startup — out of scope here.
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
    """Create the obligation, register the predicates, return the obligation."""
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
