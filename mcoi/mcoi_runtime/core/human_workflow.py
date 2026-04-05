"""Purpose: human workflow / approvals / collaborative review runtime engine.
Governance scope: managing human tasks, review packets, approval boards,
    board votes, collaborative decisions, handoffs, violation detection,
    and immutable snapshots.
Dependencies: human_workflow contracts, event_spine, core invariants.
Invariants:
  - Every human task references an assignee.
  - Board decisions require quorum or unanimity as configured.
  - Terminal tasks/decisions cannot be re-opened.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.human_workflow import (
    ApprovalBoard,
    ApprovalMode,
    BoardDecisionStatus,
    BoardMember,
    BoardVote,
    CollaborativeDecision,
    CollaborationScope,
    EscalationDisposition,
    HandoffPacket,
    HumanTaskRecord,
    HumanTaskStatus,
    HumanWorkflowClosureReport,
    HumanWorkflowSnapshot,
    HumanWorkflowViolation,
    ReviewMode,
    ReviewPacket,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-hwf", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_TASK_TERMINAL = frozenset({HumanTaskStatus.COMPLETED, HumanTaskStatus.CANCELLED})
_DECISION_TERMINAL = frozenset({
    BoardDecisionStatus.APPROVED,
    BoardDecisionStatus.REJECTED,
    BoardDecisionStatus.OVERRIDDEN,
})


class HumanWorkflowEngine:
    """Human workflow, approvals, and collaborative review engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._tasks: dict[str, HumanTaskRecord] = {}
        self._review_packets: dict[str, ReviewPacket] = {}
        self._boards: dict[str, ApprovalBoard] = {}
        self._members: dict[str, BoardMember] = {}
        self._votes: dict[str, BoardVote] = {}
        self._decisions: dict[str, CollaborativeDecision] = {}
        self._handoffs: dict[str, HandoffPacket] = {}
        self._violations: dict[str, HumanWorkflowViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def review_packet_count(self) -> int:
        return len(self._review_packets)

    @property
    def board_count(self) -> int:
        return len(self._boards)

    @property
    def member_count(self) -> int:
        return len(self._members)

    @property
    def vote_count(self) -> int:
        return len(self._votes)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def handoff_count(self) -> int:
        return len(self._handoffs)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Human tasks
    # ------------------------------------------------------------------

    def create_human_task(
        self,
        task_id: str,
        tenant_id: str,
        assignee_ref: str,
        *,
        scope: CollaborationScope = CollaborationScope.CHANGE,
        scope_ref_id: str = "",
        title: str = "Human task",
        description: str = "",
        due_at: str = "",
    ) -> HumanTaskRecord:
        """Create a human task."""
        if task_id in self._tasks:
            raise RuntimeCoreInvariantError("Duplicate task_id")
        now = _now_iso()
        task = HumanTaskRecord(
            task_id=task_id, tenant_id=tenant_id,
            assignee_ref=assignee_ref,
            status=HumanTaskStatus.PENDING,
            scope=scope, scope_ref_id=scope_ref_id,
            title=title, description=description,
            due_at=due_at, created_at=now,
        )
        self._tasks[task_id] = task
        _emit(self._events, "human_task_created", {
            "task_id": task_id, "assignee_ref": assignee_ref,
        }, task_id)
        return task

    def get_task(self, task_id: str) -> HumanTaskRecord:
        """Get a task by ID."""
        t = self._tasks.get(task_id)
        if t is None:
            raise RuntimeCoreInvariantError("Unknown task_id")
        return t

    def assign_task(self, task_id: str, assignee_ref: str) -> HumanTaskRecord:
        """Assign or reassign a task."""
        old = self.get_task(task_id)
        if old.status in _TASK_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot assign task in current status")
        updated = HumanTaskRecord(
            task_id=old.task_id, tenant_id=old.tenant_id,
            assignee_ref=assignee_ref,
            status=HumanTaskStatus.ASSIGNED,
            scope=old.scope, scope_ref_id=old.scope_ref_id,
            title=old.title, description=old.description,
            due_at=old.due_at, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_assigned", {
            "task_id": task_id, "assignee_ref": assignee_ref,
        }, task_id)
        return updated

    def start_task(self, task_id: str) -> HumanTaskRecord:
        """Mark a task as in progress."""
        old = self.get_task(task_id)
        if old.status in _TASK_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot start task in current status")
        updated = HumanTaskRecord(
            task_id=old.task_id, tenant_id=old.tenant_id,
            assignee_ref=old.assignee_ref,
            status=HumanTaskStatus.IN_PROGRESS,
            scope=old.scope, scope_ref_id=old.scope_ref_id,
            title=old.title, description=old.description,
            due_at=old.due_at, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_started", {"task_id": task_id}, task_id)
        return updated

    def complete_task(self, task_id: str) -> HumanTaskRecord:
        """Complete a task."""
        old = self.get_task(task_id)
        if old.status in _TASK_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot complete task in current status")
        updated = HumanTaskRecord(
            task_id=old.task_id, tenant_id=old.tenant_id,
            assignee_ref=old.assignee_ref,
            status=HumanTaskStatus.COMPLETED,
            scope=old.scope, scope_ref_id=old.scope_ref_id,
            title=old.title, description=old.description,
            due_at=old.due_at, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_completed", {"task_id": task_id}, task_id)
        return updated

    def cancel_task(self, task_id: str) -> HumanTaskRecord:
        """Cancel a task."""
        old = self.get_task(task_id)
        if old.status in _TASK_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot cancel task in current status")
        updated = HumanTaskRecord(
            task_id=old.task_id, tenant_id=old.tenant_id,
            assignee_ref=old.assignee_ref,
            status=HumanTaskStatus.CANCELLED,
            scope=old.scope, scope_ref_id=old.scope_ref_id,
            title=old.title, description=old.description,
            due_at=old.due_at, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_cancelled", {"task_id": task_id}, task_id)
        return updated

    def escalate_task(self, task_id: str, *, escalation_ref: str = "") -> HumanTaskRecord:
        """Escalate a task."""
        old = self.get_task(task_id)
        if old.status in _TASK_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot escalate task in current status")
        updated = HumanTaskRecord(
            task_id=old.task_id, tenant_id=old.tenant_id,
            assignee_ref=old.assignee_ref,
            status=HumanTaskStatus.ESCALATED,
            scope=old.scope, scope_ref_id=old.scope_ref_id,
            title=old.title, description=old.description,
            due_at=old.due_at, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_escalated", {
            "task_id": task_id, "escalation_ref": escalation_ref,
        }, task_id)
        return updated

    def tasks_for_tenant(self, tenant_id: str) -> tuple[HumanTaskRecord, ...]:
        """Return all tasks for a tenant."""
        return tuple(t for t in self._tasks.values() if t.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Review packets
    # ------------------------------------------------------------------

    def create_review_packet(
        self,
        packet_id: str,
        tenant_id: str,
        *,
        scope: CollaborationScope = CollaborationScope.CASE,
        scope_ref_id: str = "",
        review_mode: ReviewMode = ReviewMode.SINGLE,
        title: str = "Review packet",
    ) -> ReviewPacket:
        """Create a review packet."""
        if packet_id in self._review_packets:
            raise RuntimeCoreInvariantError("Duplicate packet_id")
        now = _now_iso()
        packet = ReviewPacket(
            packet_id=packet_id, tenant_id=tenant_id,
            scope=scope, scope_ref_id=scope_ref_id,
            review_mode=review_mode, title=title,
            reviewer_count=0, reviews_completed=0,
            reviews_approved=0, created_at=now,
        )
        self._review_packets[packet_id] = packet
        _emit(self._events, "review_packet_created", {
            "packet_id": packet_id, "review_mode": review_mode.value,
        }, packet_id)
        return packet

    def get_review_packet(self, packet_id: str) -> ReviewPacket:
        """Get a review packet by ID."""
        p = self._review_packets.get(packet_id)
        if p is None:
            raise RuntimeCoreInvariantError("Unknown packet_id")
        return p

    def assign_reviewer(
        self,
        packet_id: str,
        task_id: str,
        reviewer_ref: str,
        *,
        title: str = "Review task",
    ) -> HumanTaskRecord:
        """Assign a reviewer to a review packet by creating a review task."""
        packet = self.get_review_packet(packet_id)
        # Create the review task
        task = self.create_human_task(
            task_id, packet.tenant_id, reviewer_ref,
            scope=packet.scope, scope_ref_id=packet_id,
            title=title,
        )
        # Update reviewer count
        updated = ReviewPacket(
            packet_id=packet.packet_id, tenant_id=packet.tenant_id,
            scope=packet.scope, scope_ref_id=packet.scope_ref_id,
            review_mode=packet.review_mode, title=packet.title,
            reviewer_count=packet.reviewer_count + 1,
            reviews_completed=packet.reviews_completed,
            reviews_approved=packet.reviews_approved,
            created_at=packet.created_at, metadata=packet.metadata,
        )
        self._review_packets[packet_id] = updated
        _emit(self._events, "reviewer_assigned", {
            "packet_id": packet_id, "reviewer_ref": reviewer_ref,
        }, packet_id)
        return task

    def complete_review(
        self,
        packet_id: str,
        task_id: str,
        *,
        approved: bool = True,
    ) -> ReviewPacket:
        """Complete a review for a packet."""
        packet = self.get_review_packet(packet_id)
        task = self.get_task(task_id)
        if task.scope_ref_id != packet_id:
            raise RuntimeCoreInvariantError("Task is not assigned to review packet")
        # Complete the task
        self.complete_task(task_id)
        # Update packet counts
        updated = ReviewPacket(
            packet_id=packet.packet_id, tenant_id=packet.tenant_id,
            scope=packet.scope, scope_ref_id=packet.scope_ref_id,
            review_mode=packet.review_mode, title=packet.title,
            reviewer_count=packet.reviewer_count,
            reviews_completed=packet.reviews_completed + 1,
            reviews_approved=packet.reviews_approved + (1 if approved else 0),
            created_at=packet.created_at, metadata=packet.metadata,
        )
        self._review_packets[packet_id] = updated
        _emit(self._events, "review_completed", {
            "packet_id": packet_id, "task_id": task_id, "approved": approved,
        }, packet_id)
        return updated

    def review_packets_for_tenant(self, tenant_id: str) -> tuple[ReviewPacket, ...]:
        """Return all review packets for a tenant."""
        return tuple(p for p in self._review_packets.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Approval boards
    # ------------------------------------------------------------------

    def create_approval_board(
        self,
        board_id: str,
        tenant_id: str,
        name: str,
        *,
        approval_mode: ApprovalMode = ApprovalMode.SINGLE,
        quorum_required: int = 1,
        scope: CollaborationScope = CollaborationScope.CHANGE,
        scope_ref_id: str = "",
    ) -> ApprovalBoard:
        """Create an approval board."""
        if board_id in self._boards:
            raise RuntimeCoreInvariantError("Duplicate board_id")
        now = _now_iso()
        board = ApprovalBoard(
            board_id=board_id, tenant_id=tenant_id, name=name,
            approval_mode=approval_mode,
            quorum_required=quorum_required,
            scope=scope, scope_ref_id=scope_ref_id,
            member_count=0, created_at=now,
        )
        self._boards[board_id] = board
        _emit(self._events, "approval_board_created", {
            "board_id": board_id, "approval_mode": approval_mode.value,
        }, board_id)
        return board

    def get_board(self, board_id: str) -> ApprovalBoard:
        """Get a board by ID."""
        b = self._boards.get(board_id)
        if b is None:
            raise RuntimeCoreInvariantError("Unknown board_id")
        return b

    def add_board_member(
        self,
        member_id: str,
        board_id: str,
        identity_ref: str,
        *,
        role: str = "member",
    ) -> BoardMember:
        """Add a member to an approval board."""
        if member_id in self._members:
            raise RuntimeCoreInvariantError("Duplicate member_id")
        board = self.get_board(board_id)
        now = _now_iso()
        member = BoardMember(
            member_id=member_id, board_id=board_id,
            identity_ref=identity_ref, role=role,
            added_at=now,
        )
        self._members[member_id] = member
        # Update board member count
        updated_board = ApprovalBoard(
            board_id=board.board_id, tenant_id=board.tenant_id,
            name=board.name, approval_mode=board.approval_mode,
            quorum_required=board.quorum_required,
            scope=board.scope, scope_ref_id=board.scope_ref_id,
            member_count=board.member_count + 1,
            created_at=board.created_at, metadata=board.metadata,
        )
        self._boards[board_id] = updated_board
        _emit(self._events, "board_member_added", {
            "member_id": member_id, "board_id": board_id,
        }, board_id)
        return member

    def members_for_board(self, board_id: str) -> tuple[BoardMember, ...]:
        """Return all members for a board."""
        return tuple(m for m in self._members.values() if m.board_id == board_id)

    # ------------------------------------------------------------------
    # Votes
    # ------------------------------------------------------------------

    def record_vote(
        self,
        vote_id: str,
        board_id: str,
        member_id: str,
        *,
        scope_ref_id: str = "",
        approved: bool = True,
        reason: str = "",
    ) -> BoardVote:
        """Record a vote from a board member."""
        if vote_id in self._votes:
            raise RuntimeCoreInvariantError("Duplicate vote_id")
        board = self.get_board(board_id)
        member = self._members.get(member_id)
        if member is None:
            raise RuntimeCoreInvariantError("Unknown member_id")
        if member.board_id != board_id:
            raise RuntimeCoreInvariantError("Member is not assigned to approval board")
        # Check for duplicate votes by same member on same scope
        for v in self._votes.values():
            if (v.board_id == board_id and v.member_id == member_id
                    and v.scope_ref_id == scope_ref_id):
                raise RuntimeCoreInvariantError("Member already voted on scope")
        now = _now_iso()
        vote = BoardVote(
            vote_id=vote_id, board_id=board_id,
            member_id=member_id, scope_ref_id=scope_ref_id,
            approved=approved, reason=reason, voted_at=now,
        )
        self._votes[vote_id] = vote
        _emit(self._events, "vote_recorded", {
            "vote_id": vote_id, "board_id": board_id, "approved": approved,
        }, vote_id)
        return vote

    def votes_for_board(self, board_id: str, scope_ref_id: str = "") -> tuple[BoardVote, ...]:
        """Return votes for a board, optionally filtered by scope."""
        return tuple(
            v for v in self._votes.values()
            if v.board_id == board_id
            and (not scope_ref_id or v.scope_ref_id == scope_ref_id)
        )

    # ------------------------------------------------------------------
    # Board decisions
    # ------------------------------------------------------------------

    def resolve_board_decision(
        self,
        decision_id: str,
        board_id: str,
        *,
        scope_ref_id: str = "",
    ) -> CollaborativeDecision:
        """Resolve a board decision based on votes and approval mode."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError("Duplicate decision_id")
        board = self.get_board(board_id)
        votes = self.votes_for_board(board_id, scope_ref_id)
        total_votes = len(votes)
        approvals = sum(1 for v in votes if v.approved)
        rejections = total_votes - approvals
        now = _now_iso()

        # Determine decision status based on approval mode
        if board.approval_mode == ApprovalMode.UNANIMOUS:
            if total_votes >= board.member_count and rejections == 0:
                status = BoardDecisionStatus.APPROVED
            elif rejections > 0:
                status = BoardDecisionStatus.REJECTED
            else:
                status = BoardDecisionStatus.PENDING
        elif board.approval_mode == ApprovalMode.QUORUM:
            if approvals >= board.quorum_required:
                status = BoardDecisionStatus.APPROVED
            elif rejections > (board.member_count - board.quorum_required):
                status = BoardDecisionStatus.REJECTED
            else:
                status = BoardDecisionStatus.PENDING
        elif board.approval_mode == ApprovalMode.OVERRIDE:
            # Any single approval from an override-role member approves
            if approvals > 0:
                status = BoardDecisionStatus.OVERRIDDEN
            else:
                status = BoardDecisionStatus.PENDING
        else:
            # SINGLE mode — first vote decides
            if total_votes > 0:
                status = BoardDecisionStatus.APPROVED if approvals > 0 else BoardDecisionStatus.REJECTED
            else:
                status = BoardDecisionStatus.PENDING

        decided_by = "board" if status != BoardDecisionStatus.PENDING else ""

        decision = CollaborativeDecision(
            decision_id=decision_id, board_id=board_id,
            scope_ref_id=scope_ref_id, status=status,
            total_votes=total_votes, approvals=approvals,
            rejections=rejections,
            decided_by=decided_by, decided_at=now,
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "board_decision_resolved", {
            "decision_id": decision_id, "status": status.value,
            "approvals": approvals, "rejections": rejections,
        }, decision_id)
        return decision

    def escalate_decision(self, decision_id: str) -> CollaborativeDecision:
        """Escalate a pending decision."""
        old = self._decisions.get(decision_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown decision_id")
        if old.status in _DECISION_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot escalate decision in current status")
        updated = CollaborativeDecision(
            decision_id=old.decision_id, board_id=old.board_id,
            scope_ref_id=old.scope_ref_id,
            status=BoardDecisionStatus.ESCALATED,
            total_votes=old.total_votes, approvals=old.approvals,
            rejections=old.rejections,
            decided_by=old.decided_by, decided_at=old.decided_at,
            metadata=old.metadata,
        )
        self._decisions[decision_id] = updated
        _emit(self._events, "decision_escalated", {
            "decision_id": decision_id,
        }, decision_id)
        return updated

    def get_decision(self, decision_id: str) -> CollaborativeDecision:
        """Get a decision by ID."""
        d = self._decisions.get(decision_id)
        if d is None:
            raise RuntimeCoreInvariantError("Unknown decision_id")
        return d

    def decisions_for_board(self, board_id: str) -> tuple[CollaborativeDecision, ...]:
        """Return all decisions for a board."""
        return tuple(d for d in self._decisions.values() if d.board_id == board_id)

    # ------------------------------------------------------------------
    # Handoffs
    # ------------------------------------------------------------------

    def handoff_to_human(
        self,
        handoff_id: str,
        tenant_id: str,
        *,
        scope: CollaborationScope = CollaborationScope.SERVICE,
        scope_ref_id: str = "",
        from_ref: str = "runtime",
        to_ref: str = "human",
        reason: str = "",
    ) -> HandoffPacket:
        """Hand off work from runtime to a human."""
        if handoff_id in self._handoffs:
            raise RuntimeCoreInvariantError("Duplicate handoff_id")
        now = _now_iso()
        handoff = HandoffPacket(
            handoff_id=handoff_id, tenant_id=tenant_id,
            scope=scope, scope_ref_id=scope_ref_id,
            from_ref=from_ref, to_ref=to_ref,
            direction="to_human", reason=reason,
            handed_at=now,
        )
        self._handoffs[handoff_id] = handoff
        _emit(self._events, "handoff_to_human", {
            "handoff_id": handoff_id, "to_ref": to_ref,
        }, handoff_id)
        return handoff

    def handoff_to_runtime(
        self,
        handoff_id: str,
        tenant_id: str,
        *,
        scope: CollaborationScope = CollaborationScope.SERVICE,
        scope_ref_id: str = "",
        from_ref: str = "human",
        to_ref: str = "runtime",
        reason: str = "",
    ) -> HandoffPacket:
        """Hand off work from a human back to the runtime."""
        if handoff_id in self._handoffs:
            raise RuntimeCoreInvariantError("Duplicate handoff_id")
        now = _now_iso()
        handoff = HandoffPacket(
            handoff_id=handoff_id, tenant_id=tenant_id,
            scope=scope, scope_ref_id=scope_ref_id,
            from_ref=from_ref, to_ref=to_ref,
            direction="to_runtime", reason=reason,
            handed_at=now,
        )
        self._handoffs[handoff_id] = handoff
        _emit(self._events, "handoff_to_runtime", {
            "handoff_id": handoff_id, "from_ref": from_ref,
        }, handoff_id)
        return handoff

    def get_handoff(self, handoff_id: str) -> HandoffPacket:
        """Get a handoff by ID."""
        h = self._handoffs.get(handoff_id)
        if h is None:
            raise RuntimeCoreInvariantError("Unknown handoff_id")
        return h

    def handoffs_for_tenant(self, tenant_id: str) -> tuple[HandoffPacket, ...]:
        """Return all handoffs for a tenant."""
        return tuple(h for h in self._handoffs.values() if h.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_workflow_violations(self) -> tuple[HumanWorkflowViolation, ...]:
        """Detect human workflow violations."""
        now = _now_iso()
        new_violations: list[HumanWorkflowViolation] = []

        # Boards with no members
        for board in self._boards.values():
            if board.member_count == 0:
                vid = stable_identifier("viol-hwf", {
                    "board": board.board_id, "op": "board_no_members",
                })
                if vid not in self._violations:
                    v = HumanWorkflowViolation(
                        violation_id=vid, tenant_id=board.tenant_id,
                        scope_ref_id=board.board_id,
                        operation="board_no_members",
                        reason="approval board has no members",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Pending decisions with no votes
        for decision in self._decisions.values():
            if decision.status == BoardDecisionStatus.PENDING and decision.total_votes == 0:
                vid = stable_identifier("viol-hwf", {
                    "decision": decision.decision_id, "op": "pending_no_votes",
                })
                if vid not in self._violations:
                    board = self._boards.get(decision.board_id)
                    tenant = board.tenant_id if board else "unknown"
                    v = HumanWorkflowViolation(
                        violation_id=vid, tenant_id=tenant,
                        scope_ref_id=decision.decision_id,
                        operation="pending_no_votes",
                        reason="pending decision has no votes",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Escalated tasks with no reassignment (task still ESCALATED)
        for task in self._tasks.values():
            if task.status == HumanTaskStatus.ESCALATED:
                vid = stable_identifier("viol-hwf", {
                    "task": task.task_id, "op": "stale_escalation",
                })
                if vid not in self._violations:
                    v = HumanWorkflowViolation(
                        violation_id=vid, tenant_id=task.tenant_id,
                        scope_ref_id=task.task_id,
                        operation="stale_escalation",
                        reason="escalated task is not reassigned",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "workflow_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def workflow_snapshot(self, snapshot_id: str) -> HumanWorkflowSnapshot:
        """Capture a point-in-time workflow snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = _now_iso()
        snap = HumanWorkflowSnapshot(
            snapshot_id=snapshot_id,
            total_tasks=self.task_count,
            total_review_packets=self.review_packet_count,
            total_boards=self.board_count,
            total_members=self.member_count,
            total_votes=self.vote_count,
            total_decisions=self.decision_count,
            total_handoffs=self.handoff_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "workflow_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"tasks={self.task_count}",
            f"packets={self.review_packet_count}",
            f"boards={self.board_count}",
            f"members={self.member_count}",
            f"votes={self.vote_count}",
            f"decisions={self.decision_count}",
            f"handoffs={self.handoff_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
