"""Tests for BackgroundTicker — start/stop, idle fulfillment, exception isolation."""

from __future__ import annotations

import logging
import time

import pytest

from mcoi_runtime.contracts.obligation import ObligationState
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.intent_substrate import (
    BackgroundTicker,
    EntityAttributeEq,
    IntentResolver,
    declare_intent,
)

from .conftest import MutableState, make_deadline, make_owner


def _build_resolver(*, confirm_window_s=0.1, debounce_window_s=0.0):
    state = MutableState()
    obligations = ObligationRuntimeEngine()
    spine = EventSpineEngine()
    resolver = IntentResolver(
        state_view=state,
        obligations=obligations,
        spine=spine,
        confirm_window_s=confirm_window_s,
        debounce_window_s=debounce_window_s,
    )
    return state, obligations, resolver


def test_invalid_interval_rejected():
    _state, _obl, resolver = _build_resolver()
    with pytest.raises(ValueError):
        BackgroundTicker(resolver, interval_s=0.0)


def test_double_start_rejected():
    _state, _obl, resolver = _build_resolver()
    ticker = BackgroundTicker(resolver, interval_s=0.05)
    ticker.start()
    try:
        with pytest.raises(RuntimeError):
            ticker.start()
    finally:
        ticker.stop()


def test_stop_without_start_is_noop():
    _state, _obl, resolver = _build_resolver()
    BackgroundTicker(resolver, interval_s=0.05).stop()


def test_context_manager_starts_and_stops():
    _state, _obl, resolver = _build_resolver()
    with BackgroundTicker(resolver, interval_s=0.05) as ticker:
        assert ticker.is_running()
    assert not ticker.is_running()


def test_idle_fulfillment_drives_pending_to_completed():
    state, obligations, resolver = _build_resolver(confirm_window_s=0.1)
    state.set("vendor", {"shipped": True})
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="ship", correlation_id="c",
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    resolver.evaluate(obl.obligation_id)
    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.PENDING

    with BackgroundTicker(resolver, interval_s=0.02):
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if obligations.get_obligation(obl.obligation_id).state == ObligationState.COMPLETED:
                break
            time.sleep(0.01)

    assert obligations.get_obligation(obl.obligation_id).state == ObligationState.COMPLETED


def test_ticker_survives_resolver_exceptions(caplog):
    _state, _obl, resolver = _build_resolver()
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
