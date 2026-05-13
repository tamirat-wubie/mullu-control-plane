"""Soak test — longer wall-clock burst to catch races the 2s adversarial
test misses.

Runs ONLY when the `soak` marker is selected:
    pytest -m soak tests/intent_substrate/test_soak.py

Same correctness contract as test_adversarial: zero false success
closures under high-rate concurrent mutation, with the substrate
driving fulfillments on its own via BackgroundTicker. Uses
RecordingClosure (state-machine-agnostic) so the test focuses on
resolver verdict logic, not lifecycle plumbing.
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

pytestmark = pytest.mark.soak


def test_zero_false_completions_30s_concurrent():
    """30-second soak with 5 mutator threads against 3 entities.
    Targets ~1M+ mutations with zero false success closures."""

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

    intent_id = "soak-1"
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
        kind, _iid, _reason = record
        if kind != "success":
            return
        x = state("a") or {}
        y = state("b") or {}
        z = state("c") or {}
        if not (x.get("x") == 1 and y.get("y") == 1 and z.get("z") == 1):
            false_completions.append({"x": x, "y": y, "z": z})

    resolver.add_closure_observer(observe)

    stop = threading.Event()
    mutation_count = {"n": 0}
    count_lock = threading.Lock()

    def mutator(entity_id: str, field: str):
        i = 0
        while not stop.is_set():
            state.update(entity_id, **{field: 1})
            state.update(entity_id, **{field: 0})
            i += 2
            if i % 200 == 0:
                with count_lock:
                    mutation_count["n"] += 200
                # Brief settle window so the ticker can confirm a clean
                # candidate when all three happen to be 1 simultaneously.
                state.update(entity_id, **{field: 1})
                time.sleep(0.12)

    threads: list[threading.Thread] = []
    # Two mutators per first two entities for higher contention.
    for entity_id, field in [
        ("a", "x"), ("a", "x"),
        ("b", "y"), ("b", "y"),
        ("c", "z"),
    ]:
        t = threading.Thread(target=mutator, args=(entity_id, field))
        t.start()
        threads.append(t)

    with BackgroundTicker(resolver, interval_s=0.02):
        end = time.monotonic() + 30.0
        while time.monotonic() < end:
            resolver.on_event(make_event(EventType.WORLD_STATE_CHANGED))
            time.sleep(0.01)

    stop.set()
    for t in threads:
        t.join(timeout=5.0)

    assert not false_completions, (
        f"phantom completions under soak: count={len(false_completions)} "
        f"sample={false_completions[:3]}"
    )
    assert mutation_count["n"] > 10_000, (
        f"mutators under-ran: {mutation_count['n']}"
    )
