"""Purpose: conversation-core — manage multi-turn threaded conversations.
Governance scope: threaded communication core logic only.
Dependencies: conversation contracts, invariant helpers.
Invariants:
  - Every message belongs to a thread.
  - Thread status transitions are explicit and enforced.
  - No messages may be added to closed threads.
  - Message attribution is never fabricated.
  - Clock is injected for determinism.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

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
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


class ConversationEngine:
    """Manage multi-turn threaded conversations.

    This engine:
    - Creates and tracks conversation threads
    - Adds messages with automatic status transitions
    - Manages clarification request/response flows
    - Schedules follow-ups linked to the temporal engine
    - Generates structured status reports
    - Enforces thread lifecycle invariants
    - Uses injected clock for determinism
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock

    @property
    def clock(self) -> Callable[[], str]:
        """Public accessor for the injected clock function."""
        return self._clock

    def create_thread(
        self,
        subject: str,
        *,
        goal_id: str | None = None,
        workflow_id: str | None = None,
    ) -> ConversationThread:
        """Create a new conversation thread in open status."""
        ensure_non_empty_text("subject", subject)
        now = self._clock()
        thread_id = stable_identifier("thread", {
            "subject": subject,
            "created_at": now,
        })
        return ConversationThread(
            thread_id=thread_id,
            subject=subject,
            status=ThreadStatus.OPEN,
            messages=(),
            goal_id=goal_id,
            workflow_id=workflow_id,
            created_at=now,
            updated_at=now,
        )

    def add_message(
        self,
        thread: ConversationThread,
        message: ThreadMessage,
    ) -> ConversationThread:
        """Add a message to a thread, transitioning to active if open."""
        self._ensure_not_closed(thread)
        if message.thread_id != thread.thread_id:
            raise RuntimeCoreInvariantError("message thread_id must match thread")
        new_status = thread.status
        if thread.status is ThreadStatus.OPEN:
            new_status = ThreadStatus.ACTIVE
        return replace(
            thread,
            messages=thread.messages + (message,),
            status=new_status,
            updated_at=self._clock(),
        )

    def request_clarification(
        self,
        thread: ConversationThread,
        question: str,
        from_id: str,
        *,
        deadline: str | None = None,
    ) -> tuple[ConversationThread, ClarificationRequest]:
        """Issue a clarification request, transitioning thread to waiting."""
        self._ensure_not_closed(thread)
        ensure_non_empty_text("question", question)
        ensure_non_empty_text("from_id", from_id)
        now = self._clock()
        request_id = stable_identifier("clarif", {
            "thread_id": thread.thread_id,
            "question": question,
            "requested_at": now,
        })
        clarification = ClarificationRequest(
            request_id=request_id,
            thread_id=thread.thread_id,
            question=question,
            context=thread.subject,
            requested_from_id=from_id,
            requested_at=now,
            response_deadline=deadline,
        )
        # Add the clarification as a message on the thread
        msg_id = stable_identifier("msg", {
            "thread_id": thread.thread_id,
            "type": "clarification_request",
            "sent_at": now,
        })
        msg = ThreadMessage(
            message_id=msg_id,
            thread_id=thread.thread_id,
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.CLARIFICATION_REQUEST,
            content=question,
            sender_id="system",
            recipient_id=from_id,
            sent_at=now,
        )
        updated = replace(
            thread,
            messages=thread.messages + (msg,),
            status=ThreadStatus.WAITING,
            updated_at=now,
        )
        return updated, clarification

    def respond_to_clarification(
        self,
        thread: ConversationThread,
        request: ClarificationRequest,
        answer: str,
        by_id: str,
    ) -> tuple[ConversationThread, ClarificationResponse]:
        """Respond to a clarification, transitioning thread back to active."""
        self._ensure_not_closed(thread)
        ensure_non_empty_text("answer", answer)
        ensure_non_empty_text("by_id", by_id)
        if request.thread_id != thread.thread_id:
            raise RuntimeCoreInvariantError("clarification request thread_id must match thread")
        now = self._clock()
        response = ClarificationResponse(
            request_id=request.request_id,
            thread_id=thread.thread_id,
            answer=answer,
            responded_by_id=by_id,
            responded_at=now,
        )
        msg_id = stable_identifier("msg", {
            "thread_id": thread.thread_id,
            "type": "clarification_response",
            "sent_at": now,
        })
        msg = ThreadMessage(
            message_id=msg_id,
            thread_id=thread.thread_id,
            direction=MessageDirection.INBOUND,
            message_type=MessageType.CLARIFICATION_RESPONSE,
            content=answer,
            sender_id=by_id,
            recipient_id="system",
            sent_at=now,
        )
        updated = replace(
            thread,
            messages=thread.messages + (msg,),
            status=ThreadStatus.ACTIVE,
            updated_at=now,
        )
        return updated, response

    def schedule_follow_up(
        self,
        thread: ConversationThread,
        reason: str,
        scheduled_at: str,
    ) -> FollowUpRecord:
        """Schedule a follow-up for a thread."""
        self._ensure_not_closed(thread)
        ensure_non_empty_text("reason", reason)
        follow_up_id = stable_identifier("followup", {
            "thread_id": thread.thread_id,
            "reason": reason,
            "scheduled_at": scheduled_at,
        })
        return FollowUpRecord(
            follow_up_id=follow_up_id,
            thread_id=thread.thread_id,
            reason=reason,
            scheduled_at=scheduled_at,
        )

    def generate_status_report(
        self,
        thread: ConversationThread,
        goal_id: str | None,
        summary: str,
        progress: int,
    ) -> StatusReport:
        """Generate a status report for a thread."""
        self._ensure_not_closed(thread)
        ensure_non_empty_text("summary", summary)
        now = self._clock()
        report_id = stable_identifier("report", {
            "thread_id": thread.thread_id,
            "reported_at": now,
        })
        return StatusReport(
            report_id=report_id,
            thread_id=thread.thread_id,
            goal_id=goal_id,
            summary=summary,
            progress_pct=progress,
            reported_at=now,
        )

    def close_thread(self, thread: ConversationThread) -> ConversationThread:
        """Close a resolved thread. Only resolved threads may be closed."""
        if thread.status is ThreadStatus.CLOSED:
            raise RuntimeCoreInvariantError("thread is already closed")
        if thread.status is not ThreadStatus.RESOLVED:
            raise RuntimeCoreInvariantError("only resolved threads may be closed")
        return replace(
            thread,
            status=ThreadStatus.CLOSED,
            updated_at=self._clock(),
        )

    def resolve_thread(self, thread: ConversationThread) -> ConversationThread:
        """Resolve a thread — marks objective as met."""
        self._ensure_not_closed(thread)
        return replace(
            thread,
            status=ThreadStatus.RESOLVED,
            updated_at=self._clock(),
        )

    @staticmethod
    def _ensure_not_closed(thread: ConversationThread) -> None:
        if thread.status is ThreadStatus.CLOSED:
            raise RuntimeCoreInvariantError("cannot modify a closed thread")
