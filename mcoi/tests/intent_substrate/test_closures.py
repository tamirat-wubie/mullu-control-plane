"""Tests for ObligationClosureAdapter — the built-in IntentClosure that
wraps ObligationRuntimeEngine.

Verifies that:
  - is_open returns True for open obligations, False otherwise
  - close_success transitions to COMPLETED with substrate-tagged closer
  - close_precondition_failed transitions to CANCELLED
  - missing obligation IDs report not-open (not raise)
"""

from __future__ import annotations

from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.intent_substrate import ObligationClosureAdapter

from .conftest import make_deadline, make_owner


def _create_obl(engine, *, ref="ref-1"):
    return engine.create_obligation(
        trigger=ObligationTrigger.CUSTOM,
        trigger_ref_id=ref,
        owner=make_owner(),
        deadline=make_deadline(),
        description="t",
        correlation_id="c",
    )


def test_is_open_for_pending():
    eng = ObligationRuntimeEngine()
    adapter = ObligationClosureAdapter(eng)
    obl = _create_obl(eng)
    assert adapter.is_open(obl.obligation_id) is True


def test_is_open_for_active():
    eng = ObligationRuntimeEngine()
    adapter = ObligationClosureAdapter(eng)
    obl = _create_obl(eng)
    eng.activate(obl.obligation_id)
    assert adapter.is_open(obl.obligation_id) is True


def test_is_open_false_after_completed():
    eng = ObligationRuntimeEngine()
    adapter = ObligationClosureAdapter(eng)
    obl = _create_obl(eng)
    eng.close(
        obl.obligation_id, final_state=ObligationState.COMPLETED,
        reason="manual", closed_by="test",
    )
    assert adapter.is_open(obl.obligation_id) is False


def test_is_open_false_after_cancelled():
    eng = ObligationRuntimeEngine()
    adapter = ObligationClosureAdapter(eng)
    obl = _create_obl(eng)
    eng.close(
        obl.obligation_id, final_state=ObligationState.CANCELLED,
        reason="manual", closed_by="test",
    )
    assert adapter.is_open(obl.obligation_id) is False


def test_is_open_false_for_missing():
    eng = ObligationRuntimeEngine()
    adapter = ObligationClosureAdapter(eng)
    assert adapter.is_open("obl-nonexistent") is False


def test_close_success_transitions_to_completed():
    eng = ObligationRuntimeEngine()
    adapter = ObligationClosureAdapter(eng)
    obl = _create_obl(eng)
    closure = adapter.close_success(obl.obligation_id, "all good")
    assert closure.final_state == ObligationState.COMPLETED
    assert closure.reason == "all good"
    assert closure.closed_by == "intent_substrate"
    refreshed = eng.get_obligation(obl.obligation_id)
    assert refreshed.state == ObligationState.COMPLETED


def test_close_precondition_failed_transitions_to_cancelled():
    eng = ObligationRuntimeEngine()
    adapter = ObligationClosureAdapter(eng)
    obl = _create_obl(eng)
    closure = adapter.close_precondition_failed(obl.obligation_id, "pre fail")
    assert closure.final_state == ObligationState.CANCELLED
    assert closure.reason == "pre fail"
    assert closure.closed_by == "intent_substrate"
    refreshed = eng.get_obligation(obl.obligation_id)
    assert refreshed.state == ObligationState.CANCELLED
