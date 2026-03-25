"""Edge case tests for the governance DSL discovered during holistic audit.

Covers: condition evaluation edge cases (None, empty, Mapping contains, regex),
compiler edge cases (all-disabled bundles, empty bundles), evaluator edge cases
(deeply nested paths, scope filtering), integration edge cases (all effect
values mapped, threshold extraction, provider decisions), and contract
validation edge cases (enabled bool, frozen expected_value).
"""

from __future__ import annotations

import pytest
from types import MappingProxyType

from mcoi_runtime.contracts.autonomy import AutonomyMode
from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.governance import (
    CompilationStatus,
    PolicyAction,
    PolicyActionKind,
    PolicyBundle,
    PolicyCondition,
    PolicyConditionOperator,
    PolicyEffect,
    PolicyRule,
    PolicyScope,
    PolicyScopeKind,
    PolicyVersion,
)
from mcoi_runtime.contracts.reaction import (
    ReactionCondition,
    ReactionRule,
    ReactionTarget,
    ReactionTargetKind,
    ReactionVerdict,
)
from mcoi_runtime.core.governance_compiler import (
    GovernanceCompiler,
    GovernanceEvaluator,
    evaluate_condition,
)
from mcoi_runtime.core.governance_integration import GovernanceBridge

NOW = "2026-03-20T12:00:00+00:00"
CLOCK = lambda: NOW  # noqa: E731


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cond(fp: str, op: str, val: object = None) -> PolicyCondition:
    return PolicyCondition(field_path=fp, operator=op, expected_value=val)


def _scope(kind: PolicyScopeKind = PolicyScopeKind.GLOBAL, ref_id: str | None = None) -> PolicyScope:
    return PolicyScope(scope_id="s", kind=kind, ref_id=ref_id)


def _action(aid: str = "a1", kind: PolicyActionKind = PolicyActionKind.SET_AUTONOMY) -> PolicyAction:
    return PolicyAction(action_id=aid, kind=kind)


def _rule(
    rid: str, effect: PolicyEffect = PolicyEffect.ALLOW,
    conds: tuple = (), actions: tuple = (),
    scope: PolicyScope | None = None, priority: int = 0,
    enabled: bool = True,
) -> PolicyRule:
    return PolicyRule(
        rule_id=rid, name=f"rule-{rid}", description=f"desc-{rid}",
        effect=effect, conditions=conds, actions=actions,
        scope=scope or _scope(), priority=priority, enabled=enabled,
    )


def _version() -> PolicyVersion:
    return PolicyVersion(version_id="v1", major=1, minor=0, patch=0, created_at=NOW)


def _bundle(rules: tuple[PolicyRule, ...]) -> PolicyBundle:
    return PolicyBundle(
        bundle_id="b1", name="test", version=_version(),
        rules=rules, created_at=NOW,
    )


def _event(eid: str = "e1") -> EventRecord:
    return EventRecord(
        event_id=eid, event_type=EventType.APPROVAL_REQUESTED,
        source=EventSource.APPROVAL_SYSTEM, correlation_id="cor-1",
        payload={"state": "active"}, emitted_at=NOW,
    )


def _reaction_rule(rid: str = "rxn-1") -> ReactionRule:
    return ReactionRule(
        rule_id=rid, name=f"rule-{rid}", event_type="approval_requested",
        conditions=(ReactionCondition(
            condition_id="c1", field_path="state", operator="eq", expected_value="active"),),
        target=ReactionTarget(
            target_id=f"tgt-{rid}", kind=ReactionTargetKind.NOTIFY,
            target_ref_id="ref-1", parameters={},
        ),
        created_at=NOW,
    )


# ---------------------------------------------------------------------------
# Condition evaluation edge cases
# ---------------------------------------------------------------------------


class TestConditionEdgeCases:
    def test_none_value_eq(self) -> None:
        assert evaluate_condition(_cond("x", "eq", None), {"x": None}) is True
        assert evaluate_condition(_cond("x", "eq", None), {"x": 1}) is False

    def test_none_value_neq(self) -> None:
        assert evaluate_condition(_cond("x", "neq", None), {"x": 1}) is True
        assert evaluate_condition(_cond("x", "neq", None), {"x": None}) is False

    def test_none_value_gt_returns_false(self) -> None:
        assert evaluate_condition(_cond("x", "gt", 10), {"x": None}) is False

    def test_empty_string_contains(self) -> None:
        assert evaluate_condition(_cond("x", "contains", ""), {"x": "anything"}) is True
        assert evaluate_condition(_cond("x", "contains", ""), {"x": ""}) is True

    def test_contains_mapping_key(self) -> None:
        assert evaluate_condition(_cond("x", "contains", "key"), {"x": {"key": "val"}}) is True
        assert evaluate_condition(_cond("x", "contains", "missing"), {"x": {"key": "val"}}) is False

    def test_deeply_nested_dot_path(self) -> None:
        ctx = {"a": {"b": {"c": {"d": "found"}}}}
        assert evaluate_condition(_cond("a.b.c.d", "eq", "found"), ctx) is True
        assert evaluate_condition(_cond("a.b.c.missing", "eq", "x"), ctx) is False

    def test_matches_non_string_expected(self) -> None:
        # Non-string regex should return False, not error
        assert evaluate_condition(_cond("x", "matches", 42), {"x": "test"}) is False

    def test_matches_non_string_current(self) -> None:
        assert evaluate_condition(_cond("x", "matches", "pattern"), {"x": 42}) is False

    def test_in_with_tuple_expected(self) -> None:
        assert evaluate_condition(_cond("x", "in", ("a", "b")), {"x": "a"}) is True
        assert evaluate_condition(_cond("x", "in", ("a", "b")), {"x": "z"}) is False

    def test_exists_on_none_value(self) -> None:
        # Field exists but value is None — EXISTS should still return True
        assert evaluate_condition(_cond("x", "exists"), {"x": None}) is True

    def test_not_exists_on_none_value(self) -> None:
        # Field exists but value is None — NOT_EXISTS should return False
        assert evaluate_condition(_cond("x", "not_exists"), {"x": None}) is False

    def test_comparison_with_string_and_int(self) -> None:
        # Type mismatch — should return False, not crash
        assert evaluate_condition(_cond("x", "lt", "text"), {"x": 42}) is False
        assert evaluate_condition(_cond("x", "gte", 10), {"x": "not_a_number"}) is False


# ---------------------------------------------------------------------------
# Compiler edge cases
# ---------------------------------------------------------------------------


class TestCompilerEdgeCases:
    def test_all_disabled_bundle(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        b = _bundle(rules=(
            _rule("r1", enabled=False),
            _rule("r2", enabled=False),
        ))
        result = compiler.compile(b)
        assert result.succeeded is True  # warnings but not failure
        assert result.enabled_rule_count == 0
        assert any("disabled" in w.lower() for w in result.warnings)

    def test_many_rules_no_conflicts(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        rules = tuple(
            _rule(f"r-{i}", effect=PolicyEffect.ALLOW, priority=i)
            for i in range(20)
        )
        b = _bundle(rules=rules)
        result = compiler.compile(b)
        assert result.succeeded is True
        assert result.rule_count == 20

    def test_same_effect_same_priority_no_contradiction(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        b = _bundle(rules=(
            _rule("r1", effect=PolicyEffect.DENY, priority=0),
            _rule("r2", effect=PolicyEffect.DENY, priority=0),
        ))
        result = compiler.compile(b)
        # Same effect = no contradiction, no priority tie
        contradictions = [c for c in result.conflicts if c.kind.value == "contradictory_effects"]
        assert len(contradictions) == 0


# ---------------------------------------------------------------------------
# Evaluator edge cases
# ---------------------------------------------------------------------------


class TestEvaluatorEdgeCases:
    def test_empty_context(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", conds=(_cond("x", "exists"),))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {})
        assert trace.rules_matched == 0  # EXISTS fails on empty context

    def test_rule_with_empty_conditions_and_empty_actions(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", effect=PolicyEffect.ESCALATE, conds=(), actions=())
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {})
        assert trace.rules_fired == 1
        assert trace.final_effect == PolicyEffect.ESCALATE
        assert len(trace.actions_produced) == 0

    def test_scope_no_context_scope_info_defaults_to_apply(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        # Rule with no conditions → always matches; team scope with no context → fail-open
        r = _rule("r1", scope=_scope(PolicyScopeKind.TEAM, ref_id="team-x"))
        b = _bundle(rules=(r,))
        # No scope info in context → scope applies (fail-open), rule fires
        trace = evaluator.evaluate(b, "s1", {})
        assert trace.rules_fired == 1  # fail-open: scope applies when context lacks scope info

    def test_multiple_fired_rules_actions_collected(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        a1 = PolicyAction(action_id="a1", kind=PolicyActionKind.SET_SIMULATION_THRESHOLD, parameters={"threshold": 0.9})
        a2 = PolicyAction(action_id="a2", kind=PolicyActionKind.SET_UTILITY_THRESHOLD, parameters={"threshold": 0.7})
        r1 = _rule("r1", actions=(a1,), conds=(_cond("x", "exists"),))
        r2 = _rule("r2", actions=(a2,), conds=(_cond("x", "exists"),))
        b = _bundle(rules=(r1, r2))
        trace = evaluator.evaluate(b, "s1", {"x": 1})
        assert len(trace.actions_produced) == 2


# ---------------------------------------------------------------------------
# Integration bridge edge cases
# ---------------------------------------------------------------------------


class TestIntegrationEdgeCases:
    def test_derive_autonomy_all_effects(self) -> None:
        """Verify all 6 PolicyEffect values map to a valid AutonomyMode."""
        from mcoi_runtime.contracts.governance import PolicyEvaluationTrace

        for effect in PolicyEffect:
            trace = PolicyEvaluationTrace(
                trace_id="t", bundle_id="b", subject_id="s",
                context_snapshot={},
                rules_evaluated=0, rules_matched=0, rules_fired=0,
                matched_rule_ids=(), fired_rule_ids=(),
                final_effect=effect, actions_produced=(),
                evaluated_at=NOW,
            )
            mode = GovernanceBridge.derive_autonomy_mode(trace)
            assert isinstance(mode, AutonomyMode)

    def test_governance_gate_all_effects_produce_valid_verdicts(self) -> None:
        """Every PolicyEffect produces a valid ReactionVerdict in the gate."""
        for effect in PolicyEffect:
            r = _rule("r1", effect=effect)
            b = _bundle(rules=(r,))
            evaluator = GovernanceEvaluator(clock=CLOCK)
            gate = GovernanceBridge.build_governance_gate(evaluator, b, CLOCK)
            result = gate(_event(), _reaction_rule())
            assert isinstance(result.verdict, ReactionVerdict)

    def test_extract_thresholds_non_numeric_skipped(self) -> None:
        from mcoi_runtime.contracts.governance import PolicyEvaluationTrace

        trace = PolicyEvaluationTrace(
            trace_id="t", bundle_id="b", subject_id="s",
            context_snapshot={},
            rules_evaluated=0, rules_matched=0, rules_fired=0,
            matched_rule_ids=(), fired_rule_ids=(),
            final_effect=PolicyEffect.ALLOW,
            actions_produced=(
                PolicyAction(action_id="a1", kind=PolicyActionKind.SET_SIMULATION_THRESHOLD, parameters={"threshold": "not_a_number"}),
                PolicyAction(action_id="a2", kind=PolicyActionKind.SET_UTILITY_THRESHOLD, parameters={"threshold": 0.8}),
            ),
            evaluated_at=NOW,
        )
        thresholds = GovernanceBridge.extract_thresholds(trace)
        assert "simulation" not in thresholds  # skipped non-numeric
        assert thresholds["utility"] == 0.8

    def test_extract_escalation_threshold(self) -> None:
        from mcoi_runtime.contracts.governance import PolicyEvaluationTrace

        trace = PolicyEvaluationTrace(
            trace_id="t", bundle_id="b", subject_id="s",
            context_snapshot={},
            rules_evaluated=0, rules_matched=0, rules_fired=0,
            matched_rule_ids=(), fired_rule_ids=(),
            final_effect=PolicyEffect.ALLOW,
            actions_produced=(
                PolicyAction(action_id="a1", kind=PolicyActionKind.SET_ESCALATION_THRESHOLD, parameters={"threshold": 0.6}),
            ),
            evaluated_at=NOW,
        )
        thresholds = GovernanceBridge.extract_thresholds(trace)
        assert thresholds["escalation"] == 0.6

    def test_extract_provider_decisions_non_string_id_skipped(self) -> None:
        from mcoi_runtime.contracts.governance import PolicyEvaluationTrace

        trace = PolicyEvaluationTrace(
            trace_id="t", bundle_id="b", subject_id="s",
            context_snapshot={},
            rules_evaluated=0, rules_matched=0, rules_fired=0,
            matched_rule_ids=(), fired_rule_ids=(),
            final_effect=PolicyEffect.ALLOW,
            actions_produced=(
                PolicyAction(action_id="a1", kind=PolicyActionKind.ALLOW_PROVIDER, parameters={"provider_id": 123}),
                PolicyAction(action_id="a2", kind=PolicyActionKind.DENY_PROVIDER, parameters={"provider_id": "real-provider"}),
            ),
            evaluated_at=NOW,
        )
        decisions = GovernanceBridge.extract_provider_decisions(trace)
        assert 123 not in decisions  # skipped non-string
        assert decisions["real-provider"] is False


# ---------------------------------------------------------------------------
# Contract validation edge cases
# ---------------------------------------------------------------------------


class TestContractValidationEdgeCases:
    def test_enabled_must_be_bool(self) -> None:
        with pytest.raises(ValueError, match="enabled"):
            PolicyRule(
                rule_id="r", name="n", description="d",
                effect=PolicyEffect.ALLOW, conditions=(), actions=(),
                scope=_scope(), enabled=1,  # type: ignore[arg-type]
            )

    def test_expected_value_dict_frozen_to_mapping_proxy(self) -> None:
        c = PolicyCondition(field_path="x", operator="eq", expected_value={"key": [1, 2]})
        assert isinstance(c.expected_value, MappingProxyType)

    def test_expected_value_list_frozen_to_tuple(self) -> None:
        c = PolicyCondition(field_path="x", operator="in", expected_value=["a", "b"])
        assert isinstance(c.expected_value, tuple)

    def test_version_semver(self) -> None:
        v = PolicyVersion(version_id="v", major=3, minor=14, patch=159, created_at=NOW)
        assert v.semver == "3.14.159"

    def test_bundle_duplicate_rule_ids_rejected(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            _bundle(rules=(_rule("dup"), _rule("dup")))


# ---------------------------------------------------------------------------
# Frozen contract cross-module edge cases
# ---------------------------------------------------------------------------


class TestCrossModuleEdgeCases:
    def test_goal_execution_state_empty_subgoal_id_rejected(self) -> None:
        from mcoi_runtime.contracts.goal import GoalExecutionState, GoalStatus
        with pytest.raises(ValueError, match="completed_sub_goals"):
            GoalExecutionState(
                goal_id="g1", status=GoalStatus.EXECUTING,
                updated_at=NOW, completed_sub_goals=("",),
            )

    def test_goal_execution_state_valid_subgoal_ids(self) -> None:
        from mcoi_runtime.contracts.goal import GoalExecutionState, GoalStatus
        state = GoalExecutionState(
            goal_id="g1", status=GoalStatus.COMPLETED,
            updated_at=NOW,
            completed_sub_goals=("sg-1", "sg-2"),
            failed_sub_goals=("sg-3",),
        )
        assert len(state.completed_sub_goals) == 2

    def test_event_envelope_target_subsystems_frozen(self) -> None:
        from mcoi_runtime.contracts.event import EventEnvelope
        env = EventEnvelope(
            envelope_id="env-1", event=_event(),
            target_subsystems=["system-a", "system-b"],  # list should be frozen
            priority=1,
        )
        assert isinstance(env.target_subsystems, tuple)

    def test_event_correlation_event_ids_frozen(self) -> None:
        from mcoi_runtime.contracts.event import EventCorrelation
        corr = EventCorrelation(
            correlation_id="cor-1",
            event_ids=["e1", "e2"],  # list should be frozen
            root_event_id="e1",
            description="test correlation",
            created_at=NOW,
        )
        assert isinstance(corr.event_ids, tuple)

    def test_workflow_verification_datetime_validated(self) -> None:
        from mcoi_runtime.contracts.workflow import WorkflowVerificationRecord
        with pytest.raises(ValueError, match="verified_at"):
            WorkflowVerificationRecord(
                execution_id="ex-1", verified=True,
                verified_at="not-a-date",
            )

    def test_workflow_verification_empty_verified_at_rejected(self) -> None:
        from mcoi_runtime.contracts.workflow import WorkflowVerificationRecord
        with pytest.raises(ValueError):
            WorkflowVerificationRecord(
                execution_id="ex-1", verified=True,
                verified_at="",
            )


# ---------------------------------------------------------------------------
# Effect precedence — all 6 effects
# ---------------------------------------------------------------------------


class TestEffectPrecedenceComplete:
    def test_all_six_effects_deny_wins(self) -> None:
        """When all 6 effects fire, DENY should win (highest precedence)."""
        evaluator = GovernanceEvaluator(clock=CLOCK)
        rules = tuple(
            _rule(f"r-{e.value}", effect=e, conds=(_cond("x", "exists"),))
            for e in PolicyEffect
        )
        b = _bundle(rules=rules)
        trace = evaluator.evaluate(b, "s1", {"x": 1})
        assert trace.rules_fired == 6
        assert trace.final_effect == PolicyEffect.DENY

    def test_effect_precedence_full_ordering(self) -> None:
        """Verify DENY > REQUIRE_APPROVAL > REQUIRE_REVIEW > ESCALATE > REPLAN > ALLOW."""
        evaluator = GovernanceEvaluator(clock=CLOCK)
        effects_descending = [
            PolicyEffect.DENY,
            PolicyEffect.REQUIRE_APPROVAL,
            PolicyEffect.REQUIRE_REVIEW,
            PolicyEffect.ESCALATE,
            PolicyEffect.REPLAN,
            PolicyEffect.ALLOW,
        ]
        # Remove highest, verify next-highest wins
        for i in range(1, len(effects_descending)):
            subset = effects_descending[i:]
            rules = tuple(
                _rule(f"r-{e.value}", effect=e, conds=(_cond("x", "exists"),))
                for e in subset
            )
            b = _bundle(rules=rules)
            trace = evaluator.evaluate(b, "s1", {"x": 1})
            assert trace.final_effect == subset[0], (
                f"Expected {subset[0]} to win over {subset[1:]}"
            )


# ---------------------------------------------------------------------------
# Scope matching for all kinds
# ---------------------------------------------------------------------------


class TestScopeMatchingAllKinds:
    def test_global_scope_always_applies(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", scope=_scope(PolicyScopeKind.GLOBAL))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {})
        assert trace.rules_fired == 1

    def test_team_scope_matches(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", scope=_scope(PolicyScopeKind.TEAM, ref_id="t1"))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"scope": {"team": "t1"}})
        assert trace.rules_fired == 1

    def test_team_scope_rejects(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", scope=_scope(PolicyScopeKind.TEAM, ref_id="t1"))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"scope": {"team": "t2"}})
        assert trace.rules_fired == 0

    def test_deployment_scope_matches(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", scope=_scope(PolicyScopeKind.DEPLOYMENT, ref_id="prod"))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"scope": {"deployment": "prod"}})
        assert trace.rules_fired == 1

    def test_function_scope_matches(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", scope=_scope(PolicyScopeKind.FUNCTION, ref_id="fn-1"))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"scope": {"function": "fn-1"}})
        assert trace.rules_fired == 1

    def test_job_scope_matches(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", scope=_scope(PolicyScopeKind.JOB, ref_id="j-1"))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"scope": {"job": "j-1"}})
        assert trace.rules_fired == 1

    def test_workflow_scope_matches(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", scope=_scope(PolicyScopeKind.WORKFLOW, ref_id="wf-1"))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"scope": {"workflow": "wf-1"}})
        assert trace.rules_fired == 1

    def test_provider_scope_matches(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", scope=_scope(PolicyScopeKind.PROVIDER, ref_id="p-1"))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"scope": {"provider": "p-1"}})
        assert trace.rules_fired == 1

    def test_capability_scope_matches(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", scope=_scope(PolicyScopeKind.CAPABILITY, ref_id="cap-1"))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"scope": {"capability": "cap-1"}})
        assert trace.rules_fired == 1


# ---------------------------------------------------------------------------
# Serialization round-trips
# ---------------------------------------------------------------------------


class TestSerializationRoundTrips:
    def test_policy_rule_to_dict(self) -> None:
        r = _rule("r1", effect=PolicyEffect.DENY,
                   conds=(_cond("x", "eq", "val"),),
                   actions=(_action(),))
        d = r.to_dict()
        assert d["rule_id"] == "r1"
        assert d["effect"] == "deny"
        assert len(d["conditions"]) == 1
        assert d["conditions"][0]["field_path"] == "x"

    def test_policy_bundle_to_dict(self) -> None:
        b = _bundle(rules=(_rule("r1"),))
        d = b.to_dict()
        assert d["bundle_id"] == "b1"
        assert d["name"] == "test"
        assert len(d["rules"]) == 1
        assert d["version"]["major"] == 1

    def test_policy_conflict_to_dict(self) -> None:
        from mcoi_runtime.contracts.governance import PolicyConflict, PolicyConflictKind, PolicyConflictSeverity
        c = PolicyConflict(
            conflict_id="c1", kind=PolicyConflictKind.PRIORITY_TIE,
            severity=PolicyConflictSeverity.WARNING,
            rule_ids=("r1", "r2"), description="tie", detected_at=NOW,
        )
        d = c.to_dict()
        assert d["conflict_id"] == "c1"
        assert d["kind"] == "priority_tie"
        assert len(d["rule_ids"]) == 2

    def test_compilation_result_to_dict(self) -> None:
        from mcoi_runtime.contracts.governance import PolicyCompilationResult
        r = PolicyCompilationResult(
            compilation_id="c1", bundle_id="b1",
            status=CompilationStatus.SUCCESS,
            conflicts=(), warnings=("w1",), compiled_at=NOW,
            rule_count=5, enabled_rule_count=3,
        )
        d = r.to_dict()
        assert d["status"] == "success"
        assert d["rule_count"] == 5
        assert len(d["warnings"]) == 1

    def test_policy_version_to_dict(self) -> None:
        v = _version()
        d = v.to_dict()
        assert d["major"] == 1
        assert d["minor"] == 0
        assert d["patch"] == 0

    def test_policy_action_to_json(self) -> None:
        a = _action()
        j = a.to_json()
        assert "a1" in j
        assert "set_autonomy" in j


# ---------------------------------------------------------------------------
# Meta-reasoning threshold validation
# ---------------------------------------------------------------------------


class TestMetaReasoningThresholdValidation:
    def test_valid_threshold(self) -> None:
        from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
        eng = MetaReasoningEngine(clock=CLOCK, default_threshold=0.7)
        assert eng._default_threshold == 0.7

    def test_invalid_threshold_rejected(self) -> None:
        from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
        with pytest.raises(ValueError, match="default_threshold"):
            MetaReasoningEngine(clock=CLOCK, default_threshold=1.5)

    def test_negative_threshold_rejected(self) -> None:
        from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
        with pytest.raises(ValueError, match="default_threshold"):
            MetaReasoningEngine(clock=CLOCK, default_threshold=-0.1)
