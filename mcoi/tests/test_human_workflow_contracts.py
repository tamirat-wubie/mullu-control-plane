"""Comprehensive tests for mcoi_runtime.contracts.human_workflow contracts."""

from __future__ import annotations

import json
from typing import Mapping

import pytest

from mcoi_runtime.contracts.human_workflow import (
    ApprovalBoard,
    ApprovalMode,
    BoardDecisionStatus,
    BoardMember,
    BoardVote,
    CollaborationScope,
    CollaborativeDecision,
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TS = "2025-06-01T00:00:00+00:00"
TS2 = "2025-07-15T12:30:00Z"
BAD_DT = "not-a-date"


# ===================================================================
# Enum tests
# ===================================================================


class TestHumanTaskStatus:
    def test_member_count(self):
        assert len(HumanTaskStatus) == 6

    @pytest.mark.parametrize(
        "member,value",
        [
            (HumanTaskStatus.PENDING, "pending"),
            (HumanTaskStatus.ASSIGNED, "assigned"),
            (HumanTaskStatus.IN_PROGRESS, "in_progress"),
            (HumanTaskStatus.COMPLETED, "completed"),
            (HumanTaskStatus.CANCELLED, "cancelled"),
            (HumanTaskStatus.ESCALATED, "escalated"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    def test_lookup_by_value(self):
        assert HumanTaskStatus("pending") is HumanTaskStatus.PENDING

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            HumanTaskStatus("nonexistent")


class TestReviewMode:
    def test_member_count(self):
        assert len(ReviewMode) == 3

    @pytest.mark.parametrize(
        "member,value",
        [
            (ReviewMode.SINGLE, "single"),
            (ReviewMode.PARALLEL, "parallel"),
            (ReviewMode.SEQUENTIAL, "sequential"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    def test_lookup(self):
        assert ReviewMode("parallel") is ReviewMode.PARALLEL


class TestApprovalMode:
    def test_member_count(self):
        assert len(ApprovalMode) == 4

    @pytest.mark.parametrize(
        "member,value",
        [
            (ApprovalMode.SINGLE, "single"),
            (ApprovalMode.QUORUM, "quorum"),
            (ApprovalMode.UNANIMOUS, "unanimous"),
            (ApprovalMode.OVERRIDE, "override"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value


class TestBoardDecisionStatus:
    def test_member_count(self):
        assert len(BoardDecisionStatus) == 5

    @pytest.mark.parametrize(
        "member,value",
        [
            (BoardDecisionStatus.PENDING, "pending"),
            (BoardDecisionStatus.APPROVED, "approved"),
            (BoardDecisionStatus.REJECTED, "rejected"),
            (BoardDecisionStatus.ESCALATED, "escalated"),
            (BoardDecisionStatus.OVERRIDDEN, "overridden"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value


class TestEscalationDisposition:
    def test_member_count(self):
        assert len(EscalationDisposition) == 4

    @pytest.mark.parametrize(
        "member,value",
        [
            (EscalationDisposition.PENDING, "pending"),
            (EscalationDisposition.RESOLVED, "resolved"),
            (EscalationDisposition.REASSIGNED, "reassigned"),
            (EscalationDisposition.EXPIRED, "expired"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value


class TestCollaborationScope:
    def test_member_count(self):
        assert len(CollaborationScope) == 6

    @pytest.mark.parametrize(
        "member,value",
        [
            (CollaborationScope.CHANGE, "change"),
            (CollaborationScope.CASE, "case"),
            (CollaborationScope.PROCUREMENT, "procurement"),
            (CollaborationScope.SERVICE, "service"),
            (CollaborationScope.REGULATORY, "regulatory"),
            (CollaborationScope.EXECUTIVE, "executive"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value


# ===================================================================
# HumanTaskRecord
# ===================================================================


def _task(**kw):
    defaults = dict(
        task_id="t1",
        tenant_id="ten1",
        assignee_ref="user-a",
        status=HumanTaskStatus.PENDING,
        scope=CollaborationScope.CHANGE,
        scope_ref_id="ref1",
        title="Fix bug",
        description="desc",
        due_at=TS,
        created_at=TS,
    )
    defaults.update(kw)
    return HumanTaskRecord(**defaults)


class TestHumanTaskRecord:
    def test_valid_construction(self):
        r = _task()
        assert r.task_id == "t1"
        assert r.tenant_id == "ten1"
        assert r.assignee_ref == "user-a"
        assert r.status is HumanTaskStatus.PENDING
        assert r.scope is CollaborationScope.CHANGE
        assert r.title == "Fix bug"

    def test_frozen(self):
        r = _task()
        with pytest.raises(AttributeError):
            r.task_id = "other"

    def test_metadata_is_mapping(self):
        r = _task(metadata={"k": "v"})
        assert isinstance(r.metadata, Mapping)
        assert r.metadata["k"] == "v"
        with pytest.raises(TypeError):
            r.metadata["k2"] = "v2"

    def test_empty_metadata_default(self):
        r = _task()
        assert isinstance(r.metadata, Mapping)
        assert len(r.metadata) == 0

    def test_to_dict(self):
        r = _task()
        d = r.to_dict()
        assert isinstance(d, dict)
        # Enums preserved as enum objects
        assert d["status"] is HumanTaskStatus.PENDING
        assert d["scope"] is CollaborationScope.CHANGE

    # --- invalid inputs ---
    def test_empty_task_id(self):
        with pytest.raises(ValueError):
            _task(task_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _task(tenant_id="")

    def test_empty_assignee_ref(self):
        with pytest.raises(ValueError):
            _task(assignee_ref="")

    def test_empty_title(self):
        with pytest.raises(ValueError):
            _task(title="")

    def test_whitespace_title(self):
        with pytest.raises(ValueError):
            _task(title="   ")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            _task(status="pending")

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError):
            _task(scope="change")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _task(created_at=BAD_DT)

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _task(created_at="")

    def test_all_statuses(self):
        for s in HumanTaskStatus:
            r = _task(status=s)
            assert r.status is s

    def test_all_scopes(self):
        for s in CollaborationScope:
            r = _task(scope=s)
            assert r.scope is s


# ===================================================================
# ReviewPacket
# ===================================================================


def _review(**kw):
    defaults = dict(
        packet_id="p1",
        tenant_id="ten1",
        scope=CollaborationScope.CASE,
        scope_ref_id="ref1",
        review_mode=ReviewMode.SINGLE,
        title="Review A",
        reviewer_count=3,
        reviews_completed=2,
        reviews_approved=1,
        created_at=TS,
    )
    defaults.update(kw)
    return ReviewPacket(**defaults)


class TestReviewPacket:
    def test_valid(self):
        r = _review()
        assert r.packet_id == "p1"
        assert r.reviewer_count == 3
        assert r.reviews_completed == 2
        assert r.reviews_approved == 1
        assert r.review_mode is ReviewMode.SINGLE

    def test_frozen(self):
        r = _review()
        with pytest.raises(AttributeError):
            r.packet_id = "x"

    def test_metadata_mapping(self):
        r = _review(metadata={"a": 1})
        assert isinstance(r.metadata, Mapping)

    def test_to_dict_preserves_enums(self):
        r = _review()
        d = r.to_dict()
        assert d["scope"] is CollaborationScope.CASE
        assert d["review_mode"] is ReviewMode.SINGLE

    def test_zero_counts_valid(self):
        r = _review(reviewer_count=0, reviews_completed=0, reviews_approved=0)
        assert r.reviewer_count == 0

    def test_empty_packet_id(self):
        with pytest.raises(ValueError):
            _review(packet_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _review(tenant_id="")

    def test_empty_title(self):
        with pytest.raises(ValueError):
            _review(title="")

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError):
            _review(scope="case")

    def test_invalid_review_mode_type(self):
        with pytest.raises(ValueError):
            _review(review_mode="single")

    def test_negative_reviewer_count(self):
        with pytest.raises(ValueError):
            _review(reviewer_count=-1)

    def test_negative_reviews_completed(self):
        with pytest.raises(ValueError):
            _review(reviews_completed=-1)

    def test_negative_reviews_approved(self):
        with pytest.raises(ValueError):
            _review(reviews_approved=-1)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _review(created_at=BAD_DT)

    def test_all_review_modes(self):
        for m in ReviewMode:
            r = _review(review_mode=m)
            assert r.review_mode is m


# ===================================================================
# ApprovalBoard
# ===================================================================


def _board(**kw):
    defaults = dict(
        board_id="b1",
        tenant_id="ten1",
        name="Board Alpha",
        approval_mode=ApprovalMode.QUORUM,
        quorum_required=2,
        scope=CollaborationScope.PROCUREMENT,
        scope_ref_id="ref1",
        member_count=5,
        created_at=TS,
    )
    defaults.update(kw)
    return ApprovalBoard(**defaults)


class TestApprovalBoard:
    def test_valid(self):
        r = _board()
        assert r.board_id == "b1"
        assert r.quorum_required == 2
        assert r.member_count == 5
        assert r.approval_mode is ApprovalMode.QUORUM

    def test_frozen(self):
        r = _board()
        with pytest.raises(AttributeError):
            r.board_id = "x"

    def test_metadata_mapping(self):
        r = _board(metadata={"x": "y"})
        assert isinstance(r.metadata, Mapping)

    def test_to_dict_preserves_enums(self):
        d = _board().to_dict()
        assert d["approval_mode"] is ApprovalMode.QUORUM
        assert d["scope"] is CollaborationScope.PROCUREMENT

    def test_quorum_required_minimum_1(self):
        r = _board(quorum_required=1)
        assert r.quorum_required == 1

    def test_quorum_required_zero_raises(self):
        with pytest.raises(ValueError):
            _board(quorum_required=0)

    def test_quorum_required_negative_raises(self):
        with pytest.raises(ValueError):
            _board(quorum_required=-1)

    def test_member_count_zero_valid(self):
        r = _board(member_count=0)
        assert r.member_count == 0

    def test_member_count_negative_raises(self):
        with pytest.raises(ValueError):
            _board(member_count=-1)

    def test_empty_board_id(self):
        with pytest.raises(ValueError):
            _board(board_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _board(tenant_id="")

    def test_empty_name(self):
        with pytest.raises(ValueError):
            _board(name="")

    def test_invalid_approval_mode_type(self):
        with pytest.raises(ValueError):
            _board(approval_mode="quorum")

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError):
            _board(scope="procurement")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _board(created_at=BAD_DT)

    def test_all_approval_modes(self):
        for m in ApprovalMode:
            r = _board(approval_mode=m)
            assert r.approval_mode is m


# ===================================================================
# BoardMember
# ===================================================================


def _member(**kw):
    defaults = dict(
        member_id="m1",
        board_id="b1",
        identity_ref="id-ref-1",
        role="reviewer",
        added_at=TS,
    )
    defaults.update(kw)
    return BoardMember(**defaults)


class TestBoardMember:
    def test_valid(self):
        r = _member()
        assert r.member_id == "m1"
        assert r.role == "reviewer"

    def test_frozen(self):
        r = _member()
        with pytest.raises(AttributeError):
            r.member_id = "x"

    def test_metadata_mapping(self):
        r = _member(metadata={"z": 1})
        assert isinstance(r.metadata, Mapping)

    def test_to_dict(self):
        d = _member().to_dict()
        assert isinstance(d, dict)
        assert d["member_id"] == "m1"

    def test_to_json(self):
        j = _member().to_json()
        parsed = json.loads(j)
        assert parsed["member_id"] == "m1"

    def test_empty_member_id(self):
        with pytest.raises(ValueError):
            _member(member_id="")

    def test_empty_board_id(self):
        with pytest.raises(ValueError):
            _member(board_id="")

    def test_empty_identity_ref(self):
        with pytest.raises(ValueError):
            _member(identity_ref="")

    def test_empty_role(self):
        with pytest.raises(ValueError):
            _member(role="")

    def test_whitespace_role(self):
        with pytest.raises(ValueError):
            _member(role="   ")

    def test_invalid_added_at(self):
        with pytest.raises(ValueError):
            _member(added_at=BAD_DT)

    def test_empty_added_at(self):
        with pytest.raises(ValueError):
            _member(added_at="")


# ===================================================================
# BoardVote
# ===================================================================


def _vote(**kw):
    defaults = dict(
        vote_id="v1",
        board_id="b1",
        member_id="m1",
        scope_ref_id="ref1",
        approved=True,
        reason="looks good",
        voted_at=TS,
    )
    defaults.update(kw)
    return BoardVote(**defaults)


class TestBoardVote:
    def test_valid_approved(self):
        r = _vote(approved=True)
        assert r.approved is True

    def test_valid_rejected(self):
        r = _vote(approved=False)
        assert r.approved is False

    def test_frozen(self):
        r = _vote()
        with pytest.raises(AttributeError):
            r.approved = False

    def test_metadata_mapping(self):
        r = _vote(metadata={"q": "r"})
        assert isinstance(r.metadata, Mapping)

    def test_to_dict(self):
        d = _vote().to_dict()
        assert isinstance(d, dict)
        assert d["approved"] is True

    def test_empty_vote_id(self):
        with pytest.raises(ValueError):
            _vote(vote_id="")

    def test_empty_board_id(self):
        with pytest.raises(ValueError):
            _vote(board_id="")

    def test_empty_member_id(self):
        with pytest.raises(ValueError):
            _vote(member_id="")

    def test_invalid_voted_at(self):
        with pytest.raises(ValueError):
            _vote(voted_at=BAD_DT)

    # approved must be bool
    def test_approved_int_raises(self):
        with pytest.raises(ValueError):
            _vote(approved=1)

    def test_approved_zero_raises(self):
        with pytest.raises(ValueError):
            _vote(approved=0)

    def test_approved_string_raises(self):
        with pytest.raises(ValueError):
            _vote(approved="yes")

    def test_approved_none_raises(self):
        with pytest.raises(ValueError):
            _vote(approved=None)


# ===================================================================
# CollaborativeDecision
# ===================================================================


def _decision(**kw):
    defaults = dict(
        decision_id="d1",
        board_id="b1",
        scope_ref_id="ref1",
        status=BoardDecisionStatus.APPROVED,
        total_votes=5,
        approvals=4,
        rejections=1,
        decided_by="user-x",
        decided_at=TS,
    )
    defaults.update(kw)
    return CollaborativeDecision(**defaults)


class TestCollaborativeDecision:
    def test_valid(self):
        r = _decision()
        assert r.decision_id == "d1"
        assert r.total_votes == 5
        assert r.status is BoardDecisionStatus.APPROVED

    def test_frozen(self):
        r = _decision()
        with pytest.raises(AttributeError):
            r.decision_id = "x"

    def test_metadata_mapping(self):
        r = _decision(metadata={"a": "b"})
        assert isinstance(r.metadata, Mapping)

    def test_to_dict_preserves_enums(self):
        d = _decision().to_dict()
        assert d["status"] is BoardDecisionStatus.APPROVED

    def test_zero_votes_valid(self):
        r = _decision(total_votes=0, approvals=0, rejections=0)
        assert r.total_votes == 0

    def test_empty_decision_id(self):
        with pytest.raises(ValueError):
            _decision(decision_id="")

    def test_empty_board_id(self):
        with pytest.raises(ValueError):
            _decision(board_id="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            _decision(status="approved")

    def test_negative_total_votes(self):
        with pytest.raises(ValueError):
            _decision(total_votes=-1)

    def test_negative_approvals(self):
        with pytest.raises(ValueError):
            _decision(approvals=-1)

    def test_negative_rejections(self):
        with pytest.raises(ValueError):
            _decision(rejections=-1)

    def test_invalid_decided_at(self):
        with pytest.raises(ValueError):
            _decision(decided_at=BAD_DT)

    def test_all_decision_statuses(self):
        for s in BoardDecisionStatus:
            r = _decision(status=s)
            assert r.status is s


# ===================================================================
# HandoffPacket
# ===================================================================


def _handoff(**kw):
    defaults = dict(
        handoff_id="h1",
        tenant_id="ten1",
        scope=CollaborationScope.SERVICE,
        scope_ref_id="ref1",
        from_ref="agent-a",
        to_ref="user-b",
        direction="agent_to_human",
        reason="needs approval",
        handed_at=TS,
    )
    defaults.update(kw)
    return HandoffPacket(**defaults)


class TestHandoffPacket:
    def test_valid(self):
        r = _handoff()
        assert r.handoff_id == "h1"
        assert r.scope is CollaborationScope.SERVICE
        assert r.direction == "agent_to_human"

    def test_frozen(self):
        r = _handoff()
        with pytest.raises(AttributeError):
            r.handoff_id = "x"

    def test_metadata_mapping(self):
        r = _handoff(metadata={"m": 1})
        assert isinstance(r.metadata, Mapping)

    def test_to_dict_preserves_enums(self):
        d = _handoff().to_dict()
        assert d["scope"] is CollaborationScope.SERVICE

    def test_empty_handoff_id(self):
        with pytest.raises(ValueError):
            _handoff(handoff_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _handoff(tenant_id="")

    def test_empty_from_ref(self):
        with pytest.raises(ValueError):
            _handoff(from_ref="")

    def test_empty_to_ref(self):
        with pytest.raises(ValueError):
            _handoff(to_ref="")

    def test_empty_direction(self):
        with pytest.raises(ValueError):
            _handoff(direction="")

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError):
            _handoff(scope="service")

    def test_invalid_handed_at(self):
        with pytest.raises(ValueError):
            _handoff(handed_at=BAD_DT)

    def test_all_scopes(self):
        for s in CollaborationScope:
            r = _handoff(scope=s)
            assert r.scope is s


# ===================================================================
# HumanWorkflowSnapshot
# ===================================================================


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="s1",
        total_tasks=10,
        total_review_packets=5,
        total_boards=3,
        total_members=12,
        total_votes=20,
        total_decisions=4,
        total_handoffs=2,
        total_violations=1,
        captured_at=TS,
    )
    defaults.update(kw)
    return HumanWorkflowSnapshot(**defaults)


class TestHumanWorkflowSnapshot:
    def test_valid(self):
        r = _snapshot()
        assert r.snapshot_id == "s1"
        assert r.total_tasks == 10

    def test_frozen(self):
        r = _snapshot()
        with pytest.raises(AttributeError):
            r.snapshot_id = "x"

    def test_metadata_mapping(self):
        r = _snapshot(metadata={"k": "v"})
        assert isinstance(r.metadata, Mapping)

    def test_to_dict(self):
        d = _snapshot().to_dict()
        assert isinstance(d, dict)
        assert d["snapshot_id"] == "s1"

    def test_to_json(self):
        j = _snapshot().to_json()
        parsed = json.loads(j)
        assert parsed["snapshot_id"] == "s1"
        assert parsed["total_tasks"] == 10

    def test_all_zeros_valid(self):
        r = _snapshot(
            total_tasks=0,
            total_review_packets=0,
            total_boards=0,
            total_members=0,
            total_votes=0,
            total_decisions=0,
            total_handoffs=0,
            total_violations=0,
        )
        assert r.total_tasks == 0

    def test_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_tasks",
            "total_review_packets",
            "total_boards",
            "total_members",
            "total_votes",
            "total_decisions",
            "total_handoffs",
            "total_violations",
        ],
    )
    def test_negative_counts(self, field_name):
        with pytest.raises(ValueError):
            _snapshot(**{field_name: -1})

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at=BAD_DT)


# ===================================================================
# HumanWorkflowViolation
# ===================================================================


def _violation(**kw):
    defaults = dict(
        violation_id="viol1",
        tenant_id="ten1",
        scope_ref_id="ref1",
        operation="create_task",
        reason="unauthorized",
        detected_at=TS,
    )
    defaults.update(kw)
    return HumanWorkflowViolation(**defaults)


class TestHumanWorkflowViolation:
    def test_valid(self):
        r = _violation()
        assert r.violation_id == "viol1"
        assert r.operation == "create_task"

    def test_frozen(self):
        r = _violation()
        with pytest.raises(AttributeError):
            r.violation_id = "x"

    def test_metadata_mapping(self):
        r = _violation(metadata={"a": 1})
        assert isinstance(r.metadata, Mapping)

    def test_to_dict(self):
        d = _violation().to_dict()
        assert isinstance(d, dict)
        assert d["violation_id"] == "viol1"

    def test_to_json(self):
        j = _violation().to_json()
        parsed = json.loads(j)
        assert parsed["violation_id"] == "viol1"

    def test_empty_violation_id(self):
        with pytest.raises(ValueError):
            _violation(violation_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _violation(tenant_id="")

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            _violation(operation="")

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            _violation(reason="")

    def test_whitespace_operation(self):
        with pytest.raises(ValueError):
            _violation(operation="   ")

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            _violation(detected_at=BAD_DT)

    def test_empty_detected_at(self):
        with pytest.raises(ValueError):
            _violation(detected_at="")


# ===================================================================
# HumanWorkflowClosureReport
# ===================================================================


def _closure(**kw):
    defaults = dict(
        report_id="r1",
        tenant_id="ten1",
        total_tasks=10,
        total_review_packets=5,
        total_boards=3,
        total_decisions_approved=8,
        total_decisions_rejected=2,
        total_handoffs=4,
        total_violations=1,
        closed_at=TS,
    )
    defaults.update(kw)
    return HumanWorkflowClosureReport(**defaults)


class TestHumanWorkflowClosureReport:
    def test_valid(self):
        r = _closure()
        assert r.report_id == "r1"
        assert r.total_tasks == 10
        assert r.total_decisions_approved == 8

    def test_frozen(self):
        r = _closure()
        with pytest.raises(AttributeError):
            r.report_id = "x"

    def test_metadata_mapping(self):
        r = _closure(metadata={"k": "v"})
        assert isinstance(r.metadata, Mapping)

    def test_to_dict(self):
        d = _closure().to_dict()
        assert isinstance(d, dict)
        assert d["report_id"] == "r1"

    def test_to_json(self):
        j = _closure().to_json()
        parsed = json.loads(j)
        assert parsed["report_id"] == "r1"
        assert parsed["total_tasks"] == 10

    def test_all_zeros_valid(self):
        r = _closure(
            total_tasks=0,
            total_review_packets=0,
            total_boards=0,
            total_decisions_approved=0,
            total_decisions_rejected=0,
            total_handoffs=0,
            total_violations=0,
        )
        assert r.total_tasks == 0

    def test_empty_report_id(self):
        with pytest.raises(ValueError):
            _closure(report_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _closure(tenant_id="")

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_tasks",
            "total_review_packets",
            "total_boards",
            "total_decisions_approved",
            "total_decisions_rejected",
            "total_handoffs",
            "total_violations",
        ],
    )
    def test_negative_counts(self, field_name):
        with pytest.raises(ValueError):
            _closure(**{field_name: -1})

    def test_invalid_closed_at(self):
        with pytest.raises(ValueError):
            _closure(closed_at=BAD_DT)

    def test_empty_closed_at(self):
        with pytest.raises(ValueError):
            _closure(closed_at="")


# ===================================================================
# Cross-cutting: additional immutability and edge-case tests
# ===================================================================


class TestImmutabilityAllDataclasses:
    """Verify frozen=True across every dataclass."""

    def test_task_setattr(self):
        with pytest.raises(AttributeError):
            _task().tenant_id = "x"

    def test_review_setattr(self):
        with pytest.raises(AttributeError):
            _review().tenant_id = "x"

    def test_board_setattr(self):
        with pytest.raises(AttributeError):
            _board().tenant_id = "x"

    def test_member_setattr(self):
        with pytest.raises(AttributeError):
            _member().board_id = "x"

    def test_vote_setattr(self):
        with pytest.raises(AttributeError):
            _vote().board_id = "x"

    def test_decision_setattr(self):
        with pytest.raises(AttributeError):
            _decision().board_id = "x"

    def test_handoff_setattr(self):
        with pytest.raises(AttributeError):
            _handoff().tenant_id = "x"

    def test_snapshot_setattr(self):
        with pytest.raises(AttributeError):
            _snapshot().total_tasks = 99

    def test_violation_setattr(self):
        with pytest.raises(AttributeError):
            _violation().tenant_id = "x"

    def test_closure_setattr(self):
        with pytest.raises(AttributeError):
            _closure().tenant_id = "x"


class TestMetadataFrozenAllDataclasses:
    """Verify metadata is frozen (MappingProxyType) for every dataclass."""

    def test_task_metadata_frozen(self):
        r = _task(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_review_metadata_frozen(self):
        r = _review(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_board_metadata_frozen(self):
        r = _board(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_member_metadata_frozen(self):
        r = _member(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_vote_metadata_frozen(self):
        r = _vote(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_decision_metadata_frozen(self):
        r = _decision(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_handoff_metadata_frozen(self):
        r = _handoff(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_snapshot_metadata_frozen(self):
        r = _snapshot(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_violation_metadata_frozen(self):
        r = _violation(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_closure_metadata_frozen(self):
        r = _closure(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2


class TestToDictReturnsDict:
    """Ensure to_dict returns a plain dict for every dataclass."""

    def test_task(self):
        assert isinstance(_task().to_dict(), dict)

    def test_review(self):
        assert isinstance(_review().to_dict(), dict)

    def test_board(self):
        assert isinstance(_board().to_dict(), dict)

    def test_member(self):
        assert isinstance(_member().to_dict(), dict)

    def test_vote(self):
        assert isinstance(_vote().to_dict(), dict)

    def test_decision(self):
        assert isinstance(_decision().to_dict(), dict)

    def test_handoff(self):
        assert isinstance(_handoff().to_dict(), dict)

    def test_snapshot(self):
        assert isinstance(_snapshot().to_dict(), dict)

    def test_violation(self):
        assert isinstance(_violation().to_dict(), dict)

    def test_closure(self):
        assert isinstance(_closure().to_dict(), dict)


class TestDatetimeWithZ:
    """ISO datetimes ending with Z should be accepted."""

    def test_task_z_suffix(self):
        r = _task(created_at=TS2)
        assert r.created_at == TS2

    def test_review_z_suffix(self):
        r = _review(created_at=TS2)
        assert r.created_at == TS2

    def test_board_z_suffix(self):
        r = _board(created_at=TS2)
        assert r.created_at == TS2

    def test_member_z_suffix(self):
        r = _member(added_at=TS2)
        assert r.added_at == TS2

    def test_vote_z_suffix(self):
        r = _vote(voted_at=TS2)
        assert r.voted_at == TS2

    def test_decision_z_suffix(self):
        r = _decision(decided_at=TS2)
        assert r.decided_at == TS2

    def test_handoff_z_suffix(self):
        r = _handoff(handed_at=TS2)
        assert r.handed_at == TS2

    def test_snapshot_z_suffix(self):
        r = _snapshot(captured_at=TS2)
        assert r.captured_at == TS2

    def test_violation_z_suffix(self):
        r = _violation(detected_at=TS2)
        assert r.detected_at == TS2

    def test_closure_z_suffix(self):
        r = _closure(closed_at=TS2)
        assert r.closed_at == TS2


class TestNestedMetadata:
    """Test that nested metadata dicts are also frozen."""

    def test_nested_dict_frozen(self):
        r = _task(metadata={"outer": {"inner": 1}})
        assert isinstance(r.metadata["outer"], Mapping)
        with pytest.raises(TypeError):
            r.metadata["outer"]["new_key"] = 2

    def test_nested_list_becomes_tuple(self):
        r = _task(metadata={"items": [1, 2, 3]})
        assert isinstance(r.metadata["items"], tuple)
        assert r.metadata["items"] == (1, 2, 3)


class TestToDictMetadataThawed:
    """to_dict should thaw metadata back to plain dict."""

    def test_metadata_thawed_to_dict(self):
        r = _task(metadata={"k": "v"})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_nested_metadata_thawed(self):
        r = _task(metadata={"outer": {"inner": 1}})
        d = r.to_dict()
        assert isinstance(d["metadata"]["outer"], dict)


class TestEdgeCaseDatetimes:
    """Various valid ISO datetime formats."""

    def test_date_only(self):
        # Python 3.11+ fromisoformat accepts date-only
        r = _task(created_at="2025-06-01")
        assert r.created_at == "2025-06-01"

    def test_datetime_with_microseconds(self):
        r = _task(created_at="2025-06-01T12:00:00.123456+00:00")
        assert "123456" in r.created_at

    def test_not_a_date_raises(self):
        with pytest.raises(ValueError):
            _task(created_at="not-a-date")


class TestEnumNotString:
    """Enums passed as strings should be rejected."""

    def test_task_status_string(self):
        with pytest.raises(ValueError):
            _task(status="pending")

    def test_task_scope_string(self):
        with pytest.raises(ValueError):
            _task(scope="change")

    def test_review_scope_string(self):
        with pytest.raises(ValueError):
            _review(scope="case")

    def test_review_mode_string(self):
        with pytest.raises(ValueError):
            _review(review_mode="single")

    def test_board_approval_mode_string(self):
        with pytest.raises(ValueError):
            _board(approval_mode="quorum")

    def test_board_scope_string(self):
        with pytest.raises(ValueError):
            _board(scope="change")

    def test_decision_status_string(self):
        with pytest.raises(ValueError):
            _decision(status="approved")

    def test_handoff_scope_string(self):
        with pytest.raises(ValueError):
            _handoff(scope="service")


class TestEnumNotInt:
    """Enums passed as ints should be rejected."""

    def test_task_status_int(self):
        with pytest.raises(ValueError):
            _task(status=0)

    def test_review_mode_int(self):
        with pytest.raises(ValueError):
            _review(review_mode=1)

    def test_board_approval_mode_int(self):
        with pytest.raises(ValueError):
            _board(approval_mode=2)

    def test_decision_status_int(self):
        with pytest.raises(ValueError):
            _decision(status=3)

    def test_handoff_scope_int(self):
        with pytest.raises(ValueError):
            _handoff(scope=4)


class TestNonIntegerCounts:
    """Float or bool values for int fields should raise."""

    def test_review_count_float(self):
        with pytest.raises(ValueError):
            _review(reviewer_count=1.5)

    def test_review_count_bool(self):
        with pytest.raises(ValueError):
            _review(reviewer_count=True)

    def test_board_member_count_float(self):
        with pytest.raises(ValueError):
            _board(member_count=2.0)

    def test_board_quorum_bool(self):
        with pytest.raises(ValueError):
            _board(quorum_required=True)

    def test_decision_total_votes_float(self):
        with pytest.raises(ValueError):
            _decision(total_votes=1.0)

    def test_snapshot_total_tasks_bool(self):
        with pytest.raises(ValueError):
            _snapshot(total_tasks=True)

    def test_closure_total_tasks_float(self):
        with pytest.raises(ValueError):
            _closure(total_tasks=1.0)


class TestToDictFieldCompleteness:
    """Verify to_dict includes all fields."""

    def test_task_all_fields(self):
        d = _task().to_dict()
        expected = {
            "task_id", "tenant_id", "assignee_ref", "status", "scope",
            "scope_ref_id", "title", "description", "due_at", "created_at",
            "metadata",
        }
        assert set(d.keys()) == expected

    def test_review_all_fields(self):
        d = _review().to_dict()
        expected = {
            "packet_id", "tenant_id", "scope", "scope_ref_id", "review_mode",
            "title", "reviewer_count", "reviews_completed", "reviews_approved",
            "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_board_all_fields(self):
        d = _board().to_dict()
        expected = {
            "board_id", "tenant_id", "name", "approval_mode", "quorum_required",
            "scope", "scope_ref_id", "member_count", "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_member_all_fields(self):
        d = _member().to_dict()
        expected = {
            "member_id", "board_id", "identity_ref", "role", "added_at",
            "metadata",
        }
        assert set(d.keys()) == expected

    def test_vote_all_fields(self):
        d = _vote().to_dict()
        expected = {
            "vote_id", "board_id", "member_id", "scope_ref_id", "approved",
            "reason", "voted_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_decision_all_fields(self):
        d = _decision().to_dict()
        expected = {
            "decision_id", "board_id", "scope_ref_id", "status", "total_votes",
            "approvals", "rejections", "decided_by", "decided_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_handoff_all_fields(self):
        d = _handoff().to_dict()
        expected = {
            "handoff_id", "tenant_id", "scope", "scope_ref_id", "from_ref",
            "to_ref", "direction", "reason", "handed_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_snapshot_all_fields(self):
        d = _snapshot().to_dict()
        expected = {
            "snapshot_id", "total_tasks", "total_review_packets", "total_boards",
            "total_members", "total_votes", "total_decisions", "total_handoffs",
            "total_violations", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_violation_all_fields(self):
        d = _violation().to_dict()
        expected = {
            "violation_id", "tenant_id", "scope_ref_id", "operation", "reason",
            "detected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_closure_all_fields(self):
        d = _closure().to_dict()
        expected = {
            "report_id", "tenant_id", "total_tasks", "total_review_packets",
            "total_boards", "total_decisions_approved", "total_decisions_rejected",
            "total_handoffs", "total_violations", "closed_at", "metadata",
        }
        assert set(d.keys()) == expected


class TestToJsonNoEnums:
    """to_json works for dataclasses without enum fields."""

    def test_snapshot_to_json(self):
        j = _snapshot().to_json()
        parsed = json.loads(j)
        assert parsed["snapshot_id"] == "s1"

    def test_violation_to_json(self):
        j = _violation().to_json()
        parsed = json.loads(j)
        assert parsed["operation"] == "create_task"

    def test_closure_to_json(self):
        j = _closure().to_json()
        parsed = json.loads(j)
        assert parsed["total_decisions_approved"] == 8

    def test_member_to_json(self):
        j = _member().to_json()
        parsed = json.loads(j)
        assert parsed["role"] == "reviewer"


class TestLargeMetadata:
    """Metadata with many keys or nested structures."""

    def test_many_keys(self):
        big = {f"key_{i}": i for i in range(100)}
        r = _task(metadata=big)
        assert len(r.metadata) == 100

    def test_deeply_nested(self):
        nested = {"a": {"b": {"c": {"d": 42}}}}
        r = _task(metadata=nested)
        assert r.metadata["a"]["b"]["c"]["d"] == 42
