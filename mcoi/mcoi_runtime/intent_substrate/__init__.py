"""Intent substrate — predicate-driven obligation closure with safe
two-confirmation semantics under non-linearizable concurrent reads.

Layers on top of the existing mcoi engines (WorldStateEngine,
ObligationRuntimeEngine, EventSpineEngine) — does NOT duplicate their
state, lifecycle, or audit trail.

Public surface:

    declare_intent(...)       -> ObligationRecord
    IntentResolver(...)       -> register, evaluate, on_event, tick
    BackgroundTicker(...)     -> drives tick() while idle
    EntityAttributeEq         -> predicate kinds
    EntityAttributeThreshold
    EntityExists
    causal_priority / rank    -> derived priority view

See `resolver.py` for the two-confirmation rule, `primitives.py` for
the consistency model.
"""

from .background import BackgroundTicker
from .causal import causal_priority, deadline_urgency, rank
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
    # core
    "IntentResolver",
    "BackgroundTicker",
    "declare_intent",
    # causal
    "causal_priority",
    "deadline_urgency",
    "rank",
]
