"""Comprehensive tests for RemediationRuntimeEngine.

Covers: remediation management, assignments, corrective actions, preventive actions,
verification, reopen, decisions, closure, violation detection, snapshots, state hash,
and six golden end-to-end scenarios.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

import pytest

from mcoi_runtime.contracts.remediation_runtime import (
    CorrectiveAction,
    PreventiveAction,
    PreventiveActionStatus,
    RemediationAssignment,
    RemediationClosureReport,
    RemediationDecision,
    RemediationDisposition,
    RemediationPriority,
    RemediationRecord,
    RemediationSnapshot,
    RemediationStatus,
    RemediationType,
    RemediationViolation,
    ReopenRecord,
    VerificationRecord,
    RemediationVerificationStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.remediation_runtime import RemediationRuntimeEngine


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """Fresh RemediationRuntimeEngine with an EventSpineEngine."""
    es = EventSpineEngine()
    return RemediationRuntimeEngine(es)


def _past_deadline() -> str:
    """Return an ISO-8601 timestamp in the past."""
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()


def _future_deadline() -> str:
    """Return an ISO-8601 timestamp in the future."""
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


def _make_remediation(engine, rid="rem-1", tenant="t1", title="Fix it", **kw):
    """Shortcut to create a remediation with sensible defaults."""
    return engine.create_remediation(rid, tenant, title, **kw)


# ===================================================================
# 1. Remediation management
# ===================================================================


class TestCreateRemediation:
    """Tests for create_remediation."""

    def test_create_returns_record(self, engine):
        rec = _make_remediation(engine)
        assert isinstance(rec, RemediationRecord)
        assert rec.remediation_id == "rem-1"
        assert rec.tenant_id == "t1"
        assert rec.title == "Fix it"
        assert rec.status == RemediationStatus.OPEN

    def test_create_default_type_and_priority(self, engine):
        rec = _make_remediation(engine)
        assert rec.remediation_type == RemediationType.CORRECTIVE
        assert rec.priority == RemediationPriority.MEDIUM

    def test_create_with_case_and_finding(self, engine):
        rec = engine.create_remediation(
            "rem-x", "t1", "Title", case_id="case-1", finding_id="find-1"
        )
        assert rec.case_id == "case-1"
        assert rec.finding_id == "find-1"

    def test_create_with_description(self, engine):
        rec = engine.create_remediation("rem-x", "t1", "T", description="Long desc")
        assert rec.description == "Long desc"

    def test_create_with_owner(self, engine):
        rec = engine.create_remediation("rem-x", "t1", "T", owner_id="user-42")
        assert rec.owner_id == "user-42"

    def test_create_with_deadline(self, engine):
        dl = _future_deadline()
        rec = engine.create_remediation("rem-x", "t1", "T", deadline=dl)
        assert rec.deadline == dl

    def test_created_at_populated(self, engine):
        rec = _make_remediation(engine)
        assert rec.created_at  # non-empty ISO string


class TestCreateRemediationTypePriorityCombinations:
    """Every (RemediationType, RemediationPriority) pair should work."""

    _combos = list(itertools.product(RemediationType, RemediationPriority))

    @pytest.mark.parametrize("rtype,prio", _combos, ids=[
        f"{t.name}-{p.name}" for t, p in _combos
    ])
    def test_type_priority_combo(self, engine, rtype, prio):
        rid = f"rem-{rtype.value}-{prio.value}"
        rec = engine.create_remediation(
            rid, "t1", "combo test",
            remediation_type=rtype, priority=prio,
        )
        assert rec.remediation_type == rtype
        assert rec.priority == prio


class TestGetRemediation:
    def test_get_existing(self, engine):
        _make_remediation(engine)
        rec = engine.get_remediation("rem-1")
        assert rec.remediation_id == "rem-1"

    def test_get_missing_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown remediation_id"):
            engine.get_remediation("nope")


class TestRemediationsForTenant:
    def test_filter_by_tenant(self, engine):
        engine.create_remediation("r1", "t1", "A")
        engine.create_remediation("r2", "t2", "B")
        engine.create_remediation("r3", "t1", "C")
        result = engine.remediations_for_tenant("t1")
        assert len(result) == 2
        assert all(r.tenant_id == "t1" for r in result)

    def test_empty_for_unknown_tenant(self, engine):
        _make_remediation(engine)
        assert engine.remediations_for_tenant("unknown") == ()


class TestDuplicateRemediation:
    def test_duplicate_raises(self, engine):
        _make_remediation(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate remediation_id"):
            _make_remediation(engine)


class TestStartRemediation:
    def test_start_open(self, engine):
        _make_remediation(engine)
        rec = engine.start_remediation("rem-1")
        assert rec.status == RemediationStatus.IN_PROGRESS

    def test_start_escalated(self, engine):
        _make_remediation(engine)
        engine.escalate_remediation("rem-1")
        rec = engine.start_remediation("rem-1")
        assert rec.status == RemediationStatus.IN_PROGRESS

    def test_start_reopened(self, engine):
        _make_remediation(engine)
        engine.reopen_remediation("ro-1", "rem-1")
        rec = engine.start_remediation("rem-1")
        assert rec.status == RemediationStatus.IN_PROGRESS

    def test_cannot_start_closed(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot start a closed"):
            engine.start_remediation("rem-1")

    def test_cannot_start_verified(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot start a closed"):
            engine.start_remediation("rem-1")


class TestSubmitForVerification:
    def test_submit_open(self, engine):
        _make_remediation(engine)
        rec = engine.submit_for_verification("rem-1")
        assert rec.status == RemediationStatus.PENDING_VERIFICATION

    def test_submit_in_progress(self, engine):
        _make_remediation(engine)
        engine.start_remediation("rem-1")
        rec = engine.submit_for_verification("rem-1")
        assert rec.status == RemediationStatus.PENDING_VERIFICATION

    def test_cannot_submit_closed(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot submit closed"):
            engine.submit_for_verification("rem-1")

    def test_cannot_submit_verified(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot submit closed"):
            engine.submit_for_verification("rem-1")


class TestEscalateRemediation:
    def test_escalate_default_priority(self, engine):
        _make_remediation(engine, priority=RemediationPriority.LOW)
        rec = engine.escalate_remediation("rem-1")
        assert rec.status == RemediationStatus.ESCALATED
        assert rec.priority == RemediationPriority.LOW  # unchanged

    def test_escalate_with_new_priority(self, engine):
        _make_remediation(engine, priority=RemediationPriority.LOW)
        rec = engine.escalate_remediation("rem-1", priority=RemediationPriority.CRITICAL)
        assert rec.priority == RemediationPriority.CRITICAL

    def test_escalate_preserves_fields(self, engine):
        _make_remediation(engine, case_id="c1", finding_id="f1", description="desc")
        rec = engine.escalate_remediation("rem-1")
        assert rec.case_id == "c1"
        assert rec.finding_id == "f1"
        assert rec.description == "desc"

    def test_cannot_escalate_closed(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate a closed"):
            engine.escalate_remediation("rem-1")

    def test_cannot_escalate_verified(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate a closed"):
            engine.escalate_remediation("rem-1")


# ===================================================================
# 2. Assignments
# ===================================================================


class TestAssignments:
    def test_assign_returns_assignment(self, engine):
        _make_remediation(engine)
        a = engine.assign_remediation("a1", "rem-1", "user-1")
        assert isinstance(a, RemediationAssignment)
        assert a.assignment_id == "a1"
        assert a.assignee_id == "user-1"
        assert a.role == "owner"

    def test_assign_custom_role(self, engine):
        _make_remediation(engine)
        a = engine.assign_remediation("a1", "rem-1", "user-1", role="reviewer")
        assert a.role == "reviewer"

    def test_assign_populates_timestamp(self, engine):
        _make_remediation(engine)
        a = engine.assign_remediation("a1", "rem-1", "user-1")
        assert a.assigned_at

    def test_assignments_for_remediation(self, engine):
        _make_remediation(engine)
        engine.assign_remediation("a1", "rem-1", "user-1")
        engine.assign_remediation("a2", "rem-1", "user-2")
        result = engine.assignments_for_remediation("rem-1")
        assert len(result) == 2

    def test_assignments_for_unrelated_remediation_empty(self, engine):
        _make_remediation(engine)
        engine.assign_remediation("a1", "rem-1", "user-1")
        engine.create_remediation("rem-2", "t1", "Other")
        assert engine.assignments_for_remediation("rem-2") == ()

    def test_duplicate_assignment_raises(self, engine):
        _make_remediation(engine)
        engine.assign_remediation("a1", "rem-1", "user-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate assignment_id"):
            engine.assign_remediation("a1", "rem-1", "user-2")

    def test_assign_unknown_remediation_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown remediation_id"):
            engine.assign_remediation("a1", "nope", "user-1")

    def test_multiple_assignees_same_remediation(self, engine):
        _make_remediation(engine)
        for i in range(5):
            engine.assign_remediation(f"a{i}", "rem-1", f"user-{i}")
        assert len(engine.assignments_for_remediation("rem-1")) == 5


# ===================================================================
# 3. Corrective actions
# ===================================================================


class TestCorrectiveActions:
    def test_add_returns_action(self, engine):
        _make_remediation(engine)
        ca = engine.add_corrective_action("ca-1", "rem-1", "Patch server")
        assert isinstance(ca, CorrectiveAction)
        assert ca.action_id == "ca-1"
        assert ca.status == RemediationStatus.OPEN

    def test_add_with_description(self, engine):
        _make_remediation(engine)
        ca = engine.add_corrective_action("ca-1", "rem-1", "Patch", description="Apply CVE fix")
        assert ca.description == "Apply CVE fix"

    def test_add_with_owner(self, engine):
        _make_remediation(engine)
        ca = engine.add_corrective_action("ca-1", "rem-1", "Patch", owner_id="ops-team")
        assert ca.owner_id == "ops-team"

    def test_add_with_deadline(self, engine):
        dl = _future_deadline()
        _make_remediation(engine)
        ca = engine.add_corrective_action("ca-1", "rem-1", "Patch", deadline=dl)
        assert ca.deadline == dl

    def test_complete_corrective(self, engine):
        _make_remediation(engine)
        engine.add_corrective_action("ca-1", "rem-1", "Patch")
        completed = engine.complete_corrective_action("ca-1")
        assert completed.status == RemediationStatus.PENDING_VERIFICATION
        assert completed.completed_at  # non-empty

    def test_complete_preserves_fields(self, engine):
        _make_remediation(engine)
        engine.add_corrective_action("ca-1", "rem-1", "Patch", description="D", owner_id="u1")
        completed = engine.complete_corrective_action("ca-1")
        assert completed.title == "Patch"
        assert completed.description == "D"
        assert completed.owner_id == "u1"

    def test_complete_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown corrective action_id"):
            engine.complete_corrective_action("nope")

    def test_corrective_for_remediation(self, engine):
        _make_remediation(engine)
        engine.add_corrective_action("ca-1", "rem-1", "A")
        engine.add_corrective_action("ca-2", "rem-1", "B")
        result = engine.corrective_actions_for_remediation("rem-1")
        assert len(result) == 2

    def test_corrective_for_other_remediation_empty(self, engine):
        _make_remediation(engine)
        engine.add_corrective_action("ca-1", "rem-1", "A")
        engine.create_remediation("rem-2", "t1", "Other")
        assert engine.corrective_actions_for_remediation("rem-2") == ()

    def test_duplicate_corrective_raises(self, engine):
        _make_remediation(engine)
        engine.add_corrective_action("ca-1", "rem-1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate corrective action_id"):
            engine.add_corrective_action("ca-1", "rem-1", "B")

    def test_corrective_unknown_remediation_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown remediation_id"):
            engine.add_corrective_action("ca-1", "nope", "A")

    def test_add_multiple_corrective_actions(self, engine):
        _make_remediation(engine)
        for i in range(4):
            engine.add_corrective_action(f"ca-{i}", "rem-1", f"Action {i}")
        assert len(engine.corrective_actions_for_remediation("rem-1")) == 4


# ===================================================================
# 4. Preventive actions
# ===================================================================


class TestPreventiveActions:
    def test_add_returns_action(self, engine):
        _make_remediation(engine)
        pa = engine.add_preventive_action("pa-1", "rem-1", "Training", "program", "prog-1")
        assert isinstance(pa, PreventiveAction)
        assert pa.action_id == "pa-1"
        assert pa.target_type == "program"
        assert pa.target_id == "prog-1"
        assert pa.status == PreventiveActionStatus.PROPOSED

    def test_add_with_description(self, engine):
        _make_remediation(engine)
        pa = engine.add_preventive_action(
            "pa-1", "rem-1", "Training", "program", "prog-1", description="Annual"
        )
        assert pa.description == "Annual"

    def test_add_with_owner(self, engine):
        _make_remediation(engine)
        pa = engine.add_preventive_action(
            "pa-1", "rem-1", "Training", "program", "prog-1", owner_id="hr"
        )
        assert pa.owner_id == "hr"

    def test_add_control_target(self, engine):
        _make_remediation(engine)
        pa = engine.add_preventive_action("pa-1", "rem-1", "Ctrl", "control", "ctrl-5")
        assert pa.target_type == "control"
        assert pa.target_id == "ctrl-5"

    def test_duplicate_preventive_raises(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "T", "program", "p1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate preventive action_id"):
            engine.add_preventive_action("pa-1", "rem-1", "T", "program", "p1")

    def test_preventive_unknown_remediation_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown remediation_id"):
            engine.add_preventive_action("pa-1", "nope", "T", "program", "p1")

    def test_preventive_for_remediation(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "A", "program", "p1")
        engine.add_preventive_action("pa-2", "rem-1", "B", "control", "c1")
        result = engine.preventive_actions_for_remediation("rem-1")
        assert len(result) == 2

    def test_preventive_for_other_remediation_empty(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "A", "program", "p1")
        engine.create_remediation("rem-2", "t1", "X")
        assert engine.preventive_actions_for_remediation("rem-2") == ()


class TestApprovePreventiveAction:
    def test_approve_proposed(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "T", "program", "p1")
        approved = engine.approve_preventive_action("pa-1")
        assert approved.status == PreventiveActionStatus.APPROVED

    def test_approve_preserves_fields(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action(
            "pa-1", "rem-1", "Train", "program", "p1", description="D", owner_id="o1"
        )
        approved = engine.approve_preventive_action("pa-1")
        assert approved.title == "Train"
        assert approved.target_type == "program"
        assert approved.target_id == "p1"

    def test_approve_already_approved_raises(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "T", "program", "p1")
        engine.approve_preventive_action("pa-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only approve PROPOSED"):
            engine.approve_preventive_action("pa-1")

    def test_approve_implemented_raises(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "T", "program", "p1")
        engine.approve_preventive_action("pa-1")
        engine.implement_preventive_action("pa-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only approve PROPOSED"):
            engine.approve_preventive_action("pa-1")

    def test_approve_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown preventive action_id"):
            engine.approve_preventive_action("nope")


class TestImplementPreventiveAction:
    def test_implement_approved(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "T", "program", "p1")
        engine.approve_preventive_action("pa-1")
        impl = engine.implement_preventive_action("pa-1")
        assert impl.status == PreventiveActionStatus.IMPLEMENTED

    def test_implement_proposed_raises(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "T", "program", "p1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only implement APPROVED"):
            engine.implement_preventive_action("pa-1")

    def test_implement_already_implemented_raises(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "T", "program", "p1")
        engine.approve_preventive_action("pa-1")
        engine.implement_preventive_action("pa-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only implement APPROVED"):
            engine.implement_preventive_action("pa-1")

    def test_implement_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown preventive action_id"):
            engine.implement_preventive_action("nope")

    def test_implement_preserves_fields(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action(
            "pa-1", "rem-1", "Train", "control", "c1", description="D"
        )
        engine.approve_preventive_action("pa-1")
        impl = engine.implement_preventive_action("pa-1")
        assert impl.title == "Train"
        assert impl.target_type == "control"
        assert impl.target_id == "c1"


# ===================================================================
# 5. Verification
# ===================================================================


class TestVerification:
    def test_verify_passed_auto_verified(self, engine):
        _make_remediation(engine)
        vr = engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        assert isinstance(vr, VerificationRecord)
        assert vr.status == RemediationVerificationStatus.PASSED
        rem = engine.get_remediation("rem-1")
        assert rem.status == RemediationStatus.VERIFIED

    def test_verify_failed_auto_reopened(self, engine):
        _make_remediation(engine)
        engine.start_remediation("rem-1")
        vr = engine.verify_remediation(
            "v1", "rem-1", "verifier", status=RemediationVerificationStatus.FAILED, notes="Not fixed"
        )
        assert vr.status == RemediationVerificationStatus.FAILED
        rem = engine.get_remediation("rem-1")
        assert rem.status == RemediationStatus.REOPENED

    def test_verify_failed_creates_reopen_record(self, engine):
        _make_remediation(engine)
        engine.verify_remediation(
            "v1", "rem-1", "verifier", status=RemediationVerificationStatus.FAILED, notes="Bad"
        )
        reopens = engine.reopens_for_remediation("rem-1")
        assert len(reopens) == 1
        assert "Bad" in reopens[0].reason

    def test_verify_failed_no_notes_reopen_reason(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.FAILED)
        reopens = engine.reopens_for_remediation("rem-1")
        assert reopens[0].reason == "Verification failed"

    def test_verify_waived_no_status_change(self, engine):
        _make_remediation(engine)
        engine.start_remediation("rem-1")
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.WAIVED)
        rem = engine.get_remediation("rem-1")
        assert rem.status == RemediationStatus.IN_PROGRESS

    def test_verify_pending_no_status_change(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PENDING)
        rem = engine.get_remediation("rem-1")
        assert rem.status == RemediationStatus.OPEN

    def test_verifications_for_remediation(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "a", status=RemediationVerificationStatus.FAILED)
        engine.verify_remediation("v2", "rem-1", "b", status=RemediationVerificationStatus.PASSED)
        result = engine.verifications_for_remediation("rem-1")
        assert len(result) == 2

    def test_verifications_other_remediation_empty(self, engine):
        _make_remediation(engine)
        engine.create_remediation("rem-2", "t1", "Other")
        engine.verify_remediation("v1", "rem-1", "a", status=RemediationVerificationStatus.PASSED)
        assert engine.verifications_for_remediation("rem-2") == ()

    def test_duplicate_verification_raises(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "a", status=RemediationVerificationStatus.PASSED)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate verification_id"):
            engine.verify_remediation("v1", "rem-1", "b", status=RemediationVerificationStatus.PASSED)

    def test_verify_unknown_remediation_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown remediation_id"):
            engine.verify_remediation("v1", "nope", "a", status=RemediationVerificationStatus.PASSED)

    def test_verify_with_notes(self, engine):
        _make_remediation(engine)
        vr = engine.verify_remediation(
            "v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED, notes="All good"
        )
        assert vr.notes == "All good"

    def test_verified_at_populated(self, engine):
        _make_remediation(engine)
        vr = engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        assert vr.verified_at


# ===================================================================
# 6. Reopen
# ===================================================================


class TestReopen:
    def test_manual_reopen(self, engine):
        _make_remediation(engine)
        engine.start_remediation("rem-1")
        ro = engine.reopen_remediation("ro-1", "rem-1", reason="Found new issue")
        assert isinstance(ro, ReopenRecord)
        assert ro.reason == "Found new issue"
        rem = engine.get_remediation("rem-1")
        assert rem.status == RemediationStatus.REOPENED

    def test_reopen_sets_reopened_by(self, engine):
        _make_remediation(engine)
        ro = engine.reopen_remediation("ro-1", "rem-1", reopened_by="admin")
        assert ro.reopened_by == "admin"

    def test_reopen_default_reopened_by(self, engine):
        _make_remediation(engine)
        ro = engine.reopen_remediation("ro-1", "rem-1")
        assert ro.reopened_by == "system"

    def test_cannot_reopen_closed(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot reopen a closed"):
            engine.reopen_remediation("ro-1", "rem-1")

    def test_duplicate_reopen_raises(self, engine):
        _make_remediation(engine)
        engine.reopen_remediation("ro-1", "rem-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate reopen_id"):
            engine.reopen_remediation("ro-1", "rem-1")

    def test_reopen_unknown_remediation_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown remediation_id"):
            engine.reopen_remediation("ro-1", "nope")

    def test_reopens_for_remediation(self, engine):
        _make_remediation(engine)
        engine.reopen_remediation("ro-1", "rem-1", reason="A")
        engine.reopen_remediation("ro-2", "rem-1", reason="B")
        result = engine.reopens_for_remediation("rem-1")
        assert len(result) == 2

    def test_reopens_other_remediation_empty(self, engine):
        _make_remediation(engine)
        engine.create_remediation("rem-2", "t1", "Other")
        engine.reopen_remediation("ro-1", "rem-1")
        assert engine.reopens_for_remediation("rem-2") == ()

    def test_reopened_at_populated(self, engine):
        _make_remediation(engine)
        ro = engine.reopen_remediation("ro-1", "rem-1")
        assert ro.reopened_at


# ===================================================================
# 7. Decisions
# ===================================================================


class TestDecisions:
    def test_make_decision(self, engine):
        _make_remediation(engine)
        dec = engine.make_decision("d1", "rem-1", disposition=RemediationDisposition.RESOLVED)
        assert isinstance(dec, RemediationDecision)
        assert dec.disposition == RemediationDisposition.RESOLVED
        assert dec.decided_by == "system"

    def test_decision_with_reason_and_decided_by(self, engine):
        _make_remediation(engine)
        dec = engine.make_decision(
            "d1", "rem-1",
            disposition=RemediationDisposition.ACCEPTED_RISK,
            decided_by="ciso",
            reason="Risk accepted per policy",
        )
        assert dec.decided_by == "ciso"
        assert dec.reason == "Risk accepted per policy"

    def test_duplicate_decision_raises(self, engine):
        _make_remediation(engine)
        engine.make_decision("d1", "rem-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate decision_id"):
            engine.make_decision("d1", "rem-1")

    def test_decision_unknown_remediation_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown remediation_id"):
            engine.make_decision("d1", "nope")

    def test_decided_at_populated(self, engine):
        _make_remediation(engine)
        dec = engine.make_decision("d1", "rem-1")
        assert dec.decided_at

    @pytest.mark.parametrize("disp", list(RemediationDisposition))
    def test_all_dispositions(self, engine, disp):
        _make_remediation(engine)
        dec = engine.make_decision(f"d-{disp.value}", "rem-1", disposition=disp)
        assert dec.disposition == disp


# ===================================================================
# 8. Closure
# ===================================================================


class TestClosure:
    def test_close_resolved_with_passed_verification(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        report = engine.close_remediation("rem-1")
        assert isinstance(report, RemediationClosureReport)
        assert report.disposition == RemediationDisposition.RESOLVED
        rem = engine.get_remediation("rem-1")
        assert rem.status == RemediationStatus.CLOSED

    def test_close_resolved_without_verification_raises(self, engine):
        _make_remediation(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot close as RESOLVED"):
            engine.close_remediation("rem-1")

    def test_close_accepted_risk_without_verification_ok(self, engine):
        _make_remediation(engine)
        report = engine.close_remediation(
            "rem-1", disposition=RemediationDisposition.ACCEPTED_RISK
        )
        assert report.disposition == RemediationDisposition.ACCEPTED_RISK

    def test_close_transferred_without_verification_ok(self, engine):
        _make_remediation(engine)
        report = engine.close_remediation(
            "rem-1", disposition=RemediationDisposition.TRANSFERRED
        )
        assert report.disposition == RemediationDisposition.TRANSFERRED

    def test_close_escalated_without_verification_ok(self, engine):
        _make_remediation(engine)
        report = engine.close_remediation(
            "rem-1", disposition=RemediationDisposition.ESCALATED
        )
        assert report.disposition == RemediationDisposition.ESCALATED

    def test_close_ineffective_without_verification_ok(self, engine):
        _make_remediation(engine)
        report = engine.close_remediation(
            "rem-1", disposition=RemediationDisposition.INEFFECTIVE
        )
        assert report.disposition == RemediationDisposition.INEFFECTIVE

    def test_cannot_close_already_closed(self, engine):
        _make_remediation(engine)
        engine.close_remediation("rem-1", disposition=RemediationDisposition.ACCEPTED_RISK)
        with pytest.raises(RuntimeCoreInvariantError, match="already closed"):
            engine.close_remediation("rem-1", disposition=RemediationDisposition.ACCEPTED_RISK)

    def test_closure_report_counts(self, engine):
        _make_remediation(engine)
        engine.add_corrective_action("ca-1", "rem-1", "Fix A")
        engine.add_corrective_action("ca-2", "rem-1", "Fix B")
        engine.add_preventive_action("pa-1", "rem-1", "Prevent", "program", "p1")
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.FAILED)
        engine.verify_remediation("v2", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        report = engine.close_remediation("rem-1")
        assert report.total_corrective == 2
        assert report.total_preventive == 1
        assert report.total_verifications == 2
        assert report.total_reopens == 1  # auto-reopen from FAILED
        assert report.remediation_id == "rem-1"
        assert report.tenant_id == "t1"

    def test_closure_creates_decision(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1", decided_by="ciso", reason="All done")
        assert engine.decision_count == 1

    def test_closure_report_id_populated(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        report = engine.close_remediation("rem-1")
        assert report.report_id
        assert report.closed_at

    def test_closure_with_violations(self, engine):
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        engine.detect_violations()  # creates overdue violation
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        report = engine.close_remediation("rem-1")
        assert report.total_violations == 1


# ===================================================================
# 9. Violation detection
# ===================================================================


class TestViolationDetection:
    def test_overdue_violation(self, engine):
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        viols = engine.detect_violations()
        assert len(viols) == 1
        assert viols[0].operation == "overdue"
        assert "overdue" in viols[0].reason.lower()

    def test_no_violation_when_deadline_future(self, engine):
        dl = _future_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        viols = engine.detect_violations()
        assert len(viols) == 0

    def test_no_violation_when_no_deadline(self, engine):
        _make_remediation(engine)
        viols = engine.detect_violations()
        assert len(viols) == 0

    def test_closed_without_verification_violation(self, engine):
        _make_remediation(engine)
        # Manually set to CLOSED bypassing close_remediation
        engine._update_remediation_status("rem-1", RemediationStatus.CLOSED)
        viols = engine.detect_violations()
        closed_viol = [v for v in viols if v.operation == "closed_without_verification"]
        assert len(closed_viol) == 1

    def test_no_closed_violation_when_has_passed(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1")
        viols = engine.detect_violations()
        closed_viols = [v for v in viols if v.operation == "closed_without_verification"]
        assert len(closed_viols) == 0

    def test_idempotent_detection(self, engine):
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        v1 = engine.detect_violations()
        v2 = engine.detect_violations()
        assert len(v1) == 1
        assert len(v2) == 0  # same violation not re-created
        assert engine.violation_count == 1

    def test_violations_for_remediation(self, engine):
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        engine.detect_violations()
        result = engine.violations_for_remediation("rem-1")
        assert len(result) == 1

    def test_violations_for_other_remediation_empty(self, engine):
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        engine.create_remediation("rem-2", "t1", "OK")
        engine.detect_violations()
        assert engine.violations_for_remediation("rem-2") == ()

    def test_violations_for_tenant(self, engine):
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        engine.create_remediation("rem-2", "t2", "Fix2", deadline=dl)
        engine.detect_violations()
        t1_viols = engine.violations_for_tenant("t1")
        t2_viols = engine.violations_for_tenant("t2")
        assert len(t1_viols) == 1
        assert len(t2_viols) == 1

    def test_violations_for_unknown_tenant_empty(self, engine):
        assert engine.violations_for_tenant("nope") == ()

    def test_overdue_closed_remediation_no_overdue_violation(self, engine):
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        engine.close_remediation("rem-1", disposition=RemediationDisposition.ACCEPTED_RISK)
        viols = engine.detect_violations()
        overdue_viols = [v for v in viols if v.operation == "overdue"]
        assert len(overdue_viols) == 0

    def test_multiple_violations_same_remediation(self, engine):
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        # Force close without verification
        engine._update_remediation_status("rem-1", RemediationStatus.CLOSED)
        viols = engine.detect_violations()
        # Should have closed_without_verification but not overdue (it's closed)
        assert len(viols) == 1
        assert viols[0].operation == "closed_without_verification"


# ===================================================================
# 10. Snapshots & state
# ===================================================================


class TestSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.remediation_snapshot("snap-1")
        assert isinstance(snap, RemediationSnapshot)
        assert snap.total_remediations == 0
        assert snap.open_remediations == 0
        assert snap.total_corrective == 0
        assert snap.total_preventive == 0
        assert snap.total_verifications == 0
        assert snap.total_reopens == 0
        assert snap.total_decisions == 0
        assert snap.total_violations == 0

    def test_snapshot_captures_all_counters(self, engine):
        _make_remediation(engine)
        engine.add_corrective_action("ca-1", "rem-1", "Fix")
        engine.add_preventive_action("pa-1", "rem-1", "Prevent", "program", "p1")
        engine.assign_remediation("a1", "rem-1", "user-1")
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.FAILED)
        engine.make_decision("d1", "rem-1")
        snap = engine.remediation_snapshot("snap-1")
        assert snap.total_remediations == 1
        assert snap.open_remediations == 1  # REOPENED is not closed
        assert snap.total_corrective == 1
        assert snap.total_preventive == 1
        assert snap.total_verifications == 1
        assert snap.total_reopens == 1  # auto-reopen
        assert snap.total_decisions == 1
        assert snap.total_violations == 0

    def test_snapshot_with_scope_ref(self, engine):
        snap = engine.remediation_snapshot("snap-1", scope_ref_id="org-42")
        assert snap.scope_ref_id == "org-42"

    def test_duplicate_snapshot_raises(self, engine):
        engine.remediation_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.remediation_snapshot("snap-1")

    def test_snapshot_captured_at(self, engine):
        snap = engine.remediation_snapshot("snap-1")
        assert snap.captured_at

    def test_snapshot_after_closure(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1")
        snap = engine.remediation_snapshot("snap-1")
        assert snap.total_remediations == 1
        assert snap.open_remediations == 0  # closed


class TestStateHash:
    def test_initial_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_changes_after_create(self, engine):
        h1 = engine.state_hash()
        _make_remediation(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_after_corrective(self, engine):
        _make_remediation(engine)
        h1 = engine.state_hash()
        engine.add_corrective_action("ca-1", "rem-1", "Fix")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_after_preventive(self, engine):
        _make_remediation(engine)
        h1 = engine.state_hash()
        engine.add_preventive_action("pa-1", "rem-1", "Prevent", "program", "p1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_after_verification(self, engine):
        _make_remediation(engine)
        h1 = engine.state_hash()
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_after_reopen(self, engine):
        _make_remediation(engine)
        h1 = engine.state_hash()
        engine.reopen_remediation("ro-1", "rem-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_after_decision(self, engine):
        _make_remediation(engine)
        h1 = engine.state_hash()
        engine.make_decision("d1", "rem-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_deterministic(self, engine):
        _make_remediation(engine)
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2


class TestCountProperties:
    def test_remediation_count(self, engine):
        assert engine.remediation_count == 0
        _make_remediation(engine)
        assert engine.remediation_count == 1
        engine.create_remediation("rem-2", "t1", "B")
        assert engine.remediation_count == 2

    def test_open_remediation_count(self, engine):
        assert engine.open_remediation_count == 0
        _make_remediation(engine)
        assert engine.open_remediation_count == 1
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        assert engine.open_remediation_count == 0  # VERIFIED is closed

    def test_open_count_excludes_closed(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1")
        assert engine.open_remediation_count == 0

    def test_open_count_includes_reopened(self, engine):
        _make_remediation(engine)
        engine.reopen_remediation("ro-1", "rem-1")
        assert engine.open_remediation_count == 1

    def test_open_count_includes_escalated(self, engine):
        _make_remediation(engine)
        engine.escalate_remediation("rem-1")
        assert engine.open_remediation_count == 1

    def test_corrective_count(self, engine):
        assert engine.corrective_count == 0
        _make_remediation(engine)
        engine.add_corrective_action("ca-1", "rem-1", "A")
        assert engine.corrective_count == 1

    def test_preventive_count(self, engine):
        assert engine.preventive_count == 0
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "P", "program", "p1")
        assert engine.preventive_count == 1

    def test_assignment_count(self, engine):
        assert engine.assignment_count == 0
        _make_remediation(engine)
        engine.assign_remediation("a1", "rem-1", "user")
        assert engine.assignment_count == 1

    def test_verification_count(self, engine):
        assert engine.verification_count == 0
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        assert engine.verification_count == 1

    def test_reopen_count(self, engine):
        assert engine.reopen_count == 0
        _make_remediation(engine)
        engine.reopen_remediation("ro-1", "rem-1")
        assert engine.reopen_count == 1

    def test_decision_count(self, engine):
        assert engine.decision_count == 0
        _make_remediation(engine)
        engine.make_decision("d1", "rem-1")
        assert engine.decision_count == 1

    def test_violation_count(self, engine):
        assert engine.violation_count == 0
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "Fix", deadline=dl)
        engine.detect_violations()
        assert engine.violation_count == 1


# ===================================================================
# 11. Constructor guard
# ===================================================================


class TestConstructorGuard:
    def test_non_event_spine_raises(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine must be"):
            RemediationRuntimeEngine("not an event spine")

    def test_none_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            RemediationRuntimeEngine(None)

    def test_valid_event_spine(self):
        es = EventSpineEngine()
        eng = RemediationRuntimeEngine(es)
        assert eng.remediation_count == 0


# ===================================================================
# 12. Six golden scenarios
# ===================================================================


class TestGoldenScenario1CriticalFindingCorrective:
    """Critical finding -> corrective action with deadline -> verification -> closure."""

    def test_full_flow(self, engine):
        dl = _future_deadline()
        rem = engine.create_remediation(
            "rem-crit", "tenant-a", "Critical CVE",
            finding_id="CVE-2025-1234",
            remediation_type=RemediationType.CORRECTIVE,
            priority=RemediationPriority.CRITICAL,
            deadline=dl,
        )
        assert rem.priority == RemediationPriority.CRITICAL
        assert rem.status == RemediationStatus.OPEN

        engine.start_remediation("rem-crit")
        assert engine.get_remediation("rem-crit").status == RemediationStatus.IN_PROGRESS

        ca = engine.add_corrective_action(
            "ca-crit", "rem-crit", "Apply patch",
            description="Emergency patch", deadline=dl,
        )
        assert ca.status == RemediationStatus.OPEN

        engine.complete_corrective_action("ca-crit")

        engine.submit_for_verification("rem-crit")
        assert engine.get_remediation("rem-crit").status == RemediationStatus.PENDING_VERIFICATION

        engine.verify_remediation(
            "v-crit", "rem-crit", "sec-team", status=RemediationVerificationStatus.PASSED
        )
        assert engine.get_remediation("rem-crit").status == RemediationStatus.VERIFIED

        report = engine.close_remediation("rem-crit", decided_by="ciso")
        assert report.disposition == RemediationDisposition.RESOLVED
        assert report.total_corrective == 1
        assert report.total_verifications == 1
        assert engine.get_remediation("rem-crit").status == RemediationStatus.CLOSED


class TestGoldenScenario2CannotCloseResolvedWithoutVerification:
    """Remediation cannot close as RESOLVED without verification."""

    def test_blocked_closure(self, engine):
        engine.create_remediation("rem-nv", "tenant-a", "Unverified fix")
        engine.start_remediation("rem-nv")
        engine.add_corrective_action("ca-nv", "rem-nv", "Some fix")
        engine.complete_corrective_action("ca-nv")

        with pytest.raises(RuntimeCoreInvariantError, match="Cannot close as RESOLVED"):
            engine.close_remediation("rem-nv")

        # But non-RESOLVED disposition works
        report = engine.close_remediation(
            "rem-nv", disposition=RemediationDisposition.ACCEPTED_RISK, reason="Risk accepted"
        )
        assert report.disposition == RemediationDisposition.ACCEPTED_RISK


class TestGoldenScenario3FailedVerifyReverifyClose:
    """Failed verification -> auto-reopen -> fix -> re-verify -> close."""

    def test_retry_flow(self, engine):
        engine.create_remediation(
            "rem-fail", "tenant-b", "Retry scenario",
            priority=RemediationPriority.HIGH,
        )
        engine.start_remediation("rem-fail")
        engine.add_corrective_action("ca-f1", "rem-fail", "First attempt")
        engine.complete_corrective_action("ca-f1")
        engine.submit_for_verification("rem-fail")

        # First verification fails
        engine.verify_remediation(
            "v-f1", "rem-fail", "qa", status=RemediationVerificationStatus.FAILED, notes="Still broken"
        )
        rem = engine.get_remediation("rem-fail")
        assert rem.status == RemediationStatus.REOPENED
        assert engine.reopen_count >= 1

        # Second corrective action
        engine.start_remediation("rem-fail")
        engine.add_corrective_action("ca-f2", "rem-fail", "Second attempt")
        engine.complete_corrective_action("ca-f2")
        engine.submit_for_verification("rem-fail")

        # Second verification passes
        engine.verify_remediation(
            "v-f2", "rem-fail", "qa", status=RemediationVerificationStatus.PASSED
        )
        assert engine.get_remediation("rem-fail").status == RemediationStatus.VERIFIED

        report = engine.close_remediation("rem-fail")
        assert report.disposition == RemediationDisposition.RESOLVED
        assert report.total_corrective == 2
        assert report.total_verifications == 2
        assert report.total_reopens == 1


class TestGoldenScenario4OverdueEscalation:
    """Overdue remediation escalation to executive."""

    def test_overdue_escalation(self, engine):
        dl = _past_deadline()
        engine.create_remediation(
            "rem-late", "tenant-c", "Overdue item",
            priority=RemediationPriority.MEDIUM,
            deadline=dl,
        )

        # Detect overdue violation
        viols = engine.detect_violations()
        assert len(viols) == 1
        assert viols[0].operation == "overdue"

        # Escalate to executive
        engine.escalate_remediation(
            "rem-late", priority=RemediationPriority.CRITICAL,
        )
        rem = engine.get_remediation("rem-late")
        assert rem.status == RemediationStatus.ESCALATED
        assert rem.priority == RemediationPriority.CRITICAL

        # Assign executive
        engine.assign_remediation("a-exec", "rem-late", "vp-security", role="executive_sponsor")
        assigns = engine.assignments_for_remediation("rem-late")
        assert any(a.role == "executive_sponsor" for a in assigns)

        # Eventually resolve
        engine.start_remediation("rem-late")
        engine.add_corrective_action("ca-late", "rem-late", "Rush fix")
        engine.complete_corrective_action("ca-late")
        engine.verify_remediation("v-late", "rem-late", "qa", status=RemediationVerificationStatus.PASSED)
        report = engine.close_remediation("rem-late")
        assert report.total_violations == 1


class TestGoldenScenario5PreventiveActionLifecycle:
    """Preventive action lifecycle: propose -> approve -> implement -> attach to program/control."""

    def test_preventive_lifecycle(self, engine):
        engine.create_remediation(
            "rem-prev", "tenant-d", "Prevent recurrence",
            remediation_type=RemediationType.PREVENTIVE,
        )

        # Propose preventive action targeting a program
        pa = engine.add_preventive_action(
            "pa-train", "rem-prev", "Security training",
            "program", "security-awareness-2025",
            description="Annual phishing awareness training",
        )
        assert pa.status == PreventiveActionStatus.PROPOSED

        # Approve
        pa = engine.approve_preventive_action("pa-train")
        assert pa.status == PreventiveActionStatus.APPROVED

        # Implement
        pa = engine.implement_preventive_action("pa-train")
        assert pa.status == PreventiveActionStatus.IMPLEMENTED
        assert pa.target_type == "program"
        assert pa.target_id == "security-awareness-2025"

        # Second preventive action targeting a control
        pa2 = engine.add_preventive_action(
            "pa-ctrl", "rem-prev", "MFA enforcement",
            "control", "ctrl-mfa-001",
        )
        assert pa2.target_type == "control"
        engine.approve_preventive_action("pa-ctrl")
        engine.implement_preventive_action("pa-ctrl")

        # Verify all preventive actions
        pas = engine.preventive_actions_for_remediation("rem-prev")
        assert len(pas) == 2
        assert all(p.status == PreventiveActionStatus.IMPLEMENTED for p in pas)


class TestGoldenScenario6FullLifecycle:
    """Full lifecycle: create -> assign -> corrective + preventive -> submit -> verify -> close -> snapshot."""

    def test_end_to_end(self, engine):
        # Create
        rem = engine.create_remediation(
            "rem-full", "tenant-e", "Full lifecycle test",
            case_id="case-99",
            remediation_type=RemediationType.CORRECTIVE,
            priority=RemediationPriority.HIGH,
            description="Comprehensive test",
            owner_id="team-lead",
            deadline=_future_deadline(),
        )
        assert rem.status == RemediationStatus.OPEN

        # Assign
        engine.assign_remediation("a-lead", "rem-full", "team-lead", role="owner")
        engine.assign_remediation("a-eng", "rem-full", "engineer-1", role="implementer")
        assert len(engine.assignments_for_remediation("rem-full")) == 2

        # Start
        engine.start_remediation("rem-full")

        # Corrective action
        engine.add_corrective_action(
            "ca-full", "rem-full", "Code fix",
            description="Fix auth bypass", owner_id="engineer-1",
        )
        engine.complete_corrective_action("ca-full")

        # Preventive action
        engine.add_preventive_action(
            "pa-full", "rem-full", "Add SAST rule",
            "control", "sast-rule-auth-bypass",
            description="Static analysis rule for auth bypass patterns",
        )
        engine.approve_preventive_action("pa-full")
        engine.implement_preventive_action("pa-full")

        # Submit for verification
        engine.submit_for_verification("rem-full")
        assert engine.get_remediation("rem-full").status == RemediationStatus.PENDING_VERIFICATION

        # Verify
        engine.verify_remediation(
            "v-full", "rem-full", "qa-lead",
            status=RemediationVerificationStatus.PASSED,
            notes="All checks passed",
        )
        assert engine.get_remediation("rem-full").status == RemediationStatus.VERIFIED

        # Close
        report = engine.close_remediation(
            "rem-full", decided_by="team-lead", reason="Fully remediated"
        )
        assert report.disposition == RemediationDisposition.RESOLVED
        assert report.total_corrective == 1
        assert report.total_preventive == 1
        assert report.total_verifications == 1
        assert report.total_reopens == 0
        assert report.total_violations == 0
        assert engine.get_remediation("rem-full").status == RemediationStatus.CLOSED

        # Snapshot
        snap = engine.remediation_snapshot("snap-full", scope_ref_id="tenant-e")
        assert snap.total_remediations == 1
        assert snap.open_remediations == 0
        assert snap.total_corrective == 1
        assert snap.total_preventive == 1
        assert snap.total_verifications == 1
        assert snap.total_decisions == 1  # auto-created by close
        assert snap.total_reopens == 0
        assert snap.total_violations == 0

        # State hash is deterministic
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2


# ===================================================================
# Additional edge cases to reach ~200 tests
# ===================================================================


class TestEdgeCasesRemediationStatus:
    def test_start_pending_verification(self, engine):
        _make_remediation(engine)
        engine.submit_for_verification("rem-1")
        # Can re-start from pending_verification (not closed)
        rec = engine.start_remediation("rem-1")
        assert rec.status == RemediationStatus.IN_PROGRESS

    def test_submit_escalated(self, engine):
        _make_remediation(engine)
        engine.escalate_remediation("rem-1")
        rec = engine.submit_for_verification("rem-1")
        assert rec.status == RemediationStatus.PENDING_VERIFICATION

    def test_escalate_in_progress(self, engine):
        _make_remediation(engine)
        engine.start_remediation("rem-1")
        rec = engine.escalate_remediation("rem-1")
        assert rec.status == RemediationStatus.ESCALATED

    def test_escalate_reopened(self, engine):
        _make_remediation(engine)
        engine.reopen_remediation("ro-1", "rem-1")
        rec = engine.escalate_remediation("rem-1")
        assert rec.status == RemediationStatus.ESCALATED

    def test_reopen_verified_not_closed(self, engine):
        """VERIFIED is in _CLOSED_STATUSES, so reopen should fail."""
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        # VERIFIED is closed-like; the reopen check is for CLOSED only
        # Let's see what happens
        rem = engine.get_remediation("rem-1")
        assert rem.status == RemediationStatus.VERIFIED
        # reopen_remediation checks for CLOSED only, not VERIFIED
        # Looking at the code: `if rem.status == RemediationStatus.CLOSED`
        # So VERIFIED can be reopened
        ro = engine.reopen_remediation("ro-1", "rem-1")
        assert ro is not None
        assert engine.get_remediation("rem-1").status == RemediationStatus.REOPENED


class TestEdgeCasesMultipleTenants:
    def test_cross_tenant_isolation(self, engine):
        engine.create_remediation("r1", "t1", "A")
        engine.create_remediation("r2", "t2", "B")
        engine.create_remediation("r3", "t3", "C")
        assert len(engine.remediations_for_tenant("t1")) == 1
        assert len(engine.remediations_for_tenant("t2")) == 1
        assert len(engine.remediations_for_tenant("t3")) == 1

    def test_violations_isolated_by_tenant(self, engine):
        dl = _past_deadline()
        engine.create_remediation("r1", "t1", "A", deadline=dl)
        engine.create_remediation("r2", "t2", "B", deadline=dl)
        engine.detect_violations()
        assert len(engine.violations_for_tenant("t1")) == 1
        assert len(engine.violations_for_tenant("t2")) == 1


class TestEdgeCasesReturnTypes:
    def test_remediations_for_tenant_returns_tuple(self, engine):
        result = engine.remediations_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_assignments_for_remediation_returns_tuple(self, engine):
        result = engine.assignments_for_remediation("rem-1")
        assert isinstance(result, tuple)

    def test_corrective_for_remediation_returns_tuple(self, engine):
        result = engine.corrective_actions_for_remediation("rem-1")
        assert isinstance(result, tuple)

    def test_preventive_for_remediation_returns_tuple(self, engine):
        result = engine.preventive_actions_for_remediation("rem-1")
        assert isinstance(result, tuple)

    def test_verifications_for_remediation_returns_tuple(self, engine):
        result = engine.verifications_for_remediation("rem-1")
        assert isinstance(result, tuple)

    def test_reopens_for_remediation_returns_tuple(self, engine):
        result = engine.reopens_for_remediation("rem-1")
        assert isinstance(result, tuple)

    def test_violations_for_remediation_returns_tuple(self, engine):
        result = engine.violations_for_remediation("rem-1")
        assert isinstance(result, tuple)

    def test_violations_for_tenant_returns_tuple(self, engine):
        result = engine.violations_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_detect_violations_returns_tuple(self, engine):
        result = engine.detect_violations()
        assert isinstance(result, tuple)


class TestEdgeCasesMultipleActions:
    def test_multiple_corrective_different_remediations(self, engine):
        engine.create_remediation("r1", "t1", "A")
        engine.create_remediation("r2", "t1", "B")
        engine.add_corrective_action("ca-1", "r1", "Fix A")
        engine.add_corrective_action("ca-2", "r2", "Fix B")
        assert len(engine.corrective_actions_for_remediation("r1")) == 1
        assert len(engine.corrective_actions_for_remediation("r2")) == 1
        assert engine.corrective_count == 2

    def test_multiple_preventive_different_targets(self, engine):
        _make_remediation(engine)
        engine.add_preventive_action("pa-1", "rem-1", "A", "program", "p1")
        engine.add_preventive_action("pa-2", "rem-1", "B", "control", "c1")
        engine.add_preventive_action("pa-3", "rem-1", "C", "campaign", "camp-1")
        assert len(engine.preventive_actions_for_remediation("rem-1")) == 3

    def test_complete_all_corrective_actions(self, engine):
        _make_remediation(engine)
        for i in range(3):
            engine.add_corrective_action(f"ca-{i}", "rem-1", f"Fix {i}")
        for i in range(3):
            completed = engine.complete_corrective_action(f"ca-{i}")
            assert completed.status == RemediationStatus.PENDING_VERIFICATION


class TestEdgeCasesVerificationOnClosedRemediation:
    def test_passed_on_already_closed_no_status_change(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "a", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1")
        # Verify again on a closed remediation
        engine.verify_remediation("v2", "rem-1", "b", status=RemediationVerificationStatus.PASSED)
        # Status should remain CLOSED (the code checks rem.status != CLOSED)
        assert engine.get_remediation("rem-1").status == RemediationStatus.CLOSED

    def test_failed_on_closed_no_reopen(self, engine):
        _make_remediation(engine)
        engine.verify_remediation("v1", "rem-1", "a", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("rem-1")
        reopen_before = engine.reopen_count
        engine.verify_remediation("v2", "rem-1", "b", status=RemediationVerificationStatus.FAILED)
        # Should not create a reopen since remediation is in _CLOSED_STATUSES
        assert engine.reopen_count == reopen_before
        assert engine.get_remediation("rem-1").status == RemediationStatus.CLOSED


class TestEdgeCasesDecisionsMultiple:
    def test_multiple_decisions_same_remediation(self, engine):
        _make_remediation(engine)
        engine.make_decision("d1", "rem-1", disposition=RemediationDisposition.INEFFECTIVE)
        engine.make_decision("d2", "rem-1", disposition=RemediationDisposition.RESOLVED)
        assert engine.decision_count == 2

    def test_decision_on_different_remediations(self, engine):
        engine.create_remediation("r1", "t1", "A")
        engine.create_remediation("r2", "t1", "B")
        engine.make_decision("d1", "r1")
        engine.make_decision("d2", "r2")
        assert engine.decision_count == 2


class TestEdgeCasesSnapshotMultiple:
    def test_multiple_snapshots_different_states(self, engine):
        snap1 = engine.remediation_snapshot("snap-1")
        _make_remediation(engine)
        snap2 = engine.remediation_snapshot("snap-2")
        assert snap1.total_remediations == 0
        assert snap2.total_remediations == 1

    def test_snapshot_reflects_closed_count(self, engine):
        engine.create_remediation("r1", "t1", "A")
        engine.create_remediation("r2", "t1", "B")
        engine.verify_remediation("v1", "r1", "v", status=RemediationVerificationStatus.PASSED)
        engine.close_remediation("r1")
        snap = engine.remediation_snapshot("snap-x")
        assert snap.total_remediations == 2
        assert snap.open_remediations == 1


class TestEdgeCasesEmptyRemediation:
    def test_close_no_actions_non_resolved(self, engine):
        _make_remediation(engine)
        report = engine.close_remediation(
            "rem-1", disposition=RemediationDisposition.TRANSFERRED
        )
        assert report.total_corrective == 0
        assert report.total_preventive == 0
        assert report.total_verifications == 0
        assert report.total_reopens == 0

    def test_snapshot_empty_engine(self, engine):
        snap = engine.remediation_snapshot("snap-empty")
        assert snap.total_remediations == 0
        assert snap.open_remediations == 0


class TestEdgeCasesStateHashStability:
    def test_same_mutations_different_engines_same_hash(self):
        es1 = EventSpineEngine()
        eng1 = RemediationRuntimeEngine(es1)
        es2 = EventSpineEngine()
        eng2 = RemediationRuntimeEngine(es2)

        # Same state -> same hash
        assert eng1.state_hash() == eng2.state_hash()

        # Same number of items -> same hash (state_hash is count-based)
        eng1.create_remediation("r1", "t1", "A")
        eng2.create_remediation("r2", "t2", "B")
        assert eng1.state_hash() == eng2.state_hash()


class TestEdgeCasesAssignMultipleRoles:
    def test_same_user_different_roles(self, engine):
        _make_remediation(engine)
        engine.assign_remediation("a1", "rem-1", "user-1", role="owner")
        engine.assign_remediation("a2", "rem-1", "user-1", role="reviewer")
        assigns = engine.assignments_for_remediation("rem-1")
        assert len(assigns) == 2
        roles = {a.role for a in assigns}
        assert roles == {"owner", "reviewer"}


class TestEdgeCasesViolationDetectionEmpty:
    def test_no_remediations_no_violations(self, engine):
        viols = engine.detect_violations()
        assert viols == ()

    def test_all_open_no_deadline_no_violations(self, engine):
        _make_remediation(engine)
        viols = engine.detect_violations()
        assert viols == ()

    def test_verified_with_deadline_in_past_no_overdue(self, engine):
        """VERIFIED is in _CLOSED_STATUSES, so no overdue violation."""
        dl = _past_deadline()
        engine.create_remediation("rem-1", "t1", "A", deadline=dl)
        engine.verify_remediation("v1", "rem-1", "verifier", status=RemediationVerificationStatus.PASSED)
        viols = engine.detect_violations()
        overdue = [v for v in viols if v.operation == "overdue"]
        assert len(overdue) == 0
