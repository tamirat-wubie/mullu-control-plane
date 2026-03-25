"""Comprehensive tests for copilot runtime contracts.

Covers all enums, all dataclasses (ConversationSession, IntentRecord,
ConversationTurn, ActionPlan, CopilotDecision, EvidenceBackedResponse,
ConversationViolation, CopilotSnapshot, CopilotAssessment,
CopilotClosureReport), frozen guarantees, validation, to_dict semantics,
to_json_dict semantics, edge-case inputs, and metadata handling.
"""

from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T00:00:00+00:00"
TS2 = "2025-07-01T12:30:00+00:00"


def _session(**kw):
    defaults = dict(
        session_id="s1", tenant_id="t1", identity_ref="u1",
        mode=ConversationMode.INTERACTIVE, status=CopilotStatus.ACTIVE,
        turn_count=0, created_at=TS,
    )
    defaults.update(kw)
    return ConversationSession(**defaults)


def _intent(**kw):
    defaults = dict(
        intent_id="i1", tenant_id="t1", session_ref="s1",
        kind=IntentKind.QUERY, raw_input="hello",
        classified_at=TS,
    )
    defaults.update(kw)
    return IntentRecord(**defaults)


def _turn(**kw):
    defaults = dict(
        turn_id="tr1", tenant_id="t1", session_ref="s1",
        intent_ref="i1", user_input="hi", assistant_output="hey",
        response_mode=ResponseMode.DIRECT, created_at=TS,
    )
    defaults.update(kw)
    return ConversationTurn(**defaults)


def _plan(**kw):
    defaults = dict(
        plan_id="p1", tenant_id="t1", session_ref="s1",
        intent_ref="i1", target_runtime="rt1", operation="op1",
        risk_level=ConversationRiskLevel.LOW,
        disposition=ActionDisposition.ALLOWED, created_at=TS,
    )
    defaults.update(kw)
    return ActionPlan(**defaults)


def _decision(**kw):
    defaults = dict(
        decision_id="d1", tenant_id="t1", session_ref="s1",
        plan_ref="p1", disposition=ActionDisposition.ALLOWED,
        reason="ok", evidence_refs="", decided_at=TS,
    )
    defaults.update(kw)
    return CopilotDecision(**defaults)


def _evidence(**kw):
    defaults = dict(
        response_id="r1", tenant_id="t1", session_ref="s1",
        turn_ref="tr1", content="answer", evidence_count=3,
        confidence=0.9, created_at=TS,
    )
    defaults.update(kw)
    return EvidenceBackedResponse(**defaults)


def _violation(**kw):
    defaults = dict(
        violation_id="v1", tenant_id="t1", operation="cross_tenant",
        reason="bad", detected_at=TS,
    )
    defaults.update(kw)
    return ConversationViolation(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap1", tenant_id="t1",
        total_sessions=1, total_turns=2, total_intents=1,
        total_plans=1, total_decisions=1, total_violations=0,
        captured_at=TS,
    )
    defaults.update(kw)
    return CopilotSnapshot(**defaults)


def _assessment(**kw):
    defaults = dict(
        assessment_id="a1", tenant_id="t1",
        total_sessions=1, total_actions_allowed=5,
        total_actions_denied=0, success_rate=1.0,
        assessed_at=TS,
    )
    defaults.update(kw)
    return CopilotAssessment(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="cr1", tenant_id="t1",
        total_sessions=2, total_turns=10, total_plans=3,
        total_decisions=3, total_violations=0, created_at=TS,
    )
    defaults.update(kw)
    return CopilotClosureReport(**defaults)


# ===================================================================
# ENUM TESTS
# ===================================================================


class TestConversationMode:
    def test_interactive_value(self):
        assert ConversationMode.INTERACTIVE.value == "interactive"

    def test_guided_value(self):
        assert ConversationMode.GUIDED.value == "guided"

    def test_autonomous_value(self):
        assert ConversationMode.AUTONOMOUS.value == "autonomous"

    def test_read_only_value(self):
        assert ConversationMode.READ_ONLY.value == "read_only"

    def test_member_count(self):
        assert len(ConversationMode) == 4

    def test_from_value_interactive(self):
        assert ConversationMode("interactive") is ConversationMode.INTERACTIVE

    def test_from_value_guided(self):
        assert ConversationMode("guided") is ConversationMode.GUIDED

    def test_from_value_autonomous(self):
        assert ConversationMode("autonomous") is ConversationMode.AUTONOMOUS

    def test_from_value_read_only(self):
        assert ConversationMode("read_only") is ConversationMode.READ_ONLY

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ConversationMode("invalid")

    def test_identity(self):
        assert ConversationMode.INTERACTIVE is ConversationMode.INTERACTIVE

    def test_not_equal_to_string(self):
        assert ConversationMode.INTERACTIVE != "interactive"

    def test_name_interactive(self):
        assert ConversationMode.INTERACTIVE.name == "INTERACTIVE"

    def test_name_read_only(self):
        assert ConversationMode.READ_ONLY.name == "READ_ONLY"


class TestIntentKind:
    def test_query_value(self):
        assert IntentKind.QUERY.value == "query"

    def test_explain_value(self):
        assert IntentKind.EXPLAIN.value == "explain"

    def test_summarize_value(self):
        assert IntentKind.SUMMARIZE.value == "summarize"

    def test_action_value(self):
        assert IntentKind.ACTION.value == "action"

    def test_draft_value(self):
        assert IntentKind.DRAFT.value == "draft"

    def test_escalate_value(self):
        assert IntentKind.ESCALATE.value == "escalate"

    def test_member_count(self):
        assert len(IntentKind) == 6

    def test_from_value_action(self):
        assert IntentKind("action") is IntentKind.ACTION

    def test_from_value_draft(self):
        assert IntentKind("draft") is IntentKind.DRAFT

    def test_invalid(self):
        with pytest.raises(ValueError):
            IntentKind("nope")

    def test_identity_roundtrip(self):
        for ik in IntentKind:
            assert IntentKind(ik.value) is ik

    def test_not_equal_to_string(self):
        assert IntentKind.QUERY != "query"


class TestCopilotStatus:
    def test_active_value(self):
        assert CopilotStatus.ACTIVE.value == "active"

    def test_paused_value(self):
        assert CopilotStatus.PAUSED.value == "paused"

    def test_completed_value(self):
        assert CopilotStatus.COMPLETED.value == "completed"

    def test_terminated_value(self):
        assert CopilotStatus.TERMINATED.value == "terminated"

    def test_member_count(self):
        assert len(CopilotStatus) == 4

    def test_terminal_states_set(self):
        terminal = {CopilotStatus.COMPLETED, CopilotStatus.TERMINATED}
        assert CopilotStatus.ACTIVE not in terminal
        assert CopilotStatus.PAUSED not in terminal
        assert CopilotStatus.COMPLETED in terminal
        assert CopilotStatus.TERMINATED in terminal

    def test_from_value(self):
        assert CopilotStatus("completed") is CopilotStatus.COMPLETED

    def test_invalid(self):
        with pytest.raises(ValueError):
            CopilotStatus("unknown")

    def test_not_equal_to_string(self):
        assert CopilotStatus.ACTIVE != "active"


class TestActionDisposition:
    def test_allowed_value(self):
        assert ActionDisposition.ALLOWED.value == "allowed"

    def test_denied_value(self):
        assert ActionDisposition.DENIED.value == "denied"

    def test_escalated_value(self):
        assert ActionDisposition.ESCALATED.value == "escalated"

    def test_deferred_value(self):
        assert ActionDisposition.DEFERRED.value == "deferred"

    def test_member_count(self):
        assert len(ActionDisposition) == 4

    def test_from_value(self):
        assert ActionDisposition("denied") is ActionDisposition.DENIED

    def test_invalid(self):
        with pytest.raises(ValueError):
            ActionDisposition("rejected")

    def test_not_equal_to_string(self):
        assert ActionDisposition.ALLOWED != "allowed"


class TestResponseMode:
    def test_evidence_backed_value(self):
        assert ResponseMode.EVIDENCE_BACKED.value == "evidence_backed"

    def test_synthesis_value(self):
        assert ResponseMode.SYNTHESIS.value == "synthesis"

    def test_direct_value(self):
        assert ResponseMode.DIRECT.value == "direct"

    def test_fallback_value(self):
        assert ResponseMode.FALLBACK.value == "fallback"

    def test_member_count(self):
        assert len(ResponseMode) == 4

    def test_from_value(self):
        assert ResponseMode("synthesis") is ResponseMode.SYNTHESIS

    def test_invalid(self):
        with pytest.raises(ValueError):
            ResponseMode("unknown")


class TestConversationRiskLevel:
    def test_low_value(self):
        assert ConversationRiskLevel.LOW.value == "low"

    def test_medium_value(self):
        assert ConversationRiskLevel.MEDIUM.value == "medium"

    def test_high_value(self):
        assert ConversationRiskLevel.HIGH.value == "high"

    def test_critical_value(self):
        assert ConversationRiskLevel.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(ConversationRiskLevel) == 4

    def test_from_value(self):
        assert ConversationRiskLevel("critical") is ConversationRiskLevel.CRITICAL

    def test_invalid(self):
        with pytest.raises(ValueError):
            ConversationRiskLevel("extreme")

    def test_not_equal_to_string(self):
        assert ConversationRiskLevel.LOW != "low"


# ===================================================================
# ConversationSession TESTS
# ===================================================================


class TestConversationSession:
    def test_valid_construction(self):
        s = _session()
        assert s.session_id == "s1"
        assert s.tenant_id == "t1"
        assert s.identity_ref == "u1"
        assert s.mode is ConversationMode.INTERACTIVE
        assert s.status is CopilotStatus.ACTIVE
        assert s.turn_count == 0

    def test_all_modes(self):
        for m in ConversationMode:
            s = _session(mode=m)
            assert s.mode is m

    def test_all_statuses(self):
        for st in CopilotStatus:
            s = _session(status=st)
            assert s.status is st

    def test_frozen_session_id(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.session_id = "x"

    def test_frozen_tenant_id(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.tenant_id = "x"

    def test_frozen_identity_ref(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.identity_ref = "x"

    def test_frozen_status(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.status = CopilotStatus.PAUSED

    def test_frozen_mode(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.mode = ConversationMode.GUIDED

    def test_frozen_turn_count(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.turn_count = 99

    def test_frozen_metadata(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.metadata = {}

    def test_frozen_created_at(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.created_at = TS2

    def test_empty_session_id(self):
        with pytest.raises(ValueError):
            _session(session_id="")

    def test_whitespace_session_id(self):
        with pytest.raises(ValueError):
            _session(session_id="   ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _session(tenant_id="")

    def test_whitespace_tenant_id(self):
        with pytest.raises(ValueError):
            _session(tenant_id="  ")

    def test_empty_identity_ref(self):
        with pytest.raises(ValueError):
            _session(identity_ref="")

    def test_whitespace_identity_ref(self):
        with pytest.raises(ValueError):
            _session(identity_ref="  ")

    def test_invalid_mode_type(self):
        with pytest.raises(ValueError):
            _session(mode="interactive")

    def test_invalid_mode_none(self):
        with pytest.raises(ValueError):
            _session(mode=None)

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            _session(status="active")

    def test_invalid_status_none(self):
        with pytest.raises(ValueError):
            _session(status=None)

    def test_negative_turn_count(self):
        with pytest.raises(ValueError):
            _session(turn_count=-1)

    def test_bool_turn_count(self):
        with pytest.raises(ValueError):
            _session(turn_count=True)

    def test_float_turn_count(self):
        with pytest.raises(ValueError):
            _session(turn_count=1.5)

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _session(created_at="")

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _session(created_at="not-a-date")

    def test_valid_turn_count(self):
        s = _session(turn_count=42)
        assert s.turn_count == 42

    def test_zero_turn_count(self):
        s = _session(turn_count=0)
        assert s.turn_count == 0

    def test_large_turn_count(self):
        s = _session(turn_count=999999)
        assert s.turn_count == 999999

    def test_metadata_default_empty(self):
        s = _session()
        assert len(s.metadata) == 0

    def test_metadata_frozen_mapping(self):
        s = _session(metadata={"k": "v"})
        with pytest.raises(TypeError):
            s.metadata["k2"] = "v2"

    def test_metadata_nested_frozen(self):
        s = _session(metadata={"nested": {"a": 1}})
        with pytest.raises(TypeError):
            s.metadata["nested"]["b"] = 2

    def test_to_dict_preserves_enums(self):
        s = _session()
        d = s.to_dict()
        assert d["mode"] is ConversationMode.INTERACTIVE
        assert d["status"] is CopilotStatus.ACTIVE

    def test_to_json_dict_converts_enums(self):
        s = _session()
        d = s.to_json_dict()
        assert d["mode"] == "interactive"
        assert d["status"] == "active"

    def test_to_json_serializable(self):
        s = _session()
        j = s.to_json()
        parsed = json.loads(j)
        assert parsed["session_id"] == "s1"
        assert parsed["mode"] == "interactive"

    def test_to_dict_all_keys(self):
        s = _session()
        d = s.to_dict()
        expected_keys = {
            "session_id", "tenant_id", "identity_ref", "mode",
            "status", "turn_count", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_equality(self):
        assert _session() == _session()

    def test_inequality_session_id(self):
        assert _session(session_id="s1") != _session(session_id="s2")

    def test_inequality_status(self):
        assert _session(status=CopilotStatus.ACTIVE) != _session(status=CopilotStatus.PAUSED)

    def test_inequality_mode(self):
        assert _session(mode=ConversationMode.INTERACTIVE) != _session(mode=ConversationMode.GUIDED)

    def test_iso_date_only(self):
        s = _session(created_at="2025-06-01")
        assert s.created_at == "2025-06-01"

    def test_iso_z_suffix(self):
        s = _session(created_at="2025-06-01T00:00:00Z")
        assert s.created_at == "2025-06-01T00:00:00Z"

    def test_iso_offset(self):
        s = _session(created_at="2025-06-01T12:00:00+05:30")
        assert s.created_at == "2025-06-01T12:00:00+05:30"

    def test_metadata_with_list_frozen_to_tuple(self):
        s = _session(metadata={"items": [1, 2, 3]})
        assert isinstance(s.metadata["items"], tuple)

    def test_metadata_nested_list_frozen(self):
        s = _session(metadata={"ids": [1, 2, [3, 4]]})
        inner = s.metadata["ids"]
        assert isinstance(inner, tuple)
        assert isinstance(inner[2], tuple)

    def test_has_slots(self):
        s = _session()
        assert hasattr(s, "__slots__")

    def test_frozen_field(self):
        s = _session()
        with pytest.raises((AttributeError, FrozenInstanceError)):
            setattr(s, "session_id", "changed")

    def test_equal_objects(self):
        assert _session() == _session()


# ===================================================================
# IntentRecord TESTS
# ===================================================================


class TestIntentRecord:
    def test_valid_construction(self):
        i = _intent()
        assert i.intent_id == "i1"
        assert i.kind is IntentKind.QUERY

    def test_all_kinds(self):
        for k in IntentKind:
            i = _intent(kind=k)
            assert i.kind is k

    def test_frozen_intent_id(self):
        i = _intent()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            i.intent_id = "x"

    def test_frozen_kind(self):
        i = _intent()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            i.kind = IntentKind.ACTION

    def test_frozen_tenant_id(self):
        i = _intent()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            i.tenant_id = "x"

    def test_frozen_raw_input(self):
        i = _intent()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            i.raw_input = "x"

    def test_empty_intent_id(self):
        with pytest.raises(ValueError):
            _intent(intent_id="")

    def test_whitespace_intent_id(self):
        with pytest.raises(ValueError):
            _intent(intent_id="  ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _intent(tenant_id="")

    def test_empty_session_ref(self):
        with pytest.raises(ValueError):
            _intent(session_ref="")

    def test_empty_raw_input(self):
        with pytest.raises(ValueError):
            _intent(raw_input="")

    def test_whitespace_raw_input(self):
        with pytest.raises(ValueError):
            _intent(raw_input="   ")

    def test_invalid_kind_type(self):
        with pytest.raises(ValueError):
            _intent(kind="query")

    def test_invalid_kind_none(self):
        with pytest.raises(ValueError):
            _intent(kind=None)

    def test_invalid_classified_at(self):
        with pytest.raises(ValueError):
            _intent(classified_at="not-a-date")

    def test_empty_classified_at(self):
        with pytest.raises(ValueError):
            _intent(classified_at="")

    def test_to_dict_preserves_enums(self):
        i = _intent()
        d = i.to_dict()
        assert d["kind"] is IntentKind.QUERY

    def test_to_json_dict_converts_enums(self):
        i = _intent()
        d = i.to_json_dict()
        assert d["kind"] == "query"

    def test_to_dict_keys(self):
        d = _intent().to_dict()
        expected = {"intent_id", "tenant_id", "session_ref", "kind",
                    "raw_input", "classified_at", "metadata"}
        assert set(d.keys()) == expected

    def test_metadata_frozen(self):
        i = _intent(metadata={"x": 1})
        with pytest.raises(TypeError):
            i.metadata["y"] = 2

    def test_equality(self):
        assert _intent() == _intent()

    def test_inequality(self):
        assert _intent(intent_id="i1") != _intent(intent_id="i2")

    def test_slots(self):
        assert hasattr(_intent(), "__slots__")

    def test_to_json_roundtrip(self):
        j = _intent().to_json()
        parsed = json.loads(j)
        assert parsed["intent_id"] == "i1"
        assert parsed["kind"] == "query"


# ===================================================================
# ConversationTurn TESTS
# ===================================================================


class TestConversationTurn:
    def test_valid_construction(self):
        t = _turn()
        assert t.turn_id == "tr1"
        assert t.response_mode is ResponseMode.DIRECT

    def test_all_response_modes(self):
        for m in ResponseMode:
            t = _turn(response_mode=m)
            assert t.response_mode is m

    def test_frozen_turn_id(self):
        t = _turn()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            t.turn_id = "x"

    def test_frozen_user_input(self):
        t = _turn()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            t.user_input = "changed"

    def test_frozen_assistant_output(self):
        t = _turn()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            t.assistant_output = "changed"

    def test_frozen_response_mode(self):
        t = _turn()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            t.response_mode = ResponseMode.FALLBACK

    def test_frozen_tenant_id(self):
        t = _turn()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            t.tenant_id = "x"

    def test_empty_turn_id(self):
        with pytest.raises(ValueError):
            _turn(turn_id="")

    def test_whitespace_turn_id(self):
        with pytest.raises(ValueError):
            _turn(turn_id="  ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _turn(tenant_id="")

    def test_empty_session_ref(self):
        with pytest.raises(ValueError):
            _turn(session_ref="")

    def test_empty_intent_ref(self):
        with pytest.raises(ValueError):
            _turn(intent_ref="")

    def test_empty_user_input(self):
        with pytest.raises(ValueError):
            _turn(user_input="")

    def test_whitespace_user_input(self):
        with pytest.raises(ValueError):
            _turn(user_input="  ")

    def test_empty_assistant_output(self):
        with pytest.raises(ValueError):
            _turn(assistant_output="")

    def test_whitespace_assistant_output(self):
        with pytest.raises(ValueError):
            _turn(assistant_output="  ")

    def test_invalid_response_mode(self):
        with pytest.raises(ValueError):
            _turn(response_mode="direct")

    def test_invalid_response_mode_none(self):
        with pytest.raises(ValueError):
            _turn(response_mode=None)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _turn(created_at="nope")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _turn(created_at="")

    def test_to_dict_preserves_enums(self):
        d = _turn().to_dict()
        assert d["response_mode"] is ResponseMode.DIRECT

    def test_to_json_dict_converts(self):
        d = _turn().to_json_dict()
        assert d["response_mode"] == "direct"

    def test_to_dict_keys(self):
        d = _turn().to_dict()
        expected = {"turn_id", "tenant_id", "session_ref", "intent_ref",
                    "user_input", "assistant_output", "response_mode",
                    "created_at", "metadata"}
        assert set(d.keys()) == expected

    def test_metadata_frozen(self):
        t = _turn(metadata={"a": "b"})
        with pytest.raises(TypeError):
            t.metadata["c"] = "d"

    def test_equality(self):
        assert _turn() == _turn()

    def test_inequality(self):
        assert _turn(turn_id="tr1") != _turn(turn_id="tr2")

    def test_slots(self):
        assert hasattr(_turn(), "__slots__")

    def test_multiline_input(self):
        t = _turn(user_input="line1\nline2\nline3")
        assert "\n" in t.user_input

    def test_to_json_roundtrip(self):
        j = _turn().to_json()
        parsed = json.loads(j)
        assert parsed["turn_id"] == "tr1"


# ===================================================================
# ActionPlan TESTS
# ===================================================================


class TestActionPlan:
    def test_valid_construction(self):
        p = _plan()
        assert p.plan_id == "p1"
        assert p.risk_level is ConversationRiskLevel.LOW
        assert p.disposition is ActionDisposition.ALLOWED

    def test_all_risk_levels(self):
        for r in ConversationRiskLevel:
            p = _plan(risk_level=r)
            assert p.risk_level is r

    def test_all_dispositions(self):
        for d in ActionDisposition:
            p = _plan(disposition=d)
            assert p.disposition is d

    def test_frozen_plan_id(self):
        p = _plan()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.plan_id = "x"

    def test_frozen_risk_level(self):
        p = _plan()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.risk_level = ConversationRiskLevel.HIGH

    def test_frozen_disposition(self):
        p = _plan()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.disposition = ActionDisposition.DENIED

    def test_frozen_operation(self):
        p = _plan()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.operation = "x"

    def test_frozen_target_runtime(self):
        p = _plan()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.target_runtime = "x"

    def test_empty_plan_id(self):
        with pytest.raises(ValueError):
            _plan(plan_id="")

    def test_whitespace_plan_id(self):
        with pytest.raises(ValueError):
            _plan(plan_id="  ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _plan(tenant_id="")

    def test_empty_session_ref(self):
        with pytest.raises(ValueError):
            _plan(session_ref="")

    def test_empty_intent_ref(self):
        with pytest.raises(ValueError):
            _plan(intent_ref="")

    def test_empty_target_runtime(self):
        with pytest.raises(ValueError):
            _plan(target_runtime="")

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            _plan(operation="")

    def test_whitespace_operation(self):
        with pytest.raises(ValueError):
            _plan(operation="  ")

    def test_invalid_risk_level_type(self):
        with pytest.raises(ValueError):
            _plan(risk_level="low")

    def test_invalid_risk_level_none(self):
        with pytest.raises(ValueError):
            _plan(risk_level=None)

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            _plan(disposition="allowed")

    def test_invalid_disposition_none(self):
        with pytest.raises(ValueError):
            _plan(disposition=None)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _plan(created_at="nope")

    def test_to_dict_preserves_enums(self):
        d = _plan().to_dict()
        assert d["risk_level"] is ConversationRiskLevel.LOW
        assert d["disposition"] is ActionDisposition.ALLOWED

    def test_to_json_dict_converts(self):
        d = _plan().to_json_dict()
        assert d["risk_level"] == "low"
        assert d["disposition"] == "allowed"

    def test_to_dict_keys(self):
        d = _plan().to_dict()
        expected = {"plan_id", "tenant_id", "session_ref", "intent_ref",
                    "target_runtime", "operation", "risk_level",
                    "disposition", "created_at", "metadata"}
        assert set(d.keys()) == expected

    def test_metadata_frozen(self):
        p = _plan(metadata={"x": 1})
        with pytest.raises(TypeError):
            p.metadata["y"] = 2

    def test_equality(self):
        assert _plan() == _plan()

    def test_inequality(self):
        assert _plan(plan_id="p1") != _plan(plan_id="p2")

    def test_slots(self):
        assert hasattr(_plan(), "__slots__")

    def test_all_risk_disposition_combos(self):
        for risk in ConversationRiskLevel:
            for disp in ActionDisposition:
                p = _plan(risk_level=risk, disposition=disp)
                assert p.risk_level is risk
                assert p.disposition is disp


# ===================================================================
# CopilotDecision TESTS
# ===================================================================


class TestCopilotDecision:
    def test_valid_construction(self):
        d = _decision()
        assert d.decision_id == "d1"
        assert d.disposition is ActionDisposition.ALLOWED

    def test_all_dispositions(self):
        for disp in ActionDisposition:
            d = _decision(disposition=disp)
            assert d.disposition is disp

    def test_frozen_decision_id(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            d.decision_id = "x"

    def test_frozen_disposition(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            d.disposition = ActionDisposition.DENIED

    def test_frozen_reason(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            d.reason = "new"

    def test_frozen_tenant_id(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            d.tenant_id = "x"

    def test_frozen_plan_ref(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            d.plan_ref = "x"

    def test_empty_decision_id(self):
        with pytest.raises(ValueError):
            _decision(decision_id="")

    def test_whitespace_decision_id(self):
        with pytest.raises(ValueError):
            _decision(decision_id="  ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _decision(tenant_id="")

    def test_empty_session_ref(self):
        with pytest.raises(ValueError):
            _decision(session_ref="")

    def test_empty_plan_ref(self):
        with pytest.raises(ValueError):
            _decision(plan_ref="")

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            _decision(reason="")

    def test_whitespace_reason(self):
        with pytest.raises(ValueError):
            _decision(reason="  ")

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            _decision(disposition="allowed")

    def test_invalid_disposition_none(self):
        with pytest.raises(ValueError):
            _decision(disposition=None)

    def test_evidence_refs_can_be_empty(self):
        d = _decision(evidence_refs="")
        assert d.evidence_refs == ""

    def test_evidence_refs_nonempty(self):
        d = _decision(evidence_refs="ref1,ref2")
        assert d.evidence_refs == "ref1,ref2"

    def test_invalid_decided_at(self):
        with pytest.raises(ValueError):
            _decision(decided_at="nope")

    def test_empty_decided_at(self):
        with pytest.raises(ValueError):
            _decision(decided_at="")

    def test_to_dict_preserves_enums(self):
        d = _decision().to_dict()
        assert d["disposition"] is ActionDisposition.ALLOWED

    def test_to_json_dict_converts(self):
        d = _decision().to_json_dict()
        assert d["disposition"] == "allowed"

    def test_to_dict_keys(self):
        d = _decision().to_dict()
        expected = {"decision_id", "tenant_id", "session_ref", "plan_ref",
                    "disposition", "reason", "evidence_refs", "decided_at",
                    "metadata"}
        assert set(d.keys()) == expected

    def test_equality(self):
        assert _decision() == _decision()

    def test_inequality(self):
        assert _decision(decision_id="d1") != _decision(decision_id="d2")

    def test_slots(self):
        assert hasattr(_decision(), "__slots__")

    def test_metadata_with_values(self):
        d = _decision(metadata={"audit": True, "tags": ["a", "b"]})
        assert d.metadata["audit"] is True
        assert isinstance(d.metadata["tags"], tuple)


# ===================================================================
# EvidenceBackedResponse TESTS
# ===================================================================


class TestEvidenceBackedResponse:
    def test_valid_construction(self):
        e = _evidence()
        assert e.response_id == "r1"
        assert e.evidence_count == 3
        assert e.confidence == 0.9

    def test_confidence_zero(self):
        e = _evidence(confidence=0.0)
        assert e.confidence == 0.0

    def test_confidence_one(self):
        e = _evidence(confidence=1.0)
        assert e.confidence == 1.0

    def test_confidence_mid(self):
        e = _evidence(confidence=0.5)
        assert e.confidence == 0.5

    def test_confidence_above_one(self):
        with pytest.raises(ValueError):
            _evidence(confidence=1.1)

    def test_confidence_below_zero(self):
        with pytest.raises(ValueError):
            _evidence(confidence=-0.1)

    def test_confidence_nan(self):
        with pytest.raises(ValueError):
            _evidence(confidence=float("nan"))

    def test_confidence_inf(self):
        with pytest.raises(ValueError):
            _evidence(confidence=float("inf"))

    def test_confidence_neg_inf(self):
        with pytest.raises(ValueError):
            _evidence(confidence=float("-inf"))

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError):
            _evidence(confidence=True)

    def test_confidence_false_rejected(self):
        with pytest.raises(ValueError):
            _evidence(confidence=False)

    def test_confidence_int_one(self):
        e = _evidence(confidence=1)
        assert e.confidence == 1.0

    def test_confidence_int_zero(self):
        e = _evidence(confidence=0)
        assert e.confidence == 0.0

    def test_confidence_epsilon(self):
        e = _evidence(confidence=0.0000001)
        assert e.confidence > 0.0

    def test_confidence_near_one(self):
        e = _evidence(confidence=0.9999999)
        assert e.confidence < 1.0

    def test_evidence_count_zero(self):
        e = _evidence(evidence_count=0)
        assert e.evidence_count == 0

    def test_evidence_count_large(self):
        e = _evidence(evidence_count=1000)
        assert e.evidence_count == 1000

    def test_evidence_count_negative(self):
        with pytest.raises(ValueError):
            _evidence(evidence_count=-1)

    def test_evidence_count_bool(self):
        with pytest.raises(ValueError):
            _evidence(evidence_count=True)

    def test_evidence_count_false_bool(self):
        with pytest.raises(ValueError):
            _evidence(evidence_count=False)

    def test_frozen_response_id(self):
        e = _evidence()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            e.response_id = "x"

    def test_frozen_confidence(self):
        e = _evidence()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            e.confidence = 0.5

    def test_frozen_content(self):
        e = _evidence()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            e.content = "new"

    def test_frozen_evidence_count(self):
        e = _evidence()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            e.evidence_count = 99

    def test_empty_response_id(self):
        with pytest.raises(ValueError):
            _evidence(response_id="")

    def test_whitespace_response_id(self):
        with pytest.raises(ValueError):
            _evidence(response_id="  ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _evidence(tenant_id="")

    def test_empty_session_ref(self):
        with pytest.raises(ValueError):
            _evidence(session_ref="")

    def test_empty_turn_ref(self):
        with pytest.raises(ValueError):
            _evidence(turn_ref="")

    def test_empty_content(self):
        with pytest.raises(ValueError):
            _evidence(content="")

    def test_whitespace_content(self):
        with pytest.raises(ValueError):
            _evidence(content="  ")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _evidence(created_at="nope")

    def test_to_dict_keys(self):
        d = _evidence().to_dict()
        expected = {"response_id", "tenant_id", "session_ref", "turn_ref",
                    "content", "evidence_count", "confidence", "created_at",
                    "metadata"}
        assert set(d.keys()) == expected

    def test_to_json_serializable(self):
        j = _evidence().to_json()
        parsed = json.loads(j)
        assert parsed["confidence"] == 0.9
        assert parsed["evidence_count"] == 3

    def test_equality(self):
        assert _evidence() == _evidence()

    def test_inequality(self):
        assert _evidence(response_id="r1") != _evidence(response_id="r2")

    def test_slots(self):
        assert hasattr(_evidence(), "__slots__")

    def test_metadata_frozen(self):
        e = _evidence(metadata={"k": "v"})
        with pytest.raises(TypeError):
            e.metadata["k2"] = "v2"


# ===================================================================
# ConversationViolation TESTS
# ===================================================================


class TestConversationViolation:
    def test_valid_construction(self):
        v = _violation()
        assert v.violation_id == "v1"
        assert v.operation == "cross_tenant"

    def test_frozen_violation_id(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            v.violation_id = "x"

    def test_frozen_reason(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            v.reason = "new"

    def test_frozen_operation(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            v.operation = "x"

    def test_frozen_tenant_id(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            v.tenant_id = "x"

    def test_empty_violation_id(self):
        with pytest.raises(ValueError):
            _violation(violation_id="")

    def test_whitespace_violation_id(self):
        with pytest.raises(ValueError):
            _violation(violation_id="  ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _violation(tenant_id="")

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            _violation(operation="")

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            _violation(reason="")

    def test_whitespace_reason(self):
        with pytest.raises(ValueError):
            _violation(reason="  ")

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            _violation(detected_at="nope")

    def test_empty_detected_at(self):
        with pytest.raises(ValueError):
            _violation(detected_at="")

    def test_to_dict_keys(self):
        d = _violation().to_dict()
        expected = {"violation_id", "tenant_id", "operation", "reason",
                    "detected_at", "metadata"}
        assert set(d.keys()) == expected

    def test_equality(self):
        assert _violation() == _violation()

    def test_inequality(self):
        assert _violation(violation_id="v1") != _violation(violation_id="v2")

    def test_metadata_frozen(self):
        v = _violation(metadata={"k": "v"})
        with pytest.raises(TypeError):
            v.metadata["k2"] = "v2"

    def test_slots(self):
        assert hasattr(_violation(), "__slots__")

    def test_to_json_roundtrip(self):
        j = _violation().to_json()
        parsed = json.loads(j)
        assert parsed["violation_id"] == "v1"


# ===================================================================
# CopilotSnapshot TESTS
# ===================================================================


class TestCopilotSnapshot:
    def test_valid_construction(self):
        s = _snapshot()
        assert s.snapshot_id == "snap1"
        assert s.total_sessions == 1

    def test_frozen_snapshot_id(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.snapshot_id = "x"

    def test_frozen_total_sessions(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.total_sessions = 99

    def test_frozen_total_turns(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.total_turns = 99

    def test_frozen_total_intents(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.total_intents = 99

    def test_frozen_total_plans(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.total_plans = 99

    def test_frozen_total_decisions(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.total_decisions = 99

    def test_frozen_total_violations(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.total_violations = 99

    def test_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _snapshot(tenant_id="")

    def test_negative_total_sessions(self):
        with pytest.raises(ValueError):
            _snapshot(total_sessions=-1)

    def test_negative_total_turns(self):
        with pytest.raises(ValueError):
            _snapshot(total_turns=-1)

    def test_negative_total_intents(self):
        with pytest.raises(ValueError):
            _snapshot(total_intents=-1)

    def test_negative_total_plans(self):
        with pytest.raises(ValueError):
            _snapshot(total_plans=-1)

    def test_negative_total_decisions(self):
        with pytest.raises(ValueError):
            _snapshot(total_decisions=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            _snapshot(total_violations=-1)

    def test_bool_total_sessions(self):
        with pytest.raises(ValueError):
            _snapshot(total_sessions=True)

    def test_bool_total_turns(self):
        with pytest.raises(ValueError):
            _snapshot(total_turns=True)

    def test_zero_totals(self):
        s = _snapshot(total_sessions=0, total_turns=0, total_intents=0,
                      total_plans=0, total_decisions=0, total_violations=0)
        assert s.total_sessions == 0
        assert s.total_turns == 0

    def test_large_totals(self):
        s = _snapshot(total_sessions=999999, total_turns=999999)
        assert s.total_sessions == 999999

    def test_to_dict_keys(self):
        d = _snapshot().to_dict()
        expected = {"snapshot_id", "tenant_id", "total_sessions",
                    "total_turns", "total_intents", "total_plans",
                    "total_decisions", "total_violations",
                    "captured_at", "metadata"}
        assert set(d.keys()) == expected

    def test_equality(self):
        assert _snapshot() == _snapshot()

    def test_inequality(self):
        assert _snapshot(snapshot_id="a") != _snapshot(snapshot_id="b")

    def test_slots(self):
        assert hasattr(_snapshot(), "__slots__")

    def test_to_json_roundtrip(self):
        j = _snapshot().to_json()
        parsed = json.loads(j)
        assert parsed["snapshot_id"] == "snap1"

    def test_metadata_frozen(self):
        s = _snapshot(metadata={"k": "v"})
        with pytest.raises(TypeError):
            s.metadata["k2"] = "v2"


# ===================================================================
# CopilotAssessment TESTS
# ===================================================================


class TestCopilotAssessment:
    def test_valid_construction(self):
        a = _assessment()
        assert a.assessment_id == "a1"
        assert a.success_rate == 1.0

    def test_frozen_assessment_id(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.assessment_id = "x"

    def test_frozen_success_rate(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.success_rate = 0.5

    def test_frozen_total_sessions(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.total_sessions = 99

    def test_frozen_total_allowed(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.total_actions_allowed = 99

    def test_frozen_total_denied(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.total_actions_denied = 99

    def test_empty_assessment_id(self):
        with pytest.raises(ValueError):
            _assessment(assessment_id="")

    def test_whitespace_assessment_id(self):
        with pytest.raises(ValueError):
            _assessment(assessment_id="  ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _assessment(tenant_id="")

    def test_negative_total_sessions(self):
        with pytest.raises(ValueError):
            _assessment(total_sessions=-1)

    def test_negative_allowed(self):
        with pytest.raises(ValueError):
            _assessment(total_actions_allowed=-1)

    def test_negative_denied(self):
        with pytest.raises(ValueError):
            _assessment(total_actions_denied=-1)

    def test_bool_total_sessions(self):
        with pytest.raises(ValueError):
            _assessment(total_sessions=True)

    def test_bool_allowed(self):
        with pytest.raises(ValueError):
            _assessment(total_actions_allowed=True)

    def test_success_rate_zero(self):
        a = _assessment(success_rate=0.0)
        assert a.success_rate == 0.0

    def test_success_rate_one(self):
        a = _assessment(success_rate=1.0)
        assert a.success_rate == 1.0

    def test_success_rate_mid(self):
        a = _assessment(success_rate=0.5)
        assert a.success_rate == 0.5

    def test_success_rate_above_one(self):
        with pytest.raises(ValueError):
            _assessment(success_rate=1.01)

    def test_success_rate_below_zero(self):
        with pytest.raises(ValueError):
            _assessment(success_rate=-0.01)

    def test_success_rate_nan(self):
        with pytest.raises(ValueError):
            _assessment(success_rate=float("nan"))

    def test_success_rate_inf(self):
        with pytest.raises(ValueError):
            _assessment(success_rate=float("inf"))

    def test_success_rate_neg_inf(self):
        with pytest.raises(ValueError):
            _assessment(success_rate=float("-inf"))

    def test_success_rate_bool(self):
        with pytest.raises(ValueError):
            _assessment(success_rate=True)

    def test_success_rate_int_one(self):
        a = _assessment(success_rate=1)
        assert a.success_rate == 1.0

    def test_success_rate_int_zero(self):
        a = _assessment(success_rate=0)
        assert a.success_rate == 0.0

    def test_to_dict_keys(self):
        d = _assessment().to_dict()
        expected = {"assessment_id", "tenant_id", "total_sessions",
                    "total_actions_allowed", "total_actions_denied",
                    "success_rate", "assessed_at", "metadata"}
        assert set(d.keys()) == expected

    def test_equality(self):
        assert _assessment() == _assessment()

    def test_inequality(self):
        assert _assessment(assessment_id="a1") != _assessment(assessment_id="a2")

    def test_slots(self):
        assert hasattr(_assessment(), "__slots__")

    def test_to_json_roundtrip(self):
        j = _assessment().to_json()
        parsed = json.loads(j)
        assert parsed["success_rate"] == 1.0

    def test_metadata_frozen(self):
        a = _assessment(metadata={"k": "v"})
        with pytest.raises(TypeError):
            a.metadata["k2"] = "v2"


# ===================================================================
# CopilotClosureReport TESTS
# ===================================================================


class TestCopilotClosureReport:
    def test_valid_construction(self):
        c = _closure()
        assert c.report_id == "cr1"
        assert c.total_sessions == 2
        assert c.total_turns == 10

    def test_frozen_report_id(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            c.report_id = "x"

    def test_frozen_total_sessions(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            c.total_sessions = 99

    def test_frozen_total_turns(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            c.total_turns = 99

    def test_frozen_total_plans(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            c.total_plans = 99

    def test_frozen_total_decisions(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            c.total_decisions = 99

    def test_frozen_total_violations(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            c.total_violations = 99

    def test_empty_report_id(self):
        with pytest.raises(ValueError):
            _closure(report_id="")

    def test_whitespace_report_id(self):
        with pytest.raises(ValueError):
            _closure(report_id="  ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _closure(tenant_id="")

    def test_negative_total_sessions(self):
        with pytest.raises(ValueError):
            _closure(total_sessions=-1)

    def test_negative_total_turns(self):
        with pytest.raises(ValueError):
            _closure(total_turns=-1)

    def test_negative_total_plans(self):
        with pytest.raises(ValueError):
            _closure(total_plans=-1)

    def test_negative_total_decisions(self):
        with pytest.raises(ValueError):
            _closure(total_decisions=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            _closure(total_violations=-1)

    def test_bool_total_sessions(self):
        with pytest.raises(ValueError):
            _closure(total_sessions=True)

    def test_bool_total_turns(self):
        with pytest.raises(ValueError):
            _closure(total_turns=True)

    def test_zero_totals(self):
        c = _closure(total_sessions=0, total_turns=0, total_plans=0,
                     total_decisions=0, total_violations=0)
        assert c.total_sessions == 0

    def test_large_totals(self):
        c = _closure(total_sessions=999999, total_turns=999999)
        assert c.total_sessions == 999999

    def test_to_dict_keys(self):
        d = _closure().to_dict()
        expected = {"report_id", "tenant_id", "total_sessions",
                    "total_turns", "total_plans", "total_decisions",
                    "total_violations", "created_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_json_serializable(self):
        j = _closure().to_json()
        parsed = json.loads(j)
        assert parsed["report_id"] == "cr1"

    def test_equality(self):
        assert _closure() == _closure()

    def test_inequality(self):
        assert _closure(report_id="a") != _closure(report_id="b")

    def test_metadata_frozen(self):
        c = _closure(metadata={"k": "v"})
        with pytest.raises(TypeError):
            c.metadata["k2"] = "v2"

    def test_slots(self):
        assert hasattr(_closure(), "__slots__")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _closure(created_at="nope")


# ===================================================================
# CROSS-CUTTING / PARAMETRIZED TESTS
# ===================================================================


ALL_DATACLASS_FACTORIES = [
    _session, _intent, _turn, _plan, _decision,
    _evidence, _violation, _snapshot, _assessment, _closure,
]


class TestCrossCutting:
    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_to_dict_returns_dict(self, factory):
        assert isinstance(factory().to_dict(), dict)

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_to_json_dict_returns_dict(self, factory):
        assert isinstance(factory().to_json_dict(), dict)

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_to_json_returns_str(self, factory):
        assert isinstance(factory().to_json(), str)

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_to_json_is_valid_json(self, factory):
        parsed = json.loads(factory().to_json())
        assert isinstance(parsed, dict)

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_equality_is_stable(self, factory):
        obj = factory()
        assert obj == factory()

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_repr_contains_class_name(self, factory):
        obj = factory()
        assert type(obj).__name__ in repr(obj)

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_equality_identity(self, factory):
        obj = factory()
        assert obj == obj

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_metadata_key_present(self, factory):
        assert "metadata" in factory().to_dict()

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_tenant_id_key_present(self, factory):
        assert "tenant_id" in factory().to_dict()

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_to_dict_metadata_is_dict(self, factory):
        d = factory().to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("factory", ALL_DATACLASS_FACTORIES)
    def test_to_json_dict_metadata_is_dict(self, factory):
        d = factory().to_json_dict()
        assert isinstance(d["metadata"], dict)


# ===================================================================
# EDGE-CASE / BOUNDARY TESTS
# ===================================================================


class TestEdgeCases:
    def test_session_very_long_id(self):
        s = _session(session_id="x" * 10000)
        assert len(s.session_id) == 10000

    def test_intent_unicode_raw_input(self):
        i = _intent(raw_input="Hello \u2603 \U0001f600")
        assert "\u2603" in i.raw_input

    def test_turn_multiline_output(self):
        t = _turn(assistant_output="line1\nline2\nline3")
        assert "\n" in t.assistant_output

    def test_plan_with_all_metadata_types(self):
        p = _plan(metadata={"str": "a", "int": 1, "float": 1.5,
                            "bool": True, "null": None,
                            "list": [1, 2], "dict": {"nested": True}})
        assert p.metadata["str"] == "a"
        assert p.metadata["int"] == 1
        assert p.metadata["float"] == 1.5

    def test_evidence_boundary_zero(self):
        e = _evidence(confidence=0.0)
        assert e.confidence == 0.0

    def test_evidence_boundary_one(self):
        e = _evidence(confidence=1.0)
        assert e.confidence == 1.0

    def test_snapshot_all_zeros(self):
        s = _snapshot(total_sessions=0, total_turns=0, total_intents=0,
                      total_plans=0, total_decisions=0, total_violations=0)
        d = s.to_dict()
        for k in ["total_sessions", "total_turns", "total_intents",
                   "total_plans", "total_decisions", "total_violations"]:
            assert d[k] == 0

    def test_assessment_zero_rate(self):
        a = _assessment(success_rate=0.0, total_actions_allowed=0,
                        total_actions_denied=10)
        assert a.success_rate == 0.0

    def test_decision_long_reason(self):
        d = _decision(reason="x" * 5000)
        assert len(d.reason) == 5000

    def test_violation_long_operation(self):
        v = _violation(operation="op_" * 1000)
        assert len(v.operation) == 3000

    def test_closure_all_zeros(self):
        c = _closure(total_sessions=0, total_turns=0, total_plans=0,
                     total_decisions=0, total_violations=0)
        assert c.total_sessions == 0

    def test_session_metadata_set_frozen_to_frozenset(self):
        s = _session(metadata={"tags": {"a", "b"}})
        assert isinstance(s.metadata["tags"], frozenset)

    def test_intent_metadata_preserves_values(self):
        i = _intent(metadata={"score": 42, "label": "test"})
        assert i.metadata["score"] == 42
        assert i.metadata["label"] == "test"

    def test_turn_evidence_backed_mode(self):
        t = _turn(response_mode=ResponseMode.EVIDENCE_BACKED)
        assert t.response_mode is ResponseMode.EVIDENCE_BACKED

    def test_plan_critical_escalated(self):
        p = _plan(risk_level=ConversationRiskLevel.CRITICAL,
                  disposition=ActionDisposition.ESCALATED)
        assert p.risk_level is ConversationRiskLevel.CRITICAL
        assert p.disposition is ActionDisposition.ESCALATED

    def test_multiple_sessions_different_tenants(self):
        s1 = _session(session_id="s1", tenant_id="t1")
        s2 = _session(session_id="s2", tenant_id="t2")
        assert s1.tenant_id != s2.tenant_id

    def test_session_non_none_type_error_on_int_session_id(self):
        with pytest.raises((ValueError, TypeError)):
            _session(session_id=123)

    def test_intent_non_none_type_error_on_int_intent_id(self):
        with pytest.raises((ValueError, TypeError)):
            _intent(intent_id=123)
