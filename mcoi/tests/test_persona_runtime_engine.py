"""Comprehensive tests for the PersonaRuntimeEngine.

Tests cover: construction, persona lifecycle, role policies, style directives,
escalation directives, session bindings, behavior resolution, decisions,
assessments, snapshots, violation detection, state_hash, and replay determinism.
"""

from __future__ import annotations

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
from mcoi_runtime.core.persona_runtime import PersonaRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def clock():
    return FixedClock("2026-01-01T00:00:00+00:00")


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def engine(es, clock):
    return PersonaRuntimeEngine(es, clock=clock)


def _register_default_persona(engine, persona_id="p-1", tenant_id="t-1",
                               kind=PersonaKind.OPERATOR,
                               interaction_style=InteractionStyle.CONCISE,
                               authority_mode=AuthorityMode.GUIDED):
    return engine.register_persona(
        persona_id=persona_id, tenant_id=tenant_id,
        display_name=f"Agent {persona_id}", kind=kind,
        interaction_style=interaction_style,
        authority_mode=authority_mode,
    )


# ===================================================================
# Construction Tests
# ===================================================================


class TestEngineConstruction:
    def test_valid_construction(self, es, clock):
        eng = PersonaRuntimeEngine(es, clock=clock)
        assert eng.persona_count == 0

    def test_construction_without_clock(self, es):
        eng = PersonaRuntimeEngine(es)
        assert eng.persona_count == 0

    def test_invalid_event_spine_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError):
            PersonaRuntimeEngine("not_an_es")

    def test_invalid_event_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            PersonaRuntimeEngine(None)

    def test_initial_counts_zero(self, engine):
        assert engine.persona_count == 0
        assert engine.policy_count == 0
        assert engine.style_directive_count == 0
        assert engine.escalation_directive_count == 0
        assert engine.binding_count == 0
        assert engine.decision_count == 0
        assert engine.violation_count == 0


# ===================================================================
# Persona Registration Tests
# ===================================================================


class TestPersonaRegistration:
    def test_register_persona(self, engine):
        p = _register_default_persona(engine)
        assert isinstance(p, PersonaProfile)
        assert p.persona_id == "p-1"
        assert p.tenant_id == "t-1"
        assert p.kind is PersonaKind.OPERATOR
        assert p.status is PersonaStatus.ACTIVE

    def test_register_increments_count(self, engine):
        _register_default_persona(engine, "p-1")
        assert engine.persona_count == 1
        _register_default_persona(engine, "p-2")
        assert engine.persona_count == 2

    def test_duplicate_persona_id_rejected(self, engine):
        _register_default_persona(engine, "p-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _register_default_persona(engine, "p-1")

    def test_register_emits_event(self, engine, es):
        before = es.event_count
        _register_default_persona(engine, "p-1")
        assert es.event_count > before

    def test_register_all_kinds(self, engine):
        for i, kind in enumerate(PersonaKind):
            p = _register_default_persona(engine, f"p-{i}", kind=kind)
            assert p.kind is kind

    def test_register_all_interaction_styles(self, engine):
        for i, style in enumerate(InteractionStyle):
            p = _register_default_persona(engine, f"p-{i}", interaction_style=style)
            assert p.interaction_style is style

    def test_register_all_authority_modes(self, engine):
        for i, mode in enumerate(AuthorityMode):
            p = _register_default_persona(engine, f"p-{i}", authority_mode=mode)
            assert p.authority_mode is mode

    def test_register_sets_active_status(self, engine):
        p = _register_default_persona(engine)
        assert p.status is PersonaStatus.ACTIVE

    def test_register_uses_clock_time(self, engine, clock):
        p = _register_default_persona(engine)
        assert p.created_at == "2026-01-01T00:00:00+00:00"

    def test_get_persona(self, engine):
        _register_default_persona(engine, "p-1")
        p = engine.get_persona("p-1")
        assert p.persona_id == "p-1"

    def test_get_unknown_persona_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_persona("nonexistent")

    def test_personas_for_tenant(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        _register_default_persona(engine, "p-2", tenant_id="t-1")
        _register_default_persona(engine, "p-3", tenant_id="t-2")
        result = engine.personas_for_tenant("t-1")
        assert len(result) == 2
        assert isinstance(result, tuple)

    def test_personas_for_tenant_empty(self, engine):
        result = engine.personas_for_tenant("no-such-tenant")
        assert result == ()

    def test_personas_for_tenant_immutable(self, engine):
        _register_default_persona(engine, "p-1")
        result = engine.personas_for_tenant("t-1")
        assert isinstance(result, tuple)


# ===================================================================
# Persona Lifecycle Tests
# ===================================================================


class TestPersonaLifecycle:
    def test_suspend_active_persona(self, engine):
        _register_default_persona(engine, "p-1")
        p = engine.suspend_persona("p-1")
        assert p.status is PersonaStatus.SUSPENDED

    def test_suspend_emits_event(self, engine, es):
        _register_default_persona(engine, "p-1")
        before = es.event_count
        engine.suspend_persona("p-1")
        assert es.event_count > before

    def test_retire_active_persona(self, engine):
        _register_default_persona(engine, "p-1")
        p = engine.retire_persona("p-1")
        assert p.status is PersonaStatus.RETIRED

    def test_retire_suspended_persona(self, engine):
        _register_default_persona(engine, "p-1")
        engine.suspend_persona("p-1")
        p = engine.retire_persona("p-1")
        assert p.status is PersonaStatus.RETIRED

    def test_retire_emits_event(self, engine, es):
        _register_default_persona(engine, "p-1")
        before = es.event_count
        engine.retire_persona("p-1")
        assert es.event_count > before

    def test_activate_suspended_persona(self, engine):
        _register_default_persona(engine, "p-1")
        engine.suspend_persona("p-1")
        p = engine.activate_persona("p-1")
        assert p.status is PersonaStatus.ACTIVE

    def test_activate_emits_event(self, engine, es):
        _register_default_persona(engine, "p-1")
        engine.suspend_persona("p-1")
        before = es.event_count
        engine.activate_persona("p-1")
        assert es.event_count > before

    def test_retired_blocks_suspend(self, engine):
        _register_default_persona(engine, "p-1")
        engine.retire_persona("p-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.suspend_persona("p-1")

    def test_retired_blocks_activate(self, engine):
        _register_default_persona(engine, "p-1")
        engine.retire_persona("p-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.activate_persona("p-1")

    def test_retired_blocks_retire_again(self, engine):
        _register_default_persona(engine, "p-1")
        engine.retire_persona("p-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.retire_persona("p-1")

    def test_suspend_already_suspended_rejected(self, engine):
        _register_default_persona(engine, "p-1")
        engine.suspend_persona("p-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot suspend"):
            engine.suspend_persona("p-1")

    def test_activate_already_active_rejected(self, engine):
        _register_default_persona(engine, "p-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot activate"):
            engine.activate_persona("p-1")

    def test_suspend_unknown_persona_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.suspend_persona("nonexistent")

    def test_lifecycle_round_trip(self, engine):
        _register_default_persona(engine, "p-1")
        assert engine.get_persona("p-1").status is PersonaStatus.ACTIVE
        engine.suspend_persona("p-1")
        assert engine.get_persona("p-1").status is PersonaStatus.SUSPENDED
        engine.activate_persona("p-1")
        assert engine.get_persona("p-1").status is PersonaStatus.ACTIVE
        engine.retire_persona("p-1")
        assert engine.get_persona("p-1").status is PersonaStatus.RETIRED

    def test_multiple_suspend_activate_cycles(self, engine):
        _register_default_persona(engine, "p-1")
        for _ in range(5):
            engine.suspend_persona("p-1")
            engine.activate_persona("p-1")
        assert engine.get_persona("p-1").status is PersonaStatus.ACTIVE


# ===================================================================
# Role Behavior Policy Tests
# ===================================================================


class TestRoleBehaviorPolicy:
    def test_register_policy(self, engine):
        _register_default_persona(engine, "p-1")
        pol = engine.register_role_policy("pol-1", "t-1", "p-1")
        assert isinstance(pol, RoleBehaviorPolicy)
        assert pol.policy_id == "pol-1"

    def test_register_policy_increments_count(self, engine):
        _register_default_persona(engine, "p-1")
        engine.register_role_policy("pol-1", "t-1", "p-1")
        assert engine.policy_count == 1

    def test_duplicate_policy_rejected(self, engine):
        _register_default_persona(engine, "p-1")
        engine.register_role_policy("pol-1", "t-1", "p-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_role_policy("pol-1", "t-1", "p-1")

    def test_policy_requires_existing_persona(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.register_role_policy("pol-1", "t-1", "nonexistent")

    def test_policy_emits_event(self, engine, es):
        _register_default_persona(engine, "p-1")
        before = es.event_count
        engine.register_role_policy("pol-1", "t-1", "p-1")
        assert es.event_count > before

    def test_get_policy(self, engine):
        _register_default_persona(engine, "p-1")
        engine.register_role_policy("pol-1", "t-1", "p-1")
        pol = engine.get_policy("pol-1")
        assert pol.policy_id == "pol-1"

    def test_get_unknown_policy_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_policy("nonexistent")

    def test_policies_for_persona(self, engine):
        _register_default_persona(engine, "p-1")
        engine.register_role_policy("pol-1", "t-1", "p-1")
        engine.register_role_policy("pol-2", "t-1", "p-1")
        result = engine.policies_for_persona("p-1")
        assert len(result) == 2

    def test_policies_for_persona_empty(self, engine):
        result = engine.policies_for_persona("nonexistent")
        assert result == ()

    @pytest.mark.parametrize("es_style", list(EscalationStyle))
    def test_all_escalation_styles(self, engine, es_style):
        _register_default_persona(engine, "p-1")
        pol = engine.register_role_policy("pol-1", "t-1", "p-1", escalation_style=es_style)
        assert pol.escalation_style is es_style

    @pytest.mark.parametrize("rl", list(PersonaRiskLevel))
    def test_all_risk_levels(self, engine, rl):
        _register_default_persona(engine, "p-1")
        pol = engine.register_role_policy("pol-1", "t-1", "p-1", risk_level=rl)
        assert pol.risk_level is rl

    def test_custom_max_autonomy_depth(self, engine):
        _register_default_persona(engine, "p-1")
        pol = engine.register_role_policy("pol-1", "t-1", "p-1", max_autonomy_depth=10)
        assert pol.max_autonomy_depth == 10

    def test_default_values(self, engine):
        _register_default_persona(engine, "p-1")
        pol = engine.register_role_policy("pol-1", "t-1", "p-1")
        assert pol.escalation_style is EscalationStyle.THRESHOLD
        assert pol.risk_level is PersonaRiskLevel.LOW
        assert pol.max_autonomy_depth == 3


# ===================================================================
# Style Directive Tests
# ===================================================================


class TestStyleDirectives:
    def test_add_style_directive(self, engine):
        _register_default_persona(engine, "p-1")
        sd = engine.add_style_directive("sd-1", "t-1", "p-1", "global", "Be brief")
        assert isinstance(sd, StyleDirective)
        assert sd.directive_id == "sd-1"

    def test_add_increments_count(self, engine):
        _register_default_persona(engine, "p-1")
        engine.add_style_directive("sd-1", "t-1", "p-1", "global", "Be brief")
        assert engine.style_directive_count == 1

    def test_duplicate_rejected(self, engine):
        _register_default_persona(engine, "p-1")
        engine.add_style_directive("sd-1", "t-1", "p-1", "global", "Be brief")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.add_style_directive("sd-1", "t-1", "p-1", "global", "Be brief")

    def test_requires_existing_persona(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.add_style_directive("sd-1", "t-1", "nonexistent", "global", "x")

    def test_emits_event(self, engine, es):
        _register_default_persona(engine, "p-1")
        before = es.event_count
        engine.add_style_directive("sd-1", "t-1", "p-1", "global", "Be brief")
        assert es.event_count > before

    def test_custom_priority(self, engine):
        _register_default_persona(engine, "p-1")
        sd = engine.add_style_directive("sd-1", "t-1", "p-1", "global", "Be brief", priority=10)
        assert sd.priority == 10

    def test_uses_clock_time(self, engine, clock):
        _register_default_persona(engine, "p-1")
        sd = engine.add_style_directive("sd-1", "t-1", "p-1", "global", "Be brief")
        assert sd.created_at == "2026-01-01T00:00:00+00:00"

    def test_multiple_directives_for_persona(self, engine):
        _register_default_persona(engine, "p-1")
        engine.add_style_directive("sd-1", "t-1", "p-1", "global", "Be brief")
        engine.add_style_directive("sd-2", "t-1", "p-1", "session", "Be polite")
        assert engine.style_directive_count == 2


# ===================================================================
# Escalation Directive Tests
# ===================================================================


class TestEscalationDirectives:
    def test_add_escalation_directive(self, engine):
        _register_default_persona(engine, "p-1")
        ed = engine.add_escalation_directive("ed-1", "t-1", "p-1", "high_risk", "supervisor")
        assert isinstance(ed, EscalationDirective)
        assert ed.directive_id == "ed-1"

    def test_add_increments_count(self, engine):
        _register_default_persona(engine, "p-1")
        engine.add_escalation_directive("ed-1", "t-1", "p-1", "high_risk", "supervisor")
        assert engine.escalation_directive_count == 1

    def test_duplicate_rejected(self, engine):
        _register_default_persona(engine, "p-1")
        engine.add_escalation_directive("ed-1", "t-1", "p-1", "high_risk", "supervisor")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.add_escalation_directive("ed-1", "t-1", "p-1", "high_risk", "supervisor")

    def test_requires_existing_persona(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.add_escalation_directive("ed-1", "t-1", "nonexistent", "high_risk", "supervisor")

    def test_emits_event(self, engine, es):
        _register_default_persona(engine, "p-1")
        before = es.event_count
        engine.add_escalation_directive("ed-1", "t-1", "p-1", "high_risk", "supervisor")
        assert es.event_count > before

    def test_uses_clock_time(self, engine, clock):
        _register_default_persona(engine, "p-1")
        ed = engine.add_escalation_directive("ed-1", "t-1", "p-1", "high_risk", "supervisor")
        assert ed.created_at == "2026-01-01T00:00:00+00:00"

    def test_multiple_directives_for_persona(self, engine):
        _register_default_persona(engine, "p-1")
        engine.add_escalation_directive("ed-1", "t-1", "p-1", "high_risk", "supervisor")
        engine.add_escalation_directive("ed-2", "t-1", "p-1", "low_budget", "finance")
        assert engine.escalation_directive_count == 2


# ===================================================================
# Session Binding Tests
# ===================================================================


class TestSessionBindings:
    def test_bind_persona_to_session(self, engine):
        _register_default_persona(engine, "p-1")
        b = engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        assert isinstance(b, PersonaSessionBinding)
        assert b.binding_id == "b-1"

    def test_bind_increments_count(self, engine):
        _register_default_persona(engine, "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        assert engine.binding_count == 1

    def test_duplicate_binding_rejected(self, engine):
        _register_default_persona(engine, "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-2")

    def test_bind_emits_event(self, engine, es):
        _register_default_persona(engine, "p-1")
        before = es.event_count
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        assert es.event_count > before

    def test_bind_requires_active_persona(self, engine):
        _register_default_persona(engine, "p-1")
        engine.suspend_persona("p-1")
        with pytest.raises(RuntimeCoreInvariantError, match="not active"):
            engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")

    def test_bind_inactive_persona_message_is_bounded(self, engine):
        _register_default_persona(engine, "persona-secret")
        engine.suspend_persona("persona-secret")
        with pytest.raises(RuntimeCoreInvariantError, match="not active") as exc_info:
            engine.bind_persona_to_session("bind-secret", "t-1", "persona-secret", "sess-secret")
        message = str(exc_info.value)
        assert "not active" in message
        assert "persona-secret" not in message
        assert PersonaStatus.SUSPENDED.value not in message

    def test_bind_requires_existing_persona(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.bind_persona_to_session("b-1", "t-1", "nonexistent", "sess-1")

    def test_cross_tenant_binding_creates_violation(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cross-tenant"):
            engine.bind_persona_to_session("b-1", "t-2", "p-1", "sess-1")
        assert engine.violation_count == 1

    def test_cross_tenant_binding_messages_are_bounded(self, engine):
        _register_default_persona(engine, "persona-secret", tenant_id="tenant-secret")
        with pytest.raises(RuntimeCoreInvariantError, match="Cross-tenant") as exc_info:
            engine.bind_persona_to_session("binding-secret", "tenant-other", "persona-secret", "sess-secret")
        violation = next(iter(engine._violations.values()))
        message = str(exc_info.value)
        assert message == "Cross-tenant persona binding"
        assert "persona-secret" not in message
        assert violation.reason == "Cross-tenant persona binding"

    def test_cross_tenant_violation_is_idempotent(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.bind_persona_to_session("b-1", "t-2", "p-1", "sess-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.bind_persona_to_session("b-2", "t-2", "p-1", "sess-2")
        # Second call with different binding_id creates a different violation key
        assert engine.violation_count >= 1

    def test_bind_retired_persona_raises(self, engine):
        _register_default_persona(engine, "p-1")
        engine.retire_persona("p-1")
        # Cross-tenant check happens first; same tenant will fail on ACTIVE check
        with pytest.raises(RuntimeCoreInvariantError, match="not active"):
            engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")

    def test_bind_uses_clock_time(self, engine, clock):
        _register_default_persona(engine, "p-1")
        b = engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        assert b.bound_at == "2026-01-01T00:00:00+00:00"

    def test_multiple_bindings_per_persona(self, engine):
        _register_default_persona(engine, "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        engine.bind_persona_to_session("b-2", "t-1", "p-1", "sess-2")
        assert engine.binding_count == 2


# ===================================================================
# Behavior Resolution Tests
# ===================================================================


class TestBehaviorResolution:
    def test_resolve_no_binding_defaults(self, engine):
        behavior = engine.resolve_behavior("t-1", "sess-1")
        assert behavior["persona_kind"] == PersonaKind.OPERATOR.value
        assert behavior["interaction_style"] == InteractionStyle.CONCISE.value
        assert behavior["authority_mode"] == AuthorityMode.GUIDED.value
        assert behavior["escalation_style"] == EscalationStyle.MANUAL.value
        assert behavior["risk_level"] == PersonaRiskLevel.LOW.value

    def test_resolve_with_binding_no_policy(self, engine):
        _register_default_persona(engine, "p-1", kind=PersonaKind.EXECUTIVE,
                                  interaction_style=InteractionStyle.FORMAL,
                                  authority_mode=AuthorityMode.AUTONOMOUS)
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        behavior = engine.resolve_behavior("t-1", "sess-1")
        assert behavior["persona_kind"] == PersonaKind.EXECUTIVE.value
        assert behavior["interaction_style"] == InteractionStyle.FORMAL.value
        assert behavior["authority_mode"] == AuthorityMode.AUTONOMOUS.value
        assert behavior["escalation_style"] == EscalationStyle.MANUAL.value

    def test_resolve_with_binding_and_policy(self, engine):
        _register_default_persona(engine, "p-1", kind=PersonaKind.OPERATOR)
        engine.register_role_policy("pol-1", "t-1", "p-1",
                                    escalation_style=EscalationStyle.IMMEDIATE,
                                    risk_level=PersonaRiskLevel.HIGH)
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        behavior = engine.resolve_behavior("t-1", "sess-1")
        assert behavior["escalation_style"] == EscalationStyle.IMMEDIATE.value
        assert behavior["risk_level"] == PersonaRiskLevel.HIGH.value

    # Golden scenario 1: Operator session
    def test_golden_operator_session(self, engine):
        _register_default_persona(engine, "p-op", kind=PersonaKind.OPERATOR)
        engine.bind_persona_to_session("b-1", "t-1", "p-op", "op-sess")
        behavior = engine.resolve_behavior("t-1", "op-sess")
        assert behavior["persona_kind"] == "operator"
        assert behavior["interaction_style"] == "concise"

    # Golden scenario 2: Executive session -> CONCISE + IMMEDIATE
    def test_golden_executive_session(self, engine):
        _register_default_persona(engine, "p-ex", kind=PersonaKind.EXECUTIVE,
                                  interaction_style=InteractionStyle.CONCISE,
                                  authority_mode=AuthorityMode.AUTONOMOUS)
        engine.register_role_policy("pol-ex", "t-1", "p-ex",
                                    escalation_style=EscalationStyle.IMMEDIATE,
                                    risk_level=PersonaRiskLevel.CRITICAL)
        engine.bind_persona_to_session("b-ex", "t-1", "p-ex", "ex-sess")
        behavior = engine.resolve_behavior("t-1", "ex-sess")
        assert behavior["persona_kind"] == "executive"
        assert behavior["interaction_style"] == "concise"
        assert behavior["escalation_style"] == "immediate"

    def test_resolve_escalation_style_no_binding(self, engine):
        result = engine.resolve_escalation_style("t-1", "sess-1")
        assert result is EscalationStyle.MANUAL

    def test_resolve_escalation_style_with_policy(self, engine):
        _register_default_persona(engine, "p-1")
        engine.register_role_policy("pol-1", "t-1", "p-1",
                                    escalation_style=EscalationStyle.IMMEDIATE)
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        result = engine.resolve_escalation_style("t-1", "sess-1")
        assert result is EscalationStyle.IMMEDIATE

    def test_resolve_escalation_style_no_policy(self, engine):
        _register_default_persona(engine, "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        result = engine.resolve_escalation_style("t-1", "sess-1")
        assert result is EscalationStyle.MANUAL

    def test_resolve_behavior_returns_dict(self, engine):
        result = engine.resolve_behavior("t-1", "sess-1")
        assert isinstance(result, dict)
        expected_keys = {"persona_kind", "interaction_style", "authority_mode",
                         "escalation_style", "risk_level"}
        assert set(result.keys()) == expected_keys

    def test_resolve_behavior_different_sessions(self, engine):
        _register_default_persona(engine, "p-1", kind=PersonaKind.OPERATOR)
        _register_default_persona(engine, "p-2", kind=PersonaKind.EXECUTIVE,
                                  interaction_style=InteractionStyle.FORMAL)
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        engine.bind_persona_to_session("b-2", "t-1", "p-2", "sess-2")
        b1 = engine.resolve_behavior("t-1", "sess-1")
        b2 = engine.resolve_behavior("t-1", "sess-2")
        assert b1["persona_kind"] == "operator"
        assert b2["persona_kind"] == "executive"


# ===================================================================
# Decision Recording Tests
# ===================================================================


class TestDecisionRecording:
    def test_record_decision(self, engine):
        d = engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        assert isinstance(d, PersonaDecision)
        assert d.decision_id == "d-1"

    def test_decision_increments_count(self, engine):
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        assert engine.decision_count == 1

    def test_duplicate_decision_rejected(self, engine):
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_persona_decision(
                "d-1", "t-1", "p-1", "sess-1", "deny",
                InteractionStyle.CONCISE, AuthorityMode.GUIDED,
            )

    def test_decision_emits_event(self, engine, es):
        before = es.event_count
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        assert es.event_count > before

    def test_decision_uses_clock_time(self, engine, clock):
        d = engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        assert d.decided_at == "2026-01-01T00:00:00+00:00"

    @pytest.mark.parametrize("style", list(InteractionStyle))
    def test_all_styles_in_decisions(self, engine, style):
        d = engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            style, AuthorityMode.GUIDED,
        )
        assert d.style_applied is style

    @pytest.mark.parametrize("auth", list(AuthorityMode))
    def test_all_authority_modes_in_decisions(self, engine, auth):
        d = engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, auth,
        )
        assert d.authority_used is auth

    def test_multiple_decisions(self, engine):
        for i in range(10):
            engine.record_persona_decision(
                f"d-{i}", "t-1", "p-1", "sess-1", f"action-{i}",
                InteractionStyle.CONCISE, AuthorityMode.GUIDED,
            )
        assert engine.decision_count == 10


# ===================================================================
# Assessment Tests
# ===================================================================


class TestPersonaAssessment:
    def test_assessment_empty_tenant(self, engine):
        a = engine.persona_assessment("a-1", "t-1")
        assert isinstance(a, PersonaAssessment)
        assert a.total_personas == 0
        assert a.total_bindings == 0
        assert a.total_decisions == 0
        assert a.compliance_rate == 1.0

    def test_assessment_with_data(self, engine):
        _register_default_persona(engine, "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        a = engine.persona_assessment("a-1", "t-1")
        assert a.total_personas == 1
        assert a.total_bindings == 1
        assert a.total_decisions == 1
        assert a.compliance_rate == 1.0

    def test_assessment_emits_event(self, engine, es):
        before = es.event_count
        engine.persona_assessment("a-1", "t-1")
        assert es.event_count > before

    def test_assessment_compliance_rate_is_unit_float(self, engine):
        a = engine.persona_assessment("a-1", "t-1")
        assert 0.0 <= a.compliance_rate <= 1.0

    # Golden scenario 5: authority exceeded reduces compliance
    def test_authority_exceeded_reduces_compliance(self, engine):
        _register_default_persona(engine, "p-1", authority_mode=AuthorityMode.READ_ONLY)
        engine.register_role_policy("pol-1", "t-1", "p-1")
        # Record decision using AUTONOMOUS on READ_ONLY persona
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "force_action",
            InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS,
        )
        a = engine.persona_assessment("a-1", "t-1")
        assert a.compliance_rate < 1.0

    def test_no_policy_means_within_authority(self, engine):
        _register_default_persona(engine, "p-1", authority_mode=AuthorityMode.READ_ONLY)
        # No policy registered; AUTONOMOUS decision should be "within authority"
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "action",
            InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS,
        )
        a = engine.persona_assessment("a-1", "t-1")
        assert a.compliance_rate == 1.0

    def test_assessment_multi_tenant_isolation(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        _register_default_persona(engine, "p-2", tenant_id="t-2")
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        a1 = engine.persona_assessment("a-1", "t-1")
        a2 = engine.persona_assessment("a-2", "t-2")
        assert a1.total_decisions == 1
        assert a2.total_decisions == 0

    def test_assessment_mixed_compliance(self, engine):
        _register_default_persona(engine, "p-1", authority_mode=AuthorityMode.RESTRICTED)
        engine.register_role_policy("pol-1", "t-1", "p-1")
        # 1 compliant decision
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "read_data",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        # 1 non-compliant decision (AUTONOMOUS on RESTRICTED)
        engine.record_persona_decision(
            "d-2", "t-1", "p-1", "sess-1", "force_write",
            InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS,
        )
        a = engine.persona_assessment("a-1", "t-1")
        assert a.compliance_rate == 0.5


# ===================================================================
# Snapshot Tests
# ===================================================================


class TestPersonaSnapshot:
    def test_snapshot_empty_tenant(self, engine):
        s = engine.persona_snapshot("snap-1", "t-1")
        assert isinstance(s, PersonaSnapshot)
        assert s.total_personas == 0
        assert s.total_policies == 0
        assert s.total_bindings == 0
        assert s.total_decisions == 0
        assert s.total_violations == 0

    def test_snapshot_with_data(self, engine):
        _register_default_persona(engine, "p-1")
        engine.register_role_policy("pol-1", "t-1", "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        s = engine.persona_snapshot("snap-1", "t-1")
        assert s.total_personas == 1
        assert s.total_policies == 1
        assert s.total_bindings == 1

    def test_snapshot_tenant_isolation(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        _register_default_persona(engine, "p-2", tenant_id="t-2")
        s1 = engine.persona_snapshot("snap-1", "t-1")
        s2 = engine.persona_snapshot("snap-2", "t-2")
        assert s1.total_personas == 1
        assert s2.total_personas == 1

    def test_snapshot_uses_clock_time(self, engine, clock):
        s = engine.persona_snapshot("snap-1", "t-1")
        assert s.captured_at == "2026-01-01T00:00:00+00:00"

    def test_snapshot_counts_violations(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.bind_persona_to_session("b-1", "t-2", "p-1", "sess-1")
        s = engine.persona_snapshot("snap-1", "t-2")
        assert s.total_violations == 1


# ===================================================================
# Violation Detection Tests
# ===================================================================


class TestViolationDetection:
    def test_detect_no_violations(self, engine):
        _register_default_persona(engine, "p-1")
        engine.register_role_policy("pol-1", "t-1", "p-1")
        violations = engine.detect_persona_violations("t-1")
        assert violations == ()

    def test_detect_persona_no_policy(self, engine):
        _register_default_persona(engine, "p-1")
        violations = engine.detect_persona_violations("t-1")
        assert len(violations) == 1
        assert violations[0].operation == "persona_no_policy"

    def test_detect_idempotent(self, engine):
        """First call returns violations, second returns empty."""
        _register_default_persona(engine, "p-1")
        v1 = engine.detect_persona_violations("t-1")
        assert len(v1) == 1
        v2 = engine.detect_persona_violations("t-1")
        assert len(v2) == 0

    def test_detect_binding_to_retired_persona(self, engine):
        _register_default_persona(engine, "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        engine.retire_persona("p-1")
        violations = engine.detect_persona_violations("t-1")
        has_retired = any(v.operation == "binding_to_retired_persona" for v in violations)
        assert has_retired

    def test_violation_reasons_are_bounded(self, engine):
        _register_default_persona(engine, "persona-no-policy")
        _register_default_persona(engine, "persona-retired")
        _register_default_persona(engine, "persona-secret", authority_mode=AuthorityMode.READ_ONLY)
        engine.bind_persona_to_session("binding-secret", "t-1", "persona-retired", "sess-retired")
        engine.retire_persona("persona-retired")
        engine.record_persona_decision(
            "decision-secret", "t-1", "persona-secret", "sess-secret", "force-action",
            InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS,
        )
        violations = engine.detect_persona_violations("t-1")
        reasons = {v.operation: v.reason for v in violations}
        assert reasons["persona_no_policy"] == "Active persona has no role behavior policy"
        assert reasons["binding_to_retired_persona"] == "Binding references retired persona"
        assert reasons["authority_exceeded"] == "Autonomous authority exceeds persona mode"

    # Golden scenario 5: authority exceeded creates violation
    def test_detect_authority_exceeded(self, engine):
        _register_default_persona(engine, "p-1", authority_mode=AuthorityMode.RESTRICTED)
        engine.register_role_policy("pol-1", "t-1", "p-1")
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "force_action",
            InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS,
        )
        violations = engine.detect_persona_violations("t-1")
        has_auth = any(v.operation == "authority_exceeded" for v in violations)
        assert has_auth

    def test_detect_authority_exceeded_read_only(self, engine):
        _register_default_persona(engine, "p-1", authority_mode=AuthorityMode.READ_ONLY)
        engine.register_role_policy("pol-1", "t-1", "p-1")
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "write_action",
            InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS,
        )
        violations = engine.detect_persona_violations("t-1")
        has_auth = any(v.operation == "authority_exceeded" for v in violations)
        assert has_auth

    def test_detect_guided_persona_autonomous_ok(self, engine):
        """GUIDED persona with AUTONOMOUS decision does NOT trigger authority_exceeded."""
        _register_default_persona(engine, "p-1", authority_mode=AuthorityMode.GUIDED)
        engine.register_role_policy("pol-1", "t-1", "p-1")
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "action",
            InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS,
        )
        violations = engine.detect_persona_violations("t-1")
        auth_violations = [v for v in violations if v.operation == "authority_exceeded"]
        assert len(auth_violations) == 0

    def test_detect_autonomous_persona_autonomous_ok(self, engine):
        """AUTONOMOUS persona with AUTONOMOUS decision does NOT trigger authority_exceeded."""
        _register_default_persona(engine, "p-1", authority_mode=AuthorityMode.AUTONOMOUS)
        engine.register_role_policy("pol-1", "t-1", "p-1")
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "action",
            InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS,
        )
        violations = engine.detect_persona_violations("t-1")
        auth_violations = [v for v in violations if v.operation == "authority_exceeded"]
        assert len(auth_violations) == 0

    def test_detect_multiple_violation_types(self, engine):
        _register_default_persona(engine, "p-1", authority_mode=AuthorityMode.READ_ONLY)
        # No policy -> persona_no_policy
        # AUTONOMOUS decision -> authority_exceeded (only with policy, so add later)
        violations = engine.detect_persona_violations("t-1")
        assert len(violations) >= 1

    def test_violation_count_increments(self, engine):
        _register_default_persona(engine, "p-1")
        assert engine.violation_count == 0
        engine.detect_persona_violations("t-1")
        assert engine.violation_count == 1

    # Golden scenario 3: customer-facing persona cannot use AUTONOMOUS
    def test_customer_facing_restricted_autonomous(self, engine):
        _register_default_persona(engine, "p-cs", kind=PersonaKind.CUSTOMER_SUPPORT,
                                  authority_mode=AuthorityMode.RESTRICTED)
        engine.register_role_policy("pol-cs", "t-1", "p-cs")
        engine.record_persona_decision(
            "d-cs", "t-1", "p-cs", "sess-1", "override",
            InteractionStyle.CONVERSATIONAL, AuthorityMode.AUTONOMOUS,
        )
        violations = engine.detect_persona_violations("t-1")
        assert any(v.operation == "authority_exceeded" for v in violations)

    # Golden scenario 4: regulatory persona forces FORMAL + READ_ONLY
    def test_regulatory_persona_read_only_violation(self, engine):
        _register_default_persona(engine, "p-reg", kind=PersonaKind.REGULATORY,
                                  interaction_style=InteractionStyle.FORMAL,
                                  authority_mode=AuthorityMode.READ_ONLY)
        engine.register_role_policy("pol-reg", "t-1", "p-reg")
        engine.record_persona_decision(
            "d-reg", "t-1", "p-reg", "sess-1", "modify_regulation",
            InteractionStyle.FORMAL, AuthorityMode.AUTONOMOUS,
        )
        violations = engine.detect_persona_violations("t-1")
        assert any(v.operation == "authority_exceeded" for v in violations)

    def test_detect_tenant_isolation(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        _register_default_persona(engine, "p-2", tenant_id="t-2")
        engine.register_role_policy("pol-2", "t-2", "p-2")
        v1 = engine.detect_persona_violations("t-1")
        v2 = engine.detect_persona_violations("t-2")
        # t-1 has no policy -> violation; t-2 has policy -> no violation
        assert len(v1) == 1
        assert len(v2) == 0


# ===================================================================
# State Hash Tests
# ===================================================================


class TestStateHash:
    def test_state_hash_is_string(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_state_hash_length(self, engine):
        h = engine.state_hash()
        assert len(h) == 64

    def test_state_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_state_hash_changes_after_register(self, engine):
        h1 = engine.state_hash()
        _register_default_persona(engine, "p-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_after_policy(self, engine):
        _register_default_persona(engine, "p-1")
        h1 = engine.state_hash()
        engine.register_role_policy("pol-1", "t-1", "p-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_after_binding(self, engine):
        _register_default_persona(engine, "p-1")
        h1 = engine.state_hash()
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_after_decision(self, engine):
        h1 = engine.state_hash()
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        h2 = engine.state_hash()
        assert h1 != h2


# ===================================================================
# Snapshot (full engine) Tests
# ===================================================================


class TestEngineSnapshot:
    def test_snapshot_returns_dict(self, engine):
        s = engine.snapshot()
        assert isinstance(s, dict)

    def test_snapshot_contains_state_hash(self, engine):
        s = engine.snapshot()
        assert "_state_hash" in s

    def test_snapshot_contains_collections(self, engine):
        s = engine.snapshot()
        assert "personas" in s
        assert "policies" in s
        assert "bindings" in s
        assert "decisions" in s
        assert "violations" in s

    def test_snapshot_after_register(self, engine):
        _register_default_persona(engine, "p-1")
        s = engine.snapshot()
        assert "p-1" in s["personas"]

    def test_snapshot_persona_has_to_dict_fields(self, engine):
        _register_default_persona(engine, "p-1")
        s = engine.snapshot()
        p_data = s["personas"]["p-1"]
        assert "persona_id" in p_data
        assert "kind" in p_data


# ===================================================================
# Replay Determinism Tests (Golden scenario 6)
# ===================================================================


class TestReplayDeterminism:
    def test_replay_same_state_hash(self):
        """Same operations with FixedClock produce same state_hash."""
        clock1 = FixedClock("2026-01-01T00:00:00+00:00")
        clock2 = FixedClock("2026-01-01T00:00:00+00:00")
        es1 = EventSpineEngine()
        es2 = EventSpineEngine()
        eng1 = PersonaRuntimeEngine(es1, clock=clock1)
        eng2 = PersonaRuntimeEngine(es2, clock=clock2)

        for eng in (eng1, eng2):
            _register_default_persona(eng, "p-1", kind=PersonaKind.OPERATOR)
            eng.register_role_policy("pol-1", "t-1", "p-1")
            eng.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
            eng.record_persona_decision(
                "d-1", "t-1", "p-1", "sess-1", "approve",
                InteractionStyle.CONCISE, AuthorityMode.GUIDED,
            )
        assert eng1.state_hash() == eng2.state_hash()

    def test_replay_different_ops_different_hash(self):
        clock1 = FixedClock("2026-01-01T00:00:00+00:00")
        clock2 = FixedClock("2026-01-01T00:00:00+00:00")
        es1 = EventSpineEngine()
        es2 = EventSpineEngine()
        eng1 = PersonaRuntimeEngine(es1, clock=clock1)
        eng2 = PersonaRuntimeEngine(es2, clock=clock2)

        _register_default_persona(eng1, "p-1")
        _register_default_persona(eng2, "p-1")
        _register_default_persona(eng2, "p-2")

        assert eng1.state_hash() != eng2.state_hash()

    def test_replay_event_count_matches(self):
        clock1 = FixedClock("2026-01-01T00:00:00+00:00")
        clock2 = FixedClock("2026-01-01T00:00:00+00:00")
        es1 = EventSpineEngine()
        es2 = EventSpineEngine()
        eng1 = PersonaRuntimeEngine(es1, clock=clock1)
        eng2 = PersonaRuntimeEngine(es2, clock=clock2)

        for eng, evt_spine in ((eng1, es1), (eng2, es2)):
            _register_default_persona(eng, "p-1")
            eng.register_role_policy("pol-1", "t-1", "p-1")
            eng.add_style_directive("sd-1", "t-1", "p-1", "global", "brief")
            eng.add_escalation_directive("ed-1", "t-1", "p-1", "risk", "sup")
            eng.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")

        assert es1.event_count == es2.event_count


# ===================================================================
# Clock Injection Tests
# ===================================================================


class TestClockInjection:
    def test_fixed_clock_used_for_persona(self, engine, clock):
        p = _register_default_persona(engine, "p-1")
        assert p.created_at == "2026-01-01T00:00:00+00:00"

    def test_clock_advance(self, es):
        clock = FixedClock("2026-01-01T00:00:00+00:00")
        eng = PersonaRuntimeEngine(es, clock=clock)
        _register_default_persona(eng, "p-1")
        clock.advance("2026-06-15T12:00:00+00:00")
        _register_default_persona(eng, "p-2")
        assert eng.get_persona("p-2").created_at == "2026-06-15T12:00:00+00:00"

    def test_wall_clock_fallback(self, es):
        eng = PersonaRuntimeEngine(es)
        p = _register_default_persona(eng, "p-1")
        # Wall clock returns some ISO string
        assert "T" in p.created_at or "-" in p.created_at


# ===================================================================
# Multi-tenant isolation
# ===================================================================


class TestMultiTenantIsolation:
    def test_personas_isolated_by_tenant(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        _register_default_persona(engine, "p-2", tenant_id="t-2")
        t1 = engine.personas_for_tenant("t-1")
        t2 = engine.personas_for_tenant("t-2")
        assert len(t1) == 1
        assert len(t2) == 1
        assert t1[0].persona_id == "p-1"
        assert t2[0].persona_id == "p-2"

    def test_snapshot_isolated_by_tenant(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        _register_default_persona(engine, "p-2", tenant_id="t-2")
        s1 = engine.persona_snapshot("s-1", "t-1")
        s2 = engine.persona_snapshot("s-2", "t-2")
        assert s1.total_personas == 1
        assert s2.total_personas == 1

    def test_assessment_isolated_by_tenant(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        a1 = engine.persona_assessment("a-1", "t-1")
        a2 = engine.persona_assessment("a-2", "t-2")
        assert a1.total_decisions == 1
        assert a2.total_decisions == 0

    def test_violations_isolated_by_tenant(self, engine):
        _register_default_persona(engine, "p-1", tenant_id="t-1")
        _register_default_persona(engine, "p-2", tenant_id="t-2")
        engine.register_role_policy("pol-2", "t-2", "p-2")
        v1 = engine.detect_persona_violations("t-1")
        v2 = engine.detect_persona_violations("t-2")
        assert len(v1) == 1  # p-1 has no policy
        assert len(v2) == 0  # p-2 has policy


# ===================================================================
# Edge Cases and Stress Tests
# ===================================================================


class TestEdgeCases:
    def test_register_many_personas(self, engine):
        for i in range(50):
            _register_default_persona(engine, f"p-{i}")
        assert engine.persona_count == 50

    def test_register_many_policies(self, engine):
        _register_default_persona(engine, "p-1")
        for i in range(20):
            engine.register_role_policy(f"pol-{i}", "t-1", "p-1")
        assert engine.policy_count == 20

    def test_register_many_bindings(self, engine):
        _register_default_persona(engine, "p-1")
        for i in range(20):
            engine.bind_persona_to_session(f"b-{i}", "t-1", "p-1", f"sess-{i}")
        assert engine.binding_count == 20

    def test_register_many_decisions(self, engine):
        for i in range(30):
            engine.record_persona_decision(
                f"d-{i}", "t-1", "p-1", "sess-1", f"action-{i}",
                InteractionStyle.CONCISE, AuthorityMode.GUIDED,
            )
        assert engine.decision_count == 30

    def test_state_hash_stable_with_same_ops(self, engine):
        _register_default_persona(engine, "p-1")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        h3 = engine.state_hash()
        assert h1 == h2 == h3

    def test_collections_returns_dict(self, engine):
        c = engine._collections()
        assert isinstance(c, dict)
        assert "personas" in c
        assert "policies" in c

    def test_snapshot_dict_structure(self, engine):
        _register_default_persona(engine, "p-1")
        engine.register_role_policy("pol-1", "t-1", "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "approve",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )
        s = engine.snapshot()
        assert "personas" in s
        assert "policies" in s
        assert "bindings" in s
        assert "decisions" in s
        assert "violations" in s
        assert "style_directives" in s
        assert "escalation_directives" in s
        assert "_state_hash" in s

    def test_resolve_behavior_after_suspend(self, engine):
        """Binding still exists after suspend, resolve should still work."""
        _register_default_persona(engine, "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        engine.suspend_persona("p-1")
        # resolve_behavior still returns persona's profile data
        behavior = engine.resolve_behavior("t-1", "sess-1")
        assert behavior["persona_kind"] == "operator"

    def test_resolve_behavior_after_retire(self, engine):
        """Binding still exists after retire, resolve should still work."""
        _register_default_persona(engine, "p-1")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")
        engine.retire_persona("p-1")
        behavior = engine.resolve_behavior("t-1", "sess-1")
        assert behavior["persona_kind"] == "operator"

    def test_full_workflow(self, engine, es):
        """Complete workflow: register, policy, bind, decide, assess, snapshot, detect."""
        p = _register_default_persona(engine, "p-1", kind=PersonaKind.OPERATOR)
        engine.register_role_policy("pol-1", "t-1", "p-1",
                                    escalation_style=EscalationStyle.IMMEDIATE,
                                    risk_level=PersonaRiskLevel.HIGH)
        engine.add_style_directive("sd-1", "t-1", "p-1", "global", "action-focused")
        engine.add_escalation_directive("ed-1", "t-1", "p-1", "overload", "manager")
        engine.bind_persona_to_session("b-1", "t-1", "p-1", "sess-1")

        behavior = engine.resolve_behavior("t-1", "sess-1")
        assert behavior["persona_kind"] == "operator"
        assert behavior["escalation_style"] == "immediate"

        engine.record_persona_decision(
            "d-1", "t-1", "p-1", "sess-1", "execute_task",
            InteractionStyle.CONCISE, AuthorityMode.GUIDED,
        )

        a = engine.persona_assessment("a-1", "t-1")
        assert a.compliance_rate == 1.0

        snap = engine.persona_snapshot("snap-1", "t-1")
        assert snap.total_personas == 1
        assert snap.total_policies == 1
        assert snap.total_bindings == 1

        violations = engine.detect_persona_violations("t-1")
        assert len(violations) == 0

        assert es.event_count > 0
