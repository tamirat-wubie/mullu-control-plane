"""Purpose: governance DSL compiler and evaluator — compiles policy bundles,
detects conflicts, and evaluates rules against request contexts to produce
deterministic, auditable governance decisions.
Governance scope: governance plane core logic only.
Dependencies: governance contracts, autonomy contracts, invariant helpers.
Invariants:
  - Compilation detects conflicts before rules are active.
  - Evaluation is deterministic and side-effect free.
  - Higher-priority rules override lower-priority rules (DENY > ESCALATE > ALLOW).
  - Every evaluation produces an auditable trace.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.governance import (
    CompilationStatus,
    PolicyAction,
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
)
from .invariants import stable_identifier


# ---------------------------------------------------------------------------
# Effect precedence — used to resolve which effect wins when multiple rules fire
# ---------------------------------------------------------------------------

_EFFECT_PRECEDENCE: dict[PolicyEffect, int] = {
    PolicyEffect.DENY: 60,
    PolicyEffect.REQUIRE_APPROVAL: 50,
    PolicyEffect.REQUIRE_REVIEW: 40,
    PolicyEffect.ESCALATE: 30,
    PolicyEffect.REPLAN: 20,
    PolicyEffect.ALLOW: 10,
}


def _effect_rank(effect: PolicyEffect) -> int:
    return _EFFECT_PRECEDENCE.get(effect, 0)


# ---------------------------------------------------------------------------
# Condition evaluator (reuses reaction-engine pattern)
# ---------------------------------------------------------------------------


def evaluate_condition(condition: PolicyCondition, context: Mapping[str, Any]) -> bool:
    """Evaluate a single governance condition against a context mapping.

    Returns True if the condition is satisfied, False otherwise.
    Uses dot-path traversal into nested context dictionaries.
    """
    parts = condition.field_path.split(".")
    current: Any = context
    for part in parts:
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            # Field not found — exists/not_exists handle this; others fail
            if condition.operator == PolicyConditionOperator.NOT_EXISTS:
                return True
            return False

    op = condition.operator
    expected = condition.expected_value

    if op == PolicyConditionOperator.EXISTS:
        return True
    if op == PolicyConditionOperator.NOT_EXISTS:
        return False  # field was found
    if op == PolicyConditionOperator.EQ:
        return current == expected
    if op == PolicyConditionOperator.NEQ:
        return current != expected
    if op == PolicyConditionOperator.CONTAINS:
        if isinstance(current, str) and isinstance(expected, str):
            return expected in current
        if isinstance(current, (list, tuple)):
            return expected in current
        if isinstance(current, Mapping):
            return expected in current
        return False
    if op == PolicyConditionOperator.IN:
        if isinstance(expected, (list, tuple)):
            return current in expected
        return False
    if op == PolicyConditionOperator.MATCHES:
        if isinstance(current, str) and isinstance(expected, str):
            try:
                return bool(re.search(expected, current))
            except re.error:
                return False
        return False

    # Comparison operators — type-safe
    try:
        if op == PolicyConditionOperator.GT:
            return current > expected
        if op == PolicyConditionOperator.GTE:
            return current >= expected
        if op == PolicyConditionOperator.LT:
            return current < expected
        if op == PolicyConditionOperator.LTE:
            return current <= expected
    except TypeError:
        return False  # incompatible types

    return False


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def _scopes_overlap(a: PolicyScope, b: PolicyScope) -> bool:
    """Check if two scopes could potentially overlap."""
    # Global overlaps everything
    if a.kind == PolicyScopeKind.GLOBAL or b.kind == PolicyScopeKind.GLOBAL:
        return True
    # Same kind + same ref = overlap
    if a.kind == b.kind:
        if a.ref_id is None or b.ref_id is None:
            return True  # unspecified ref = wildcard
        return a.ref_id == b.ref_id
    return False


def _detect_conflicts(
    rules: tuple[PolicyRule, ...],
    clock: Callable[[], str],
) -> tuple[PolicyConflict, ...]:
    """Detect conflicts between governance rules."""
    conflicts: list[PolicyConflict] = []
    enabled = [r for r in rules if r.enabled]

    for i, ra in enumerate(enabled):
        for rb in enabled[i + 1:]:
            # Check for contradictory effects in overlapping scopes
            if _scopes_overlap(ra.scope, rb.scope):
                # DENY vs ALLOW on same scope = contradiction
                effects = {ra.effect, rb.effect}
                if PolicyEffect.DENY in effects and PolicyEffect.ALLOW in effects:
                    if ra.priority == rb.priority:
                        conflicts.append(PolicyConflict(
                            conflict_id=stable_identifier("conflict", {
                                "a": ra.rule_id, "b": rb.rule_id, "kind": "contradictory",
                            }),
                            kind=PolicyConflictKind.CONTRADICTORY_EFFECTS,
                            severity=PolicyConflictSeverity.ERROR,
                            rule_ids=(ra.rule_id, rb.rule_id),
                            description=(
                                f"Rules '{ra.rule_id}' and '{rb.rule_id}' have contradictory "
                                f"effects ({ra.effect.value} vs {rb.effect.value}) at the same "
                                f"priority in overlapping scopes"
                            ),
                            detected_at=clock(),
                        ))

                # Priority tie with different effects
                if ra.priority == rb.priority and ra.effect != rb.effect:
                    conflicts.append(PolicyConflict(
                        conflict_id=stable_identifier("conflict", {
                            "a": ra.rule_id, "b": rb.rule_id, "kind": "priority_tie",
                        }),
                        kind=PolicyConflictKind.PRIORITY_TIE,
                        severity=PolicyConflictSeverity.WARNING,
                        rule_ids=(ra.rule_id, rb.rule_id),
                        description=(
                            f"Rules '{ra.rule_id}' and '{rb.rule_id}' have the same priority "
                            f"({ra.priority}) but different effects — resolution uses effect "
                            f"precedence (DENY > ESCALATE > ALLOW)"
                        ),
                        detected_at=clock(),
                    ))

    return tuple(conflicts)


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------


class GovernanceCompiler:
    """Compiles governance bundles — validates rules, detects conflicts,
    and produces a compilation result.

    The compiler is stateless. It takes a bundle and returns a result.
    """

    def __init__(self, clock: Callable[[], str]) -> None:
        self._clock = clock

    def compile(self, bundle: PolicyBundle) -> PolicyCompilationResult:
        """Compile a governance bundle: validate + detect conflicts."""
        warnings: list[str] = []

        # Validate: at least one rule
        if not bundle.rules:
            warnings.append("Bundle contains no rules")

        # Validate: check for disabled rules
        disabled = [r for r in bundle.rules if not r.enabled]
        if disabled:
            warnings.append(f"{len(disabled)} rule(s) are disabled")

        # Detect conflicts
        conflicts = _detect_conflicts(bundle.rules, self._clock)

        # Determine compilation status
        has_fatal = any(c.severity == PolicyConflictSeverity.FATAL for c in conflicts)
        has_error = any(c.severity == PolicyConflictSeverity.ERROR for c in conflicts)

        if has_fatal:
            status = CompilationStatus.FAILED
        elif has_error or warnings:
            status = CompilationStatus.SUCCESS_WITH_WARNINGS
        else:
            status = CompilationStatus.SUCCESS

        now = self._clock()
        return PolicyCompilationResult(
            compilation_id=stable_identifier("compilation", {
                "bundle_id": bundle.bundle_id,
                "version": bundle.version.semver,
                "compiled_at": now,
            }),
            bundle_id=bundle.bundle_id,
            status=status,
            conflicts=conflicts,
            warnings=tuple(warnings),
            compiled_at=now,
            rule_count=len(bundle.rules),
            enabled_rule_count=len(bundle.enabled_rules),
        )


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class GovernanceEvaluator:
    """Evaluates compiled governance bundles against request contexts.

    Produces deterministic, auditable evaluation traces.
    """

    def __init__(self, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._traces: list[PolicyEvaluationTrace] = []

    def evaluate(
        self,
        bundle: PolicyBundle,
        subject_id: str,
        context: Mapping[str, Any],
    ) -> PolicyEvaluationTrace:
        """Evaluate all enabled rules in a bundle against a context.

        Rules are evaluated in priority order (highest first).
        When multiple rules fire, the highest-precedence effect wins
        (DENY > REQUIRE_APPROVAL > REQUIRE_REVIEW > ESCALATE > REPLAN > ALLOW).
        """
        rules = sorted(
            bundle.enabled_rules,
            key=lambda r: (-r.priority, -_effect_rank(r.effect), r.rule_id),
        )

        matched_ids: list[str] = []
        fired_ids: list[str] = []
        fired_actions: list[PolicyAction] = []
        winning_effect = PolicyEffect.ALLOW  # default if no rules match

        for rule in rules:
            # Evaluate all conditions — all must pass for a match
            all_pass = all(
                evaluate_condition(cond, context)
                for cond in rule.conditions
            ) if rule.conditions else True

            if all_pass:
                matched_ids.append(rule.rule_id)

                # Check scope applicability
                if self._scope_applies(rule.scope, context):
                    fired_ids.append(rule.rule_id)
                    fired_actions.extend(rule.actions)

                    # Update winning effect based on precedence
                    if _effect_rank(rule.effect) > _effect_rank(winning_effect):
                        winning_effect = rule.effect

        eval_now = self._clock()
        trace = PolicyEvaluationTrace(
            trace_id=stable_identifier("trace", {
                "bundle_id": bundle.bundle_id,
                "subject_id": subject_id,
                "evaluated_at": eval_now,
            }),
            bundle_id=bundle.bundle_id,
            subject_id=subject_id,
            context_snapshot=context,
            rules_evaluated=len(rules),
            rules_matched=len(matched_ids),
            rules_fired=len(fired_ids),
            matched_rule_ids=tuple(matched_ids),
            fired_rule_ids=tuple(fired_ids),
            final_effect=winning_effect,
            actions_produced=tuple(fired_actions),
            evaluated_at=eval_now,
        )
        self._traces.append(trace)
        return trace

    @staticmethod
    def _scope_applies(scope: PolicyScope, context: Mapping[str, Any]) -> bool:
        """Check if a rule's scope applies to the current evaluation context."""
        if scope.kind == PolicyScopeKind.GLOBAL:
            return True

        scope_key = f"scope.{scope.kind.value}"
        parts = scope_key.split(".")
        current: Any = context
        for part in parts:
            if isinstance(current, Mapping) and part in current:
                current = current[part]
            else:
                # Missing scope context means the scoped rule does not apply.
                return False

        # If scope has a specific ref_id, check it matches
        if scope.ref_id is not None:
            return current == scope.ref_id

        return True

    @property
    def trace_count(self) -> int:
        return len(self._traces)

    def list_traces(self) -> tuple[PolicyEvaluationTrace, ...]:
        return tuple(self._traces)

    def clear_traces(self) -> None:
        self._traces.clear()
