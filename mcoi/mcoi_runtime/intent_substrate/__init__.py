"""Intent substrate — predicate-driven closure with safe two-confirmation
semantics under non-linearizable concurrent reads.

Layers on top of EventSpineEngine for events. The lifecycle backend
(what "closing" an intent means in your domain) is supplied by the
caller via an IntentClosure adapter — the resolver itself is
state-machine-agnostic.

Public surface:

    declare_intent(...)           -> ObligationRecord
        Convenience for the obligation-backed case (creates an
        obligation, registers predicates, persists predicates in
        obligation metadata for restart resilience).

    restore_intents_from_obligations(resolver, obligation_engine)
        Re-register substrate-driven intents from open obligations.
        Call once at startup, after constructing the resolver, before
        accepting events.

    IntentResolver(...)           -> register, evaluate, on_event, tick
        The verdict / two-confirm engine.

    IntentClosure (Protocol)
        Application-supplied adapter the resolver calls to perform the
        actual transition.

    ObligationClosureAdapter      -> closes obligations COMPLETED/CANCELLED
        Built-in IntentClosure for the obligation case. Roll your own
        for service requests, recovery executions, orchestration
        steps, etc.

    BackgroundTicker(...)         -> drives tick() while idle
    EntityAttributeEq             -> predicate kinds
    EntityAttributeThreshold
    EntityExists
    causal_priority / rank        -> derived priority view over obligations

See `resolver.py` for the two-confirmation rule, `primitives.py` for
the consistency model, `closures.py` for the IntentClosure protocol,
`persistence.py` for the restart-resilience layer.
"""

from .background import BackgroundTicker
from .causal import causal_priority, deadline_urgency, rank
from .closures import IntentClosure, ObligationClosureAdapter
from .declaration import declare_intent
from .persistence import (
    IntentRestoreReport,
    IntentRestoreSkip,
    METADATA_KEY,
    deserialize_predicate,
    deserialize_predicate_set,
    restore_intents_from_obligations,
    restore_intents_from_obligations_report,
    serialize_predicate,
    serialize_predicate_set,
)
from .predicates import (
    EntityAttributeEq,
    EntityAttributeThreshold,
    EntityExists,
)
from .primitives import (
    EntityId,
    EntityVector,
    IntentId,
    IntentPredicate,
    StateView,
    gather_vector,
    hash_state,
)
from .resolver import IntentResolver

__all__ = [
    # primitives
    "EntityId",
    "EntityVector",
    "IntentId",
    "IntentPredicate",
    "StateView",
    "gather_vector",
    "hash_state",
    # predicates
    "EntityAttributeEq",
    "EntityAttributeThreshold",
    "EntityExists",
    # closures
    "IntentClosure",
    "ObligationClosureAdapter",
    # core
    "IntentResolver",
    "BackgroundTicker",
    "declare_intent",
    # persistence
    "IntentRestoreReport",
    "IntentRestoreSkip",
    "METADATA_KEY",
    "serialize_predicate",
    "deserialize_predicate",
    "serialize_predicate_set",
    "deserialize_predicate_set",
    "restore_intents_from_obligations",
    "restore_intents_from_obligations_report",
    # causal
    "causal_priority",
    "deadline_urgency",
    "rank",
]
