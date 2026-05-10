"""Core primitives for the intent substrate.

The substrate layers automatic predicate-driven obligation closure on
top of the existing mcoi engines:

  - Lifecycle:    ObligationRuntimeEngine (PENDING -> ACTIVE -> closed)
  - Audit trail:  EventSpineEngine        (event records, correlations)

Notably, the substrate does NOT couple to WorldStateEngine. That engine
holds evidence-derived, immutable entities — the wrong primitive for
predicate-driven fulfillment that needs to observe mutable state. In
mcoi, mutable state lives across many per-engine state machines
(obligation lifecycle, approval queues, workflow stages, etc.).
Rather than pick one, the resolver consumes an application-supplied
`StateView` callable that returns the current attribute mapping for an
entity. The application is responsible for wiring it to whichever
engines hold the relevant state.

This module defines:

  StateView
    A callable `(entity_id) -> Mapping[str, Any] | None`. Returns the
    current attribute slice for an entity, or None if absent.

  EntityVector
    Per-entity hash projection used for the two-confirmation rule. If
    any hash advances between candidate read and confirm read, the
    candidate is rejected — defending against phantom success under
    non-linearizable concurrent mutation.

  IntentPredicate (Protocol)
    Adapter-affinity discipline: each predicate binds to exactly ONE
    entity_id. Cross-entity AND/OR composition happens at the intent
    level. This keeps each evaluation operating on a self-consistent
    slice of state; the only consistency concern at the substrate
    level is *cross-entity* drift, handled by the EntityVector check.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from mcoi_runtime.contracts.event import EventType

EntityId = str

#: Caller-supplied state lookup. Returns the current attribute mapping
#: for the entity, or None if it does not (yet) exist.
StateView = Callable[[EntityId], "Mapping[str, Any] | None"]

EntityVector = Mapping[EntityId, str]

_MISSING_HASH = "<missing>"


def hash_state(attrs: "Mapping[str, Any] | None") -> str:
    """Stable hash of a state mapping. None hashes to a sentinel so
    that "entity does not exist" is a distinguishable, comparable
    state for two-confirm purposes.
    """
    if attrs is None:
        return _MISSING_HASH
    payload = json.dumps(dict(attrs), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def gather_vector(
    entity_ids: set[EntityId],
    state_view: StateView,
) -> dict[EntityId, str]:
    """Build an EntityVector by hashing each requested entity's current state."""
    return {eid: hash_state(state_view(eid)) for eid in entity_ids}


@runtime_checkable
class IntentPredicate(Protocol):
    """Predicate evaluated against a single entity's attribute mapping.

    Affinity rule: every predicate binds to exactly one `entity_id`.
    Cross-entity logic (AND/OR) is composed at the intent level, never
    inside a predicate. Each evaluation reads one entity's state; the
    state-view callable is responsible for returning a self-consistent
    slice for that entity.
    """

    @property
    def entity_id(self) -> EntityId: ...

    def evaluate(self, state: "Mapping[str, Any] | None") -> bool: ...

    def watches(self) -> set[EventType]:
        """Event types that should re-trigger evaluation of this predicate.

        Default for the starter predicates is WORLD_STATE_CHANGED;
        application-specific predicates can subscribe to narrower types
        (APPROVAL_DECIDED, INCIDENT_RESOLVED, etc.) for efficiency.
        """
        ...
