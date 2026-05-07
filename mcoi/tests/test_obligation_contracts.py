"""Purpose: verify obligation runtime contracts — ObligationRecord, ObligationOwner,
ObligationDeadline, ObligationClosure, ObligationTransfer, ObligationEscalation.
Governance scope: obligation plane contract tests only.
"""

from __future__ import annotations

import pytest

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


_CLOCK = "2026-03-20T00:00:00+00:00"
_DUE = "2026-03-21T00:00:00+00:00"
_WARN = "2026-03-20T18:00:00+00:00"


def _owner(oid: str = "owner-1") -> ObligationOwner:
    return ObligationOwner(owner_id=oid, owner_type="agent", display_name="Agent-1")


def _deadline(did: str = "dl-1") -> ObligationDeadline:
    return ObligationDeadline(deadline_id=did, due_at=_DUE, warn_at=_WARN)


def _obligation(oid: str = "obl-1") -> ObligationRecord:
    return ObligationRecord(
        obligation_id=oid,
        trigger=ObligationTrigger.APPROVAL_REQUEST,
        trigger_ref_id="apr-1",
        state=ObligationState.PENDING,
        owner=_owner(),
        deadline=_deadline(),
        description="Respond to approval request apr-1",
        correlation_id="corr-1",
        metadata={"priority": "high"},
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


# ---------------------------------------------------------------------------
# ObligationOwner
# ---------------------------------------------------------------------------

class TestObligationOwner:
    def test_valid(self) -> None:
        o = _owner()
        assert o.owner_id == "owner-1"
        assert o.owner_type == "agent"

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="owner_id"):
            ObligationOwner(owner_id="", owner_type="agent", display_name="A")

    def test_frozen(self) -> None:
        o = _owner()
        with pytest.raises(AttributeError):
            o.owner_id = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ObligationDeadline
# ---------------------------------------------------------------------------

class TestObligationDeadline:
    def test_valid(self) -> None:
        d = _deadline()
        assert d.hard is True
        assert d.warn_at == _WARN

    def test_without_warn(self) -> None:
        d = ObligationDeadline(deadline_id="dl-1", due_at=_DUE)
        assert d.warn_at is None

    def test_invalid_due_at_rejected(self) -> None:
        with pytest.raises(ValueError, match="due_at"):
            ObligationDeadline(deadline_id="dl-1", due_at="not-a-date")

    def test_soft_deadline(self) -> None:
        d = ObligationDeadline(deadline_id="dl-1", due_at=_DUE, hard=False)
        assert d.hard is False


# ---------------------------------------------------------------------------
# ObligationRecord
# ---------------------------------------------------------------------------

class TestObligationRecord:
    def test_valid(self) -> None:
        o = _obligation()
        assert o.obligation_id == "obl-1"
        assert o.trigger == ObligationTrigger.APPROVAL_REQUEST
        assert o.state == ObligationState.PENDING

    def test_metadata_frozen(self) -> None:
        o = _obligation()
        with pytest.raises(TypeError):
            o.metadata["new"] = "val"  # type: ignore[index]

    def test_invalid_trigger_rejected(self) -> None:
        with pytest.raises(ValueError, match="trigger"):
            ObligationRecord(
                obligation_id="obl-1",
                trigger="bad",  # type: ignore[arg-type]
                trigger_ref_id="x", state=ObligationState.PENDING,
                owner=_owner(), deadline=_deadline(),
                description="test", correlation_id="c-1",
                metadata={}, created_at=_CLOCK, updated_at=_CLOCK,
            )

    def test_invalid_state_rejected(self) -> None:
        with pytest.raises(ValueError, match="state"):
            ObligationRecord(
                obligation_id="obl-1",
                trigger=ObligationTrigger.JOB_ASSIGNMENT,
                trigger_ref_id="x", state="bad",  # type: ignore[arg-type]
                owner=_owner(), deadline=_deadline(),
                description="test", correlation_id="c-1",
                metadata={}, created_at=_CLOCK, updated_at=_CLOCK,
            )

    def test_frozen(self) -> None:
        o = _obligation()
        with pytest.raises(AttributeError):
            o.state = ObligationState.ACTIVE  # type: ignore[misc]

    def test_to_dict(self) -> None:
        d = _obligation().to_dict()
        assert d["obligation_id"] == "obl-1"
        assert isinstance(d["metadata"], dict)

    def test_all_triggers(self) -> None:
        for trigger in ObligationTrigger:
            o = ObligationRecord(
                obligation_id=f"obl-{trigger.value}",
                trigger=trigger, trigger_ref_id="ref-1",
                state=ObligationState.ACTIVE,
                owner=_owner(), deadline=_deadline(),
                description=f"test {trigger.value}",
                correlation_id="c-1", metadata={},
                created_at=_CLOCK, updated_at=_CLOCK,
            )
            assert o.trigger == trigger

    def test_all_states(self) -> None:
        for state in ObligationState:
            o = ObligationRecord(
                obligation_id=f"obl-{state.value}",
                trigger=ObligationTrigger.CUSTOM,
                trigger_ref_id="ref-1", state=state,
                owner=_owner(), deadline=_deadline(),
                description=f"test {state.value}",
                correlation_id="c-1", metadata={},
                created_at=_CLOCK, updated_at=_CLOCK,
            )
            assert o.state == state


# ---------------------------------------------------------------------------
# ObligationClosure
# ---------------------------------------------------------------------------

class TestObligationClosure:
    def test_valid_completed(self) -> None:
        c = ObligationClosure(
            closure_id="cls-1", obligation_id="obl-1",
            final_state=ObligationState.COMPLETED,
            reason="approved by reviewer",
            closed_by="reviewer-1", closed_at=_CLOCK,
        )
        assert c.final_state == ObligationState.COMPLETED

    def test_valid_expired(self) -> None:
        c = ObligationClosure(
            closure_id="cls-1", obligation_id="obl-1",
            final_state=ObligationState.EXPIRED,
            reason="deadline passed",
            closed_by="system", closed_at=_CLOCK,
        )
        assert c.final_state == ObligationState.EXPIRED

    def test_valid_cancelled(self) -> None:
        c = ObligationClosure(
            closure_id="cls-1", obligation_id="obl-1",
            final_state=ObligationState.CANCELLED,
            reason="no longer needed",
            closed_by="admin", closed_at=_CLOCK,
        )
        assert c.final_state == ObligationState.CANCELLED

    def test_invalid_final_state_rejected(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            ObligationClosure(
                closure_id="cls-1", obligation_id="obl-1",
                final_state=ObligationState.ACTIVE,
                reason="test", closed_by="x", closed_at=_CLOCK,
            )
        assert str(exc_info.value) == "final_state must be a terminal closure state"
        assert "active" not in str(exc_info.value).lower()

    def test_pending_state_rejected(self) -> None:
        with pytest.raises(ValueError, match="final_state"):
            ObligationClosure(
                closure_id="cls-1", obligation_id="obl-1",
                final_state=ObligationState.PENDING,
                reason="test", closed_by="x", closed_at=_CLOCK,
            )


# ---------------------------------------------------------------------------
# ObligationTransfer
# ---------------------------------------------------------------------------

class TestObligationTransfer:
    def test_valid(self) -> None:
        t = ObligationTransfer(
            transfer_id="tr-1", obligation_id="obl-1",
            from_owner=_owner("a"), to_owner=_owner("b"),
            reason="reassignment", transferred_at=_CLOCK,
        )
        assert t.from_owner.owner_id == "a"
        assert t.to_owner.owner_id == "b"

    def test_same_owner_rejected(self) -> None:
        with pytest.raises(ValueError, match="same owner"):
            ObligationTransfer(
                transfer_id="tr-1", obligation_id="obl-1",
                from_owner=_owner("a"), to_owner=_owner("a"),
                reason="test", transferred_at=_CLOCK,
            )

    def test_frozen(self) -> None:
        t = ObligationTransfer(
            transfer_id="tr-1", obligation_id="obl-1",
            from_owner=_owner("a"), to_owner=_owner("b"),
            reason="test", transferred_at=_CLOCK,
        )
        with pytest.raises(AttributeError):
            t.transfer_id = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ObligationEscalation
# ---------------------------------------------------------------------------

class TestObligationEscalation:
    def test_valid(self) -> None:
        e = ObligationEscalation(
            escalation_id="esc-1", obligation_id="obl-1",
            escalated_to=_owner("manager-1"),
            reason="deadline breach", severity="high",
            escalated_at=_CLOCK,
        )
        assert e.severity == "high"

    def test_empty_reason_rejected(self) -> None:
        with pytest.raises(ValueError, match="reason"):
            ObligationEscalation(
                escalation_id="esc-1", obligation_id="obl-1",
                escalated_to=_owner("m"),
                reason="", severity="high",
                escalated_at=_CLOCK,
            )

    def test_invalid_escalated_to_rejected(self) -> None:
        with pytest.raises(ValueError, match="escalated_to"):
            ObligationEscalation(
                escalation_id="esc-1", obligation_id="obl-1",
                escalated_to="not-owner",  # type: ignore[arg-type]
                reason="test", severity="high",
                escalated_at=_CLOCK,
            )
