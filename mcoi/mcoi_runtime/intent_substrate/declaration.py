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

The obligation IS the intent's durable identity, lifecycle, audit
trail, owner, deadline, and metadata. As of the persistence layer,
predicates are also durably stored: declare_intent serializes them
into obligation.metadata under `persistence.METADATA_KEY`, and
`persistence.restore_intents_from_obligations` rebuilds the resolver's
in-memory registry on startup.
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

from .persistence import METADATA_KEY, serialize_predicate_set
from .primitives import IntentPredicate
from .resolver import IntentResolver

_RESERVED_METADATA_KEYS = frozenset(
    {"intent_substrate", "predicate_count", METADATA_KEY}
)


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
    """Create the obligation, register the predicates, return the obligation.

    Predicates are serialized into obligation metadata so they survive
    a process restart — see `persistence.restore_intents_from_obligations`.
    """
    pre_t = tuple(preconditions)
    succ_t = tuple(success)
    if extra_metadata:
        reserved_keys = _RESERVED_METADATA_KEYS.intersection(extra_metadata)
        if reserved_keys:
            raise ValueError(
                "extra_metadata cannot override reserved intent_substrate keys: "
                + ", ".join(sorted(reserved_keys))
            )
    metadata: dict[str, object] = {
        "intent_substrate": "true",
        "predicate_count": str(len(pre_t) + len(succ_t)),
        METADATA_KEY: serialize_predicate_set(pre_t, succ_t),
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
        preconditions=pre_t,
        success=succ_t,
    )
    return obligation
