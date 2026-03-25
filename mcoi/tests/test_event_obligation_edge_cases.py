"""Purpose: edge case tests for event-obligation integration bridge.
Governance scope: cross-plane integration edge cases and error paths.
Dependencies: event spine engine, obligation runtime engine, bridge.
Invariants: bridge methods handle edge cases gracefully with clear errors.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import (
    EventRecord,
    EventSource,
    EventType,
)
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.core.event_obligation_integration import EventObligationBridge
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

_CLOCK = "2026-03-20T12:00:00+00:00"
_DUE = "2026-03-21T12:00:00+00:00"
_WARN = "2026-03-21T06:00:00+00:00"
_PAST = "2026-03-19T00:00:00+00:00"
_CLOCK_FN = lambda: _CLOCK  # noqa: E731


def _spine() -> EventSpineEngine:
    return EventSpineEngine(clock=_CLOCK_FN)


def _obl_engine() -> ObligationRuntimeEngine:
    return ObligationRuntimeEngine(clock=_CLOCK_FN)


def _owner(oid: str = "agent-1", otype: str = "agent") -> ObligationOwner:
    return ObligationOwner(owner_id=oid, owner_type=otype, display_name=f"Owner {oid}")


def _deadline(due: str = _DUE, warn: str = _WARN, did: str = "dl-1") -> ObligationDeadline:
    return ObligationDeadline(deadline_id=did, due_at=due, warn_at=warn)


def _event(eid: str = "evt-1", etype: EventType = EventType.APPROVAL_REQUESTED) -> EventRecord:
    return EventRecord(
        event_id=eid,
        event_type=etype,
        source=EventSource.APPROVAL_SYSTEM,
        correlation_id="corr-1",
        payload={"detail": "test"},
        emitted_at=_CLOCK,
    )


# --- close_and_emit edge cases ---


class TestCloseAndEmitEdgeCases:
    def test_close_already_completed_raises(self) -> None:
        """Closing an already-completed obligation must fail."""
        spine, eng = _spine(), _obl_engine()
        obl, _ = EventObligationBridge.process_event(
            spine, eng, _event(),
            owner=_owner(), deadline=_deadline(),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            description="test obligation",
        )
        eng.activate(obl.obligation_id)
        EventObligationBridge.close_and_emit(
            spine, eng, obl.obligation_id,
            final_state=ObligationState.COMPLETED,
            reason="done", closed_by="agent-1",
        )
        with pytest.raises(ValueError):
            EventObligationBridge.close_and_emit(
                spine, eng, obl.obligation_id,
                final_state=ObligationState.COMPLETED,
                reason="duplicate close", closed_by="agent-1",
            )

    def test_close_expired_emits_expired_event_type(self) -> None:
        """Closing with EXPIRED state emits OBLIGATION_EXPIRED, not CLOSED."""
        spine, eng = _spine(), _obl_engine()
        obl, _ = EventObligationBridge.process_event(
            spine, eng, _event(),
            owner=_owner(), deadline=_deadline(),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            description="test",
        )
        eng.activate(obl.obligation_id)
        _, evt = EventObligationBridge.close_and_emit(
            spine, eng, obl.obligation_id,
            final_state=ObligationState.EXPIRED,
            reason="deadline passed", closed_by="system",
        )
        assert evt.event_type == EventType.OBLIGATION_EXPIRED

    def test_close_cancelled_emits_closed_event_type(self) -> None:
        """Closing with CANCELLED state emits OBLIGATION_CLOSED."""
        spine, eng = _spine(), _obl_engine()
        obl, _ = EventObligationBridge.process_event(
            spine, eng, _event(eid="evt-cancel"),
            owner=_owner(), deadline=_deadline(),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            description="test",
        )
        eng.activate(obl.obligation_id)
        _, evt = EventObligationBridge.close_and_emit(
            spine, eng, obl.obligation_id,
            final_state=ObligationState.CANCELLED,
            reason="no longer needed", closed_by="operator",
        )
        assert evt.event_type == EventType.OBLIGATION_CLOSED


# --- transfer_and_emit edge cases ---


class TestTransferAndEmitEdgeCases:
    def test_transfer_to_same_owner_raises(self) -> None:
        """Transferring to the same owner must fail."""
        spine, eng = _spine(), _obl_engine()
        owner = _owner()
        obl, _ = EventObligationBridge.process_event(
            spine, eng, _event(eid="evt-transfer"),
            owner=owner, deadline=_deadline(),
            trigger=ObligationTrigger.ESCALATION_ACK,
            description="test",
        )
        eng.activate(obl.obligation_id)
        with pytest.raises(ValueError):
            EventObligationBridge.transfer_and_emit(
                spine, eng, obl.obligation_id,
                to_owner=owner, reason="self transfer",
            )

    def test_multiple_transfers_preserve_history(self) -> None:
        """Transferring multiple times builds a full history."""
        spine, eng = _spine(), _obl_engine()
        obl, _ = EventObligationBridge.process_event(
            spine, eng, _event(eid="evt-multi-t"),
            owner=_owner("a1"), deadline=_deadline(),
            trigger=ObligationTrigger.ESCALATION_ACK,
            description="test",
        )
        eng.activate(obl.obligation_id)

        EventObligationBridge.transfer_and_emit(
            spine, eng, obl.obligation_id,
            to_owner=_owner("a2"), reason="first transfer",
        )
        EventObligationBridge.transfer_and_emit(
            spine, eng, obl.obligation_id,
            to_owner=_owner("a3"), reason="second transfer",
        )

        history = eng.transfer_history(obl.obligation_id)
        assert len(history) == 2
        assert history[0].to_owner.owner_id == "a2"
        assert history[1].to_owner.owner_id == "a3"


# --- escalate_and_emit edge cases ---


class TestEscalateAndEmitEdgeCases:
    def test_multiple_escalations_chain(self) -> None:
        """Multiple escalations stack correctly."""
        spine, eng = _spine(), _obl_engine()
        obl, _ = EventObligationBridge.process_event(
            spine, eng, _event(eid="evt-esc-chain"),
            owner=_owner("a1"), deadline=_deadline(),
            trigger=ObligationTrigger.ESCALATION_ACK,
            description="test",
        )
        eng.activate(obl.obligation_id)

        EventObligationBridge.escalate_and_emit(
            spine, eng, obl.obligation_id,
            escalated_to=_owner("mgr-1"), reason="timeout", severity="medium",
        )
        EventObligationBridge.escalate_and_emit(
            spine, eng, obl.obligation_id,
            escalated_to=_owner("dir-1"), reason="still unresolved", severity="high",
        )

        esc_history = eng.escalation_history(obl.obligation_id)
        assert len(esc_history) == 2
        assert esc_history[0].escalated_to.owner_id == "mgr-1"
        assert esc_history[1].escalated_to.owner_id == "dir-1"


# --- check_expired_obligations edge cases ---


class TestCheckExpiredEdgeCases:
    def test_no_obligations_returns_empty(self) -> None:
        """Empty engine returns no expired obligations."""
        eng = _obl_engine()
        result = EventObligationBridge.check_expired_obligations(eng, current_time=_CLOCK)
        assert result == ()

    def test_all_fulfilled_returns_empty(self) -> None:
        """Completed obligations are not returned as expired."""
        spine, eng = _spine(), _obl_engine()
        obl, _ = EventObligationBridge.process_event(
            spine, eng, _event(eid="evt-fulfilled"),
            owner=_owner(), deadline=_deadline(due=_PAST),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            description="test",
        )
        eng.activate(obl.obligation_id)
        eng.close(obl.obligation_id, final_state=ObligationState.COMPLETED,
                  reason="done", closed_by="agent")

        result = EventObligationBridge.check_expired_obligations(eng, current_time=_CLOCK)
        assert result == ()

    def test_pending_with_past_deadline_is_expired(self) -> None:
        """Pending obligations with past deadlines are detected."""
        spine, eng = _spine(), _obl_engine()
        obl, _ = EventObligationBridge.process_event(
            spine, eng, _event(eid="evt-pending-exp"),
            owner=_owner(), deadline=_deadline(due=_PAST, warn=_PAST),
            trigger=ObligationTrigger.COMMUNICATION_FOLLOW_UP,
            description="test",
        )
        # Leave in PENDING state (don't activate)
        result = EventObligationBridge.check_expired_obligations(eng, current_time=_CLOCK)
        assert len(result) == 1
        assert result[0].obligation_id == obl.obligation_id


# --- reconstruct_timeline edge cases ---


class TestReconstructTimelineEdgeCases:
    def test_empty_correlation_returns_empty(self) -> None:
        """Non-existent correlation_id returns empty timeline."""
        spine = _spine()
        result = EventObligationBridge.reconstruct_timeline(spine, "nonexistent-corr")
        assert result == ()

    def test_timeline_preserves_order(self) -> None:
        """Events in timeline are ordered by emission."""
        spine = _spine()
        corr = "ordered-corr"

        for i in range(3):
            spine.emit(EventRecord(
                event_id=f"ord-{i}",
                event_type=EventType.JOB_STATE_TRANSITION,
                source=EventSource.JOB_RUNTIME,
                correlation_id=corr,
                payload={"seq": i},
                emitted_at=_CLOCK,
            ))

        timeline = EventObligationBridge.reconstruct_timeline(spine, corr)
        assert len(timeline) == 3
        for i, evt in enumerate(timeline):
            assert evt.event_id == f"ord-{i}"


# --- process_event edge cases ---


class TestProcessEventEdgeCases:
    def test_process_event_returns_consistent_correlation(self) -> None:
        """Obligation created from event shares the same correlation_id."""
        spine, eng = _spine(), _obl_engine()
        event = _event(eid="evt-corr-check")
        obl, obl_evt = EventObligationBridge.process_event(
            spine, eng, event,
            owner=_owner(), deadline=_deadline(),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            description="test correlation",
        )
        assert obl.correlation_id == event.correlation_id
        assert obl_evt.correlation_id == event.correlation_id

    def test_duplicate_process_events_create_separate_obligations(self) -> None:
        """Processing different events creates distinct obligations."""
        spine, eng = _spine(), _obl_engine()
        obl1, _ = EventObligationBridge.process_event(
            spine, eng, _event(eid="evt-dup-1"),
            owner=_owner(), deadline=_deadline(),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            description="first",
        )
        obl2, _ = EventObligationBridge.process_event(
            spine, eng, _event(eid="evt-dup-2"),
            owner=_owner(), deadline=_deadline(),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            description="second",
        )
        assert obl1.obligation_id != obl2.obligation_id
        assert eng.obligation_count == 2
