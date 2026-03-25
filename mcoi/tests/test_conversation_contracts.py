"""Purpose: verify conversation thread and threaded messaging contracts.
Governance scope: conversation contract tests only.
Dependencies: conversation contracts.
Invariants: contracts reject invalid state, enforce frozen semantics.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.conversation import (
    ClarificationRequest,
    ClarificationResponse,
    ConversationThread,
    FollowUpRecord,
    MessageDirection,
    MessageType,
    StatusReport,
    ThreadMessage,
    ThreadStatus,
)


_CLOCK = "2026-03-19T00:00:00+00:00"
_CLOCK_LATER = "2026-03-19T01:00:00+00:00"


# --- ThreadMessage ---


def test_thread_message_construction() -> None:
    msg = ThreadMessage(
        message_id="msg-1",
        thread_id="thread-1",
        direction=MessageDirection.OUTBOUND,
        message_type=MessageType.REQUEST,
        content="Please review the report.",
        sender_id="agent-1",
        recipient_id="operator-1",
        sent_at=_CLOCK,
    )
    assert msg.message_id == "msg-1"
    assert msg.thread_id == "thread-1"
    assert msg.direction is MessageDirection.OUTBOUND
    assert msg.message_type is MessageType.REQUEST
    assert msg.content == "Please review the report."
    assert msg.sender_id == "agent-1"
    assert msg.recipient_id == "operator-1"
    assert msg.sent_at == _CLOCK
    assert msg.metadata == {}


def test_thread_message_with_metadata() -> None:
    msg = ThreadMessage(
        message_id="msg-2",
        thread_id="thread-1",
        direction=MessageDirection.INBOUND,
        message_type=MessageType.RESPONSE,
        content="Approved.",
        sender_id="operator-1",
        recipient_id="agent-1",
        sent_at=_CLOCK,
        metadata={"priority": "high"},
    )
    assert msg.metadata["priority"] == "high"


def test_thread_message_rejects_empty_message_id() -> None:
    with pytest.raises(ValueError, match="message_id"):
        ThreadMessage(
            message_id="",
            thread_id="thread-1",
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.REQUEST,
            content="content",
            sender_id="sender",
            recipient_id="recipient",
            sent_at=_CLOCK,
        )


def test_thread_message_rejects_empty_thread_id() -> None:
    with pytest.raises(ValueError, match="thread_id"):
        ThreadMessage(
            message_id="msg-1",
            thread_id="",
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.REQUEST,
            content="content",
            sender_id="sender",
            recipient_id="recipient",
            sent_at=_CLOCK,
        )


def test_thread_message_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="content"):
        ThreadMessage(
            message_id="msg-1",
            thread_id="thread-1",
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.REQUEST,
            content="",
            sender_id="sender",
            recipient_id="recipient",
            sent_at=_CLOCK,
        )


def test_thread_message_rejects_empty_sender_id() -> None:
    with pytest.raises(ValueError, match="sender_id"):
        ThreadMessage(
            message_id="msg-1",
            thread_id="thread-1",
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.REQUEST,
            content="content",
            sender_id="",
            recipient_id="recipient",
            sent_at=_CLOCK,
        )


def test_thread_message_rejects_empty_recipient_id() -> None:
    with pytest.raises(ValueError, match="recipient_id"):
        ThreadMessage(
            message_id="msg-1",
            thread_id="thread-1",
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.REQUEST,
            content="content",
            sender_id="sender",
            recipient_id="",
            sent_at=_CLOCK,
        )


def test_thread_message_rejects_invalid_sent_at() -> None:
    with pytest.raises(ValueError, match="sent_at"):
        ThreadMessage(
            message_id="msg-1",
            thread_id="thread-1",
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.REQUEST,
            content="content",
            sender_id="sender",
            recipient_id="recipient",
            sent_at="not-a-date",
        )


def test_thread_message_all_message_types() -> None:
    for mt in MessageType:
        msg = ThreadMessage(
            message_id=f"msg-{mt.value}",
            thread_id="thread-1",
            direction=MessageDirection.OUTBOUND,
            message_type=mt,
            content="content",
            sender_id="sender",
            recipient_id="recipient",
            sent_at=_CLOCK,
        )
        assert msg.message_type is mt


def test_thread_message_is_frozen() -> None:
    msg = ThreadMessage(
        message_id="msg-1",
        thread_id="thread-1",
        direction=MessageDirection.OUTBOUND,
        message_type=MessageType.REQUEST,
        content="content",
        sender_id="sender",
        recipient_id="recipient",
        sent_at=_CLOCK,
    )
    with pytest.raises(AttributeError):
        msg.content = "new content"  # type: ignore[misc]


def test_thread_message_serializes_to_dict() -> None:
    msg = ThreadMessage(
        message_id="msg-1",
        thread_id="thread-1",
        direction=MessageDirection.OUTBOUND,
        message_type=MessageType.REQUEST,
        content="hello",
        sender_id="s",
        recipient_id="r",
        sent_at=_CLOCK,
    )
    d = msg.to_dict()
    assert d["message_id"] == "msg-1"
    assert d["direction"] == "outbound"


# --- ConversationThread ---


def test_conversation_thread_construction() -> None:
    thread = ConversationThread(
        thread_id="thread-1",
        subject="Project review",
        status=ThreadStatus.OPEN,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    assert thread.thread_id == "thread-1"
    assert thread.subject == "Project review"
    assert thread.status is ThreadStatus.OPEN
    assert thread.messages == ()
    assert thread.goal_id is None
    assert thread.workflow_id is None


def test_conversation_thread_with_messages() -> None:
    msg = ThreadMessage(
        message_id="msg-1",
        thread_id="thread-1",
        direction=MessageDirection.OUTBOUND,
        message_type=MessageType.REQUEST,
        content="hello",
        sender_id="s",
        recipient_id="r",
        sent_at=_CLOCK,
    )
    thread = ConversationThread(
        thread_id="thread-1",
        subject="Test",
        status=ThreadStatus.ACTIVE,
        messages=(msg,),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    assert len(thread.messages) == 1
    assert thread.messages[0].message_id == "msg-1"


def test_conversation_thread_with_goal_and_workflow() -> None:
    thread = ConversationThread(
        thread_id="thread-1",
        subject="Test",
        status=ThreadStatus.OPEN,
        goal_id="goal-1",
        workflow_id="wf-1",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    assert thread.goal_id == "goal-1"
    assert thread.workflow_id == "wf-1"


def test_conversation_thread_rejects_empty_thread_id() -> None:
    with pytest.raises(ValueError, match="thread_id"):
        ConversationThread(
            thread_id="",
            subject="Test",
            status=ThreadStatus.OPEN,
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )


def test_conversation_thread_rejects_empty_subject() -> None:
    with pytest.raises(ValueError, match="subject"):
        ConversationThread(
            thread_id="thread-1",
            subject="",
            status=ThreadStatus.OPEN,
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )


def test_conversation_thread_rejects_empty_goal_id() -> None:
    with pytest.raises(ValueError, match="goal_id"):
        ConversationThread(
            thread_id="thread-1",
            subject="Test",
            status=ThreadStatus.OPEN,
            goal_id="",
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )


def test_conversation_thread_rejects_empty_workflow_id() -> None:
    with pytest.raises(ValueError, match="workflow_id"):
        ConversationThread(
            thread_id="thread-1",
            subject="Test",
            status=ThreadStatus.OPEN,
            workflow_id="  ",
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )


# --- ClarificationRequest ---


def test_clarification_request_construction() -> None:
    req = ClarificationRequest(
        request_id="clar-1",
        thread_id="thread-1",
        question="What is the target deadline?",
        context="Project review discussion",
        requested_from_id="operator-1",
        requested_at=_CLOCK,
    )
    assert req.request_id == "clar-1"
    assert req.question == "What is the target deadline?"
    assert req.response_deadline is None


def test_clarification_request_with_deadline() -> None:
    req = ClarificationRequest(
        request_id="clar-1",
        thread_id="thread-1",
        question="Confirm scope?",
        context="Scope review",
        requested_from_id="operator-1",
        requested_at=_CLOCK,
        response_deadline=_CLOCK_LATER,
    )
    assert req.response_deadline == _CLOCK_LATER


def test_clarification_request_rejects_empty_question() -> None:
    with pytest.raises(ValueError, match="question"):
        ClarificationRequest(
            request_id="clar-1",
            thread_id="thread-1",
            question="",
            context="ctx",
            requested_from_id="op-1",
            requested_at=_CLOCK,
        )


def test_clarification_request_rejects_empty_request_id() -> None:
    with pytest.raises(ValueError, match="request_id"):
        ClarificationRequest(
            request_id="",
            thread_id="thread-1",
            question="q",
            context="ctx",
            requested_from_id="op-1",
            requested_at=_CLOCK,
        )


# --- ClarificationResponse ---


def test_clarification_response_construction() -> None:
    resp = ClarificationResponse(
        request_id="clar-1",
        thread_id="thread-1",
        answer="The deadline is next Friday.",
        responded_by_id="operator-1",
        responded_at=_CLOCK_LATER,
    )
    assert resp.request_id == "clar-1"
    assert resp.answer == "The deadline is next Friday."


def test_clarification_response_rejects_empty_answer() -> None:
    with pytest.raises(ValueError, match="answer"):
        ClarificationResponse(
            request_id="clar-1",
            thread_id="thread-1",
            answer="",
            responded_by_id="op-1",
            responded_at=_CLOCK_LATER,
        )


def test_clarification_response_rejects_empty_responded_by_id() -> None:
    with pytest.raises(ValueError, match="responded_by_id"):
        ClarificationResponse(
            request_id="clar-1",
            thread_id="thread-1",
            answer="yes",
            responded_by_id="",
            responded_at=_CLOCK_LATER,
        )


# --- FollowUpRecord ---


def test_follow_up_record_construction() -> None:
    rec = FollowUpRecord(
        follow_up_id="fu-1",
        thread_id="thread-1",
        reason="Check status after 24h",
        scheduled_at=_CLOCK_LATER,
    )
    assert rec.follow_up_id == "fu-1"
    assert rec.resolved is False
    assert rec.executed_at is None


def test_follow_up_record_with_execution() -> None:
    rec = FollowUpRecord(
        follow_up_id="fu-1",
        thread_id="thread-1",
        reason="Re-check",
        scheduled_at=_CLOCK,
        executed_at=_CLOCK_LATER,
        resolved=True,
    )
    assert rec.executed_at == _CLOCK_LATER
    assert rec.resolved is True


def test_follow_up_record_rejects_empty_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        FollowUpRecord(
            follow_up_id="fu-1",
            thread_id="thread-1",
            reason="",
            scheduled_at=_CLOCK,
        )


def test_follow_up_record_rejects_empty_follow_up_id() -> None:
    with pytest.raises(ValueError, match="follow_up_id"):
        FollowUpRecord(
            follow_up_id="",
            thread_id="thread-1",
            reason="reason",
            scheduled_at=_CLOCK,
        )


def test_follow_up_record_rejects_invalid_scheduled_at() -> None:
    with pytest.raises(ValueError, match="scheduled_at"):
        FollowUpRecord(
            follow_up_id="fu-1",
            thread_id="thread-1",
            reason="reason",
            scheduled_at="bad-date",
        )


# --- StatusReport ---


def test_status_report_construction() -> None:
    report = StatusReport(
        report_id="rpt-1",
        thread_id="thread-1",
        goal_id="goal-1",
        summary="On track, 75% complete.",
        progress_pct=75,
        reported_at=_CLOCK,
    )
    assert report.report_id == "rpt-1"
    assert report.progress_pct == 75
    assert report.goal_id == "goal-1"


def test_status_report_without_goal() -> None:
    report = StatusReport(
        report_id="rpt-2",
        thread_id="thread-1",
        goal_id=None,
        summary="General update.",
        progress_pct=50,
        reported_at=_CLOCK,
    )
    assert report.goal_id is None


def test_status_report_progress_zero() -> None:
    report = StatusReport(
        report_id="rpt-3",
        thread_id="thread-1",
        goal_id=None,
        summary="Just started.",
        progress_pct=0,
        reported_at=_CLOCK,
    )
    assert report.progress_pct == 0


def test_status_report_progress_hundred() -> None:
    report = StatusReport(
        report_id="rpt-4",
        thread_id="thread-1",
        goal_id=None,
        summary="Complete.",
        progress_pct=100,
        reported_at=_CLOCK,
    )
    assert report.progress_pct == 100


def test_status_report_rejects_progress_below_zero() -> None:
    with pytest.raises(ValueError, match="progress_pct"):
        StatusReport(
            report_id="rpt-5",
            thread_id="thread-1",
            goal_id=None,
            summary="Bad.",
            progress_pct=-1,
            reported_at=_CLOCK,
        )


def test_status_report_rejects_progress_above_hundred() -> None:
    with pytest.raises(ValueError, match="progress_pct"):
        StatusReport(
            report_id="rpt-6",
            thread_id="thread-1",
            goal_id=None,
            summary="Bad.",
            progress_pct=101,
            reported_at=_CLOCK,
        )


def test_status_report_rejects_empty_summary() -> None:
    with pytest.raises(ValueError, match="summary"):
        StatusReport(
            report_id="rpt-7",
            thread_id="thread-1",
            goal_id=None,
            summary="",
            progress_pct=50,
            reported_at=_CLOCK,
        )


def test_status_report_rejects_empty_report_id() -> None:
    with pytest.raises(ValueError, match="report_id"):
        StatusReport(
            report_id="",
            thread_id="thread-1",
            goal_id=None,
            summary="Summary.",
            progress_pct=50,
            reported_at=_CLOCK,
        )


def test_status_report_rejects_empty_goal_id() -> None:
    with pytest.raises(ValueError, match="goal_id"):
        StatusReport(
            report_id="rpt-8",
            thread_id="thread-1",
            goal_id="",
            summary="Summary.",
            progress_pct=50,
            reported_at=_CLOCK,
        )


# --- StrEnum values ---


def test_thread_status_values() -> None:
    assert set(ThreadStatus) == {
        ThreadStatus.OPEN,
        ThreadStatus.ACTIVE,
        ThreadStatus.WAITING,
        ThreadStatus.RESOLVED,
        ThreadStatus.CLOSED,
    }


def test_message_direction_values() -> None:
    assert set(MessageDirection) == {MessageDirection.OUTBOUND, MessageDirection.INBOUND}


def test_message_type_values() -> None:
    assert set(MessageType) == {
        MessageType.REQUEST,
        MessageType.RESPONSE,
        MessageType.CLARIFICATION_REQUEST,
        MessageType.CLARIFICATION_RESPONSE,
        MessageType.STATUS_UPDATE,
        MessageType.FOLLOW_UP,
    }
