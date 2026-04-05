"""Tests for the governance compiler and evaluator engines.

Covers: condition evaluation (all 11 operators), conflict detection,
compilation (success/warning/fail), evaluation (rule matching, priority,
scope filtering, effect precedence), trace recording, and edge cases.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.governance import (
    CompilationStatus,
    PolicyAction,
    PolicyActionKind,
    PolicyBundle,
    PolicyCondition,
    PolicyConditionOperator,
    PolicyConflict,
    PolicyConflictKind,
    PolicyConflictSeverity,
    PolicyEffect,
    PolicyRule,
    PolicyScope,
    PolicyScopeKind,
    PolicyVersion,
)
from mcoi_runtime.core.governance_compiler import (
    GovernanceCompiler,
    GovernanceEvaluator,
    evaluate_condition,
)

NOW = "2026-03-20T12:00:00+00:00"
CLOCK = lambda: NOW  # noqa: E731


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cond(fp: str = "subject.role", op: str = "eq", val: object = "admin") -> PolicyCondition:
    return PolicyCondition(field_path=fp, operator=op, expected_value=val)


def _scope(sid: str = "s1", kind: PolicyScopeKind = PolicyScopeKind.GLOBAL, ref_id: str | None = None) -> PolicyScope:
    return PolicyScope(scope_id=sid, kind=kind, ref_id=ref_id)


def _action(aid: str = "a1", kind: PolicyActionKind = PolicyActionKind.SET_AUTONOMY) -> PolicyAction:
    return PolicyAction(action_id=aid, kind=kind)


def _rule(
    rid: str = "r1",
    effect: PolicyEffect = PolicyEffect.ALLOW,
    conds: tuple = (),
    actions: tuple = (),
    scope: PolicyScope | None = None,
    priority: int = 0,
    enabled: bool = True,
) -> PolicyRule:
    return PolicyRule(
        rule_id=rid, name=f"rule-{rid}", description=f"desc-{rid}",
        effect=effect, conditions=conds or (_cond(),),
        actions=actions or (_action(f"a-{rid}"),),
        scope=scope or _scope(), priority=priority, enabled=enabled,
    )


def _version() -> PolicyVersion:
    return PolicyVersion(version_id="v1", major=1, minor=0, patch=0, created_at=NOW)


def _bundle(rules: tuple[PolicyRule, ...] = ()) -> PolicyBundle:
    return PolicyBundle(
        bundle_id="b1", name="test-bundle", version=_version(),
        rules=rules or (_rule(),), created_at=NOW,
    )


# ---------------------------------------------------------------------------
# Condition evaluation — all 11 operators
# ---------------------------------------------------------------------------


class TestConditionEvaluation:
    def test_eq(self) -> None:
        assert evaluate_condition(_cond("x", "eq", 42), {"x": 42}) is True
        assert evaluate_condition(_cond("x", "eq", 42), {"x": 99}) is False

    def test_neq(self) -> None:
        assert evaluate_condition(_cond("x", "neq", 42), {"x": 99}) is True
        assert evaluate_condition(_cond("x", "neq", 42), {"x": 42}) is False

    def test_gt(self) -> None:
        assert evaluate_condition(_cond("x", "gt", 10), {"x": 20}) is True
        assert evaluate_condition(_cond("x", "gt", 10), {"x": 5}) is False

    def test_gte(self) -> None:
        assert evaluate_condition(_cond("x", "gte", 10), {"x": 10}) is True
        assert evaluate_condition(_cond("x", "gte", 10), {"x": 9}) is False

    def test_lt(self) -> None:
        assert evaluate_condition(_cond("x", "lt", 10), {"x": 5}) is True
        assert evaluate_condition(_cond("x", "lt", 10), {"x": 15}) is False

    def test_lte(self) -> None:
        assert evaluate_condition(_cond("x", "lte", 10), {"x": 10}) is True
        assert evaluate_condition(_cond("x", "lte", 10), {"x": 11}) is False

    def test_contains_string(self) -> None:
        assert evaluate_condition(_cond("x", "contains", "ell"), {"x": "hello"}) is True
        assert evaluate_condition(_cond("x", "contains", "xyz"), {"x": "hello"}) is False

    def test_contains_list(self) -> None:
        assert evaluate_condition(_cond("x", "contains", "a"), {"x": ["a", "b"]}) is True
        assert evaluate_condition(_cond("x", "contains", "z"), {"x": ["a", "b"]}) is False

    def test_in_operator(self) -> None:
        assert evaluate_condition(_cond("x", "in", ["a", "b"]), {"x": "a"}) is True
        assert evaluate_condition(_cond("x", "in", ["a", "b"]), {"x": "z"}) is False

    def test_exists(self) -> None:
        assert evaluate_condition(_cond("x", "exists"), {"x": 1}) is True
        assert evaluate_condition(_cond("missing", "exists"), {"x": 1}) is False

    def test_not_exists(self) -> None:
        assert evaluate_condition(_cond("missing", "not_exists"), {"x": 1}) is True
        assert evaluate_condition(_cond("x", "not_exists"), {"x": 1}) is False

    def test_matches_regex(self) -> None:
        assert evaluate_condition(_cond("x", "matches", r"^admin-\d+$"), {"x": "admin-42"}) is True
        assert evaluate_condition(_cond("x", "matches", r"^admin-\d+$"), {"x": "user-1"}) is False

    def test_matches_invalid_regex(self) -> None:
        assert evaluate_condition(_cond("x", "matches", "[invalid"), {"x": "test"}) is False

    def test_dot_path_traversal(self) -> None:
        ctx = {"subject": {"role": "admin", "team": {"id": "t1"}}}
        assert evaluate_condition(_cond("subject.role", "eq", "admin"), ctx) is True
        assert evaluate_condition(_cond("subject.team.id", "eq", "t1"), ctx) is True

    def test_missing_field_returns_false(self) -> None:
        assert evaluate_condition(_cond("missing.path", "eq", "x"), {}) is False

    def test_type_mismatch_comparison_returns_false(self) -> None:
        assert evaluate_condition(_cond("x", "gt", "text"), {"x": 42}) is False

    def test_contains_non_iterable_returns_false(self) -> None:
        assert evaluate_condition(_cond("x", "contains", "a"), {"x": 42}) is False

    def test_in_non_sequence_returns_false(self) -> None:
        assert evaluate_condition(_cond("x", "in", "not_a_list"), {"x": "a"}) is False


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


class TestCompilation:
    def test_clean_compilation(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        result = compiler.compile(_bundle())
        assert result.status == CompilationStatus.SUCCESS
        assert result.succeeded is True
        assert result.rule_count == 1
        assert result.enabled_rule_count == 1

    def test_empty_bundle_warns(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        b = PolicyBundle(
            bundle_id="b", name="empty", version=_version(),
            rules=(), created_at=NOW,
        )
        result = compiler.compile(b)
        assert result.status == CompilationStatus.SUCCESS_WITH_WARNINGS
        assert any("no rules" in w.lower() for w in result.warnings)

    def test_disabled_rules_warned(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        b = _bundle(rules=(_rule("r1", enabled=False),))
        result = compiler.compile(b)
        assert any("disabled" in w.lower() for w in result.warnings)

    def test_contradictory_effects_detected(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        b = _bundle(rules=(
            _rule("r1", effect=PolicyEffect.ALLOW, priority=0),
            _rule("r2", effect=PolicyEffect.DENY, priority=0),
        ))
        result = compiler.compile(b)
        assert len(result.conflicts) >= 1
        kinds = {c.kind for c in result.conflicts}
        assert PolicyConflictKind.CONTRADICTORY_EFFECTS in kinds

    def test_priority_tie_detected(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        b = _bundle(rules=(
            _rule("r1", effect=PolicyEffect.ALLOW, priority=5),
            _rule("r2", effect=PolicyEffect.ESCALATE, priority=5),
        ))
        result = compiler.compile(b)
        kinds = {c.kind for c in result.conflicts}
        assert PolicyConflictKind.PRIORITY_TIE in kinds

    def test_no_conflict_different_priorities(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        b = _bundle(rules=(
            _rule("r1", effect=PolicyEffect.ALLOW, priority=10),
            _rule("r2", effect=PolicyEffect.DENY, priority=20),
        ))
        result = compiler.compile(b)
        # No contradictory_effects because priorities differ
        contradictory = [c for c in result.conflicts if c.kind == PolicyConflictKind.CONTRADICTORY_EFFECTS]
        assert len(contradictory) == 0

    def test_disabled_rules_not_in_conflict_detection(self) -> None:
        compiler = GovernanceCompiler(clock=CLOCK)
        b = _bundle(rules=(
            _rule("r1", effect=PolicyEffect.ALLOW, priority=0),
            _rule("r2", effect=PolicyEffect.DENY, priority=0, enabled=False),
        ))
        result = compiler.compile(b)
        contradictory = [c for c in result.conflicts if c.kind == PolicyConflictKind.CONTRADICTORY_EFFECTS]
        assert len(contradictory) == 0


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class TestEvaluation:
    def test_single_rule_matches(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        b = _bundle(rules=(_rule("r1", conds=(_cond("subject.role", "eq", "admin"),)),))
        ctx = {"subject": {"role": "admin"}}
        trace = evaluator.evaluate(b, "s1", ctx)
        assert trace.rules_matched == 1
        assert trace.rules_fired == 1
        assert trace.final_effect == PolicyEffect.ALLOW

    def test_no_rules_match(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        b = _bundle(rules=(_rule("r1", conds=(_cond("subject.role", "eq", "admin"),)),))
        ctx = {"subject": {"role": "user"}}
        trace = evaluator.evaluate(b, "s1", ctx)
        assert trace.rules_matched == 0
        assert trace.rules_fired == 0
        assert trace.final_effect == PolicyEffect.ALLOW  # default

    def test_effect_precedence_deny_wins(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        b = _bundle(rules=(
            _rule("r1", effect=PolicyEffect.ALLOW, conds=(_cond("x", "exists"),)),
            _rule("r2", effect=PolicyEffect.DENY, conds=(_cond("x", "exists"),)),
        ))
        trace = evaluator.evaluate(b, "s1", {"x": 1})
        assert trace.final_effect == PolicyEffect.DENY

    def test_effect_precedence_require_approval_over_allow(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        b = _bundle(rules=(
            _rule("r1", effect=PolicyEffect.ALLOW, conds=(_cond("x", "exists"),)),
            _rule("r2", effect=PolicyEffect.REQUIRE_APPROVAL, conds=(_cond("x", "exists"),)),
        ))
        trace = evaluator.evaluate(b, "s1", {"x": 1})
        assert trace.final_effect == PolicyEffect.REQUIRE_APPROVAL

    def test_priority_ordering(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        # Higher priority rules fire first, but effect precedence still applies
        b = _bundle(rules=(
            _rule("r-low", effect=PolicyEffect.DENY, conds=(_cond("x", "exists"),), priority=1),
            _rule("r-high", effect=PolicyEffect.ALLOW, conds=(_cond("x", "exists"),), priority=10),
        ))
        trace = evaluator.evaluate(b, "s1", {"x": 1})
        # DENY still wins because of effect precedence, not priority
        assert trace.final_effect == PolicyEffect.DENY

    def test_disabled_rules_skipped(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        b = _bundle(rules=(
            _rule("r1", effect=PolicyEffect.DENY, conds=(_cond("x", "exists"),), enabled=False),
            _rule("r2", effect=PolicyEffect.ALLOW, conds=(_cond("x", "exists"),)),
        ))
        trace = evaluator.evaluate(b, "s1", {"x": 1})
        assert trace.final_effect == PolicyEffect.ALLOW
        assert "r1" not in trace.matched_rule_ids

    def test_no_conditions_rule_always_matches(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = PolicyRule(
            rule_id="r-unconditional", name="always", description="always matches",
            effect=PolicyEffect.ESCALATE, conditions=(), actions=(_action(),),
            scope=_scope(),
        )
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {})
        assert trace.rules_matched == 1
        assert trace.final_effect == PolicyEffect.ESCALATE

    def test_multiple_conditions_all_must_pass(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule("r1", conds=(
            _cond("subject.role", "eq", "admin"),
            _cond("action.class", "eq", "execute_write"),
        ))
        b = _bundle(rules=(r,))

        # Both pass
        trace = evaluator.evaluate(b, "s1", {
            "subject": {"role": "admin"},
            "action": {"class": "execute_write"},
        })
        assert trace.rules_matched == 1

        # One fails
        trace2 = evaluator.evaluate(b, "s1", {
            "subject": {"role": "admin"},
            "action": {"class": "observe"},
        })
        assert trace2.rules_matched == 0

    def test_scope_filtering(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule(
            "r1",
            scope=PolicyScope(scope_id="s", kind=PolicyScopeKind.TEAM, ref_id="team-alpha"),
            conds=(_cond("x", "exists"),),
        )
        b = _bundle(rules=(r,))

        # Matching scope
        trace = evaluator.evaluate(b, "s1", {"x": 1, "scope": {"team": "team-alpha"}})
        assert trace.rules_fired == 1

        # Non-matching scope — condition matches but scope doesn't
        trace2 = evaluator.evaluate(b, "s1", {"x": 1, "scope": {"team": "team-beta"}})
        assert trace2.rules_matched == 1  # condition matched
        assert trace2.rules_fired == 0  # scope filtered it out

    def test_missing_scope_context_does_not_apply(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        r = _rule(
            "r1",
            scope=PolicyScope(scope_id="s", kind=PolicyScopeKind.TEAM, ref_id="team-alpha"),
            conds=(_cond("x", "exists"),),
        )
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"x": 1})
        assert trace.rules_matched == 1
        assert trace.rules_fired == 0

    def test_actions_collected(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        a1 = PolicyAction(action_id="a1", kind=PolicyActionKind.SET_SIMULATION_THRESHOLD, parameters={"threshold": 0.8})
        a2 = PolicyAction(action_id="a2", kind=PolicyActionKind.SET_UTILITY_THRESHOLD, parameters={"threshold": 0.7})
        r = _rule("r1", actions=(a1, a2), conds=(_cond("x", "exists"),))
        b = _bundle(rules=(r,))
        trace = evaluator.evaluate(b, "s1", {"x": 1})
        assert len(trace.actions_produced) == 2

    def test_trace_recorded(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        b = _bundle()
        evaluator.evaluate(b, "s1", {"subject": {"role": "admin"}})
        evaluator.evaluate(b, "s2", {"subject": {"role": "user"}})
        assert evaluator.trace_count == 2
        traces = evaluator.list_traces()
        assert len(traces) == 2

    def test_clear_traces(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        evaluator.evaluate(_bundle(), "s1", {"subject": {"role": "admin"}})
        evaluator.clear_traces()
        assert evaluator.trace_count == 0

    def test_context_snapshot_captured(self) -> None:
        evaluator = GovernanceEvaluator(clock=CLOCK)
        ctx = {"subject": {"role": "admin"}, "extra": "data"}
        trace = evaluator.evaluate(_bundle(), "s1", ctx)
        # Context is frozen in the trace
        assert trace.context_snapshot is not None
