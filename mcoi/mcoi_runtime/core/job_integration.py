"""Purpose: bridge the job runtime with conversation, learning, and escalation subsystems.
Governance scope: job-to-subsystem integration logic only.
Dependencies: job contracts, job engine, conversation engine, learning engine, escalation manager.
Invariants:
  - Bridge methods are pure orchestrations; they compose existing engine calls.
  - No new state. No background work. No network.
  - Clock determinism is inherited from the underlying engines.
  - Job state transitions are delegated to JobEngine; bridges never mutate state directly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from mcoi_runtime.contracts.conversation import (
    ClarificationRequest,
    ClarificationResponse,
    ConversationThread,
    MessageDirection,
    MessageType,
    ThreadMessage,
    ThreadStatus,
)
from mcoi_runtime.contracts.job import (
    JobDescriptor,
    JobState,
    JobStatus,
    PauseReason,
)
from mcoi_runtime.contracts.knowledge_ingestion import (
    ConfidenceLevel,
    LessonRecord,
)
from mcoi_runtime.contracts.organization import (
    EscalationState,
    EscalationStep,
)
from mcoi_runtime.core.conversation import ConversationEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from mcoi_runtime.core.jobs import JobEngine, WorkQueue
from mcoi_runtime.core.learning import LearningEngine
from mcoi_runtime.core.organization import EscalationManager, OrgDirectory


# ---------------------------------------------------------------------------
# Job <-> Conversation bridge
# ---------------------------------------------------------------------------


class JobConversationBridge:
    """Bridge between job runtime and conversation engine.

    Responsibilities:
    - Create conversation threads linked to jobs
    - Pause jobs with clarification requests
    - Resume jobs when clarification responses arrive
    """

    @staticmethod
    def create_job_thread(
        job_descriptor: JobDescriptor,
        conversation_engine: ConversationEngine,
    ) -> ConversationThread:
        """Create a conversation thread bound to a job.

        The thread subject is the job name, and goal_id is taken from the
        descriptor if present.
        """
        return conversation_engine.create_thread(
            job_descriptor.name,
            goal_id=job_descriptor.goal_id if hasattr(job_descriptor, "goal_id") else None,
        )

    @staticmethod
    def pause_job_with_clarification(
        job_engine: JobEngine,
        conversation_engine: ConversationEngine,
        job_id: str,
        question: str,
        from_id: str,
        *,
        thread: ConversationThread,
    ) -> tuple[JobState, ConversationThread, ClarificationRequest]:
        """Pause a running job and issue a clarification request on its thread.

        Returns the updated job state, updated thread, and the clarification request.
        """
        # Pause the job via engine (returns tuple[JobState, JobPauseRecord])
        job_state, _pause_record = job_engine.pause_job(job_id, reason=PauseReason.AWAITING_RESPONSE)

        # Issue clarification on the thread
        updated_thread, clarification = conversation_engine.request_clarification(
            thread, question, from_id,
        )

        return job_state, updated_thread, clarification

    @staticmethod
    def resume_on_response(
        job_engine: JobEngine,
        conversation_engine: ConversationEngine,
        job_id: str,
        answer: str,
        by_id: str,
        *,
        thread: ConversationThread,
        clarification_request: ClarificationRequest,
    ) -> tuple[JobState, ConversationThread, ClarificationResponse]:
        """Resume a paused job after receiving a clarification response.

        Returns the updated job state, updated thread, and the clarification response.
        """
        # Resume the job via engine (returns tuple[JobState, JobResumeRecord])
        job_state, _resume_record = job_engine.resume_job(
            job_id, resumed_by_id=by_id, reason="clarification response received",
        )

        # Respond to clarification on the thread
        updated_thread, response = conversation_engine.respond_to_clarification(
            thread, clarification_request, answer, by_id,
        )

        return job_state, updated_thread, response

    @staticmethod
    def persist_whqr_binding_clarification_requests(
        thread: ConversationThread,
        requests: tuple[ClarificationRequest, ...],
    ) -> ConversationThread:
        """Persist WHQR binding clarification requests on a job conversation thread."""
        _ensure_thread_open_for_bridge(thread)
        if not requests:
            return thread
        messages = list(thread.messages)
        updated_at = thread.updated_at
        for request in requests:
            _ensure_whqr_binding_request(thread, request)
            messages.append(
                ThreadMessage(
                    message_id=stable_identifier(
                        "msg",
                        {
                            "thread_id": thread.thread_id,
                            "request_id": request.request_id,
                            "type": "whqr_binding_clarification_request",
                        },
                    ),
                    thread_id=thread.thread_id,
                    direction=MessageDirection.OUTBOUND,
                    message_type=MessageType.CLARIFICATION_REQUEST,
                    content=request.question,
                    sender_id="system",
                    recipient_id=request.requested_from_id,
                    sent_at=request.requested_at,
                    metadata={
                        "whqr_binding": True,
                        "clarification_request_id": request.request_id,
                        "clarification_context": request.context,
                    },
                )
            )
            updated_at = request.requested_at
        return replace(thread, messages=tuple(messages), status=ThreadStatus.WAITING, updated_at=updated_at)

    @staticmethod
    def persist_whqr_binding_clarification_response(
        conversation_engine: ConversationEngine,
        thread: ConversationThread,
        request: ClarificationRequest,
        answer: str,
        by_id: str,
    ) -> tuple[ConversationThread, ClarificationResponse]:
        """Persist one WHQR binding clarification response with replay metadata."""
        _ensure_thread_open_for_bridge(thread)
        _ensure_whqr_binding_request(thread, request)
        ensure_non_empty_text("answer", answer)
        ensure_non_empty_text("by_id", by_id)
        responded_at = conversation_engine.clock()
        response = ClarificationResponse(
            request_id=request.request_id,
            thread_id=thread.thread_id,
            answer=answer,
            responded_by_id=by_id,
            responded_at=responded_at,
        )
        message = ThreadMessage(
            message_id=stable_identifier(
                "msg",
                {
                    "thread_id": thread.thread_id,
                    "request_id": request.request_id,
                    "type": "whqr_binding_clarification_response",
                    "sent_at": responded_at,
                },
            ),
            thread_id=thread.thread_id,
            direction=MessageDirection.INBOUND,
            message_type=MessageType.CLARIFICATION_RESPONSE,
            content=answer,
            sender_id=by_id,
            recipient_id="system",
            sent_at=responded_at,
            metadata={
                "whqr_binding": True,
                "clarification_request_id": request.request_id,
            },
        )
        updated_thread = replace(
            thread,
            messages=thread.messages + (message,),
            status=ThreadStatus.ACTIVE,
            updated_at=responded_at,
        )
        return updated_thread, response

    @staticmethod
    def replay_whqr_binding_clarifications(thread: ConversationThread) -> "WHQRJobClarificationReplay":
        """Reconstruct WHQR binding clarification requests and responses from thread messages."""
        requests: list[ClarificationRequest] = []
        responses: list[ClarificationResponse] = []
        for message in thread.messages:
            if message.metadata.get("whqr_binding") is not True:
                continue
            request_id = message.metadata.get("clarification_request_id")
            if not isinstance(request_id, str) or not request_id.strip():
                raise RuntimeCoreInvariantError("WHQR binding message missing clarification_request_id")
            if message.message_type is MessageType.CLARIFICATION_REQUEST:
                context = message.metadata.get("clarification_context")
                if not isinstance(context, str) or not context.strip():
                    raise RuntimeCoreInvariantError("WHQR binding request message missing clarification_context")
                requests.append(
                    ClarificationRequest(
                        request_id=request_id,
                        thread_id=message.thread_id,
                        question=message.content,
                        context=context,
                        requested_from_id=message.recipient_id,
                        requested_at=message.sent_at,
                    )
                )
            elif message.message_type is MessageType.CLARIFICATION_RESPONSE:
                responses.append(
                    ClarificationResponse(
                        request_id=request_id,
                        thread_id=message.thread_id,
                        answer=message.content,
                        responded_by_id=message.sender_id,
                        responded_at=message.sent_at,
                    )
                )
        return WHQRJobClarificationReplay(tuple(requests), tuple(responses))


@dataclass(frozen=True, slots=True)
class WHQRJobClarificationReplay:
    """Replayable WHQR binding clarification pairs captured in a job thread."""

    requests: tuple[ClarificationRequest, ...]
    responses: tuple[ClarificationResponse, ...]

    @property
    def ready_for_binding_map(self) -> bool:
        return bool(self.requests and self.responses)


# ---------------------------------------------------------------------------
# Job <-> Learning bridge
# ---------------------------------------------------------------------------


class JobLearningBridge:
    """Bridge between job runtime and learning engine.

    Responsibilities:
    - Record lessons from job outcomes
    - Update workflow confidence based on job success/failure
    """

    @staticmethod
    def record_job_outcome(
        learning_engine: LearningEngine,
        job_id: str,
        outcome_success: bool,
        context: str,
    ) -> LessonRecord:
        """Record a lesson from a completed job outcome.

        Maps success/failure to a structured lesson in the learning engine.
        """
        outcome_label = "succeeded" if outcome_success else "failed"
        lesson_text = (
            f"Job {job_id} {outcome_label}. Context: {context}"
        )
        return learning_engine.record_lesson(
            source_id=job_id,
            context=context,
            action=f"execute-job-{job_id}",
            outcome=outcome_label,
            lesson=lesson_text,
        )

    @staticmethod
    def update_workflow_confidence(
        learning_engine: LearningEngine,
        workflow_id: str,
        success: bool,
    ) -> ConfidenceLevel:
        """Update confidence for a workflow knowledge artifact based on job outcome."""
        return learning_engine.update_confidence(
            knowledge_id=workflow_id,
            outcome_success=success,
        )


# ---------------------------------------------------------------------------
# Job <-> Escalation bridge
# ---------------------------------------------------------------------------


class JobEscalationBridge:
    """Bridge between job runtime and escalation subsystem.

    Responsibilities:
    - Trigger escalation for overdue jobs
    - Check and advance escalation chains
    """

    @staticmethod
    def escalate_overdue_job(
        job_engine: JobEngine,
        escalation_manager: EscalationManager,
        org_directory: OrgDirectory,
        job_id: str,
        chain_id: str,
    ) -> EscalationState:
        """Start an escalation chain for an overdue job.

        Pauses the job with reason=escalated, then starts the escalation chain.
        """
        # Pause the job as escalated (returns tuple[JobState, JobPauseRecord])
        _job_state, _pause_record = job_engine.pause_job(job_id, reason=PauseReason.OPERATOR_HOLD)

        # Start the escalation chain
        state = escalation_manager.start_escalation(chain_id)
        return state

    @staticmethod
    def check_and_advance_escalation(
        escalation_manager: EscalationManager,
        state: EscalationState,
        now: str,
    ) -> tuple[bool, EscalationStep | None]:
        """Check whether escalation should advance and return the result.

        Returns (should_escalate, next_step_or_None).
        Does NOT mutate the escalation state; the caller must call
        advance_escalation if should_escalate is True.
        """
        return escalation_manager.check_escalation(state, now)


def _ensure_thread_open_for_bridge(thread: ConversationThread) -> None:
    if thread.status is ThreadStatus.CLOSED:
        raise RuntimeCoreInvariantError("cannot modify a closed thread")


def _ensure_whqr_binding_request(thread: ConversationThread, request: ClarificationRequest) -> None:
    if not isinstance(request, ClarificationRequest):
        raise RuntimeCoreInvariantError("request must be a ClarificationRequest")
    if request.thread_id != thread.thread_id:
        raise RuntimeCoreInvariantError("clarification request thread_id must match thread")
    if not request.context.startswith("whqr_binding_gap "):
        raise RuntimeCoreInvariantError("clarification request must carry WHQR binding context")
