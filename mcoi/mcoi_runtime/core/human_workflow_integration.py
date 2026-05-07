"""Purpose: human workflow runtime integration bridge.
Governance scope: composing human workflow runtime with change requests,
    case reviews, regulatory submissions, procurement, service requests,
    executive decisions; memory mesh and operational graph attachment.
Dependencies: human_workflow engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every human workflow action emits events.
  - Workflow state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.human_workflow import (
    ApprovalMode,
    CollaborationScope,
    ReviewMode,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .human_workflow import HumanWorkflowEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-hint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class HumanWorkflowIntegration:
    """Integration bridge for human workflow runtime with platform layers."""

    def __init__(
        self,
        workflow_engine: HumanWorkflowEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(workflow_engine, HumanWorkflowEngine):
            raise RuntimeCoreInvariantError(
                "workflow_engine must be a HumanWorkflowEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._workflow = workflow_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Workflow creation helpers
    # ------------------------------------------------------------------

    def workflow_from_change_request(
        self,
        board_id: str,
        tenant_id: str,
        change_ref: str,
        *,
        approval_mode: ApprovalMode = ApprovalMode.QUORUM,
        quorum_required: int = 2,
    ) -> dict[str, Any]:
        """Create an approval board for a change request."""
        board = self._workflow.create_approval_board(
            board_id, tenant_id,
            "Change approval",
            approval_mode=approval_mode,
            quorum_required=quorum_required,
            scope=CollaborationScope.CHANGE,
            scope_ref_id=change_ref,
        )
        _emit(self._events, "workflow_from_change_request", {
            "board_id": board_id, "change_ref": change_ref,
        }, board_id)
        return {
            "board_id": board.board_id,
            "tenant_id": board.tenant_id,
            "change_ref": change_ref,
            "approval_mode": board.approval_mode.value,
            "scope": board.scope.value,
            "source_type": "change_request",
        }

    def workflow_from_case_review(
        self,
        packet_id: str,
        tenant_id: str,
        case_ref: str,
        *,
        review_mode: ReviewMode = ReviewMode.PARALLEL,
    ) -> dict[str, Any]:
        """Create a review packet for case evidence review."""
        packet = self._workflow.create_review_packet(
            packet_id, tenant_id,
            scope=CollaborationScope.CASE,
            scope_ref_id=case_ref,
            review_mode=review_mode,
            title="Case review",
        )
        _emit(self._events, "workflow_from_case_review", {
            "packet_id": packet_id, "case_ref": case_ref,
        }, packet_id)
        return {
            "packet_id": packet.packet_id,
            "tenant_id": packet.tenant_id,
            "case_ref": case_ref,
            "review_mode": packet.review_mode.value,
            "scope": packet.scope.value,
            "source_type": "case_review",
        }

    def workflow_from_regulatory_submission(
        self,
        packet_id: str,
        tenant_id: str,
        submission_ref: str,
        *,
        review_mode: ReviewMode = ReviewMode.SEQUENTIAL,
    ) -> dict[str, Any]:
        """Create a review packet for regulatory submission."""
        packet = self._workflow.create_review_packet(
            packet_id, tenant_id,
            scope=CollaborationScope.REGULATORY,
            scope_ref_id=submission_ref,
            review_mode=review_mode,
            title="Regulatory review",
        )
        _emit(self._events, "workflow_from_regulatory_submission", {
            "packet_id": packet_id, "submission_ref": submission_ref,
        }, packet_id)
        return {
            "packet_id": packet.packet_id,
            "tenant_id": packet.tenant_id,
            "submission_ref": submission_ref,
            "review_mode": packet.review_mode.value,
            "scope": packet.scope.value,
            "source_type": "regulatory_submission",
        }

    def workflow_from_procurement_request(
        self,
        board_id: str,
        tenant_id: str,
        procurement_ref: str,
        *,
        approval_mode: ApprovalMode = ApprovalMode.QUORUM,
        quorum_required: int = 2,
    ) -> dict[str, Any]:
        """Create an approval board for procurement request."""
        board = self._workflow.create_approval_board(
            board_id, tenant_id,
            "Procurement approval",
            approval_mode=approval_mode,
            quorum_required=quorum_required,
            scope=CollaborationScope.PROCUREMENT,
            scope_ref_id=procurement_ref,
        )
        _emit(self._events, "workflow_from_procurement_request", {
            "board_id": board_id, "procurement_ref": procurement_ref,
        }, board_id)
        return {
            "board_id": board.board_id,
            "tenant_id": board.tenant_id,
            "procurement_ref": procurement_ref,
            "approval_mode": board.approval_mode.value,
            "scope": board.scope.value,
            "source_type": "procurement_request",
        }

    def workflow_from_service_request(
        self,
        handoff_id: str,
        tenant_id: str,
        service_ref: str,
        *,
        to_ref: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        """Create a handoff for service request human processing."""
        handoff = self._workflow.handoff_to_human(
            handoff_id, tenant_id,
            scope=CollaborationScope.SERVICE,
            scope_ref_id=service_ref,
            to_ref=to_ref or "service_team",
            reason=reason or "Service request requires human action",
        )
        _emit(self._events, "workflow_from_service_request", {
            "handoff_id": handoff_id, "service_ref": service_ref,
        }, handoff_id)
        return {
            "handoff_id": handoff.handoff_id,
            "tenant_id": handoff.tenant_id,
            "service_ref": service_ref,
            "direction": handoff.direction,
            "scope": handoff.scope.value,
            "source_type": "service_request",
        }

    def workflow_from_executive_decision(
        self,
        board_id: str,
        tenant_id: str,
        directive_ref: str,
        *,
        approval_mode: ApprovalMode = ApprovalMode.OVERRIDE,
        quorum_required: int = 1,
    ) -> dict[str, Any]:
        """Create an override board for executive decisions."""
        board = self._workflow.create_approval_board(
            board_id, tenant_id,
            "Executive decision",
            approval_mode=approval_mode,
            quorum_required=quorum_required,
            scope=CollaborationScope.EXECUTIVE,
            scope_ref_id=directive_ref,
        )
        _emit(self._events, "workflow_from_executive_decision", {
            "board_id": board_id, "directive_ref": directive_ref,
        }, board_id)
        return {
            "board_id": board.board_id,
            "tenant_id": board.tenant_id,
            "directive_ref": directive_ref,
            "approval_mode": board.approval_mode.value,
            "scope": board.scope.value,
            "source_type": "executive_decision",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_human_workflow_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist human workflow state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_tasks": self._workflow.task_count,
            "total_review_packets": self._workflow.review_packet_count,
            "total_boards": self._workflow.board_count,
            "total_members": self._workflow.member_count,
            "total_votes": self._workflow.vote_count,
            "total_decisions": self._workflow.decision_count,
            "total_handoffs": self._workflow.handoff_count,
            "total_violations": self._workflow.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-hwf", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Human workflow state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("human_workflow", "approvals", "collaboration"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "human_workflow_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_human_workflow_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return human workflow state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_tasks": self._workflow.task_count,
            "total_review_packets": self._workflow.review_packet_count,
            "total_boards": self._workflow.board_count,
            "total_members": self._workflow.member_count,
            "total_votes": self._workflow.vote_count,
            "total_decisions": self._workflow.decision_count,
            "total_handoffs": self._workflow.handoff_count,
            "total_violations": self._workflow.violation_count,
        }
