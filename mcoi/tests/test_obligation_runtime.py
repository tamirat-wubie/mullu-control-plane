"""Purpose: verify obligation runtime engine — create, activate, close, transfer,
escalate, event generation, history.
Governance scope: obligation plane engine tests only.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.obligation import (
    ObligationClosure,
    ObligationDeadline,
    ObligationEscalation,
    ObligationOwner,
    ObligationRecord,
    ObligationState,
    ObligationTransfer,
    ObligationTrigger,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine


_CLOCK = "2026-03-20T00:00:00+00:00"
_DUE = "2026-03-21T00:00:00+00:00"
_CLOCK_FN = lambda: _CLOCK  # noqa: E731


def _engine() -> ObligationRuntimeEngine:
    return ObligationRuntimeEngine(clock=_CLOCK_FN)


def _owner(oid: str = "agent-1") -> ObligationOwner:
    return ObligationOwner(owner_id=oid, owner_type="agent", display_name=f"Agent {oid}")


def _deadline(did: str = "dl-1") -> ObligationDeadline:
    return ObligationDeadline(deadline_id=did, due_at=_DUE)


def _event(eid: str = "evt-1") -> EventRecord:
    return EventRecord(
        event_id=eid, event_type=EventType.APPROVAL_REQUESTED,
        source=EventSource.APPROVAL_SYSTEM,
        correlation_id="corr-1", payload={}, emitted_at=_CLOCK,
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

class TestCreation:
    def test_create_obligation(self) -> None:
        eng = _engine()
        obl = eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            trigger_ref_id="apr-1",
            owner=_owner(),
            deadline=_deadline(),
            description="Respond to approval",
            correlation_id="corr-1",
        )
        assert obl.state == ObligationState.PENDING
        assert eng.obligation_count == 1

    def test_create_from_event(self) -> None:
        eng = _engine()
        obl = eng.create_from_event(
            _event(),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            owner=_owner(),
            deadline=_deadline(),
            description="Respond to approval request",
        )
        assert obl.trigger_ref_id == "evt-1"
        assert obl.correlation_id == "corr-1"

    def test_auto_id(self) -> None:
        eng = _engine()
        obl = eng.create_obligation(
            trigger=ObligationTrigger.JOB_ASSIGNMENT,
            trigger_ref_id="job-1",
            owner=_owner(),
            deadline=_deadline(),
            description="Complete job",
            correlation_id="corr-1",
        )
        assert obl.obligation_id.startswith("obl-")

    def test_duplicate_rejected(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="already exists") as excinfo:
            eng.create_obligation(
                obligation_id="obl-1",
                trigger=ObligationTrigger.CUSTOM,
                trigger_ref_id="x",
                owner=_owner(), deadline=_deadline(),
                description="test", correlation_id="c-1",
            )
        assert str(excinfo.value) == "obligation already exists"
        assert "obl-1" not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

class TestRetrieval:
    def test_get(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        assert eng.get_obligation("obl-1") is not None
        assert eng.get_obligation("obl-missing") is None

    def test_list_by_state(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        assert len(eng.list_obligations(state=ObligationState.PENDING)) == 1
        assert len(eng.list_obligations(state=ObligationState.ACTIVE)) == 0

    def test_list_by_owner(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner("a"), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.create_obligation(
            obligation_id="obl-2",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="y",
            owner=_owner("b"), deadline=_deadline(),
            description="test", correlation_id="c-2",
        )
        assert len(eng.list_obligations(owner_id="a")) == 1


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------

class TestActivation:
    def test_activate(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        updated = eng.activate("obl-1")
        assert updated.state == ObligationState.ACTIVE

    def test_activate_wrong_state(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.activate("obl-1")
        with pytest.raises(RuntimeCoreInvariantError, match="state mismatch") as excinfo:
            eng.activate("obl-1")
        assert str(excinfo.value) == "obligation state mismatch"
        assert "pending" not in str(excinfo.value).lower()
        assert "active" not in str(excinfo.value).lower()
        assert "obl-1" not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Closure
# ---------------------------------------------------------------------------

class TestClosure:
    def test_close_completed(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.activate("obl-1")
        closure = eng.close(
            "obl-1", final_state=ObligationState.COMPLETED,
            reason="done", closed_by="agent-1",
        )
        assert isinstance(closure, ObligationClosure)
        assert eng.get_obligation("obl-1").state == ObligationState.COMPLETED
        assert eng.open_count == 0

    def test_close_expired(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        closure = eng.close(
            "obl-1", final_state=ObligationState.EXPIRED,
            reason="deadline passed", closed_by="system",
        )
        assert closure.final_state == ObligationState.EXPIRED

    def test_close_already_closed_rejected(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.close("obl-1", final_state=ObligationState.COMPLETED,
                  reason="done", closed_by="x")
        with pytest.raises(RuntimeCoreInvariantError, match="already closed") as excinfo:
            eng.close("obl-1", final_state=ObligationState.COMPLETED,
                      reason="again", closed_by="x")
        assert str(excinfo.value) == "obligation already closed"
        assert "obl-1" not in str(excinfo.value)
        assert "completed" not in str(excinfo.value).lower()

    def test_closure_for(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.close("obl-1", final_state=ObligationState.COMPLETED,
                  reason="done", closed_by="x")
        assert eng.closure_for("obl-1") is not None
        assert eng.closure_for("obl-missing") is None


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------

class TestTransfer:
    def test_transfer(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.JOB_ASSIGNMENT,
            trigger_ref_id="job-1",
            owner=_owner("a"), deadline=_deadline(),
            description="complete job", correlation_id="c-1",
        )
        eng.activate("obl-1")
        xfr = eng.transfer("obl-1", to_owner=_owner("b"), reason="reassignment")
        assert isinstance(xfr, ObligationTransfer)
        assert eng.get_obligation("obl-1").owner.owner_id == "b"

    def test_transfer_closed_rejected(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner("a"), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.close("obl-1", final_state=ObligationState.COMPLETED,
                  reason="done", closed_by="x")
        with pytest.raises(RuntimeCoreInvariantError, match="closed") as excinfo:
            eng.transfer("obl-1", to_owner=_owner("b"), reason="test")
        assert str(excinfo.value) == "cannot transfer closed obligation"
        assert "obl-1" not in str(excinfo.value)

    def test_transfer_history(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner("a"), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.activate("obl-1")
        eng.transfer("obl-1", to_owner=_owner("b"), reason="first")
        eng.transfer("obl-1", to_owner=_owner("c"), reason="second")
        history = eng.transfer_history("obl-1")
        assert len(history) == 2


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

class TestEscalation:
    def test_escalate(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.INCIDENT_SLA,
            trigger_ref_id="inc-1",
            owner=_owner("agent"), deadline=_deadline(),
            description="resolve incident", correlation_id="c-1",
        )
        eng.activate("obl-1")
        esc = eng.escalate(
            "obl-1", escalated_to=_owner("manager"),
            reason="deadline approaching", severity="high",
        )
        assert isinstance(esc, ObligationEscalation)
        obl = eng.get_obligation("obl-1")
        assert obl.state == ObligationState.ESCALATED
        assert obl.owner.owner_id == "manager"

    def test_escalation_history(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner("a"), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.activate("obl-1")
        eng.escalate("obl-1", escalated_to=_owner("b"), reason="first")
        history = eng.escalation_history("obl-1")
        assert len(history) == 1

    def test_escalate_closed_rejected(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner("a"), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.close("obl-1", final_state=ObligationState.COMPLETED,
                  reason="done", closed_by="x")
        with pytest.raises(RuntimeCoreInvariantError, match="closed") as excinfo:
            eng.escalate("obl-1", escalated_to=_owner("b"), reason="urgent")
        assert str(excinfo.value) == "cannot escalate closed obligation"
        assert "obl-1" not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Event generation
# ---------------------------------------------------------------------------

class TestEventGeneration:
    def test_obligation_event(self) -> None:
        eng = _engine()
        obl = eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            trigger_ref_id="apr-1",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="corr-1",
        )
        evt = eng.obligation_event(obl, EventType.OBLIGATION_CREATED)
        assert isinstance(evt, EventRecord)
        assert evt.event_type == EventType.OBLIGATION_CREATED
        assert evt.source == EventSource.OBLIGATION_RUNTIME
        assert evt.correlation_id == "corr-1"

    def test_closure_event(self) -> None:
        eng = _engine()
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        eng.close("obl-1", final_state=ObligationState.COMPLETED,
                  reason="done", closed_by="x")
        obl = eng.get_obligation("obl-1")
        evt = eng.obligation_event(obl, EventType.OBLIGATION_CLOSED)
        assert evt.event_type == EventType.OBLIGATION_CLOSED


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestProperties:
    def test_counts(self) -> None:
        eng = _engine()
        assert eng.obligation_count == 0
        assert eng.open_count == 0
        eng.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="x",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="c-1",
        )
        assert eng.obligation_count == 1
        assert eng.open_count == 1
        eng.close("obl-1", final_state=ObligationState.COMPLETED,
                  reason="done", closed_by="x")
        assert eng.open_count == 0
        assert eng.closure_count == 1
