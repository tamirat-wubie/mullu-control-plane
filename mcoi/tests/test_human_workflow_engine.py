"""Comprehensive tests for HumanWorkflowEngine.

Covers: constructor validation, duplicate IDs, task lifecycle, terminal guards,
review packets, approval boards, votes, decision resolution (all 4 modes),
decision escalation, handoffs, violation detection, snapshots, state hashing,
and 6 golden integration scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.human_workflow import HumanWorkflowEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.human_workflow import (
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
    HumanWorkflowSnapshot,
    HumanWorkflowViolation,
    ReviewMode,
    ReviewPacket,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(spine: EventSpineEngine) -> HumanWorkflowEngine:
    return HumanWorkflowEngine(spine)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _make_task(engine: HumanWorkflowEngine, task_id: str = "t1",
               tenant_id: str = "tenant-a", assignee_ref: str = "user-1",
               **kw) -> HumanTaskRecord:
    return engine.create_human_task(task_id, tenant_id, assignee_ref, **kw)


def _make_board(engine: HumanWorkflowEngine, board_id: str = "b1",
                tenant_id: str = "tenant-a", name: str = "Board",
                **kw) -> ApprovalBoard:
    return engine.create_approval_board(board_id, tenant_id, name, **kw)


def _make_board_with_members(engine: HumanWorkflowEngine,
                             board_id: str = "b1",
                             tenant_id: str = "tenant-a",
                             name: str = "Board",
                             member_ids: list[str] | None = None,
                             **kw):
    board = _make_board(engine, board_id, tenant_id, name, **kw)
    ids = member_ids or ["m1", "m2", "m3"]
    members = []
    for i, mid in enumerate(ids):
        m = engine.add_board_member(mid, board_id, f"identity-{i}")
        members.append(m)
    return board, members


def _make_review_packet(engine: HumanWorkflowEngine, packet_id: str = "pkt1",
                        tenant_id: str = "tenant-a", **kw) -> ReviewPacket:
    return engine.create_review_packet(packet_id, tenant_id, **kw)


# ===================================================================
# 1. Constructor validation
# ===================================================================


class TestConstructorValidation:
    def test_requires_event_spine_instance(self):
        with pytest.raises(RuntimeCoreInvariantError):
            HumanWorkflowEngine("not-a-spine")

    def test_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            HumanWorkflowEngine(None)

    def test_rejects_dict(self):
        with pytest.raises(RuntimeCoreInvariantError):
            HumanWorkflowEngine({})

    def test_rejects_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            HumanWorkflowEngine(42)

    def test_accepts_event_spine(self, spine):
        eng = HumanWorkflowEngine(spine)
        assert eng.task_count == 0

    def test_initial_counts_zero(self, engine):
        assert engine.task_count == 0
        assert engine.review_packet_count == 0
        assert engine.board_count == 0
        assert engine.member_count == 0
        assert engine.vote_count == 0
        assert engine.decision_count == 0
        assert engine.handoff_count == 0
        assert engine.violation_count == 0


# ===================================================================
# 2. Human Task — create
# ===================================================================


class TestCreateHumanTask:
    def test_returns_task_record(self, engine):
        t = _make_task(engine)
        assert isinstance(t, HumanTaskRecord)

    def test_status_is_pending(self, engine):
        t = _make_task(engine)
        assert t.status == HumanTaskStatus.PENDING

    def test_task_id_preserved(self, engine):
        t = _make_task(engine, task_id="my-task")
        assert t.task_id == "my-task"

    def test_tenant_id_preserved(self, engine):
        t = _make_task(engine, tenant_id="ten-x")
        assert t.tenant_id == "ten-x"

    def test_assignee_ref_preserved(self, engine):
        t = _make_task(engine, assignee_ref="alice")
        assert t.assignee_ref == "alice"

    def test_default_scope_is_change(self, engine):
        t = _make_task(engine)
        assert t.scope == CollaborationScope.CHANGE

    def test_custom_scope(self, engine):
        t = _make_task(engine, scope=CollaborationScope.CASE)
        assert t.scope == CollaborationScope.CASE

    def test_default_title(self, engine):
        t = _make_task(engine)
        assert t.title == "Human task"

    def test_custom_title(self, engine):
        t = _make_task(engine, title="Review evidence")
        assert t.title == "Review evidence"

    def test_default_description_empty(self, engine):
        t = _make_task(engine)
        assert t.description == ""

    def test_custom_description(self, engine):
        t = _make_task(engine, description="Detailed")
        assert t.description == "Detailed"

    def test_default_due_at_empty(self, engine):
        t = _make_task(engine)
        assert t.due_at == ""

    def test_default_scope_ref_id_empty(self, engine):
        t = _make_task(engine)
        assert t.scope_ref_id == ""

    def test_custom_scope_ref_id(self, engine):
        t = _make_task(engine, scope_ref_id="ref-123")
        assert t.scope_ref_id == "ref-123"

    def test_created_at_set(self, engine):
        t = _make_task(engine)
        assert t.created_at != ""

    def test_increments_task_count(self, engine):
        _make_task(engine, "t1")
        assert engine.task_count == 1
        _make_task(engine, "t2")
        assert engine.task_count == 2

    def test_duplicate_task_id_raises(self, engine):
        _make_task(engine, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate task_id"):
            _make_task(engine, "t1")


# ===================================================================
# 3. get_task
# ===================================================================


class TestGetTask:
    def test_returns_created_task(self, engine):
        _make_task(engine, "t1")
        t = engine.get_task("t1")
        assert t.task_id == "t1"

    def test_unknown_task_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown task_id"):
            engine.get_task("nope")


# ===================================================================
# 4. assign_task
# ===================================================================


class TestAssignTask:
    def test_assigns_pending_task(self, engine):
        _make_task(engine, "t1")
        t = engine.assign_task("t1", "bob")
        assert t.status == HumanTaskStatus.ASSIGNED
        assert t.assignee_ref == "bob"

    def test_reassign_assigned_task(self, engine):
        _make_task(engine, "t1")
        engine.assign_task("t1", "bob")
        t = engine.assign_task("t1", "carol")
        assert t.assignee_ref == "carol"

    def test_assign_escalated_task(self, engine):
        _make_task(engine, "t1")
        engine.escalate_task("t1")
        t = engine.assign_task("t1", "manager")
        assert t.status == HumanTaskStatus.ASSIGNED

    def test_assign_in_progress_task(self, engine):
        _make_task(engine, "t1")
        engine.start_task("t1")
        t = engine.assign_task("t1", "bob")
        assert t.status == HumanTaskStatus.ASSIGNED

    def test_terminal_completed_blocks_assign(self, engine):
        _make_task(engine, "t1")
        engine.complete_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot assign"):
            engine.assign_task("t1", "bob")

    def test_terminal_cancelled_blocks_assign(self, engine):
        _make_task(engine, "t1")
        engine.cancel_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot assign"):
            engine.assign_task("t1", "bob")

    def test_unknown_task_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.assign_task("nope", "bob")


# ===================================================================
# 5. start_task
# ===================================================================


class TestStartTask:
    def test_start_pending(self, engine):
        _make_task(engine, "t1")
        t = engine.start_task("t1")
        assert t.status == HumanTaskStatus.IN_PROGRESS

    def test_start_assigned(self, engine):
        _make_task(engine, "t1")
        engine.assign_task("t1", "bob")
        t = engine.start_task("t1")
        assert t.status == HumanTaskStatus.IN_PROGRESS

    def test_terminal_completed_blocks_start(self, engine):
        _make_task(engine, "t1")
        engine.complete_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot start"):
            engine.start_task("t1")

    def test_terminal_cancelled_blocks_start(self, engine):
        _make_task(engine, "t1")
        engine.cancel_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot start"):
            engine.start_task("t1")


# ===================================================================
# 6. complete_task
# ===================================================================


class TestCompleteTask:
    def test_complete_pending(self, engine):
        _make_task(engine, "t1")
        t = engine.complete_task("t1")
        assert t.status == HumanTaskStatus.COMPLETED

    def test_complete_assigned(self, engine):
        _make_task(engine, "t1")
        engine.assign_task("t1", "bob")
        t = engine.complete_task("t1")
        assert t.status == HumanTaskStatus.COMPLETED

    def test_complete_in_progress(self, engine):
        _make_task(engine, "t1")
        engine.start_task("t1")
        t = engine.complete_task("t1")
        assert t.status == HumanTaskStatus.COMPLETED

    def test_complete_escalated(self, engine):
        _make_task(engine, "t1")
        engine.escalate_task("t1")
        t = engine.complete_task("t1")
        assert t.status == HumanTaskStatus.COMPLETED

    def test_double_complete_raises(self, engine):
        _make_task(engine, "t1")
        engine.complete_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot complete"):
            engine.complete_task("t1")

    def test_cancelled_blocks_complete(self, engine):
        _make_task(engine, "t1")
        engine.cancel_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot complete"):
            engine.complete_task("t1")


# ===================================================================
# 7. cancel_task
# ===================================================================


class TestCancelTask:
    def test_cancel_pending(self, engine):
        _make_task(engine, "t1")
        t = engine.cancel_task("t1")
        assert t.status == HumanTaskStatus.CANCELLED

    def test_cancel_assigned(self, engine):
        _make_task(engine, "t1")
        engine.assign_task("t1", "bob")
        t = engine.cancel_task("t1")
        assert t.status == HumanTaskStatus.CANCELLED

    def test_cancel_in_progress(self, engine):
        _make_task(engine, "t1")
        engine.start_task("t1")
        t = engine.cancel_task("t1")
        assert t.status == HumanTaskStatus.CANCELLED

    def test_cancel_escalated(self, engine):
        _make_task(engine, "t1")
        engine.escalate_task("t1")
        t = engine.cancel_task("t1")
        assert t.status == HumanTaskStatus.CANCELLED

    def test_double_cancel_raises(self, engine):
        _make_task(engine, "t1")
        engine.cancel_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot cancel"):
            engine.cancel_task("t1")

    def test_completed_blocks_cancel(self, engine):
        _make_task(engine, "t1")
        engine.complete_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot cancel"):
            engine.cancel_task("t1")


# ===================================================================
# 8. escalate_task
# ===================================================================


class TestEscalateTask:
    def test_escalate_pending(self, engine):
        _make_task(engine, "t1")
        t = engine.escalate_task("t1")
        assert t.status == HumanTaskStatus.ESCALATED

    def test_escalate_assigned(self, engine):
        _make_task(engine, "t1")
        engine.assign_task("t1", "bob")
        t = engine.escalate_task("t1")
        assert t.status == HumanTaskStatus.ESCALATED

    def test_escalate_in_progress(self, engine):
        _make_task(engine, "t1")
        engine.start_task("t1")
        t = engine.escalate_task("t1")
        assert t.status == HumanTaskStatus.ESCALATED

    def test_escalation_ref_accepted(self, engine):
        _make_task(engine, "t1")
        t = engine.escalate_task("t1", escalation_ref="esc-001")
        assert t.status == HumanTaskStatus.ESCALATED

    def test_completed_blocks_escalate(self, engine):
        _make_task(engine, "t1")
        engine.complete_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate"):
            engine.escalate_task("t1")

    def test_cancelled_blocks_escalate(self, engine):
        _make_task(engine, "t1")
        engine.cancel_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate"):
            engine.escalate_task("t1")


# ===================================================================
# 9. tasks_for_tenant
# ===================================================================


class TestTasksForTenant:
    def test_empty_when_no_tasks(self, engine):
        assert engine.tasks_for_tenant("tenant-a") == ()

    def test_returns_matching_tasks(self, engine):
        _make_task(engine, "t1", tenant_id="tenant-a")
        _make_task(engine, "t2", tenant_id="tenant-a")
        _make_task(engine, "t3", tenant_id="tenant-b")
        result = engine.tasks_for_tenant("tenant-a")
        assert len(result) == 2
        assert all(t.tenant_id == "tenant-a" for t in result)

    def test_returns_tuple(self, engine):
        result = engine.tasks_for_tenant("x")
        assert isinstance(result, tuple)


# ===================================================================
# 10. Task lifecycle — full paths
# ===================================================================


class TestTaskLifecyclePaths:
    def test_pending_to_assigned_to_in_progress_to_completed(self, engine):
        _make_task(engine, "t1")
        engine.assign_task("t1", "bob")
        engine.start_task("t1")
        t = engine.complete_task("t1")
        assert t.status == HumanTaskStatus.COMPLETED

    def test_pending_to_assigned_to_cancelled(self, engine):
        _make_task(engine, "t1")
        engine.assign_task("t1", "bob")
        t = engine.cancel_task("t1")
        assert t.status == HumanTaskStatus.CANCELLED

    def test_pending_to_escalated_to_assigned_to_completed(self, engine):
        _make_task(engine, "t1")
        engine.escalate_task("t1")
        engine.assign_task("t1", "manager")
        t = engine.complete_task("t1")
        assert t.status == HumanTaskStatus.COMPLETED

    def test_pending_directly_to_completed(self, engine):
        _make_task(engine, "t1")
        t = engine.complete_task("t1")
        assert t.status == HumanTaskStatus.COMPLETED

    def test_pending_directly_to_cancelled(self, engine):
        _make_task(engine, "t1")
        t = engine.cancel_task("t1")
        assert t.status == HumanTaskStatus.CANCELLED

    def test_in_progress_to_escalated_to_cancelled(self, engine):
        _make_task(engine, "t1")
        engine.start_task("t1")
        engine.escalate_task("t1")
        t = engine.cancel_task("t1")
        assert t.status == HumanTaskStatus.CANCELLED


# ===================================================================
# 11. Review Packets — create
# ===================================================================


class TestCreateReviewPacket:
    def test_returns_review_packet(self, engine):
        p = _make_review_packet(engine)
        assert isinstance(p, ReviewPacket)

    def test_initial_counts_zero(self, engine):
        p = _make_review_packet(engine)
        assert p.reviewer_count == 0
        assert p.reviews_completed == 0
        assert p.reviews_approved == 0

    def test_packet_id_preserved(self, engine):
        p = _make_review_packet(engine, packet_id="pkt-x")
        assert p.packet_id == "pkt-x"

    def test_default_scope_is_case(self, engine):
        p = _make_review_packet(engine)
        assert p.scope == CollaborationScope.CASE

    def test_custom_scope(self, engine):
        p = _make_review_packet(engine, scope=CollaborationScope.REGULATORY)
        assert p.scope == CollaborationScope.REGULATORY

    def test_default_review_mode_single(self, engine):
        p = _make_review_packet(engine)
        assert p.review_mode == ReviewMode.SINGLE

    def test_custom_review_mode(self, engine):
        p = _make_review_packet(engine, review_mode=ReviewMode.PARALLEL)
        assert p.review_mode == ReviewMode.PARALLEL

    def test_default_title(self, engine):
        p = _make_review_packet(engine)
        assert p.title == "Review packet"

    def test_custom_title(self, engine):
        p = _make_review_packet(engine, title="Evidence pack")
        assert p.title == "Evidence pack"

    def test_increments_count(self, engine):
        _make_review_packet(engine, "p1")
        assert engine.review_packet_count == 1

    def test_duplicate_packet_id_raises(self, engine):
        _make_review_packet(engine, "p1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate packet_id"):
            _make_review_packet(engine, "p1")


# ===================================================================
# 12. get_review_packet
# ===================================================================


class TestGetReviewPacket:
    def test_returns_packet(self, engine):
        _make_review_packet(engine, "p1")
        p = engine.get_review_packet("p1")
        assert p.packet_id == "p1"

    def test_unknown_packet_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown packet_id"):
            engine.get_review_packet("nope")


# ===================================================================
# 13. assign_reviewer
# ===================================================================


class TestAssignReviewer:
    def test_creates_task(self, engine):
        _make_review_packet(engine, "p1")
        t = engine.assign_reviewer("p1", "rt1", "reviewer-alice")
        assert isinstance(t, HumanTaskRecord)
        assert t.task_id == "rt1"
        assert t.assignee_ref == "reviewer-alice"

    def test_increments_reviewer_count(self, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        p = engine.get_review_packet("p1")
        assert p.reviewer_count == 1
        engine.assign_reviewer("p1", "rt2", "bob")
        p = engine.get_review_packet("p1")
        assert p.reviewer_count == 2

    def test_task_scope_ref_id_points_to_packet(self, engine):
        _make_review_packet(engine, "p1")
        t = engine.assign_reviewer("p1", "rt1", "alice")
        assert t.scope_ref_id == "p1"

    def test_task_tenant_matches_packet(self, engine):
        _make_review_packet(engine, "p1", tenant_id="ten-x")
        t = engine.assign_reviewer("p1", "rt1", "alice")
        assert t.tenant_id == "ten-x"

    def test_unknown_packet_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.assign_reviewer("nope", "rt1", "alice")

    def test_duplicate_task_id_raises(self, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate task_id"):
            engine.assign_reviewer("p1", "rt1", "bob")

    def test_custom_title(self, engine):
        _make_review_packet(engine, "p1")
        t = engine.assign_reviewer("p1", "rt1", "alice", title="Check docs")
        assert t.title == "Check docs"

    def test_default_title(self, engine):
        _make_review_packet(engine, "p1")
        t = engine.assign_reviewer("p1", "rt1", "alice")
        assert t.title == "Review task"

    def test_increments_task_count(self, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        assert engine.task_count == 1


# ===================================================================
# 14. complete_review
# ===================================================================


class TestCompleteReview:
    def test_increments_completed(self, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        p = engine.complete_review("p1", "rt1", approved=True)
        assert p.reviews_completed == 1

    def test_approved_increments_approved_count(self, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        p = engine.complete_review("p1", "rt1", approved=True)
        assert p.reviews_approved == 1

    def test_rejected_does_not_increment_approved(self, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        p = engine.complete_review("p1", "rt1", approved=False)
        assert p.reviews_approved == 0
        assert p.reviews_completed == 1

    def test_completes_underlying_task(self, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        engine.complete_review("p1", "rt1")
        t = engine.get_task("rt1")
        assert t.status == HumanTaskStatus.COMPLETED

    def test_task_not_in_packet_raises(self, engine):
        _make_review_packet(engine, "p1")
        _make_task(engine, "standalone", scope_ref_id="other")
        with pytest.raises(RuntimeCoreInvariantError, match="not assigned to packet"):
            engine.complete_review("p1", "standalone")

    def test_unknown_packet_raises(self, engine):
        _make_task(engine, "t1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.complete_review("nope", "t1")

    def test_unknown_task_raises(self, engine):
        _make_review_packet(engine, "p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.complete_review("p1", "nope")

    def test_double_complete_raises(self, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        engine.complete_review("p1", "rt1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.complete_review("p1", "rt1")

    def test_multiple_reviews(self, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        engine.assign_reviewer("p1", "rt2", "bob")
        engine.complete_review("p1", "rt1", approved=True)
        p = engine.complete_review("p1", "rt2", approved=False)
        assert p.reviews_completed == 2
        assert p.reviews_approved == 1
        assert p.reviewer_count == 2


# ===================================================================
# 15. review_packets_for_tenant
# ===================================================================


class TestReviewPacketsForTenant:
    def test_empty(self, engine):
        assert engine.review_packets_for_tenant("t") == ()

    def test_filters_by_tenant(self, engine):
        _make_review_packet(engine, "p1", tenant_id="a")
        _make_review_packet(engine, "p2", tenant_id="b")
        result = engine.review_packets_for_tenant("a")
        assert len(result) == 1
        assert result[0].packet_id == "p1"

    def test_returns_tuple(self, engine):
        assert isinstance(engine.review_packets_for_tenant("x"), tuple)


# ===================================================================
# 16. Approval Boards — create
# ===================================================================


class TestCreateApprovalBoard:
    def test_returns_board(self, engine):
        b = _make_board(engine)
        assert isinstance(b, ApprovalBoard)

    def test_member_count_zero(self, engine):
        b = _make_board(engine)
        assert b.member_count == 0

    def test_board_id_preserved(self, engine):
        b = _make_board(engine, board_id="b-x")
        assert b.board_id == "b-x"

    def test_default_approval_mode_single(self, engine):
        b = _make_board(engine)
        assert b.approval_mode == ApprovalMode.SINGLE

    def test_custom_approval_mode(self, engine):
        b = _make_board(engine, approval_mode=ApprovalMode.QUORUM)
        assert b.approval_mode == ApprovalMode.QUORUM

    def test_default_quorum_required(self, engine):
        b = _make_board(engine)
        assert b.quorum_required == 1

    def test_custom_quorum_required(self, engine):
        b = _make_board(engine, quorum_required=3)
        assert b.quorum_required == 3

    def test_default_scope_change(self, engine):
        b = _make_board(engine)
        assert b.scope == CollaborationScope.CHANGE

    def test_custom_scope(self, engine):
        b = _make_board(engine, scope=CollaborationScope.PROCUREMENT)
        assert b.scope == CollaborationScope.PROCUREMENT

    def test_increments_board_count(self, engine):
        _make_board(engine, "b1")
        assert engine.board_count == 1

    def test_duplicate_board_id_raises(self, engine):
        _make_board(engine, "b1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate board_id"):
            _make_board(engine, "b1")


# ===================================================================
# 17. get_board
# ===================================================================


class TestGetBoard:
    def test_returns_board(self, engine):
        _make_board(engine, "b1")
        b = engine.get_board("b1")
        assert b.board_id == "b1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown board_id"):
            engine.get_board("nope")


# ===================================================================
# 18. add_board_member
# ===================================================================


class TestAddBoardMember:
    def test_returns_member(self, engine):
        _make_board(engine, "b1")
        m = engine.add_board_member("m1", "b1", "identity-alice")
        assert isinstance(m, BoardMember)
        assert m.member_id == "m1"

    def test_identity_ref_preserved(self, engine):
        _make_board(engine, "b1")
        m = engine.add_board_member("m1", "b1", "identity-alice")
        assert m.identity_ref == "identity-alice"

    def test_board_id_preserved(self, engine):
        _make_board(engine, "b1")
        m = engine.add_board_member("m1", "b1", "identity-alice")
        assert m.board_id == "b1"

    def test_default_role_member(self, engine):
        _make_board(engine, "b1")
        m = engine.add_board_member("m1", "b1", "identity-alice")
        assert m.role == "member"

    def test_custom_role(self, engine):
        _make_board(engine, "b1")
        m = engine.add_board_member("m1", "b1", "identity-alice", role="chair")
        assert m.role == "chair"

    def test_increments_board_member_count(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        b = engine.get_board("b1")
        assert b.member_count == 1
        engine.add_board_member("m2", "b1", "bob")
        b = engine.get_board("b1")
        assert b.member_count == 2

    def test_increments_engine_member_count(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        assert engine.member_count == 1

    def test_duplicate_member_id_raises(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate member_id"):
            engine.add_board_member("m1", "b1", "bob")

    def test_unknown_board_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_board_member("m1", "nope", "alice")

    def test_added_at_set(self, engine):
        _make_board(engine, "b1")
        m = engine.add_board_member("m1", "b1", "alice")
        assert m.added_at != ""


# ===================================================================
# 19. members_for_board
# ===================================================================


class TestMembersForBoard:
    def test_empty(self, engine):
        _make_board(engine, "b1")
        assert engine.members_for_board("b1") == ()

    def test_returns_members(self, engine):
        _make_board(engine, "b1")
        _make_board(engine, "b2")
        engine.add_board_member("m1", "b1", "alice")
        engine.add_board_member("m2", "b2", "bob")
        result = engine.members_for_board("b1")
        assert len(result) == 1
        assert result[0].member_id == "m1"

    def test_returns_tuple(self, engine):
        assert isinstance(engine.members_for_board("x"), tuple)


# ===================================================================
# 20. record_vote
# ===================================================================


class TestRecordVote:
    def test_returns_vote(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        v = engine.record_vote("v1", "b1", "m1")
        assert isinstance(v, BoardVote)

    def test_vote_id_preserved(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        v = engine.record_vote("v1", "b1", "m1")
        assert v.vote_id == "v1"

    def test_default_approved_true(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        v = engine.record_vote("v1", "b1", "m1")
        assert v.approved is True

    def test_explicit_rejected(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        v = engine.record_vote("v1", "b1", "m1", approved=False)
        assert v.approved is False

    def test_reason_preserved(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        v = engine.record_vote("v1", "b1", "m1", reason="Looks good")
        assert v.reason == "Looks good"

    def test_scope_ref_id_preserved(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        v = engine.record_vote("v1", "b1", "m1", scope_ref_id="change-1")
        assert v.scope_ref_id == "change-1"

    def test_increments_vote_count(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1")
        assert engine.vote_count == 1

    def test_duplicate_vote_id_raises(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.add_board_member("m2", "b1", "bob")
        engine.record_vote("v1", "b1", "m1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate vote_id"):
            engine.record_vote("v1", "b1", "m2")

    def test_unknown_member_raises(self, engine):
        _make_board(engine, "b1")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown member_id"):
            engine.record_vote("v1", "b1", "nope")

    def test_member_wrong_board_raises(self, engine):
        _make_board(engine, "b1")
        _make_board(engine, "b2")
        engine.add_board_member("m1", "b1", "alice")
        with pytest.raises(RuntimeCoreInvariantError, match="not on board"):
            engine.record_vote("v1", "b2", "m1")

    def test_duplicate_vote_same_member_same_scope_raises(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", scope_ref_id="change-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already voted"):
            engine.record_vote("v2", "b1", "m1", scope_ref_id="change-1")

    def test_same_member_different_scope_ok(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", scope_ref_id="change-1")
        v = engine.record_vote("v2", "b1", "m1", scope_ref_id="change-2")
        assert v.vote_id == "v2"

    def test_unknown_board_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_vote("v1", "nope", "m1")


# ===================================================================
# 21. votes_for_board
# ===================================================================


class TestVotesForBoard:
    def test_empty(self, engine):
        _make_board(engine, "b1")
        assert engine.votes_for_board("b1") == ()

    def test_returns_all_votes(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.add_board_member("m2", "b1", "bob")
        engine.record_vote("v1", "b1", "m1")
        engine.record_vote("v2", "b1", "m2")
        assert len(engine.votes_for_board("b1")) == 2

    def test_filters_by_scope_ref_id(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", scope_ref_id="s1")
        engine.record_vote("v2", "b1", "m1", scope_ref_id="s2")
        result = engine.votes_for_board("b1", scope_ref_id="s1")
        assert len(result) == 1
        assert result[0].scope_ref_id == "s1"

    def test_empty_scope_ref_returns_all(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", scope_ref_id="s1")
        result = engine.votes_for_board("b1", scope_ref_id="")
        assert len(result) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.votes_for_board("b1" if False else "x"), tuple)


# ===================================================================
# 22. Decision resolution — SINGLE mode
# ===================================================================


class TestDecisionResolutionSingle:
    def test_no_votes_pending(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.PENDING
        assert d.total_votes == 0

    def test_single_approval(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.APPROVED

    def test_single_rejection(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", approved=False)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.REJECTED

    def test_decided_by_board(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.decided_by == "board"

    def test_pending_decided_by_empty(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        d = engine.resolve_board_decision("d1", "b1")
        assert d.decided_by == ""

    def test_duplicate_decision_id_raises(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("d1", "b1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate decision_id"):
            engine.resolve_board_decision("d1", "b1")

    def test_unknown_board_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resolve_board_decision("d1", "nope")

    def test_scope_ref_id_preserved(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", scope_ref_id="change-1")
        d = engine.resolve_board_decision("d1", "b1", scope_ref_id="change-1")
        assert d.scope_ref_id == "change-1"

    def test_counts_correct(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.total_votes == 1
        assert d.approvals == 1
        assert d.rejections == 0


# ===================================================================
# 23. Decision resolution — QUORUM mode
# ===================================================================


class TestDecisionResolutionQuorum:
    def test_quorum_met_approved(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.QUORUM,
                    quorum_required=2)
        for i in range(3):
            engine.add_board_member(f"m{i}", "b1", f"id-{i}")
        engine.record_vote("v0", "b1", "m0", approved=True)
        engine.record_vote("v1", "b1", "m1", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.APPROVED

    def test_quorum_not_met_pending(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.QUORUM,
                    quorum_required=2)
        for i in range(3):
            engine.add_board_member(f"m{i}", "b1", f"id-{i}")
        engine.record_vote("v0", "b1", "m0", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.PENDING

    def test_too_many_rejections_rejected(self, engine):
        # board: 3 members, quorum=2 => rejections > (3-2)=1 means rejected
        _make_board(engine, "b1", approval_mode=ApprovalMode.QUORUM,
                    quorum_required=2)
        for i in range(3):
            engine.add_board_member(f"m{i}", "b1", f"id-{i}")
        engine.record_vote("v0", "b1", "m0", approved=False)
        engine.record_vote("v1", "b1", "m1", approved=False)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.REJECTED

    def test_single_rejection_still_pending(self, engine):
        # board: 3 members, quorum=2 => rejections > 1 needed for reject
        _make_board(engine, "b1", approval_mode=ApprovalMode.QUORUM,
                    quorum_required=2)
        for i in range(3):
            engine.add_board_member(f"m{i}", "b1", f"id-{i}")
        engine.record_vote("v0", "b1", "m0", approved=False)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.PENDING

    def test_quorum_exact_boundary(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.QUORUM,
                    quorum_required=3)
        for i in range(5):
            engine.add_board_member(f"m{i}", "b1", f"id-{i}")
        # 3 approvals == quorum_required => APPROVED
        for i in range(3):
            engine.record_vote(f"v{i}", "b1", f"m{i}", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.APPROVED

    def test_counts_preserved(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.QUORUM,
                    quorum_required=2)
        for i in range(3):
            engine.add_board_member(f"m{i}", "b1", f"id-{i}")
        engine.record_vote("v0", "b1", "m0", approved=True)
        engine.record_vote("v1", "b1", "m1", approved=False)
        engine.record_vote("v2", "b1", "m2", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.total_votes == 3
        assert d.approvals == 2
        assert d.rejections == 1


# ===================================================================
# 24. Decision resolution — UNANIMOUS mode
# ===================================================================


class TestDecisionResolutionUnanimous:
    def test_all_approve_approved(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.UNANIMOUS)
        engine.add_board_member("m1", "b1", "alice")
        engine.add_board_member("m2", "b1", "bob")
        engine.record_vote("v1", "b1", "m1", approved=True)
        engine.record_vote("v2", "b1", "m2", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.APPROVED

    def test_any_rejection_rejected(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.UNANIMOUS)
        engine.add_board_member("m1", "b1", "alice")
        engine.add_board_member("m2", "b1", "bob")
        engine.record_vote("v1", "b1", "m1", approved=True)
        engine.record_vote("v2", "b1", "m2", approved=False)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.REJECTED

    def test_not_all_voted_pending(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.UNANIMOUS)
        engine.add_board_member("m1", "b1", "alice")
        engine.add_board_member("m2", "b1", "bob")
        engine.record_vote("v1", "b1", "m1", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.PENDING

    def test_no_votes_pending(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.UNANIMOUS)
        engine.add_board_member("m1", "b1", "alice")
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.PENDING

    def test_single_member_approves(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.UNANIMOUS)
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.APPROVED

    def test_single_member_rejects(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.UNANIMOUS)
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", approved=False)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.REJECTED


# ===================================================================
# 25. Decision resolution — OVERRIDE mode
# ===================================================================


class TestDecisionResolutionOverride:
    def test_any_approval_overridden(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.OVERRIDE)
        engine.add_board_member("m1", "b1", "exec")
        engine.record_vote("v1", "b1", "m1", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.OVERRIDDEN

    def test_no_votes_pending(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.OVERRIDE)
        engine.add_board_member("m1", "b1", "exec")
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.PENDING

    def test_only_rejections_pending(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.OVERRIDE)
        engine.add_board_member("m1", "b1", "exec")
        engine.record_vote("v1", "b1", "m1", approved=False)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.PENDING

    def test_mixed_with_one_approval_overridden(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.OVERRIDE)
        engine.add_board_member("m1", "b1", "exec1")
        engine.add_board_member("m2", "b1", "exec2")
        engine.record_vote("v1", "b1", "m1", approved=False)
        engine.record_vote("v2", "b1", "m2", approved=True)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == BoardDecisionStatus.OVERRIDDEN


# ===================================================================
# 26. Decision resolution — scoped votes
# ===================================================================


class TestDecisionResolutionScoped:
    def test_scoped_votes_filter(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        # Vote on scope "change-1"
        engine.record_vote("v1", "b1", "m1", scope_ref_id="change-1", approved=True)
        # Vote on scope "change-2"
        engine.record_vote("v2", "b1", "m1", scope_ref_id="change-2", approved=False)
        # Resolve for change-1
        d = engine.resolve_board_decision("d1", "b1", scope_ref_id="change-1")
        assert d.status == BoardDecisionStatus.APPROVED
        assert d.total_votes == 1

    def test_scoped_decision_scope_ref_id(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", scope_ref_id="change-1", approved=False)
        d = engine.resolve_board_decision("d1", "b1", scope_ref_id="change-1")
        assert d.scope_ref_id == "change-1"
        assert d.status == BoardDecisionStatus.REJECTED


# ===================================================================
# 27. escalate_decision
# ===================================================================


class TestEscalateDecision:
    def test_escalate_pending(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("d1", "b1")
        d = engine.escalate_decision("d1")
        assert d.status == BoardDecisionStatus.ESCALATED

    def test_escalate_approved_raises(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", approved=True)
        engine.resolve_board_decision("d1", "b1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate"):
            engine.escalate_decision("d1")

    def test_escalate_rejected_raises(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", approved=False)
        engine.resolve_board_decision("d1", "b1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate"):
            engine.escalate_decision("d1")

    def test_escalate_overridden_raises(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.OVERRIDE)
        engine.add_board_member("m1", "b1", "exec")
        engine.record_vote("v1", "b1", "m1", approved=True)
        engine.resolve_board_decision("d1", "b1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate"):
            engine.escalate_decision("d1")

    def test_unknown_decision_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown decision_id"):
            engine.escalate_decision("nope")

    def test_preserves_vote_counts(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("d1", "b1")  # pending, 0 votes
        d = engine.escalate_decision("d1")
        assert d.total_votes == 0
        assert d.approvals == 0
        assert d.rejections == 0


# ===================================================================
# 28. get_decision / decisions_for_board
# ===================================================================


class TestGetDecision:
    def test_returns_decision(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("d1", "b1")
        d = engine.get_decision("d1")
        assert d.decision_id == "d1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown decision_id"):
            engine.get_decision("nope")


class TestDecisionsForBoard:
    def test_empty(self, engine):
        _make_board(engine, "b1")
        assert engine.decisions_for_board("b1") == ()

    def test_returns_matching(self, engine):
        _make_board(engine, "b1")
        _make_board(engine, "b2")
        engine.add_board_member("m1", "b1", "alice")
        engine.add_board_member("m2", "b2", "bob")
        engine.resolve_board_decision("d1", "b1")
        engine.resolve_board_decision("d2", "b2")
        result = engine.decisions_for_board("b1")
        assert len(result) == 1
        assert result[0].decision_id == "d1"

    def test_returns_tuple(self, engine):
        assert isinstance(engine.decisions_for_board("x"), tuple)


# ===================================================================
# 29. Handoffs
# ===================================================================


class TestHandoffToHuman:
    def test_returns_handoff(self, engine):
        h = engine.handoff_to_human("h1", "tenant-a")
        assert isinstance(h, HandoffPacket)

    def test_direction_to_human(self, engine):
        h = engine.handoff_to_human("h1", "tenant-a")
        assert h.direction == "to_human"

    def test_default_from_ref_runtime(self, engine):
        h = engine.handoff_to_human("h1", "tenant-a")
        assert h.from_ref == "runtime"

    def test_custom_to_ref(self, engine):
        h = engine.handoff_to_human("h1", "tenant-a", to_ref="agent-bob")
        assert h.to_ref == "agent-bob"

    def test_default_scope_service(self, engine):
        h = engine.handoff_to_human("h1", "tenant-a")
        assert h.scope == CollaborationScope.SERVICE

    def test_custom_scope(self, engine):
        h = engine.handoff_to_human("h1", "tenant-a",
                                     scope=CollaborationScope.EXECUTIVE)
        assert h.scope == CollaborationScope.EXECUTIVE

    def test_reason_preserved(self, engine):
        h = engine.handoff_to_human("h1", "tenant-a", reason="Need approval")
        assert h.reason == "Need approval"

    def test_duplicate_raises(self, engine):
        engine.handoff_to_human("h1", "tenant-a")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate handoff_id"):
            engine.handoff_to_human("h1", "tenant-a")

    def test_increments_count(self, engine):
        engine.handoff_to_human("h1", "tenant-a")
        assert engine.handoff_count == 1

    def test_scope_ref_id_preserved(self, engine):
        h = engine.handoff_to_human("h1", "tenant-a", scope_ref_id="svc-123")
        assert h.scope_ref_id == "svc-123"


class TestHandoffToRuntime:
    def test_returns_handoff(self, engine):
        h = engine.handoff_to_runtime("h1", "tenant-a", from_ref="human-bob")
        assert isinstance(h, HandoffPacket)

    def test_direction_to_runtime(self, engine):
        h = engine.handoff_to_runtime("h1", "tenant-a", from_ref="bob")
        assert h.direction == "to_runtime"

    def test_default_to_ref_runtime(self, engine):
        h = engine.handoff_to_runtime("h1", "tenant-a", from_ref="bob")
        assert h.to_ref == "runtime"

    def test_custom_from_ref(self, engine):
        h = engine.handoff_to_runtime("h1", "tenant-a", from_ref="agent-alice")
        assert h.from_ref == "agent-alice"

    def test_reason_preserved(self, engine):
        h = engine.handoff_to_runtime("h1", "tenant-a", from_ref="bob",
                                       reason="Done with review")
        assert h.reason == "Done with review"

    def test_duplicate_raises(self, engine):
        engine.handoff_to_runtime("h1", "tenant-a", from_ref="bob")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate handoff_id"):
            engine.handoff_to_runtime("h1", "tenant-a", from_ref="bob")

    def test_handoff_id_shared_namespace(self, engine):
        engine.handoff_to_human("h1", "tenant-a")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate handoff_id"):
            engine.handoff_to_runtime("h1", "tenant-a", from_ref="bob")

    def test_scope_ref_id_preserved(self, engine):
        h = engine.handoff_to_runtime("h1", "tenant-a", from_ref="bob",
                                       scope_ref_id="svc-123")
        assert h.scope_ref_id == "svc-123"


class TestGetHandoff:
    def test_returns_handoff(self, engine):
        engine.handoff_to_human("h1", "tenant-a")
        h = engine.get_handoff("h1")
        assert h.handoff_id == "h1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown handoff_id"):
            engine.get_handoff("nope")


class TestHandoffsForTenant:
    def test_empty(self, engine):
        assert engine.handoffs_for_tenant("x") == ()

    def test_filters_by_tenant(self, engine):
        engine.handoff_to_human("h1", "a")
        engine.handoff_to_human("h2", "b")
        result = engine.handoffs_for_tenant("a")
        assert len(result) == 1
        assert result[0].handoff_id == "h1"

    def test_returns_tuple(self, engine):
        assert isinstance(engine.handoffs_for_tenant("x"), tuple)


# ===================================================================
# 30. Violation detection
# ===================================================================


class TestDetectWorkflowViolations:
    def test_no_violations_empty_engine(self, engine):
        result = engine.detect_workflow_violations()
        assert result == ()

    def test_board_no_members_violation(self, engine):
        _make_board(engine, "b1")
        violations = engine.detect_workflow_violations()
        assert len(violations) == 1
        assert violations[0].operation == "board_no_members"
        assert "b1" in violations[0].reason

    def test_board_with_members_no_violation(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        violations = engine.detect_workflow_violations()
        # Filter for board_no_members only
        board_violations = [v for v in violations if v.operation == "board_no_members"]
        assert len(board_violations) == 0

    def test_pending_no_votes_violation(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("d1", "b1")  # pending, 0 votes
        violations = engine.detect_workflow_violations()
        pending_violations = [v for v in violations if v.operation == "pending_no_votes"]
        assert len(pending_violations) == 1

    def test_pending_with_votes_no_violation(self, engine):
        _make_board(engine, "b1", approval_mode=ApprovalMode.UNANIMOUS)
        engine.add_board_member("m1", "b1", "alice")
        engine.add_board_member("m2", "b1", "bob")
        engine.record_vote("v1", "b1", "m1", approved=True)
        engine.resolve_board_decision("d1", "b1")  # pending (not all voted)
        d = engine.get_decision("d1")
        assert d.status == BoardDecisionStatus.PENDING
        assert d.total_votes == 1
        violations = engine.detect_workflow_violations()
        pending_violations = [v for v in violations if v.operation == "pending_no_votes"]
        assert len(pending_violations) == 0

    def test_stale_escalation_violation(self, engine):
        _make_task(engine, "t1")
        engine.escalate_task("t1")
        violations = engine.detect_workflow_violations()
        esc_violations = [v for v in violations if v.operation == "stale_escalation"]
        assert len(esc_violations) == 1
        assert "t1" in esc_violations[0].reason

    def test_escalated_then_reassigned_no_violation(self, engine):
        _make_task(engine, "t1")
        engine.escalate_task("t1")
        engine.assign_task("t1", "manager")  # no longer ESCALATED
        violations = engine.detect_workflow_violations()
        esc_violations = [v for v in violations if v.operation == "stale_escalation"]
        assert len(esc_violations) == 0

    def test_idempotency_second_call_empty(self, engine):
        _make_board(engine, "b1")  # board with no members
        first = engine.detect_workflow_violations()
        assert len(first) == 1
        second = engine.detect_workflow_violations()
        assert len(second) == 0

    def test_idempotency_violation_count_stable(self, engine):
        _make_board(engine, "b1")
        engine.detect_workflow_violations()
        assert engine.violation_count == 1
        engine.detect_workflow_violations()
        assert engine.violation_count == 1

    def test_multiple_violation_types(self, engine):
        _make_board(engine, "b1")  # board_no_members
        _make_task(engine, "t1")
        engine.escalate_task("t1")  # stale_escalation
        violations = engine.detect_workflow_violations()
        ops = {v.operation for v in violations}
        assert "board_no_members" in ops
        assert "stale_escalation" in ops

    def test_returns_tuple(self, engine):
        result = engine.detect_workflow_violations()
        assert isinstance(result, tuple)

    def test_violation_tenant_id_from_board(self, engine):
        _make_board(engine, "b1", tenant_id="ten-x")
        violations = engine.detect_workflow_violations()
        assert violations[0].tenant_id == "ten-x"

    def test_violation_tenant_id_from_task(self, engine):
        _make_task(engine, "t1", tenant_id="ten-y")
        engine.escalate_task("t1")
        violations = engine.detect_workflow_violations()
        esc = [v for v in violations if v.operation == "stale_escalation"]
        assert esc[0].tenant_id == "ten-y"

    def test_multiple_boards_no_members(self, engine):
        _make_board(engine, "b1")
        _make_board(engine, "b2")
        violations = engine.detect_workflow_violations()
        board_violations = [v for v in violations if v.operation == "board_no_members"]
        assert len(board_violations) == 2

    def test_new_violation_after_new_condition(self, engine):
        _make_board(engine, "b1")
        v1 = engine.detect_workflow_violations()
        assert len(v1) == 1
        # Add another board without members
        _make_board(engine, "b2")
        v2 = engine.detect_workflow_violations()
        assert len(v2) == 1  # only the new one
        assert engine.violation_count == 2


# ===================================================================
# 31. Snapshot
# ===================================================================


class TestWorkflowSnapshot:
    def test_returns_snapshot(self, engine):
        s = engine.workflow_snapshot("s1")
        assert isinstance(s, HumanWorkflowSnapshot)

    def test_snapshot_id_preserved(self, engine):
        s = engine.workflow_snapshot("s1")
        assert s.snapshot_id == "s1"

    def test_captures_task_count(self, engine):
        _make_task(engine, "t1")
        _make_task(engine, "t2")
        s = engine.workflow_snapshot("s1")
        assert s.total_tasks == 2

    def test_captures_review_packet_count(self, engine):
        _make_review_packet(engine, "p1")
        s = engine.workflow_snapshot("s1")
        assert s.total_review_packets == 1

    def test_captures_board_count(self, engine):
        _make_board(engine, "b1")
        s = engine.workflow_snapshot("s1")
        assert s.total_boards == 1

    def test_captures_member_count(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        s = engine.workflow_snapshot("s1")
        assert s.total_members == 1

    def test_captures_vote_count(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1")
        s = engine.workflow_snapshot("s1")
        assert s.total_votes == 1

    def test_captures_decision_count(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("d1", "b1")
        s = engine.workflow_snapshot("s1")
        assert s.total_decisions == 1

    def test_captures_handoff_count(self, engine):
        engine.handoff_to_human("h1", "tenant-a")
        s = engine.workflow_snapshot("s1")
        assert s.total_handoffs == 1

    def test_captures_violation_count(self, engine):
        _make_board(engine, "b1")
        engine.detect_workflow_violations()
        s = engine.workflow_snapshot("s1")
        assert s.total_violations == 1

    def test_empty_snapshot(self, engine):
        s = engine.workflow_snapshot("s1")
        assert s.total_tasks == 0
        assert s.total_review_packets == 0
        assert s.total_boards == 0
        assert s.total_members == 0
        assert s.total_votes == 0
        assert s.total_decisions == 0
        assert s.total_handoffs == 0
        assert s.total_violations == 0

    def test_duplicate_snapshot_id_raises(self, engine):
        engine.workflow_snapshot("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.workflow_snapshot("s1")

    def test_captured_at_set(self, engine):
        s = engine.workflow_snapshot("s1")
        assert s.captured_at != ""

    def test_multiple_snapshots(self, engine):
        s1 = engine.workflow_snapshot("s1")
        _make_task(engine, "t1")
        s2 = engine.workflow_snapshot("s2")
        assert s1.total_tasks == 0
        assert s2.total_tasks == 1


# ===================================================================
# 32. State hash
# ===================================================================


class TestStateHash:
    def test_returns_string(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_is_16_chars(self, engine):
        h = engine.state_hash()
        assert len(h) == 64

    def test_hex_chars(self, engine):
        h = engine.state_hash()
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_on_task_creation(self, engine):
        h1 = engine.state_hash()
        _make_task(engine, "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_board_creation(self, engine):
        h1 = engine.state_hash()
        _make_board(engine, "b1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_member_add(self, engine):
        _make_board(engine, "b1")
        h1 = engine.state_hash()
        engine.add_board_member("m1", "b1", "alice")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_vote(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        h1 = engine.state_hash()
        engine.record_vote("v1", "b1", "m1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_decision(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        h1 = engine.state_hash()
        engine.resolve_board_decision("d1", "b1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_handoff(self, engine):
        h1 = engine.state_hash()
        engine.handoff_to_human("h1", "tenant-a")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_violation_detection(self, engine):
        _make_board(engine, "b1")
        h1 = engine.state_hash()
        engine.detect_workflow_violations()
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_review_packet(self, engine):
        h1 = engine.state_hash()
        _make_review_packet(engine, "p1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_is_method_not_property(self, engine):
        # state_hash is callable as a method
        assert callable(engine.state_hash)
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_two_engines_same_state_same_hash(self, spine):
        e1 = HumanWorkflowEngine(EventSpineEngine())
        e2 = HumanWorkflowEngine(EventSpineEngine())
        assert e1.state_hash() == e2.state_hash()


# ===================================================================
# 33. Properties
# ===================================================================


class TestProperties:
    def test_task_count(self, engine):
        assert engine.task_count == 0
        _make_task(engine, "t1")
        assert engine.task_count == 1

    def test_review_packet_count(self, engine):
        assert engine.review_packet_count == 0
        _make_review_packet(engine, "p1")
        assert engine.review_packet_count == 1

    def test_board_count(self, engine):
        assert engine.board_count == 0
        _make_board(engine, "b1")
        assert engine.board_count == 1

    def test_member_count(self, engine):
        assert engine.member_count == 0
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        assert engine.member_count == 1

    def test_vote_count(self, engine):
        assert engine.vote_count == 0
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1")
        assert engine.vote_count == 1

    def test_decision_count(self, engine):
        assert engine.decision_count == 0
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("d1", "b1")
        assert engine.decision_count == 1

    def test_handoff_count(self, engine):
        assert engine.handoff_count == 0
        engine.handoff_to_human("h1", "tenant-a")
        assert engine.handoff_count == 1

    def test_violation_count(self, engine):
        assert engine.violation_count == 0
        _make_board(engine, "b1")
        engine.detect_workflow_violations()
        assert engine.violation_count == 1


# ===================================================================
# 34. Event emission verification
# ===================================================================


class TestEventEmission:
    def test_create_task_emits_event(self, spine, engine):
        before = spine.event_count
        _make_task(engine, "t1")
        assert spine.event_count > before

    def test_assign_task_emits_event(self, spine, engine):
        _make_task(engine, "t1")
        before = spine.event_count
        engine.assign_task("t1", "bob")
        assert spine.event_count > before

    def test_start_task_emits_event(self, spine, engine):
        _make_task(engine, "t1")
        before = spine.event_count
        engine.start_task("t1")
        assert spine.event_count > before

    def test_complete_task_emits_event(self, spine, engine):
        _make_task(engine, "t1")
        before = spine.event_count
        engine.complete_task("t1")
        assert spine.event_count > before

    def test_cancel_task_emits_event(self, spine, engine):
        _make_task(engine, "t1")
        before = spine.event_count
        engine.cancel_task("t1")
        assert spine.event_count > before

    def test_escalate_task_emits_event(self, spine, engine):
        _make_task(engine, "t1")
        before = spine.event_count
        engine.escalate_task("t1")
        assert spine.event_count > before

    def test_create_review_packet_emits_event(self, spine, engine):
        before = spine.event_count
        _make_review_packet(engine, "p1")
        assert spine.event_count > before

    def test_assign_reviewer_emits_event(self, spine, engine):
        _make_review_packet(engine, "p1")
        before = spine.event_count
        engine.assign_reviewer("p1", "rt1", "alice")
        assert spine.event_count > before

    def test_complete_review_emits_event(self, spine, engine):
        _make_review_packet(engine, "p1")
        engine.assign_reviewer("p1", "rt1", "alice")
        before = spine.event_count
        engine.complete_review("p1", "rt1")
        assert spine.event_count > before

    def test_create_board_emits_event(self, spine, engine):
        before = spine.event_count
        _make_board(engine, "b1")
        assert spine.event_count > before

    def test_add_board_member_emits_event(self, spine, engine):
        _make_board(engine, "b1")
        before = spine.event_count
        engine.add_board_member("m1", "b1", "alice")
        assert spine.event_count > before

    def test_record_vote_emits_event(self, spine, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        before = spine.event_count
        engine.record_vote("v1", "b1", "m1")
        assert spine.event_count > before

    def test_resolve_decision_emits_event(self, spine, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        before = spine.event_count
        engine.resolve_board_decision("d1", "b1")
        assert spine.event_count > before

    def test_escalate_decision_emits_event(self, spine, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("d1", "b1")
        before = spine.event_count
        engine.escalate_decision("d1")
        assert spine.event_count > before

    def test_handoff_to_human_emits_event(self, spine, engine):
        before = spine.event_count
        engine.handoff_to_human("h1", "tenant-a")
        assert spine.event_count > before

    def test_handoff_to_runtime_emits_event(self, spine, engine):
        before = spine.event_count
        engine.handoff_to_runtime("h1", "tenant-a", from_ref="bob")
        assert spine.event_count > before

    def test_violation_detection_emits_event(self, spine, engine):
        _make_board(engine, "b1")
        before = spine.event_count
        engine.detect_workflow_violations()
        assert spine.event_count > before

    def test_snapshot_emits_event(self, spine, engine):
        before = spine.event_count
        engine.workflow_snapshot("s1")
        assert spine.event_count > before


# ===================================================================
# 35. Immutability / frozen records
# ===================================================================


class TestImmutability:
    def test_task_record_frozen(self, engine):
        t = _make_task(engine, "t1")
        with pytest.raises(AttributeError):
            t.status = HumanTaskStatus.COMPLETED

    def test_review_packet_frozen(self, engine):
        p = _make_review_packet(engine, "p1")
        with pytest.raises(AttributeError):
            p.reviewer_count = 99

    def test_board_frozen(self, engine):
        b = _make_board(engine, "b1")
        with pytest.raises(AttributeError):
            b.member_count = 99

    def test_member_frozen(self, engine):
        _make_board(engine, "b1")
        m = engine.add_board_member("m1", "b1", "alice")
        with pytest.raises(AttributeError):
            m.role = "admin"

    def test_vote_frozen(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        v = engine.record_vote("v1", "b1", "m1")
        with pytest.raises(AttributeError):
            v.approved = False

    def test_decision_frozen(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        d = engine.resolve_board_decision("d1", "b1")
        with pytest.raises(AttributeError):
            d.status = BoardDecisionStatus.APPROVED

    def test_handoff_frozen(self, engine):
        h = engine.handoff_to_human("h1", "tenant-a")
        with pytest.raises(AttributeError):
            h.direction = "to_runtime"

    def test_snapshot_frozen(self, engine):
        s = engine.workflow_snapshot("s1")
        with pytest.raises(AttributeError):
            s.total_tasks = 99


# ===================================================================
# GOLDEN SCENARIO 1: Procurement board approval (QUORUM)
# ===================================================================


class TestGoldenProcurementBoardApproval:
    def test_full_procurement_approval_flow(self, engine):
        # Create procurement board with quorum mode
        board = engine.create_approval_board(
            "procurement-board", "tenant-acme", "Procurement Committee",
            approval_mode=ApprovalMode.QUORUM,
            quorum_required=2,
            scope=CollaborationScope.PROCUREMENT,
        )
        assert board.member_count == 0

        # Add 3 members
        engine.add_board_member("pm-cfo", "procurement-board", "cfo@acme",
                                role="approver")
        engine.add_board_member("pm-cto", "procurement-board", "cto@acme",
                                role="approver")
        engine.add_board_member("pm-coo", "procurement-board", "coo@acme",
                                role="approver")
        board = engine.get_board("procurement-board")
        assert board.member_count == 3

        # Record votes (2 approve, 1 reject)
        engine.record_vote("pv-1", "procurement-board", "pm-cfo",
                           scope_ref_id="po-100", approved=True,
                           reason="Within budget")
        engine.record_vote("pv-2", "procurement-board", "pm-cto",
                           scope_ref_id="po-100", approved=True,
                           reason="Technical fit")
        engine.record_vote("pv-3", "procurement-board", "pm-coo",
                           scope_ref_id="po-100", approved=False,
                           reason="Timeline concern")

        # Resolve
        decision = engine.resolve_board_decision(
            "pd-1", "procurement-board", scope_ref_id="po-100",
        )
        assert decision.status == BoardDecisionStatus.APPROVED
        assert decision.approvals == 2
        assert decision.rejections == 1
        assert decision.total_votes == 3
        assert decision.decided_by == "board"

        # Verify counts
        assert engine.board_count == 1
        assert engine.member_count == 3
        assert engine.vote_count == 3
        assert engine.decision_count == 1

    def test_procurement_quorum_not_met(self, engine):
        engine.create_approval_board(
            "pb", "tenant-acme", "Procurement",
            approval_mode=ApprovalMode.QUORUM, quorum_required=2,
        )
        engine.add_board_member("m1", "pb", "alice")
        engine.add_board_member("m2", "pb", "bob")
        engine.add_board_member("m3", "pb", "carol")
        engine.record_vote("v1", "pb", "m1", approved=True)
        d = engine.resolve_board_decision("d1", "pb")
        assert d.status == BoardDecisionStatus.PENDING

    def test_procurement_quorum_rejected(self, engine):
        engine.create_approval_board(
            "pb", "tenant-acme", "Procurement",
            approval_mode=ApprovalMode.QUORUM, quorum_required=2,
        )
        engine.add_board_member("m1", "pb", "alice")
        engine.add_board_member("m2", "pb", "bob")
        engine.add_board_member("m3", "pb", "carol")
        engine.record_vote("v1", "pb", "m1", approved=False)
        engine.record_vote("v2", "pb", "m2", approved=False)
        d = engine.resolve_board_decision("d1", "pb")
        assert d.status == BoardDecisionStatus.REJECTED


# ===================================================================
# GOLDEN SCENARIO 2: Case evidence parallel review
# ===================================================================


class TestGoldenCaseEvidenceReview:
    def test_parallel_review_all_approved(self, engine):
        # Create packet
        packet = engine.create_review_packet(
            "evidence-pack-1", "tenant-legal",
            scope=CollaborationScope.CASE,
            review_mode=ReviewMode.PARALLEL,
            title="Case #42 Evidence Bundle",
        )
        assert packet.reviewer_count == 0

        # Assign 3 reviewers
        engine.assign_reviewer("evidence-pack-1", "rev-t1", "analyst-a",
                               title="Forensic review")
        engine.assign_reviewer("evidence-pack-1", "rev-t2", "analyst-b",
                               title="Chain of custody review")
        engine.assign_reviewer("evidence-pack-1", "rev-t3", "analyst-c",
                               title="Relevance review")
        pkt = engine.get_review_packet("evidence-pack-1")
        assert pkt.reviewer_count == 3

        # Complete reviews — all approved
        engine.complete_review("evidence-pack-1", "rev-t1", approved=True)
        engine.complete_review("evidence-pack-1", "rev-t2", approved=True)
        pkt = engine.complete_review("evidence-pack-1", "rev-t3", approved=True)

        assert pkt.reviews_completed == 3
        assert pkt.reviews_approved == 3
        assert pkt.reviewer_count == 3

        # All tasks completed
        for tid in ["rev-t1", "rev-t2", "rev-t3"]:
            assert engine.get_task(tid).status == HumanTaskStatus.COMPLETED

    def test_parallel_review_mixed_results(self, engine):
        _make_review_packet(engine, "pkt-mix", tenant_id="legal")
        engine.assign_reviewer("pkt-mix", "r1", "analyst-1")
        engine.assign_reviewer("pkt-mix", "r2", "analyst-2")
        engine.complete_review("pkt-mix", "r1", approved=True)
        pkt = engine.complete_review("pkt-mix", "r2", approved=False)
        assert pkt.reviews_completed == 2
        assert pkt.reviews_approved == 1

    def test_review_tasks_belong_to_tenant(self, engine):
        _make_review_packet(engine, "pkt1", tenant_id="legal-co")
        t = engine.assign_reviewer("pkt1", "r1", "analyst")
        assert t.tenant_id == "legal-co"


# ===================================================================
# GOLDEN SCENARIO 3: Executive override
# ===================================================================


class TestGoldenExecutiveOverride:
    def test_single_exec_override(self, engine):
        board = engine.create_approval_board(
            "exec-board", "tenant-acme", "Executive Override Board",
            approval_mode=ApprovalMode.OVERRIDE,
            scope=CollaborationScope.EXECUTIVE,
        )
        engine.add_board_member("exec-ceo", "exec-board", "ceo@acme",
                                role="executive")

        engine.record_vote("ev-1", "exec-board", "exec-ceo",
                           approved=True, reason="Emergency override")

        d = engine.resolve_board_decision("ed-1", "exec-board")
        assert d.status == BoardDecisionStatus.OVERRIDDEN
        assert d.decided_by == "board"

    def test_override_with_no_approval_pending(self, engine):
        engine.create_approval_board(
            "eb", "t", "Exec",
            approval_mode=ApprovalMode.OVERRIDE,
        )
        engine.add_board_member("em1", "eb", "exec1")
        engine.record_vote("ev1", "eb", "em1", approved=False)
        d = engine.resolve_board_decision("d1", "eb")
        assert d.status == BoardDecisionStatus.PENDING

    def test_override_cannot_be_escalated(self, engine):
        engine.create_approval_board(
            "eb", "t", "Exec",
            approval_mode=ApprovalMode.OVERRIDE,
        )
        engine.add_board_member("em1", "eb", "exec1")
        engine.record_vote("ev1", "eb", "em1", approved=True)
        engine.resolve_board_decision("d1", "eb")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate"):
            engine.escalate_decision("d1")


# ===================================================================
# GOLDEN SCENARIO 4: Service handoff round-trip
# ===================================================================


class TestGoldenServiceHandoff:
    def test_roundtrip_handoff(self, engine):
        # Runtime hands off to human
        h1 = engine.handoff_to_human(
            "ho-1", "tenant-support",
            scope=CollaborationScope.SERVICE,
            scope_ref_id="ticket-999",
            from_ref="runtime",
            to_ref="agent-bob",
            reason="Customer escalation",
        )
        assert h1.direction == "to_human"
        assert h1.from_ref == "runtime"
        assert h1.to_ref == "agent-bob"

        # Human hands off back to runtime
        h2 = engine.handoff_to_runtime(
            "ho-2", "tenant-support",
            scope=CollaborationScope.SERVICE,
            scope_ref_id="ticket-999",
            from_ref="agent-bob",
            to_ref="runtime",
            reason="Resolution applied, returning to automation",
        )
        assert h2.direction == "to_runtime"
        assert h2.from_ref == "agent-bob"
        assert h2.to_ref == "runtime"

        # Verify tenant filtering
        handoffs = engine.handoffs_for_tenant("tenant-support")
        assert len(handoffs) == 2

    def test_multiple_handoffs_different_tenants(self, engine):
        engine.handoff_to_human("h1", "t1")
        engine.handoff_to_human("h2", "t2")
        assert len(engine.handoffs_for_tenant("t1")) == 1
        assert len(engine.handoffs_for_tenant("t2")) == 1
        assert engine.handoff_count == 2


# ===================================================================
# GOLDEN SCENARIO 5: Missed SLA escalation + violation detection
# ===================================================================


class TestGoldenMissedSLAEscalation:
    def test_escalation_triggers_stale_violation(self, engine):
        # Create and escalate task
        _make_task(engine, "sla-task", tenant_id="tenant-ops",
                   assignee_ref="agent-1", title="Process SLA breach")
        engine.escalate_task("sla-task", escalation_ref="esc-mgr")

        # Detect violations
        violations = engine.detect_workflow_violations()
        esc_violations = [v for v in violations if v.operation == "stale_escalation"]
        assert len(esc_violations) == 1
        assert "sla-task" in esc_violations[0].reason

        # Reassign clears future detection
        engine.assign_task("sla-task", "manager-2")
        new_violations = engine.detect_workflow_violations()
        new_esc = [v for v in new_violations if v.operation == "stale_escalation"]
        assert len(new_esc) == 0

    def test_escalation_then_complete(self, engine):
        _make_task(engine, "t1")
        engine.escalate_task("t1")
        engine.assign_task("t1", "manager")
        engine.start_task("t1")
        t = engine.complete_task("t1")
        assert t.status == HumanTaskStatus.COMPLETED

    def test_multiple_escalated_tasks_multiple_violations(self, engine):
        for i in range(3):
            _make_task(engine, f"esc-{i}")
            engine.escalate_task(f"esc-{i}")
        violations = engine.detect_workflow_violations()
        esc_v = [v for v in violations if v.operation == "stale_escalation"]
        assert len(esc_v) == 3


# ===================================================================
# GOLDEN SCENARIO 6: Full lifecycle integration
# ===================================================================


class TestGoldenFullLifecycle:
    def test_comprehensive_lifecycle(self, engine):
        # --- Tasks ---
        t1 = _make_task(engine, "task-1", "tenant-main", "alice",
                        title="Investigate alert")
        t2 = _make_task(engine, "task-2", "tenant-main", "bob",
                        title="Verify fix")
        engine.assign_task("task-1", "alice")
        engine.start_task("task-1")
        engine.complete_task("task-1")
        engine.cancel_task("task-2")

        assert engine.task_count == 2

        # --- Review packet ---
        _make_review_packet(engine, "review-1", "tenant-main",
                            title="Alert review pack")
        engine.assign_reviewer("review-1", "rev-task-1", "reviewer-x")
        engine.assign_reviewer("review-1", "rev-task-2", "reviewer-y")
        engine.complete_review("review-1", "rev-task-1", approved=True)
        pkt = engine.complete_review("review-1", "rev-task-2", approved=True)
        assert pkt.reviews_completed == 2
        assert pkt.reviews_approved == 2
        assert engine.task_count == 4  # 2 original + 2 review tasks

        # --- Board + votes + decision ---
        engine.create_approval_board(
            "change-board", "tenant-main", "Change Advisory Board",
            approval_mode=ApprovalMode.QUORUM, quorum_required=2,
        )
        engine.add_board_member("cb-m1", "change-board", "director-a")
        engine.add_board_member("cb-m2", "change-board", "director-b")
        engine.add_board_member("cb-m3", "change-board", "director-c")

        engine.record_vote("cv-1", "change-board", "cb-m1",
                           scope_ref_id="change-req-1", approved=True)
        engine.record_vote("cv-2", "change-board", "cb-m2",
                           scope_ref_id="change-req-1", approved=True)
        decision = engine.resolve_board_decision(
            "cd-1", "change-board", scope_ref_id="change-req-1",
        )
        assert decision.status == BoardDecisionStatus.APPROVED

        # --- Handoffs ---
        engine.handoff_to_human("ho-1", "tenant-main",
                                scope_ref_id="incident-7",
                                to_ref="specialist")
        engine.handoff_to_runtime("ho-2", "tenant-main",
                                   scope_ref_id="incident-7",
                                   from_ref="specialist")

        # --- Violations ---
        # Create a board with no members to trigger violation
        engine.create_approval_board("empty-board", "tenant-main", "Empty")
        violations = engine.detect_workflow_violations()
        board_v = [v for v in violations if v.operation == "board_no_members"]
        assert len(board_v) == 1

        # --- Snapshot ---
        snap = engine.workflow_snapshot("final-snapshot")
        assert snap.total_tasks == 4
        assert snap.total_review_packets == 1
        assert snap.total_boards == 2
        assert snap.total_members == 3
        assert snap.total_votes == 2
        assert snap.total_decisions == 1
        assert snap.total_handoffs == 2
        assert snap.total_violations == 1

        # --- State hash ---
        h = engine.state_hash()
        assert len(h) == 64

    def test_lifecycle_state_hash_progression(self, engine):
        hashes = [engine.state_hash()]
        _make_task(engine, "t1")
        hashes.append(engine.state_hash())
        _make_review_packet(engine, "p1")
        hashes.append(engine.state_hash())
        _make_board(engine, "b1")
        hashes.append(engine.state_hash())
        engine.add_board_member("m1", "b1", "alice")
        hashes.append(engine.state_hash())
        engine.record_vote("v1", "b1", "m1")
        hashes.append(engine.state_hash())
        engine.resolve_board_decision("d1", "b1")
        hashes.append(engine.state_hash())
        engine.handoff_to_human("h1", "tenant-a")
        hashes.append(engine.state_hash())
        # All hashes should be different
        assert len(set(hashes)) == len(hashes)


# ===================================================================
# Additional edge cases
# ===================================================================


class TestEdgeCases:
    def test_many_tasks_same_tenant(self, engine):
        for i in range(20):
            _make_task(engine, f"t-{i}", tenant_id="bulk")
        assert len(engine.tasks_for_tenant("bulk")) == 20
        assert engine.task_count == 20

    def test_many_boards(self, engine):
        for i in range(10):
            _make_board(engine, f"b-{i}")
        assert engine.board_count == 10

    def test_vote_on_different_scopes_same_board(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", scope_ref_id="s1")
        engine.record_vote("v2", "b1", "m1", scope_ref_id="s2")
        engine.record_vote("v3", "b1", "m1", scope_ref_id="s3")
        assert engine.vote_count == 3

    def test_multiple_decisions_same_board_different_scopes(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", scope_ref_id="s1", approved=True)
        engine.record_vote("v2", "b1", "m1", scope_ref_id="s2", approved=False)
        d1 = engine.resolve_board_decision("d1", "b1", scope_ref_id="s1")
        d2 = engine.resolve_board_decision("d2", "b1", scope_ref_id="s2")
        assert d1.status == BoardDecisionStatus.APPROVED
        assert d2.status == BoardDecisionStatus.REJECTED
        decs = engine.decisions_for_board("b1")
        assert len(decs) == 2

    def test_get_task_reflects_latest_state(self, engine):
        _make_task(engine, "t1")
        assert engine.get_task("t1").status == HumanTaskStatus.PENDING
        engine.assign_task("t1", "bob")
        assert engine.get_task("t1").status == HumanTaskStatus.ASSIGNED
        engine.start_task("t1")
        assert engine.get_task("t1").status == HumanTaskStatus.IN_PROGRESS
        engine.complete_task("t1")
        assert engine.get_task("t1").status == HumanTaskStatus.COMPLETED

    def test_assign_reviewer_to_multiple_packets(self, engine):
        _make_review_packet(engine, "p1")
        _make_review_packet(engine, "p2")
        engine.assign_reviewer("p1", "rt1", "alice")
        engine.assign_reviewer("p2", "rt2", "bob")
        assert engine.task_count == 2

    def test_task_preserves_metadata_through_transitions(self, engine):
        _make_task(engine, "t1", scope_ref_id="ref-1", title="My task",
                   description="Details", scope=CollaborationScope.REGULATORY)
        engine.assign_task("t1", "bob")
        t = engine.get_task("t1")
        assert t.title == "My task"
        assert t.description == "Details"
        assert t.scope == CollaborationScope.REGULATORY
        assert t.scope_ref_id == "ref-1"

    def test_decision_decided_at_set(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        d = engine.resolve_board_decision("d1", "b1")
        assert d.decided_at != ""

    def test_handoff_handed_at_set(self, engine):
        h = engine.handoff_to_human("h1", "t1")
        assert h.handed_at != ""

    def test_violation_detected_at_set(self, engine):
        _make_board(engine, "b1")
        violations = engine.detect_workflow_violations()
        assert violations[0].detected_at != ""

    def test_snapshot_after_violations_reflects_count(self, engine):
        _make_board(engine, "b1")
        _make_board(engine, "b2")
        engine.detect_workflow_violations()
        snap = engine.workflow_snapshot("s1")
        assert snap.total_violations == 2

    def test_escalate_decision_preserves_board_id(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("d1", "b1")
        d = engine.escalate_decision("d1")
        assert d.board_id == "b1"

    def test_all_collaboration_scopes_accepted(self, engine):
        for i, scope in enumerate(CollaborationScope):
            _make_task(engine, f"t-{i}", scope=scope)
        assert engine.task_count == len(CollaborationScope)

    def test_all_approval_modes_accepted(self, engine):
        for i, mode in enumerate(ApprovalMode):
            _make_board(engine, f"b-{i}", approval_mode=mode)
        assert engine.board_count == len(ApprovalMode)

    def test_all_review_modes_accepted(self, engine):
        for i, mode in enumerate(ReviewMode):
            _make_review_packet(engine, f"p-{i}", review_mode=mode)
        assert engine.review_packet_count == len(ReviewMode)


# ===================================================================
# Terminal guard exhaustive matrix
# ===================================================================


class TestTerminalGuardMatrix:
    """Test that COMPLETED and CANCELLED block all transition methods."""

    @pytest.mark.parametrize("terminal_action", ["complete_task", "cancel_task"])
    @pytest.mark.parametrize("blocked_action", [
        "assign_task", "start_task", "complete_task", "cancel_task", "escalate_task",
    ])
    def test_terminal_blocks_all_transitions(self, engine, terminal_action, blocked_action):
        _make_task(engine, "t1")
        # Reach terminal state
        getattr(engine, terminal_action)("t1")
        # Try blocked transition
        with pytest.raises(RuntimeCoreInvariantError):
            if blocked_action == "assign_task":
                engine.assign_task("t1", "someone")
            elif blocked_action == "escalate_task":
                engine.escalate_task("t1")
            else:
                getattr(engine, blocked_action)("t1")


class TestDecisionTerminalGuardMatrix:
    """Test that terminal decisions block escalation."""

    @pytest.mark.parametrize("mode,approved,expected_status", [
        (ApprovalMode.SINGLE, True, BoardDecisionStatus.APPROVED),
        (ApprovalMode.SINGLE, False, BoardDecisionStatus.REJECTED),
        (ApprovalMode.OVERRIDE, True, BoardDecisionStatus.OVERRIDDEN),
    ])
    def test_terminal_decision_blocks_escalation(self, engine, mode, approved,
                                                  expected_status):
        engine.create_approval_board("b1", "t", "Board", approval_mode=mode)
        engine.add_board_member("m1", "b1", "alice")
        engine.record_vote("v1", "b1", "m1", approved=approved)
        d = engine.resolve_board_decision("d1", "b1")
        assert d.status == expected_status
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate"):
            engine.escalate_decision("d1")


# ===================================================================
# Duplicate ID exhaustive tests
# ===================================================================


class TestDuplicateIDExhaustive:
    def test_duplicate_task_id(self, engine):
        _make_task(engine, "dup")
        with pytest.raises(RuntimeCoreInvariantError):
            _make_task(engine, "dup")

    def test_duplicate_packet_id(self, engine):
        _make_review_packet(engine, "dup")
        with pytest.raises(RuntimeCoreInvariantError):
            _make_review_packet(engine, "dup")

    def test_duplicate_board_id(self, engine):
        _make_board(engine, "dup")
        with pytest.raises(RuntimeCoreInvariantError):
            _make_board(engine, "dup")

    def test_duplicate_member_id(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("dup", "b1", "alice")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_board_member("dup", "b1", "bob")

    def test_duplicate_vote_id(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.add_board_member("m2", "b1", "bob")
        engine.record_vote("dup", "b1", "m1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_vote("dup", "b1", "m2")

    def test_duplicate_decision_id(self, engine):
        _make_board(engine, "b1")
        engine.add_board_member("m1", "b1", "alice")
        engine.resolve_board_decision("dup", "b1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resolve_board_decision("dup", "b1")

    def test_duplicate_handoff_id_same_direction(self, engine):
        engine.handoff_to_human("dup", "t")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.handoff_to_human("dup", "t")

    def test_duplicate_handoff_id_cross_direction(self, engine):
        engine.handoff_to_human("dup", "t")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.handoff_to_runtime("dup", "t", from_ref="bob")

    def test_duplicate_snapshot_id(self, engine):
        engine.workflow_snapshot("dup")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.workflow_snapshot("dup")


# ===================================================================
# Unknown entity lookups
# ===================================================================


class TestUnknownEntityLookups:
    def test_get_task_unknown(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_task("x")

    def test_get_review_packet_unknown(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_review_packet("x")

    def test_get_board_unknown(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_board("x")

    def test_get_decision_unknown(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_decision("x")

    def test_get_handoff_unknown(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_handoff("x")
