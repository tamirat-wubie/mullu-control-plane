"""Tests for persistence — predicate (de)serialization and restart restore."""

from __future__ import annotations

import json
import time

import pytest

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.obligation import (
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.intent_substrate import (
    BackgroundTicker,
    EntityAttributeEq,
    EntityAttributeThreshold,
    EntityExists,
    IntentResolver,
    METADATA_KEY,
    ObligationClosureAdapter,
    declare_intent,
    deserialize_predicate,
    deserialize_predicate_set,
    restore_intents_from_obligations,
    restore_intents_from_obligations_report,
    serialize_predicate,
    serialize_predicate_set,
)

from .conftest import MutableState, make_deadline, make_owner


# ---- Predicate (de)serialization round-trip ----


def test_attribute_eq_roundtrip_basic():
    p = EntityAttributeEq("vendor", "approved", True)
    data = serialize_predicate(p)
    assert data["kind"] == "EntityAttributeEq"
    restored = deserialize_predicate(data)
    assert restored == p


def test_attribute_eq_roundtrip_custom_watches():
    p = EntityAttributeEq(
        "vendor", "status", "approved",
        watches_kinds=(EventType.APPROVAL_DECIDED, EventType.WORLD_STATE_CHANGED),
    )
    restored = deserialize_predicate(serialize_predicate(p))
    assert restored == p
    assert set(restored.watches_kinds) == {
        EventType.APPROVAL_DECIDED, EventType.WORLD_STATE_CHANGED,
    }


def test_attribute_eq_roundtrip_with_complex_value():
    """Values must be JSON-serializable; nested dicts/lists OK."""
    p = EntityAttributeEq("e", "config", {"nested": [1, 2, 3], "ok": True})
    restored = deserialize_predicate(serialize_predicate(p))
    assert restored == p


def test_attribute_threshold_roundtrip():
    p = EntityAttributeThreshold("budget", "allocated", ">=", 10_000.0)
    restored = deserialize_predicate(serialize_predicate(p))
    assert restored == p


@pytest.mark.parametrize("threshold", ["10000", True, float("nan"), float("inf")])
def test_attribute_threshold_deserialize_rejects_loose_threshold(threshold):
    with pytest.raises(ValueError, match="threshold must be a finite number"):
        deserialize_predicate(
            {
                "kind": "EntityAttributeThreshold",
                "entity_id": "budget",
                "attribute": "allocated",
                "op": ">=",
                "threshold": threshold,
            }
        )


def test_entity_exists_roundtrip():
    p = EntityExists("vendor")
    restored = deserialize_predicate(serialize_predicate(p))
    assert restored == p


def test_unknown_predicate_kind_raises():
    """Custom predicate not in the registry can't serialize."""
    class CustomPredicate:
        entity_id = "x"
        def evaluate(self, _state): return True
        def watches(self): return set()

    with pytest.raises(ValueError, match="not registered"):
        serialize_predicate(CustomPredicate())


def test_deserialize_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown predicate kind"):
        deserialize_predicate({"kind": "MadeUp"})


def test_deserialize_missing_watches_uses_default_world_state_event():
    restored = deserialize_predicate({
        "kind": "EntityExists",
        "entity_id": "vendor",
    })
    assert isinstance(restored, EntityExists)
    assert restored.watches() == {EventType.WORLD_STATE_CHANGED}


def test_predicate_set_roundtrip():
    pre = (
        EntityAttributeEq("a", "ready", True),
    )
    succ = (
        EntityAttributeEq("a", "shipped", True),
        EntityAttributeThreshold("budget", "allocated", ">=", 1000),
        EntityExists("manifest"),
    )
    blob = serialize_predicate_set(pre, succ)
    # Must be a valid JSON string.
    parsed = json.loads(blob)
    assert "preconditions" in parsed and "success" in parsed

    rpre, rsucc = deserialize_predicate_set(blob)
    assert rpre == pre
    assert rsucc == succ


def test_predicate_set_empty_pair():
    blob = serialize_predicate_set((), ())
    rpre, rsucc = deserialize_predicate_set(blob)
    assert rpre == ()
    assert rsucc == ()


# ---- declare_intent persists predicates in obligation metadata ----


def _build():
    state = MutableState()
    obligations = ObligationRuntimeEngine()
    spine = EventSpineEngine()
    resolver = IntentResolver(
        state_view=state,
        closure=ObligationClosureAdapter(obligations),
        spine=spine,
        confirm_window_s=0.1,
        debounce_window_s=0.0,
    )
    return state, obligations, spine, resolver


def test_declare_writes_serialized_predicates_to_metadata():
    _state, obligations, _spine, resolver = _build()
    pre = (EntityAttributeEq("e", "ready", True),)
    succ = (EntityAttributeEq("e", "shipped", True),)
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=pre, success=succ,
    )
    blob = obl.metadata.get(METADATA_KEY)
    assert isinstance(blob, str)
    rpre, rsucc = deserialize_predicate_set(blob)
    assert rpre == pre
    assert rsucc == succ


# ---- restore_intents_from_obligations ----


def test_restore_from_empty_engine_returns_zero():
    _state, obligations, _spine, resolver = _build()
    n = restore_intents_from_obligations(resolver, obligations)
    assert n == 0


def test_restore_skips_non_substrate_obligations():
    _state, obligations, _spine, resolver = _build()
    # An obligation NOT created via declare_intent has no substrate flag.
    obligations.create_obligation(
        trigger=ObligationTrigger.CUSTOM,
        trigger_ref_id="ref-non-substrate",
        owner=make_owner(),
        deadline=make_deadline(),
        description="manual obligation",
        correlation_id="manual",
        metadata={"intent_substrate": "false"},
    )
    n = restore_intents_from_obligations(resolver, obligations)
    assert n == 0
    assert not resolver.is_registered("ref-non-substrate")


def test_restore_skips_terminal_obligations():
    _state, obligations, _spine, resolver = _build()
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        success=(EntityAttributeEq("e", "shipped", True),),
    )
    obligations.close(
        obl.obligation_id, final_state=ObligationState.COMPLETED,
        reason="manual", closed_by="test",
    )
    # Fresh resolver simulating restart.
    fresh_state = MutableState()
    fresh_resolver = IntentResolver(
        state_view=fresh_state,
        closure=ObligationClosureAdapter(obligations),
        spine=EventSpineEngine(),
    )
    n = restore_intents_from_obligations(fresh_resolver, obligations)
    assert n == 0
    assert not fresh_resolver.is_registered(obl.obligation_id)


def test_restore_registers_open_substrate_obligations():
    _state, obligations, _spine, resolver = _build()
    obl_a = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="a", correlation_id="ca",
        success=(EntityAttributeEq("e", "shipped", True),),
    )
    obl_b = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="b", correlation_id="cb",
        preconditions=(EntityAttributeEq("e2", "ready", True),),
        success=(),
    )
    # Fresh resolver simulating restart.
    fresh_state = MutableState()
    fresh_resolver = IntentResolver(
        state_view=fresh_state,
        closure=ObligationClosureAdapter(obligations),
        spine=EventSpineEngine(),
    )
    n = restore_intents_from_obligations(fresh_resolver, obligations)
    assert n == 2
    assert fresh_resolver.is_registered(obl_a.obligation_id)
    assert fresh_resolver.is_registered(obl_b.obligation_id)


def test_restore_skips_malformed_metadata_without_crashing():
    _state, obligations, _spine, _resolver = _build()
    obligations.create_obligation(
        trigger=ObligationTrigger.CUSTOM,
        trigger_ref_id="bad-ref",
        owner=make_owner(),
        deadline=make_deadline(),
        description="malformed substrate",
        correlation_id="bad",
        metadata={
            "intent_substrate": "true",
            METADATA_KEY: "not valid json{",
        },
    )
    fresh_state = MutableState()
    fresh_resolver = IntentResolver(
        state_view=fresh_state,
        closure=ObligationClosureAdapter(obligations),
        spine=EventSpineEngine(),
    )
    n = restore_intents_from_obligations(fresh_resolver, obligations)
    assert n == 0  # malformed entry skipped


def test_restore_report_records_malformed_metadata_without_payload_leak():
    _state, obligations, _spine, _resolver = _build()
    bad = obligations.create_obligation(
        trigger=ObligationTrigger.CUSTOM,
        trigger_ref_id="bad-ref",
        owner=make_owner(),
        deadline=make_deadline(),
        description="malformed substrate",
        correlation_id="bad",
        metadata={
            "intent_substrate": "true",
            METADATA_KEY: "not valid json{secret-predicate}",
        },
    )
    fresh_state = MutableState()
    fresh_resolver = IntentResolver(
        state_view=fresh_state,
        closure=ObligationClosureAdapter(obligations),
        spine=EventSpineEngine(),
    )
    report = restore_intents_from_obligations_report(fresh_resolver, obligations)
    assert report.scanned_count == 1
    assert report.restored_count == 0
    assert report.skipped_count == 1
    assert report.skipped[0].obligation_id == bad.obligation_id
    assert report.skipped[0].reason == "malformed_predicate_metadata"
    assert report.skipped[0].detail == "JSONDecodeError"
    assert "secret-predicate" not in repr(report)


def test_restore_report_records_missing_predicate_metadata():
    _state, obligations, _spine, _resolver = _build()
    missing = obligations.create_obligation(
        trigger=ObligationTrigger.CUSTOM,
        trigger_ref_id="missing-ref",
        owner=make_owner(),
        deadline=make_deadline(),
        description="missing predicate metadata",
        correlation_id="missing",
        metadata={"intent_substrate": "true"},
    )
    fresh_state = MutableState()
    fresh_resolver = IntentResolver(
        state_view=fresh_state,
        closure=ObligationClosureAdapter(obligations),
        spine=EventSpineEngine(),
    )
    report = restore_intents_from_obligations_report(fresh_resolver, obligations)
    assert report.scanned_count == 1
    assert report.restored_count == 0
    assert report.skipped_count == 1
    assert report.skipped[0].obligation_id == missing.obligation_id
    assert report.skipped[0].reason == "missing_predicate_metadata"
    assert report.skipped[0].detail == "metadata key absent or empty"


def test_restore_is_idempotent():
    _state, obligations, _spine, resolver = _build()
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        success=(EntityAttributeEq("e", "shipped", True),),
    )
    fresh_state = MutableState()
    fresh_resolver = IntentResolver(
        state_view=fresh_state,
        closure=ObligationClosureAdapter(obligations),
        spine=EventSpineEngine(),
    )
    n1 = restore_intents_from_obligations(fresh_resolver, obligations)
    n2 = restore_intents_from_obligations(fresh_resolver, obligations)
    assert n1 == 1
    assert n2 == 1
    assert fresh_resolver.is_registered(obl.obligation_id)


# ---- Full restart-cycle integration ----


def test_restart_cycle_drives_intent_to_completion():
    """End-to-end: declare an intent, throw away the resolver as if the
    process restarted, restore from obligations, then drive to
    COMPLETED via the new resolver. This is the headline persistence
    guarantee — in-flight obligations don't get stuck after a restart.
    """
    state, obligations, _spine_initial, resolver_initial = _build()
    state.set("vendor", {"shipped": True})

    obl = declare_intent(
        resolver=resolver_initial, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="ship", correlation_id="c",
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    # Simulate restart: discard the resolver entirely. The obligation
    # is still in the engine; predicates are persisted in metadata.
    del resolver_initial

    fresh_spine = EventSpineEngine()
    fresh_resolver = IntentResolver(
        state_view=state,  # state is the same — it's the world, not the resolver
        closure=ObligationClosureAdapter(obligations),
        spine=fresh_spine,
        confirm_window_s=0.1,
        debounce_window_s=0.0,
    )
    n = restore_intents_from_obligations(fresh_resolver, obligations)
    assert n == 1
    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING

    fresh_resolver.evaluate(obl.obligation_id)
    assert fresh_resolver.pending_count() == 1

    with BackgroundTicker(fresh_resolver, interval_s=0.02):
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if obligations.get_obligation(obl.obligation_id).state == ObligationState.COMPLETED:
                break
            time.sleep(0.01)

    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.COMPLETED
