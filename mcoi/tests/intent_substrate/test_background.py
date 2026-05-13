"""Tests for BackgroundTicker — start/stop, idle fulfillment, exception isolation."""

from __future__ import annotations

import logging
import time

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.intent_substrate import (
    BackgroundTicker,
    EntityAttributeEq,
    IntentResolver,
)

from .conftest import MutableState, RecordingClosure


def _build_resolver(*, confirm_window_s=0.1, debounce_window_s=0.0):
    state = MutableState()
    closure = RecordingClosure()
    spine = EventSpineEngine()
    resolver = IntentResolver(
        state_view=state,
        closure=closure,
        spine=spine,
        confirm_window_s=confirm_window_s,
        debounce_window_s=debounce_window_s,
    )
    return state, closure, resolver


def test_invalid_interval_rejected():
    _state, _closure, resolver = _build_resolver()
    with pytest.raises(ValueError):
        BackgroundTicker(resolver, interval_s=0.0)


def test_double_start_rejected():
    _state, _closure, resolver = _build_resolver()
    ticker = BackgroundTicker(resolver, interval_s=0.05)
    ticker.start()
    try:
        with pytest.raises(RuntimeError):
            ticker.start()
    finally:
        ticker.stop()


def test_stop_without_start_is_noop():
    _state, _closure, resolver = _build_resolver()
    BackgroundTicker(resolver, interval_s=0.05).stop()


def test_context_manager_starts_and_stops():
    _state, _closure, resolver = _build_resolver()
    with BackgroundTicker(resolver, interval_s=0.05) as ticker:
        assert ticker.is_running()
    assert not ticker.is_running()


def test_idle_fulfillment_drives_pending_to_close_success():
    state, closure, resolver = _build_resolver(confirm_window_s=0.1)
    state.set("vendor", {"shipped": True})
    closure.register("i1")
    resolver.register_intent(
        "i1", preconditions=(),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate("i1")
    assert resolver.pending_count() == 1
    assert closure.successes == []

    with BackgroundTicker(resolver, interval_s=0.02):
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if closure.successes:
                break
            time.sleep(0.01)

    assert len(closure.successes) == 1


def test_observer_notified_for_background_ticker_close():
    """Regression: tick() must notify closure observers, even when
    invoked from BackgroundTicker (not from evaluate/on_event). If
    tick() returns records but doesn't call _notify, observers stay
    silent and downstream consumers (audit, logging, metrics) miss
    every background-driven closure."""
    state, closure, resolver = _build_resolver(confirm_window_s=0.1)
    state.set("vendor", {"shipped": True})
    closure.register("i1")
    resolver.register_intent(
        "i1", preconditions=(),
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate("i1")  # creates pending — no notify yet
    assert resolver.pending_count() == 1

    received = []
    resolver.add_closure_observer(lambda r: received.append(r))

    with BackgroundTicker(resolver, interval_s=0.02):
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if received:
                break
            time.sleep(0.01)

    assert len(received) == 1, (
        "BackgroundTicker drove the close but observer was not notified"
    )


def test_ticker_survives_resolver_exceptions(caplog):
    _state, _closure, resolver = _build_resolver()
    call_count = {"n": 0}
    original_tick = resolver.tick

    def flaky_tick():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("synthetic")
        return original_tick()

    resolver.tick = flaky_tick  # type: ignore[method-assign]

    with caplog.at_level(
        logging.ERROR, logger="mcoi_runtime.intent_substrate.background"
    ):
        with BackgroundTicker(resolver, interval_s=0.02):
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline and call_count["n"] < 3:
                time.sleep(0.01)

    assert call_count["n"] >= 3
    assert any(
        "synthetic" in r.getMessage() or r.exc_info for r in caplog.records
    )
