"""Tests for IntentResolver — register, dispatch, two-confirm safety."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.obligation import (
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.intent_substrate import (
    EntityAttributeEq,
    EntityAttributeThreshold,
    IntentResolver,
    declare_intent,
)

from .conftest import FakeClock, MutableState, make_deadline, make_event, make_owner


def _build(*, confirm_window_s=0.5, debounce_window_s=0.0):
    state = MutableState()
    obligations = ObligationRuntimeEngine()
    spine = EventSpineEngine()
    clock = FakeClock()
    resolver = IntentResolver(
        state_view=state,
        obligations=obligations,
        spine=spine,
        confirm_window_s=confirm_window_s,
        debounce_window_s=debounce_window_s,
        clock=clock,
    )
    return state, obligations, spine, resolver, clock


def test_register_unknown_obligation_rejected():
    _state, obligations, spine, resolver, _clock = _build()
    with pytest.raises(LookupError):
        resolver.register_intent(
            "obl-nope", preconditions=(), success=()
        )


def test_open_when_pre_holds_no_success():
    state, obligations, spine, resolver, _clock = _build()
    state.set("vendor", {"approved": True})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate(obl.obligation_id)
    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING


def test_precondition_failure_cancels_obligation():
    state, obligations, spine, resolver, _clock = _build()
    state.set("vendor", {"approved": False})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(),
    )
    resolver.evaluate(obl.obligation_id)
    refreshed = obligations.get_obligation(obl.obligation_id)
    assert refreshed.state == ObligationState.CANCELLED


def test_two_confirm_path_to_completed():
    state, obligations, spine, resolver, clock = _build(confirm_window_s=0.5)
    state.set("vendor", {"approved": True, "shipped": True})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate(obl.obligation_id)
    # After first eval, candidate fulfillment is pending — not yet COMPLETED.
    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING
    assert resolver.pending_count() == 1

    clock.advance(0.6)
    resolver.evaluate(obl.obligation_id)
    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.COMPLETED
    assert resolver.pending_count() == 0


def test_two_confirm_rejects_when_state_advances():
    """Phantom-fulfillment defense: if any relevant entity hash advances
    between candidate and confirm, fulfillment is rejected — even if
    success still passes against the new state. Safety property: NOT
    COMPLETED until a baseline survives the full confirm window with
    no advance."""
    state, obligations, spine, resolver, clock = _build(confirm_window_s=0.5)
    state.set("vendor", {"approved": True, "shipped": True})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate(obl.obligation_id)

    # Mutate an unrelated attribute — hash changes, value still satisfies.
    state.update("vendor", touched_at="now")
    clock.advance(0.6)
    resolver.evaluate(obl.obligation_id)
    # Safety property: NOT COMPLETED.
    assert obligations.get_obligation(obl.obligation_id).state != ObligationState.COMPLETED


def test_two_confirm_rejects_when_success_no_longer_holds():
    state, obligations, spine, resolver, clock = _build(confirm_window_s=0.5)
    state.set("vendor", {"approved": True, "shipped": True})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate(obl.obligation_id)

    state.update("vendor", shipped=False)
    clock.advance(0.6)
    resolver.evaluate(obl.obligation_id)
    assert obligations.get_obligation(obl.obligation_id).state != ObligationState.COMPLETED


def test_event_dispatch_routes_only_to_indexed_intents():
    state, obligations, spine, resolver, _clock = _build(confirm_window_s=0.1)
    state.set("vendor", {"approved": True, "shipped": True})
    state.set("budget", {"allocated": 0})

    obl_a = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="A", correlation_id="cA",
        preconditions=(),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    obl_b = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="B", correlation_id="cB",
        preconditions=(),
        success=(
            EntityAttributeEq(
                "budget", "approved", True,
                watches_kinds=(EventType.APPROVAL_DECIDED,),
            ),
        ),
    )
    closures = []
    resolver.add_closure_observer(lambda c: closures.append(c.obligation_id))

    # WORLD_STATE_CHANGED event: only obl_a watches that type.
    resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))

    # obl_a should have entered pending fulfillment (success holds).
    a = obligations.get_obligation(obl_a.obligation_id)
    b = obligations.get_obligation(obl_b.obligation_id)
    assert a.state == ObligationState.PENDING  # candidate, not yet confirmed
    assert resolver.pending_count() == 1
    assert b.state == ObligationState.PENDING


def test_event_for_unsubscribed_type_ignored():
    state, obligations, spine, resolver, _clock = _build()
    state.set("vendor", {"approved": True})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(EntityAttributeEq("vendor", "approved", True),),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    closures = []
    resolver.add_closure_observer(lambda c: closures.append(c))

    # Event type the predicate does NOT watch.
    resolver.on_event(make_event(EventType.JOB_STATE_TRANSITION))
    assert closures == []
    assert resolver.pending_count() == 0


def test_emit_and_dispatch_writes_to_spine():
    state, obligations, spine, resolver, _clock = _build()
    state.set("vendor", {"approved": True, "shipped": True})
    declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    event = make_event(EventType.WORLD_STATE_CHANGED)
    resolver.emit_and_dispatch(event)
    # The event made it into the spine.
    assert spine.get_event(event.event_id) is event


def test_deregistered_intent_no_longer_responds():
    state, obligations, spine, resolver, _clock = _build()
    state.set("vendor", {"approved": True, "shipped": True})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.deregister_intent(obl.obligation_id)
    assert not resolver.is_registered(obl.obligation_id)
    resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
    # Obligation is still PENDING; resolver no longer drives it.
    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING


def test_already_closed_obligation_skipped():
    state, obligations, spine, resolver, _clock = _build()
    state.set("vendor", {"approved": True, "shipped": True})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    obligations.close(
        obl.obligation_id,
        final_state=ObligationState.CANCELLED,
        reason="manual cancel",
        closed_by="test",
    )
    # Resolver evaluation should noop and self-clean.
    resolver.evaluate(obl.obligation_id)
    assert not resolver.is_registered(obl.obligation_id)


def test_threshold_predicate_end_to_end():
    state, obligations, spine, resolver, clock = _build(confirm_window_s=0.1)
    state.set("queue", {"depth": 0})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(),
        success=(EntityAttributeThreshold("queue", "depth", "<=", 0),),
    )
    resolver.evaluate(obl.obligation_id)
    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING
    assert resolver.pending_count() == 1
    clock.advance(0.2)
    resolver.evaluate(obl.obligation_id)
    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.COMPLETED
