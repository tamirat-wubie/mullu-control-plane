"""Tests for IntentResolver — verdict logic, two-confirm safety, dispatch.

These tests use RecordingClosure (state-machine-agnostic) so they
exercise resolver behavior without coupling to ObligationRuntimeEngine.
For obligation-backed end-to-end behavior, see test_integration.py
and test_declaration.py.
"""

from __future__ import annotations

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.intent_substrate import (
    EntityAttributeEq,
    EntityAttributeThreshold,
    IntentResolver,
)

from .conftest import FakeClock, MutableState, RecordingClosure, make_event


def _build(*, confirm_window_s=0.5, debounce_window_s=0.0):
    state = MutableState()
    closure = RecordingClosure()
    spine = EventSpineEngine()
    clock = FakeClock()
    resolver = IntentResolver(
        state_view=state,
        closure=closure,
        spine=spine,
        confirm_window_s=confirm_window_s,
        debounce_window_s=debounce_window_s,
        clock=clock,
    )
    return state, closure, spine, resolver, clock


def _register(resolver, closure, intent_id, *, preconditions=(), success=()):
    closure.register(intent_id)
    resolver.register_intent(
        intent_id, preconditions=preconditions, success=success
    )


def test_open_when_pre_holds_no_success_no_close():
    state, closure, _spine, resolver, _clock = _build()
    state.set("vendor", {"approved": True})
    _register(
        resolver, closure, "i1",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate("i1")
    assert closure.successes == []
    assert closure.failures == []


def test_precondition_failure_calls_close_precondition_failed():
    state, closure, _spine, resolver, _clock = _build()
    state.set("vendor", {"approved": False})
    _register(
        resolver, closure, "i1",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(),
    )
    resolver.evaluate("i1")
    assert len(closure.failures) == 1
    assert closure.failures[0][0] == "i1"
    assert "precondition" in closure.failures[0][1]


def test_two_confirm_path_to_close_success():
    state, closure, _spine, resolver, clock = _build(confirm_window_s=0.5)
    state.set("vendor", {"approved": True, "shipped": True})
    _register(
        resolver, closure, "i1",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate("i1")
    # First eval: candidate pending — no close yet.
    assert closure.successes == []
    assert resolver.pending_count() == 1

    clock.advance(0.6)
    resolver.evaluate("i1")
    assert len(closure.successes) == 1
    assert closure.successes[0][0] == "i1"
    assert resolver.pending_count() == 0


def test_two_confirm_rejects_when_state_advances():
    """Phantom-fulfillment defense: if any relevant entity hash advances
    between candidate and confirm, success is rejected even if the
    success predicate still passes against the new state. Safety: never
    close_success unless a baseline survives the full confirm window."""
    state, closure, _spine, resolver, clock = _build(confirm_window_s=0.5)
    state.set("vendor", {"approved": True, "shipped": True})
    _register(
        resolver, closure, "i1",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate("i1")

    # Mutate an unrelated attribute — hash changes, value still satisfies.
    state.update("vendor", touched_at="now")
    clock.advance(0.6)
    resolver.evaluate("i1")
    # Safety property: NO close_success.
    assert closure.successes == []


def test_two_confirm_rejects_when_success_no_longer_holds():
    state, closure, _spine, resolver, clock = _build(confirm_window_s=0.5)
    state.set("vendor", {"approved": True, "shipped": True})
    _register(
        resolver, closure, "i1",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate("i1")

    state.update("vendor", shipped=False)
    clock.advance(0.6)
    resolver.evaluate("i1")
    assert closure.successes == []


def test_event_dispatch_routes_only_to_indexed_intents():
    state, closure, _spine, resolver, _clock = _build(confirm_window_s=0.1)
    state.set("vendor", {"shipped": True})
    state.set("budget", {"approved": True})

    _register(
        resolver, closure, "i_vendor",
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    _register(
        resolver, closure, "i_budget",
        success=(
            EntityAttributeEq(
                "budget", "approved", True,
                watches_kinds=(EventType.APPROVAL_DECIDED,),
            ),
        ),
    )

    # WORLD_STATE_CHANGED — only i_vendor watches that type.
    resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
    # i_vendor should be in pending (success holds, awaits confirm).
    assert resolver.pending_count() == 1


def test_event_for_unsubscribed_type_ignored():
    state, closure, _spine, resolver, _clock = _build()
    state.set("vendor", {"approved": True})
    _register(
        resolver, closure, "i1",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    # Type the predicate doesn't watch.
    resolver.on_event(make_event(EventType.JOB_STATE_TRANSITION))
    assert closure.successes == []
    assert closure.failures == []
    assert resolver.pending_count() == 0


def test_debounced_event_is_deferred_until_tick():
    state, closure, _spine, resolver, clock = _build(
        confirm_window_s=0.1,
        debounce_window_s=1.0,
    )
    state.set("vendor", {"shipped": False})
    _register(
        resolver, closure, "i1",
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )

    resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
    clock.advance(0.2)
    state.update("vendor", shipped=True)
    resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))

    assert closure.successes == []
    assert resolver.pending_count() == 0

    clock.advance(0.8)
    resolver.tick()
    assert resolver.pending_count() == 1

    clock.advance(0.2)
    resolver.tick()
    assert len(closure.successes) == 1
    assert closure.successes[0][0] == "i1"


def test_emit_and_dispatch_writes_to_spine():
    state, closure, spine, resolver, _clock = _build()
    state.set("vendor", {"shipped": True})
    _register(
        resolver, closure, "i1",
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    event = make_event(EventType.WORLD_STATE_CHANGED)
    resolver.emit_and_dispatch(event)
    assert spine.get_event(event.event_id) is event


def test_deregister_stops_responses():
    state, closure, _spine, resolver, _clock = _build()
    state.set("vendor", {"shipped": True})
    _register(
        resolver, closure, "i1",
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.deregister_intent("i1")
    assert not resolver.is_registered("i1")
    resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
    assert closure.successes == []


def test_reregister_replaces_old_event_index_entries():
    state, closure, _spine, resolver, _clock = _build(confirm_window_s=0.1)
    state.set("vendor", {"shipped": True})
    closure.register("i1")
    resolver.register_intent(
        "i1",
        preconditions=(),
        success=(
            EntityAttributeEq(
                "vendor",
                "shipped",
                True,
                watches_kinds=(EventType.APPROVAL_DECIDED,),
            ),
        ),
    )
    resolver.register_intent(
        "i1",
        preconditions=(),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )

    resolver.on_event(make_event(EventType.APPROVAL_DECIDED))
    assert resolver.pending_count() == 0

    resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
    assert resolver.pending_count() == 1


def test_intent_with_closed_lifecycle_self_cleans():
    """If an intent is closed externally (closure.is_open returns False),
    the resolver self-cleans on its next look at the intent."""
    state, closure, _spine, resolver, _clock = _build()
    state.set("vendor", {"shipped": True})
    _register(
        resolver, closure, "i1",
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    # Close externally (e.g. manual cancel).
    closure._open.discard("i1")
    resolver.evaluate("i1")
    assert not resolver.is_registered("i1")
    assert closure.successes == []  # not closed by resolver


def test_threshold_predicate_end_to_end():
    state, closure, _spine, resolver, clock = _build(confirm_window_s=0.1)
    state.set("queue", {"depth": 0})
    _register(
        resolver, closure, "i1",
        success=(EntityAttributeThreshold("queue", "depth", "<=", 0),),
    )
    resolver.evaluate("i1")
    assert resolver.pending_count() == 1
    clock.advance(0.2)
    resolver.evaluate("i1")
    assert len(closure.successes) == 1


def test_observer_receives_closure_records():
    state, closure, _spine, resolver, clock = _build(confirm_window_s=0.1)
    state.set("vendor", {"shipped": True})
    _register(
        resolver, closure, "i1",
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    received = []
    resolver.add_closure_observer(lambda r: received.append(r))
    resolver.evaluate("i1")
    clock.advance(0.2)
    resolver.evaluate("i1")
    # Observer should have received the success record from the closure.
    assert len(received) == 1
    assert received[0] == ("success", "i1", "intent_substrate: success predicates confirmed")
