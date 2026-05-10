"""Intent substrate — predicate-driven closure with safe two-confirmation
semantics under non-linearizable concurrent reads.

Layers on top of EventSpineEngine for events. The lifecycle backend
(what "closing" an intent means in your domain) is supplied by the
caller via an IntentClosure adapter — the resolver itself is
state-machine-agnostic.

Public surface:

    declare_intent(...)           -> ObligationRecord
        Convenience for the obligation-backed case (creates an
        obligation, registers predicates).

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
the consistency model, `closures.py` for the IntentClosure protocol.
"""

from .background import BackgroundTicker
from .causal import causal_priority, deadline_urgency, rank
from .closures import IntentClosure, ObligationClosureAdapter
from .declaration import declare_intent
from .predicates import (
    EntityAttributeEq,
    EntityAttributeThreshold,
    EntityExists,
)
from .primitives import (
    EntityId,
    EntityVector,
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
    # causal
    "causal_priority",
    "deadline_urgency",
    "rank",
]
