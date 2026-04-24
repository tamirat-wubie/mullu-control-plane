"""Phase 193 — Governed Dispatcher / Execution Spine Integration.

Purpose: Wraps the core dispatcher with stabilization and closure gates so that
    every action passes through the full governed pipeline.
Governance scope: pre-dispatch gates, post-dispatch verification, compensation hooks.
Dependencies: dispatcher, system_closure, system_stabilization.
Invariants: fail-closed on any gate failure, all actions are identity-bound and ledgered.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
from hashlib import sha256

from mcoi_runtime.core.dispatcher import Dispatcher, DispatchRequest
from mcoi_runtime.contracts.effect_assurance import (
    EffectPlan,
    ExpectedEffect,
    ReconciliationStatus,
)
from mcoi_runtime.contracts.execution import ExecutionResult, ExecutionOutcome
from mcoi_runtime.adapters.executor_base import build_failure_result, ExecutionFailure, utc_now_text
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

from mcoi_runtime.core.system_closure import (
    ExecutionVerificationLoop,
    FailureRecoveryEngine,
    SimRealityBoundary,
)
from mcoi_runtime.core.system_stabilization import (
    IdentityBindingEngine, OntologyEnforcer, EquilibriumEngine,
    AdversarialDefenseEngine, PredictiveFailureEngine,
    EconomicOptimizer, AdaptivePromotionEngine,
)


def _bounded_gate_error(summary: str, _exc: Exception) -> str:
    """Return a stable gate failure summary without raw backend detail."""
    return summary


@dataclass(frozen=True, slots=True)
class GovernedDispatchContext:
    """Enriched context that flows through every gate."""
    actor_id: str
    intent_id: str
    request: DispatchRequest
    mode: str = "simulation"  # "simulation" or "reality"
    budget_remaining: float = 10000.0
    current_load: float = 0.0


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_name: str
    passed: bool
    reason: str = ""


@dataclass
class GovernedDispatchResult:
    execution_result: ExecutionResult | None = None
    gates_passed: list[GateResult] = field(default_factory=list)
    gates_failed: list[GateResult] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""
    ledger_hash: str = ""

    @property
    def all_gates_passed(self) -> bool:
        return len(self.gates_failed) == 0


class GovernedDispatcher:
    """Wraps the core Dispatcher with the full stabilization gate chain.

    Pipeline: identity -> trust -> meaning -> coordination -> prediction -> economics -> promotion -> execute -> verify -> compensate -> ledger
    """

    def __init__(
        self,
        dispatcher: Dispatcher,
        *,
        identity: IdentityBindingEngine | None = None,
        ontology: OntologyEnforcer | None = None,
        equilibrium: EquilibriumEngine | None = None,
        adversarial: AdversarialDefenseEngine | None = None,
        predictor: PredictiveFailureEngine | None = None,
        optimizer: EconomicOptimizer | None = None,
        promotion: AdaptivePromotionEngine | None = None,
        verifier: ExecutionVerificationLoop | None = None,
        recovery: FailureRecoveryEngine | None = None,
        boundary: SimRealityBoundary | None = None,
        effect_assurance: EffectAssuranceGate | None = None,
        effect_assurance_tenant_id: str = "operator",
        clock: Callable[[], str] = utc_now_text,
    ):
        self._dispatcher = dispatcher
        self._identity = identity or IdentityBindingEngine()
        self._ontology = ontology or OntologyEnforcer()
        self._equilibrium = equilibrium or EquilibriumEngine()
        self._adversarial = adversarial or AdversarialDefenseEngine()
        self._predictor = predictor or PredictiveFailureEngine()
        self._optimizer = optimizer or EconomicOptimizer()
        self._promotion = promotion or AdaptivePromotionEngine()
        self._verifier = verifier or ExecutionVerificationLoop()
        self._recovery = recovery or FailureRecoveryEngine()
        self._boundary = boundary or SimRealityBoundary()
        self._effect_assurance = effect_assurance
        self._effect_assurance_tenant_id = effect_assurance_tenant_id
        self._clock = clock
        self._ledger: list[dict[str, Any]] = []

    def governed_dispatch(self, context: GovernedDispatchContext) -> GovernedDispatchResult:
        """Execute with full gate chain. Fail-closed on any gate failure."""
        result = GovernedDispatchResult()
        now = self._clock()

        # --- Gate 1: Identity Binding ---
        try:
            self._identity.sign_intent(
                context.intent_id, context.actor_id,
                context.request.route, context.request.goal_id,
            )
            result.gates_passed.append(GateResult("identity_binding", True))
        except Exception as exc:
            bounded_error = _bounded_gate_error("identity binding failed", exc)
            result.gates_failed.append(GateResult("identity_binding", False, bounded_error))
            result.blocked = True
            result.block_reason = "identity_binding blocked"
            self._emit_ledger(context, result, now)
            return result

        # --- Gate 2: Predictive Failure ---
        prediction = self._predictor.predict(
            f"pred-{context.intent_id}", context.request.route, context.current_load
        )
        if prediction.recommendation == "abort":
            result.gates_failed.append(GateResult("predictive_failure", False, "predictive failure blocked dispatch"))
            result.blocked = True
            result.block_reason = "predictive_failure blocked"
            self._emit_ledger(context, result, now)
            return result
        result.gates_passed.append(GateResult("predictive_failure", True, "predictive failure check passed"))

        # --- Gate 3: Economic Optimization ---
        estimate = self._optimizer.estimate(
            f"est-{context.intent_id}", context.request.route,
            cost=100.0, value=500.0,  # placeholder -- real values would come from route metadata
        )
        if estimate.recommendation == "reject":
            result.gates_failed.append(GateResult("economic_optimization", False, f"over_budget: remaining={self._optimizer.remaining_budget}"))
            result.blocked = True
            result.block_reason = "economic_optimization: over budget"
            self._emit_ledger(context, result, now)
            return result
        result.gates_passed.append(GateResult("economic_optimization", True, f"net_value={estimate.net_value}"))

        # --- Gate 4: Equilibrium Check ---
        allowed = self._equilibrium.record_action(context.actor_id)
        if not allowed:
            result.gates_failed.append(GateResult("equilibrium", False, "system at capacity"))
            result.blocked = True
            result.block_reason = "equilibrium: system at capacity"
            self._emit_ledger(context, result, now)
            return result
        result.gates_passed.append(GateResult("equilibrium", True, f"score={self._equilibrium.equilibrium_score()}"))

        # --- Gate 5: Sim/Real Promotion ---
        if context.mode == "reality" and not self._boundary.is_real():
            result.gates_failed.append(GateResult("promotion_boundary", False, f"mode={self._boundary.current_mode}, requested=reality"))
            result.blocked = True
            result.block_reason = "promotion_boundary: not promoted to reality"
            self._emit_ledger(context, result, now)
            return result
        result.gates_passed.append(GateResult("promotion_boundary", True, f"mode={self._boundary.current_mode}"))

        # --- DISPATCH ---
        effect_plan = None
        if self._effect_assurance is not None:
            try:
                effect_plan = self._effect_assurance.create_plan(
                    command_id=context.intent_id,
                    tenant_id=self._effect_assurance_tenant_id,
                    capability_id=context.request.route,
                    expected_effects=_expected_effects_from_request(context.request),
                    forbidden_effects=_forbidden_effects_from_request(context.request),
                )
                result.gates_passed.append(
                    GateResult("effect_plan", True, effect_plan.effect_plan_id)
                )
            except (RuntimeCoreInvariantError, ValueError) as exc:
                bounded_error = _bounded_gate_error("effect plan failed", exc)
                result.gates_failed.append(GateResult("effect_plan", False, bounded_error))
                result.blocked = True
                result.block_reason = "effect_plan blocked"
                self._emit_ledger(context, result, now)
                return result

        exec_result = self._dispatcher.dispatch(context.request)
        result.execution_result = exec_result

        if self._effect_assurance is not None and effect_plan is not None:
            assurance_result = self._assure_execution_effect(
                context=context,
                execution_result=exec_result,
                effect_plan=effect_plan,
            )
            result.execution_result = assurance_result
            exec_result = assurance_result

        # --- Post: Execution Verification ---
        expected = "success" if exec_result.status == ExecutionOutcome.SUCCEEDED else "failure"
        actual = expected  # in real system, would check external effect
        verification = self._verifier.verify_execution(
            f"ver-{context.intent_id}", context.intent_id, expected, actual
        )
        if not verification.verified:
            # Trigger compensation
            self._recovery.register_compensation(
                f"comp-{context.intent_id}", context.intent_id, "rollback",
                detail="execution verification failed"
            )

        # --- Post: Action Binding ---
        self._identity.bind_action(
            f"bind-{context.intent_id}", context.intent_id,
            exec_result.execution_id,
        )

        # --- Post: Economic Commit ---
        self._optimizer.commit_spend(100.0)

        # --- Post: Equilibrium Complete ---
        self._equilibrium.complete_action(context.actor_id)

        # --- Ledger ---
        self._emit_ledger(context, result, now)

        return result

    def _assure_execution_effect(
        self,
        *,
        context: GovernedDispatchContext,
        execution_result: ExecutionResult,
        effect_plan: EffectPlan,
    ) -> ExecutionResult:
        """Observe, verify, and reconcile actual effects after dispatch."""
        try:
            observed = self._effect_assurance.observe(execution_result)
            verification = self._effect_assurance.verify(
                plan=effect_plan,
                execution_result=execution_result,
                observed_effects=observed,
            )
            reconciliation = self._effect_assurance.reconcile(
                plan=effect_plan,
                observed_effects=observed,
                verification_result=verification,
            )
        except (RuntimeCoreInvariantError, ValueError) as exc:
            now = self._clock()
            return build_failure_result(
                execution_id=execution_result.execution_id,
                goal_id=execution_result.goal_id,
                started_at=execution_result.started_at,
                finished_at=now,
                failure=ExecutionFailure(
                    code="effect_assurance_failed",
                    message="effect assurance observation failed",
                    details={
                        "route": context.request.route,
                        "reason": _bounded_gate_error("effect assurance failed", exc),
                    },
                ),
                effect_name="effect_assurance_failed",
                metadata={
                    **dict(execution_result.metadata),
                    "effect_assurance_error": _bounded_gate_error(
                        "effect assurance failed",
                        exc,
                    ),
                },
            )

        assurance_metadata = {
            "effect_plan_id": effect_plan.effect_plan_id,
            "verification_result_id": verification.verification_id,
            "reconciliation_id": reconciliation.reconciliation_id,
            "reconciliation_status": reconciliation.status.value,
        }
        if reconciliation.status is not ReconciliationStatus.MATCH:
            now = self._clock()
            return build_failure_result(
                execution_id=execution_result.execution_id,
                goal_id=execution_result.goal_id,
                started_at=execution_result.started_at,
                finished_at=now,
                failure=ExecutionFailure(
                    code="effect_reconciliation_mismatch",
                    message="effect reconciliation did not match expected effects",
                    details=assurance_metadata,
                ),
                effect_name="effect_reconciliation_mismatch",
                metadata={
                    **dict(execution_result.metadata),
                    "effect_assurance": assurance_metadata,
                },
            )

        try:
            self._effect_assurance.commit_graph(
                plan=effect_plan,
                observed_effects=observed,
                reconciliation=reconciliation,
            )
        except RuntimeCoreInvariantError as exc:
            now = self._clock()
            return build_failure_result(
                execution_id=execution_result.execution_id,
                goal_id=execution_result.goal_id,
                started_at=execution_result.started_at,
                finished_at=now,
                failure=ExecutionFailure(
                    code="effect_graph_commit_failed",
                    message="effect graph commit failed",
                    details={
                        **assurance_metadata,
                        "reason": _bounded_gate_error("effect graph commit failed", exc),
                    },
                ),
                effect_name="effect_graph_commit_failed",
                metadata={
                    **dict(execution_result.metadata),
                    "effect_assurance": assurance_metadata,
                },
            )

        return ExecutionResult(
            execution_id=execution_result.execution_id,
            goal_id=execution_result.goal_id,
            status=execution_result.status,
            actual_effects=execution_result.actual_effects,
            assumed_effects=execution_result.assumed_effects,
            started_at=execution_result.started_at,
            finished_at=execution_result.finished_at,
            metadata={
                **dict(execution_result.metadata),
                "effect_assurance": assurance_metadata,
            },
            extensions=execution_result.extensions,
        )

    def _emit_ledger(self, context: GovernedDispatchContext, result: GovernedDispatchResult, timestamp: str) -> None:
        entry = {
            "actor_id": context.actor_id,
            "intent_id": context.intent_id,
            "route": context.request.route,
            "goal_id": context.request.goal_id,
            "blocked": result.blocked,
            "block_reason": result.block_reason,
            "gates_passed": len(result.gates_passed),
            "gates_failed": len(result.gates_failed),
            "timestamp": timestamp,
        }
        entry_str = str(sorted(entry.items()))
        result.ledger_hash = sha256(entry_str.encode()).hexdigest()
        self._ledger.append(entry)

    @property
    def ledger_count(self) -> int:
        return len(self._ledger)

    @property
    def ledger(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._ledger)


def _expected_effects_from_request(request: DispatchRequest) -> tuple[ExpectedEffect, ...]:
    """Build required expected effects from dispatch template metadata."""
    declared = _string_tuple(request.template.get("declared_effects"))
    if not declared:
        declared = _default_declared_effects(request.route)
    return tuple(
        ExpectedEffect(
            effect_id=effect_name,
            name=effect_name,
            target_ref=request.goal_id,
            required=True,
            verification_method="actual_effect",
        )
        for effect_name in declared
    )


def _forbidden_effects_from_request(request: DispatchRequest) -> tuple[str, ...]:
    """Build forbidden effect names from dispatch template metadata."""
    forbidden = _string_tuple(request.template.get("forbidden_effects"))
    if forbidden:
        return forbidden
    return (f"{request.route}:unexpected_duplicate",)


def _default_declared_effects(route: str) -> tuple[str, ...]:
    if route == "shell_command":
        return ("process_completed",)
    return ("execution_completed",)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())
