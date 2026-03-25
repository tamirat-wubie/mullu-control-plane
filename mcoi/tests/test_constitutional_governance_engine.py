"""Purpose: comprehensive tests for ConstitutionalGovernanceEngine.
Governance scope: constitutional governance runtime engine testing.
Dependencies: pytest, mcoi_runtime core + contracts.
Invariants: every public method exercised; golden scenarios validate
    cross-method interaction; duplicate/terminal guards tested.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.constitutional_governance import ConstitutionalGovernanceEngine
from mcoi_runtime.contracts.constitutional_governance import (
    ConstitutionAssessment,
    ConstitutionBundle,
    ConstitutionClosureReport,
    ConstitutionDecision,
    ConstitutionRule,
    ConstitutionRuleKind,
    ConstitutionSnapshot,
    ConstitutionStatus,
    ConstitutionViolation,
    EmergencyGovernanceRecord,
    EmergencyMode,
    GlobalOverrideRecord,
    GlobalPolicyDisposition,
    OverrideDisposition,
    PrecedenceLevel,
    PrecedenceResolution,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def engine(es):
    return ConstitutionalGovernanceEngine(es)


@pytest.fixture
def engine_with_rules(engine):
    """Engine pre-loaded with a few rules for convenience."""
    engine.register_rule("r1", "t1", "Rule One", ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
    engine.register_rule("r2", "t1", "Rule Two", ConstitutionRuleKind.ALLOW, PrecedenceLevel.TENANT)
    engine.register_rule("r3", "t1", "Rule Three", ConstitutionRuleKind.SOFT_DENY, PrecedenceLevel.PLATFORM)
    engine.register_rule("r4", "t2", "Rule Four", ConstitutionRuleKind.RESTRICT, PrecedenceLevel.RUNTIME)
    return engine


# ===================================================================
# Section 1: Constructor
# ===================================================================

class TestConstructor:
    def test_accepts_event_spine(self, es):
        eng = ConstitutionalGovernanceEngine(es)
        assert eng.rule_count == 0

    def test_rejects_non_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceEngine("not_an_engine")

    def test_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceEngine(None)

    def test_rejects_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstitutionalGovernanceEngine(42)

    def test_initial_counts_zero(self, engine):
        assert engine.rule_count == 0
        assert engine.bundle_count == 0
        assert engine.override_count == 0
        assert engine.decision_count == 0
        assert engine.violation_count == 0
        assert engine.resolution_count == 0
        assert engine.emergency_record_count == 0
        assert engine.assessment_count == 0


# ===================================================================
# Section 2: register_rule
# ===================================================================

class TestRegisterRule:
    def test_basic_registration(self, engine):
        r = engine.register_rule("r1", "t1", "Test Rule")
        assert isinstance(r, ConstitutionRule)
        assert r.rule_id == "r1"
        assert r.tenant_id == "t1"
        assert r.display_name == "Test Rule"
        assert r.status == ConstitutionStatus.ACTIVE

    def test_default_kind_hard_deny(self, engine):
        r = engine.register_rule("r1", "t1", "Test")
        assert r.kind == ConstitutionRuleKind.HARD_DENY

    def test_default_precedence_constitutional(self, engine):
        r = engine.register_rule("r1", "t1", "Test")
        assert r.precedence == PrecedenceLevel.CONSTITUTIONAL

    def test_default_target_runtime_all(self, engine):
        r = engine.register_rule("r1", "t1", "Test")
        assert r.target_runtime == "all"

    def test_default_target_action_all(self, engine):
        r = engine.register_rule("r1", "t1", "Test")
        assert r.target_action == "all"

    def test_custom_kind(self, engine):
        r = engine.register_rule("r1", "t1", "Test", kind=ConstitutionRuleKind.ALLOW)
        assert r.kind == ConstitutionRuleKind.ALLOW

    def test_custom_precedence(self, engine):
        r = engine.register_rule("r1", "t1", "Test", precedence=PrecedenceLevel.RUNTIME)
        assert r.precedence == PrecedenceLevel.RUNTIME

    def test_custom_target_runtime(self, engine):
        r = engine.register_rule("r1", "t1", "Test", target_runtime="agent-rt")
        assert r.target_runtime == "agent-rt"

    def test_custom_target_action(self, engine):
        r = engine.register_rule("r1", "t1", "Test", target_action="deploy")
        assert r.target_action == "deploy"

    def test_increments_rule_count(self, engine):
        engine.register_rule("r1", "t1", "A")
        assert engine.rule_count == 1
        engine.register_rule("r2", "t1", "B")
        assert engine.rule_count == 2

    def test_duplicate_raises(self, engine):
        engine.register_rule("r1", "t1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate rule_id"):
            engine.register_rule("r1", "t1", "B")

    def test_created_at_is_iso(self, engine):
        r = engine.register_rule("r1", "t1", "A")
        assert "T" in r.created_at

    def test_emits_event(self, es, engine):
        before = es.event_count
        engine.register_rule("r1", "t1", "A")
        assert es.event_count == before + 1

    @pytest.mark.parametrize("kind", list(ConstitutionRuleKind))
    def test_all_rule_kinds(self, engine, kind):
        r = engine.register_rule(f"r-{kind.value}", "t1", f"Rule {kind.value}", kind=kind)
        assert r.kind == kind

    @pytest.mark.parametrize("prec", list(PrecedenceLevel))
    def test_all_precedence_levels(self, engine, prec):
        r = engine.register_rule(f"r-{prec.value}", "t1", f"Rule {prec.value}", precedence=prec)
        assert r.precedence == prec

    def test_multiple_tenants(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t2", "B")
        assert engine.rule_count == 2


# ===================================================================
# Section 3: get_rule
# ===================================================================

class TestGetRule:
    def test_returns_registered_rule(self, engine):
        engine.register_rule("r1", "t1", "Test")
        r = engine.get_rule("r1")
        assert r.rule_id == "r1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown rule_id"):
            engine.get_rule("nonexistent")

    def test_returns_updated_rule_after_suspend(self, engine):
        engine.register_rule("r1", "t1", "Test")
        engine.suspend_rule("r1")
        r = engine.get_rule("r1")
        assert r.status == ConstitutionStatus.SUSPENDED

    def test_returns_updated_rule_after_retire(self, engine):
        engine.register_rule("r1", "t1", "Test")
        engine.retire_rule("r1")
        r = engine.get_rule("r1")
        assert r.status == ConstitutionStatus.RETIRED


# ===================================================================
# Section 4: suspend_rule
# ===================================================================

class TestSuspendRule:
    def test_suspends_active_rule(self, engine):
        engine.register_rule("r1", "t1", "Test")
        r = engine.suspend_rule("r1")
        assert r.status == ConstitutionStatus.SUSPENDED

    def test_suspend_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown rule_id"):
            engine.suspend_rule("nope")

    def test_suspend_retired_raises(self, engine):
        engine.register_rule("r1", "t1", "Test")
        engine.retire_rule("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.suspend_rule("r1")

    def test_suspend_already_suspended_ok(self, engine):
        engine.register_rule("r1", "t1", "Test")
        engine.suspend_rule("r1")
        r = engine.suspend_rule("r1")
        assert r.status == ConstitutionStatus.SUSPENDED

    def test_emits_event(self, es, engine):
        engine.register_rule("r1", "t1", "Test")
        before = es.event_count
        engine.suspend_rule("r1")
        assert es.event_count == before + 1

    def test_preserves_rule_id(self, engine):
        engine.register_rule("r1", "t1", "Test")
        r = engine.suspend_rule("r1")
        assert r.rule_id == "r1"

    def test_preserves_tenant_id(self, engine):
        engine.register_rule("r1", "t1", "Test")
        r = engine.suspend_rule("r1")
        assert r.tenant_id == "t1"

    def test_preserves_kind(self, engine):
        engine.register_rule("r1", "t1", "Test", kind=ConstitutionRuleKind.RESTRICT)
        r = engine.suspend_rule("r1")
        assert r.kind == ConstitutionRuleKind.RESTRICT


# ===================================================================
# Section 5: retire_rule
# ===================================================================

class TestRetireRule:
    def test_retires_active_rule(self, engine):
        engine.register_rule("r1", "t1", "Test")
        r = engine.retire_rule("r1")
        assert r.status == ConstitutionStatus.RETIRED

    def test_retires_suspended_rule(self, engine):
        engine.register_rule("r1", "t1", "Test")
        engine.suspend_rule("r1")
        r = engine.retire_rule("r1")
        assert r.status == ConstitutionStatus.RETIRED

    def test_retire_already_retired_raises(self, engine):
        engine.register_rule("r1", "t1", "Test")
        engine.retire_rule("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="already retired"):
            engine.retire_rule("r1")

    def test_retire_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown rule_id"):
            engine.retire_rule("nope")

    def test_emits_event(self, es, engine):
        engine.register_rule("r1", "t1", "Test")
        before = es.event_count
        engine.retire_rule("r1")
        assert es.event_count == before + 1

    def test_preserves_display_name(self, engine):
        engine.register_rule("r1", "t1", "My Rule")
        r = engine.retire_rule("r1")
        assert r.display_name == "My Rule"


# ===================================================================
# Section 6: rules_for_tenant / active_rules_for_tenant
# ===================================================================

class TestRulesForTenant:
    def test_empty_for_unknown_tenant(self, engine):
        assert engine.rules_for_tenant("t1") == ()

    def test_returns_all_tenant_rules(self, engine_with_rules):
        rules = engine_with_rules.rules_for_tenant("t1")
        assert len(rules) == 3

    def test_excludes_other_tenants(self, engine_with_rules):
        rules = engine_with_rules.rules_for_tenant("t2")
        assert len(rules) == 1
        assert rules[0].rule_id == "r4"

    def test_returns_tuple(self, engine_with_rules):
        rules = engine_with_rules.rules_for_tenant("t1")
        assert isinstance(rules, tuple)

    def test_includes_suspended_and_retired(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.register_rule("r3", "t1", "C")
        engine.suspend_rule("r2")
        engine.retire_rule("r3")
        rules = engine.rules_for_tenant("t1")
        assert len(rules) == 3


class TestActiveRulesForTenant:
    def test_empty_for_unknown_tenant(self, engine):
        assert engine.active_rules_for_tenant("t1") == ()

    def test_returns_only_active(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.suspend_rule("r2")
        active = engine.active_rules_for_tenant("t1")
        assert len(active) == 1
        assert active[0].rule_id == "r1"

    def test_excludes_retired(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.retire_rule("r1")
        assert engine.active_rules_for_tenant("t1") == ()

    def test_returns_tuple(self, engine):
        assert isinstance(engine.active_rules_for_tenant("t1"), tuple)

    def test_multi_tenant_isolation(self, engine_with_rules):
        t1_active = engine_with_rules.active_rules_for_tenant("t1")
        t2_active = engine_with_rules.active_rules_for_tenant("t2")
        assert len(t1_active) == 3
        assert len(t2_active) == 1


# ===================================================================
# Section 7: register_bundle
# ===================================================================

class TestRegisterBundle:
    def test_basic_registration(self, engine):
        b = engine.register_bundle("b1", "t1", "Bundle One")
        assert isinstance(b, ConstitutionBundle)
        assert b.bundle_id == "b1"
        assert b.tenant_id == "t1"
        assert b.display_name == "Bundle One"

    def test_initial_rule_count_zero(self, engine):
        b = engine.register_bundle("b1", "t1", "B")
        assert b.rule_count == 0

    def test_status_active(self, engine):
        b = engine.register_bundle("b1", "t1", "B")
        assert b.status == ConstitutionStatus.ACTIVE

    def test_increments_bundle_count(self, engine):
        engine.register_bundle("b1", "t1", "A")
        assert engine.bundle_count == 1
        engine.register_bundle("b2", "t1", "B")
        assert engine.bundle_count == 2

    def test_duplicate_raises(self, engine):
        engine.register_bundle("b1", "t1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate bundle_id"):
            engine.register_bundle("b1", "t1", "B")

    def test_emits_event(self, es, engine):
        before = es.event_count
        engine.register_bundle("b1", "t1", "A")
        assert es.event_count == before + 1

    def test_created_at_present(self, engine):
        b = engine.register_bundle("b1", "t1", "A")
        assert "T" in b.created_at


# ===================================================================
# Section 8: add_rule_to_bundle
# ===================================================================

class TestAddRuleToBundle:
    def test_adds_rule(self, engine):
        engine.register_rule("r1", "t1", "Rule")
        engine.register_bundle("b1", "t1", "Bundle")
        b = engine.add_rule_to_bundle("b1", "r1")
        assert b.rule_count == 1

    def test_increments_rule_count_each_time(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.register_bundle("b1", "t1", "Bundle")
        engine.add_rule_to_bundle("b1", "r1")
        b = engine.add_rule_to_bundle("b1", "r2")
        assert b.rule_count == 2

    def test_unknown_bundle_raises(self, engine):
        engine.register_rule("r1", "t1", "Rule")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown bundle_id"):
            engine.add_rule_to_bundle("nope", "r1")

    def test_unknown_rule_raises(self, engine):
        engine.register_bundle("b1", "t1", "Bundle")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown rule_id"):
            engine.add_rule_to_bundle("b1", "nope")

    def test_duplicate_rule_in_bundle_raises(self, engine):
        engine.register_rule("r1", "t1", "Rule")
        engine.register_bundle("b1", "t1", "Bundle")
        engine.add_rule_to_bundle("b1", "r1")
        with pytest.raises(RuntimeCoreInvariantError, match="already in bundle"):
            engine.add_rule_to_bundle("b1", "r1")

    def test_emits_event(self, es, engine):
        engine.register_rule("r1", "t1", "Rule")
        engine.register_bundle("b1", "t1", "Bundle")
        before = es.event_count
        engine.add_rule_to_bundle("b1", "r1")
        assert es.event_count == before + 1

    def test_preserves_bundle_metadata(self, engine):
        engine.register_rule("r1", "t1", "Rule")
        engine.register_bundle("b1", "t1", "My Bundle")
        b = engine.add_rule_to_bundle("b1", "r1")
        assert b.display_name == "My Bundle"
        assert b.tenant_id == "t1"


# ===================================================================
# Section 9: get_bundle / bundles_for_tenant
# ===================================================================

class TestGetBundle:
    def test_returns_registered(self, engine):
        engine.register_bundle("b1", "t1", "B")
        b = engine.get_bundle("b1")
        assert b.bundle_id == "b1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown bundle_id"):
            engine.get_bundle("nope")


class TestBundlesForTenant:
    def test_empty(self, engine):
        assert engine.bundles_for_tenant("t1") == ()

    def test_returns_correct_bundles(self, engine):
        engine.register_bundle("b1", "t1", "A")
        engine.register_bundle("b2", "t1", "B")
        engine.register_bundle("b3", "t2", "C")
        bundles = engine.bundles_for_tenant("t1")
        assert len(bundles) == 2

    def test_returns_tuple(self, engine):
        assert isinstance(engine.bundles_for_tenant("t1"), tuple)


# ===================================================================
# Section 10: evaluate_global_policy
# ===================================================================

class TestEvaluateGlobalPolicy:
    def test_no_rules_returns_allowed(self, engine):
        d = engine.evaluate_global_policy("d1", "t1", "rt", "act")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED
        assert d.matched_rule_id == "none"

    def test_hard_deny_returns_denied(self, engine):
        engine.register_rule("r1", "t1", "Block", ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED
        assert d.matched_rule_id == "r1"

    def test_soft_deny_returns_escalated(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY, PrecedenceLevel.CONSTITUTIONAL)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ESCALATED

    def test_restrict_returns_restricted(self, engine):
        engine.register_rule("r1", "t1", "Restrict", ConstitutionRuleKind.RESTRICT, PrecedenceLevel.CONSTITUTIONAL)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.RESTRICTED

    def test_allow_returns_allowed(self, engine):
        engine.register_rule("r1", "t1", "Allow", ConstitutionRuleKind.ALLOW, PrecedenceLevel.CONSTITUTIONAL)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_require_returns_allowed(self, engine):
        engine.register_rule("r1", "t1", "Require", ConstitutionRuleKind.REQUIRE, PrecedenceLevel.CONSTITUTIONAL)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_duplicate_decision_raises(self, engine):
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate decision_id"):
            engine.evaluate_global_policy("d1", "t1", "rt", "act")

    def test_increments_decision_count(self, engine):
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        assert engine.decision_count == 1

    def test_emits_event(self, es, engine):
        before = es.event_count
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        assert es.event_count == before + 1

    def test_decision_fields(self, engine):
        d = engine.evaluate_global_policy("d1", "t1", "my-rt", "my-act")
        assert d.decision_id == "d1"
        assert d.tenant_id == "t1"
        assert d.target_runtime == "my-rt"
        assert d.target_action == "my-act"
        assert d.emergency_mode == EmergencyMode.NORMAL

    def test_highest_precedence_wins(self, engine):
        engine.register_rule("r1", "t1", "Allow", ConstitutionRuleKind.ALLOW, PrecedenceLevel.TENANT)
        engine.register_rule("r2", "t1", "Deny", ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED
        assert d.matched_rule_id == "r2"

    def test_target_runtime_matching(self, engine):
        engine.register_rule("r1", "t1", "Deny", ConstitutionRuleKind.HARD_DENY, target_runtime="agent-rt")
        d = engine.evaluate_global_policy("d1", "t1", "other-rt", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_target_runtime_match_specific(self, engine):
        engine.register_rule("r1", "t1", "Deny", ConstitutionRuleKind.HARD_DENY, target_runtime="agent-rt")
        d = engine.evaluate_global_policy("d1", "t1", "agent-rt", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_target_action_matching(self, engine):
        engine.register_rule("r1", "t1", "Deny", ConstitutionRuleKind.HARD_DENY, target_action="deploy")
        d = engine.evaluate_global_policy("d1", "t1", "all", "build")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_target_action_match_specific(self, engine):
        engine.register_rule("r1", "t1", "Deny", ConstitutionRuleKind.HARD_DENY, target_action="deploy")
        d = engine.evaluate_global_policy("d1", "t1", "all", "deploy")
        assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_rule_all_matches_any_runtime(self, engine):
        engine.register_rule("r1", "t1", "Deny", ConstitutionRuleKind.HARD_DENY, target_runtime="all")
        d = engine.evaluate_global_policy("d1", "t1", "arbitrary", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_rule_all_matches_any_action(self, engine):
        engine.register_rule("r1", "t1", "Deny", ConstitutionRuleKind.HARD_DENY, target_action="all")
        d = engine.evaluate_global_policy("d1", "t1", "all", "arbitrary")
        assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_suspended_rules_ignored(self, engine):
        engine.register_rule("r1", "t1", "Deny", ConstitutionRuleKind.HARD_DENY)
        engine.suspend_rule("r1")
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_retired_rules_ignored(self, engine):
        engine.register_rule("r1", "t1", "Deny", ConstitutionRuleKind.HARD_DENY)
        engine.retire_rule("r1")
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_other_tenant_rules_ignored(self, engine):
        engine.register_rule("r1", "t2", "Deny", ConstitutionRuleKind.HARD_DENY)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED


class TestEvaluateEmergencyModes:
    def test_lockdown_returns_denied(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        d = engine.evaluate_global_policy("d1", "t1", "rt", "act")
        assert d.disposition == GlobalPolicyDisposition.DENIED
        assert d.matched_rule_id == "emergency_lockdown"
        assert d.emergency_mode == EmergencyMode.LOCKDOWN

    def test_degraded_returns_restricted(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.DEGRADED, "auth", "reason")
        d = engine.evaluate_global_policy("d1", "t1", "rt", "act")
        assert d.disposition == GlobalPolicyDisposition.RESTRICTED
        assert d.emergency_mode == EmergencyMode.DEGRADED

    def test_restricted_returns_restricted(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.RESTRICTED, "auth", "reason")
        d = engine.evaluate_global_policy("d1", "t1", "rt", "act")
        assert d.disposition == GlobalPolicyDisposition.RESTRICTED
        assert d.emergency_mode == EmergencyMode.RESTRICTED

    def test_lockdown_overrides_allow_rule(self, engine):
        engine.register_rule("r1", "t1", "Allow", ConstitutionRuleKind.ALLOW, PrecedenceLevel.CONSTITUTIONAL)
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_normal_mode_evaluates_rules(self, engine):
        engine.register_rule("r1", "t1", "Deny", ConstitutionRuleKind.HARD_DENY)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED
        assert d.emergency_mode == EmergencyMode.NORMAL

    def test_after_exit_emergency_evaluates_normally(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        engine.exit_emergency_mode("e2", "t1", "auth", "resolved")
        d = engine.evaluate_global_policy("d1", "t1", "rt", "act")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED


class TestGetDecision:
    def test_returns_decision(self, engine):
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        d = engine.get_decision("d1")
        assert d.decision_id == "d1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown decision_id"):
            engine.get_decision("nope")


class TestDecisionsForTenant:
    def test_empty(self, engine):
        assert engine.decisions_for_tenant("t1") == ()

    def test_returns_correct(self, engine):
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        engine.evaluate_global_policy("d2", "t2", "rt", "act")
        decs = engine.decisions_for_tenant("t1")
        assert len(decs) == 1
        assert decs[0].decision_id == "d1"

    def test_returns_tuple(self, engine):
        assert isinstance(engine.decisions_for_tenant("t1"), tuple)


# ===================================================================
# Section 11: resolve_precedence
# ===================================================================

class TestResolvePrecedence:
    def test_constitutional_beats_platform(self, engine):
        engine.register_rule("r1", "t1", "A", precedence=PrecedenceLevel.CONSTITUTIONAL)
        engine.register_rule("r2", "t1", "B", precedence=PrecedenceLevel.PLATFORM)
        res = engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert res.winning_rule_id == "r1"
        assert res.losing_rule_id == "r2"

    def test_platform_beats_tenant(self, engine):
        engine.register_rule("r1", "t1", "A", precedence=PrecedenceLevel.PLATFORM)
        engine.register_rule("r2", "t1", "B", precedence=PrecedenceLevel.TENANT)
        res = engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert res.winning_rule_id == "r1"
        assert res.losing_rule_id == "r2"

    def test_tenant_beats_runtime(self, engine):
        engine.register_rule("r1", "t1", "A", precedence=PrecedenceLevel.TENANT)
        engine.register_rule("r2", "t1", "B", precedence=PrecedenceLevel.RUNTIME)
        res = engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert res.winning_rule_id == "r1"

    def test_constitutional_beats_runtime(self, engine):
        engine.register_rule("r1", "t1", "A", precedence=PrecedenceLevel.CONSTITUTIONAL)
        engine.register_rule("r2", "t1", "B", precedence=PrecedenceLevel.RUNTIME)
        res = engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert res.winning_rule_id == "r1"

    def test_order_b_a_still_correct(self, engine):
        engine.register_rule("r1", "t1", "A", precedence=PrecedenceLevel.RUNTIME)
        engine.register_rule("r2", "t1", "B", precedence=PrecedenceLevel.CONSTITUTIONAL)
        res = engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert res.winning_rule_id == "r2"
        assert res.losing_rule_id == "r1"

    def test_same_precedence_first_wins(self, engine):
        engine.register_rule("r1", "t1", "A", precedence=PrecedenceLevel.TENANT)
        engine.register_rule("r2", "t1", "B", precedence=PrecedenceLevel.TENANT)
        res = engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert res.winning_rule_id == "r1"

    def test_duplicate_resolution_raises(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.resolve_precedence("p1", "t1", "r1", "r2")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate resolution_id"):
            engine.resolve_precedence("p1", "t1", "r1", "r2")

    def test_unknown_rule_a_raises(self, engine):
        engine.register_rule("r1", "t1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown rule_id"):
            engine.resolve_precedence("p1", "t1", "nope", "r1")

    def test_unknown_rule_b_raises(self, engine):
        engine.register_rule("r1", "t1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown rule_id"):
            engine.resolve_precedence("p1", "t1", "r1", "nope")

    def test_increments_resolution_count(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert engine.resolution_count == 1

    def test_emits_event(self, es, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        before = es.event_count
        engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert es.event_count == before + 1

    def test_resolution_fields(self, engine):
        engine.register_rule("r1", "t1", "A", precedence=PrecedenceLevel.CONSTITUTIONAL)
        engine.register_rule("r2", "t1", "B", precedence=PrecedenceLevel.RUNTIME)
        res = engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert res.resolution_id == "p1"
        assert res.tenant_id == "t1"
        assert res.winning_precedence == PrecedenceLevel.CONSTITUTIONAL
        assert res.losing_precedence == PrecedenceLevel.RUNTIME
        assert "T" in res.resolved_at

    def test_resolutions_for_tenant(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.resolve_precedence("p1", "t1", "r1", "r2")
        rr = engine.resolutions_for_tenant("t1")
        assert len(rr) == 1

    def test_resolutions_for_tenant_empty(self, engine):
        assert engine.resolutions_for_tenant("t1") == ()


# ===================================================================
# Section 12: apply_override
# ===================================================================

class TestApplyOverride:
    def test_override_soft_deny_applied(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        ov = engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert ov.disposition == OverrideDisposition.APPLIED

    def test_override_allow_applied(self, engine):
        engine.register_rule("r1", "t1", "Allow", ConstitutionRuleKind.ALLOW)
        ov = engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert ov.disposition == OverrideDisposition.APPLIED

    def test_override_restrict_applied(self, engine):
        engine.register_rule("r1", "t1", "Restrict", ConstitutionRuleKind.RESTRICT)
        ov = engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert ov.disposition == OverrideDisposition.APPLIED

    def test_override_require_applied(self, engine):
        engine.register_rule("r1", "t1", "Require", ConstitutionRuleKind.REQUIRE)
        ov = engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert ov.disposition == OverrideDisposition.APPLIED

    def test_override_hard_deny_denied(self, engine):
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        ov = engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert ov.disposition == OverrideDisposition.DENIED

    def test_hard_deny_override_records_violation(self, engine):
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert engine.violation_count == 1

    def test_non_hard_deny_override_suspends_rule(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        r = engine.get_rule("r1")
        assert r.status == ConstitutionStatus.SUSPENDED

    def test_hard_deny_override_does_not_suspend(self, engine):
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        r = engine.get_rule("r1")
        assert r.status == ConstitutionStatus.ACTIVE

    def test_duplicate_override_raises(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate override_id"):
            engine.apply_override("o1", "r1", "t1", "admin", "reason")

    def test_unknown_rule_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown rule_id"):
            engine.apply_override("o1", "nope", "t1", "admin", "reason")

    def test_increments_override_count(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert engine.override_count == 1

    def test_override_fields(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        ov = engine.apply_override("o1", "r1", "t1", "admin-ref", "my reason")
        assert ov.override_id == "o1"
        assert ov.rule_id == "r1"
        assert ov.tenant_id == "t1"
        assert ov.authority_ref == "admin-ref"
        assert ov.reason == "my reason"

    def test_hard_deny_override_reason_annotated(self, engine):
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        ov = engine.apply_override("o1", "r1", "t1", "admin", "custom reason")
        assert "hard_deny rule cannot be overridden" in ov.reason
        assert "custom reason" in ov.reason

    def test_emits_event(self, es, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        before = es.event_count
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert es.event_count == before + 1

    def test_get_override(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        ov = engine.get_override("o1")
        assert ov.override_id == "o1"

    def test_get_override_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown override_id"):
            engine.get_override("nope")

    def test_overrides_for_tenant(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        ovs = engine.overrides_for_tenant("t1")
        assert len(ovs) == 1

    def test_overrides_for_tenant_empty(self, engine):
        assert engine.overrides_for_tenant("t1") == ()

    def test_override_already_suspended_rule(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.suspend_rule("r1")
        ov = engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert ov.disposition == OverrideDisposition.APPLIED
        assert engine.get_rule("r1").status == ConstitutionStatus.SUSPENDED


# ===================================================================
# Section 13: Emergency modes
# ===================================================================

class TestEnterEmergencyMode:
    def test_enter_lockdown(self, engine):
        rec = engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        assert rec.mode == EmergencyMode.LOCKDOWN
        assert rec.previous_mode == EmergencyMode.NORMAL

    def test_enter_degraded(self, engine):
        rec = engine.enter_emergency_mode("e1", "t1", EmergencyMode.DEGRADED, "auth", "reason")
        assert rec.mode == EmergencyMode.DEGRADED

    def test_enter_restricted(self, engine):
        rec = engine.enter_emergency_mode("e1", "t1", EmergencyMode.RESTRICTED, "auth", "reason")
        assert rec.mode == EmergencyMode.RESTRICTED

    def test_enter_normal_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="cannot enter NORMAL mode"):
            engine.enter_emergency_mode("e1", "t1", EmergencyMode.NORMAL, "auth", "reason")

    def test_duplicate_raises(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate emergency_id"):
            engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")

    def test_updates_tenant_mode(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        assert engine.get_emergency_mode("t1") == EmergencyMode.LOCKDOWN

    def test_records_previous_mode(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        rec = engine.enter_emergency_mode("e2", "t1", EmergencyMode.DEGRADED, "auth", "escalate")
        assert rec.previous_mode == EmergencyMode.LOCKDOWN

    def test_increments_emergency_record_count(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        assert engine.emergency_record_count == 1

    def test_emits_event(self, es, engine):
        before = es.event_count
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        assert es.event_count == before + 1

    def test_record_fields(self, engine):
        rec = engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth-ref", "my reason")
        assert rec.emergency_id == "e1"
        assert rec.tenant_id == "t1"
        assert rec.authority_ref == "auth-ref"
        assert rec.reason == "my reason"
        assert "T" in rec.created_at

    def test_multi_tenant(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "r")
        engine.enter_emergency_mode("e2", "t2", EmergencyMode.DEGRADED, "auth", "r")
        assert engine.get_emergency_mode("t1") == EmergencyMode.LOCKDOWN
        assert engine.get_emergency_mode("t2") == EmergencyMode.DEGRADED


class TestExitEmergencyMode:
    def test_exit_returns_to_normal(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        rec = engine.exit_emergency_mode("e2", "t1", "auth", "resolved")
        assert rec.mode == EmergencyMode.NORMAL
        assert rec.previous_mode == EmergencyMode.LOCKDOWN

    def test_exit_updates_tenant_mode(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        engine.exit_emergency_mode("e2", "t1", "auth", "resolved")
        assert engine.get_emergency_mode("t1") == EmergencyMode.NORMAL

    def test_exit_not_in_emergency_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not in emergency mode"):
            engine.exit_emergency_mode("e1", "t1", "auth", "resolved")

    def test_exit_duplicate_id_raises(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate emergency_id"):
            engine.exit_emergency_mode("e1", "t1", "auth", "resolved")

    def test_exit_emits_event(self, es, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        before = es.event_count
        engine.exit_emergency_mode("e2", "t1", "auth", "resolved")
        assert es.event_count == before + 1

    def test_exit_increments_record_count(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        engine.exit_emergency_mode("e2", "t1", "auth", "resolved")
        assert engine.emergency_record_count == 2


class TestGetEmergencyMode:
    def test_default_normal(self, engine):
        assert engine.get_emergency_mode("t1") == EmergencyMode.NORMAL

    def test_after_enter(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        assert engine.get_emergency_mode("t1") == EmergencyMode.LOCKDOWN

    def test_unknown_tenant_normal(self, engine):
        assert engine.get_emergency_mode("unknown") == EmergencyMode.NORMAL


class TestEmergencyRecordsForTenant:
    def test_empty(self, engine):
        assert engine.emergency_records_for_tenant("t1") == ()

    def test_returns_correct(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        recs = engine.emergency_records_for_tenant("t1")
        assert len(recs) == 1

    def test_multi_tenant(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        engine.enter_emergency_mode("e2", "t2", EmergencyMode.DEGRADED, "auth", "reason")
        assert len(engine.emergency_records_for_tenant("t1")) == 1
        assert len(engine.emergency_records_for_tenant("t2")) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.emergency_records_for_tenant("t1"), tuple)


# ===================================================================
# Section 14: constitution_snapshot
# ===================================================================

class TestConstitutionSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.snapshot_id == "s1"
        assert snap.tenant_id == "t1"
        assert snap.total_rules == 0
        assert snap.active_rules == 0
        assert snap.total_bundles == 0
        assert snap.total_overrides == 0
        assert snap.total_decisions == 0
        assert snap.total_violations == 0
        assert snap.emergency_mode == EmergencyMode.NORMAL

    def test_snapshot_with_rules(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.suspend_rule("r2")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.total_rules == 2
        assert snap.active_rules == 1

    def test_snapshot_with_bundles(self, engine):
        engine.register_bundle("b1", "t1", "B")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.total_bundles == 1

    def test_snapshot_with_overrides(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.total_overrides == 1

    def test_snapshot_with_decisions(self, engine):
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.total_decisions == 1

    def test_snapshot_with_violations(self, engine):
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.total_violations == 1

    def test_snapshot_emergency_mode(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.emergency_mode == EmergencyMode.LOCKDOWN

    def test_snapshot_emits_event(self, es, engine):
        before = es.event_count
        engine.constitution_snapshot("s1", "t1")
        assert es.event_count == before + 1

    def test_snapshot_multi_tenant_isolation(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t2", "B")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.total_rules == 1

    def test_snapshot_returns_snapshot_type(self, engine):
        snap = engine.constitution_snapshot("s1", "t1")
        assert isinstance(snap, ConstitutionSnapshot)

    def test_snapshot_captured_at(self, engine):
        snap = engine.constitution_snapshot("s1", "t1")
        assert "T" in snap.captured_at


# ===================================================================
# Section 15: constitution_assessment
# ===================================================================

class TestConstitutionAssessment:
    def test_no_rules_score_one(self, engine):
        a = engine.constitution_assessment("a1", "t1")
        assert a.compliance_score == 1.0

    def test_all_active_score_one(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        a = engine.constitution_assessment("a1", "t1")
        assert a.compliance_score == 1.0

    def test_half_suspended_score(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.suspend_rule("r2")
        a = engine.constitution_assessment("a1", "t1")
        assert a.compliance_score == 0.5

    def test_violation_penalty(self, engine):
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        a = engine.constitution_assessment("a1", "t1")
        # 1 rule, 1 active, base=1.0, penalty=0.1, score=0.9
        assert a.compliance_score == 0.9

    def test_multiple_violations_penalty(self, engine):
        engine.register_rule("r1", "t1", "Hard1", ConstitutionRuleKind.HARD_DENY)
        engine.register_rule("r2", "t1", "Hard2", ConstitutionRuleKind.HARD_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        engine.apply_override("o2", "r2", "t1", "admin", "reason")
        a = engine.constitution_assessment("a1", "t1")
        # 2 rules, 2 active, base=1.0, penalty=min(2*0.1,1.0)=0.2, score=0.8
        assert a.compliance_score == 0.8

    def test_score_clamped_zero(self, engine):
        # Create 1 rule, suspend it, add 10 violations to force score negative
        engine.register_rule("r1", "t1", "A", ConstitutionRuleKind.SOFT_DENY)
        engine.suspend_rule("r1")
        # base = 0/1 = 0.0, penalty = 0 since min(0, 0)=0, score = 0.0
        a = engine.constitution_assessment("a1", "t1")
        assert a.compliance_score >= 0.0

    def test_duplicate_assessment_raises(self, engine):
        engine.constitution_assessment("a1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate assessment_id"):
            engine.constitution_assessment("a1", "t1")

    def test_assessment_fields(self, engine):
        engine.register_rule("r1", "t1", "A")
        a = engine.constitution_assessment("a1", "t1")
        assert a.assessment_id == "a1"
        assert a.tenant_id == "t1"
        assert a.total_rules == 1
        assert a.active_rules == 1
        assert a.override_count == 0
        assert a.violation_count == 0
        assert "T" in a.assessed_at

    def test_increments_assessment_count(self, engine):
        engine.constitution_assessment("a1", "t1")
        assert engine.assessment_count == 1

    def test_emits_event(self, es, engine):
        before = es.event_count
        engine.constitution_assessment("a1", "t1")
        assert es.event_count == before + 1

    def test_assessment_type(self, engine):
        a = engine.constitution_assessment("a1", "t1")
        assert isinstance(a, ConstitutionAssessment)

    def test_score_clamped_to_one(self, engine):
        a = engine.constitution_assessment("a1", "t1")
        assert a.compliance_score <= 1.0


# ===================================================================
# Section 16: detect_constitution_violations
# ===================================================================

class TestDetectConstitutionViolations:
    def test_no_violations_empty(self, engine):
        vs = engine.detect_constitution_violations("t1")
        assert vs == ()

    def test_suspended_no_override_violation(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.suspend_rule("r1")
        vs = engine.detect_constitution_violations("t1")
        assert len(vs) == 1
        assert vs[0].operation == "suspended_no_override"

    def test_empty_bundle_violation(self, engine):
        engine.register_bundle("b1", "t1", "B")
        vs = engine.detect_constitution_violations("t1")
        assert len(vs) == 1
        assert vs[0].operation == "empty_bundle"

    def test_policy_denied_violation(self, engine):
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        engine.evaluate_global_policy("d1", "t1", "all", "all")
        vs = engine.detect_constitution_violations("t1")
        assert any(v.operation == "policy_denied" for v in vs)

    def test_idempotent_second_call_empty(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.suspend_rule("r1")
        vs1 = engine.detect_constitution_violations("t1")
        assert len(vs1) == 1
        vs2 = engine.detect_constitution_violations("t1")
        assert len(vs2) == 0

    def test_emergency_lockdown_denial_no_policy_denied_violation(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        vs = engine.detect_constitution_violations("t1")
        # emergency_lockdown matched_rule_id is excluded from policy_denied check
        assert not any(v.operation == "policy_denied" for v in vs)

    def test_bundle_with_rules_no_violation(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_bundle("b1", "t1", "B")
        engine.add_rule_to_bundle("b1", "r1")
        vs = engine.detect_constitution_violations("t1")
        assert not any(v.operation == "empty_bundle" for v in vs)

    def test_suspended_with_override_no_violation(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        # r1 is now suspended with an override record
        vs = engine.detect_constitution_violations("t1")
        assert not any(v.operation == "suspended_no_override" for v in vs)

    def test_multi_tenant_isolation(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.suspend_rule("r1")
        vs = engine.detect_constitution_violations("t2")
        assert vs == ()

    def test_emits_event_when_violations_found(self, es, engine):
        engine.register_rule("r1", "t1", "A")
        engine.suspend_rule("r1")
        before = es.event_count
        engine.detect_constitution_violations("t1")
        assert es.event_count == before + 1

    def test_no_event_when_no_violations(self, es, engine):
        before = es.event_count
        engine.detect_constitution_violations("t1")
        assert es.event_count == before

    def test_multiple_violation_types(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.suspend_rule("r1")
        engine.register_bundle("b1", "t1", "B")
        engine.register_rule("r2", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        engine.evaluate_global_policy("d1", "t1", "all", "all")
        vs = engine.detect_constitution_violations("t1")
        ops = {v.operation for v in vs}
        assert "suspended_no_override" in ops
        assert "empty_bundle" in ops
        assert "policy_denied" in ops

    def test_violations_for_tenant(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.suspend_rule("r1")
        engine.detect_constitution_violations("t1")
        vt = engine.violations_for_tenant("t1")
        assert len(vt) == 1

    def test_violations_for_tenant_empty(self, engine):
        assert engine.violations_for_tenant("t1") == ()


# ===================================================================
# Section 17: closure_report
# ===================================================================

class TestClosureReport:
    def test_empty_report(self, engine):
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.report_id == "rpt1"
        assert rpt.tenant_id == "t1"
        assert rpt.total_rules == 0
        assert rpt.total_bundles == 0
        assert rpt.total_overrides == 0
        assert rpt.total_decisions == 0
        assert rpt.total_violations == 0
        assert rpt.total_resolutions == 0

    def test_report_with_data(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.register_bundle("b1", "t1", "B")
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_rules == 2
        assert rpt.total_bundles == 1
        assert rpt.total_decisions == 1

    def test_report_emits_event(self, es, engine):
        before = es.event_count
        engine.closure_report("rpt1", "t1")
        assert es.event_count == before + 1

    def test_report_type(self, engine):
        rpt = engine.closure_report("rpt1", "t1")
        assert isinstance(rpt, ConstitutionClosureReport)

    def test_report_created_at(self, engine):
        rpt = engine.closure_report("rpt1", "t1")
        assert "T" in rpt.created_at

    def test_report_includes_resolutions(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.resolve_precedence("p1", "t1", "r1", "r2")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_resolutions == 1

    def test_report_includes_violations(self, engine):
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_violations == 1

    def test_report_multi_tenant_isolation(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t2", "B")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_rules == 1


# ===================================================================
# Section 18: state_hash
# ===================================================================

class TestStateHash:
    def test_empty_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_deterministic(self, engine):
        engine.register_rule("r1", "t1", "A")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_on_rule_add(self, engine):
        h1 = engine.state_hash()
        engine.register_rule("r1", "t1", "A")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_suspend(self, engine):
        engine.register_rule("r1", "t1", "A")
        h1 = engine.state_hash()
        engine.suspend_rule("r1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_retire(self, engine):
        engine.register_rule("r1", "t1", "A")
        h1 = engine.state_hash()
        engine.retire_rule("r1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_bundle_add(self, engine):
        h1 = engine.state_hash()
        engine.register_bundle("b1", "t1", "B")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_decision(self, engine):
        h1 = engine.state_hash()
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_override(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        h1 = engine.state_hash()
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_violation(self, engine):
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        h1 = engine.state_hash()
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_emergency(self, engine):
        h1 = engine.state_hash()
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_resolution(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        h1 = engine.state_hash()
        engine.resolve_precedence("p1", "t1", "r1", "r2")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_add_rule_to_bundle(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_bundle("b1", "t1", "B")
        h1 = engine.state_hash()
        engine.add_rule_to_bundle("b1", "r1")
        h2 = engine.state_hash()
        assert h1 != h2


# ===================================================================
# Section 19: Properties
# ===================================================================

class TestProperties:
    def test_rule_count(self, engine):
        assert engine.rule_count == 0
        engine.register_rule("r1", "t1", "A")
        assert engine.rule_count == 1

    def test_bundle_count(self, engine):
        assert engine.bundle_count == 0
        engine.register_bundle("b1", "t1", "B")
        assert engine.bundle_count == 1

    def test_override_count(self, engine):
        assert engine.override_count == 0
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert engine.override_count == 1

    def test_decision_count(self, engine):
        assert engine.decision_count == 0
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        assert engine.decision_count == 1

    def test_violation_count(self, engine):
        assert engine.violation_count == 0
        engine.register_rule("r1", "t1", "Hard", ConstitutionRuleKind.HARD_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert engine.violation_count == 1

    def test_resolution_count(self, engine):
        assert engine.resolution_count == 0
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert engine.resolution_count == 1

    def test_emergency_record_count(self, engine):
        assert engine.emergency_record_count == 0
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        assert engine.emergency_record_count == 1

    def test_assessment_count(self, engine):
        assert engine.assessment_count == 0
        engine.constitution_assessment("a1", "t1")
        assert engine.assessment_count == 1


# ===================================================================
# Section 20: Precedence ordering (exhaustive pairs)
# ===================================================================

class TestPrecedenceOrdering:
    @pytest.mark.parametrize("high,low", [
        (PrecedenceLevel.CONSTITUTIONAL, PrecedenceLevel.PLATFORM),
        (PrecedenceLevel.CONSTITUTIONAL, PrecedenceLevel.TENANT),
        (PrecedenceLevel.CONSTITUTIONAL, PrecedenceLevel.RUNTIME),
        (PrecedenceLevel.PLATFORM, PrecedenceLevel.TENANT),
        (PrecedenceLevel.PLATFORM, PrecedenceLevel.RUNTIME),
        (PrecedenceLevel.TENANT, PrecedenceLevel.RUNTIME),
    ])
    def test_high_beats_low(self, engine, high, low):
        engine.register_rule("rH", "t1", "High", precedence=high)
        engine.register_rule("rL", "t1", "Low", precedence=low)
        res = engine.resolve_precedence("p1", "t1", "rH", "rL")
        assert res.winning_rule_id == "rH"

    @pytest.mark.parametrize("high,low", [
        (PrecedenceLevel.CONSTITUTIONAL, PrecedenceLevel.PLATFORM),
        (PrecedenceLevel.CONSTITUTIONAL, PrecedenceLevel.TENANT),
        (PrecedenceLevel.CONSTITUTIONAL, PrecedenceLevel.RUNTIME),
        (PrecedenceLevel.PLATFORM, PrecedenceLevel.TENANT),
        (PrecedenceLevel.PLATFORM, PrecedenceLevel.RUNTIME),
        (PrecedenceLevel.TENANT, PrecedenceLevel.RUNTIME),
    ])
    def test_high_beats_low_reversed_args(self, engine, high, low):
        engine.register_rule("rH", "t1", "High", precedence=high)
        engine.register_rule("rL", "t1", "Low", precedence=low)
        res = engine.resolve_precedence("p1", "t1", "rL", "rH")
        assert res.winning_rule_id == "rH"


# ===================================================================
# Section 21: Policy evaluation with all rule kinds
# ===================================================================

class TestPolicyAllKinds:
    @pytest.mark.parametrize("kind,expected", [
        (ConstitutionRuleKind.HARD_DENY, GlobalPolicyDisposition.DENIED),
        (ConstitutionRuleKind.SOFT_DENY, GlobalPolicyDisposition.ESCALATED),
        (ConstitutionRuleKind.RESTRICT, GlobalPolicyDisposition.RESTRICTED),
        (ConstitutionRuleKind.ALLOW, GlobalPolicyDisposition.ALLOWED),
        (ConstitutionRuleKind.REQUIRE, GlobalPolicyDisposition.ALLOWED),
    ])
    def test_kind_to_disposition(self, engine, kind, expected):
        engine.register_rule("r1", "t1", "Rule", kind=kind)
        d = engine.evaluate_global_policy(f"d-{kind.value}", "t1", "all", "all")
        assert d.disposition == expected


# ===================================================================
# Section 22: Policy evaluation precedence among competing rules
# ===================================================================

class TestPolicyPrecedenceWinner:
    def test_constitutional_hard_deny_beats_tenant_allow(self, engine):
        engine.register_rule("r1", "t1", "Allow", ConstitutionRuleKind.ALLOW, PrecedenceLevel.TENANT)
        engine.register_rule("r2", "t1", "Deny", ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_platform_soft_deny_beats_runtime_allow(self, engine):
        engine.register_rule("r1", "t1", "Allow", ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME)
        engine.register_rule("r2", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY, PrecedenceLevel.PLATFORM)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ESCALATED

    def test_tenant_restrict_beats_runtime_allow(self, engine):
        engine.register_rule("r1", "t1", "Allow", ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME)
        engine.register_rule("r2", "t1", "Restrict", ConstitutionRuleKind.RESTRICT, PrecedenceLevel.TENANT)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.RESTRICTED

    def test_three_rules_highest_wins(self, engine):
        engine.register_rule("r1", "t1", "Allow", ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME)
        engine.register_rule("r2", "t1", "Restrict", ConstitutionRuleKind.RESTRICT, PrecedenceLevel.TENANT)
        engine.register_rule("r3", "t1", "Deny", ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED
        assert d.matched_rule_id == "r3"


# ===================================================================
# Section 23: Golden scenario 1 — global deny overrides local allow
# ===================================================================

class TestGoldenGlobalDenyOverridesLocalAllow:
    def test_global_deny_wins(self, engine):
        engine.register_rule("local-allow", "t1", "Local Allow",
                             ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME, "agent-rt", "deploy")
        engine.register_rule("global-deny", "t1", "Global Deny",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL, "all", "all")
        d = engine.evaluate_global_policy("d1", "t1", "agent-rt", "deploy")
        assert d.disposition == GlobalPolicyDisposition.DENIED
        assert d.matched_rule_id == "global-deny"

    def test_without_global_deny_local_allow_works(self, engine):
        engine.register_rule("local-allow", "t1", "Local Allow",
                             ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME, "agent-rt", "deploy")
        d = engine.evaluate_global_policy("d1", "t1", "agent-rt", "deploy")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_global_deny_appears_in_closure(self, engine):
        engine.register_rule("local-allow", "t1", "Local Allow",
                             ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME)
        engine.register_rule("global-deny", "t1", "Global Deny",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        engine.evaluate_global_policy("d1", "t1", "all", "all")
        rpt = engine.closure_report("rpt1", "t1")
        assert rpt.total_decisions == 1
        assert rpt.total_rules == 2

    def test_precedence_resolution_confirms(self, engine):
        engine.register_rule("local-allow", "t1", "Local Allow",
                             ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME)
        engine.register_rule("global-deny", "t1", "Global Deny",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        res = engine.resolve_precedence("p1", "t1", "local-allow", "global-deny")
        assert res.winning_rule_id == "global-deny"

    def test_violation_detected_for_denied(self, engine):
        engine.register_rule("global-deny", "t1", "Global Deny",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        engine.evaluate_global_policy("d1", "t1", "all", "all")
        vs = engine.detect_constitution_violations("t1")
        assert any(v.operation == "policy_denied" for v in vs)


# ===================================================================
# Section 24: Golden scenario 2 — emergency lockdown blocks actions
# ===================================================================

class TestGoldenEmergencyLockdown:
    def test_lockdown_blocks_any_action(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "security-admin", "breach detected")
        for i, action in enumerate(["deploy", "build", "test", "release", "read"]):
            d = engine.evaluate_global_policy(f"d{i}", "t1", "any-rt", action)
            assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_lockdown_blocks_even_with_allow_rules(self, engine):
        engine.register_rule("allow-all", "t1", "Allow All",
                             ConstitutionRuleKind.ALLOW, PrecedenceLevel.CONSTITUTIONAL)
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "admin", "incident")
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_exit_lockdown_resumes(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "admin", "incident")
        engine.exit_emergency_mode("e2", "t1", "admin", "resolved")
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_lockdown_per_tenant(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "admin", "incident")
        d = engine.evaluate_global_policy("d1", "t2", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_lockdown_snapshot_reflects_mode(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "admin", "incident")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.emergency_mode == EmergencyMode.LOCKDOWN


# ===================================================================
# Section 25: Golden scenario 3 — executive override vs hard-stop
# ===================================================================

class TestGoldenExecutiveOverrideHardStop:
    def test_override_recorded_but_denied_for_hard_deny(self, engine):
        engine.register_rule("hard-stop", "t1", "Hard Stop",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        ov = engine.apply_override("exec-ov", "hard-stop", "t1", "CEO", "business critical")
        assert ov.disposition == OverrideDisposition.DENIED

    def test_hard_stop_remains_active(self, engine):
        engine.register_rule("hard-stop", "t1", "Hard Stop",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        engine.apply_override("exec-ov", "hard-stop", "t1", "CEO", "business critical")
        r = engine.get_rule("hard-stop")
        assert r.status == ConstitutionStatus.ACTIVE

    def test_violation_recorded(self, engine):
        engine.register_rule("hard-stop", "t1", "Hard Stop",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        engine.apply_override("exec-ov", "hard-stop", "t1", "CEO", "business critical")
        vs = engine.violations_for_tenant("t1")
        assert len(vs) == 1
        assert "hard_deny" in vs[0].reason

    def test_policy_still_denied_after_override_attempt(self, engine):
        engine.register_rule("hard-stop", "t1", "Hard Stop",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        engine.apply_override("exec-ov", "hard-stop", "t1", "CEO", "business critical")
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_soft_deny_override_succeeds(self, engine):
        engine.register_rule("soft-stop", "t1", "Soft Stop",
                             ConstitutionRuleKind.SOFT_DENY, PrecedenceLevel.PLATFORM)
        ov = engine.apply_override("exec-ov", "soft-stop", "t1", "CEO", "business critical")
        assert ov.disposition == OverrideDisposition.APPLIED
        r = engine.get_rule("soft-stop")
        assert r.status == ConstitutionStatus.SUSPENDED

    def test_assessment_reflects_violation(self, engine):
        engine.register_rule("hard-stop", "t1", "Hard Stop",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        engine.apply_override("exec-ov", "hard-stop", "t1", "CEO", "business critical")
        a = engine.constitution_assessment("a1", "t1")
        assert a.violation_count == 1
        assert a.compliance_score < 1.0


# ===================================================================
# Section 26: Golden scenario 4 — marketplace offering blocked
# ===================================================================

class TestGoldenMarketplaceBlocked:
    def test_marketplace_deploy_blocked(self, engine):
        engine.register_rule("mkt-block", "t1", "Block marketplace deploys",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.PLATFORM,
                             target_runtime="marketplace", target_action="deploy")
        d = engine.evaluate_global_policy("d1", "t1", "marketplace", "deploy")
        assert d.disposition == GlobalPolicyDisposition.DENIED

    def test_non_marketplace_not_blocked(self, engine):
        engine.register_rule("mkt-block", "t1", "Block marketplace deploys",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.PLATFORM,
                             target_runtime="marketplace", target_action="deploy")
        d = engine.evaluate_global_policy("d1", "t1", "agent-rt", "deploy")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_marketplace_read_not_blocked(self, engine):
        engine.register_rule("mkt-block", "t1", "Block marketplace deploys",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.PLATFORM,
                             target_runtime="marketplace", target_action="deploy")
        d = engine.evaluate_global_policy("d1", "t1", "marketplace", "read")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_restrict_marketplace_instead(self, engine):
        engine.register_rule("mkt-restrict", "t1", "Restrict marketplace",
                             ConstitutionRuleKind.RESTRICT, PrecedenceLevel.PLATFORM,
                             target_runtime="marketplace", target_action="all")
        d = engine.evaluate_global_policy("d1", "t1", "marketplace", "deploy")
        assert d.disposition == GlobalPolicyDisposition.RESTRICTED

    def test_marketplace_block_in_bundle(self, engine):
        engine.register_rule("mkt-block", "t1", "Block marketplace",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.PLATFORM,
                             target_runtime="marketplace", target_action="deploy")
        engine.register_bundle("security-bundle", "t1", "Security Bundle")
        engine.add_rule_to_bundle("security-bundle", "mkt-block")
        b = engine.get_bundle("security-bundle")
        assert b.rule_count == 1


# ===================================================================
# Section 27: Golden scenario 5 — release promotion denied by global policy
# ===================================================================

class TestGoldenReleasePromotionDenied:
    def test_release_denied_by_global_policy(self, engine):
        engine.register_rule("no-release", "t1", "Block releases",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL,
                             target_runtime="all", target_action="release")
        engine.register_rule("local-ready", "t1", "Local readiness",
                             ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME,
                             target_runtime="ci-cd", target_action="release")
        d = engine.evaluate_global_policy("d1", "t1", "ci-cd", "release")
        assert d.disposition == GlobalPolicyDisposition.DENIED
        assert d.matched_rule_id == "no-release"

    def test_after_retire_global_block_release_allowed(self, engine):
        engine.register_rule("no-release", "t1", "Block releases",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL,
                             target_action="release")
        engine.register_rule("local-ready", "t1", "Local readiness",
                             ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME,
                             target_action="release")
        engine.retire_rule("no-release")
        d = engine.evaluate_global_policy("d1", "t1", "ci-cd", "release")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_escalation_path_with_soft_deny(self, engine):
        engine.register_rule("soft-release", "t1", "Soft block releases",
                             ConstitutionRuleKind.SOFT_DENY, PrecedenceLevel.PLATFORM,
                             target_action="release")
        d = engine.evaluate_global_policy("d1", "t1", "ci-cd", "release")
        assert d.disposition == GlobalPolicyDisposition.ESCALATED

    def test_release_denial_detected_as_violation(self, engine):
        engine.register_rule("no-release", "t1", "Block releases",
                             ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL,
                             target_action="release")
        engine.evaluate_global_policy("d1", "t1", "ci-cd", "release")
        vs = engine.detect_constitution_violations("t1")
        assert any(v.operation == "policy_denied" for v in vs)


# ===================================================================
# Section 28: Golden scenario 6 — replay/restore preserves state
# ===================================================================

class TestGoldenReplayRestore:
    def test_state_hash_reproducible(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_bundle("b1", "t1", "B")
        engine.add_rule_to_bundle("b1", "r1")
        engine.evaluate_global_policy("d1", "t1", "all", "all")
        h = engine.state_hash()
        # Second call same hash
        assert engine.state_hash() == h

    def test_two_engines_same_ops_same_hash(self, es):
        e1 = ConstitutionalGovernanceEngine(es)
        es2 = EventSpineEngine()
        e2 = ConstitutionalGovernanceEngine(es2)
        for eng in (e1, e2):
            eng.register_rule("r1", "t1", "A", ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
            eng.register_bundle("b1", "t1", "B")
            eng.add_rule_to_bundle("b1", "r1")
            eng.evaluate_global_policy("d1", "t1", "all", "all")
        assert e1.state_hash() == e2.state_hash()

    def test_snapshot_captures_full_state(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B", ConstitutionRuleKind.SOFT_DENY)
        engine.suspend_rule("r2")
        engine.register_bundle("b1", "t1", "B")
        engine.add_rule_to_bundle("b1", "r1")
        engine.evaluate_global_policy("d1", "t1", "all", "all")
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.DEGRADED, "auth", "test")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.total_rules == 2
        assert snap.active_rules == 1
        assert snap.total_bundles == 1
        assert snap.total_decisions == 1
        assert snap.emergency_mode == EmergencyMode.DEGRADED

    def test_divergent_ops_different_hash(self, es):
        e1 = ConstitutionalGovernanceEngine(es)
        es2 = EventSpineEngine()
        e2 = ConstitutionalGovernanceEngine(es2)
        e1.register_rule("r1", "t1", "A")
        e2.register_rule("r1", "t1", "A")
        e1.suspend_rule("r1")
        # e2 did not suspend
        assert e1.state_hash() != e2.state_hash()

    def test_closure_report_matches_snapshot(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_bundle("b1", "t1", "B")
        engine.evaluate_global_policy("d1", "t1", "all", "all")
        snap = engine.constitution_snapshot("s1", "t1")
        rpt = engine.closure_report("rpt1", "t1")
        assert snap.total_rules == rpt.total_rules
        assert snap.total_bundles == rpt.total_bundles
        assert snap.total_decisions == rpt.total_decisions


# ===================================================================
# Section 29: Edge cases and mixed scenarios
# ===================================================================

class TestEdgeCases:
    def test_many_rules_same_tenant(self, engine):
        for i in range(50):
            engine.register_rule(f"r{i}", "t1", f"Rule {i}", ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME)
        assert engine.rule_count == 50
        assert len(engine.active_rules_for_tenant("t1")) == 50

    def test_many_bundles(self, engine):
        for i in range(20):
            engine.register_bundle(f"b{i}", "t1", f"Bundle {i}")
        assert engine.bundle_count == 20

    def test_many_decisions(self, engine):
        for i in range(30):
            engine.evaluate_global_policy(f"d{i}", "t1", "rt", "act")
        assert engine.decision_count == 30

    def test_override_then_policy_eval(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        # Rule now suspended, policy should allow
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_retire_after_suspend(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.suspend_rule("r1")
        r = engine.retire_rule("r1")
        assert r.status == ConstitutionStatus.RETIRED

    def test_emergency_transition_lockdown_to_degraded(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        rec = engine.enter_emergency_mode("e2", "t1", EmergencyMode.DEGRADED, "auth", "de-escalate")
        assert rec.previous_mode == EmergencyMode.LOCKDOWN
        assert engine.get_emergency_mode("t1") == EmergencyMode.DEGRADED

    def test_multiple_tenants_independent(self, engine):
        engine.register_rule("r1", "t1", "Deny T1", ConstitutionRuleKind.HARD_DENY)
        engine.register_rule("r2", "t2", "Allow T2", ConstitutionRuleKind.ALLOW)
        d1 = engine.evaluate_global_policy("d1", "t1", "all", "all")
        d2 = engine.evaluate_global_policy("d2", "t2", "all", "all")
        assert d1.disposition == GlobalPolicyDisposition.DENIED
        assert d2.disposition == GlobalPolicyDisposition.ALLOWED

    def test_bundle_multiple_rules(self, engine):
        for i in range(5):
            engine.register_rule(f"r{i}", "t1", f"Rule {i}")
        engine.register_bundle("b1", "t1", "Big Bundle")
        for i in range(5):
            engine.add_rule_to_bundle("b1", f"r{i}")
        b = engine.get_bundle("b1")
        assert b.rule_count == 5

    def test_assessment_after_complex_state(self, engine):
        engine.register_rule("r1", "t1", "A", ConstitutionRuleKind.HARD_DENY)
        engine.register_rule("r2", "t1", "B", ConstitutionRuleKind.SOFT_DENY)
        engine.register_rule("r3", "t1", "C", ConstitutionRuleKind.ALLOW)
        engine.apply_override("o1", "r1", "t1", "admin", "reason")  # denied, violation
        engine.apply_override("o2", "r2", "t1", "admin", "reason")  # applied, r2 suspended
        a = engine.constitution_assessment("a1", "t1")
        assert a.total_rules == 3
        assert a.active_rules == 2  # r1 still active (hard deny override denied), r3 active
        assert a.override_count == 2
        assert a.violation_count == 1

    def test_snapshot_after_exit_emergency(self, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        engine.exit_emergency_mode("e2", "t1", "auth", "resolved")
        snap = engine.constitution_snapshot("s1", "t1")
        assert snap.emergency_mode == EmergencyMode.NORMAL

    def test_full_lifecycle(self, engine):
        # Register, evaluate, override, emergency, assess, detect, close
        engine.register_rule("r1", "t1", "A", ConstitutionRuleKind.HARD_DENY, PrecedenceLevel.CONSTITUTIONAL)
        engine.register_rule("r2", "t1", "B", ConstitutionRuleKind.SOFT_DENY, PrecedenceLevel.PLATFORM)
        engine.register_bundle("b1", "t1", "Bundle")
        engine.add_rule_to_bundle("b1", "r1")
        engine.add_rule_to_bundle("b1", "r2")
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.DENIED
        engine.apply_override("o1", "r1", "t1", "admin", "attempt")
        engine.apply_override("o2", "r2", "t1", "admin", "override soft")
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "admin", "incident")
        engine.exit_emergency_mode("e2", "t1", "admin", "resolved")
        engine.resolve_precedence("p1", "t1", "r1", "r2")
        vs = engine.detect_constitution_violations("t1")
        a = engine.constitution_assessment("a1", "t1")
        rpt = engine.closure_report("rpt1", "t1")
        h = engine.state_hash()
        assert isinstance(h, str)
        assert rpt.total_rules == 2
        assert a.total_rules == 2


# ===================================================================
# Section 30: Stress / boundary
# ===================================================================

class TestStressBoundary:
    def test_100_rules(self, engine):
        for i in range(100):
            engine.register_rule(f"r{i}", "t1", f"Rule {i}", ConstitutionRuleKind.ALLOW, PrecedenceLevel.RUNTIME)
        assert engine.rule_count == 100
        d = engine.evaluate_global_policy("d1", "t1", "all", "all")
        assert d.disposition == GlobalPolicyDisposition.ALLOWED

    def test_100_decisions(self, engine):
        for i in range(100):
            engine.evaluate_global_policy(f"d{i}", "t1", "rt", "act")
        assert engine.decision_count == 100

    def test_state_hash_after_bulk_ops(self, engine):
        for i in range(50):
            engine.register_rule(f"r{i}", "t1", f"Rule {i}")
        h = engine.state_hash()
        assert isinstance(h, str) and len(h) == 64

    def test_empty_string_rule_id_rejected(self, engine):
        # The contracts require non-empty text; engine calls constructors
        with pytest.raises((RuntimeCoreInvariantError, ValueError)):
            engine.register_rule("", "t1", "A")

    def test_empty_string_tenant_id_rejected(self, engine):
        with pytest.raises((RuntimeCoreInvariantError, ValueError)):
            engine.register_rule("r1", "", "A")

    def test_empty_string_display_name_rejected(self, engine):
        with pytest.raises((RuntimeCoreInvariantError, ValueError)):
            engine.register_rule("r1", "t1", "")

    def test_empty_string_bundle_id_rejected(self, engine):
        with pytest.raises((RuntimeCoreInvariantError, ValueError)):
            engine.register_bundle("", "t1", "B")

    def test_whitespace_only_rule_id_rejected(self, engine):
        with pytest.raises((RuntimeCoreInvariantError, ValueError)):
            engine.register_rule("   ", "t1", "A")

    def test_whitespace_only_tenant_rejected(self, engine):
        with pytest.raises((RuntimeCoreInvariantError, ValueError)):
            engine.register_rule("r1", "   ", "A")


# ===================================================================
# Section 31: Event emission verification
# ===================================================================

class TestEventEmission:
    def test_register_rule_emits(self, es, engine):
        engine.register_rule("r1", "t1", "A")
        assert es.event_count >= 1

    def test_suspend_emits(self, es, engine):
        engine.register_rule("r1", "t1", "A")
        c = es.event_count
        engine.suspend_rule("r1")
        assert es.event_count == c + 1

    def test_retire_emits(self, es, engine):
        engine.register_rule("r1", "t1", "A")
        c = es.event_count
        engine.retire_rule("r1")
        assert es.event_count == c + 1

    def test_register_bundle_emits(self, es, engine):
        c = es.event_count
        engine.register_bundle("b1", "t1", "B")
        assert es.event_count == c + 1

    def test_add_rule_to_bundle_emits(self, es, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_bundle("b1", "t1", "B")
        c = es.event_count
        engine.add_rule_to_bundle("b1", "r1")
        assert es.event_count == c + 1

    def test_evaluate_policy_emits(self, es, engine):
        c = es.event_count
        engine.evaluate_global_policy("d1", "t1", "rt", "act")
        assert es.event_count == c + 1

    def test_resolve_precedence_emits(self, es, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        c = es.event_count
        engine.resolve_precedence("p1", "t1", "r1", "r2")
        assert es.event_count == c + 1

    def test_apply_override_emits(self, es, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        c = es.event_count
        engine.apply_override("o1", "r1", "t1", "admin", "reason")
        assert es.event_count == c + 1

    def test_enter_emergency_emits(self, es, engine):
        c = es.event_count
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        assert es.event_count == c + 1

    def test_exit_emergency_emits(self, es, engine):
        engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        c = es.event_count
        engine.exit_emergency_mode("e2", "t1", "auth", "resolved")
        assert es.event_count == c + 1

    def test_snapshot_emits(self, es, engine):
        c = es.event_count
        engine.constitution_snapshot("s1", "t1")
        assert es.event_count == c + 1

    def test_assessment_emits(self, es, engine):
        c = es.event_count
        engine.constitution_assessment("a1", "t1")
        assert es.event_count == c + 1

    def test_closure_report_emits(self, es, engine):
        c = es.event_count
        engine.closure_report("rpt1", "t1")
        assert es.event_count == c + 1

    def test_detect_violations_emits_when_found(self, es, engine):
        engine.register_rule("r1", "t1", "A")
        engine.suspend_rule("r1")
        c = es.event_count
        engine.detect_constitution_violations("t1")
        assert es.event_count == c + 1

    def test_detect_violations_no_emit_when_clean(self, es, engine):
        c = es.event_count
        engine.detect_constitution_violations("t1")
        assert es.event_count == c


# ===================================================================
# Section 32: Frozen / immutable return values
# ===================================================================

class TestImmutability:
    def test_rule_is_frozen(self, engine):
        r = engine.register_rule("r1", "t1", "A")
        with pytest.raises(AttributeError):
            r.status = ConstitutionStatus.RETIRED

    def test_bundle_is_frozen(self, engine):
        b = engine.register_bundle("b1", "t1", "B")
        with pytest.raises(AttributeError):
            b.rule_count = 99

    def test_decision_is_frozen(self, engine):
        d = engine.evaluate_global_policy("d1", "t1", "rt", "act")
        with pytest.raises(AttributeError):
            d.disposition = GlobalPolicyDisposition.DENIED

    def test_override_is_frozen(self, engine):
        engine.register_rule("r1", "t1", "Soft", ConstitutionRuleKind.SOFT_DENY)
        ov = engine.apply_override("o1", "r1", "t1", "admin", "reason")
        with pytest.raises(AttributeError):
            ov.disposition = OverrideDisposition.DENIED

    def test_resolution_is_frozen(self, engine):
        engine.register_rule("r1", "t1", "A")
        engine.register_rule("r2", "t1", "B")
        res = engine.resolve_precedence("p1", "t1", "r1", "r2")
        with pytest.raises(AttributeError):
            res.winning_rule_id = "hacked"

    def test_emergency_record_is_frozen(self, engine):
        rec = engine.enter_emergency_mode("e1", "t1", EmergencyMode.LOCKDOWN, "auth", "reason")
        with pytest.raises(AttributeError):
            rec.mode = EmergencyMode.NORMAL

    def test_snapshot_is_frozen(self, engine):
        snap = engine.constitution_snapshot("s1", "t1")
        with pytest.raises(AttributeError):
            snap.total_rules = 999

    def test_assessment_is_frozen(self, engine):
        a = engine.constitution_assessment("a1", "t1")
        with pytest.raises(AttributeError):
            a.compliance_score = 0.0

    def test_closure_report_is_frozen(self, engine):
        rpt = engine.closure_report("rpt1", "t1")
        with pytest.raises(AttributeError):
            rpt.total_rules = 999

    def test_rules_for_tenant_returns_tuple(self, engine):
        engine.register_rule("r1", "t1", "A")
        result = engine.rules_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_active_rules_for_tenant_returns_tuple(self, engine):
        result = engine.active_rules_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_bundles_for_tenant_returns_tuple(self, engine):
        result = engine.bundles_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_decisions_for_tenant_returns_tuple(self, engine):
        result = engine.decisions_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_overrides_for_tenant_returns_tuple(self, engine):
        result = engine.overrides_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_violations_for_tenant_returns_tuple(self, engine):
        result = engine.violations_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_emergency_records_for_tenant_returns_tuple(self, engine):
        result = engine.emergency_records_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_resolutions_for_tenant_returns_tuple(self, engine):
        result = engine.resolutions_for_tenant("t1")
        assert isinstance(result, tuple)
