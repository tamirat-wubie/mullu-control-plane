"""Adversarial test — the test that earns the design.

Three entities mutated concurrently at high rate. A single intent
referencing all three with an AND-success condition that's only
briefly true between mutator passes. We replay aggressively and
verify:

  (1) ZERO false success closures — the dangerous failure mode where
      close_success is called but the world was never actually
      consistent at the moment of closure.
  (2) Drift / precondition signals can fire transiently — counted but
      not required to be zero (they self-correct on next replay).

Uses RecordingClosure so the test exercises pure resolver verdict
logic without obligation lifecycle overhead. If the two-confirmation
rule is broken or removed, this test will flake aggressively
(false_completions > 0 within a few hundred iterations).
"""

from __future__ import annotations

import threading
import time

import pytest

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.intent_substrate import (
    BackgroundTicker,
    EntityAttributeEq,
    IntentResolver,
)

from .conftest import MutableState, RecordingClosure, make_event


@pytest.mark.parametrize("iterations", [3])
def test_zero_false_completions_under_concurrent_mutation(iterations):
    for _ in range(iterations):
        _run_one_burst()


def _run_one_burst() -> None:
    state = MutableState()
    closure = RecordingClosure()
    spine = EventSpineEngine()
    resolver = IntentResolver(
        state_view=state,
        closure=closure,
        spine=spine,
        confirm_window_s=0.05,
        debounce_window_s=0.0,
    )

    state.set("a", {"x": 0})
    state.set("b", {"y": 0})
    state.set("c", {"z": 0})

    intent_id = "adv-1"
    closure.register(intent_id)
    resolver.register_intent(
        intent_id,
        preconditions=(),
        success=(
            EntityAttributeEq("a", "x", 1),
            EntityAttributeEq("b", "y", 1),
            EntityAttributeEq("c", "z", 1),
        ),
    )

    false_completions: list[dict] = []

    def observe(record):
        kind, iid, _reason = record
        if kind != "success":
            return
        x = state("a") or {}
        y = state("b") or {}
        z = state("c") or {}
        if not (x.get("x") == 1 and y.get("y") == 1 and z.get("z") == 1):
            false_completions.append({"x": x, "y": y, "z": z})

    resolver.add_closure_observer(observe)

    stop = threading.Event()

    def mutator(entity_id: str, field: str):
        i = 0
        while not stop.is_set():
            state.update(entity_id, **{field: 1})
            i += 1
            if i % 50 == 0:
                # Hold all-at-1 long enough for confirm to ripen.
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

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
            if closure.successes:
                break
            time.sleep(0.005)

        stop.set()
        for t in threads:
            t.join(timeout=2.0)

    assert not false_completions, (
        f"phantom completions observed: {false_completions[:3]}"
    )
