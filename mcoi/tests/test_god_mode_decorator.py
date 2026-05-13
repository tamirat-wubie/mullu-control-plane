"""Tests for `@requires_god_ticket` decorator and demonstrator wiring.

Verifies that:
- callable refuses to run without a ticket
- mismatched ticket (wrong capability) is rejected
- expired/consumed/revoked ticket is rejected
- successful call consumes the ticket and emits a SUCCESS receipt
- raised exception consumes the ticket and emits a FAILURE receipt
- the `replay.mutate_recorder` demonstrator actually mutates the trace
"""
from __future__ import annotations

import pytest

from mcoi_runtime.contracts.god_mode import (
    GodCapability,
    GodCapabilityBlastRadius,
    GodReceiptOutcome,
)
from mcoi_runtime.core.god_mode_demonstrators import truncate_replay_trace
from mcoi_runtime.core.god_mode_engine import (
    GodModeEngine,
    GodModeEngineError,
    requires_god_ticket,
    set_engine,
)
from mcoi_runtime.core.god_mode_registry import (
    GodModeRegistry,
    set_registry,
)


_VERY_LONG_JUST = "x" * 130


@pytest.fixture(autouse=True)
def _isolated_engine():
    registry = GodModeRegistry()
    registry.register_capability(
        GodCapability(
            module="replay",
            name="mutate_recorder",
            description="Mutate the in-memory replay recorder buffer.",
            blast_radius=GodCapabilityBlastRadius.PLATFORM,
            bypasses=("replay_immutability",),
            default_ttl_seconds=120,
        )
    )
    registry.register_capability(
        GodCapability(
            module="rbac",
            name="impersonate_user",
            description="Act as another identity.",
            blast_radius=GodCapabilityBlastRadius.PLATFORM,
            bypasses=("identity_binding",),
            default_ttl_seconds=300,
        )
    )
    registry.agree_to_register(
        module="replay",
        name="mutate_recorder",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    registry.agree_to_register(
        module="rbac",
        name="impersonate_user",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    engine = GodModeEngine(registry=registry)
    set_registry(registry)
    set_engine(engine)
    yield engine
    set_registry(None)
    set_engine(None)


class _FakeRecorder:
    """Minimal stand-in for ReplayRecorder for decorator tests."""

    def __init__(self) -> None:
        self._traces: dict[str, list[dict[str, str]]] = {}


def _issue(engine, *, module="replay", name="mutate_recorder", actor="alice"):
    ticket, _ = engine.issue_ticket(
        actor_id=actor,
        module=module,
        name=name,
        justification=_VERY_LONG_JUST,
    )
    return ticket.ticket_id


# --- Decorator behavior ---


def test_decorator_refuses_without_ticket(_isolated_engine):
    with pytest.raises(GodModeEngineError):
        truncate_replay_trace(recorder=_FakeRecorder(), trace_id="t-1", keep_frames=0)


def test_decorator_rejects_mismatched_capability(_isolated_engine):
    # Issue a ticket for impersonate_user, try to use it for mutate_recorder
    wrong_ticket = _issue(_isolated_engine, module="rbac", name="impersonate_user")
    with pytest.raises(GodModeEngineError):
        truncate_replay_trace(
            recorder=_FakeRecorder(),
            trace_id="t-1",
            keep_frames=0,
            ticket_id=wrong_ticket,
        )


def test_decorator_rejects_consumed_ticket(_isolated_engine):
    tid = _issue(_isolated_engine)
    rec = _FakeRecorder()
    rec._traces["t-1"] = [{"op": "x"}, {"op": "y"}, {"op": "z"}]
    truncate_replay_trace(recorder=rec, trace_id="t-1", keep_frames=1, ticket_id=tid)
    # Second call should fail because ticket is consumed.
    with pytest.raises(GodModeEngineError):
        truncate_replay_trace(
            recorder=rec, trace_id="t-1", keep_frames=0, ticket_id=tid
        )


def test_decorator_rejects_revoked_ticket(_isolated_engine):
    tid = _issue(_isolated_engine)
    _isolated_engine.revoke(ticket_id=tid, actor_id="auditor", reason="late")
    with pytest.raises(GodModeEngineError):
        truncate_replay_trace(
            recorder=_FakeRecorder(),
            trace_id="t-1",
            keep_frames=0,
            ticket_id=tid,
        )


def test_decorator_emits_success_receipt(_isolated_engine):
    tid = _issue(_isolated_engine)
    rec = _FakeRecorder()
    rec._traces["t-1"] = [{"op": "x"}, {"op": "y"}, {"op": "z"}]
    result = truncate_replay_trace(
        recorder=rec, trace_id="t-1", keep_frames=1, ticket_id=tid
    )
    assert result["dropped_frames"] == 2
    receipts = _isolated_engine.list_receipts()
    assert len(receipts) == 1
    assert receipts[0].outcome == GodReceiptOutcome.SUCCESS


def test_decorator_emits_failure_receipt_on_exception(_isolated_engine):
    tid = _issue(_isolated_engine)
    rec = _FakeRecorder()
    # No trace registered → demonstrator raises ValueError
    with pytest.raises(ValueError):
        truncate_replay_trace(
            recorder=rec, trace_id="t-missing", keep_frames=0, ticket_id=tid
        )
    receipts = _isolated_engine.list_receipts()
    assert len(receipts) == 1
    assert receipts[0].outcome == GodReceiptOutcome.FAILURE
    assert "t-missing" in receipts[0].failure_reason


def test_decorator_preserves_metadata(_isolated_engine):
    """`__god_capability__` attribute carries the (module, name) pair."""
    assert getattr(truncate_replay_trace, "__god_capability__") == (
        "replay",
        "mutate_recorder",
    )


def test_decorator_unknown_ticket(_isolated_engine):
    with pytest.raises(GodModeEngineError):
        truncate_replay_trace(
            recorder=_FakeRecorder(),
            trace_id="t-1",
            keep_frames=0,
            ticket_id="god-tkt-doesnotexist",
        )


# --- Demonstrator behavior ---


def test_demonstrator_truncates_correctly(_isolated_engine):
    tid = _issue(_isolated_engine)
    rec = _FakeRecorder()
    rec._traces["t-1"] = [{"op": str(i)} for i in range(10)]
    result = truncate_replay_trace(
        recorder=rec, trace_id="t-1", keep_frames=3, ticket_id=tid
    )
    assert result == {
        "trace_id": "t-1",
        "original_frames": 10,
        "kept_frames": 3,
        "dropped_frames": 7,
    }
    assert len(rec._traces["t-1"]) == 3


def test_demonstrator_keep_frames_exceeds_total_no_op(_isolated_engine):
    tid = _issue(_isolated_engine)
    rec = _FakeRecorder()
    rec._traces["t-1"] = [{"op": "x"}, {"op": "y"}]
    result = truncate_replay_trace(
        recorder=rec, trace_id="t-1", keep_frames=99, ticket_id=tid
    )
    assert result["dropped_frames"] == 0
    assert len(rec._traces["t-1"]) == 2


def test_demonstrator_unknown_trace_raises(_isolated_engine):
    tid = _issue(_isolated_engine)
    with pytest.raises(ValueError, match="not active"):
        truncate_replay_trace(
            recorder=_FakeRecorder(),
            trace_id="t-missing",
            keep_frames=0,
            ticket_id=tid,
        )


def test_demonstrator_negative_keep_frames_raises(_isolated_engine):
    tid = _issue(_isolated_engine)
    rec = _FakeRecorder()
    rec._traces["t-1"] = [{"op": "x"}]
    with pytest.raises(ValueError, match=">= 0"):
        truncate_replay_trace(
            recorder=rec, trace_id="t-1", keep_frames=-1, ticket_id=tid
        )


# --- New decorator instance for an inline test capability ---


def test_decorator_works_with_custom_capability(_isolated_engine):
    """Anyone can build their own god-gated callable."""

    @requires_god_ticket(module="rbac", name="impersonate_user")
    def _act_as(target: str) -> str:
        return f"acted-as:{target}"

    tid = _issue(_isolated_engine, module="rbac", name="impersonate_user")
    result = _act_as("user-42", ticket_id=tid)
    assert result == "acted-as:user-42"
    receipts = _isolated_engine.list_receipts(module="rbac")
    assert len(receipts) == 1
    assert receipts[0].outcome == GodReceiptOutcome.SUCCESS
