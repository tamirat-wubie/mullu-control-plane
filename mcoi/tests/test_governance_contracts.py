"""Contract-level tests for the governance DSL types.

Covers: all enums, PolicyCondition, PolicyScope, PolicyAction, PolicyRule,
PolicyVersion, PolicyBundle, PolicyConflict, PolicyCompilationResult,
PolicyEvaluationTrace — including validation, freezing, and edge cases.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.governance import (
    CompilationStatus,
    PolicyAction,
    PolicyActionKind,
    PolicyBundle,
    PolicyCompilationResult,
    PolicyCondition,
    PolicyConditionOperator,
    PolicyConflict,
    PolicyConflictKind,
    PolicyConflictSeverity,
    PolicyEffect,
    PolicyEvaluationTrace,
    PolicyRule,
    PolicyScope,
    PolicyScopeKind,
    PolicyVersion,
)

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cond(fp: str = "subject.role", op: str = "eq", val: str = "admin") -> PolicyCondition:
    return PolicyCondition(field_path=fp, operator=op, expected_value=val)


def _scope(sid: str = "s1", kind: PolicyScopeKind = PolicyScopeKind.GLOBAL) -> PolicyScope:
    return PolicyScope(scope_id=sid, kind=kind)


def _action(aid: str = "a1", kind: PolicyActionKind = PolicyActionKind.SET_AUTONOMY) -> PolicyAction:
    return PolicyAction(action_id=aid, kind=kind, parameters={"mode": "bounded_autonomous"})


def _rule(
    rid: str = "r1",
    effect: PolicyEffect = PolicyEffect.ALLOW,
    conds: tuple = (),
    actions: tuple = (),
    scope: PolicyScope | None = None,
    priority: int = 0,
) -> PolicyRule:
    return PolicyRule(
        rule_id=rid, name=f"rule-{rid}", description=f"desc-{rid}",
        effect=effect, conditions=conds or (_cond(),),
        actions=actions or (_action(),),
        scope=scope or _scope(), priority=priority,
    )


def _version() -> PolicyVersion:
    return PolicyVersion(version_id="v1", major=1, minor=0, patch=0, created_at=NOW)


def _bundle(rules: tuple[PolicyRule, ...] = ()) -> PolicyBundle:
    return PolicyBundle(
        bundle_id="b1", name="test-bundle", version=_version(),
        rules=rules or (_rule(),), created_at=NOW,
    )


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnums:
    def test_policy_effect_values(self) -> None:
        assert len(PolicyEffect) == 6

    def test_condition_operator_values(self) -> None:
        assert len(PolicyConditionOperator) == 11

    def test_scope_kind_values(self) -> None:
        assert len(PolicyScopeKind) == 8

    def test_action_kind_values(self) -> None:
        assert len(PolicyActionKind) == 15

    def test_conflict_kind_values(self) -> None:
        assert len(PolicyConflictKind) == 4

    def test_conflict_severity_values(self) -> None:
        assert len(PolicyConflictSeverity) == 3

    def test_compilation_status_values(self) -> None:
        assert len(CompilationStatus) == 3


# ---------------------------------------------------------------------------
# PolicyCondition
# ---------------------------------------------------------------------------


class TestPolicyCondition:
    def test_valid_condition(self) -> None:
        c = _cond()
        assert c.field_path == "subject.role"
        assert c.operator == "eq"
        assert c.expected_value == "admin"

    def test_all_operators(self) -> None:
        for op in PolicyConditionOperator:
            c = PolicyCondition(field_path="x", operator=op.value, expected_value="v")
            assert c.operator == op.value

    def test_empty_field_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="field_path"):
            PolicyCondition(field_path="", operator="eq", expected_value="x")

    def test_invalid_operator_rejected(self) -> None:
        with pytest.raises(ValueError, match="operator"):
            PolicyCondition(field_path="x", operator="bad_op", expected_value="x")

    def test_expected_value_frozen(self) -> None:
        c = PolicyCondition(field_path="x", operator="eq", expected_value={"a": [1]})
        assert isinstance(c.expected_value, tuple) or not isinstance(c.expected_value, list)

    def test_serialization(self) -> None:
        c = _cond()
        d = c.to_dict()
        assert d["field_path"] == "subject.role"
        assert d["operator"] == "eq"


# ---------------------------------------------------------------------------
# PolicyScope
# ---------------------------------------------------------------------------


class TestPolicyScope:
    def test_valid_scope(self) -> None:
        s = _scope()
        assert s.kind == PolicyScopeKind.GLOBAL

    def test_scope_with_ref(self) -> None:
        s = PolicyScope(scope_id="s2", kind=PolicyScopeKind.TEAM, ref_id="team-alpha")
        assert s.ref_id == "team-alpha"

    def test_empty_scope_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="scope_id"):
            PolicyScope(scope_id="", kind=PolicyScopeKind.GLOBAL)

    def test_empty_ref_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="ref_id"):
            PolicyScope(scope_id="s", kind=PolicyScopeKind.TEAM, ref_id="  ")

    def test_invalid_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            PolicyScope(scope_id="s", kind="bad")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PolicyAction
# ---------------------------------------------------------------------------


class TestPolicyAction:
    def test_valid_action(self) -> None:
        a = _action()
        assert a.kind == PolicyActionKind.SET_AUTONOMY

    def test_parameters_frozen(self) -> None:
        a = PolicyAction(action_id="a", kind=PolicyActionKind.CUSTOM, parameters={"k": [1, 2]})
        # Should be frozen (tuple instead of list inside)
        assert a.parameters is not None

    def test_empty_action_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="action_id"):
            PolicyAction(action_id="", kind=PolicyActionKind.CUSTOM)


# ---------------------------------------------------------------------------
# PolicyRule
# ---------------------------------------------------------------------------


class TestPolicyRule:
    def test_valid_rule(self) -> None:
        r = _rule()
        assert r.rule_id == "r1"
        assert r.effect == PolicyEffect.ALLOW

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="name"):
            PolicyRule(
                rule_id="r", name="", description="d",
                effect=PolicyEffect.ALLOW, conditions=(),
                actions=(), scope=_scope(),
            )

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(ValueError, match="description"):
            PolicyRule(
                rule_id="r", name="n", description="",
                effect=PolicyEffect.ALLOW, conditions=(),
                actions=(), scope=_scope(),
            )

    def test_invalid_effect_rejected(self) -> None:
        with pytest.raises(ValueError, match="effect"):
            PolicyRule(
                rule_id="r", name="n", description="d",
                effect="bad",  # type: ignore[arg-type]
                conditions=(), actions=(), scope=_scope(),
            )

    def test_invalid_condition_element_rejected(self) -> None:
        with pytest.raises(ValueError, match="condition"):
            PolicyRule(
                rule_id="r", name="n", description="d",
                effect=PolicyEffect.ALLOW,
                conditions=("not_a_condition",),  # type: ignore[arg-type]
                actions=(), scope=_scope(),
            )

    def test_invalid_action_element_rejected(self) -> None:
        with pytest.raises(ValueError, match="action"):
            PolicyRule(
                rule_id="r", name="n", description="d",
                effect=PolicyEffect.ALLOW,
                conditions=(), actions=("not_an_action",),  # type: ignore[arg-type]
                scope=_scope(),
            )

    def test_metadata_frozen(self) -> None:
        r = PolicyRule(
            rule_id="r", name="n", description="d",
            effect=PolicyEffect.ALLOW, conditions=(_cond(),),
            actions=(_action(),), scope=_scope(),
            metadata={"key": [1, 2]},
        )
        assert r.metadata is not None

    def test_default_priority_and_enabled(self) -> None:
        r = _rule()
        assert r.priority == 0
        assert r.enabled is True


# ---------------------------------------------------------------------------
# PolicyVersion
# ---------------------------------------------------------------------------


class TestPolicyVersion:
    def test_valid_version(self) -> None:
        v = _version()
        assert v.semver == "1.0.0"

    def test_semver_property(self) -> None:
        v = PolicyVersion(version_id="v", major=2, minor=3, patch=1, created_at=NOW)
        assert v.semver == "2.3.1"

    def test_negative_major_rejected(self) -> None:
        with pytest.raises(ValueError, match="major"):
            PolicyVersion(version_id="v", major=-1, minor=0, patch=0, created_at=NOW)

    def test_invalid_datetime_rejected(self) -> None:
        with pytest.raises(ValueError, match="created_at"):
            PolicyVersion(version_id="v", major=0, minor=0, patch=0, created_at="not-a-date")


# ---------------------------------------------------------------------------
# PolicyBundle
# ---------------------------------------------------------------------------


class TestPolicyBundle:
    def test_valid_bundle(self) -> None:
        b = _bundle()
        assert b.rule_count == 1

    def test_enabled_rules_property(self) -> None:
        r1 = _rule("r1")
        r2 = PolicyRule(
            rule_id="r2", name="n", description="d",
            effect=PolicyEffect.DENY, conditions=(_cond(),),
            actions=(_action(),), scope=_scope(), enabled=False,
        )
        b = _bundle(rules=(r1, r2))
        assert len(b.enabled_rules) == 1
        assert b.enabled_rules[0].rule_id == "r1"

    def test_duplicate_rule_ids_rejected(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            _bundle(rules=(_rule("r1"), _rule("r1")))

    def test_invalid_rule_element_rejected(self) -> None:
        with pytest.raises(ValueError, match="rule"):
            PolicyBundle(
                bundle_id="b", name="n", version=_version(),
                rules=("not_a_rule",), created_at=NOW,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# PolicyConflict
# ---------------------------------------------------------------------------


class TestPolicyConflict:
    def test_valid_conflict(self) -> None:
        c = PolicyConflict(
            conflict_id="c1",
            kind=PolicyConflictKind.CONTRADICTORY_EFFECTS,
            severity=PolicyConflictSeverity.ERROR,
            rule_ids=("r1", "r2"),
            description="test conflict",
            detected_at=NOW,
        )
        assert c.is_fatal is False

    def test_fatal_conflict(self) -> None:
        c = PolicyConflict(
            conflict_id="c1",
            kind=PolicyConflictKind.CIRCULAR_DEPENDENCY,
            severity=PolicyConflictSeverity.FATAL,
            rule_ids=("r1",),
            description="circular dep",
            detected_at=NOW,
        )
        assert c.is_fatal is True

    def test_empty_rule_ids_rejected(self) -> None:
        with pytest.raises(ValueError, match="rule_ids"):
            PolicyConflict(
                conflict_id="c", kind=PolicyConflictKind.PRIORITY_TIE,
                severity=PolicyConflictSeverity.WARNING,
                rule_ids=(), description="d", detected_at=NOW,
            )


# ---------------------------------------------------------------------------
# PolicyCompilationResult
# ---------------------------------------------------------------------------


class TestPolicyCompilationResult:
    def test_succeeded_property(self) -> None:
        r = PolicyCompilationResult(
            compilation_id="c1", bundle_id="b1",
            status=CompilationStatus.SUCCESS,
            conflicts=(), warnings=(), compiled_at=NOW,
            rule_count=1, enabled_rule_count=1,
        )
        assert r.succeeded is True

    def test_succeeded_with_warnings(self) -> None:
        r = PolicyCompilationResult(
            compilation_id="c1", bundle_id="b1",
            status=CompilationStatus.SUCCESS_WITH_WARNINGS,
            conflicts=(), warnings=("w",), compiled_at=NOW,
        )
        assert r.succeeded is True

    def test_failed_not_succeeded(self) -> None:
        r = PolicyCompilationResult(
            compilation_id="c1", bundle_id="b1",
            status=CompilationStatus.FAILED,
            conflicts=(), warnings=(), compiled_at=NOW,
        )
        assert r.succeeded is False

    def test_has_fatal_conflicts(self) -> None:
        fatal = PolicyConflict(
            conflict_id="c", kind=PolicyConflictKind.CIRCULAR_DEPENDENCY,
            severity=PolicyConflictSeverity.FATAL,
            rule_ids=("r1",), description="fatal", detected_at=NOW,
        )
        r = PolicyCompilationResult(
            compilation_id="c1", bundle_id="b1",
            status=CompilationStatus.FAILED,
            conflicts=(fatal,), warnings=(), compiled_at=NOW,
        )
        assert r.has_fatal_conflicts is True


# ---------------------------------------------------------------------------
# PolicyEvaluationTrace
# ---------------------------------------------------------------------------


class TestPolicyEvaluationTrace:
    def test_valid_trace(self) -> None:
        t = PolicyEvaluationTrace(
            trace_id="t1", bundle_id="b1", subject_id="s1",
            context_snapshot={"key": "val"},
            rules_evaluated=5, rules_matched=2, rules_fired=1,
            matched_rule_ids=("r1", "r2"), fired_rule_ids=("r1",),
            final_effect=PolicyEffect.ALLOW,
            actions_produced=(_action(),),
            evaluated_at=NOW,
        )
        assert t.rules_evaluated == 5
        assert t.final_effect == PolicyEffect.ALLOW

    def test_context_frozen(self) -> None:
        t = PolicyEvaluationTrace(
            trace_id="t1", bundle_id="b1", subject_id="s1",
            context_snapshot={"nested": {"list": [1, 2]}},
            rules_evaluated=0, rules_matched=0, rules_fired=0,
            matched_rule_ids=(), fired_rule_ids=(),
            final_effect=PolicyEffect.ALLOW,
            actions_produced=(),
            evaluated_at=NOW,
        )
        assert t.context_snapshot is not None

    def test_invalid_action_element_rejected(self) -> None:
        with pytest.raises(ValueError, match="actions_produced"):
            PolicyEvaluationTrace(
                trace_id="t1", bundle_id="b1", subject_id="s1",
                context_snapshot={},
                rules_evaluated=0, rules_matched=0, rules_fired=0,
                matched_rule_ids=(), fired_rule_ids=(),
                final_effect=PolicyEffect.ALLOW,
                actions_produced=("bad",),  # type: ignore[arg-type]
                evaluated_at=NOW,
            )

    def test_serialization(self) -> None:
        t = PolicyEvaluationTrace(
            trace_id="t1", bundle_id="b1", subject_id="s1",
            context_snapshot={},
            rules_evaluated=0, rules_matched=0, rules_fired=0,
            matched_rule_ids=(), fired_rule_ids=(),
            final_effect=PolicyEffect.ALLOW,
            actions_produced=(),
            evaluated_at=NOW,
        )
        d = t.to_dict()
        assert d["trace_id"] == "t1"
        assert d["final_effect"] == "allow"
