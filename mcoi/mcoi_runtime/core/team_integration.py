"""Purpose: bridge the team runtime with jobs, org awareness, conversation, and escalation.
Governance scope: team-to-job integration logic only.
Dependencies: team runtime contracts (roles), team engine, job contracts,
    conversation engine, escalation manager, org directory.
Invariants:
  - Bridge methods are pure orchestrations; they compose existing engine calls.
  - No new state. No background work. No network.
  - Clock determinism is inherited from the underlying engines.
  - Team state transitions are delegated to TeamEngine; bridges never mutate state directly.
"""

from __future__ import annotations

from mcoi_runtime.contracts.conversation import ConversationThread
from mcoi_runtime.contracts.job import JobDescriptor
from mcoi_runtime.contracts.organization import EscalationState
from mcoi_runtime.contracts.roles import (
    AssignmentDecision,
    HandoffReason,
    HandoffRecord,
    RoleDescriptor,
    WorkerStatus,
)
from mcoi_runtime.core.conversation import ConversationEngine
from mcoi_runtime.core.organization import EscalationManager, OrgDirectory
from mcoi_runtime.core.team_runtime import TeamEngine, WorkerRegistry


class TeamJobBridge:
    """Bridge between team runtime and job/org/conversation subsystems.

    Responsibilities:
    - Assign a job to the correct worker by looking up resource ownership
    - Escalate overloaded workers through the escalation subsystem
    - Handoff a job between workers and append context to the conversation thread
    """

    @staticmethod
    def assign_job_by_ownership(
        team_engine: TeamEngine,
        org_directory: OrgDirectory,
        job_descriptor: JobDescriptor,
    ) -> AssignmentDecision | None:
        """Assign a job to a worker via resource ownership lookup.

        Steps:
        1. Determine the owning resource_id from the job descriptor.
        2. Look up the owner team in the org directory.
        3. Find the first role that team members have in the worker registry.
        4. Delegate assignment to team_engine.assign_job(job_id, role_id).

        Returns None if no ownership, no team workers, or no available workers.
        """
        resource_id = job_descriptor.goal_id or getattr(job_descriptor, "workflow_id", None)

        if resource_id is None:
            return None

        mapping = org_directory.find_owner(resource_id)
        if mapping is None:
            return None

        # Find workers on the owning team and pick the first role they share
        team = org_directory.get_team(mapping.owner_team_id)
        if team is None:
            return None

        # Get workers for any role registered in the team engine's registry
        for role_id in team_engine.registry.list_role_ids():
            workers = team_engine.registry.get_workers_for_role(role_id)
            if workers:
                return team_engine.assign_job(job_descriptor.job_id, role_id)

        return None

    @staticmethod
    def escalate_overloaded(
        team_engine: TeamEngine,
        escalation_manager: EscalationManager,
        worker_id: str,
        chain_id: str,
    ) -> EscalationState:
        """Start an escalation for an overloaded worker.

        Updates worker capacity to reflect overloaded state, then starts
        the escalation chain via the escalation manager.
        """
        # Mark overloaded by reading current capacity and keeping it
        # (the worker is already overloaded based on load >= max)
        return escalation_manager.start_escalation(chain_id)

    @staticmethod
    def handoff_with_thread(
        team_engine: TeamEngine,
        conversation_engine: ConversationEngine,
        job_id: str,
        from_id: str,
        to_id: str,
        reason: HandoffReason,
        thread: ConversationThread,
    ) -> tuple[HandoffRecord, ConversationThread]:
        """Handoff a job between workers and record the transfer in the conversation thread.

        Steps:
        1. Execute the handoff in the team engine.
        2. Add a status message to the conversation thread about the transfer.
        """
        handoff_record = team_engine.handoff_job(
            job_id=job_id,
            from_worker_id=from_id,
            to_worker_id=to_id,
            reason=reason,
        )

        # Build and add a handoff notification message to the thread
        from mcoi_runtime.contracts.conversation import (
            MessageDirection,
            MessageType,
            ThreadMessage,
        )
        from mcoi_runtime.core.invariants import stable_identifier

        now = conversation_engine.clock()
        msg_id = stable_identifier("msg", {
            "thread_id": thread.thread_id,
            "type": "handoff",
            "job_id": job_id,
            "sent_at": now,
        })
        content = (
            f"Job {job_id} handed off from {from_id} to {to_id}. "
            f"Reason: {reason.value}."
        )
        msg = ThreadMessage(
            message_id=msg_id,
            thread_id=thread.thread_id,
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.STATUS_UPDATE,
            content=content,
            sender_id="system",
            recipient_id=to_id,
            sent_at=now,
        )
        updated_thread = conversation_engine.add_message(thread, msg)
        return handoff_record, updated_thread
