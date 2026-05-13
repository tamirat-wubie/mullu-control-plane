"""Predicate serialization for restart resilience.

The IntentResolver's `_intents` and `_pending` live in process memory,
so a restart loses the predicate associations even though the
obligations themselves persist via ObligationRuntimeEngine.

This module bridges that gap:

  - `declare_intent` writes a serialized form of the predicates into
    obligation.metadata under METADATA_KEY at declare time.
  - `restore_intents_from_obligations(resolver, obligation_engine)`
    walks open substrate-tagged obligations on startup, deserializes
    their predicates, and re-registers each intent with the resolver.

Limitation: predicate values must be JSON-serializable (str / int /
float / bool / None / list / dict). Types that don't survive
json.dumps cannot be used in persistent intents. Custom predicate
kinds must be registered in `_PREDICATE_KINDS` and their serialize /
deserialize logic added to the dispatch in this module.

Pending fulfillment confirmations are NOT persisted: a restart drops
the candidate vector. The resolver simply re-evaluates from a fresh
baseline on the next event, so intents that were mid-confirm at
restart will (correctly) start a new candidate cycle. The two-confirm
safety property is preserved across restart — no false COMPLETED
closure is possible.
"""

from __future__ import annotations

import json
from typing import Any

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.obligation import ObligationState
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

from .predicates import (
    EntityAttributeEq,
    EntityAttributeThreshold,
    EntityExists,
)
from .primitives import IntentPredicate
from .resolver import IntentResolver

#: Metadata key under which serialized predicates are stored on the
#: obligation. Keep stable across versions — changing it strands all
#: existing in-flight obligations.
METADATA_KEY = "intent_substrate_predicates"

#: Registry of persistable predicate kind -> class. Add new entries
#: here AND extend serialize_predicate / deserialize_predicate when
#: introducing new predicate types that need persistence.
_PREDICATE_KINDS: dict[str, type] = {
    "EntityAttributeEq": EntityAttributeEq,
    "EntityAttributeThreshold": EntityAttributeThreshold,
    "EntityExists": EntityExists,
}

_TERMINAL_OBLIGATION_STATES = (
    ObligationState.COMPLETED,
    ObligationState.EXPIRED,
    ObligationState.CANCELLED,
)


def serialize_predicate(p: IntentPredicate) -> dict[str, Any]:
    """Serialize a predicate to a JSON-friendly dict.

    Raises ValueError if the predicate's kind is not registered for
    persistence — application predicates that aren't in
    `_PREDICATE_KINDS` cannot survive a restart.
    """
    kind = type(p).__name__
    if kind not in _PREDICATE_KINDS:
        raise ValueError(
            f"predicate kind {kind!r} is not registered for persistence"
        )
    if isinstance(p, EntityAttributeEq):
        return {
            "kind": kind,
            "entity_id": p.entity_id,
            "attribute": p.attribute,
            "value": p.value,
            "watches_kinds": [k.value for k in p.watches_kinds],
        }
    if isinstance(p, EntityAttributeThreshold):
        return {
            "kind": kind,
            "entity_id": p.entity_id,
            "attribute": p.attribute,
            "op": p.op,
            "threshold": p.threshold,
            "watches_kinds": [k.value for k in p.watches_kinds],
        }
    if isinstance(p, EntityExists):
        return {
            "kind": kind,
            "entity_id": p.entity_id,
            "watches_kinds": [k.value for k in p.watches_kinds],
        }
    raise ValueError(f"no serializer for predicate kind {kind!r}")


def deserialize_predicate(data: dict[str, Any]) -> IntentPredicate:
    """Construct a predicate from its serialized form."""
    kind = data.get("kind")
    cls = _PREDICATE_KINDS.get(kind) if kind else None
    if cls is None:
        raise ValueError(f"unknown predicate kind {kind!r}")
    raw_watches = data.get("watches_kinds")
    watches_kinds = tuple(
        EventType(k)
        for k in (
            raw_watches
            if raw_watches is not None
            else (EventType.WORLD_STATE_CHANGED.value,)
        )
    )
    if cls is EntityAttributeEq:
        return EntityAttributeEq(
            entity_id=data["entity_id"],
            attribute=data["attribute"],
            value=data["value"],
            watches_kinds=watches_kinds,
        )
    if cls is EntityAttributeThreshold:
        return EntityAttributeThreshold(
            entity_id=data["entity_id"],
            attribute=data["attribute"],
            op=data["op"],
            threshold=float(data["threshold"]),
            watches_kinds=watches_kinds,
        )
    if cls is EntityExists:
        return EntityExists(
            entity_id=data["entity_id"],
            watches_kinds=watches_kinds,
        )
    raise ValueError(f"no deserializer for predicate kind {kind!r}")


def serialize_predicate_set(
    preconditions: tuple[IntentPredicate, ...],
    success: tuple[IntentPredicate, ...],
) -> str:
    """Serialize a (preconditions, success) pair to a JSON string."""
    return json.dumps(
        {
            "preconditions": [serialize_predicate(p) for p in preconditions],
            "success": [serialize_predicate(p) for p in success],
        },
        sort_keys=True,
    )


def deserialize_predicate_set(
    blob: str,
) -> tuple[tuple[IntentPredicate, ...], tuple[IntentPredicate, ...]]:
    data = json.loads(blob)
    pre = tuple(deserialize_predicate(p) for p in data.get("preconditions", []))
    succ = tuple(deserialize_predicate(p) for p in data.get("success", []))
    return pre, succ


def restore_intents_from_obligations(
    resolver: IntentResolver,
    obligation_engine: ObligationRuntimeEngine,
) -> int:
    """Re-register substrate-driven intents from open obligations.

    Walks every obligation tagged with intent_substrate metadata; for
    each non-terminal one, deserializes its persisted predicates and
    registers with the resolver. Returns the count of restored intents.

    Call once at startup, after constructing the resolver, before
    accepting events. Idempotent — calling twice without intervening
    state changes simply re-registers the same intents.

    Malformed entries are skipped silently (no crash on a single bad
    record). Production callers should log skips via observation of
    the (count, total) ratio.
    """
    count = 0
    for obl in obligation_engine.list_obligations():
        if obl.metadata.get("intent_substrate") != "true":
            continue
        if obl.state in _TERMINAL_OBLIGATION_STATES:
            continue
        blob = obl.metadata.get(METADATA_KEY)
        if not blob:
            continue
        try:
            pre, succ = deserialize_predicate_set(blob)
        except (ValueError, KeyError, json.JSONDecodeError):
            continue
        resolver.register_intent(
            obl.obligation_id,
            preconditions=pre,
            success=succ,
        )
        count += 1
    return count
