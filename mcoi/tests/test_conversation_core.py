"""Purpose: verify conversation-core — thread lifecycle, messaging, clarification, follow-ups.
Governance scope: conversation engine tests only.
Dependencies: conversation engine, conversation contracts.
Invariants: thread transitions are enforced, clock is deterministic, closed threads reject mutation.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.conversation import (
    MessageDirection,
    MessageType,
    ThreadMessage,
    ThreadStatus,
)
from mcoi_runtime.core.conversation import ConversationEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


_CLOCK_T0 = "2026-03-19T00:00:00+00:00"
_CLOCK_T1 = "2026-03-19T01:00:00+00:00"
_CLOCK_T2 = "2026-03-19T02:00:00+00:00"
_CLOCK_T3 = "2026-03-19T03:00:00+00:00"
_CLOCK_T4 = "2026-03-19T04:00:00+00:00"


def _make_engine(times: list[str] | None = None) -> ConversationEngine:
    """Create engine with a deterministic clock that steps through provided times."""
    if times is None:
        times = [_CLOCK_T0, _CLOCK_T1, _CLOCK_T2, _CLOCK_T3, _CLOCK_T4]
    it = iter(times)
    return ConversationEngine(clock=lambda: next(it))


def _make_message(thread_id: str, *, msg_id: str = "msg-1") -> ThreadMessage:
    return ThreadMessage(
        message_id=msg_id,
        thread_id=thread_id,
        direction=MessageDirection.OUTBOUND,
        message_type=MessageType.REQUEST,
        content="Test message content",
        sender_id="agent-1",
        recipient_id="operator-1",
        sent_at=_CLOCK_T0,
    )


# --- Thread creation ---


def test_create_thread_returns_open_status() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Project review")
    assert thread.status is ThreadStatus.OPEN
    assert thread.subject == "Project review"
    assert thread.messages == ()
    assert thread.thread_id.startswith("thread-")
    assert thread.created_at == _CLOCK_T0
    assert thread.updated_at == _CLOCK_T0


def test_create_thread_with_goal_and_workflow() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Review", goal_id="goal-1", workflow_id="wf-1")
    assert thread.goal_id == "goal-1"
    assert thread.workflow_id == "wf-1"


def test_create_thread_without_goal_or_workflow() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Simple thread")
    assert thread.goal_id is None
    assert thread.workflow_id is None


def test_create_thread_rejects_empty_subject() -> None:
    engine = _make_engine()
    with pytest.raises(RuntimeCoreInvariantError, match="subject"):
        engine.create_thread("")


# --- Adding messages ---


def test_add_message_transitions_open_to_active() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    updated = engine.add_message(thread, msg)
    assert updated.status is ThreadStatus.ACTIVE
    assert len(updated.messages) == 1
    assert updated.messages[0].message_id == "msg-1"


def test_add_message_keeps_active_status() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg1 = _make_message(thread.thread_id, msg_id="msg-1")
    thread = engine.add_message(thread, msg1)
    assert thread.status is ThreadStatus.ACTIVE
    msg2 = _make_message(thread.thread_id, msg_id="msg-2")
    thread = engine.add_message(thread, msg2)
    assert thread.status is ThreadStatus.ACTIVE
    assert len(thread.messages) == 2


def test_add_message_updates_timestamp() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    updated = engine.add_message(thread, msg)
    assert updated.updated_at == _CLOCK_T1


def test_add_message_rejects_mismatched_thread_id() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message("wrong-thread-id")
    with pytest.raises(RuntimeCoreInvariantError, match="thread_id must match"):
        engine.add_message(thread, msg)


# --- Clarification flow ---


def test_clarification_request_transitions_to_waiting() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread, clarif = engine.request_clarification(thread, "What is the scope?", "operator-1")
    assert thread.status is ThreadStatus.WAITING
    assert clarif.question == "What is the scope?"
    assert clarif.thread_id == thread.thread_id
    assert clarif.requested_from_id == "operator-1"
    # A clarification_request message was added to the thread
    last_msg = thread.messages[-1]
    assert last_msg.message_type is MessageType.CLARIFICATION_REQUEST


def test_clarification_response_transitions_to_active() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread, clarif = engine.request_clarification(thread, "Scope?", "operator-1")
    assert thread.status is ThreadStatus.WAITING
    thread, resp = engine.respond_to_clarification(thread, clarif, "Full scope.", "operator-1")
    assert thread.status is ThreadStatus.ACTIVE
    assert resp.answer == "Full scope."
    assert resp.request_id == clarif.request_id
    # A clarification_response message was added
    last_msg = thread.messages[-1]
    assert last_msg.message_type is MessageType.CLARIFICATION_RESPONSE


def test_clarification_request_with_deadline() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    deadline = "2026-03-20T00:00:00+00:00"
    thread, clarif = engine.request_clarification(
        thread, "Confirm?", "op-1", deadline=deadline
    )
    assert clarif.response_deadline == deadline


def test_clarification_response_rejects_mismatched_thread() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread, clarif = engine.request_clarification(thread, "Q?", "op-1")

    # Create a different thread
    engine2 = _make_engine()
    other_thread = engine2.create_thread("Other")
    with pytest.raises(RuntimeCoreInvariantError, match="thread_id must match"):
        engine.respond_to_clarification(other_thread, clarif, "A", "op-1")


# --- Follow-up scheduling ---


def test_schedule_follow_up() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    follow_up = engine.schedule_follow_up(thread, "Check in 24h", _CLOCK_T2)
    assert follow_up.thread_id == thread.thread_id
    assert follow_up.reason == "Check in 24h"
    assert follow_up.scheduled_at == _CLOCK_T2
    assert follow_up.resolved is False
    assert follow_up.executed_at is None
    assert follow_up.follow_up_id.startswith("followup-")


# --- Status reports ---


def test_generate_status_report() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    report = engine.generate_status_report(thread, "goal-1", "On track.", 75)
    assert report.thread_id == thread.thread_id
    assert report.goal_id == "goal-1"
    assert report.summary == "On track."
    assert report.progress_pct == 75
    assert report.report_id.startswith("report-")


def test_generate_status_report_without_goal() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    report = engine.generate_status_report(thread, None, "General update.", 50)
    assert report.goal_id is None


def test_generate_status_report_rejects_invalid_progress() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    with pytest.raises(ValueError, match="progress_pct"):
        engine.generate_status_report(thread, None, "Bad.", -1)
    with pytest.raises(ValueError, match="progress_pct"):
        engine.generate_status_report(thread, None, "Bad.", 101)


# --- Thread resolution and closing ---


def test_resolve_thread() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    resolved = engine.resolve_thread(thread)
    assert resolved.status is ThreadStatus.RESOLVED


def test_close_thread() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread = engine.resolve_thread(thread)
    closed = engine.close_thread(thread)
    assert closed.status is ThreadStatus.CLOSED


def test_close_thread_rejects_non_resolved() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    assert thread.status is ThreadStatus.ACTIVE
    with pytest.raises(RuntimeCoreInvariantError, match="only resolved threads"):
        engine.close_thread(thread)


def test_close_thread_rejects_already_closed() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread = engine.resolve_thread(thread)
    thread = engine.close_thread(thread)
    with pytest.raises(RuntimeCoreInvariantError, match="already closed"):
        engine.close_thread(thread)


# --- Cannot modify closed threads ---


def test_cannot_add_message_to_closed_thread() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread = engine.resolve_thread(thread)
    thread = engine.close_thread(thread)
    with pytest.raises(RuntimeCoreInvariantError, match="closed"):
        engine.add_message(thread, _make_message(thread.thread_id, msg_id="msg-new"))


def test_cannot_request_clarification_on_closed_thread() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread = engine.resolve_thread(thread)
    thread = engine.close_thread(thread)
    with pytest.raises(RuntimeCoreInvariantError, match="closed"):
        engine.request_clarification(thread, "Q?", "op-1")


def test_cannot_schedule_follow_up_on_closed_thread() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread = engine.resolve_thread(thread)
    thread = engine.close_thread(thread)
    with pytest.raises(RuntimeCoreInvariantError, match="closed"):
        engine.schedule_follow_up(thread, "Check", _CLOCK_T3)


def test_cannot_generate_status_report_on_closed_thread() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread = engine.resolve_thread(thread)
    thread = engine.close_thread(thread)
    with pytest.raises(RuntimeCoreInvariantError, match="closed"):
        engine.generate_status_report(thread, None, "Report.", 50)


def test_cannot_resolve_closed_thread() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Test")
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    thread = engine.resolve_thread(thread)
    thread = engine.close_thread(thread)
    with pytest.raises(RuntimeCoreInvariantError, match="closed"):
        engine.resolve_thread(thread)


# --- Clock injection determinism ---


def test_clock_injection_determinism() -> None:
    fixed_time = "2026-01-01T12:00:00+00:00"
    engine = ConversationEngine(clock=lambda: fixed_time)
    thread = engine.create_thread("Deterministic test")
    assert thread.created_at == fixed_time
    assert thread.updated_at == fixed_time


def test_clock_advances_through_operations() -> None:
    times = [_CLOCK_T0, _CLOCK_T1, _CLOCK_T2, _CLOCK_T3]
    engine = _make_engine(times)
    # T0: create
    thread = engine.create_thread("Test")
    assert thread.created_at == _CLOCK_T0
    # T1: add message
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    assert thread.updated_at == _CLOCK_T1
    # T2: resolve
    thread = engine.resolve_thread(thread)
    assert thread.updated_at == _CLOCK_T2
    # T3: close
    thread = engine.close_thread(thread)
    assert thread.updated_at == _CLOCK_T3


# --- Thread linkage ---


def test_thread_linkage_to_goal() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Goal thread", goal_id="goal-42")
    assert thread.goal_id == "goal-42"


def test_thread_linkage_to_workflow() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Workflow thread", workflow_id="wf-99")
    assert thread.workflow_id == "wf-99"


def test_thread_linkage_to_both() -> None:
    engine = _make_engine()
    thread = engine.create_thread("Both", goal_id="g-1", workflow_id="wf-1")
    assert thread.goal_id == "g-1"
    assert thread.workflow_id == "wf-1"


# --- Full lifecycle ---


def test_full_thread_lifecycle() -> None:
    times = [_CLOCK_T0, _CLOCK_T1, _CLOCK_T2, _CLOCK_T3, _CLOCK_T4,
             "2026-03-19T05:00:00+00:00", "2026-03-19T06:00:00+00:00"]
    engine = _make_engine(times)

    # Create
    thread = engine.create_thread("Full lifecycle test", goal_id="goal-1")
    assert thread.status is ThreadStatus.OPEN

    # Add message -> active
    msg = _make_message(thread.thread_id)
    thread = engine.add_message(thread, msg)
    assert thread.status is ThreadStatus.ACTIVE

    # Request clarification -> waiting
    thread, clarif = engine.request_clarification(thread, "Details?", "op-1")
    assert thread.status is ThreadStatus.WAITING

    # Respond to clarification -> active
    thread, resp = engine.respond_to_clarification(thread, clarif, "Here are details.", "op-1")
    assert thread.status is ThreadStatus.ACTIVE

    # Resolve
    thread = engine.resolve_thread(thread)
    assert thread.status is ThreadStatus.RESOLVED

    # Close
    thread = engine.close_thread(thread)
    assert thread.status is ThreadStatus.CLOSED
    assert len(thread.messages) == 3  # original + clarification_request + clarification_response
