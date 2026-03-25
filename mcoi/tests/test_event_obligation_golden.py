"""Purpose: golden scenario tests for event spine + obligation runtime integration.
Governance scope: cross-plane integration tests only.
Tests:
  1. Approval request creates obligation for approver
  2. Unanswered thread creates follow-up obligation
  3. Incident escalation transfers obligation to new owner
  4. Job reassignment preserves obligation history
  5. Obligation closure emits event and updates spine
  6. Expired obligation triggers escalation chain
  7. Correlated events reconstruct a full causal timeline for one job
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import (
    EventRecord,
    EventSource,
    EventSubscription,
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


def _deadline(did: str = "dl-1", due: str = _DUE) -> ObligationDeadline:
    return ObligationDeadline(deadline_id=did, due_at=due, warn_at=_WARN)


def _event(
    eid: str, etype: EventType, source: EventSource,
    corr: str = "corr-1",
) -> EventRecord:
    return EventRecord(
        event_id=eid, event_type=etype, source=source,
        correlation_id=corr, payload={"detail": "test"},
        emitted_at=_CLOCK,
    )


# ---------------------------------------------------------------------------
# 1. Approval request creates obligation for approver
# ---------------------------------------------------------------------------

class TestApprovalCreatesObligation:
    def test_approval_request_to_obligation(self) -> None:
        spine = _spine()
        obl_eng = _obl_engine()

        # Emit approval-requested event
        evt = _event("evt-apr-1", EventType.APPROVAL_REQUESTED, EventSource.APPROVAL_SYSTEM)
        spine.emit(evt)

        # Process event into obligation
        obl, obl_evt = EventObligationBridge.process_event(
            spine, obl_eng, evt,
            owner=_owner("reviewer-1"),
            deadline=_deadline(),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            description="Respond to approval request apr-1",
        )

        assert obl.state == ObligationState.PENDING
        assert obl.trigger == ObligationTrigger.APPROVAL_REQUEST
        assert obl.owner.owner_id == "reviewer-1"
        assert obl_evt.event_type == EventType.OBLIGATION_CREATED
        assert spine.event_count == 2  # original + obligation-created


# ---------------------------------------------------------------------------
# 2. Unanswered thread creates follow-up obligation
# ---------------------------------------------------------------------------

class TestUnansweredThreadFollowUp:
    def test_communication_timeout_creates_obligation(self) -> None:
        spine = _spine()
        obl_eng = _obl_engine()

        # Communication sent
        sent = _event("evt-msg-1", EventType.COMMUNICATION_SENT,
                       EventSource.COMMUNICATION_SYSTEM, corr="thread-1")
        spine.emit(sent)

        # Timeout event
        timeout = _event("evt-timeout-1", EventType.COMMUNICATION_TIMED_OUT,
                          EventSource.COMMUNICATION_SYSTEM, corr="thread-1")
        spine.emit(timeout)

        # Create follow-up obligation
        obl, obl_evt = EventObligationBridge.process_event(
            spine, obl_eng, timeout,
            owner=_owner("sender-1"),
            deadline=_deadline(),
            trigger=ObligationTrigger.COMMUNICATION_FOLLOW_UP,
            description="Follow up on unanswered thread thread-1",
        )

        assert obl.trigger == ObligationTrigger.COMMUNICATION_FOLLOW_UP
        assert obl.correlation_id == "thread-1"
        assert spine.event_count == 3


# ---------------------------------------------------------------------------
# 3. Incident escalation transfers obligation to new owner
# ---------------------------------------------------------------------------

class TestIncidentEscalationTransfer:
    def test_incident_escalation_transfers(self) -> None:
        spine = _spine()
        obl_eng = _obl_engine()

        # Incident opened -> obligation
        opened = _event("evt-inc-1", EventType.INCIDENT_OPENED,
                         EventSource.INCIDENT_SYSTEM, corr="inc-1")
        spine.emit(opened)
        obl, _ = EventObligationBridge.process_event(
            spine, obl_eng, opened,
            owner=_owner("oncall-1"),
            deadline=_deadline(),
            trigger=ObligationTrigger.INCIDENT_SLA,
            description="Resolve incident inc-1 within SLA",
        )
        obl_eng.activate(obl.obligation_id)

        # Escalation event arrives
        escalated_evt = _event("evt-inc-esc-1", EventType.INCIDENT_ESCALATED,
                                EventSource.INCIDENT_SYSTEM, corr="inc-1")
        spine.emit(escalated_evt)

        # Transfer obligation to new owner
        updated_obl, xfr_evt = EventObligationBridge.transfer_and_emit(
            spine, obl_eng, obl.obligation_id,
            to_owner=_owner("manager-1", "manager"),
            reason="incident escalated to management",
        )

        assert updated_obl.owner.owner_id == "manager-1"
        assert xfr_evt.event_type == EventType.OBLIGATION_TRANSFERRED
        assert obl_eng.transfer_count == 1


# ---------------------------------------------------------------------------
# 4. Job reassignment preserves obligation history
# ---------------------------------------------------------------------------

class TestJobReassignmentHistory:
    def test_reassignment_preserves_history(self) -> None:
        spine = _spine()
        obl_eng = _obl_engine()

        # Job assigned
        assigned = _event("evt-job-1", EventType.JOB_STATE_TRANSITION,
                           EventSource.JOB_RUNTIME, corr="job-1")
        spine.emit(assigned)
        obl, _ = EventObligationBridge.process_event(
            spine, obl_eng, assigned,
            owner=_owner("worker-a"),
            deadline=_deadline(),
            trigger=ObligationTrigger.JOB_ASSIGNMENT,
            description="Complete assigned job job-1",
        )
        obl_eng.activate(obl.obligation_id)

        # Reassign twice
        EventObligationBridge.transfer_and_emit(
            spine, obl_eng, obl.obligation_id,
            to_owner=_owner("worker-b"), reason="reassignment round 1",
        )
        EventObligationBridge.transfer_and_emit(
            spine, obl_eng, obl.obligation_id,
            to_owner=_owner("worker-c"), reason="reassignment round 2",
        )

        # History preserved
        history = obl_eng.transfer_history(obl.obligation_id)
        assert len(history) == 2
        assert history[0].from_owner.owner_id == "worker-a"
        assert history[0].to_owner.owner_id == "worker-b"
        assert history[1].from_owner.owner_id == "worker-b"
        assert history[1].to_owner.owner_id == "worker-c"


# ---------------------------------------------------------------------------
# 5. Obligation closure emits event and updates spine
# ---------------------------------------------------------------------------

class TestObligationClosureEmitsEvent:
    def test_closure_emits_event(self) -> None:
        spine = _spine()
        obl_eng = _obl_engine()

        # Create and activate
        evt = _event("evt-1", EventType.REVIEW_REQUESTED,
                      EventSource.REVIEW_SYSTEM, corr="review-1")
        spine.emit(evt)
        obl, _ = EventObligationBridge.process_event(
            spine, obl_eng, evt,
            owner=_owner("reviewer"),
            deadline=_deadline(),
            trigger=ObligationTrigger.REVIEW_REQUEST,
            description="Review runbook drift",
        )
        obl_eng.activate(obl.obligation_id)

        # Close
        closed_obl, close_evt = EventObligationBridge.close_and_emit(
            spine, obl_eng, obl.obligation_id,
            final_state=ObligationState.COMPLETED,
            reason="review approved",
            closed_by="reviewer",
        )

        assert closed_obl.state == ObligationState.COMPLETED
        assert close_evt.event_type == EventType.OBLIGATION_CLOSED
        assert close_evt.correlation_id == "review-1"
        # spine has: original + obl-created + obl-closed = 3
        assert spine.event_count == 3


# ---------------------------------------------------------------------------
# 6. Expired obligation triggers escalation chain
# ---------------------------------------------------------------------------

class TestExpiredObligationEscalation:
    def test_expired_triggers_escalation(self) -> None:
        spine = _spine()
        obl_eng = _obl_engine()

        # Create obligation with past deadline
        evt = _event("evt-1", EventType.APPROVAL_REQUESTED,
                      EventSource.APPROVAL_SYSTEM, corr="apr-2")
        spine.emit(evt)
        obl, _ = EventObligationBridge.process_event(
            spine, obl_eng, evt,
            owner=_owner("approver"),
            deadline=ObligationDeadline(deadline_id="dl-past", due_at=_PAST),
            trigger=ObligationTrigger.APPROVAL_REQUEST,
            description="Respond to approval",
        )
        obl_eng.activate(obl.obligation_id)

        # Check for expired
        expired = EventObligationBridge.check_expired_obligations(
            obl_eng, current_time=_CLOCK,
        )
        assert len(expired) == 1
        assert expired[0].obligation_id == obl.obligation_id

        # Escalate the expired obligation
        esc_obl, esc_evt = EventObligationBridge.escalate_and_emit(
            spine, obl_eng, obl.obligation_id,
            escalated_to=_owner("manager"),
            reason="deadline breach — approval not received",
            severity="critical",
        )

        assert esc_obl.state == ObligationState.ESCALATED
        assert esc_obl.owner.owner_id == "manager"
        assert esc_evt.event_type == EventType.OBLIGATION_ESCALATED

        # Now close as expired
        final_obl, exp_evt = EventObligationBridge.close_and_emit(
            spine, obl_eng, obl.obligation_id,
            final_state=ObligationState.EXPIRED,
            reason="deadline passed, escalation sent",
            closed_by="system",
        )
        assert final_obl.state == ObligationState.EXPIRED
        assert exp_evt.event_type == EventType.OBLIGATION_EXPIRED


# ---------------------------------------------------------------------------
# 7. Correlated events reconstruct full causal timeline for one job
# ---------------------------------------------------------------------------

class TestCausalTimeline:
    def test_full_job_timeline(self) -> None:
        spine = _spine()
        obl_eng = _obl_engine()
        corr = "job-42"

        # 1. Job state transition: pending -> running
        e1 = _event("evt-j1", EventType.JOB_STATE_TRANSITION,
                      EventSource.JOB_RUNTIME, corr=corr)
        spine.emit(e1)

        # 2. Create obligation
        obl, e2 = EventObligationBridge.process_event(
            spine, obl_eng, e1,
            owner=_owner("worker"),
            deadline=_deadline(),
            trigger=ObligationTrigger.JOB_ASSIGNMENT,
            description="Complete job-42",
        )
        obl_eng.activate(obl.obligation_id)

        # 3. Workflow stage transition
        e3 = _event("evt-j2", EventType.WORKFLOW_STAGE_TRANSITION,
                      EventSource.WORKFLOW_RUNTIME, corr=corr)
        spine.emit(e3)

        # 4. Transfer obligation
        _, e4 = EventObligationBridge.transfer_and_emit(
            spine, obl_eng, obl.obligation_id,
            to_owner=_owner("worker-b"), reason="load balancing",
        )

        # 5. Close obligation
        _, e5 = EventObligationBridge.close_and_emit(
            spine, obl_eng, obl.obligation_id,
            final_state=ObligationState.COMPLETED,
            reason="job completed successfully",
            closed_by="worker-b",
        )

        # Reconstruct timeline
        timeline = EventObligationBridge.reconstruct_timeline(spine, corr)
        assert len(timeline) == 5

        # Verify order and types
        types = [e.event_type for e in timeline]
        assert EventType.JOB_STATE_TRANSITION in types
        assert EventType.OBLIGATION_CREATED in types
        assert EventType.WORKFLOW_STAGE_TRANSITION in types
        assert EventType.OBLIGATION_TRANSFERRED in types
        assert EventType.OBLIGATION_CLOSED in types

        # Correlate
        correlation = spine.correlate(corr)
        assert correlation is not None
        assert len(correlation.event_ids) == 5
        assert correlation.root_event_id == timeline[0].event_id

        # Window
        window = spine.build_window(corr)
        assert window is not None
        assert window.event_count == 5
