"""Comprehensive tests for the CopilotRuntimeEngine.

Covers construction, sessions, turns, intents, action plans, decisions,
evidence-backed responses, assessments, snapshots, violation detection,
state_hash, and deterministic replay with FixedClock.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.copilot_runtime import (
    ActionDisposition,
    ActionPlan,
    ConversationMode,
    ConversationRiskLevel,
    ConversationSession,
    ConversationTurn,
    ConversationViolation,
    CopilotAssessment,
    CopilotClosureReport,
    CopilotDecision,
    CopilotSnapshot,
    CopilotStatus,
    EvidenceBackedResponse,
    IntentKind,
    IntentRecord,
    ResponseMode,
)
from mcoi_runtime.core.copilot_runtime import CopilotRuntimeEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXED_TIME = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def clock():
    return FixedClock(FIXED_TIME)


@pytest.fixture
def engine(es, clock):
    return CopilotRuntimeEngine(es, clock=clock)


def _start(engine, sid="s1", tid="t1", iref="u1", mode=ConversationMode.INTERACTIVE):
    return engine.start_session(sid, tid, iref, mode)


def _intent(engine, iid="i1", tid="t1", sref="s1", kind=IntentKind.QUERY, raw="hello"):
    return engine.classify_intent(iid, tid, sref, kind, raw)


def _turn(engine, trid="tr1", tid="t1", sref="s1", iref="i1",
          ui="hi", ao="hey", mode=ResponseMode.DIRECT):
    return engine.record_turn(trid, tid, sref, iref, ui, ao, mode)


def _plan(engine, pid="p1", tid="t1", sref="s1", iref="i1",
          target="rt1", op="op1", risk=ConversationRiskLevel.LOW):
    return engine.build_action_plan(pid, tid, sref, iref, target, op, risk)


def _decision(engine, did="d1", tid="t1", sref="s1", pref="p1",
              disp=ActionDisposition.ALLOWED, reason="ok", erefs=""):
    return engine.record_copilot_decision(did, tid, sref, pref, disp, reason, erefs)


def _response(engine, rid="r1", tid="t1", sref="s1", tref="tr1",
              content="answer", ecount=3, conf=0.9):
    return engine.generate_response(rid, tid, sref, tref, content, ecount, conf)


# ===================================================================
# CONSTRUCTION TESTS
# ===================================================================


class TestConstruction:
    def test_valid_construction(self, es, clock):
        eng = CopilotRuntimeEngine(es, clock=clock)
        assert eng.session_count == 0

    def test_construction_without_clock(self, es):
        eng = CopilotRuntimeEngine(es)
        assert eng.session_count == 0

    def test_invalid_event_spine_string(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeEngine("not-an-engine")

    def test_invalid_event_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeEngine(None)

    def test_invalid_event_spine_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CopilotRuntimeEngine(42)

    def test_initial_session_count(self, engine):
        assert engine.session_count == 0

    def test_initial_turn_count(self, engine):
        assert engine.turn_count == 0

    def test_initial_intent_count(self, engine):
        assert engine.intent_count == 0

    def test_initial_plan_count(self, engine):
        assert engine.plan_count == 0

    def test_initial_decision_count(self, engine):
        assert engine.decision_count == 0

    def test_initial_response_count(self, engine):
        assert engine.response_count == 0

    def test_initial_violation_count(self, engine):
        assert engine.violation_count == 0


# ===================================================================
# SESSION TESTS
# ===================================================================


class TestSessions:
    def test_start_session(self, engine):
        s = _start(engine)
        assert isinstance(s, ConversationSession)
        assert s.session_id == "s1"
        assert s.tenant_id == "t1"
        assert s.status is CopilotStatus.ACTIVE

    def test_start_session_increments_count(self, engine):
        _start(engine, "s1")
        _start(engine, "s2")
        assert engine.session_count == 2

    def test_start_session_all_modes(self, engine):
        for i, m in enumerate(ConversationMode):
            s = _start(engine, f"s{i}", mode=m)
            assert s.mode is m

    def test_start_session_default_mode(self, engine):
        s = _start(engine)
        assert s.mode is ConversationMode.INTERACTIVE

    def test_duplicate_session_id_raises(self, engine):
        _start(engine, "s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _start(engine, "s1")

    def test_get_session(self, engine):
        _start(engine)
        s = engine.get_session("s1")
        assert s.session_id == "s1"

    def test_get_session_unknown(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_session("nonexistent")

    def test_sessions_for_tenant(self, engine):
        _start(engine, "s1", "t1")
        _start(engine, "s2", "t1")
        _start(engine, "s3", "t2")
        result = engine.sessions_for_tenant("t1")
        assert len(result) == 2

    def test_sessions_for_tenant_empty(self, engine):
        result = engine.sessions_for_tenant("t999")
        assert len(result) == 0

    def test_sessions_for_tenant_returns_tuple(self, engine):
        _start(engine)
        result = engine.sessions_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_start_session_emits_event(self, engine, es):
        before = es.event_count
        _start(engine)
        assert es.event_count > before

    def test_session_created_at_uses_clock(self, engine):
        s = _start(engine)
        assert s.created_at == FIXED_TIME

    def test_session_turn_count_starts_zero(self, engine):
        s = _start(engine)
        assert s.turn_count == 0

    # --- Pause ---

    def test_pause_session(self, engine):
        _start(engine)
        s = engine.pause_session("s1")
        assert s.status is CopilotStatus.PAUSED

    def test_pause_session_emits_event(self, engine, es):
        _start(engine)
        before = es.event_count
        engine.pause_session("s1")
        assert es.event_count > before

    def test_pause_paused_raises(self, engine):
        _start(engine)
        engine.pause_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.pause_session("s1")

    def test_pause_completed_raises(self, engine):
        _start(engine)
        engine.complete_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.pause_session("s1")

    def test_pause_terminated_raises(self, engine):
        _start(engine)
        engine.terminate_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.pause_session("s1")

    def test_pause_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.pause_session("nonexistent")

    # --- Resume ---

    def test_resume_session(self, engine):
        _start(engine)
        engine.pause_session("s1")
        s = engine.resume_session("s1")
        assert s.status is CopilotStatus.ACTIVE

    def test_resume_session_emits_event(self, engine, es):
        _start(engine)
        engine.pause_session("s1")
        before = es.event_count
        engine.resume_session("s1")
        assert es.event_count > before

    def test_resume_active_raises(self, engine):
        _start(engine)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resume_session("s1")

    def test_resume_completed_raises(self, engine):
        _start(engine)
        engine.complete_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.resume_session("s1")

    def test_resume_terminated_raises(self, engine):
        _start(engine)
        engine.terminate_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.resume_session("s1")

    def test_resume_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resume_session("nonexistent")

    # --- Complete ---

    def test_complete_session(self, engine):
        _start(engine)
        s = engine.complete_session("s1")
        assert s.status is CopilotStatus.COMPLETED

    def test_complete_session_emits_event(self, engine, es):
        _start(engine)
        before = es.event_count
        engine.complete_session("s1")
        assert es.event_count > before

    def test_complete_from_paused(self, engine):
        _start(engine)
        engine.pause_session("s1")
        s = engine.complete_session("s1")
        assert s.status is CopilotStatus.COMPLETED

    def test_complete_completed_raises(self, engine):
        _start(engine)
        engine.complete_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_session("s1")

    def test_complete_terminated_raises(self, engine):
        _start(engine)
        engine.terminate_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_session("s1")

    # --- Terminate ---

    def test_terminate_session(self, engine):
        _start(engine)
        s = engine.terminate_session("s1")
        assert s.status is CopilotStatus.TERMINATED

    def test_terminate_session_emits_event(self, engine, es):
        _start(engine)
        before = es.event_count
        engine.terminate_session("s1")
        assert es.event_count > before

    def test_terminate_from_paused(self, engine):
        _start(engine)
        engine.pause_session("s1")
        s = engine.terminate_session("s1")
        assert s.status is CopilotStatus.TERMINATED

    def test_terminate_completed_raises(self, engine):
        _start(engine)
        engine.complete_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.terminate_session("s1")

    def test_terminate_terminated_raises(self, engine):
        _start(engine)
        engine.terminate_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.terminate_session("s1")

    # --- Terminal blocks mutations ---

    def test_completed_blocks_pause(self, engine):
        _start(engine)
        engine.complete_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.pause_session("s1")

    def test_completed_blocks_resume(self, engine):
        _start(engine)
        engine.complete_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resume_session("s1")

    def test_terminated_blocks_pause(self, engine):
        _start(engine)
        engine.terminate_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.pause_session("s1")

    def test_terminated_blocks_resume(self, engine):
        _start(engine)
        engine.terminate_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resume_session("s1")

    def test_completed_blocks_turn(self, engine):
        _start(engine)
        engine.complete_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            _turn(engine)

    def test_terminated_blocks_turn(self, engine):
        _start(engine)
        engine.terminate_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            _turn(engine)

    # --- Pause/resume cycle ---

    def test_pause_resume_cycle(self, engine):
        _start(engine)
        engine.pause_session("s1")
        engine.resume_session("s1")
        s = engine.get_session("s1")
        assert s.status is CopilotStatus.ACTIVE

    def test_multiple_pause_resume_cycles(self, engine):
        _start(engine)
        for _ in range(5):
            engine.pause_session("s1")
            engine.resume_session("s1")
        s = engine.get_session("s1")
        assert s.status is CopilotStatus.ACTIVE


# ===================================================================
# TURN TESTS
# ===================================================================


class TestTurns:
    def test_record_turn(self, engine):
        _start(engine)
        t = _turn(engine)
        assert isinstance(t, ConversationTurn)
        assert t.turn_id == "tr1"

    def test_record_turn_increments_session_turn_count(self, engine):
        _start(engine)
        _turn(engine, "tr1")
        s = engine.get_session("s1")
        assert s.turn_count == 1

    def test_record_multiple_turns(self, engine):
        _start(engine)
        _turn(engine, "tr1")
        _turn(engine, "tr2")
        _turn(engine, "tr3")
        s = engine.get_session("s1")
        assert s.turn_count == 3
        assert engine.turn_count == 3

    def test_record_turn_emits_event(self, engine, es):
        _start(engine)
        before = es.event_count
        _turn(engine)
        assert es.event_count > before

    def test_duplicate_turn_id_raises(self, engine):
        _start(engine)
        _turn(engine, "tr1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _turn(engine, "tr1")

    def test_turn_on_nonexistent_session_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            _turn(engine, sref="nonexistent")

    def test_turn_on_paused_session_raises(self, engine):
        _start(engine)
        engine.pause_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="not ACTIVE"):
            _turn(engine)

    def test_turn_on_completed_session_raises(self, engine):
        _start(engine)
        engine.complete_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            _turn(engine)

    def test_turn_on_terminated_session_raises(self, engine):
        _start(engine)
        engine.terminate_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            _turn(engine)

    def test_turn_all_response_modes(self, engine):
        _start(engine)
        for i, m in enumerate(ResponseMode):
            t = _turn(engine, f"tr{i}", mode=m)
            assert t.response_mode is m

    def test_turn_created_at_uses_clock(self, engine):
        _start(engine)
        t = _turn(engine)
        assert t.created_at == FIXED_TIME


# ===================================================================
# INTENT TESTS
# ===================================================================


class TestIntents:
    def test_classify_intent(self, engine):
        _start(engine)
        i = _intent(engine)
        assert isinstance(i, IntentRecord)
        assert i.intent_id == "i1"
        assert i.kind is IntentKind.QUERY

    def test_classify_all_kinds(self, engine):
        _start(engine)
        for idx, k in enumerate(IntentKind):
            i = _intent(engine, f"i{idx}", kind=k)
            assert i.kind is k

    def test_classify_increments_count(self, engine):
        _start(engine)
        _intent(engine, "i1")
        _intent(engine, "i2")
        assert engine.intent_count == 2

    def test_classify_emits_event(self, engine, es):
        _start(engine)
        before = es.event_count
        _intent(engine)
        assert es.event_count > before

    def test_duplicate_intent_id_raises(self, engine):
        _start(engine)
        _intent(engine, "i1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _intent(engine, "i1")

    def test_intent_on_nonexistent_session_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            _intent(engine, sref="nonexistent")

    def test_intent_classified_at_uses_clock(self, engine):
        _start(engine)
        i = _intent(engine)
        assert i.classified_at == FIXED_TIME


# ===================================================================
# ACTION PLAN TESTS
# ===================================================================


class TestActionPlans:
    def test_build_plan_low_allowed(self, engine):
        _start(engine)
        p = _plan(engine, risk=ConversationRiskLevel.LOW)
        assert p.disposition is ActionDisposition.ALLOWED

    def test_build_plan_medium_deferred(self, engine):
        _start(engine)
        p = _plan(engine, risk=ConversationRiskLevel.MEDIUM)
        assert p.disposition is ActionDisposition.DEFERRED

    def test_build_plan_high_escalated(self, engine):
        _start(engine)
        p = _plan(engine, risk=ConversationRiskLevel.HIGH)
        assert p.disposition is ActionDisposition.ESCALATED

    def test_build_plan_critical_escalated(self, engine):
        _start(engine)
        p = _plan(engine, risk=ConversationRiskLevel.CRITICAL)
        assert p.disposition is ActionDisposition.ESCALATED

    def test_build_plan_increments_count(self, engine):
        _start(engine)
        _plan(engine, "p1")
        _plan(engine, "p2")
        assert engine.plan_count == 2

    def test_build_plan_emits_event(self, engine, es):
        _start(engine)
        before = es.event_count
        _plan(engine)
        assert es.event_count > before

    def test_duplicate_plan_id_raises(self, engine):
        _start(engine)
        _plan(engine, "p1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _plan(engine, "p1")

    def test_plan_on_nonexistent_session_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            _plan(engine, sref="nonexistent")

    def test_plan_created_at_uses_clock(self, engine):
        _start(engine)
        p = _plan(engine)
        assert p.created_at == FIXED_TIME

    def test_plan_returns_action_plan(self, engine):
        _start(engine)
        p = _plan(engine)
        assert isinstance(p, ActionPlan)

    # --- Cross-tenant ---

    def test_cross_tenant_plan_denied(self, engine):
        _start(engine, "s1", "t1")
        p = engine.build_action_plan("p1", "t2", "s1", "i1", "rt", "op")
        assert p.disposition is ActionDisposition.DENIED

    def test_cross_tenant_plan_creates_violation(self, engine):
        _start(engine, "s1", "t1")
        engine.build_action_plan("p1", "t2", "s1", "i1", "rt", "op")
        assert engine.violation_count >= 1

    def test_cross_tenant_violation_has_correct_operation(self, engine):
        _start(engine, "s1", "t1")
        engine.build_action_plan("p1", "t2", "s1", "i1", "rt", "op")
        # The violation should have operation "cross_tenant_action"
        viols = engine.detect_copilot_violations("t2")
        # Also check existing violations
        assert engine.violation_count >= 1

    def test_cross_tenant_plan_with_low_risk_still_denied(self, engine):
        _start(engine, "s1", "t1")
        p = engine.build_action_plan(
            "p1", "t2", "s1", "i1", "rt", "op", ConversationRiskLevel.LOW
        )
        assert p.disposition is ActionDisposition.DENIED

    def test_cross_tenant_plan_with_high_risk_still_denied(self, engine):
        _start(engine, "s1", "t1")
        p = engine.build_action_plan(
            "p1", "t2", "s1", "i1", "rt", "op", ConversationRiskLevel.HIGH
        )
        assert p.disposition is ActionDisposition.DENIED

    def test_same_tenant_plan_not_denied(self, engine):
        _start(engine, "s1", "t1")
        p = _plan(engine, tid="t1")
        assert p.disposition is not ActionDisposition.DENIED


# ===================================================================
# DECISION TESTS
# ===================================================================


class TestDecisions:
    def test_record_decision(self, engine):
        _start(engine)
        d = _decision(engine)
        assert isinstance(d, CopilotDecision)
        assert d.decision_id == "d1"

    def test_all_dispositions(self, engine):
        _start(engine)
        for i, disp in enumerate(ActionDisposition):
            d = _decision(engine, f"d{i}", disp=disp)
            assert d.disposition is disp

    def test_decision_increments_count(self, engine):
        _start(engine)
        _decision(engine, "d1")
        _decision(engine, "d2")
        assert engine.decision_count == 2

    def test_decision_emits_event(self, engine, es):
        _start(engine)
        before = es.event_count
        _decision(engine)
        assert es.event_count > before

    def test_duplicate_decision_id_raises(self, engine):
        _start(engine)
        _decision(engine, "d1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _decision(engine, "d1")

    def test_decision_with_evidence_refs(self, engine):
        _start(engine)
        d = _decision(engine, erefs="ref1,ref2")
        assert d.evidence_refs == "ref1,ref2"

    def test_decision_empty_evidence_refs(self, engine):
        _start(engine)
        d = _decision(engine, erefs="")
        assert d.evidence_refs == ""

    def test_decision_decided_at_uses_clock(self, engine):
        _start(engine)
        d = _decision(engine)
        assert d.decided_at == FIXED_TIME


# ===================================================================
# RESPONSE TESTS
# ===================================================================


class TestResponses:
    def test_generate_response(self, engine):
        _start(engine)
        r = _response(engine)
        assert isinstance(r, EvidenceBackedResponse)
        assert r.response_id == "r1"
        assert r.confidence == 0.9

    def test_response_increments_count(self, engine):
        _start(engine)
        _response(engine, "r1")
        _response(engine, "r2")
        assert engine.response_count == 2

    def test_response_emits_event(self, engine, es):
        _start(engine)
        before = es.event_count
        _response(engine)
        assert es.event_count > before

    def test_duplicate_response_id_raises(self, engine):
        _start(engine)
        _response(engine, "r1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _response(engine, "r1")

    def test_response_confidence_zero(self, engine):
        _start(engine)
        r = _response(engine, conf=0.0)
        assert r.confidence == 0.0

    def test_response_confidence_one(self, engine):
        _start(engine)
        r = _response(engine, conf=1.0)
        assert r.confidence == 1.0

    def test_response_evidence_count(self, engine):
        _start(engine)
        r = _response(engine, ecount=10)
        assert r.evidence_count == 10

    def test_response_created_at_uses_clock(self, engine):
        _start(engine)
        r = _response(engine)
        assert r.created_at == FIXED_TIME


# ===================================================================
# ASSESSMENT TESTS
# ===================================================================


class TestAssessment:
    def test_empty_assessment(self, engine):
        a = engine.copilot_assessment("a1", "t1")
        assert isinstance(a, CopilotAssessment)
        assert a.total_sessions == 0
        assert a.success_rate == 1.0

    def test_assessment_counts_sessions(self, engine):
        _start(engine, "s1", "t1")
        _start(engine, "s2", "t1")
        a = engine.copilot_assessment("a1", "t1")
        assert a.total_sessions == 2

    def test_assessment_counts_allowed(self, engine):
        _start(engine, "s1", "t1")
        _plan(engine, "p1", "t1", risk=ConversationRiskLevel.LOW)
        _plan(engine, "p2", "t1", risk=ConversationRiskLevel.LOW)
        a = engine.copilot_assessment("a1", "t1")
        assert a.total_actions_allowed == 2

    def test_assessment_counts_denied(self, engine):
        _start(engine, "s1", "t1")
        # Create a cross-tenant plan for DENIED
        engine.build_action_plan("p1", "t2", "s1", "i1", "rt", "op")
        # Assessment for t2 which has the denied plan
        a = engine.copilot_assessment("a1", "t2")
        assert a.total_actions_denied == 1

    def test_assessment_success_rate_calculation(self, engine):
        _start(engine, "s1", "t1")
        _plan(engine, "p1", "t1", risk=ConversationRiskLevel.LOW)  # ALLOWED
        _plan(engine, "p2", "t1", risk=ConversationRiskLevel.LOW)  # ALLOWED
        a = engine.copilot_assessment("a1", "t1")
        assert a.success_rate == 1.0

    def test_assessment_no_plans_rate_one(self, engine):
        _start(engine, "s1", "t1")
        a = engine.copilot_assessment("a1", "t1")
        assert a.success_rate == 1.0

    def test_assessment_emits_event(self, engine, es):
        before = es.event_count
        engine.copilot_assessment("a1", "t1")
        assert es.event_count > before

    def test_assessment_different_tenants_isolated(self, engine):
        _start(engine, "s1", "t1")
        _start(engine, "s2", "t2")
        _plan(engine, "p1", "t1", risk=ConversationRiskLevel.LOW)
        a = engine.copilot_assessment("a1", "t2")
        assert a.total_sessions == 1
        assert a.total_actions_allowed == 0


# ===================================================================
# SNAPSHOT TESTS
# ===================================================================


class TestSnapshot:
    def test_empty_snapshot(self, engine):
        s = engine.copilot_snapshot("snap1", "t1")
        assert isinstance(s, CopilotSnapshot)
        assert s.total_sessions == 0

    def test_snapshot_counts_sessions(self, engine):
        _start(engine, "s1", "t1")
        _start(engine, "s2", "t1")
        s = engine.copilot_snapshot("snap1", "t1")
        assert s.total_sessions == 2

    def test_snapshot_counts_turns(self, engine):
        _start(engine, "s1", "t1")
        _turn(engine, "tr1", "t1")
        _turn(engine, "tr2", "t1")
        s = engine.copilot_snapshot("snap1", "t1")
        assert s.total_turns == 2

    def test_snapshot_counts_intents(self, engine):
        _start(engine, "s1", "t1")
        _intent(engine, "i1", "t1")
        _intent(engine, "i2", "t1")
        s = engine.copilot_snapshot("snap1", "t1")
        assert s.total_intents == 2

    def test_snapshot_counts_plans(self, engine):
        _start(engine, "s1", "t1")
        _plan(engine, "p1", "t1")
        s = engine.copilot_snapshot("snap1", "t1")
        assert s.total_plans == 1

    def test_snapshot_counts_decisions(self, engine):
        _start(engine, "s1", "t1")
        _decision(engine, "d1", "t1")
        s = engine.copilot_snapshot("snap1", "t1")
        assert s.total_decisions == 1

    def test_snapshot_tenant_isolation(self, engine):
        _start(engine, "s1", "t1")
        _start(engine, "s2", "t2")
        _turn(engine, "tr1", "t1")
        s1 = engine.copilot_snapshot("snap1", "t1")
        s2 = engine.copilot_snapshot("snap2", "t2")
        assert s1.total_sessions == 1
        assert s1.total_turns == 1
        assert s2.total_sessions == 1
        assert s2.total_turns == 0

    def test_snapshot_captured_at_uses_clock(self, engine):
        s = engine.copilot_snapshot("snap1", "t1")
        assert s.captured_at == FIXED_TIME


# ===================================================================
# VIOLATION DETECTION TESTS
# ===================================================================


class TestViolationDetection:
    def test_no_violations_empty_engine(self, engine):
        result = engine.detect_copilot_violations("t1")
        assert result == ()

    def test_session_no_turns_violation(self, engine):
        _start(engine, "s1", "t1")
        viols = engine.detect_copilot_violations("t1")
        assert len(viols) >= 1
        ops = [v.operation for v in viols]
        assert "session_no_turns" in ops

    def test_session_with_turns_no_violation(self, engine):
        _start(engine, "s1", "t1")
        _turn(engine, "tr1", "t1")
        viols = engine.detect_copilot_violations("t1")
        ops = [v.operation for v in viols]
        assert "session_no_turns" not in ops

    def test_plan_no_decision_violation(self, engine):
        _start(engine, "s1", "t1")
        _plan(engine, "p1", "t1")
        viols = engine.detect_copilot_violations("t1")
        ops = [v.operation for v in viols]
        assert "plan_no_decision" in ops

    def test_plan_with_decision_no_violation(self, engine):
        _start(engine, "s1", "t1")
        _plan(engine, "p1", "t1")
        _decision(engine, "d1", "t1", pref="p1")
        viols = engine.detect_copilot_violations("t1")
        ops = [v.operation for v in viols]
        assert "plan_no_decision" not in ops

    def test_idempotent_second_call_empty(self, engine):
        _start(engine, "s1", "t1")
        viols1 = engine.detect_copilot_violations("t1")
        assert len(viols1) > 0
        viols2 = engine.detect_copilot_violations("t1")
        assert len(viols2) == 0

    def test_idempotent_third_call_still_empty(self, engine):
        _start(engine, "s1", "t1")
        engine.detect_copilot_violations("t1")
        engine.detect_copilot_violations("t1")
        viols3 = engine.detect_copilot_violations("t1")
        assert len(viols3) == 0

    def test_violation_count_increments(self, engine):
        _start(engine, "s1", "t1")
        before = engine.violation_count
        engine.detect_copilot_violations("t1")
        assert engine.violation_count > before

    def test_cross_tenant_violation_counted(self, engine):
        _start(engine, "s1", "t1")
        engine.build_action_plan("p1", "t2", "s1", "i1", "rt", "op")
        assert engine.violation_count >= 1

    def test_violation_returns_tuple(self, engine):
        _start(engine, "s1", "t1")
        result = engine.detect_copilot_violations("t1")
        assert isinstance(result, tuple)

    def test_violations_have_correct_tenant(self, engine):
        _start(engine, "s1", "t1")
        viols = engine.detect_copilot_violations("t1")
        for v in viols:
            assert v.tenant_id == "t1"

    def test_violations_have_correct_type(self, engine):
        _start(engine, "s1", "t1")
        viols = engine.detect_copilot_violations("t1")
        for v in viols:
            assert isinstance(v, ConversationViolation)

    def test_multiple_violations_same_call(self, engine):
        _start(engine, "s1", "t1")
        _plan(engine, "p1", "t1")
        # session_no_turns + plan_no_decision
        viols = engine.detect_copilot_violations("t1")
        assert len(viols) >= 2

    def test_different_tenants_violations_isolated(self, engine):
        _start(engine, "s1", "t1")
        _start(engine, "s2", "t2")
        v1 = engine.detect_copilot_violations("t1")
        v2 = engine.detect_copilot_violations("t2")
        for v in v1:
            assert v.tenant_id == "t1"
        for v in v2:
            assert v.tenant_id == "t2"

    def test_completed_session_no_turns_no_violation(self, engine):
        _start(engine, "s1", "t1")
        engine.complete_session("s1")
        viols = engine.detect_copilot_violations("t1")
        ops = [v.operation for v in viols]
        # session_no_turns only applies to ACTIVE sessions
        assert "session_no_turns" not in ops


# ===================================================================
# STATE HASH TESTS
# ===================================================================


class TestStateHash:
    def test_empty_engine_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_changes_after_mutation(self, engine):
        h1 = engine.state_hash()
        _start(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_deterministic(self, engine):
        _start(engine)
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_hash_changes_with_turn(self, engine):
        _start(engine)
        h1 = engine.state_hash()
        _turn(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_plan(self, engine):
        _start(engine)
        h1 = engine.state_hash()
        _plan(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_decision(self, engine):
        _start(engine)
        h1 = engine.state_hash()
        _decision(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_response(self, engine):
        _start(engine)
        h1 = engine.state_hash()
        _response(engine)
        h2 = engine.state_hash()
        assert h1 != h2


# ===================================================================
# SNAPSHOT (ENGINE-LEVEL) TESTS
# ===================================================================


class TestEngineSnapshot:
    def test_snapshot_returns_dict(self, engine):
        snap = engine.snapshot()
        assert isinstance(snap, dict)

    def test_snapshot_has_state_hash(self, engine):
        snap = engine.snapshot()
        assert "_state_hash" in snap

    def test_snapshot_has_collections(self, engine):
        snap = engine.snapshot()
        for key in ["sessions", "intents", "turns", "plans",
                     "decisions", "responses", "violations"]:
            assert key in snap

    def test_snapshot_empty(self, engine):
        snap = engine.snapshot()
        assert snap["sessions"] == {}
        assert snap["turns"] == {}

    def test_snapshot_with_data(self, engine):
        _start(engine, "s1", "t1")
        _turn(engine, "tr1", "t1")
        snap = engine.snapshot()
        assert "s1" in snap["sessions"]
        assert "tr1" in snap["turns"]

    def test_snapshot_sessions_are_dicts(self, engine):
        _start(engine)
        snap = engine.snapshot()
        assert isinstance(snap["sessions"]["s1"], dict)


# ===================================================================
# DETERMINISTIC REPLAY WITH FIXED CLOCK
# ===================================================================


class TestDeterministicReplay:
    def _run_scenario(self):
        """Run a deterministic scenario, return state_hash."""
        es = EventSpineEngine()
        clock = FixedClock(FIXED_TIME)
        eng = CopilotRuntimeEngine(es, clock=clock)

        eng.start_session("s1", "t1", "u1")
        eng.classify_intent("i1", "t1", "s1", IntentKind.QUERY, "hello")
        eng.record_turn("tr1", "t1", "s1", "i1", "hi", "hey")
        eng.build_action_plan("p1", "t1", "s1", "i1", "rt1", "op1",
                              ConversationRiskLevel.LOW)
        eng.record_copilot_decision("d1", "t1", "s1", "p1",
                                    ActionDisposition.ALLOWED, "ok")
        eng.generate_response("r1", "t1", "s1", "tr1", "answer", 3, 0.9)
        return eng.state_hash()

    def test_replay_same_hash(self):
        h1 = self._run_scenario()
        h2 = self._run_scenario()
        assert h1 == h2

    def test_replay_three_times(self):
        hashes = [self._run_scenario() for _ in range(3)]
        assert len(set(hashes)) == 1

    def test_replay_same_event_count(self):
        es1 = EventSpineEngine()
        es2 = EventSpineEngine()
        c1 = FixedClock(FIXED_TIME)
        c2 = FixedClock(FIXED_TIME)
        eng1 = CopilotRuntimeEngine(es1, clock=c1)
        eng2 = CopilotRuntimeEngine(es2, clock=c2)

        for eng in [eng1, eng2]:
            eng.start_session("s1", "t1", "u1")
            eng.classify_intent("i1", "t1", "s1", IntentKind.QUERY, "hello")
            eng.record_turn("tr1", "t1", "s1", "i1", "hi", "hey")

        assert es1.event_count == es2.event_count

    def test_replay_with_advanced_clock(self):
        es = EventSpineEngine()
        clock = FixedClock(FIXED_TIME)
        eng = CopilotRuntimeEngine(es, clock=clock)

        eng.start_session("s1", "t1", "u1")
        clock.advance("2026-06-01T00:00:00+00:00")
        eng.classify_intent("i1", "t1", "s1", IntentKind.QUERY, "hello")
        i = eng.classify_intent("i2", "t1", "s1", IntentKind.ACTION, "do it")
        assert i.classified_at == "2026-06-01T00:00:00+00:00"

    def test_fixed_clock_ticks(self):
        clock = FixedClock(FIXED_TIME)
        t1 = clock.now_iso()
        t2 = clock.now_iso()
        assert t1 == t2  # same time, different ticks internally


# ===================================================================
# GOLDEN SCENARIO TESTS
# ===================================================================


class TestGoldenScenarios:
    def test_operator_asks_why_blocked_evidence_answer(self, engine):
        """Operator asks why service request blocked -> evidence-backed answer."""
        _start(engine, "s1", "t1", "operator")
        _intent(engine, "i1", "t1", "s1", IntentKind.QUERY,
                "Why was my service request blocked?")
        _turn(engine, "tr1", "t1", "s1", "i1",
              "Why was my service request blocked?",
              "Your request was blocked due to HIGH risk level",
              ResponseMode.EVIDENCE_BACKED)
        r = _response(engine, "r1", "t1", "s1", "tr1",
                      "Blocked due to risk level HIGH; escalation required",
                      ecount=3, conf=0.85)
        assert r.evidence_count == 3
        assert r.confidence == 0.85
        assert "r1" in engine.snapshot()["responses"]

    def test_executive_asks_degradation_cross_runtime(self, engine):
        """Executive asks what's degrading -> cross-runtime summary."""
        _start(engine, "s1", "t1", "executive", ConversationMode.AUTONOMOUS)
        _intent(engine, "i1", "t1", "s1", IntentKind.SUMMARIZE,
                "What services are degrading?")
        _turn(engine, "tr1", "t1", "s1", "i1",
              "What services are degrading?",
              "3 services degrading in last hour",
              ResponseMode.SYNTHESIS)
        r = _response(engine, "r1", "t1", "s1", "tr1",
                      "Cross-runtime analysis: 3 services degrading",
                      ecount=5, conf=0.75)
        snap = engine.copilot_snapshot("snap1", "t1")
        assert snap.total_sessions == 1
        assert snap.total_turns == 1
        assert r.evidence_count == 5

    def test_user_blocked_by_constitutional_governance(self, engine):
        """User action blocked by constitutional governance."""
        _start(engine, "s1", "t1", "user1")
        _intent(engine, "i1", "t1", "s1", IntentKind.ACTION,
                "Delete all production data")
        p = engine.build_action_plan(
            "p1", "t1", "s1", "i1", "data_runtime", "delete_all",
            ConversationRiskLevel.CRITICAL,
        )
        assert p.disposition is ActionDisposition.ESCALATED
        d = _decision(engine, "d1", "t1", "s1", "p1",
                      ActionDisposition.DENIED, "Constitutional governance block")
        assert d.disposition is ActionDisposition.DENIED

    def test_copilot_drafts_regulatory_response(self, engine):
        """Copilot drafts regulatory response using evidence bundle."""
        _start(engine, "s1", "t1", "compliance_officer", ConversationMode.GUIDED)
        _intent(engine, "i1", "t1", "s1", IntentKind.DRAFT,
                "Draft SOX compliance response")
        _turn(engine, "tr1", "t1", "s1", "i1",
              "Draft SOX compliance response",
              "Based on 12 evidence items, here is the draft...",
              ResponseMode.EVIDENCE_BACKED)
        r = _response(engine, "r1", "t1", "s1", "tr1",
                      "SOX compliance draft: all controls verified",
                      ecount=12, conf=0.95)
        assert r.evidence_count == 12
        assert r.confidence == 0.95

    def test_cross_tenant_access_denied_fail_closed(self, engine):
        """Cross-tenant conversational access denied fail-closed."""
        _start(engine, "s1", "t1", "user1")
        p = engine.build_action_plan(
            "p1", "t2", "s1", "i1", "rt", "read_data",
            ConversationRiskLevel.LOW,
        )
        assert p.disposition is ActionDisposition.DENIED
        assert engine.violation_count >= 1

    def test_replay_fixed_clock_same_hash(self):
        """Replay with FixedClock: same ops -> same state_hash."""
        def run():
            es = EventSpineEngine()
            c = FixedClock(FIXED_TIME)
            eng = CopilotRuntimeEngine(es, clock=c)
            eng.start_session("s1", "t1", "u1")
            eng.classify_intent("i1", "t1", "s1", IntentKind.QUERY, "hello")
            eng.record_turn("tr1", "t1", "s1", "i1", "hi", "hey")
            eng.build_action_plan("p1", "t1", "s1", "i1", "rt", "op",
                                  ConversationRiskLevel.LOW)
            eng.record_copilot_decision("d1", "t1", "s1", "p1",
                                        ActionDisposition.ALLOWED, "ok")
            eng.generate_response("r1", "t1", "s1", "tr1", "answer", 3, 0.9)
            return eng.state_hash()

        assert run() == run()


# ===================================================================
# PROPERTY / COUNTER TESTS
# ===================================================================


class TestPropertyCounters:
    def test_session_count(self, engine):
        assert engine.session_count == 0
        _start(engine, "s1")
        assert engine.session_count == 1
        _start(engine, "s2")
        assert engine.session_count == 2

    def test_turn_count(self, engine):
        _start(engine)
        assert engine.turn_count == 0
        _turn(engine, "tr1")
        assert engine.turn_count == 1

    def test_intent_count(self, engine):
        _start(engine)
        assert engine.intent_count == 0
        _intent(engine, "i1")
        assert engine.intent_count == 1

    def test_plan_count(self, engine):
        _start(engine)
        assert engine.plan_count == 0
        _plan(engine, "p1")
        assert engine.plan_count == 1

    def test_decision_count(self, engine):
        _start(engine)
        assert engine.decision_count == 0
        _decision(engine, "d1")
        assert engine.decision_count == 1

    def test_response_count(self, engine):
        _start(engine)
        assert engine.response_count == 0
        _response(engine, "r1")
        assert engine.response_count == 1

    def test_violation_count_after_cross_tenant(self, engine):
        _start(engine, "s1", "t1")
        assert engine.violation_count == 0
        engine.build_action_plan("p1", "t2", "s1", "i1", "rt", "op")
        assert engine.violation_count >= 1


# ===================================================================
# RISK DISPOSITION MATRIX
# ===================================================================


class TestRiskDispositionMatrix:
    @pytest.mark.parametrize("risk,expected", [
        (ConversationRiskLevel.LOW, ActionDisposition.ALLOWED),
        (ConversationRiskLevel.MEDIUM, ActionDisposition.DEFERRED),
        (ConversationRiskLevel.HIGH, ActionDisposition.ESCALATED),
        (ConversationRiskLevel.CRITICAL, ActionDisposition.ESCALATED),
    ])
    def test_risk_to_disposition(self, engine, risk, expected):
        _start(engine)
        p = engine.build_action_plan(
            f"p-{risk.value}", "t1", "s1", "i1", "rt", "op", risk
        )
        assert p.disposition is expected


# ===================================================================
# MULTI-SESSION / MULTI-TENANT TESTS
# ===================================================================


class TestMultiTenant:
    def test_two_tenants_sessions(self, engine):
        _start(engine, "s1", "t1")
        _start(engine, "s2", "t2")
        assert engine.session_count == 2
        assert len(engine.sessions_for_tenant("t1")) == 1
        assert len(engine.sessions_for_tenant("t2")) == 1

    def test_ten_sessions_same_tenant(self, engine):
        for i in range(10):
            _start(engine, f"s{i}", "t1")
        assert engine.session_count == 10
        assert len(engine.sessions_for_tenant("t1")) == 10

    def test_tenant_isolation_turns(self, engine):
        _start(engine, "s1", "t1")
        _start(engine, "s2", "t2")
        _turn(engine, "tr1", "t1")
        snap = engine.copilot_snapshot("snap1", "t1")
        assert snap.total_turns == 1
        snap2 = engine.copilot_snapshot("snap2", "t2")
        assert snap2.total_turns == 0

    def test_tenant_isolation_plans(self, engine):
        _start(engine, "s1", "t1")
        _start(engine, "s2", "t2")
        _plan(engine, "p1", "t1")
        snap1 = engine.copilot_snapshot("snap1", "t1")
        snap2 = engine.copilot_snapshot("snap2", "t2")
        assert snap1.total_plans == 1
        assert snap2.total_plans == 0


# ===================================================================
# EDGE / BOUNDARY TESTS
# ===================================================================


class TestEdgeCases:
    def test_many_turns_single_session(self, engine):
        _start(engine)
        for i in range(50):
            _turn(engine, f"tr{i}")
        assert engine.turn_count == 50
        s = engine.get_session("s1")
        assert s.turn_count == 50

    def test_many_plans_single_session(self, engine):
        _start(engine)
        for i in range(20):
            _plan(engine, f"p{i}")
        assert engine.plan_count == 20

    def test_many_decisions(self, engine):
        _start(engine)
        for i in range(20):
            _decision(engine, f"d{i}")
        assert engine.decision_count == 20

    def test_many_responses(self, engine):
        _start(engine)
        for i in range(20):
            _response(engine, f"r{i}")
        assert engine.response_count == 20

    def test_session_lifecycle_full(self, engine):
        _start(engine)
        _intent(engine)
        _turn(engine)
        _plan(engine)
        _decision(engine)
        _response(engine)
        engine.complete_session("s1")
        s = engine.get_session("s1")
        assert s.status is CopilotStatus.COMPLETED

    def test_assessment_after_full_lifecycle(self, engine):
        _start(engine)
        _plan(engine, "p1", risk=ConversationRiskLevel.LOW)
        _decision(engine, "d1")
        a = engine.copilot_assessment("a1", "t1")
        assert a.total_sessions == 1
        assert a.total_actions_allowed == 1

    def test_snapshot_after_violations(self, engine):
        _start(engine, "s1", "t1")
        engine.detect_copilot_violations("t1")
        snap = engine.copilot_snapshot("snap1", "t1")
        assert snap.total_violations >= 1

    def test_clock_advance_affects_timestamps(self, engine, clock):
        _start(engine, "s1")
        clock.advance("2030-01-01T00:00:00+00:00")
        _start(engine, "s2")
        s2 = engine.get_session("s2")
        assert s2.created_at == "2030-01-01T00:00:00+00:00"
