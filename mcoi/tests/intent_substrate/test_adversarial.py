"""Adversarial test — the test that earns the design.

Three entities mutated concurrently at high rate. A single intent
referencing all three with an AND-success condition that's only
briefly true between mutator passes. We replay aggressively and
verify:

  (1) ZERO false COMPLETIONS — the dangerous failure mode where the
      obligation is closed COMPLETED but the world was never actually
      consistent.
  (2) Drift / precondition signals can fire transiently — counted but
      not required to be zero (they self-correct on next replay).

If the two-confirmation rule is broken or removed, this test will
flake aggressively (false_completions > 0 within a few hundred
iterations).
"""

from __future__ import annotations

import threading
import time

import pytest

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.obligation import ObligationState
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.intent_substrate import (
    BackgroundTicker,
    EntityAttributeEq,
    IntentResolver,
    declare_intent,
)

from .conftest import MutableState, make_deadline, make_event, make_owner


@pytest.mark.parametrize("iterations", [3])
def test_zero_false_completions_under_concurrent_mutation(iterations):
    for _ in range(iterations):
        _run_one_burst()


def _run_one_burst() -> None:
    state = MutableState()
    obligations = ObligationRuntimeEngine()
    spine = EventSpineEngine()
    resolver = IntentResolver(
        state_view=state,
        obligations=obligations,
        spine=spine,
        confirm_window_s=0.05,
        debounce_window_s=0.0,
    )

    state.set("a", {"x": 0})
    state.set("b", {"y": 0})
    state.set("c", {"z": 0})

    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="all three at target", correlation_id="adv",
        success=(
            EntityAttributeEq("a", "x", 1),
            EntityAttributeEq("b", "y", 1),
            EntityAttributeEq("c", "z", 1),
        ),
    )

    false_completions: list[dict] = []

    def observe(closure):
        if closure.final_state != ObligationState.COMPLETED:
            return
        # Verify reality at the moment of the COMPLETED transition. A
        # phantom completion = closed COMPLETED while not all three
        # values are actually 1.
        x = state("a") or {}
        y = state("b") or {}
        z = state("c") or {}
        if not (x.get("x") == 1 and y.get("y") == 1 and z.get("z") == 1):
            false_completions.append(
                {"x": x, "y": y, "z": z}
            )

    resolver.add_closure_observer(observe)

    stop = threading.Event()

    def mutator(entity_id: str, field: str):
        i = 0
        while not stop.is_set():
            state.update(entity_id, **{field: 1})
            i += 1
            if i % 50 == 0:
                # Hold all-at-1 long enough for the confirm window to
                # ripen; the resolver should complete cleanly here.
                time.sleep(0.15)
            state.update(entity_id, **{field: 0})

    threads = [
        threading.Thread(target=mutator, args=("a", "x")),
        threading.Thread(target=mutator, args=("b", "y")),
        threading.Thread(target=mutator, args=("c", "z")),
    ]

    with BackgroundTicker(resolver, interval_s=0.02):
        for t in threads:
            t.start()

        # Drive replay aggressively by emitting WORLD_STATE_CHANGED
        # events into the resolver. We don't bother with the spine
        # here — on_event is the dispatch entry point.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
            if obligations.get_obligation(obl.obligation_id).state == ObligationState.COMPLETED:
                break
            time.sleep(0.005)

        stop.set()
        for t in threads:
            t.join(timeout=2.0)

    assert not false_completions, (
        f"phantom completions observed: {false_completions[:3]}"
    )
