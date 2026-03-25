"""Comprehensive tests for ChangeRuntimeEngine.

Covers: constructor, create/get/status, plan, approval, execution,
pause/resume/abort/rollback, completion, evidence, impact assessment,
status transitions, queries, properties, state_hash, events, and
8 golden scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.change_runtime import ChangeRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.change_runtime import (
    ChangeApprovalBinding,
    ChangeEvidenceKind,
    ChangeEvidence,
    ChangeExecution,
    ChangeImpactAssessment,
    ChangeOutcome,
    ChangePlan,
    ChangeRequest,
    ChangeScope,
    ChangeStatus,
    ChangeStep,
    ChangeType,
    RollbackDisposition,
    RollbackPlan,
    RolloutMode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> tuple[ChangeRuntimeEngine, EventSpineEngine]:
    es = EventSpineEngine()
    cre = ChangeRuntimeEngine(es)
    return cre, es


def _make_change(
    cre: ChangeRuntimeEngine,
    change_id: str = "chg-1",
    title: str = "Test Change",
    change_type: ChangeType = ChangeType.CONFIGURATION,
    **kwargs,
) -> ChangeRequest:
    return cre.create_change_request(change_id, title, change_type, **kwargs)


def _two_step_plan(cre: ChangeRuntimeEngine, change_id: str = "chg-1", plan_id: str = "plan-1"):
    return cre.plan_change(plan_id, change_id, "Plan A", [
        {"step_id": "s1", "action": "act-1", "target_ref_id": "t1", "description": "d1"},
        {"step_id": "s2", "action": "act-2", "target_ref_id": "t2", "description": "d2"},
    ])


def _approve(cre: ChangeRuntimeEngine, change_id: str = "chg-1"):
    cre.submit_for_approval(change_id)
    return cre.approve_change("apr-1", change_id, "admin")


def _drive_to_in_progress(cre: ChangeRuntimeEngine, change_id: str = "chg-1"):
    """Create change, plan, approve, execute first step."""
    _make_change(cre, change_id)
    _two_step_plan(cre, change_id)
    _approve(cre, change_id)
    cre.execute_change_step(change_id, "s1")


# ===================================================================
# 1. Constructor validation
# ===================================================================

class TestConstructor:
    def test_valid_construction(self):
        cre, _ = _engine()
        assert cre.change_count == 0

    def test_requires_event_spine_engine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ChangeRuntimeEngine("not-an-engine")  # type: ignore

    def test_requires_event_spine_engine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ChangeRuntimeEngine(None)  # type: ignore

    def test_requires_event_spine_engine_dict(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ChangeRuntimeEngine({})  # type: ignore

    def test_initial_counts_are_zero(self):
        cre, _ = _engine()
        assert cre.change_count == 0
        assert cre.plan_count == 0
        assert cre.outcome_count == 0


# ===================================================================
# 2. create_change_request
# ===================================================================

class TestCreateChangeRequest:
    def test_basic_creation(self):
        cre, _ = _engine()
        cr = _make_change(cre)
        assert cr.change_id == "chg-1"
        assert cr.title == "Test Change"
        assert cr.change_type == ChangeType.CONFIGURATION
        assert cr.status == ChangeStatus.DRAFT
        assert cr.approval_required is True

    def test_duplicate_raises(self):
        cre, _ = _engine()
        _make_change(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            _make_change(cre)

    def test_change_count_increments(self):
        cre, _ = _engine()
        _make_change(cre, "c1")
        _make_change(cre, "c2")
        assert cre.change_count == 2

    def test_default_scope_is_global(self):
        cre, _ = _engine()
        cr = _make_change(cre)
        assert cr.scope == ChangeScope.GLOBAL

    def test_default_rollout_mode_immediate(self):
        cre, _ = _engine()
        cr = _make_change(cre)
        assert cr.rollout_mode == RolloutMode.IMMEDIATE

    def test_approval_required_false(self):
        cre, _ = _engine()
        cr = _make_change(cre, approval_required=False)
        assert cr.approval_required is False

    def test_custom_metadata(self):
        cre, _ = _engine()
        cr = _make_change(cre, metadata={"key": "val"})
        assert cr.metadata["key"] == "val"

    def test_scope_ref_id_defaults_to_change_id(self):
        cre, _ = _engine()
        cr = _make_change(cre)
        assert cr.scope_ref_id == "chg-1"

    def test_custom_scope_ref_id(self):
        cre, _ = _engine()
        cr = _make_change(cre, scope_ref_id="custom")
        assert cr.scope_ref_id == "custom"

    def test_custom_priority(self):
        cre, _ = _engine()
        cr = _make_change(cre, priority="high")
        assert cr.priority == "high"

    def test_custom_requested_by(self):
        cre, _ = _engine()
        cr = _make_change(cre, requested_by="alice")
        assert cr.requested_by == "alice"

    def test_custom_reason(self):
        cre, _ = _engine()
        cr = _make_change(cre, reason="perf improvement")
        assert cr.reason == "perf improvement"

    def test_recommendation_id(self):
        cre, _ = _engine()
        cr = _make_change(cre, recommendation_id="rec-42")
        assert cr.recommendation_id == "rec-42"

    def test_description(self):
        cre, _ = _engine()
        cr = _make_change(cre, description="desc here")
        assert cr.description == "desc here"

    # all change types
    @pytest.mark.parametrize("ct", list(ChangeType))
    def test_all_change_types(self, ct):
        cre, _ = _engine()
        cr = _make_change(cre, change_type=ct)
        assert cr.change_type == ct

    # all scopes
    @pytest.mark.parametrize("scope", list(ChangeScope))
    def test_all_scopes(self, scope):
        cre, _ = _engine()
        cr = _make_change(cre, scope=scope)
        assert cr.scope == scope

    # all rollout modes
    @pytest.mark.parametrize("rm", list(RolloutMode))
    def test_all_rollout_modes(self, rm):
        cre, _ = _engine()
        cr = _make_change(cre, rollout_mode=rm)
        assert cr.rollout_mode == rm

    def test_created_at_is_set(self):
        cre, _ = _engine()
        cr = _make_change(cre)
        assert cr.created_at != ""

    def test_emits_event(self):
        cre, es = _engine()
        _make_change(cre)
        events = es.list_events()
        assert len(events) >= 1
        assert events[0].payload["action"] == "change_request_created"


# ===================================================================
# 3. plan_change
# ===================================================================

class TestPlanChange:
    def test_basic_plan(self):
        cre, _ = _engine()
        _make_change(cre)
        plan = _two_step_plan(cre)
        assert plan.plan_id == "plan-1"
        assert plan.change_id == "chg-1"
        assert plan.title == "Plan A"
        assert len(plan.step_ids) == 2

    def test_unknown_change_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.plan_change("p1", "no-such", "title", [])

    def test_duplicate_plan_raises(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            _two_step_plan(cre)

    def test_plan_count(self):
        cre, _ = _engine()
        _make_change(cre, "c1")
        _make_change(cre, "c2")
        cre.plan_change("p1", "c1", "P1", [{"step_id": "s1", "action": "a"}])
        cre.plan_change("p2", "c2", "P2", [{"step_id": "s2", "action": "b"}])
        assert cre.plan_count == 2

    def test_step_ids_created(self):
        cre, _ = _engine()
        _make_change(cre)
        plan = _two_step_plan(cre)
        assert "s1" in plan.step_ids
        assert "s2" in plan.step_ids

    def test_get_plan(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        p = cre.get_plan("plan-1")
        assert p is not None
        assert p.plan_id == "plan-1"

    def test_get_plan_not_found(self):
        cre, _ = _engine()
        assert cre.get_plan("nope") is None

    def test_rollout_mode_inherited(self):
        cre, _ = _engine()
        _make_change(cre, rollout_mode=RolloutMode.CANARY)
        plan = _two_step_plan(cre)
        assert plan.rollout_mode == RolloutMode.CANARY

    def test_rollout_mode_override(self):
        cre, _ = _engine()
        _make_change(cre, rollout_mode=RolloutMode.CANARY)
        plan = cre.plan_change("p1", "chg-1", "P", [], rollout_mode=RolloutMode.PHASED)
        assert plan.rollout_mode == RolloutMode.PHASED

    def test_estimated_duration(self):
        cre, _ = _engine()
        _make_change(cre)
        plan = cre.plan_change("p1", "chg-1", "P", [], estimated_duration_seconds=120.0)
        assert plan.estimated_duration_seconds == 120.0

    def test_step_ordinals(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        steps = cre.get_steps("chg-1")
        ordinals = sorted(s.ordinal for s in steps)
        assert ordinals == [0, 1]

    def test_step_auto_id(self):
        cre, _ = _engine()
        _make_change(cre)
        plan = cre.plan_change("p1", "chg-1", "P", [
            {"action": "do-something"},
        ])
        assert len(plan.step_ids) == 1
        assert plan.step_ids[0].startswith("p1-step-")

    def test_plan_emits_event(self):
        cre, es = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        events = es.list_events()
        actions = [e.payload["action"] for e in events]
        assert "change_planned" in actions


# ===================================================================
# 4. submit_for_approval
# ===================================================================

class TestSubmitForApproval:
    def test_draft_to_pending_approval(self):
        cre, _ = _engine()
        _make_change(cre)
        result = cre.submit_for_approval("chg-1")
        assert result == ChangeStatus.PENDING_APPROVAL
        assert cre.get_change_status("chg-1") == ChangeStatus.PENDING_APPROVAL

    def test_submit_unknown_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.submit_for_approval("nope")

    def test_submit_non_draft_raises(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.submit_for_approval("chg-1")

    def test_submit_emits_event(self):
        cre, es = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_submitted_for_approval" in actions


# ===================================================================
# 5. approve_change
# ===================================================================

class TestApproveChange:
    def test_approve_true_transitions_to_approved(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        binding = cre.approve_change("apr-1", "chg-1", "admin")
        assert binding.approved is True
        assert cre.get_change_status("chg-1") == ChangeStatus.APPROVED

    def test_approve_false_transitions_to_aborted(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        binding = cre.approve_change("apr-1", "chg-1", "admin", approved=False)
        assert binding.approved is False
        assert cre.get_change_status("chg-1") == ChangeStatus.ABORTED

    def test_approve_from_draft(self):
        cre, _ = _engine()
        _make_change(cre)
        binding = cre.approve_change("apr-1", "chg-1", "admin")
        assert cre.get_change_status("chg-1") == ChangeStatus.APPROVED

    def test_approval_unknown_change_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.approve_change("a1", "nope", "admin")

    def test_get_approvals(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        cre.approve_change("apr-1", "chg-1", "admin")
        approvals = cre.get_approvals("chg-1")
        assert len(approvals) == 1
        assert approvals[0].approved_by == "admin"

    def test_get_approvals_empty(self):
        cre, _ = _engine()
        assert cre.get_approvals("chg-1") == ()

    def test_is_approved_after_approval(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        cre.approve_change("apr-1", "chg-1", "admin")
        assert cre.is_approved("chg-1") is True

    def test_is_approved_before_approval(self):
        cre, _ = _engine()
        _make_change(cre)
        assert cre.is_approved("chg-1") is False

    def test_is_approved_for_unknown(self):
        cre, _ = _engine()
        assert cre.is_approved("nope") is False

    def test_approval_with_reason(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        binding = cre.approve_change("apr-1", "chg-1", "admin", reason="looks good")
        assert binding.reason == "looks good"

    def test_approve_emits_event(self):
        cre, es = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        cre.approve_change("apr-1", "chg-1", "admin")
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_approval" in actions

    def test_binding_fields(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        b = cre.approve_change("apr-1", "chg-1", "admin")
        assert b.approval_id == "apr-1"
        assert b.change_id == "chg-1"
        assert b.approved_at != ""


# ===================================================================
# 6. execute_change_step
# ===================================================================

class TestExecuteChangeStep:
    def test_approval_guard_blocks_draft(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="requires approval"):
            cre.execute_change_step("chg-1", "s1")

    def test_no_approval_required_executes_from_draft(self):
        cre, _ = _engine()
        _make_change(cre, approval_required=False)
        _two_step_plan(cre)
        step = cre.execute_change_step("chg-1", "s1")
        assert step.status == ChangeStatus.COMPLETED
        assert cre.get_change_status("chg-1") == ChangeStatus.IN_PROGRESS

    def test_first_step_transitions_approved_to_in_progress(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        cre.execute_change_step("chg-1", "s1")
        assert cre.get_change_status("chg-1") == ChangeStatus.IN_PROGRESS

    def test_step_success_true(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        step = cre.execute_change_step("chg-1", "s1")
        assert step.status == ChangeStatus.COMPLETED

    def test_step_success_false(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        step = cre.execute_change_step("chg-1", "s1", success=False)
        assert step.status == ChangeStatus.FAILED

    def test_execution_record_created(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        cre.execute_change_step("chg-1", "s1")
        ex = cre.get_execution("chg-1")
        assert ex is not None
        assert ex.change_id == "chg-1"
        assert ex.steps_total == 2

    def test_execution_steps_completed_updated(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        cre.execute_change_step("chg-1", "s1")
        cre.execute_change_step("chg-1", "s2")
        ex = cre.get_execution("chg-1")
        assert ex.steps_completed == 2

    def test_execution_steps_failed_updated(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        cre.execute_change_step("chg-1", "s1", success=False)
        ex = cre.get_execution("chg-1")
        assert ex.steps_failed == 1

    def test_step_metadata(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        step = cre.execute_change_step("chg-1", "s1", metadata={"x": 1})
        assert step.metadata["x"] == 1

    def test_unknown_change_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.execute_change_step("nope", "s1")

    def test_unknown_step_raises(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="step .* not found"):
            cre.execute_change_step("chg-1", "no-such-step")

    def test_execute_emits_event(self):
        cre, es = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        cre.execute_change_step("chg-1", "s1")
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_step_executed" in actions

    def test_step_completed_at_set(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        step = cre.execute_change_step("chg-1", "s1")
        assert step.completed_at != ""

    def test_step_started_at_set(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        step = cre.execute_change_step("chg-1", "s1")
        assert step.started_at != ""


# ===================================================================
# 7. pause_change / resume_change
# ===================================================================

class TestPauseResume:
    def test_pause_in_progress(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        result = cre.pause_change("chg-1")
        assert result == ChangeStatus.PAUSED
        assert cre.get_change_status("chg-1") == ChangeStatus.PAUSED

    def test_resume_paused(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        result = cre.resume_change("chg-1")
        assert result == ChangeStatus.IN_PROGRESS
        assert cre.get_change_status("chg-1") == ChangeStatus.IN_PROGRESS

    def test_pause_with_reason(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1", reason="maintenance window")
        assert cre.get_change_status("chg-1") == ChangeStatus.PAUSED

    def test_pause_non_in_progress_raises(self):
        cre, _ = _engine()
        _make_change(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.pause_change("chg-1")

    def test_resume_completed_raises(self):
        cre, _ = _engine()
        _make_change(cre, approval_required=False)
        _two_step_plan(cre)
        cre.execute_change_step("chg-1", "s1")
        cre.execute_change_step("chg-1", "s2")
        cre.complete_change("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.resume_change("chg-1")

    def test_pause_unknown_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.pause_change("nope")

    def test_resume_unknown_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.resume_change("nope")

    def test_pause_emits_event(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_paused" in actions

    def test_resume_emits_event(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        cre.resume_change("chg-1")
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_resumed" in actions

    def test_multiple_pause_resume_cycles(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        cre.resume_change("chg-1")
        cre.pause_change("chg-1")
        cre.resume_change("chg-1")
        assert cre.get_change_status("chg-1") == ChangeStatus.IN_PROGRESS

    def test_is_approved_while_paused(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        assert cre.is_approved("chg-1") is True


# ===================================================================
# 8. abort_change
# ===================================================================

class TestAbortChange:
    def test_abort_from_draft(self):
        """DRAFT has no direct transition to ABORTED in the map,
        so this should raise."""
        cre, _ = _engine()
        _make_change(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.abort_change("chg-1")

    def test_abort_from_pending_approval(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        # PENDING_APPROVAL -> ABORTED is valid via approve_change(approved=False)
        # but abort_change also uses _transition; let's check.
        # Actually PENDING_APPROVAL -> ABORTED IS a valid transition.
        result = cre.abort_change("chg-1")
        assert result == ChangeStatus.ABORTED

    def test_abort_from_approved(self):
        cre, _ = _engine()
        _make_change(cre)
        _approve(cre)
        result = cre.abort_change("chg-1")
        assert result == ChangeStatus.ABORTED

    def test_abort_from_in_progress(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        result = cre.abort_change("chg-1")
        assert result == ChangeStatus.ABORTED

    def test_abort_from_paused(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        result = cre.abort_change("chg-1")
        assert result == ChangeStatus.ABORTED

    def test_abort_with_reason(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.abort_change("chg-1", reason="budget exceeded")
        assert cre.get_change_status("chg-1") == ChangeStatus.ABORTED

    def test_abort_unknown_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.abort_change("nope")

    def test_abort_completed_raises(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.abort_change("chg-1")

    def test_abort_emits_event(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        cre.abort_change("chg-1")
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_aborted" in actions


# ===================================================================
# 9. rollback_change
# ===================================================================

class TestRollbackChange:
    def test_rollback_from_in_progress(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        rb = cre.rollback_change("chg-1")
        assert isinstance(rb, RollbackPlan)
        assert rb.change_id == "chg-1"
        assert rb.disposition == RollbackDisposition.TRIGGERED
        assert cre.get_change_status("chg-1") == ChangeStatus.ROLLED_BACK

    def test_rollback_from_paused(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        rb = cre.rollback_change("chg-1")
        assert cre.get_change_status("chg-1") == ChangeStatus.ROLLED_BACK

    def test_rollback_from_failed(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        # Transition to FAILED is not directly exposed; we need to go through
        # the internal mechanism. Let's use _transition directly or work around.
        # Actually the engine doesn't have a direct "fail" method, but
        # FAILED -> ROLLED_BACK is valid. Let's manually set FAILED state.
        cre._status["chg-1"] = ChangeStatus.FAILED
        rb = cre.rollback_change("chg-1")
        assert cre.get_change_status("chg-1") == ChangeStatus.ROLLED_BACK

    def test_rollback_with_reason(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        rb = cre.rollback_change("chg-1", reason="regression detected")
        assert rb.reason == "regression detected"

    def test_rollback_with_steps(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        rb = cre.rollback_change("chg-1", rollback_steps=["undo-s1", "undo-s2"])
        assert rb.rollback_steps == ("undo-s1", "undo-s2")

    def test_get_rollback(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.rollback_change("chg-1")
        rb = cre.get_rollback("chg-1")
        assert rb is not None
        assert rb.change_id == "chg-1"

    def test_get_rollback_none(self):
        cre, _ = _engine()
        assert cre.get_rollback("chg-1") is None

    def test_rollback_unknown_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.rollback_change("nope")

    def test_rollback_emits_event(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        cre.rollback_change("chg-1")
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_rolled_back" in actions

    def test_rollback_id_non_empty(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        rb = cre.rollback_change("chg-1")
        assert rb.rollback_id != ""

    def test_rollback_terminal(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.rollback_change("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.abort_change("chg-1")


# ===================================================================
# 10. complete_change
# ===================================================================

class TestCompleteChange:
    def test_complete_from_in_progress(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        outcome = cre.complete_change("chg-1")
        assert isinstance(outcome, ChangeOutcome)
        assert outcome.success is True
        assert outcome.change_id == "chg-1"
        assert cre.get_change_status("chg-1") == ChangeStatus.COMPLETED

    def test_complete_with_improvement(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        outcome = cre.complete_change("chg-1", improvement_observed=True, improvement_pct=15.5)
        assert outcome.improvement_observed is True
        assert outcome.improvement_pct == 15.5

    def test_complete_failure(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        outcome = cre.complete_change("chg-1", success=False)
        assert outcome.success is False
        assert outcome.status == ChangeStatus.FAILED

    def test_outcome_count(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        assert cre.outcome_count == 1

    def test_get_outcome(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        o = cre.get_outcome("chg-1")
        assert o is not None
        assert o.change_id == "chg-1"

    def test_get_outcome_none(self):
        cre, _ = _engine()
        assert cre.get_outcome("chg-1") is None

    def test_complete_unknown_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.complete_change("nope")

    def test_complete_from_draft_raises(self):
        """DRAFT -> COMPLETED is not a valid transition."""
        cre, _ = _engine()
        _make_change(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="cannot complete"):
            cre.complete_change("chg-1")

    def test_complete_terminal(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.abort_change("chg-1")

    def test_complete_emits_event(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_completed" in actions

    def test_outcome_evidence_count_zero(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        outcome = cre.complete_change("chg-1")
        assert outcome.evidence_count == 0

    def test_outcome_evidence_count_after_collection(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        cre.collect_evidence("chg-1", ChangeEvidenceKind.METRIC_BEFORE)
        outcome = cre.complete_change("chg-1")
        assert outcome.evidence_count == 2

    def test_outcome_rollback_disposition_not_needed(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        outcome = cre.complete_change("chg-1")
        assert outcome.rollback_disposition == RollbackDisposition.NOT_NEEDED

    def test_outcome_has_execution_id(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        outcome = cre.complete_change("chg-1")
        assert outcome.execution_id != ""

    def test_outcome_completed_at(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        outcome = cre.complete_change("chg-1")
        assert outcome.completed_at != ""


# ===================================================================
# 11. collect_evidence
# ===================================================================

class TestCollectEvidence:
    def test_basic_evidence(self):
        cre, _ = _engine()
        _make_change(cre)
        ev = cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        assert isinstance(ev, ChangeEvidence)
        assert ev.kind == ChangeEvidenceKind.LOG_ENTRY
        assert ev.change_id == "chg-1"

    def test_evidence_with_metric(self):
        cre, _ = _engine()
        _make_change(cre)
        ev = cre.collect_evidence(
            "chg-1", ChangeEvidenceKind.METRIC_BEFORE,
            metric_name="latency", metric_value=42.5,
        )
        assert ev.metric_name == "latency"
        assert ev.metric_value == 42.5

    def test_evidence_with_description(self):
        cre, _ = _engine()
        _make_change(cre)
        ev = cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY, description="test log")
        assert ev.description == "test log"

    def test_evidence_with_metadata(self):
        cre, _ = _engine()
        _make_change(cre)
        ev = cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY, metadata={"k": "v"})
        assert ev.metadata["k"] == "v"

    @pytest.mark.parametrize("kind", list(ChangeEvidenceKind))
    def test_all_evidence_kinds(self, kind):
        cre, _ = _engine()
        _make_change(cre)
        ev = cre.collect_evidence("chg-1", kind)
        assert ev.kind == kind

    def test_multiple_evidence_per_change(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        cre.collect_evidence("chg-1", ChangeEvidenceKind.METRIC_BEFORE)
        cre.collect_evidence("chg-1", ChangeEvidenceKind.METRIC_AFTER)
        evs = cre.get_evidence("chg-1")
        assert len(evs) == 3

    def test_get_evidence_empty(self):
        cre, _ = _engine()
        assert cre.get_evidence("chg-1") == ()

    def test_evidence_unknown_change_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.collect_evidence("nope", ChangeEvidenceKind.LOG_ENTRY)

    def test_evidence_emits_event(self):
        cre, es = _engine()
        _make_change(cre)
        cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_evidence_collected" in actions

    def test_evidence_id_non_empty(self):
        cre, _ = _engine()
        _make_change(cre)
        ev = cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        assert ev.evidence_id != ""

    def test_evidence_collected_at(self):
        cre, _ = _engine()
        _make_change(cre)
        ev = cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        assert ev.collected_at != ""


# ===================================================================
# 12. assess_change_impact
# ===================================================================

class TestAssessChangeImpact:
    def test_basic_assessment(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "latency", 100.0, 80.0)
        assert isinstance(a, ChangeImpactAssessment)
        assert a.metric_name == "latency"
        assert a.baseline_value == 100.0
        assert a.current_value == 80.0

    def test_improvement_calculation_positive(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "throughput", 100.0, 120.0)
        assert a.improvement_pct == pytest.approx(20.0)

    def test_improvement_calculation_negative(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "latency", 100.0, 80.0)
        assert a.improvement_pct == pytest.approx(-20.0)

    def test_zero_baseline(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "errors", 0.0, 5.0)
        assert a.improvement_pct == 0.0

    def test_custom_confidence(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "m", 10.0, 12.0, confidence=0.95)
        assert a.confidence == 0.95

    def test_custom_window(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "m", 10.0, 12.0, assessment_window_seconds=7200.0)
        assert a.assessment_window_seconds == 7200.0

    def test_unknown_change_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.assess_change_impact("nope", "m", 10.0, 12.0)

    def test_assessment_emits_event(self):
        cre, es = _engine()
        _make_change(cre)
        cre.assess_change_impact("chg-1", "m", 10.0, 12.0)
        actions = [e.payload["action"] for e in es.list_events()]
        assert "change_impact_assessed" in actions

    def test_assessment_id_non_empty(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "m", 10.0, 12.0)
        assert a.assessment_id != ""

    def test_negative_baseline(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "pnl", -100.0, -50.0)
        # improvement = (-50 - (-100)) / abs(-100) * 100 = 50%
        assert a.improvement_pct == pytest.approx(50.0)

    def test_same_values_zero_improvement(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "m", 50.0, 50.0)
        assert a.improvement_pct == pytest.approx(0.0)


# ===================================================================
# 13. Status transition validation
# ===================================================================

class TestStatusTransitions:
    """Invalid transitions should raise RuntimeCoreInvariantError."""

    def test_draft_to_completed_invalid(self):
        cre, _ = _engine()
        _make_change(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="cannot complete"):
            cre.complete_change("chg-1")

    def test_draft_to_paused_invalid(self):
        cre, _ = _engine()
        _make_change(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.pause_change("chg-1")

    def test_draft_to_rolled_back_invalid(self):
        cre, _ = _engine()
        _make_change(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.rollback_change("chg-1")

    def test_pending_to_in_progress_invalid(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        # PENDING_APPROVAL does not have IN_PROGRESS in valid transitions
        with pytest.raises(RuntimeCoreInvariantError):
            cre.resume_change("chg-1")

    def test_completed_is_terminal(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.pause_change("chg-1")

    def test_aborted_is_terminal(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.abort_change("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.resume_change("chg-1")

    def test_rolled_back_is_terminal(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.rollback_change("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.pause_change("chg-1")

    def test_approved_to_paused_invalid(self):
        cre, _ = _engine()
        _make_change(cre)
        _approve(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.pause_change("chg-1")

    def test_draft_to_aborted_invalid(self):
        cre, _ = _engine()
        _make_change(cre)
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.abort_change("chg-1")

    def test_completed_to_rolled_back_invalid(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="invalid transition"):
            cre.rollback_change("chg-1")

    def test_aborted_to_completed_invalid(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.abort_change("chg-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot complete"):
            cre.complete_change("chg-1")

    def test_valid_draft_to_pending_approval(self):
        cre, _ = _engine()
        _make_change(cre)
        st = cre.submit_for_approval("chg-1")
        assert st == ChangeStatus.PENDING_APPROVAL

    def test_valid_draft_to_approved(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.approve_change("a1", "chg-1", "admin")
        assert cre.get_change_status("chg-1") == ChangeStatus.APPROVED

    def test_valid_draft_to_in_progress_no_approval(self):
        cre, _ = _engine()
        _make_change(cre, approval_required=False)
        _two_step_plan(cre)
        cre.execute_change_step("chg-1", "s1")
        assert cre.get_change_status("chg-1") == ChangeStatus.IN_PROGRESS

    def test_valid_approved_to_in_progress(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        cre.execute_change_step("chg-1", "s1")
        assert cre.get_change_status("chg-1") == ChangeStatus.IN_PROGRESS

    def test_valid_in_progress_to_paused(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        assert cre.get_change_status("chg-1") == ChangeStatus.PAUSED

    def test_valid_paused_to_in_progress(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        cre.resume_change("chg-1")
        assert cre.get_change_status("chg-1") == ChangeStatus.IN_PROGRESS


# ===================================================================
# 14. Queries
# ===================================================================

class TestQueries:
    def test_get_change_found(self):
        cre, _ = _engine()
        _make_change(cre)
        cr = cre.get_change("chg-1")
        assert cr is not None
        assert cr.change_id == "chg-1"

    def test_get_change_not_found(self):
        cre, _ = _engine()
        assert cre.get_change("nope") is None

    def test_get_change_status_found(self):
        cre, _ = _engine()
        _make_change(cre)
        assert cre.get_change_status("chg-1") == ChangeStatus.DRAFT

    def test_get_change_status_not_found_raises(self):
        cre, _ = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            cre.get_change_status("nope")

    def test_get_execution_found(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        ex = cre.get_execution("chg-1")
        assert ex is not None

    def test_get_execution_not_found(self):
        cre, _ = _engine()
        assert cre.get_execution("nope") is None

    def test_get_outcome_found(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        o = cre.get_outcome("chg-1")
        assert o is not None

    def test_get_outcome_not_found(self):
        cre, _ = _engine()
        assert cre.get_outcome("nope") is None

    def test_get_evidence_found(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        evs = cre.get_evidence("chg-1")
        assert len(evs) == 1

    def test_get_evidence_not_found(self):
        cre, _ = _engine()
        assert cre.get_evidence("nope") == ()

    def test_get_rollback_found(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.rollback_change("chg-1")
        rb = cre.get_rollback("chg-1")
        assert rb is not None

    def test_get_rollback_not_found(self):
        cre, _ = _engine()
        assert cre.get_rollback("nope") is None

    def test_get_steps_found(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        steps = cre.get_steps("chg-1")
        assert len(steps) == 2

    def test_get_steps_none(self):
        cre, _ = _engine()
        assert cre.get_steps("nope") == ()

    def test_get_steps_returns_tuple(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        steps = cre.get_steps("chg-1")
        assert isinstance(steps, tuple)

    def test_get_evidence_returns_tuple(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        evs = cre.get_evidence("chg-1")
        assert isinstance(evs, tuple)

    def test_get_approvals_returns_tuple(self):
        cre, _ = _engine()
        _make_change(cre)
        _approve(cre)
        approvals = cre.get_approvals("chg-1")
        assert isinstance(approvals, tuple)


# ===================================================================
# 15. Properties
# ===================================================================

class TestProperties:
    def test_change_count(self):
        cre, _ = _engine()
        assert cre.change_count == 0
        _make_change(cre, "c1")
        assert cre.change_count == 1
        _make_change(cre, "c2")
        assert cre.change_count == 2

    def test_plan_count(self):
        cre, _ = _engine()
        assert cre.plan_count == 0
        _make_change(cre)
        _two_step_plan(cre)
        assert cre.plan_count == 1

    def test_outcome_count(self):
        cre, _ = _engine()
        assert cre.outcome_count == 0
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        assert cre.outcome_count == 1


# ===================================================================
# 16. state_hash
# ===================================================================

class TestStateHash:
    def test_is_string(self):
        cre, _ = _engine()
        assert isinstance(cre.state_hash(), str)

    def test_deterministic(self):
        cre, _ = _engine()
        h1 = cre.state_hash()
        h2 = cre.state_hash()
        assert h1 == h2

    def test_changes_with_state(self):
        cre, _ = _engine()
        h1 = cre.state_hash()
        _make_change(cre)
        h2 = cre.state_hash()
        assert h1 != h2

    def test_different_statuses_different_hash(self):
        cre, _ = _engine()
        _make_change(cre)
        h_draft = cre.state_hash()
        cre.submit_for_approval("chg-1")
        h_pending = cre.state_hash()
        assert h_draft != h_pending

    def test_length_16(self):
        cre, _ = _engine()
        assert len(cre.state_hash()) == 64

    def test_is_method_not_property(self):
        cre, _ = _engine()
        # Should be callable
        assert callable(cre.state_hash)
        assert cre.state_hash() == cre.state_hash()

    def test_two_changes_vs_one(self):
        cre1, _ = _engine()
        _make_change(cre1, "c1")
        h1 = cre1.state_hash()

        cre2, es2 = _engine()
        _make_change(cre2, "c1")
        _make_change(cre2, "c2")
        h2 = cre2.state_hash()
        assert h1 != h2


# ===================================================================
# 17. Events: all mutations emit events
# ===================================================================

class TestEventEmission:
    def test_create_emits(self):
        cre, es = _engine()
        _make_change(cre)
        assert es.event_count >= 1

    def test_plan_emits(self):
        cre, es = _engine()
        _make_change(cre)
        before = es.event_count
        _two_step_plan(cre)
        assert es.event_count > before

    def test_submit_emits(self):
        cre, es = _engine()
        _make_change(cre)
        before = es.event_count
        cre.submit_for_approval("chg-1")
        assert es.event_count > before

    def test_approve_emits(self):
        cre, es = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        before = es.event_count
        cre.approve_change("a1", "chg-1", "admin")
        assert es.event_count > before

    def test_execute_step_emits(self):
        cre, es = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        before = es.event_count
        cre.execute_change_step("chg-1", "s1")
        assert es.event_count > before

    def test_pause_emits(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        before = es.event_count
        cre.pause_change("chg-1")
        assert es.event_count > before

    def test_resume_emits(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        before = es.event_count
        cre.resume_change("chg-1")
        assert es.event_count > before

    def test_abort_emits(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        before = es.event_count
        cre.abort_change("chg-1")
        assert es.event_count > before

    def test_rollback_emits(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        before = es.event_count
        cre.rollback_change("chg-1")
        assert es.event_count > before

    def test_complete_emits(self):
        cre, es = _engine()
        _drive_to_in_progress(cre)
        before = es.event_count
        cre.complete_change("chg-1")
        assert es.event_count > before

    def test_evidence_emits(self):
        cre, es = _engine()
        _make_change(cre)
        before = es.event_count
        cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        assert es.event_count > before

    def test_impact_emits(self):
        cre, es = _engine()
        _make_change(cre)
        before = es.event_count
        cre.assess_change_impact("chg-1", "m", 10.0, 12.0)
        assert es.event_count > before

    def test_event_correlation_id_matches_change(self):
        cre, es = _engine()
        _make_change(cre)
        events = es.list_events()
        assert events[0].correlation_id == "chg-1"

    def test_all_events_have_action_in_payload(self):
        cre, es = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        cre.execute_change_step("chg-1", "s1")
        for e in es.list_events():
            assert "action" in e.payload


# ===================================================================
# 18. Golden Scenarios
# ===================================================================

class TestGoldenScenario1_OptimizationRecommendation:
    """Optimization recommendation becomes approved change request."""

    def test_full_flow(self):
        cre, es = _engine()
        # Create change from a recommendation
        cr = cre.create_change_request(
            "chg-opt-1", "Optimize connector preference",
            ChangeType.CONNECTOR_PREFERENCE,
            recommendation_id="rec-99",
            scope=ChangeScope.CONNECTOR,
            scope_ref_id="conn-abc",
            description="Prefer lower-latency connector",
            rollout_mode=RolloutMode.IMMEDIATE,
            requested_by="optimizer-agent",
            reason="latency improvement",
        )
        assert cr.recommendation_id == "rec-99"
        assert cr.status == ChangeStatus.DRAFT

        # Plan it
        plan = cre.plan_change("plan-opt-1", "chg-opt-1", "Connector switch", [
            {"step_id": "s-swap", "action": "swap-connector", "target_ref_id": "conn-abc"},
        ])
        assert len(plan.step_ids) == 1

        # Submit and approve
        cre.submit_for_approval("chg-opt-1")
        assert cre.get_change_status("chg-opt-1") == ChangeStatus.PENDING_APPROVAL
        cre.approve_change("apr-opt-1", "chg-opt-1", "ops-lead", reason="approved by ops")
        assert cre.get_change_status("chg-opt-1") == ChangeStatus.APPROVED

        # Execute
        cre.execute_change_step("chg-opt-1", "s-swap")
        assert cre.get_change_status("chg-opt-1") == ChangeStatus.IN_PROGRESS

        # Complete
        outcome = cre.complete_change("chg-opt-1", improvement_observed=True, improvement_pct=12.0)
        assert outcome.success is True
        assert outcome.improvement_observed is True
        assert cre.get_change_status("chg-opt-1") == ChangeStatus.COMPLETED

        # Events recorded
        assert es.event_count >= 5


class TestGoldenScenario2_CanaryRollout:
    """Canary rollout changes connector preference and records evidence."""

    def test_canary_with_evidence(self):
        cre, es = _engine()
        cr = cre.create_change_request(
            "chg-canary", "Canary connector change",
            ChangeType.CONNECTOR_PREFERENCE,
            rollout_mode=RolloutMode.CANARY,
            scope=ChangeScope.CONNECTOR,
            approval_required=False,
        )
        plan = cre.plan_change("plan-canary", "chg-canary", "Canary plan", [
            {"step_id": "canary-1", "action": "route-10pct", "target_ref_id": "conn-new"},
            {"step_id": "canary-2", "action": "route-100pct", "target_ref_id": "conn-new"},
        ])
        assert plan.rollout_mode == RolloutMode.CANARY

        # Execute first step (no approval needed)
        cre.execute_change_step("chg-canary", "canary-1")
        assert cre.get_change_status("chg-canary") == ChangeStatus.IN_PROGRESS

        # Collect evidence
        ev1 = cre.collect_evidence(
            "chg-canary", ChangeEvidenceKind.METRIC_BEFORE,
            metric_name="error_rate", metric_value=0.05,
        )
        ev2 = cre.collect_evidence(
            "chg-canary", ChangeEvidenceKind.METRIC_AFTER,
            metric_name="error_rate", metric_value=0.03,
        )
        assert ev1.kind == ChangeEvidenceKind.METRIC_BEFORE
        assert ev2.kind == ChangeEvidenceKind.METRIC_AFTER

        # Execute second step
        cre.execute_change_step("chg-canary", "canary-2")

        # Complete
        outcome = cre.complete_change("chg-canary", improvement_observed=True, improvement_pct=40.0)
        assert outcome.evidence_count == 2
        assert outcome.success is True


class TestGoldenScenario3_FailedRolloutTriggerRollback:
    """Failed rollout triggers rollback plan."""

    def test_rollback_on_failure(self):
        cre, es = _engine()
        cre.create_change_request(
            "chg-fail", "Risky routing change",
            ChangeType.ROUTING_RULE,
            scope=ChangeScope.GLOBAL,
        )
        cre.plan_change("plan-fail", "chg-fail", "Route update", [
            {"step_id": "sf1", "action": "update-route", "target_ref_id": "route-main"},
            {"step_id": "sf2", "action": "verify-route", "target_ref_id": "route-main"},
        ])
        _approve(cre, "chg-fail")

        # First step succeeds
        cre.execute_change_step("chg-fail", "sf1")
        # Second step fails
        cre.execute_change_step("chg-fail", "sf2", success=False)

        ex = cre.get_execution("chg-fail")
        assert ex.steps_completed == 1
        assert ex.steps_failed == 1

        # Rollback
        rb = cre.rollback_change("chg-fail", reason="step sf2 failed",
                                  rollback_steps=["undo-sf1"])
        assert rb.disposition == RollbackDisposition.TRIGGERED
        assert cre.get_change_status("chg-fail") == ChangeStatus.ROLLED_BACK


class TestGoldenScenario4_ApprovalRequired:
    """Approval-required change pauses until approval arrives."""

    def test_approval_blocks_execution(self):
        cre, _ = _engine()
        cre.create_change_request(
            "chg-wait", "Budget threshold update",
            ChangeType.BUDGET_THRESHOLD,
            approval_required=True,
        )
        cre.plan_change("plan-wait", "chg-wait", "Budget plan", [
            {"step_id": "sw1", "action": "update-threshold", "target_ref_id": "budget-main"},
        ])

        # Attempt execution without approval
        with pytest.raises(RuntimeCoreInvariantError, match="requires approval"):
            cre.execute_change_step("chg-wait", "sw1")

        # Submit and approve
        cre.submit_for_approval("chg-wait")
        cre.approve_change("apr-wait", "chg-wait", "cfo")

        # Now execution works
        step = cre.execute_change_step("chg-wait", "sw1")
        assert step.status == ChangeStatus.COMPLETED
        assert cre.get_change_status("chg-wait") == ChangeStatus.IN_PROGRESS


class TestGoldenScenario5_DomainPackActivation:
    """Domain-pack activation change updates runtime resolution safely."""

    def test_domain_pack_lifecycle(self):
        cre, es = _engine()
        cr = cre.create_change_request(
            "chg-dp", "Activate healthcare domain pack",
            ChangeType.DOMAIN_PACK_ACTIVATION,
            scope=ChangeScope.DOMAIN_PACK,
            scope_ref_id="dp-healthcare-v2",
            description="Activate v2 of healthcare domain pack",
            rollout_mode=RolloutMode.PHASED,
        )
        assert cr.scope == ChangeScope.DOMAIN_PACK

        plan = cre.plan_change("plan-dp", "chg-dp", "Domain pack activation", [
            {"step_id": "dp-1", "action": "load-schemas", "target_ref_id": "dp-healthcare-v2"},
            {"step_id": "dp-2", "action": "validate-bindings", "target_ref_id": "dp-healthcare-v2"},
            {"step_id": "dp-3", "action": "activate", "target_ref_id": "dp-healthcare-v2"},
        ])
        assert plan.rollout_mode == RolloutMode.PHASED

        cre.submit_for_approval("chg-dp")
        cre.approve_change("apr-dp", "chg-dp", "platform-admin")

        for sid in ["dp-1", "dp-2", "dp-3"]:
            cre.execute_change_step("chg-dp", sid)

        ex = cre.get_execution("chg-dp")
        assert ex.steps_completed == 3
        assert ex.steps_total == 3

        outcome = cre.complete_change("chg-dp")
        assert outcome.success is True
        assert cre.get_change_status("chg-dp") == ChangeStatus.COMPLETED


class TestGoldenScenario6_FinancialThreshold:
    """Financial threshold adjustment changes later budget gating."""

    def test_financial_change(self):
        cre, es = _engine()
        cr = cre.create_change_request(
            "chg-fin", "Raise daily spend limit",
            ChangeType.BUDGET_THRESHOLD,
            scope=ChangeScope.PORTFOLIO,
            scope_ref_id="portfolio-main",
            priority="high",
            reason="Q4 budget increase",
            requested_by="finance-team",
        )
        assert cr.priority == "high"
        assert cr.scope == ChangeScope.PORTFOLIO

        cre.plan_change("plan-fin", "chg-fin", "Budget update", [
            {"step_id": "fin-1", "action": "update-limit", "target_ref_id": "budget-daily",
             "metadata": {"old_limit": 1000, "new_limit": 2000}},
        ])

        # Collect pre-change evidence
        cre.collect_evidence(
            "chg-fin", ChangeEvidenceKind.METRIC_BEFORE,
            metric_name="daily_spend_limit", metric_value=1000.0,
        )

        cre.submit_for_approval("chg-fin")
        cre.approve_change("apr-fin", "chg-fin", "cfo", reason="Q4 approved")

        step = cre.execute_change_step("chg-fin", "fin-1")
        assert step.status == ChangeStatus.COMPLETED

        # Post-change evidence
        cre.collect_evidence(
            "chg-fin", ChangeEvidenceKind.METRIC_AFTER,
            metric_name="daily_spend_limit", metric_value=2000.0,
        )

        # Impact assessment
        impact = cre.assess_change_impact("chg-fin", "daily_spend_limit", 1000.0, 2000.0)
        assert impact.improvement_pct == pytest.approx(100.0)

        outcome = cre.complete_change("chg-fin", improvement_observed=True, improvement_pct=100.0)
        assert outcome.evidence_count == 2


class TestGoldenScenario7_ReplayPreservesState:
    """Replay/restore preserves change execution state (same inputs -> same state_hash)."""

    def test_deterministic_replay(self):
        def run_scenario(cre: ChangeRuntimeEngine):
            cre.create_change_request(
                "chg-replay", "Replay test",
                ChangeType.CONFIGURATION,
                approval_required=False,
            )
            cre.plan_change("plan-replay", "chg-replay", "Replay plan", [
                {"step_id": "sr1", "action": "do-thing", "target_ref_id": "t1"},
            ])
            cre.execute_change_step("chg-replay", "sr1")
            return cre.state_hash()

        cre1, _ = _engine()
        h1 = run_scenario(cre1)

        cre2, _ = _engine()
        h2 = run_scenario(cre2)

        assert h1 == h2

    def test_same_changes_same_hash(self):
        """Two engines with identical change sets yield same state_hash."""
        def build(cre):
            cre.create_change_request("a", "A", ChangeType.CONFIGURATION)
            cre.create_change_request("b", "B", ChangeType.ROUTING_RULE)

        cre1, _ = _engine()
        build(cre1)

        cre2, _ = _engine()
        build(cre2)

        assert cre1.state_hash() == cre2.state_hash()


class TestGoldenScenario8_OutcomeAssessment:
    """Outcome assessment shows whether the change improved KPIs."""

    def test_kpi_improvement_assessment(self):
        cre, es = _engine()
        cre.create_change_request(
            "chg-kpi", "Improve response time",
            ChangeType.CONFIGURATION,
            scope=ChangeScope.GLOBAL,
            approval_required=False,
        )
        cre.plan_change("plan-kpi", "chg-kpi", "Config tweak", [
            {"step_id": "kpi-1", "action": "apply-config", "target_ref_id": "config-main"},
        ])

        # Before evidence
        cre.collect_evidence(
            "chg-kpi", ChangeEvidenceKind.METRIC_BEFORE,
            metric_name="p99_latency_ms", metric_value=500.0,
        )

        # Execute
        cre.execute_change_step("chg-kpi", "kpi-1")

        # After evidence
        cre.collect_evidence(
            "chg-kpi", ChangeEvidenceKind.METRIC_AFTER,
            metric_name="p99_latency_ms", metric_value=350.0,
        )

        # Impact assessment
        impact = cre.assess_change_impact(
            "chg-kpi", "p99_latency_ms", 500.0, 350.0,
            confidence=0.9,
            assessment_window_seconds=1800.0,
        )
        # (350 - 500) / 500 * 100 = -30%
        assert impact.improvement_pct == pytest.approx(-30.0)
        assert impact.confidence == 0.9

        # Complete with improvement flag
        outcome = cre.complete_change(
            "chg-kpi",
            improvement_observed=True,
            improvement_pct=30.0,  # latency *reduction* is improvement
        )
        assert outcome.improvement_observed is True
        assert outcome.improvement_pct == 30.0
        assert outcome.evidence_count == 2
        assert outcome.success is True

        # Verify full event trail
        all_events = es.list_events()
        actions = [e.payload["action"] for e in all_events]
        assert "change_request_created" in actions
        assert "change_planned" in actions
        assert "change_evidence_collected" in actions
        assert "change_step_executed" in actions
        assert "change_impact_assessed" in actions
        assert "change_completed" in actions

    def test_no_improvement(self):
        cre, _ = _engine()
        cre.create_change_request(
            "chg-noimpr", "No-op change",
            ChangeType.CONFIGURATION,
            approval_required=False,
        )
        cre.plan_change("plan-ni", "chg-noimpr", "Noop", [
            {"step_id": "ni-1", "action": "noop", "target_ref_id": "x"},
        ])
        cre.execute_change_step("chg-noimpr", "ni-1")

        impact = cre.assess_change_impact("chg-noimpr", "metric", 100.0, 100.0)
        assert impact.improvement_pct == pytest.approx(0.0)

        outcome = cre.complete_change("chg-noimpr", improvement_observed=False)
        assert outcome.improvement_observed is False
        assert outcome.improvement_pct == 0.0

    def test_regression_detected(self):
        cre, _ = _engine()
        cre.create_change_request(
            "chg-regr", "Regressive change",
            ChangeType.ESCALATION_TIMING,
            approval_required=False,
        )
        cre.plan_change("plan-regr", "chg-regr", "Timing change", [
            {"step_id": "regr-1", "action": "update-timing", "target_ref_id": "esc-1"},
        ])
        cre.execute_change_step("chg-regr", "regr-1")

        # Regression: error rate went UP
        impact = cre.assess_change_impact("chg-regr", "error_rate", 0.01, 0.05)
        # (0.05 - 0.01) / 0.01 * 100 = 400%
        assert impact.improvement_pct == pytest.approx(400.0)

        # Rollback
        rb = cre.rollback_change("chg-regr", reason="regression in error rate")
        assert rb.disposition == RollbackDisposition.TRIGGERED
        assert cre.get_change_status("chg-regr") == ChangeStatus.ROLLED_BACK


# ===================================================================
# Additional edge-case and coverage tests
# ===================================================================

class TestEdgeCases:
    def test_approve_reject_multiple(self):
        """Multiple approvals on same change (first approves, then rejected is
        recorded but change is already APPROVED -> trying to abort from APPROVED
        via approve_change(approved=False) transitions to ABORTED."""
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        cre.approve_change("a1", "chg-1", "alice")
        assert cre.get_change_status("chg-1") == ChangeStatus.APPROVED
        # Now reject (APPROVED -> ABORTED is valid)
        cre.approve_change("a2", "chg-1", "bob", approved=False)
        assert cre.get_change_status("chg-1") == ChangeStatus.ABORTED
        approvals = cre.get_approvals("chg-1")
        assert len(approvals) == 2

    def test_execution_without_plan_creates_record(self):
        """Executing a step that exists but without a formal plan
        for the change still creates an execution record."""
        cre, _ = _engine()
        _make_change(cre, approval_required=False)
        _two_step_plan(cre)
        cre.execute_change_step("chg-1", "s1")
        ex = cre.get_execution("chg-1")
        assert ex is not None

    def test_complete_from_paused(self):
        """complete_change allows transition from PAUSED directly."""
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.pause_change("chg-1")
        outcome = cre.complete_change("chg-1")
        assert outcome.success is True
        assert cre.get_change_status("chg-1") == ChangeStatus.COMPLETED

    def test_frozen_change_request(self):
        """ChangeRequest is frozen (immutable)."""
        cre, _ = _engine()
        cr = _make_change(cre)
        with pytest.raises(AttributeError):
            cr.title = "mutated"  # type: ignore

    def test_frozen_plan(self):
        cre, _ = _engine()
        _make_change(cre)
        plan = _two_step_plan(cre)
        with pytest.raises(AttributeError):
            plan.title = "mutated"  # type: ignore

    def test_frozen_step(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        _approve(cre)
        step = cre.execute_change_step("chg-1", "s1")
        with pytest.raises(AttributeError):
            step.status = ChangeStatus.DRAFT  # type: ignore

    def test_frozen_approval_binding(self):
        cre, _ = _engine()
        _make_change(cre)
        _approve(cre)
        b = cre.get_approvals("chg-1")[0]
        with pytest.raises(AttributeError):
            b.approved = False  # type: ignore

    def test_frozen_evidence(self):
        cre, _ = _engine()
        _make_change(cre)
        ev = cre.collect_evidence("chg-1", ChangeEvidenceKind.LOG_ENTRY)
        with pytest.raises(AttributeError):
            ev.kind = ChangeEvidenceKind.METRIC_BEFORE  # type: ignore

    def test_frozen_outcome(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        outcome = cre.complete_change("chg-1")
        with pytest.raises(AttributeError):
            outcome.success = False  # type: ignore

    def test_frozen_rollback(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        rb = cre.rollback_change("chg-1")
        with pytest.raises(AttributeError):
            rb.reason = "changed"  # type: ignore

    def test_frozen_impact(self):
        cre, _ = _engine()
        _make_change(cre)
        a = cre.assess_change_impact("chg-1", "m", 10.0, 12.0)
        with pytest.raises(AttributeError):
            a.confidence = 0.5  # type: ignore

    def test_multiple_changes_independent_status(self):
        cre, _ = _engine()
        _make_change(cre, "c1")
        _make_change(cre, "c2")
        cre.submit_for_approval("c1")
        assert cre.get_change_status("c1") == ChangeStatus.PENDING_APPROVAL
        assert cre.get_change_status("c2") == ChangeStatus.DRAFT

    def test_empty_metadata_default(self):
        cre, _ = _engine()
        cr = _make_change(cre)
        assert cr.metadata == {}

    def test_step_action_preserved(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        steps = cre.get_steps("chg-1")
        actions = {s.action for s in steps}
        assert "act-1" in actions
        assert "act-2" in actions

    def test_step_target_ref_preserved(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        steps = cre.get_steps("chg-1")
        refs = {s.target_ref_id for s in steps}
        assert "t1" in refs
        assert "t2" in refs

    def test_step_description_preserved(self):
        cre, _ = _engine()
        _make_change(cre)
        _two_step_plan(cre)
        steps = cre.get_steps("chg-1")
        descs = {s.description for s in steps}
        assert "d1" in descs
        assert "d2" in descs

    def test_approve_pending_approval_to_approved(self):
        """Explicit PENDING_APPROVAL -> APPROVED path."""
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        cre.approve_change("a1", "chg-1", "admin")
        assert cre.get_change_status("chg-1") == ChangeStatus.APPROVED

    def test_abort_from_pending_approval_via_reject(self):
        cre, _ = _engine()
        _make_change(cre)
        cre.submit_for_approval("chg-1")
        cre.approve_change("a1", "chg-1", "admin", approved=False)
        assert cre.get_change_status("chg-1") == ChangeStatus.ABORTED

    def test_is_approved_in_progress(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        assert cre.is_approved("chg-1") is True

    def test_is_approved_completed(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.complete_change("chg-1")
        assert cre.is_approved("chg-1") is True

    def test_is_approved_aborted_false(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.abort_change("chg-1")
        assert cre.is_approved("chg-1") is False

    def test_is_approved_rolled_back_false(self):
        cre, _ = _engine()
        _drive_to_in_progress(cre)
        cre.rollback_change("chg-1")
        assert cre.is_approved("chg-1") is False

    def test_execution_rollout_mode_from_plan(self):
        cre, _ = _engine()
        _make_change(cre, rollout_mode=RolloutMode.CANARY)
        cre.plan_change("p1", "chg-1", "P", [
            {"step_id": "s1", "action": "a", "target_ref_id": "t"},
        ])
        _approve(cre)
        cre.execute_change_step("chg-1", "s1")
        ex = cre.get_execution("chg-1")
        assert ex.rollout_mode == RolloutMode.CANARY

    def test_plan_empty_steps(self):
        cre, _ = _engine()
        _make_change(cre)
        plan = cre.plan_change("p1", "chg-1", "Empty", [])
        assert plan.step_ids == ()

    def test_state_hash_empty_engine(self):
        cre, _ = _engine()
        h = cre.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_event_spine_shared(self):
        """Two engines sharing the same EventSpineEngine accumulate events together."""
        es = EventSpineEngine()
        cre1 = ChangeRuntimeEngine(es)
        cre2 = ChangeRuntimeEngine(es)
        cre1.create_change_request("c1", "T1", ChangeType.CONFIGURATION)
        cre2.create_change_request("c2", "T2", ChangeType.ROUTING_RULE)
        assert es.event_count >= 2
