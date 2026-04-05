"""Purpose: governance integration bridge — connects the governance compiler/evaluator
to autonomy, policy, and reaction engines for unified governance enforcement.
Governance scope: governance plane integration only.
Dependencies: governance contracts, governance compiler, autonomy engine, policy engine,
reaction engine, event spine.
Invariants:
  - All bridge methods are stateless static methods (pure orchestration).
  - Governance evaluation precedes execution dispatch.
  - Every governance decision is traceable through evaluation traces.
  - Autonomy mode is derived from governance rules, not hardcoded.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.autonomy import AutonomyMode
from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.governance import (
    CompilationStatus,
    PolicyAction,
    PolicyActionKind,
    PolicyBundle,
    PolicyCompilationResult,
    PolicyCondition,
    PolicyConditionOperator,
    PolicyEffect,
    PolicyEvaluationTrace,
    PolicyRule,
    PolicyScope,
    PolicyScopeKind,
    PolicyVersion,
)
from mcoi_runtime.contracts.reaction import ReactionGateResult, ReactionRule, ReactionVerdict
from .governance_compiler import GovernanceCompiler, GovernanceEvaluator
from .invariants import stable_identifier


class GovernanceBridge:
    """Stateless integration bridge connecting governance to other planes."""

    # -------------------------------------------------------------------
    # Bundle helpers
    # -------------------------------------------------------------------

    @staticmethod
    def create_version(
        major: int,
        minor: int,
        patch: int,
        created_at: str,
        description: str = "",
    ) -> PolicyVersion:
        """Create a governance bundle version."""
        return PolicyVersion(
            version_id=stable_identifier("ver", {
                "major": major, "minor": minor, "patch": patch,
                "created_at": created_at,
            }),
            major=major,
            minor=minor,
            patch=patch,
            created_at=created_at,
            description=description,
        )

    @staticmethod
    def create_bundle(
        name: str,
        rules: tuple[PolicyRule, ...],
        version: PolicyVersion,
        created_at: str,
    ) -> PolicyBundle:
        """Create a governance bundle."""
        return PolicyBundle(
            bundle_id=stable_identifier("bundle", {
                "name": name,
                "version": version.semver,
                "created_at": created_at,
            }),
            name=name,
            version=version,
            rules=rules,
            created_at=created_at,
        )

    # -------------------------------------------------------------------
    # Compile + evaluate
    # -------------------------------------------------------------------

    @staticmethod
    def compile_and_evaluate(
        compiler: GovernanceCompiler,
        evaluator: GovernanceEvaluator,
        bundle: PolicyBundle,
        subject_id: str,
        context: Mapping[str, Any],
    ) -> tuple[PolicyCompilationResult, PolicyEvaluationTrace | None]:
        """Compile a bundle and, if compilation succeeds, evaluate it.

        Returns (compilation_result, trace_or_none).
        If compilation fails, trace is None.
        """
        result = compiler.compile(bundle)
        if not result.succeeded:
            return result, None
        trace = evaluator.evaluate(bundle, subject_id, context)
        return result, trace

    # -------------------------------------------------------------------
    # Autonomy derivation
    # -------------------------------------------------------------------

    @staticmethod
    def derive_autonomy_mode(trace: PolicyEvaluationTrace) -> AutonomyMode:
        """Derive the effective autonomy mode from a governance evaluation trace.

        Maps governance effects to autonomy modes:
          DENY → OBSERVE_ONLY (prevent execution entirely)
          REQUIRE_APPROVAL → APPROVAL_REQUIRED
          REQUIRE_REVIEW / ESCALATE / REPLAN → SUGGEST_ONLY
          ALLOW → BOUNDED_AUTONOMOUS
        """
        _EFFECT_TO_AUTONOMY = {
            PolicyEffect.DENY: AutonomyMode.OBSERVE_ONLY,
            PolicyEffect.REQUIRE_APPROVAL: AutonomyMode.APPROVAL_REQUIRED,
            PolicyEffect.REQUIRE_REVIEW: AutonomyMode.SUGGEST_ONLY,
            PolicyEffect.ESCALATE: AutonomyMode.SUGGEST_ONLY,
            PolicyEffect.REPLAN: AutonomyMode.SUGGEST_ONLY,
            PolicyEffect.ALLOW: AutonomyMode.BOUNDED_AUTONOMOUS,
        }
        return _EFFECT_TO_AUTONOMY.get(trace.final_effect, AutonomyMode.OBSERVE_ONLY)

    # -------------------------------------------------------------------
    # Reaction gate integration
    # -------------------------------------------------------------------

    @staticmethod
    def build_governance_gate(
        evaluator: GovernanceEvaluator,
        bundle: PolicyBundle,
        clock: Callable[[], str],
    ) -> Callable[[EventRecord, ReactionRule], ReactionGateResult]:
        """Build a reaction gate callback that enforces governance rules.

        When a reaction rule fires, this gate evaluates the governance bundle
        against the event context. If governance denies, the reaction is rejected.
        """
        def gate(event: EventRecord, rule: ReactionRule) -> ReactionGateResult:
            context: dict[str, Any] = {
                "event": {
                    "type": event.event_type.value if isinstance(event.event_type, EventType) else str(event.event_type),
                    "source": event.source.value if isinstance(event.source, EventSource) else str(event.source),
                    "correlation_id": event.correlation_id,
                },
                "reaction": {
                    "rule_id": rule.rule_id,
                    "target_kind": rule.target.kind.value,
                    "target_ref_id": rule.target.target_ref_id,
                },
                "payload": dict(event.payload) if isinstance(event.payload, Mapping) else {},
            }

            trace = evaluator.evaluate(bundle, f"reaction:{rule.rule_id}", context)

            # Map governance effect → reaction verdict (exhaustive)
            _EFFECT_TO_VERDICT = {
                PolicyEffect.DENY: ReactionVerdict.REJECT,
                PolicyEffect.REQUIRE_APPROVAL: ReactionVerdict.REQUIRES_APPROVAL,
                PolicyEffect.ESCALATE: ReactionVerdict.ESCALATE,
                PolicyEffect.REPLAN: ReactionVerdict.ESCALATE,
                PolicyEffect.REQUIRE_REVIEW: ReactionVerdict.DEFER,
                PolicyEffect.ALLOW: ReactionVerdict.PROCEED,
            }
            verdict = _EFFECT_TO_VERDICT.get(trace.final_effect, ReactionVerdict.REJECT)

            return ReactionGateResult(
                gate_id=stable_identifier("gov-gate", {
                    "trace_id": trace.trace_id,
                    "rule_id": rule.rule_id,
                }),
                rule_id=rule.rule_id,
                event_id=event.event_id,
                verdict=verdict,
                simulation_safe=verdict != ReactionVerdict.REJECT,
                utility_acceptable=verdict != ReactionVerdict.REJECT,
                meta_reasoning_clear=verdict not in (ReactionVerdict.ESCALATE, ReactionVerdict.REQUIRES_APPROVAL),
                confidence=1.0 if verdict == ReactionVerdict.PROCEED else 0.5,
                reason="governance decision",
                gated_at=clock(),
            )

        return gate

    # -------------------------------------------------------------------
    # Action extraction helpers
    # -------------------------------------------------------------------

    @staticmethod
    def extract_actions(
        trace: PolicyEvaluationTrace,
        kind: PolicyActionKind,
    ) -> tuple[PolicyAction, ...]:
        """Extract all actions of a specific kind from an evaluation trace."""
        return tuple(a for a in trace.actions_produced if a.kind == kind)

    @staticmethod
    def extract_thresholds(trace: PolicyEvaluationTrace) -> Mapping[str, float]:
        """Extract simulation/utility/meta threshold settings from governance actions."""
        thresholds: dict[str, float] = {}
        for action in trace.actions_produced:
            if action.kind == PolicyActionKind.SET_SIMULATION_THRESHOLD:
                val = action.parameters.get("threshold")
                if isinstance(val, (int, float)):
                    thresholds["simulation"] = float(val)
            elif action.kind == PolicyActionKind.SET_UTILITY_THRESHOLD:
                val = action.parameters.get("threshold")
                if isinstance(val, (int, float)):
                    thresholds["utility"] = float(val)
            elif action.kind == PolicyActionKind.SET_META_THRESHOLD:
                val = action.parameters.get("threshold")
                if isinstance(val, (int, float)):
                    thresholds["meta_reasoning"] = float(val)
            elif action.kind == PolicyActionKind.SET_ESCALATION_THRESHOLD:
                val = action.parameters.get("threshold")
                if isinstance(val, (int, float)):
                    thresholds["escalation"] = float(val)
        return MappingProxyType(thresholds)

    @staticmethod
    def extract_provider_decisions(trace: PolicyEvaluationTrace) -> Mapping[str, bool]:
        """Extract provider allow/deny decisions from governance actions.

        Returns immutable mapping {provider_id: True (allowed) | False (denied)}.
        """
        decisions: dict[str, bool] = {}
        for action in trace.actions_produced:
            provider_id = action.parameters.get("provider_id")
            if not isinstance(provider_id, str):
                continue
            if action.kind == PolicyActionKind.ALLOW_PROVIDER:
                decisions[provider_id] = True
            elif action.kind == PolicyActionKind.DENY_PROVIDER:
                decisions[provider_id] = False
        return MappingProxyType(decisions)

    @staticmethod
    def extract_retention_rules(trace: PolicyEvaluationTrace) -> tuple[Mapping[str, Any], ...]:
        """Extract retention rule parameters from governance actions."""
        return tuple(
            a.parameters for a in trace.actions_produced
            if a.kind == PolicyActionKind.SET_RETENTION
        )

    # -------------------------------------------------------------------
    # Rule builder helpers (DSL sugar)
    # -------------------------------------------------------------------

    @staticmethod
    def rule_deny_provider(
        rule_id: str,
        provider_id: str,
        reason: str,
        scope: PolicyScope | None = None,
        priority: int = 0,
    ) -> PolicyRule:
        """Convenience: build a rule that denies a specific provider."""
        return PolicyRule(
            rule_id=rule_id,
            name=f"deny-provider-{provider_id}",
            description=reason,
            effect=PolicyEffect.DENY,
            conditions=(
                PolicyCondition(
                    field_path="provider.id",
                    operator=PolicyConditionOperator.EQ,
                    expected_value=provider_id,
                ),
            ),
            actions=(
                PolicyAction(
                    action_id=f"act-{rule_id}",
                    kind=PolicyActionKind.DENY_PROVIDER,
                    parameters={"provider_id": provider_id},
                ),
            ),
            scope=scope or PolicyScope(scope_id="s-global", kind=PolicyScopeKind.GLOBAL),
            priority=priority,
        )

    @staticmethod
    def rule_require_approval_for_action(
        rule_id: str,
        action_class: str,
        reason: str,
        scope: PolicyScope | None = None,
        priority: int = 0,
    ) -> PolicyRule:
        """Convenience: build a rule that requires approval for an action class."""
        return PolicyRule(
            rule_id=rule_id,
            name=f"require-approval-{action_class}",
            description=reason,
            effect=PolicyEffect.REQUIRE_APPROVAL,
            conditions=(
                PolicyCondition(
                    field_path="action.class",
                    operator=PolicyConditionOperator.EQ,
                    expected_value=action_class,
                ),
            ),
            actions=(
                PolicyAction(
                    action_id=f"act-{rule_id}",
                    kind=PolicyActionKind.SET_APPROVAL_REQUIRED,
                    parameters={"action_class": action_class},
                ),
            ),
            scope=scope or PolicyScope(scope_id="s-global", kind=PolicyScopeKind.GLOBAL),
            priority=priority,
        )

    @staticmethod
    def rule_set_threshold(
        rule_id: str,
        threshold_kind: PolicyActionKind,
        threshold_value: float,
        reason: str,
        scope: PolicyScope | None = None,
        priority: int = 0,
    ) -> PolicyRule:
        """Convenience: build a rule that sets a simulation/utility/meta threshold."""
        return PolicyRule(
            rule_id=rule_id,
            name=f"threshold-{threshold_kind.value}",
            description=reason,
            effect=PolicyEffect.ALLOW,
            conditions=(),
            actions=(
                PolicyAction(
                    action_id=f"act-{rule_id}",
                    kind=threshold_kind,
                    parameters={"threshold": threshold_value},
                ),
            ),
            scope=scope or PolicyScope(scope_id="s-global", kind=PolicyScopeKind.GLOBAL),
            priority=priority,
        )
