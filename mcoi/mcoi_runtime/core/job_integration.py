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

from mcoi_runtime.contracts.conversation import (
    ClarificationRequest,
    ClarificationResponse,
    ConversationThread,
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
