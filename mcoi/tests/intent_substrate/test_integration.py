"""End-to-end integration test — vendor onboarding intent driven through
its full lifecycle across all three engines (ObligationRuntimeEngine,
EventSpineEngine, IntentResolver) with a realistic two-entity AND
success condition.

This is the textbook AND-across-entities case the substrate is designed
to handle correctly under non-linearizable cross-entity reads.
"""

from __future__ import annotations

import time

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.obligation import ObligationState
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.intent_substrate import (
    BackgroundTicker,
    EntityAttributeEq,
    EntityAttributeThreshold,
    IntentResolver,
    declare_intent,
)

from .conftest import MutableState, make_deadline, make_event, make_owner


def _wait_for(predicate, *, timeout_s=2.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _build_intent():
    state = MutableState()
    obligations = ObligationRuntimeEngine()
    spine = EventSpineEngine()
    resolver = IntentResolver(
        state_view=state,
        obligations=obligations,
        spine=spine,
        confirm_window_s=0.1,
        debounce_window_s=0.0,
    )
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner("ops"), deadline=make_deadline(),
        description="vendor-001 onboarding complete",
        correlation_id="vendor-001-onboarding",
        success=(
            EntityAttributeEq(
                "approval:vendor-001", "status", "approved",
                # Subscribe to BOTH approval events and the coarse
                # WORLD_STATE_CHANGED for safety.
                watches_kinds=(
                    EventType.APPROVAL_DECIDED,
                    EventType.WORLD_STATE_CHANGED,
                ),
            ),
            EntityAttributeThreshold(
                "budget:vendor", "allocated", ">=", 10_000.0,
                watches_kinds=(EventType.WORLD_STATE_CHANGED,),
            ),
        ),
    )
    return state, obligations, spine, resolver, obl


def test_full_lifecycle_completes_when_both_conditions_meet():
    state, obligations, _spine, resolver, obl = _build_intent()
    with BackgroundTicker(resolver, interval_s=0.02):
        # Initial: no approval, no allocation. Intent stays open.
        resolver.evaluate(obl.obligation_id)
        assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING
        assert resolver.pending_count() == 0

        # Step 1: approval submitted but not decided.
        state.set("approval:vendor-001", {"status": "pending"})
        resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
        time.sleep(0.05)
        assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING

        # Step 2: approval decided.
        state.update("approval:vendor-001", status="approved")
        resolver.on_event(make_event(EventType.APPROVAL_DECIDED))
        time.sleep(0.05)
        # Budget still 0, so success doesn't hold.
        assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING
        assert resolver.pending_count() == 0

        # Step 3: partial allocation (5k — below threshold).
        state.set("budget:vendor", {"allocated": 5_000})
        resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
        time.sleep(0.05)
        assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING
        assert resolver.pending_count() == 0

        # Step 4: top up to 11k (meets threshold). Both conditions now
        # hold; resolver enters PENDING_FULFILLMENT and ticker confirms.
        state.update("budget:vendor", allocated=11_000)
        resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))

        assert _wait_for(
            lambda: obligations.get_obligation(obl.obligation_id).state
            == ObligationState.COMPLETED,
            timeout_s=1.5,
        ), (
            f"intent never completed — state is "
            f"{obligations.get_obligation(obl.obligation_id).state}"
        )


def test_intent_substrate_metadata_persisted_on_obligation():
    """The substrate's metadata flag stays on the obligation through
    closure so consumers can identify substrate-driven closures."""
    _state, obligations, _spine, _resolver, obl = _build_intent()
    fetched = obligations.get_obligation(obl.obligation_id)
    assert fetched.metadata.get("intent_substrate") == "true"
