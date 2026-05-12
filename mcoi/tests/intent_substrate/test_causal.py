"""Tests for causal priority over ObligationRecord."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from mcoi_runtime.contracts.obligation import (
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.intent_substrate import (
    causal_priority,
    deadline_urgency,
    rank,
)

from .conftest import make_deadline, make_owner


def _far_future_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()


def _near_future_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()


def _past_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()


def _make_obligation(obligations, *, correlation_id="corr-1", deadline_iso=None):
    # trigger_ref_id must be unique per call — obligation IDs are
    # derived from (trigger, trigger_ref_id) and collisions are rejected.
    return obligations.create_obligation(
        trigger=ObligationTrigger.CUSTOM,
        trigger_ref_id=f"ref-{correlation_id}-{uuid.uuid4().hex[:8]}",
        owner=make_owner(),
        deadline=make_deadline(deadline_iso or _far_future_iso()),
        description=f"obl for {correlation_id}",
        correlation_id=correlation_id,
    )


def test_deadline_urgency_no_deadline():
    assert deadline_urgency(None) == 1.0
    assert deadline_urgency("") == 1.0


def test_deadline_urgency_past_caps_at_ten():
    assert deadline_urgency(_past_iso()) == 10.0


def test_deadline_urgency_far_future_near_one():
    u = deadline_urgency(_far_future_iso())
    assert 1.0 <= u <= 1.01


def test_deadline_urgency_near_future_high():
    u = deadline_urgency(_near_future_iso())
    assert 8.0 < u <= 10.0


def test_priority_lone_open_no_correlation_siblings():
    obligations = ObligationRuntimeEngine()
    obl = _make_obligation(obligations, correlation_id="solo")
    p = causal_priority(obl, obligations)
    # 1 (no siblings) * ~1.0 (no urgency) * 1.0 (PENDING) = ~1.0
    assert p == pytest.approx(1.0, abs=0.05)


def test_priority_grows_with_open_correlation_siblings():
    obligations = ObligationRuntimeEngine()
    root = _make_obligation(obligations, correlation_id="group")
    _make_obligation(obligations, correlation_id="group")
    _make_obligation(obligations, correlation_id="group")
    p = causal_priority(root, obligations)
    # 1 + 2 siblings = 3 base
    assert 2.9 <= p <= 3.1


def test_priority_excludes_closed_siblings():
    obligations = ObligationRuntimeEngine()
    root = _make_obligation(obligations, correlation_id="group")
    sibling = _make_obligation(obligations, correlation_id="group")
    obligations.close(
        sibling.obligation_id,
        final_state=ObligationState.COMPLETED,
        reason="done", closed_by="test",
    )
    p = causal_priority(root, obligations)
    # 1 + 0 open siblings (the only sibling is closed) = 1 base
    assert 0.95 <= p <= 1.05


def test_escalated_state_amplifies_priority():
    obligations = ObligationRuntimeEngine()
    root = _make_obligation(obligations, correlation_id="solo")
    obligations.activate(root.obligation_id)
    obligations.escalate(
        root.obligation_id,
        escalated_to=make_owner("escalator"),
        reason="overdue",
    )
    refreshed = obligations.get_obligation(root.obligation_id)
    p = causal_priority(refreshed, obligations)
    # 1 * ~1.0 * 5.0 = ~5.0
    assert 4.5 <= p <= 5.5


def test_completed_priority_is_zero():
    obligations = ObligationRuntimeEngine()
    obl = _make_obligation(obligations)
    obligations.close(
        obl.obligation_id,
        final_state=ObligationState.COMPLETED,
        reason="done", closed_by="test",
    )
    refreshed = obligations.get_obligation(obl.obligation_id)
    assert causal_priority(refreshed, obligations) == 0.0


def test_rank_orders_high_to_low():
    obligations = ObligationRuntimeEngine()
    solo = _make_obligation(obligations, correlation_id="solo")
    group_a = _make_obligation(obligations, correlation_id="group")
    _make_obligation(obligations, correlation_id="group")
    _make_obligation(obligations, correlation_id="group")
    ranked = rank([solo, group_a], obligations)
    # group_a has 2 siblings -> base 3; solo has 0 -> base 1
    assert ranked[0][0] == group_a.obligation_id
    assert ranked[1][0] == solo.obligation_id
    assert ranked[0][1] > ranked[1][1]
