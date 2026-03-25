"""Comprehensive tests for persona / role / behavioral style runtime contracts.

Tests cover: enum membership, dataclass construction, validation failures,
frozen immutability, metadata freezing, to_dict() serialization, to_json_dict(),
to_json(), and edge cases for every contract type.
"""

from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.persona_runtime import (
    AuthorityMode,
    EscalationDirective,
    EscalationStyle,
    InteractionStyle,
    PersonaAssessment,
    PersonaClosureReport,
    PersonaDecision,
    PersonaKind,
    PersonaProfile,
    PersonaRiskLevel,
    PersonaSessionBinding,
    PersonaSnapshot,
    PersonaStatus,
    PersonaViolation,
    RoleBehaviorPolicy,
    StyleDirective,
)


# ===================================================================
# Helpers: valid kwargs for each dataclass
# ===================================================================

TS = "2025-06-01T00:00:00+00:00"


def _persona_profile_kw(**overrides):
    base = dict(
        persona_id="p-1", tenant_id="t-1", display_name="Ops Agent",
        kind=PersonaKind.OPERATOR, status=PersonaStatus.ACTIVE,
        interaction_style=InteractionStyle.CONCISE,
        authority_mode=AuthorityMode.GUIDED, created_at=TS,
    )
    base.update(overrides)
    return base


def _role_behavior_policy_kw(**overrides):
    base = dict(
        policy_id="pol-1", tenant_id="t-1", persona_ref="p-1",
        escalation_style=EscalationStyle.THRESHOLD,
        risk_level=PersonaRiskLevel.LOW,
        max_autonomy_depth=3, created_at=TS,
    )
    base.update(overrides)
    return base


def _style_directive_kw(**overrides):
    base = dict(
        directive_id="sd-1", tenant_id="t-1", persona_ref="p-1",
        scope="global", instruction="Be brief", priority=0,
        created_at=TS,
    )
    base.update(overrides)
    return base


def _escalation_directive_kw(**overrides):
    base = dict(
        directive_id="ed-1", tenant_id="t-1", persona_ref="p-1",
        trigger_condition="high_risk", target_role="supervisor",
        created_at=TS,
    )
    base.update(overrides)
    return base


def _persona_session_binding_kw(**overrides):
    base = dict(
        binding_id="b-1", tenant_id="t-1", persona_ref="p-1",
        session_ref="sess-1", bound_at=TS,
    )
    base.update(overrides)
    return base


def _persona_decision_kw(**overrides):
    base = dict(
        decision_id="d-1", tenant_id="t-1", persona_ref="p-1",
        session_ref="sess-1", action_taken="approve_order",
        style_applied=InteractionStyle.CONCISE,
        authority_used=AuthorityMode.GUIDED, decided_at=TS,
    )
    base.update(overrides)
    return base


def _persona_assessment_kw(**overrides):
    base = dict(
        assessment_id="a-1", tenant_id="t-1",
        total_personas=5, total_bindings=3, total_decisions=10,
        compliance_rate=0.95, assessed_at=TS,
    )
    base.update(overrides)
    return base


def _persona_violation_kw(**overrides):
    base = dict(
        violation_id="v-1", tenant_id="t-1",
        operation="authority_exceeded", reason="Used AUTONOMOUS",
        detected_at=TS,
    )
    base.update(overrides)
    return base


def _persona_snapshot_kw(**overrides):
    base = dict(
        snapshot_id="snap-1", tenant_id="t-1",
        total_personas=2, total_policies=1, total_bindings=3,
        total_decisions=5, total_violations=0, captured_at=TS,
    )
    base.update(overrides)
    return base


def _persona_closure_report_kw(**overrides):
    base = dict(
        report_id="rpt-1", tenant_id="t-1",
        total_personas=2, total_policies=1, total_bindings=3,
        total_decisions=5, total_violations=0, created_at=TS,
    )
    base.update(overrides)
    return base


# ===================================================================
# Enum Membership Tests
# ===================================================================


class TestPersonaStatusEnum:
    def test_members(self):
        assert set(PersonaStatus) == {PersonaStatus.ACTIVE, PersonaStatus.SUSPENDED, PersonaStatus.RETIRED}

    @pytest.mark.parametrize("member,value", [
        (PersonaStatus.ACTIVE, "active"),
        (PersonaStatus.SUSPENDED, "suspended"),
        (PersonaStatus.RETIRED, "retired"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(PersonaStatus) == 3

    def test_from_value(self):
        assert PersonaStatus("active") is PersonaStatus.ACTIVE


class TestPersonaKindEnum:
    def test_members(self):
        expected = {PersonaKind.EXECUTIVE, PersonaKind.OPERATOR, PersonaKind.INVESTIGATOR,
                    PersonaKind.CUSTOMER_SUPPORT, PersonaKind.REGULATORY, PersonaKind.TECHNICAL}
        assert set(PersonaKind) == expected

    @pytest.mark.parametrize("member,value", [
        (PersonaKind.EXECUTIVE, "executive"),
        (PersonaKind.OPERATOR, "operator"),
        (PersonaKind.INVESTIGATOR, "investigator"),
        (PersonaKind.CUSTOMER_SUPPORT, "customer_support"),
        (PersonaKind.REGULATORY, "regulatory"),
        (PersonaKind.TECHNICAL, "technical"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(PersonaKind) == 6


class TestInteractionStyleEnum:
    def test_members(self):
        expected = {InteractionStyle.CONCISE, InteractionStyle.DETAILED,
                    InteractionStyle.FORMAL, InteractionStyle.CONVERSATIONAL}
        assert set(InteractionStyle) == expected

    @pytest.mark.parametrize("member,value", [
        (InteractionStyle.CONCISE, "concise"),
        (InteractionStyle.DETAILED, "detailed"),
        (InteractionStyle.FORMAL, "formal"),
        (InteractionStyle.CONVERSATIONAL, "conversational"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(InteractionStyle) == 4


class TestEscalationStyleEnum:
    def test_members(self):
        expected = {EscalationStyle.IMMEDIATE, EscalationStyle.THRESHOLD,
                    EscalationStyle.DEFERRED, EscalationStyle.MANUAL}
        assert set(EscalationStyle) == expected

    @pytest.mark.parametrize("member,value", [
        (EscalationStyle.IMMEDIATE, "immediate"),
        (EscalationStyle.THRESHOLD, "threshold"),
        (EscalationStyle.DEFERRED, "deferred"),
        (EscalationStyle.MANUAL, "manual"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(EscalationStyle) == 4


class TestAuthorityModeEnum:
    def test_members(self):
        expected = {AuthorityMode.AUTONOMOUS, AuthorityMode.GUIDED,
                    AuthorityMode.RESTRICTED, AuthorityMode.READ_ONLY}
        assert set(AuthorityMode) == expected

    @pytest.mark.parametrize("member,value", [
        (AuthorityMode.AUTONOMOUS, "autonomous"),
        (AuthorityMode.GUIDED, "guided"),
        (AuthorityMode.RESTRICTED, "restricted"),
        (AuthorityMode.READ_ONLY, "read_only"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(AuthorityMode) == 4


class TestPersonaRiskLevelEnum:
    def test_members(self):
        expected = {PersonaRiskLevel.LOW, PersonaRiskLevel.MEDIUM,
                    PersonaRiskLevel.HIGH, PersonaRiskLevel.CRITICAL}
        assert set(PersonaRiskLevel) == expected

    @pytest.mark.parametrize("member,value", [
        (PersonaRiskLevel.LOW, "low"),
        (PersonaRiskLevel.MEDIUM, "medium"),
        (PersonaRiskLevel.HIGH, "high"),
        (PersonaRiskLevel.CRITICAL, "critical"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(PersonaRiskLevel) == 4


# ===================================================================
# PersonaProfile Tests
# ===================================================================


class TestPersonaProfile:
    def test_valid_construction(self):
        p = PersonaProfile(**_persona_profile_kw())
        assert p.persona_id == "p-1"
        assert p.tenant_id == "t-1"
        assert p.display_name == "Ops Agent"
        assert p.kind is PersonaKind.OPERATOR
        assert p.status is PersonaStatus.ACTIVE
        assert p.interaction_style is InteractionStyle.CONCISE
        assert p.authority_mode is AuthorityMode.GUIDED
        assert p.created_at == TS

    def test_slots(self):
        p = PersonaProfile(**_persona_profile_kw())
        assert hasattr(p, "__slots__")

    def test_frozen(self):
        p = PersonaProfile(**_persona_profile_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "persona_id", "new")

    def test_frozen_tenant(self):
        p = PersonaProfile(**_persona_profile_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "tenant_id", "new")

    def test_frozen_display_name(self):
        p = PersonaProfile(**_persona_profile_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "display_name", "new")

    def test_frozen_kind(self):
        p = PersonaProfile(**_persona_profile_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "kind", PersonaKind.EXECUTIVE)

    def test_frozen_status(self):
        p = PersonaProfile(**_persona_profile_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "status", PersonaStatus.RETIRED)

    def test_frozen_metadata(self):
        p = PersonaProfile(**_persona_profile_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "metadata", {})

    def test_metadata_frozen_mapping(self):
        p = PersonaProfile(**_persona_profile_kw(metadata={"key": "val"}))
        assert isinstance(p.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            p.metadata["new"] = "x"

    def test_metadata_default_empty(self):
        p = PersonaProfile(**_persona_profile_kw())
        assert len(p.metadata) == 0

    def test_metadata_nested_frozen(self):
        p = PersonaProfile(**_persona_profile_kw(metadata={"a": {"b": 1}}))
        assert isinstance(p.metadata["a"], MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("persona_id", ""),
        ("persona_id", "   "),
        ("tenant_id", ""),
        ("tenant_id", "   "),
        ("display_name", ""),
        ("display_name", "   "),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            PersonaProfile(**_persona_profile_kw(**{field: val}))

    @pytest.mark.parametrize("field,val", [
        ("persona_id", 123),
        ("tenant_id", None),
        ("display_name", 0),
    ])
    def test_non_string_rejected(self, field, val):
        with pytest.raises((ValueError, TypeError)):
            PersonaProfile(**_persona_profile_kw(**{field: val}))

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            PersonaProfile(**_persona_profile_kw(kind="operator"))

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            PersonaProfile(**_persona_profile_kw(status="active"))

    def test_invalid_interaction_style_rejected(self):
        with pytest.raises(ValueError):
            PersonaProfile(**_persona_profile_kw(interaction_style="concise"))

    def test_invalid_authority_mode_rejected(self):
        with pytest.raises(ValueError):
            PersonaProfile(**_persona_profile_kw(authority_mode="guided"))

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            PersonaProfile(**_persona_profile_kw(created_at="not-a-date"))

    def test_to_dict(self):
        p = PersonaProfile(**_persona_profile_kw())
        d = p.to_dict()
        assert d["persona_id"] == "p-1"
        assert d["kind"] is PersonaKind.OPERATOR  # preserves enum
        assert d["status"] is PersonaStatus.ACTIVE

    def test_to_dict_metadata_thawed(self):
        p = PersonaProfile(**_persona_profile_kw(metadata={"x": 1}))
        d = p.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_json_dict(self):
        p = PersonaProfile(**_persona_profile_kw())
        d = p.to_json_dict()
        assert d["kind"] == "operator"  # enum -> value
        assert d["status"] == "active"

    def test_to_json(self):
        p = PersonaProfile(**_persona_profile_kw())
        j = p.to_json()
        parsed = json.loads(j)
        assert parsed["kind"] == "operator"

    @pytest.mark.parametrize("kind", list(PersonaKind))
    def test_all_kinds_accepted(self, kind):
        p = PersonaProfile(**_persona_profile_kw(kind=kind))
        assert p.kind is kind

    @pytest.mark.parametrize("status", list(PersonaStatus))
    def test_all_statuses_accepted(self, status):
        p = PersonaProfile(**_persona_profile_kw(status=status))
        assert p.status is status

    @pytest.mark.parametrize("style", list(InteractionStyle))
    def test_all_interaction_styles_accepted(self, style):
        p = PersonaProfile(**_persona_profile_kw(interaction_style=style))
        assert p.interaction_style is style

    @pytest.mark.parametrize("mode", list(AuthorityMode))
    def test_all_authority_modes_accepted(self, mode):
        p = PersonaProfile(**_persona_profile_kw(authority_mode=mode))
        assert p.authority_mode is mode

    def test_different_persona_ids_distinct(self):
        p1 = PersonaProfile(**_persona_profile_kw(persona_id="p-1"))
        p2 = PersonaProfile(**_persona_profile_kw(persona_id="p-2"))
        assert p1.persona_id != p2.persona_id

    def test_iso_date_without_tz(self):
        p = PersonaProfile(**_persona_profile_kw(created_at="2025-06-01"))
        assert p.created_at == "2025-06-01"

    def test_iso_date_with_z(self):
        p = PersonaProfile(**_persona_profile_kw(created_at="2025-06-01T00:00:00Z"))
        assert p.created_at == "2025-06-01T00:00:00Z"


# ===================================================================
# RoleBehaviorPolicy Tests
# ===================================================================


class TestRoleBehaviorPolicy:
    def test_valid_construction(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw())
        assert r.policy_id == "pol-1"
        assert r.tenant_id == "t-1"
        assert r.persona_ref == "p-1"
        assert r.escalation_style is EscalationStyle.THRESHOLD
        assert r.risk_level is PersonaRiskLevel.LOW
        assert r.max_autonomy_depth == 3

    def test_slots(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw())
        assert hasattr(r, "__slots__")

    def test_frozen(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "policy_id", "new")

    def test_frozen_escalation_style(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "escalation_style", EscalationStyle.IMMEDIATE)

    def test_frozen_risk_level(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "risk_level", PersonaRiskLevel.HIGH)

    def test_metadata_frozen(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw(metadata={"a": 1}))
        assert isinstance(r.metadata, MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("policy_id", ""),
        ("tenant_id", ""),
        ("persona_ref", ""),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            RoleBehaviorPolicy(**_role_behavior_policy_kw(**{field: val}))

    def test_invalid_escalation_style_rejected(self):
        with pytest.raises(ValueError):
            RoleBehaviorPolicy(**_role_behavior_policy_kw(escalation_style="threshold"))

    def test_invalid_risk_level_rejected(self):
        with pytest.raises(ValueError):
            RoleBehaviorPolicy(**_role_behavior_policy_kw(risk_level="low"))

    def test_negative_max_autonomy_depth_rejected(self):
        with pytest.raises(ValueError):
            RoleBehaviorPolicy(**_role_behavior_policy_kw(max_autonomy_depth=-1))

    def test_zero_max_autonomy_depth_accepted(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw(max_autonomy_depth=0))
        assert r.max_autonomy_depth == 0

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            RoleBehaviorPolicy(**_role_behavior_policy_kw(created_at="bad"))

    def test_to_dict(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw())
        d = r.to_dict()
        assert d["escalation_style"] is EscalationStyle.THRESHOLD

    def test_to_json_dict(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw())
        d = r.to_json_dict()
        assert d["escalation_style"] == "threshold"
        assert d["risk_level"] == "low"

    def test_to_json(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw())
        j = r.to_json()
        parsed = json.loads(j)
        assert parsed["max_autonomy_depth"] == 3

    @pytest.mark.parametrize("es", list(EscalationStyle))
    def test_all_escalation_styles(self, es):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw(escalation_style=es))
        assert r.escalation_style is es

    @pytest.mark.parametrize("rl", list(PersonaRiskLevel))
    def test_all_risk_levels(self, rl):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw(risk_level=rl))
        assert r.risk_level is rl

    def test_bool_max_autonomy_depth_rejected(self):
        with pytest.raises(ValueError):
            RoleBehaviorPolicy(**_role_behavior_policy_kw(max_autonomy_depth=True))

    def test_float_max_autonomy_depth_rejected(self):
        with pytest.raises(ValueError):
            RoleBehaviorPolicy(**_role_behavior_policy_kw(max_autonomy_depth=1.5))


# ===================================================================
# StyleDirective Tests
# ===================================================================


class TestStyleDirective:
    def test_valid_construction(self):
        s = StyleDirective(**_style_directive_kw())
        assert s.directive_id == "sd-1"
        assert s.scope == "global"
        assert s.instruction == "Be brief"
        assert s.priority == 0

    def test_slots(self):
        s = StyleDirective(**_style_directive_kw())
        assert hasattr(s, "__slots__")

    def test_frozen(self):
        s = StyleDirective(**_style_directive_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "directive_id", "new")

    def test_frozen_instruction(self):
        s = StyleDirective(**_style_directive_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "instruction", "new")

    def test_frozen_priority(self):
        s = StyleDirective(**_style_directive_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "priority", 99)

    def test_metadata_frozen(self):
        s = StyleDirective(**_style_directive_kw(metadata={"k": "v"}))
        assert isinstance(s.metadata, MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("directive_id", ""),
        ("tenant_id", ""),
        ("persona_ref", ""),
        ("scope", ""),
        ("instruction", ""),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            StyleDirective(**_style_directive_kw(**{field: val}))

    def test_negative_priority_rejected(self):
        with pytest.raises(ValueError):
            StyleDirective(**_style_directive_kw(priority=-1))

    def test_zero_priority_accepted(self):
        s = StyleDirective(**_style_directive_kw(priority=0))
        assert s.priority == 0

    def test_high_priority_accepted(self):
        s = StyleDirective(**_style_directive_kw(priority=100))
        assert s.priority == 100

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            StyleDirective(**_style_directive_kw(created_at="bad"))

    def test_to_dict(self):
        s = StyleDirective(**_style_directive_kw())
        d = s.to_dict()
        assert d["directive_id"] == "sd-1"

    def test_to_json_dict(self):
        s = StyleDirective(**_style_directive_kw())
        d = s.to_json_dict()
        assert isinstance(d["priority"], int)

    def test_to_json(self):
        s = StyleDirective(**_style_directive_kw())
        j = s.to_json()
        parsed = json.loads(j)
        assert parsed["scope"] == "global"

    def test_bool_priority_rejected(self):
        with pytest.raises(ValueError):
            StyleDirective(**_style_directive_kw(priority=True))


# ===================================================================
# EscalationDirective Tests
# ===================================================================


class TestEscalationDirective:
    def test_valid_construction(self):
        e = EscalationDirective(**_escalation_directive_kw())
        assert e.directive_id == "ed-1"
        assert e.trigger_condition == "high_risk"
        assert e.target_role == "supervisor"

    def test_slots(self):
        e = EscalationDirective(**_escalation_directive_kw())
        assert hasattr(e, "__slots__")

    def test_frozen(self):
        e = EscalationDirective(**_escalation_directive_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(e, "directive_id", "new")

    def test_frozen_trigger(self):
        e = EscalationDirective(**_escalation_directive_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(e, "trigger_condition", "new")

    def test_frozen_target(self):
        e = EscalationDirective(**_escalation_directive_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(e, "target_role", "new")

    def test_metadata_frozen(self):
        e = EscalationDirective(**_escalation_directive_kw(metadata={"a": 1}))
        assert isinstance(e.metadata, MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("directive_id", ""),
        ("tenant_id", ""),
        ("persona_ref", ""),
        ("trigger_condition", ""),
        ("target_role", ""),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            EscalationDirective(**_escalation_directive_kw(**{field: val}))

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            EscalationDirective(**_escalation_directive_kw(created_at="nope"))

    def test_to_dict(self):
        e = EscalationDirective(**_escalation_directive_kw())
        d = e.to_dict()
        assert d["target_role"] == "supervisor"

    def test_to_json(self):
        e = EscalationDirective(**_escalation_directive_kw())
        j = e.to_json()
        parsed = json.loads(j)
        assert parsed["trigger_condition"] == "high_risk"


# ===================================================================
# PersonaSessionBinding Tests
# ===================================================================


class TestPersonaSessionBinding:
    def test_valid_construction(self):
        b = PersonaSessionBinding(**_persona_session_binding_kw())
        assert b.binding_id == "b-1"
        assert b.session_ref == "sess-1"

    def test_slots(self):
        b = PersonaSessionBinding(**_persona_session_binding_kw())
        assert hasattr(b, "__slots__")

    def test_frozen(self):
        b = PersonaSessionBinding(**_persona_session_binding_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(b, "binding_id", "new")

    def test_frozen_session_ref(self):
        b = PersonaSessionBinding(**_persona_session_binding_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(b, "session_ref", "new")

    def test_frozen_persona_ref(self):
        b = PersonaSessionBinding(**_persona_session_binding_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(b, "persona_ref", "new")

    def test_metadata_frozen(self):
        b = PersonaSessionBinding(**_persona_session_binding_kw(metadata={"x": "y"}))
        assert isinstance(b.metadata, MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("binding_id", ""),
        ("tenant_id", ""),
        ("persona_ref", ""),
        ("session_ref", ""),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            PersonaSessionBinding(**_persona_session_binding_kw(**{field: val}))

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            PersonaSessionBinding(**_persona_session_binding_kw(bound_at="bad"))

    def test_to_dict(self):
        b = PersonaSessionBinding(**_persona_session_binding_kw())
        d = b.to_dict()
        assert d["session_ref"] == "sess-1"

    def test_to_json(self):
        b = PersonaSessionBinding(**_persona_session_binding_kw())
        j = b.to_json()
        parsed = json.loads(j)
        assert parsed["binding_id"] == "b-1"


# ===================================================================
# PersonaDecision Tests
# ===================================================================


class TestPersonaDecision:
    def test_valid_construction(self):
        d = PersonaDecision(**_persona_decision_kw())
        assert d.decision_id == "d-1"
        assert d.action_taken == "approve_order"
        assert d.style_applied is InteractionStyle.CONCISE
        assert d.authority_used is AuthorityMode.GUIDED

    def test_slots(self):
        d = PersonaDecision(**_persona_decision_kw())
        assert hasattr(d, "__slots__")

    def test_frozen(self):
        d = PersonaDecision(**_persona_decision_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "new")

    def test_frozen_action(self):
        d = PersonaDecision(**_persona_decision_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "action_taken", "new")

    def test_frozen_style(self):
        d = PersonaDecision(**_persona_decision_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "style_applied", InteractionStyle.FORMAL)

    def test_frozen_authority(self):
        d = PersonaDecision(**_persona_decision_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "authority_used", AuthorityMode.AUTONOMOUS)

    def test_metadata_frozen(self):
        d = PersonaDecision(**_persona_decision_kw(metadata={"k": "v"}))
        assert isinstance(d.metadata, MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("decision_id", ""),
        ("tenant_id", ""),
        ("persona_ref", ""),
        ("session_ref", ""),
        ("action_taken", ""),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            PersonaDecision(**_persona_decision_kw(**{field: val}))

    def test_invalid_style_rejected(self):
        with pytest.raises(ValueError):
            PersonaDecision(**_persona_decision_kw(style_applied="concise"))

    def test_invalid_authority_rejected(self):
        with pytest.raises(ValueError):
            PersonaDecision(**_persona_decision_kw(authority_used="guided"))

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            PersonaDecision(**_persona_decision_kw(decided_at="nope"))

    def test_to_dict_preserves_enums(self):
        d = PersonaDecision(**_persona_decision_kw())
        dd = d.to_dict()
        assert dd["style_applied"] is InteractionStyle.CONCISE
        assert dd["authority_used"] is AuthorityMode.GUIDED

    def test_to_json_dict_converts_enums(self):
        d = PersonaDecision(**_persona_decision_kw())
        dd = d.to_json_dict()
        assert dd["style_applied"] == "concise"
        assert dd["authority_used"] == "guided"

    def test_to_json(self):
        d = PersonaDecision(**_persona_decision_kw())
        j = d.to_json()
        parsed = json.loads(j)
        assert parsed["action_taken"] == "approve_order"

    @pytest.mark.parametrize("style", list(InteractionStyle))
    def test_all_styles_accepted(self, style):
        d = PersonaDecision(**_persona_decision_kw(style_applied=style))
        assert d.style_applied is style

    @pytest.mark.parametrize("auth", list(AuthorityMode))
    def test_all_authority_modes_accepted(self, auth):
        d = PersonaDecision(**_persona_decision_kw(authority_used=auth))
        assert d.authority_used is auth


# ===================================================================
# PersonaAssessment Tests
# ===================================================================


class TestPersonaAssessment:
    def test_valid_construction(self):
        a = PersonaAssessment(**_persona_assessment_kw())
        assert a.assessment_id == "a-1"
        assert a.total_personas == 5
        assert a.compliance_rate == 0.95

    def test_slots(self):
        a = PersonaAssessment(**_persona_assessment_kw())
        assert hasattr(a, "__slots__")

    def test_frozen(self):
        a = PersonaAssessment(**_persona_assessment_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "new")

    def test_frozen_compliance(self):
        a = PersonaAssessment(**_persona_assessment_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "compliance_rate", 0.5)

    def test_metadata_frozen(self):
        a = PersonaAssessment(**_persona_assessment_kw(metadata={"k": 1}))
        assert isinstance(a.metadata, MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("assessment_id", ""),
        ("tenant_id", ""),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            PersonaAssessment(**_persona_assessment_kw(**{field: val}))

    @pytest.mark.parametrize("field", ["total_personas", "total_bindings", "total_decisions"])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            PersonaAssessment(**_persona_assessment_kw(**{field: -1}))

    def test_compliance_rate_zero_accepted(self):
        a = PersonaAssessment(**_persona_assessment_kw(compliance_rate=0.0))
        assert a.compliance_rate == 0.0

    def test_compliance_rate_one_accepted(self):
        a = PersonaAssessment(**_persona_assessment_kw(compliance_rate=1.0))
        assert a.compliance_rate == 1.0

    def test_compliance_rate_above_one_rejected(self):
        with pytest.raises(ValueError):
            PersonaAssessment(**_persona_assessment_kw(compliance_rate=1.1))

    def test_compliance_rate_below_zero_rejected(self):
        with pytest.raises(ValueError):
            PersonaAssessment(**_persona_assessment_kw(compliance_rate=-0.1))

    def test_compliance_rate_nan_rejected(self):
        with pytest.raises(ValueError):
            PersonaAssessment(**_persona_assessment_kw(compliance_rate=float("nan")))

    def test_compliance_rate_inf_rejected(self):
        with pytest.raises(ValueError):
            PersonaAssessment(**_persona_assessment_kw(compliance_rate=float("inf")))

    def test_compliance_rate_bool_rejected(self):
        with pytest.raises(ValueError):
            PersonaAssessment(**_persona_assessment_kw(compliance_rate=True))

    def test_compliance_rate_is_unit_float(self):
        a = PersonaAssessment(**_persona_assessment_kw(compliance_rate=0.5))
        assert 0.0 <= a.compliance_rate <= 1.0

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            PersonaAssessment(**_persona_assessment_kw(assessed_at="nope"))

    def test_to_dict(self):
        a = PersonaAssessment(**_persona_assessment_kw())
        d = a.to_dict()
        assert d["compliance_rate"] == 0.95

    def test_to_json(self):
        a = PersonaAssessment(**_persona_assessment_kw())
        j = a.to_json()
        parsed = json.loads(j)
        assert parsed["total_personas"] == 5

    @pytest.mark.parametrize("field", ["total_personas", "total_bindings", "total_decisions"])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            PersonaAssessment(**_persona_assessment_kw(**{field: True}))

    def test_int_compliance_rate_accepted(self):
        # int 0 and 1 should be accepted as valid unit floats
        a = PersonaAssessment(**_persona_assessment_kw(compliance_rate=0))
        assert a.compliance_rate == 0.0
        a2 = PersonaAssessment(**_persona_assessment_kw(compliance_rate=1))
        assert a2.compliance_rate == 1.0


# ===================================================================
# PersonaViolation Tests
# ===================================================================


class TestPersonaViolation:
    def test_valid_construction(self):
        v = PersonaViolation(**_persona_violation_kw())
        assert v.violation_id == "v-1"
        assert v.operation == "authority_exceeded"
        assert v.reason == "Used AUTONOMOUS"

    def test_slots(self):
        v = PersonaViolation(**_persona_violation_kw())
        assert hasattr(v, "__slots__")

    def test_frozen(self):
        v = PersonaViolation(**_persona_violation_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "new")

    def test_frozen_operation(self):
        v = PersonaViolation(**_persona_violation_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "operation", "new")

    def test_frozen_reason(self):
        v = PersonaViolation(**_persona_violation_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "reason", "new")

    def test_metadata_frozen(self):
        v = PersonaViolation(**_persona_violation_kw(metadata={"k": "v"}))
        assert isinstance(v.metadata, MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("violation_id", ""),
        ("tenant_id", ""),
        ("operation", ""),
        ("reason", ""),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            PersonaViolation(**_persona_violation_kw(**{field: val}))

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            PersonaViolation(**_persona_violation_kw(detected_at="bad"))

    def test_to_dict(self):
        v = PersonaViolation(**_persona_violation_kw())
        d = v.to_dict()
        assert d["operation"] == "authority_exceeded"

    def test_to_json(self):
        v = PersonaViolation(**_persona_violation_kw())
        j = v.to_json()
        parsed = json.loads(j)
        assert parsed["violation_id"] == "v-1"


# ===================================================================
# PersonaSnapshot Tests
# ===================================================================


class TestPersonaSnapshot:
    def test_valid_construction(self):
        s = PersonaSnapshot(**_persona_snapshot_kw())
        assert s.snapshot_id == "snap-1"
        assert s.total_personas == 2
        assert s.total_violations == 0

    def test_slots(self):
        s = PersonaSnapshot(**_persona_snapshot_kw())
        assert hasattr(s, "__slots__")

    def test_frozen(self):
        s = PersonaSnapshot(**_persona_snapshot_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "new")

    def test_frozen_total_personas(self):
        s = PersonaSnapshot(**_persona_snapshot_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "total_personas", 99)

    def test_metadata_frozen(self):
        s = PersonaSnapshot(**_persona_snapshot_kw(metadata={"a": "b"}))
        assert isinstance(s.metadata, MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("snapshot_id", ""),
        ("tenant_id", ""),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            PersonaSnapshot(**_persona_snapshot_kw(**{field: val}))

    @pytest.mark.parametrize("field", [
        "total_personas", "total_policies", "total_bindings",
        "total_decisions", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            PersonaSnapshot(**_persona_snapshot_kw(**{field: -1}))

    @pytest.mark.parametrize("field", [
        "total_personas", "total_policies", "total_bindings",
        "total_decisions", "total_violations",
    ])
    def test_zero_accepted(self, field):
        s = PersonaSnapshot(**_persona_snapshot_kw(**{field: 0}))
        assert getattr(s, field) == 0

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            PersonaSnapshot(**_persona_snapshot_kw(captured_at="nope"))

    def test_to_dict(self):
        s = PersonaSnapshot(**_persona_snapshot_kw())
        d = s.to_dict()
        assert d["total_policies"] == 1

    def test_to_json(self):
        s = PersonaSnapshot(**_persona_snapshot_kw())
        j = s.to_json()
        parsed = json.loads(j)
        assert parsed["total_bindings"] == 3

    @pytest.mark.parametrize("field", [
        "total_personas", "total_policies", "total_bindings",
        "total_decisions", "total_violations",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            PersonaSnapshot(**_persona_snapshot_kw(**{field: True}))


# ===================================================================
# PersonaClosureReport Tests
# ===================================================================


class TestPersonaClosureReport:
    def test_valid_construction(self):
        r = PersonaClosureReport(**_persona_closure_report_kw())
        assert r.report_id == "rpt-1"
        assert r.total_personas == 2

    def test_slots(self):
        r = PersonaClosureReport(**_persona_closure_report_kw())
        assert hasattr(r, "__slots__")

    def test_frozen(self):
        r = PersonaClosureReport(**_persona_closure_report_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "report_id", "new")

    def test_frozen_total_violations(self):
        r = PersonaClosureReport(**_persona_closure_report_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "total_violations", 99)

    def test_metadata_frozen(self):
        r = PersonaClosureReport(**_persona_closure_report_kw(metadata={"x": 1}))
        assert isinstance(r.metadata, MappingProxyType)

    @pytest.mark.parametrize("field,val", [
        ("report_id", ""),
        ("tenant_id", ""),
    ])
    def test_empty_string_rejected(self, field, val):
        with pytest.raises(ValueError):
            PersonaClosureReport(**_persona_closure_report_kw(**{field: val}))

    @pytest.mark.parametrize("field", [
        "total_personas", "total_policies", "total_bindings",
        "total_decisions", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            PersonaClosureReport(**_persona_closure_report_kw(**{field: -1}))

    @pytest.mark.parametrize("field", [
        "total_personas", "total_policies", "total_bindings",
        "total_decisions", "total_violations",
    ])
    def test_zero_accepted(self, field):
        r = PersonaClosureReport(**_persona_closure_report_kw(**{field: 0}))
        assert getattr(r, field) == 0

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            PersonaClosureReport(**_persona_closure_report_kw(created_at="bad"))

    def test_to_dict(self):
        r = PersonaClosureReport(**_persona_closure_report_kw())
        d = r.to_dict()
        assert d["report_id"] == "rpt-1"

    def test_to_json(self):
        r = PersonaClosureReport(**_persona_closure_report_kw())
        j = r.to_json()
        parsed = json.loads(j)
        assert parsed["total_decisions"] == 5

    @pytest.mark.parametrize("field", [
        "total_personas", "total_policies", "total_bindings",
        "total_decisions", "total_violations",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            PersonaClosureReport(**_persona_closure_report_kw(**{field: True}))


# ===================================================================
# Cross-cutting serialization round-trip tests
# ===================================================================


class TestSerializationRoundTrips:
    """Ensure to_dict() and to_json_dict() produce consistent results."""

    def test_persona_profile_round_trip(self):
        p = PersonaProfile(**_persona_profile_kw(metadata={"a": 1}))
        d = p.to_dict()
        jd = p.to_json_dict()
        assert d["persona_id"] == jd["persona_id"]
        assert d["metadata"]["a"] == jd["metadata"]["a"]

    def test_role_behavior_policy_round_trip(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw(metadata={"x": "y"}))
        d = r.to_dict()
        jd = r.to_json_dict()
        assert d["policy_id"] == jd["policy_id"]

    def test_style_directive_round_trip(self):
        s = StyleDirective(**_style_directive_kw())
        d = s.to_dict()
        jd = s.to_json_dict()
        assert d["instruction"] == jd["instruction"]

    def test_escalation_directive_round_trip(self):
        e = EscalationDirective(**_escalation_directive_kw())
        d = e.to_dict()
        jd = e.to_json_dict()
        assert d["trigger_condition"] == jd["trigger_condition"]

    def test_binding_round_trip(self):
        b = PersonaSessionBinding(**_persona_session_binding_kw())
        d = b.to_dict()
        jd = b.to_json_dict()
        assert d["session_ref"] == jd["session_ref"]

    def test_decision_round_trip(self):
        dec = PersonaDecision(**_persona_decision_kw())
        d = dec.to_dict()
        jd = dec.to_json_dict()
        # to_dict preserves enum, to_json_dict converts
        assert d["style_applied"] is InteractionStyle.CONCISE
        assert jd["style_applied"] == "concise"

    def test_assessment_round_trip(self):
        a = PersonaAssessment(**_persona_assessment_kw())
        d = a.to_dict()
        jd = a.to_json_dict()
        assert d["compliance_rate"] == jd["compliance_rate"]

    def test_violation_round_trip(self):
        v = PersonaViolation(**_persona_violation_kw())
        d = v.to_dict()
        jd = v.to_json_dict()
        assert d["reason"] == jd["reason"]

    def test_snapshot_round_trip(self):
        s = PersonaSnapshot(**_persona_snapshot_kw())
        d = s.to_dict()
        jd = s.to_json_dict()
        assert d["total_personas"] == jd["total_personas"]

    def test_closure_report_round_trip(self):
        r = PersonaClosureReport(**_persona_closure_report_kw())
        d = r.to_dict()
        jd = r.to_json_dict()
        assert d["report_id"] == jd["report_id"]

    def test_to_json_is_valid_json_for_all(self):
        """All contract types should produce valid JSON via to_json()."""
        instances = [
            PersonaProfile(**_persona_profile_kw()),
            RoleBehaviorPolicy(**_role_behavior_policy_kw()),
            StyleDirective(**_style_directive_kw()),
            EscalationDirective(**_escalation_directive_kw()),
            PersonaSessionBinding(**_persona_session_binding_kw()),
            PersonaDecision(**_persona_decision_kw()),
            PersonaAssessment(**_persona_assessment_kw()),
            PersonaViolation(**_persona_violation_kw()),
            PersonaSnapshot(**_persona_snapshot_kw()),
            PersonaClosureReport(**_persona_closure_report_kw()),
        ]
        for inst in instances:
            j = inst.to_json()
            parsed = json.loads(j)
            assert isinstance(parsed, dict)


# ===================================================================
# Edge-case / boundary tests
# ===================================================================


class TestEdgeCases:
    def test_persona_profile_whitespace_only_persona_id(self):
        with pytest.raises(ValueError):
            PersonaProfile(**_persona_profile_kw(persona_id="   "))

    def test_persona_profile_tab_only_tenant(self):
        with pytest.raises(ValueError):
            PersonaProfile(**_persona_profile_kw(tenant_id="\t"))

    def test_persona_profile_newline_name(self):
        with pytest.raises(ValueError):
            PersonaProfile(**_persona_profile_kw(display_name="\n"))

    def test_assessment_compliance_rate_half(self):
        a = PersonaAssessment(**_persona_assessment_kw(compliance_rate=0.5))
        assert a.compliance_rate == 0.5

    def test_assessment_compliance_rate_epsilon(self):
        a = PersonaAssessment(**_persona_assessment_kw(compliance_rate=0.001))
        assert a.compliance_rate == pytest.approx(0.001)

    def test_snapshot_large_counts(self):
        s = PersonaSnapshot(**_persona_snapshot_kw(
            total_personas=999999, total_policies=888888,
            total_bindings=777777, total_decisions=666666,
            total_violations=555555,
        ))
        assert s.total_personas == 999999

    def test_closure_large_counts(self):
        r = PersonaClosureReport(**_persona_closure_report_kw(
            total_personas=100000, total_violations=50000,
        ))
        assert r.total_violations == 50000

    def test_metadata_empty_dict_accepted(self):
        p = PersonaProfile(**_persona_profile_kw(metadata={}))
        assert len(p.metadata) == 0

    def test_metadata_complex_nested(self):
        m = {"level1": {"level2": {"level3": "deep"}}}
        p = PersonaProfile(**_persona_profile_kw(metadata=m))
        assert p.metadata["level1"]["level2"]["level3"] == "deep"

    def test_persona_profile_special_chars_in_name(self):
        p = PersonaProfile(**_persona_profile_kw(display_name="Agent #1 (v2.0)"))
        assert p.display_name == "Agent #1 (v2.0)"

    def test_persona_profile_unicode_name(self):
        p = PersonaProfile(**_persona_profile_kw(display_name="Agente Operativo"))
        assert p.display_name == "Agente Operativo"

    def test_policy_max_autonomy_depth_large(self):
        r = RoleBehaviorPolicy(**_role_behavior_policy_kw(max_autonomy_depth=1000))
        assert r.max_autonomy_depth == 1000

    def test_style_directive_long_instruction(self):
        s = StyleDirective(**_style_directive_kw(instruction="x" * 10000))
        assert len(s.instruction) == 10000

    def test_escalation_directive_long_trigger(self):
        e = EscalationDirective(**_escalation_directive_kw(trigger_condition="y" * 5000))
        assert len(e.trigger_condition) == 5000

    def test_violation_long_reason(self):
        v = PersonaViolation(**_persona_violation_kw(reason="z" * 10000))
        assert len(v.reason) == 10000

    def test_binding_different_sessions(self):
        b1 = PersonaSessionBinding(**_persona_session_binding_kw(binding_id="b-1", session_ref="s-1"))
        b2 = PersonaSessionBinding(**_persona_session_binding_kw(binding_id="b-2", session_ref="s-2"))
        assert b1.session_ref != b2.session_ref

    def test_decision_different_actions(self):
        d1 = PersonaDecision(**_persona_decision_kw(decision_id="d-1", action_taken="approve"))
        d2 = PersonaDecision(**_persona_decision_kw(decision_id="d-2", action_taken="deny"))
        assert d1.action_taken != d2.action_taken

    def test_all_contracts_have_to_dict(self):
        instances = [
            PersonaProfile(**_persona_profile_kw()),
            RoleBehaviorPolicy(**_role_behavior_policy_kw()),
            StyleDirective(**_style_directive_kw()),
            EscalationDirective(**_escalation_directive_kw()),
            PersonaSessionBinding(**_persona_session_binding_kw()),
            PersonaDecision(**_persona_decision_kw()),
            PersonaAssessment(**_persona_assessment_kw()),
            PersonaViolation(**_persona_violation_kw()),
            PersonaSnapshot(**_persona_snapshot_kw()),
            PersonaClosureReport(**_persona_closure_report_kw()),
        ]
        for inst in instances:
            assert hasattr(inst, "to_dict")
            assert callable(inst.to_dict)

    def test_all_contracts_have_to_json_dict(self):
        instances = [
            PersonaProfile(**_persona_profile_kw()),
            RoleBehaviorPolicy(**_role_behavior_policy_kw()),
            StyleDirective(**_style_directive_kw()),
            EscalationDirective(**_escalation_directive_kw()),
            PersonaSessionBinding(**_persona_session_binding_kw()),
            PersonaDecision(**_persona_decision_kw()),
            PersonaAssessment(**_persona_assessment_kw()),
            PersonaViolation(**_persona_violation_kw()),
            PersonaSnapshot(**_persona_snapshot_kw()),
            PersonaClosureReport(**_persona_closure_report_kw()),
        ]
        for inst in instances:
            assert hasattr(inst, "to_json_dict")

    def test_all_contracts_have_to_json(self):
        instances = [
            PersonaProfile(**_persona_profile_kw()),
            RoleBehaviorPolicy(**_role_behavior_policy_kw()),
            StyleDirective(**_style_directive_kw()),
            EscalationDirective(**_escalation_directive_kw()),
            PersonaSessionBinding(**_persona_session_binding_kw()),
            PersonaDecision(**_persona_decision_kw()),
            PersonaAssessment(**_persona_assessment_kw()),
            PersonaViolation(**_persona_violation_kw()),
            PersonaSnapshot(**_persona_snapshot_kw()),
            PersonaClosureReport(**_persona_closure_report_kw()),
        ]
        for inst in instances:
            assert hasattr(inst, "to_json")

    def test_all_contracts_are_frozen(self):
        instances = [
            ("persona_id", PersonaProfile(**_persona_profile_kw())),
            ("policy_id", RoleBehaviorPolicy(**_role_behavior_policy_kw())),
            ("directive_id", StyleDirective(**_style_directive_kw())),
            ("directive_id", EscalationDirective(**_escalation_directive_kw())),
            ("binding_id", PersonaSessionBinding(**_persona_session_binding_kw())),
            ("decision_id", PersonaDecision(**_persona_decision_kw())),
            ("assessment_id", PersonaAssessment(**_persona_assessment_kw())),
            ("violation_id", PersonaViolation(**_persona_violation_kw())),
            ("snapshot_id", PersonaSnapshot(**_persona_snapshot_kw())),
            ("report_id", PersonaClosureReport(**_persona_closure_report_kw())),
        ]
        for field, inst in instances:
            with pytest.raises((FrozenInstanceError, AttributeError)):
                setattr(inst, field, "hacked")

    def test_all_contracts_have_slots(self):
        instances = [
            PersonaProfile(**_persona_profile_kw()),
            RoleBehaviorPolicy(**_role_behavior_policy_kw()),
            StyleDirective(**_style_directive_kw()),
            EscalationDirective(**_escalation_directive_kw()),
            PersonaSessionBinding(**_persona_session_binding_kw()),
            PersonaDecision(**_persona_decision_kw()),
            PersonaAssessment(**_persona_assessment_kw()),
            PersonaViolation(**_persona_violation_kw()),
            PersonaSnapshot(**_persona_snapshot_kw()),
            PersonaClosureReport(**_persona_closure_report_kw()),
        ]
        for inst in instances:
            assert hasattr(inst, "__slots__")

    def test_datetime_iso_formats(self):
        """Various valid ISO 8601 formats should be accepted."""
        formats = [
            "2025-06-01",
            "2025-06-01T00:00:00",
            "2025-06-01T00:00:00+00:00",
            "2025-06-01T12:30:00Z",
            "2025-06-01T12:30:00-05:00",
        ]
        for fmt in formats:
            p = PersonaProfile(**_persona_profile_kw(created_at=fmt))
            assert p.created_at == fmt
