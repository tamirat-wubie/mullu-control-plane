"""Purpose: universal governed action kernel for intent-to-evidence execution.
Governance scope: goal, world-state, plan, simulation, capability admission,
    governed dispatch, terminal closure, learning admission, and proof hashes.
Dependencies: goal, plan, simulation, world-state, capability admission,
    governed dispatcher, terminal closure, and closure learning modules.
Invariants:
  - No dispatch occurs without a typed goal, world snapshot, plan, simulation,
    and accepted capability admission.
  - Open world-state contradictions block execution before simulation output is
    treated as actionable.
  - Abort, escalation, approval-required, and missing capability decisions fail closed.
  - Successful dispatch can be closed and admitted to learning only through
    explicit verification, reconciliation, certificate, and memory binding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.effect_assurance import (
    EffectPlan,
    EffectReconciliation,
    ExpectedEffect,
    ReconciliationStatus,
)
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import (
    ExecutionMode,
    ExecutionOutcome,
    ExecutionResult,
    coerce_execution_mode,
)
from mcoi_runtime.contracts.governed_action import (
    AuthorityProofRecord,
    GovernedAction,
    GovernedActionState,
    build_capability_passport,
)
from mcoi_runtime.contracts.life_meaning import (
    AffectedSymbol,
    BoundaryState,
    Delta,
    FeelingStatus,
    ImpactLevel,
    LifeMeaningDecision,
    LifeMeaningJudgment,
    LifeStatus,
)
from mcoi_runtime.contracts.goal import GoalDescriptor, GoalPriority
from mcoi_runtime.contracts.governed_capability_fabric import (
    CommandCapabilityAdmissionDecision,
    CommandCapabilityAdmissionStatus,
)
from mcoi_runtime.contracts.learning import (
    LearningAdmissionDecision,
    LearningAdmissionStatus,
)
from mcoi_runtime.contracts.meta_reasoning import (
    HealthStatus,
    OperatingSubstrateSelfModelProjection,
    SelfModelCapabilityProjection,
)
from mcoi_runtime.contracts.plan import Plan, PlanItem
from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationComparison,
    SimulationOption,
    SimulationRequest,
    SimulationVerdict,
    VerdictType,
)
from mcoi_runtime.contracts.terminal_closure import (
    TerminalClosureCertificate,
    TerminalClosureDisposition,
)
from mcoi_runtime.contracts.verification import (
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)
from mcoi_runtime.contracts.whqr import WHQRDocument
from mcoi_runtime.contracts.world_state import WorldStateSnapshot
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.core.closure_learning import ClosureLearningAdmissionGate
from mcoi_runtime.core.command_capability_admission import (
    CommandCapabilityAdmissionGate,
)
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.governed_dispatcher import (
    GovernedDispatchContext,
    GovernedDispatchResult,
    GovernedDispatcher,
)
from mcoi_runtime.core.intent_ir import (
    IntentCompilationCertificate,
    IntentCompilationError,
    IntentIRCompiler,
)
from mcoi_runtime.core.invariants import (
    RuntimeCoreInvariantError,
    ensure_non_empty_text,
    stable_identifier,
)
from mcoi_runtime.core.life_meaning_governance import judge_life_meaning
from mcoi_runtime.core.memory import MemoryEntry, MemoryTier
from mcoi_runtime.core.simulation import SimulationEngine
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.core.world_state import WorldStateEngine


_BLOCKING_SIMULATION_VERDICTS = frozenset(
    {VerdictType.ABORT, VerdictType.APPROVAL_REQUIRED, VerdictType.ESCALATE}
)


def _coerce_universal_action_execution_mode(mode: ExecutionMode | str) -> ExecutionMode:
    """Normalize legacy action-mode labels to the shared ExecutionMode ABI."""

    if mode == "reality":
        return ExecutionMode.REAL
    if mode == "sandbox":
        return ExecutionMode.TEST
    return coerce_execution_mode(mode)


@dataclass(frozen=True, slots=True)
class UniversalActionRequest:
    """Typed request admitted by the universal action kernel."""

    actor_id: str
    tenant_id: str
    intent_id: str
    objective: str
    dispatch_request: DispatchRequest
    risk_level: RiskLevel = RiskLevel.LOW
    estimated_cost: float = 100.0
    estimated_duration_seconds: float = 1.0
    success_probability: float = 0.9
    mode: ExecutionMode | str = ExecutionMode.SIMULATION
    metadata: Mapping[str, Any] = field(default_factory=dict)
    operating_substrate_projection: OperatingSubstrateSelfModelProjection | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _coerce_universal_action_execution_mode(self.mode).value)
        for field_name in ("actor_id", "tenant_id", "intent_id", "objective", "mode"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        if not isinstance(self.risk_level, RiskLevel):
            raise ValueError("risk_level must be a RiskLevel value")
        if self.estimated_cost < 0:
            raise ValueError("estimated_cost must be non-negative")
        if self.estimated_duration_seconds < 0:
            raise ValueError("estimated_duration_seconds must be non-negative")
        if self.success_probability < 0.0 or self.success_probability > 1.0:
            raise ValueError("success_probability must be between 0.0 and 1.0")
        if self.operating_substrate_projection is not None and not isinstance(
            self.operating_substrate_projection,
            OperatingSubstrateSelfModelProjection,
        ):
            raise ValueError(
                "operating_substrate_projection must be an OperatingSubstrateSelfModelProjection"
            )


@dataclass(frozen=True, slots=True)
class GoalCertificate:
    certificate_id: str
    goal: GoalDescriptor
    issued_at: str


@dataclass(frozen=True, slots=True)
class WorldSupportCertificate:
    certificate_id: str
    snapshot: WorldStateSnapshot
    allows_execution: bool
    reason: str
    evidence_refs: tuple[str, ...]
    issued_at: str


@dataclass(frozen=True, slots=True)
class OperatingSubstrateSupportCertificate:
    certificate_id: str
    projection: OperatingSubstrateSelfModelProjection | None
    capability_id: str
    allows_execution: bool
    reason: str
    evidence_refs: tuple[str, ...]
    issued_at: str


@dataclass(frozen=True, slots=True)
class PlanCertificate:
    certificate_id: str
    plan: Plan
    issued_at: str


@dataclass(frozen=True, slots=True)
class SimulationCertificate:
    certificate_id: str
    request: SimulationRequest
    comparison: SimulationComparison
    verdict: SimulationVerdict
    issued_at: str


@dataclass(frozen=True, slots=True)
class EffectPredictionCertificate:
    certificate_id: str
    plan: EffectPlan
    issued_at: str


@dataclass(frozen=True, slots=True)
class RecoveryPlanCertificate:
    certificate_id: str
    recovery_plan_id: str
    effect_plan_id: str
    rollback_plan_id: str
    compensation_plan_id: str
    recovery_kind: str
    review_required_on_failure: bool
    issued_at: str


@dataclass(frozen=True, slots=True)
class UniversalActionResult:
    """Terminal result for one universal governed action attempt."""

    action_id: str
    blocked: bool
    block_reason: str
    action_envelope: Mapping[str, Any]
    trace_ref: str
    admission_receipt_ref: str
    execution_receipt_ref: str | None
    closure_state: str
    goal_certificate: GoalCertificate
    world_certificate: WorldSupportCertificate
    plan_certificate: PlanCertificate | None = None
    simulation_certificate: SimulationCertificate | None = None
    effect_prediction_certificate: EffectPredictionCertificate | None = None
    recovery_plan_certificate: RecoveryPlanCertificate | None = None
    intent_certificate: IntentCompilationCertificate | None = None
    operating_substrate_certificate: OperatingSubstrateSupportCertificate | None = None
    capability_decision: CommandCapabilityAdmissionDecision | None = None
    governed_action: GovernedAction | None = None
    dispatch_result: GovernedDispatchResult | None = None
    terminal_certificate: TerminalClosureCertificate | None = None
    learning_decision: LearningAdmissionDecision | None = None
    life_meaning_judgment: LifeMeaningJudgment | None = None
    proof_hash: str = ""

    @property
    def dispatched(self) -> bool:
        return self.dispatch_result is not None and not self.blocked


class UniversalActionKernel:
    """Compose core runtime planes into one fail-closed action path."""

    def __init__(
        self,
        *,
        world_state: WorldStateEngine,
        simulator: SimulationEngine,
        capability_admission: CommandCapabilityAdmissionGate,
        governed_dispatcher: GovernedDispatcher,
        terminal_closure: TerminalClosureCertifier | None = None,
        learning_admission: ClosureLearningAdmissionGate | None = None,
        intent_compiler: IntentIRCompiler | None = None,
        clock: Callable[[], str],
    ) -> None:
        self._world_state = world_state
        self._simulator = simulator
        self._capability_admission = capability_admission
        self._governed_dispatcher = governed_dispatcher
        self._terminal_closure = terminal_closure
        self._learning_admission = learning_admission
        self._intent_compiler = intent_compiler or IntentIRCompiler()
        self._clock = clock

    def run(self, request: UniversalActionRequest) -> UniversalActionResult:
        """Run goal, world, plan, simulation, capability, dispatch, and closure gates."""
        now = self._clock()
        action_id = stable_identifier(
            "universal-action",
            {
                "tenant_id": request.tenant_id,
                "intent_id": request.intent_id,
                "route": request.dispatch_request.route,
            },
        )
        trace_ref = _build_trace_ref(request=request, action_id=action_id)
        goal_certificate = self._build_goal_certificate(request, now)
        world_certificate = self._build_world_certificate(request, now)
        if not world_certificate.allows_execution:
            return self._blocked(
                action_id=action_id,
                request=request,
                issued_at=now,
                trace_ref=trace_ref,
                block_reason=world_certificate.reason,
                goal_certificate=goal_certificate,
                world_certificate=world_certificate,
            )

        try:
            intent_certificate = self._compile_intent(request=request, issued_at=now)
        except IntentCompilationError:
            return self._blocked(
                action_id=action_id,
                request=request,
                issued_at=now,
                trace_ref=trace_ref,
                block_reason="intent_compilation_rejected",
                goal_certificate=goal_certificate,
                world_certificate=world_certificate,
            )

        capability_decision = self._capability_admission.admit(
            command_id=intent_certificate.typed_intent.command_id,
            intent_name=intent_certificate.typed_intent.intent_name,
        )
        if capability_decision.status is not CommandCapabilityAdmissionStatus.ACCEPTED:
            return self._blocked(
                action_id=action_id,
                request=request,
                issued_at=now,
                trace_ref=trace_ref,
                block_reason="capability_admission_rejected",
                goal_certificate=goal_certificate,
                world_certificate=world_certificate,
                intent_certificate=intent_certificate,
                capability_decision=capability_decision,
            )

        operating_substrate_certificate = self._build_operating_substrate_certificate(
            request=request,
            capability_decision=capability_decision,
            issued_at=now,
        )
        if (
            operating_substrate_certificate is not None
            and not operating_substrate_certificate.allows_execution
        ):
            return self._blocked(
                action_id=action_id,
                request=request,
                issued_at=now,
                trace_ref=trace_ref,
                block_reason=operating_substrate_certificate.reason,
                goal_certificate=goal_certificate,
                world_certificate=world_certificate,
                intent_certificate=intent_certificate,
                capability_decision=capability_decision,
                operating_substrate_certificate=operating_substrate_certificate,
            )

        try:
            governed_action = self._build_governed_action(
                request=request,
                intent_certificate=intent_certificate,
                capability_decision=capability_decision,
                issued_at=now,
            )
        except (RuntimeCoreInvariantError, ValueError) as exc:
            return self._blocked(
                action_id=action_id,
                request=request,
                issued_at=now,
                trace_ref=trace_ref,
                block_reason=(
                    "recovery_plan_missing"
                    if "requires rollback or compensation" in str(exc)
                    else "governed_action_admission_rejected"
                ),
                goal_certificate=goal_certificate,
                world_certificate=world_certificate,
                intent_certificate=intent_certificate,
                operating_substrate_certificate=operating_substrate_certificate,
                capability_decision=capability_decision,
            )

        plan_certificate = self._build_plan_certificate(
            request=request,
            world_certificate=world_certificate,
            capability_decision=capability_decision,
            governed_action=governed_action,
            issued_at=now,
        )
        effect_prediction_certificate = self._build_effect_prediction_certificate(
            request=request,
            governed_action=governed_action,
            issued_at=now,
        )
        recovery_plan_certificate = self._build_recovery_plan_certificate(
            governed_action=governed_action,
            effect_prediction_certificate=effect_prediction_certificate,
            issued_at=now,
        )
        simulation_certificate = self._build_simulation_certificate(
            request=request,
            plan_certificate=plan_certificate,
            issued_at=now,
        )
        if simulation_certificate.verdict.verdict_type in _BLOCKING_SIMULATION_VERDICTS:
            return self._blocked(
                action_id=action_id,
                request=request,
                issued_at=now,
                trace_ref=trace_ref,
                block_reason=f"simulation_{simulation_certificate.verdict.verdict_type.value}",
                goal_certificate=goal_certificate,
                world_certificate=world_certificate,
                plan_certificate=plan_certificate,
                simulation_certificate=simulation_certificate,
                effect_prediction_certificate=effect_prediction_certificate,
                recovery_plan_certificate=recovery_plan_certificate,
                intent_certificate=intent_certificate,
                operating_substrate_certificate=operating_substrate_certificate,
                capability_decision=capability_decision,
                governed_action=governed_action,
            )

        life_meaning_judgment = self._build_life_meaning_preflight_judgment(
            action_id=action_id,
            request=request,
            issued_at=now,
            trace_ref=trace_ref,
            goal_certificate=goal_certificate,
            world_certificate=world_certificate,
            plan_certificate=plan_certificate,
            simulation_certificate=simulation_certificate,
            effect_prediction_certificate=effect_prediction_certificate,
            recovery_plan_certificate=recovery_plan_certificate,
            intent_certificate=intent_certificate,
            operating_substrate_certificate=operating_substrate_certificate,
            capability_decision=capability_decision,
            governed_action=governed_action,
        )
        if life_meaning_judgment.decision is not LifeMeaningDecision.PASS:
            return self._blocked(
                action_id=action_id,
                request=request,
                issued_at=now,
                trace_ref=trace_ref,
                block_reason=f"life_meaning_judgment_{life_meaning_judgment.decision.value}",
                goal_certificate=goal_certificate,
                world_certificate=world_certificate,
                plan_certificate=plan_certificate,
                simulation_certificate=simulation_certificate,
                effect_prediction_certificate=effect_prediction_certificate,
                recovery_plan_certificate=recovery_plan_certificate,
                intent_certificate=intent_certificate,
                operating_substrate_certificate=operating_substrate_certificate,
                capability_decision=capability_decision,
                governed_action=governed_action,
                decision_status=_life_meaning_decision_status(life_meaning_judgment),
                life_meaning_judgment=life_meaning_judgment,
            )

        dispatch_result = self._governed_dispatcher.governed_dispatch(
            GovernedDispatchContext(
                actor_id=request.actor_id,
                intent_id=request.intent_id,
                request=request.dispatch_request,
                mode=request.mode,
            )
        )
        terminal_certificate, learning_decision = self._close_and_admit_learning(
            request=request,
            dispatch_result=dispatch_result,
            capability_decision=capability_decision,
            effect_prediction_certificate=effect_prediction_certificate,
        )
        result = UniversalActionResult(
            action_id=action_id,
            blocked=dispatch_result.blocked,
            block_reason=dispatch_result.block_reason,
            action_envelope=_build_action_envelope(
                request=request,
                issued_at=now,
                capability_decision=capability_decision,
            ),
            trace_ref=trace_ref,
            admission_receipt_ref=_build_admission_receipt_ref(
                action_id=action_id,
                trace_ref=trace_ref,
                decision_status="block" if dispatch_result.blocked else "allow",
                life_meaning_judgment_id=life_meaning_judgment.judgment_id,
            ),
            execution_receipt_ref=_build_execution_receipt_ref(
                request=request,
                trace_ref=trace_ref,
                dispatch_result=dispatch_result,
            ),
            closure_state=_build_closure_state(
                blocked=dispatch_result.blocked,
                dispatch_result=dispatch_result,
                terminal_certificate=terminal_certificate,
            ),
            goal_certificate=goal_certificate,
            world_certificate=world_certificate,
            plan_certificate=plan_certificate,
            simulation_certificate=simulation_certificate,
            effect_prediction_certificate=effect_prediction_certificate,
            recovery_plan_certificate=recovery_plan_certificate,
            intent_certificate=intent_certificate,
            operating_substrate_certificate=operating_substrate_certificate,
            capability_decision=capability_decision,
            governed_action=governed_action,
            dispatch_result=dispatch_result,
            terminal_certificate=terminal_certificate,
            learning_decision=learning_decision,
            life_meaning_judgment=life_meaning_judgment,
        )
        return self._with_proof_hash(result)

    def _build_goal_certificate(
        self, request: UniversalActionRequest, issued_at: str
    ) -> GoalCertificate:
        priority = (
            GoalPriority.HIGH
            if request.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
            else GoalPriority.NORMAL
        )
        goal = GoalDescriptor(
            goal_id=request.dispatch_request.goal_id,
            description=request.objective,
            priority=priority,
            created_at=issued_at,
            metadata={
                "tenant_id": request.tenant_id,
                "intent_id": request.intent_id,
                "route": request.dispatch_request.route,
            },
        )
        return GoalCertificate(
            certificate_id=stable_identifier(
                "goal-cert", {"goal_id": goal.goal_id, "issued_at": issued_at}
            ),
            goal=goal,
            issued_at=issued_at,
        )

    def _build_world_certificate(
        self, request: UniversalActionRequest, issued_at: str
    ) -> WorldSupportCertificate:
        snapshot = self._world_state.assemble_snapshot()
        allows_execution = len(snapshot.unresolved_contradictions) == 0
        reason = (
            "world_state_supports_execution"
            if allows_execution
            else "open_world_contradictions"
        )
        evidence_refs = _world_support_evidence_refs(snapshot=snapshot, reason=reason)
        return WorldSupportCertificate(
            certificate_id=stable_identifier(
                "world-support-cert",
                {
                    "intent_id": request.intent_id,
                    "snapshot_id": snapshot.snapshot_id,
                    "issued_at": issued_at,
                },
            ),
            snapshot=snapshot,
            allows_execution=allows_execution,
            reason=reason,
            evidence_refs=evidence_refs,
            issued_at=issued_at,
        )

    def _build_operating_substrate_certificate(
        self,
        *,
        request: UniversalActionRequest,
        capability_decision: CommandCapabilityAdmissionDecision,
        issued_at: str,
    ) -> OperatingSubstrateSupportCertificate | None:
        projection_required = _operating_substrate_projection_required(request)
        projection = request.operating_substrate_projection
        capability_id = capability_decision.capability_id
        if projection is None:
            if not projection_required:
                return None
            return OperatingSubstrateSupportCertificate(
                certificate_id=stable_identifier(
                    "operating-substrate-support-cert",
                    {
                        "intent_id": request.intent_id,
                        "capability_id": capability_id,
                        "projection_id": "missing",
                        "issued_at": issued_at,
                    },
                ),
                projection=None,
                capability_id=capability_id,
                allows_execution=False,
                reason="operating_substrate_self_model_missing",
                evidence_refs=("operating-substrate://projection/missing",),
                issued_at=issued_at,
            )

        matched_capability = _operating_substrate_capability(
            projection=projection,
            capability_id=capability_id,
            route=request.dispatch_request.route,
        )
        reason = _operating_substrate_support_reason(
            projection=projection,
            matched_capability=matched_capability,
        )
        allows_execution = reason == "operating_substrate_supports_execution"
        evidence_refs = _operating_substrate_evidence_refs(
            projection=projection,
            matched_capability=matched_capability,
            reason=reason,
        )
        return OperatingSubstrateSupportCertificate(
            certificate_id=stable_identifier(
                "operating-substrate-support-cert",
                {
                    "intent_id": request.intent_id,
                    "capability_id": capability_id,
                    "projection_id": projection.projection_id,
                    "reason": reason,
                    "issued_at": issued_at,
                },
            ),
            projection=projection,
            capability_id=capability_id,
            allows_execution=allows_execution,
            reason=reason,
            evidence_refs=evidence_refs,
            issued_at=issued_at,
        )

    def _build_plan_certificate(
        self,
        *,
        request: UniversalActionRequest,
        world_certificate: WorldSupportCertificate,
        capability_decision: CommandCapabilityAdmissionDecision,
        governed_action: GovernedAction,
        issued_at: str,
    ) -> PlanCertificate:
        plan_item = PlanItem(
            item_id=f"step-{request.intent_id}-dispatch",
            description="Dispatch through governed capability",
            order=0,
        )
        plan = Plan(
            plan_id=stable_identifier(
                "plan", {"intent_id": request.intent_id, "issued_at": issued_at}
            ),
            goal_id=request.dispatch_request.goal_id,
            state_hash=world_certificate.snapshot.state_hash,
            registry_hash=stable_identifier(
                "capability-registry",
                {
                    "capability_id": capability_decision.capability_id,
                    "decided_at": capability_decision.decided_at,
                },
            ),
            items=(plan_item,),
            status="certified",
            objective=request.objective,
            created_at=issued_at,
            updated_at=issued_at,
            metadata={
                "tenant_id": request.tenant_id,
                "route": request.dispatch_request.route,
                "capability_id": capability_decision.capability_id,
                "governed_action_id": governed_action.governed_action_id,
                "evidence_required": capability_decision.evidence_required,
            },
        )
        return PlanCertificate(
            certificate_id=stable_identifier(
                "plan-cert", {"plan_id": plan.plan_id, "issued_at": issued_at}
            ),
            plan=plan,
            issued_at=issued_at,
        )

    def _build_simulation_certificate(
        self,
        *,
        request: UniversalActionRequest,
        plan_certificate: PlanCertificate,
        issued_at: str,
    ) -> SimulationCertificate:
        option = SimulationOption(
            option_id=f"option-{request.intent_id}-dispatch",
            label=request.dispatch_request.route,
            risk_level=request.risk_level,
            estimated_cost=request.estimated_cost,
            estimated_duration_seconds=request.estimated_duration_seconds,
            success_probability=request.success_probability,
        )
        simulation_request = SimulationRequest(
            request_id=stable_identifier(
                "sim-request", {"plan_id": plan_certificate.plan.plan_id}
            ),
            context_type="plan",
            context_id=plan_certificate.plan.plan_id,
            description="Dry-run governed action plan",
            options=(option,),
        )
        comparison, verdict = self._simulator.full_simulation(
            simulation_request,
            obligation_count=0,
        )
        return SimulationCertificate(
            certificate_id=stable_identifier(
                "simulation-cert",
                {
                    "request_id": simulation_request.request_id,
                    "verdict_id": verdict.verdict_id,
                    "issued_at": issued_at,
                },
            ),
            request=simulation_request,
            comparison=comparison,
            verdict=verdict,
            issued_at=issued_at,
        )

    def _blocked(
        self,
        *,
        action_id: str,
        request: UniversalActionRequest,
        issued_at: str,
        trace_ref: str,
        block_reason: str,
        goal_certificate: GoalCertificate,
        world_certificate: WorldSupportCertificate,
        plan_certificate: PlanCertificate | None = None,
        simulation_certificate: SimulationCertificate | None = None,
        effect_prediction_certificate: EffectPredictionCertificate | None = None,
        recovery_plan_certificate: RecoveryPlanCertificate | None = None,
        capability_decision: CommandCapabilityAdmissionDecision | None = None,
        governed_action: GovernedAction | None = None,
        intent_certificate: IntentCompilationCertificate | None = None,
        operating_substrate_certificate: OperatingSubstrateSupportCertificate | None = None,
        decision_status: str = "block",
        life_meaning_judgment: LifeMeaningJudgment | None = None,
    ) -> UniversalActionResult:
        result = UniversalActionResult(
            action_id=action_id,
            blocked=True,
            block_reason=block_reason,
            action_envelope=_build_action_envelope(
                request=request,
                issued_at=issued_at,
                capability_decision=capability_decision,
            ),
            trace_ref=trace_ref,
            admission_receipt_ref=_build_admission_receipt_ref(
                action_id=action_id,
                trace_ref=trace_ref,
                decision_status=decision_status,
                life_meaning_judgment_id=f"life-meaning:{action_id}",
            ),
            execution_receipt_ref=None,
            closure_state=_blocked_closure_state(decision_status),
            goal_certificate=goal_certificate,
            world_certificate=world_certificate,
            plan_certificate=plan_certificate,
            simulation_certificate=simulation_certificate,
            effect_prediction_certificate=effect_prediction_certificate,
            recovery_plan_certificate=recovery_plan_certificate,
            intent_certificate=intent_certificate,
            operating_substrate_certificate=operating_substrate_certificate,
            capability_decision=capability_decision,
            governed_action=governed_action,
            life_meaning_judgment=life_meaning_judgment,
        )
        if result.life_meaning_judgment is not None:
            result = replace(
                result,
                life_meaning_judgment=_life_meaning_judgment_with_admission_ref(
                    result.life_meaning_judgment,
                    result.admission_receipt_ref,
                ),
            )
        if result.life_meaning_judgment is None:
            result = replace(
                result,
                life_meaning_judgment=self._build_life_meaning_result_judgment(
                    request=request,
                    result=result,
                    decision=_uao_record_decision(result),
                ),
            )
        return self._with_proof_hash(result)

    def _build_life_meaning_preflight_judgment(
        self,
        *,
        action_id: str,
        request: UniversalActionRequest,
        issued_at: str,
        trace_ref: str,
        goal_certificate: GoalCertificate,
        world_certificate: WorldSupportCertificate,
        plan_certificate: PlanCertificate,
        simulation_certificate: SimulationCertificate,
        effect_prediction_certificate: EffectPredictionCertificate,
        recovery_plan_certificate: RecoveryPlanCertificate,
        intent_certificate: IntentCompilationCertificate,
        operating_substrate_certificate: OperatingSubstrateSupportCertificate | None,
        capability_decision: CommandCapabilityAdmissionDecision,
        governed_action: GovernedAction,
    ) -> LifeMeaningJudgment:
        provisional_result = UniversalActionResult(
            action_id=action_id,
            blocked=False,
            block_reason="",
            action_envelope=_build_action_envelope(
                request=request,
                issued_at=issued_at,
                capability_decision=capability_decision,
            ),
            trace_ref=trace_ref,
            admission_receipt_ref=_build_admission_receipt_ref(
                action_id=action_id,
                trace_ref=trace_ref,
                decision_status="allow",
                life_meaning_judgment_id=f"life-meaning:{action_id}",
            ),
            execution_receipt_ref=None,
            closure_state="closed_deferred",
            goal_certificate=goal_certificate,
            world_certificate=world_certificate,
            plan_certificate=plan_certificate,
            simulation_certificate=simulation_certificate,
            effect_prediction_certificate=effect_prediction_certificate,
            recovery_plan_certificate=recovery_plan_certificate,
            intent_certificate=intent_certificate,
            operating_substrate_certificate=operating_substrate_certificate,
            capability_decision=capability_decision,
            governed_action=governed_action,
        )
        return self._build_life_meaning_result_judgment(
            request=request,
            result=provisional_result,
            decision={
                "status": "allow",
                "reason_code": "life_meaning_preflight",
                "proof_state": "Pass",
                "solver_outcome": "SolvedUnverified",
                "next_action": "governed_dispatch",
                "execution_allowed": True,
            },
        )

    def _build_life_meaning_result_judgment(
        self,
        *,
        request: UniversalActionRequest,
        result: UniversalActionResult,
        decision: Mapping[str, Any],
    ) -> LifeMeaningJudgment:
        action_envelope = _uao_record_action_envelope(request=request, result=result)
        evidence_refs = _uao_record_evidence_refs(
            result=result,
            action_envelope=action_envelope,
        )
        policy_refs = _uao_record_policy_refs(request=request, result=result)
        effect_classes = _uao_record_effect_classes(result)
        return _build_life_meaning_judgment(
            request=request,
            result=result,
            decision=decision,
            effect_classes=effect_classes,
            evidence_refs=evidence_refs,
            policy_refs=policy_refs,
        )

    def _compile_intent(
        self,
        *,
        request: UniversalActionRequest,
        issued_at: str,
    ) -> IntentCompilationCertificate:
        return self._intent_compiler.compile(
            actor_id=request.actor_id,
            tenant_id=request.tenant_id,
            command_id=request.intent_id,
            objective=request.objective,
            dispatch_request=request.dispatch_request,
            risk=request.risk_level.value,
            mode=request.mode,
            issued_at=issued_at,
        )

    def _build_governed_action(
        self,
        *,
        request: UniversalActionRequest,
        intent_certificate: IntentCompilationCertificate,
        capability_decision: CommandCapabilityAdmissionDecision,
        issued_at: str,
    ) -> GovernedAction:
        capability_entry = self._capability_admission.capability_for_intent(
            intent_certificate.typed_intent.intent_name
        )
        passport_hash = stable_identifier(
            "capability-passport",
            {
                "capability_id": capability_entry.capability_id,
                "version": capability_entry.version,
                "input_schema_ref": capability_entry.input_schema_ref,
                "output_schema_ref": capability_entry.output_schema_ref,
                "expected_effects": capability_entry.effect_model.expected_effects,
                "required_roles": capability_entry.authority_policy.required_roles,
            },
        )
        capability_passport = build_capability_passport(
            capability_entry,
            passport_hash=passport_hash,
        )
        authority_proof = AuthorityProofRecord(
            actor_id=request.actor_id,
            tenant_id=request.tenant_id,
            required_roles=capability_passport.required_roles,
            actor_roles=_text_tuple_from_metadata(request.metadata, "actor_roles"),
            approval_chain=capability_passport.approval_chain,
            approval_refs=_text_tuple_from_metadata(request.metadata, "approval_refs"),
            approval_actor_ids=_text_tuple_from_metadata(
                request.metadata, "approval_actor_ids"
            ),
            separation_of_duty=capability_passport.separation_of_duty,
        )
        return GovernedAction(
            governed_action_id=stable_identifier(
                "governed-action",
                {
                    "tenant_id": request.tenant_id,
                    "actor_id": request.actor_id,
                    "intent_id": request.intent_id,
                    "capability_id": capability_decision.capability_id,
                    "intent_hash": intent_certificate.intent_hash,
                    "passport_hash": passport_hash,
                },
            ),
            command_id=request.intent_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            typed_intent=intent_certificate.typed_intent,
            capability_passport=capability_passport,
            authority_proof=authority_proof,
            state=GovernedActionState.ADMITTED,
            issued_at=issued_at,
            metadata={
                "capability_decision_reason": capability_decision.reason,
                "domain": capability_decision.domain,
                "owner_team": capability_decision.owner_team,
                "intent_compilation_certificate": intent_certificate.certificate_id,
                "intent_hash": intent_certificate.intent_hash,
                "intent_schema": intent_certificate.intent_schema,
            },
        )

    def _build_effect_prediction_certificate(
        self,
        *,
        request: UniversalActionRequest,
        governed_action: GovernedAction,
        issued_at: str,
    ) -> EffectPredictionCertificate:
        passport = governed_action.capability_passport
        plan = EffectPlan(
            effect_plan_id=stable_identifier(
                "universal-effect-plan",
                {
                    "intent_id": request.intent_id,
                    "capability_id": passport.capability_id,
                    "passport_hash": passport.passport_hash,
                },
            ),
            command_id=request.intent_id,
            tenant_id=request.tenant_id,
            capability_id=passport.capability_id,
            expected_effects=tuple(
                ExpectedEffect(
                    effect_id=stable_identifier(
                        "universal-expected-effect",
                        {
                            "intent_id": request.intent_id,
                            "capability_id": passport.capability_id,
                            "name": effect_name,
                        },
                    ),
                    name=effect_name,
                    target_ref=f"capability://{passport.capability_id}",
                    required=True,
                    verification_method="execution_receipt_reconciliation",
                )
                for effect_name in passport.expected_effects
            ),
            forbidden_effects=passport.forbidden_effects,
            rollback_plan_id=passport.rollback_capability or None,
            compensation_plan_id=passport.compensation_capability or None,
            graph_node_refs=(
                f"command://{request.intent_id}",
                f"capability://{passport.capability_id}",
            ),
            graph_edge_refs=(
                f"command://{request.intent_id}->capability://{passport.capability_id}",
            ),
            created_at=issued_at,
        )
        return EffectPredictionCertificate(
            certificate_id=stable_identifier(
                "effect-prediction-cert",
                {
                    "effect_plan_id": plan.effect_plan_id,
                    "command_id": plan.command_id,
                    "created_at": plan.created_at,
                },
            ),
            plan=plan,
            issued_at=issued_at,
        )

    def _build_recovery_plan_certificate(
        self,
        *,
        governed_action: GovernedAction,
        effect_prediction_certificate: EffectPredictionCertificate,
        issued_at: str,
    ) -> RecoveryPlanCertificate:
        passport = governed_action.capability_passport
        rollback_plan_id = passport.rollback_capability
        compensation_plan_id = passport.compensation_capability
        if rollback_plan_id and compensation_plan_id:
            recovery_kind = "rollback_and_compensation"
        elif rollback_plan_id:
            recovery_kind = "rollback"
        else:
            recovery_kind = "compensation"
        recovery_plan_id = stable_identifier(
            "universal-recovery-plan",
            {
                "governed_action_id": governed_action.governed_action_id,
                "effect_plan_id": effect_prediction_certificate.plan.effect_plan_id,
                "rollback_plan_id": rollback_plan_id,
                "compensation_plan_id": compensation_plan_id,
            },
        )
        return RecoveryPlanCertificate(
            certificate_id=stable_identifier(
                "recovery-plan-cert",
                {
                    "recovery_plan_id": recovery_plan_id,
                    "effect_plan_id": effect_prediction_certificate.plan.effect_plan_id,
                    "issued_at": issued_at,
                },
            ),
            recovery_plan_id=recovery_plan_id,
            effect_plan_id=effect_prediction_certificate.plan.effect_plan_id,
            rollback_plan_id=rollback_plan_id,
            compensation_plan_id=compensation_plan_id,
            recovery_kind=recovery_kind,
            review_required_on_failure=passport.review_required_on_failure,
            issued_at=issued_at,
        )

    def _close_and_admit_learning(
        self,
        *,
        request: UniversalActionRequest,
        dispatch_result: GovernedDispatchResult,
        capability_decision: CommandCapabilityAdmissionDecision,
        effect_prediction_certificate: EffectPredictionCertificate,
    ) -> tuple[TerminalClosureCertificate | None, LearningAdmissionDecision | None]:
        if self._terminal_closure is None:
            return None, None
        if dispatch_result.blocked or dispatch_result.execution_result is None:
            return None, None
        execution_result = dispatch_result.execution_result
        if execution_result.status is not ExecutionOutcome.SUCCEEDED:
            return None, None

        issued_at = self._clock()
        verification_result = _build_verification_result(
            request=request,
            execution_result=execution_result,
            issued_at=issued_at,
        )
        reconciliation = _build_reconciliation(
            request=request,
            execution_result=execution_result,
            verification_result=verification_result,
            capability_decision=capability_decision,
            effect_plan=effect_prediction_certificate.plan,
            issued_at=issued_at,
        )
        evidence_refs = tuple(
            evidence.uri or evidence.description for evidence in verification_result.evidence
        )
        if reconciliation.status is not ReconciliationStatus.MATCH:
            terminal_certificate = self._terminal_closure.certify_requires_review(
                execution_result=execution_result,
                verification_result=verification_result,
                reconciliation=reconciliation,
                case_id=stable_identifier(
                    "effect-reconciliation-case",
                    {
                        "intent_id": request.intent_id,
                        "execution_id": execution_result.execution_id,
                        "reconciliation_id": reconciliation.reconciliation_id,
                    },
                ),
                evidence_refs=evidence_refs,
                graph_refs=(
                    request.dispatch_request.goal_id,
                    effect_prediction_certificate.plan.effect_plan_id,
                ),
            )
            return terminal_certificate, None
        memory_entry = _build_execution_success_memory(
            request=request,
            execution_result=execution_result,
            verification_result=verification_result,
            reconciliation=reconciliation,
        )
        terminal_certificate = self._terminal_closure.certify_committed(
            execution_result=execution_result,
            verification_result=verification_result,
            reconciliation=reconciliation,
            evidence_refs=evidence_refs,
            memory_entry=memory_entry,
            graph_refs=(
                request.dispatch_request.goal_id,
                effect_prediction_certificate.plan.effect_plan_id,
            ),
        )
        if self._learning_admission is None:
            return terminal_certificate, None
        learning_decision = self._learning_admission.decide(
            certificate=terminal_certificate,
            memory_entry=memory_entry,
            learning_scope=request.tenant_id,
            proposed_use="planning",
        )
        return terminal_certificate, learning_decision

    def _with_proof_hash(self, result: UniversalActionResult) -> UniversalActionResult:
        payload = {
            "action_id": result.action_id,
            "blocked": result.blocked,
            "block_reason": result.block_reason,
            "action_envelope": dict(result.action_envelope),
            "trace_ref": result.trace_ref,
            "admission_receipt_ref": result.admission_receipt_ref,
            "execution_receipt_ref": result.execution_receipt_ref,
            "closure_state": result.closure_state,
            "goal_certificate_id": result.goal_certificate.certificate_id,
            "world_certificate_id": result.world_certificate.certificate_id,
            "plan_certificate_id": result.plan_certificate.certificate_id
            if result.plan_certificate
            else "",
            "simulation_certificate_id": (
                result.simulation_certificate.certificate_id
                if result.simulation_certificate
                else ""
            ),
            "effect_prediction_certificate_id": (
                result.effect_prediction_certificate.certificate_id
                if result.effect_prediction_certificate
                else ""
            ),
            "effect_plan_id": (
                result.effect_prediction_certificate.plan.effect_plan_id
                if result.effect_prediction_certificate
                else ""
            ),
            "recovery_plan_certificate_id": (
                result.recovery_plan_certificate.certificate_id
                if result.recovery_plan_certificate
                else ""
            ),
            "recovery_plan_id": (
                result.recovery_plan_certificate.recovery_plan_id
                if result.recovery_plan_certificate
                else ""
            ),
            "intent_certificate_id": result.intent_certificate.certificate_id
            if result.intent_certificate
            else "",
            "intent_hash": result.intent_certificate.intent_hash
            if result.intent_certificate
            else "",
            "operating_substrate_certificate_id": (
                result.operating_substrate_certificate.certificate_id
                if result.operating_substrate_certificate
                else ""
            ),
            "operating_substrate_projection_id": (
                result.operating_substrate_certificate.projection.projection_id
                if result.operating_substrate_certificate is not None
                and result.operating_substrate_certificate.projection is not None
                else ""
            ),
            "operating_substrate_reason": (
                result.operating_substrate_certificate.reason
                if result.operating_substrate_certificate
                else ""
            ),
            "world_support_evidence_refs": result.world_certificate.evidence_refs,
            "operating_substrate_evidence_refs": (
                result.operating_substrate_certificate.evidence_refs
                if result.operating_substrate_certificate
                else ()
            ),
            "capability_status": result.capability_decision.status.value
            if result.capability_decision
            else "",
            "capability_id": result.capability_decision.capability_id
            if result.capability_decision
            else "",
            "governed_action_id": result.governed_action.governed_action_id
            if result.governed_action
            else "",
            "dispatch_ledger_hash": result.dispatch_result.ledger_hash
            if result.dispatch_result
            else "",
            "terminal_certificate_id": (
                result.terminal_certificate.certificate_id
                if result.terminal_certificate
                else ""
            ),
            "whqr_replay_binding": _uao_record_whqr_replay_binding(result) or {},
            "learning_admission_id": result.learning_decision.admission_id
            if result.learning_decision
            else "",
            "reconciliation_ref": _uao_record_reconciliation_ref(result) or "",
            "memory_ref": _uao_record_memory_ref(result) or "",
            "life_meaning_judgment": (
                result.life_meaning_judgment.as_dict()
                if result.life_meaning_judgment is not None
                else {}
            ),
        }
        encoded = json.dumps(
            payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )
        proof_hash = stable_identifier("universal-action-proof", {"payload": encoded})
        return UniversalActionResult(
            action_id=result.action_id,
            blocked=result.blocked,
            block_reason=result.block_reason,
            action_envelope=result.action_envelope,
            trace_ref=result.trace_ref,
            admission_receipt_ref=result.admission_receipt_ref,
            execution_receipt_ref=result.execution_receipt_ref,
            closure_state=result.closure_state,
            goal_certificate=result.goal_certificate,
            world_certificate=result.world_certificate,
            plan_certificate=result.plan_certificate,
            simulation_certificate=result.simulation_certificate,
            effect_prediction_certificate=result.effect_prediction_certificate,
            recovery_plan_certificate=result.recovery_plan_certificate,
            intent_certificate=result.intent_certificate,
            operating_substrate_certificate=result.operating_substrate_certificate,
            capability_decision=result.capability_decision,
            governed_action=result.governed_action,
            dispatch_result=result.dispatch_result,
            terminal_certificate=result.terminal_certificate,
            learning_decision=result.learning_decision,
            life_meaning_judgment=result.life_meaning_judgment,
            proof_hash=proof_hash,
        )


def build_universal_action_kernel(
    *,
    world_state: WorldStateEngine,
    simulator: SimulationEngine,
    capability_admission: CommandCapabilityAdmissionGate,
    governed_dispatcher: GovernedDispatcher,
    terminal_closure: TerminalClosureCertifier | None = None,
    learning_admission: ClosureLearningAdmissionGate | None = None,
    clock: Callable[[], str],
) -> UniversalActionKernel:
    """Construct the kernel with explicit runtime dependencies."""
    if not isinstance(world_state, WorldStateEngine):
        raise RuntimeCoreInvariantError("world_state must be a WorldStateEngine")
    if not isinstance(simulator, SimulationEngine):
        raise RuntimeCoreInvariantError("simulator must be a SimulationEngine")
    if not isinstance(capability_admission, CommandCapabilityAdmissionGate):
        raise RuntimeCoreInvariantError(
            "capability_admission must be a CommandCapabilityAdmissionGate"
        )
    if not isinstance(governed_dispatcher, GovernedDispatcher):
        raise RuntimeCoreInvariantError(
            "governed_dispatcher must be a GovernedDispatcher"
        )
    return UniversalActionKernel(
        world_state=world_state,
        simulator=simulator,
        capability_admission=capability_admission,
        governed_dispatcher=governed_dispatcher,
        terminal_closure=terminal_closure,
        learning_admission=learning_admission,
        clock=clock,
    )


def build_universal_action_orchestration_record(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
) -> dict[str, Any]:
    """Materialize a UAO v1 record from one kernel request/result pair.

    Input contract: request and result must describe the same actor, tenant,
    intent, and action envelope produced by UniversalActionKernel.run.
    Output contract: returns a JSON-serializable Universal Action Orchestration
    record with no raw private reasoning payloads.
    Error contract: raises RuntimeCoreInvariantError when the request/result
    identity binding is inconsistent.
    """
    action_envelope = _uao_record_action_envelope(request=request, result=result)
    _ensure_record_identity_binding(
        request=request, result=result, action_envelope=action_envelope
    )
    created_at = action_envelope["requested_at"]
    decision = _uao_record_decision(result)
    capability_refs = _uao_record_capability_refs(request=request, result=result)
    evidence_refs = _uao_record_evidence_refs(
        result=result, action_envelope=action_envelope
    )
    input_refs = _unique_text_list((action_envelope["source"], *evidence_refs))
    policy_refs = _uao_record_policy_refs(request=request, result=result)
    temporal_refs = _uao_record_temporal_refs(result=result, created_at=created_at)
    recovery_plan = _uao_record_recovery_plan(result)
    effect_classes = _uao_record_effect_classes(result)
    outcome_ref = _uao_record_outcome_ref(result)
    reconciliation_ref = _uao_record_reconciliation_ref(result)
    memory_ref = _uao_record_memory_ref(result)
    whqr_replay_binding = _uao_record_whqr_replay_binding(result)
    receipt_refs = _uao_record_receipt_refs(
        result=result,
        decision_status=decision["status"],
        reconciliation_ref=reconciliation_ref,
        memory_ref=memory_ref,
        whqr_replay_binding=whqr_replay_binding,
    )
    claim_ledger = _uao_record_claim_ledger(
        result=result,
        decision=decision,
        receipt_refs=receipt_refs,
        outcome_ref=outcome_ref,
        reconciliation_ref=reconciliation_ref,
        memory_ref=memory_ref,
        recovery_plan=recovery_plan,
    )
    fracture_report = _uao_record_fracture_report(
        result=result,
        decision=decision,
        claim_ledger=claim_ledger,
        recovery_plan=recovery_plan,
        capability_refs=capability_refs,
        policy_refs=policy_refs,
        evidence_refs=evidence_refs,
    )
    life_meaning_judgment = _uao_record_life_meaning_judgment(
        request=request,
        result=result,
        decision=decision,
        effect_classes=effect_classes,
        evidence_refs=evidence_refs,
        policy_refs=policy_refs,
    )
    life_continuity_judgment = _uao_record_life_continuity_judgment(
        request=request,
        result=result,
        decision=decision,
        effect_classes=effect_classes,
        evidence_refs=evidence_refs,
        policy_refs=policy_refs,
        life_meaning_judgment=life_meaning_judgment,
    )
    return {
        "orchestration_id": stable_identifier(
            "universal-action-orchestration",
            {
                "action_id": result.action_id,
                "proof_hash": result.proof_hash,
                "trace_ref": result.trace_ref,
            },
        ),
        "uao_schema_version": "uao.v1",
        "action_id": result.action_id,
        "tenant_id": request.tenant_id,
        "actor_id": request.actor_id,
        "created_at": created_at,
        "action_envelope": action_envelope,
        "effect_bearing": True,
        "effect_classes": effect_classes,
        "input_refs": input_refs,
        "policy_refs": policy_refs,
        "capability_refs": capability_refs,
        "temporal_refs": temporal_refs,
        "recovery_plan": recovery_plan,
        "claim_ledger": claim_ledger,
        "fracture_report": fracture_report,
        "life_meaning_judgment": life_meaning_judgment,
        "life_continuity_judgment": life_continuity_judgment,
        "exposure_boundary": {
            "redaction_level": "audit",
            "allowed_audiences": ["operator", "auditor"],
            "blocked_payload_classes": [
                "raw_private_reasoning",
                "secrets",
                "internal_provider_payloads",
                "cross_tenant_data",
            ],
        },
        "pipeline_stages": _uao_record_pipeline_stages(
            result=result,
            action_envelope=action_envelope,
            capability_refs=capability_refs,
            input_refs=input_refs,
            receipt_refs=receipt_refs,
            fracture_report=fracture_report,
            outcome_ref=outcome_ref,
            reconciliation_ref=reconciliation_ref,
            memory_ref=memory_ref,
        ),
        "admission_guards": _uao_record_admission_guards(
            request=request,
            result=result,
            capability_refs=capability_refs,
            evidence_refs=evidence_refs,
            policy_refs=policy_refs,
            temporal_refs=temporal_refs,
            recovery_plan=recovery_plan,
        ),
        "decision": decision,
        "trace_ref": result.trace_ref,
        "causal_decision_trace_ref": result.trace_ref,
        "admission_receipt_ref": result.admission_receipt_ref,
        "execution_receipt_ref": result.execution_receipt_ref,
        "receipts": _uao_record_receipts(
            result=result,
            receipt_refs=receipt_refs,
            outcome_ref=outcome_ref,
            reconciliation_ref=reconciliation_ref,
            memory_ref=memory_ref,
            whqr_replay_binding=whqr_replay_binding,
        ),
        "reconciliation": _uao_record_reconciliation(
            result=result, outcome_ref=outcome_ref
        ),
        "memory_update": _uao_record_memory_update(
            request=request,
            result=result,
            action_envelope=action_envelope,
            memory_ref=memory_ref,
        ),
        "closure_state": result.closure_state,
        "closure": {
            "status": result.closure_state,
            "terminal": True,
            "closure_receipt_ref": receipt_refs["closure"],
            "reconciliation_ref": reconciliation_ref,
            "memory_ref": memory_ref,
            "whqr_replay_binding": whqr_replay_binding,
            "next_action": (
                "operator_review"
                if result.blocked or _result_requires_review(result)
                else "retain_receipts"
            ),
        },
        "raw_reasoning_included": False,
        "lineage": _uao_record_lineage(result),
    }


def _text_tuple_from_metadata(metadata: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = metadata.get(key, ())
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


def _operating_substrate_projection_required(request: UniversalActionRequest) -> bool:
    return request.metadata.get("require_operating_substrate_projection") is True


def _operating_substrate_capability(
    *,
    projection: OperatingSubstrateSelfModelProjection,
    capability_id: str,
    route: str,
) -> SelfModelCapabilityProjection | None:
    for capability in projection.capabilities:
        if capability.capability_id in {capability_id, route}:
            return capability
    return None


def _operating_substrate_support_reason(
    *,
    projection: OperatingSubstrateSelfModelProjection,
    matched_capability: SelfModelCapabilityProjection | None,
) -> str:
    if projection.mutation_authorized or projection.raw_private_reasoning_included:
        return "operating_substrate_self_model_unsafe"
    if projection.solver_outcome is not SolverOutcome.SOLVED_VERIFIED:
        return "operating_substrate_self_model_rejected"
    if projection.overall_status is not HealthStatus.HEALTHY:
        return "operating_substrate_self_model_rejected"
    if matched_capability is None:
        return "operating_substrate_capability_uncovered"
    if not matched_capability.admitted:
        return "operating_substrate_capability_not_admitted"
    if matched_capability.status is not HealthStatus.HEALTHY:
        return "operating_substrate_capability_unavailable"
    return "operating_substrate_supports_execution"


def _operating_substrate_evidence_refs(
    *,
    projection: OperatingSubstrateSelfModelProjection,
    matched_capability: SelfModelCapabilityProjection | None,
    reason: str,
) -> tuple[str, ...]:
    refs: list[str] = [
        f"operating-substrate://projection/{projection.projection_id}",
        f"operating-substrate://status/{projection.overall_status.value}",
        f"operating-substrate://solver-outcome/{projection.solver_outcome.value}",
        f"operating-substrate://reason/{reason}",
    ]
    refs.extend(projection.evidence_refs)
    if matched_capability is not None:
        refs.append(f"operating-substrate://capability/{matched_capability.capability_id}")
        refs.extend(matched_capability.evidence_refs)
        refs.extend(matched_capability.open_incident_refs)
    return tuple(_unique_text_list(refs))


def _world_support_evidence_refs(
    *,
    snapshot: WorldStateSnapshot,
    reason: str,
) -> tuple[str, ...]:
    refs: list[str] = [
        f"world-state://snapshot/{snapshot.snapshot_id}",
        f"world-state://state-hash/{snapshot.state_hash}",
        f"world-state://support/{reason}",
    ]
    for contradiction in snapshot.unresolved_contradictions:
        refs.append(f"world-state://contradiction/{contradiction.contradiction_id}")
        refs.extend(contradiction.conflicting_evidence_ids)
    return tuple(_unique_text_list(refs))


def _build_action_envelope(
    *,
    request: UniversalActionRequest,
    issued_at: str,
    capability_decision: CommandCapabilityAdmissionDecision | None,
) -> Mapping[str, Any]:
    approval_refs = _text_tuple_from_metadata(request.metadata, "approval_refs")
    evidence_refs = _text_tuple_from_metadata(request.metadata, "evidence_refs")
    capability_refs = (
        (capability_decision.capability_id,)
        if capability_decision is not None and capability_decision.capability_id
        else ()
    )
    return {
        "source": _action_source_ref(request),
        "actor": request.actor_id,
        "tenant": request.tenant_id,
        "intent": request.intent_id,
        "target": request.dispatch_request.route,
        "risk": _uao_risk_class(request.risk_level),
        "requested_at": issued_at,
        "approval_ref": approval_refs[0] if approval_refs else None,
        "evidence_refs": evidence_refs,
        "capability_refs": capability_refs,
    }


def _action_source_ref(request: UniversalActionRequest) -> str:
    source_ref = request.metadata.get("source_ref", request.metadata.get("source"))
    if isinstance(source_ref, str) and source_ref.strip():
        return source_ref.strip()
    source_id = stable_identifier(
        "universal-action-source",
        {
            "tenant_id": request.tenant_id,
            "intent_id": request.intent_id,
            "route": request.dispatch_request.route,
        },
    )
    return f"action://{source_id}"


def _uao_risk_class(risk_level: RiskLevel) -> str:
    if risk_level in {RiskLevel.MINIMAL, RiskLevel.LOW}:
        return "low"
    if risk_level is RiskLevel.MODERATE:
        return "H2"
    if risk_level is RiskLevel.HIGH:
        return "H3"
    return "H4"


def _build_trace_ref(*, request: UniversalActionRequest, action_id: str) -> str:
    return stable_identifier(
        "causal-decision-trace",
        {
            "action_id": action_id,
            "tenant_id": request.tenant_id,
            "intent_id": request.intent_id,
            "route": request.dispatch_request.route,
        },
    )


def _build_admission_receipt_ref(
    *,
    action_id: str,
    trace_ref: str,
    decision_status: str,
    life_meaning_judgment_id: str = "",
) -> str:
    return stable_identifier(
        "universal-action-admission-receipt",
        {
            "action_id": action_id,
            "trace_ref": trace_ref,
            "decision_status": decision_status,
            "life_meaning_judgment_id": life_meaning_judgment_id,
        },
    )


def _build_execution_receipt_ref(
    *,
    request: UniversalActionRequest,
    trace_ref: str,
    dispatch_result: GovernedDispatchResult,
) -> str | None:
    if dispatch_result.blocked or dispatch_result.execution_result is None:
        return None
    return stable_identifier(
        "universal-action-execution-receipt",
        {
            "tenant_id": request.tenant_id,
            "intent_id": request.intent_id,
            "trace_ref": trace_ref,
            "execution_id": dispatch_result.execution_result.execution_id,
            "ledger_hash": dispatch_result.ledger_hash,
        },
    )


def _build_closure_state(
    *,
    blocked: bool,
    dispatch_result: GovernedDispatchResult | None,
    terminal_certificate: TerminalClosureCertificate | None,
) -> str:
    if terminal_certificate is not None:
        return _uao_closure_state_from_terminal(terminal_certificate.disposition)
    if blocked:
        return "closed_blocked"
    if dispatch_result is not None:
        return "closed_allowed"
    return "closed_deferred"


def _blocked_closure_state(decision_status: str) -> str:
    if decision_status == "defer":
        return "closed_deferred"
    if decision_status == "escalate":
        return "closed_escalated"
    return "closed_blocked"


def _life_meaning_decision_status(judgment: LifeMeaningJudgment) -> str:
    if judgment.decision is LifeMeaningDecision.PAUSE:
        return "defer"
    if judgment.decision is LifeMeaningDecision.ESCALATE:
        return "escalate"
    return "block"


def _life_meaning_judgment_with_admission_ref(
    judgment: LifeMeaningJudgment,
    admission_receipt_ref: str,
) -> LifeMeaningJudgment:
    evidence_refs = tuple(
        ref
        for ref in judgment.evidence_refs
        if not ref.startswith("universal-action-admission-receipt-")
        or ref == admission_receipt_ref
    )
    if admission_receipt_ref not in evidence_refs:
        evidence_refs = (*evidence_refs, admission_receipt_ref)
    return LifeMeaningJudgment(
        judgment_id=judgment.judgment_id,
        action_id=judgment.action_id,
        decision=judgment.decision,
        affected_symbols=judgment.affected_symbols,
        life_impact=judgment.life_impact,
        feeling_impact=judgment.feeling_impact,
        meaning_impact=judgment.meaning_impact,
        truth_preserved=judgment.truth_preserved,
        dignity_boundary=judgment.dignity_boundary,
        consent_required=judgment.consent_required,
        consent_present=judgment.consent_present,
        love_delta=judgment.love_delta,
        resonance_delta=judgment.resonance_delta,
        domination_risk=judgment.domination_risk,
        justice_repair_required=judgment.justice_repair_required,
        continuity_delta=judgment.continuity_delta,
        irreversible=judgment.irreversible,
        reasons=judgment.reasons,
        evidence_refs=evidence_refs,
        approval_required=judgment.approval_required,
        rollback_required=judgment.rollback_required,
    )


def _uao_closure_state_from_terminal(disposition: TerminalClosureDisposition) -> str:
    if disposition is TerminalClosureDisposition.REQUIRES_REVIEW:
        return "closed_escalated"
    return "closed_allowed"


def _build_verification_result(
    *,
    request: UniversalActionRequest,
    execution_result: ExecutionResult,
    issued_at: str,
) -> VerificationResult:
    return VerificationResult(
        verification_id=stable_identifier(
            "universal-verification",
            {
                "intent_id": request.intent_id,
                "execution_id": execution_result.execution_id,
                "issued_at": issued_at,
            },
        ),
        execution_id=execution_result.execution_id,
        status=VerificationStatus.PASS,
        checks=(
            VerificationCheck(
                name="execution_succeeded",
                status=VerificationStatus.PASS,
                details={"status": execution_result.status.value},
            ),
        ),
        evidence=(
            EvidenceRecord(
                description="universal action execution evidence",
                uri=f"proof://{request.tenant_id}/{execution_result.execution_id}/verification",
                details={
                    "goal_id": execution_result.goal_id,
                    "intent_id": request.intent_id,
                    "route": request.dispatch_request.route,
                },
            ),
        ),
        closed_at=issued_at,
        metadata={
            "kernel": "universal_action",
            "intent_id": request.intent_id,
            "goal_id": execution_result.goal_id,
        },
    )


def _build_reconciliation(
    *,
    request: UniversalActionRequest,
    execution_result: ExecutionResult,
    verification_result: VerificationResult,
    capability_decision: CommandCapabilityAdmissionDecision,
    effect_plan: EffectPlan,
    issued_at: str,
) -> EffectReconciliation:
    actual_names = tuple(effect.name for effect in execution_result.actual_effects)
    expected_names = tuple(effect.name for effect in effect_plan.expected_effects)
    forbidden_names = set(effect_plan.forbidden_effects)
    matched_effects = tuple(name for name in expected_names if name in actual_names)
    missing_effects = tuple(name for name in expected_names if name not in actual_names)
    unexpected_effects = tuple(
        name for name in actual_names if name not in expected_names or name in forbidden_names
    )
    status = (
        ReconciliationStatus.MATCH
        if not missing_effects and not unexpected_effects
        else ReconciliationStatus.MISMATCH
    )
    return EffectReconciliation(
        reconciliation_id=stable_identifier(
            "universal-reconciliation",
            {
                "intent_id": request.intent_id,
                "execution_id": execution_result.execution_id,
                "verification_id": verification_result.verification_id,
                "effect_plan_id": effect_plan.effect_plan_id,
                "status": status.value,
            },
        ),
        command_id=request.intent_id,
        effect_plan_id=effect_plan.effect_plan_id,
        status=status,
        matched_effects=matched_effects,
        missing_effects=missing_effects,
        unexpected_effects=unexpected_effects,
        verification_result_id=verification_result.verification_id,
        case_id=(
            None
            if status is ReconciliationStatus.MATCH
            else stable_identifier(
                "effect-reconciliation-case",
                {
                    "intent_id": request.intent_id,
                    "capability_id": capability_decision.capability_id,
                    "effect_plan_id": effect_plan.effect_plan_id,
                },
            )
        ),
        decided_at=issued_at,
    )


def _build_execution_success_memory(
    *,
    request: UniversalActionRequest,
    execution_result: ExecutionResult,
    verification_result: VerificationResult,
    reconciliation: EffectReconciliation,
) -> MemoryEntry:
    return MemoryEntry(
        entry_id=stable_identifier(
            "universal-action-memory",
            {
                "intent_id": request.intent_id,
                "execution_id": execution_result.execution_id,
                "verification_id": verification_result.verification_id,
            },
        ),
        tier=MemoryTier.EPISODIC,
        category="execution_success",
        content={
            "trust_class": "trusted",
            "command_id": request.intent_id,
            "execution_id": execution_result.execution_id,
            "goal_id": execution_result.goal_id,
            "route": request.dispatch_request.route,
            "verification_id": verification_result.verification_id,
            "reconciliation_id": reconciliation.reconciliation_id,
        },
        source_ids=(
            execution_result.execution_id,
            verification_result.verification_id,
            reconciliation.reconciliation_id,
        ),
    )


def _ensure_record_identity_binding(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
    action_envelope: Mapping[str, Any],
) -> None:
    if action_envelope["actor"] != request.actor_id:
        raise RuntimeCoreInvariantError(
            "UAO record actor binding does not match request"
        )
    if action_envelope["tenant"] != request.tenant_id:
        raise RuntimeCoreInvariantError(
            "UAO record tenant binding does not match request"
        )
    if action_envelope["intent"] != request.intent_id:
        raise RuntimeCoreInvariantError(
            "UAO record intent binding does not match request"
        )
    if result.goal_certificate.goal.metadata.get("intent_id") != request.intent_id:
        raise RuntimeCoreInvariantError(
            "UAO record goal certificate does not match request intent"
        )


def _uao_record_action_envelope(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
) -> dict[str, Any]:
    return {
        "source": str(
            result.action_envelope.get("source") or _action_source_ref(request)
        ),
        "actor": str(result.action_envelope.get("actor") or request.actor_id),
        "tenant": str(result.action_envelope.get("tenant") or request.tenant_id),
        "intent": str(result.action_envelope.get("intent") or request.intent_id),
        "target": str(
            result.action_envelope.get("target") or request.dispatch_request.route
        ),
        "risk": str(
            result.action_envelope.get("risk") or _uao_risk_class(request.risk_level)
        ),
        "requested_at": str(
            result.action_envelope.get("requested_at")
            or result.goal_certificate.issued_at
        ),
        "approval_ref": _optional_text_value(
            result.action_envelope.get("approval_ref")
        ),
        "evidence_refs": _unique_text_list(
            result.action_envelope.get("evidence_refs", ())
        ),
        "capability_refs": _uao_record_capability_refs(request=request, result=result),
    }


def _uao_record_capability_refs(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
) -> list[str]:
    refs: list[str] = []
    refs.extend(_text_iterable(result.action_envelope.get("capability_refs", ())))
    if (
        result.capability_decision is not None
        and result.capability_decision.capability_id
    ):
        refs.append(result.capability_decision.capability_id)
    refs.append(request.dispatch_request.route)
    return _unique_text_list(refs)


def _uao_record_evidence_refs(
    *,
    result: UniversalActionResult,
    action_envelope: Mapping[str, Any],
) -> list[str]:
    refs: list[str] = []
    refs.extend(_text_iterable(action_envelope.get("evidence_refs", ())))
    if result.terminal_certificate is not None:
        refs.extend(result.terminal_certificate.evidence_refs)
    refs.extend(result.world_certificate.evidence_refs)
    if result.operating_substrate_certificate is not None:
        refs.extend(result.operating_substrate_certificate.evidence_refs)
    refs.append(result.world_certificate.snapshot.snapshot_id)
    return _unique_text_list(refs)


def _uao_record_policy_refs(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
) -> list[str]:
    refs = list(_text_tuple_from_metadata(request.metadata, "policy_refs"))
    refs.append("policy://mullusi/universal-action-kernel/v1")
    if result.capability_decision is not None and result.capability_decision.domain:
        refs.append(f"policy://capability-domain/{result.capability_decision.domain}")
    return _unique_text_list(refs)


def _uao_record_temporal_refs(
    *,
    result: UniversalActionResult,
    created_at: str,
) -> list[str]:
    refs = [f"temporal://universal-action/{created_at}"]
    if result.terminal_certificate is not None:
        refs.append(
            f"temporal://terminal-closure/{result.terminal_certificate.closed_at}"
        )
    return _unique_text_list(refs)


def _uao_record_recovery_plan(result: UniversalActionResult) -> dict[str, Any]:
    certificate = result.recovery_plan_certificate
    if certificate is None:
        effect_plan_ref = (
            result.effect_prediction_certificate.plan.effect_plan_id
            if result.effect_prediction_certificate is not None
            else None
        )
        return {
            "available": False,
            "recovery_plan_ref": None,
            "recovery_kind": "none",
            "rollback_plan_ref": None,
            "compensation_plan_ref": None,
            "review_required_on_failure": True,
            "certificate_ref": None,
            "effect_plan_ref": effect_plan_ref,
        }
    return {
        "available": True,
        "recovery_plan_ref": certificate.recovery_plan_id,
        "recovery_kind": certificate.recovery_kind,
        "rollback_plan_ref": certificate.rollback_plan_id or None,
        "compensation_plan_ref": certificate.compensation_plan_id or None,
        "review_required_on_failure": certificate.review_required_on_failure,
        "certificate_ref": certificate.certificate_id,
        "effect_plan_ref": certificate.effect_plan_id,
    }


def _uao_record_claim_ledger(
    *,
    result: UniversalActionResult,
    decision: Mapping[str, Any],
    receipt_refs: Mapping[str, str],
    outcome_ref: str | None,
    reconciliation_ref: str | None,
    memory_ref: str | None,
    recovery_plan: Mapping[str, Any],
) -> dict[str, Any]:
    ledger_ref = stable_identifier(
        "universal-action-claim-ledger",
        {
            "action_id": result.action_id,
            "trace_ref": result.trace_ref,
            "closure_state": result.closure_state,
        },
    )
    claims = [
        _uao_claim(
            result=result,
            claim_type="decision",
            statement=(
                "Universal action decision "
                f"{decision['status']} recorded for {result.action_id}."
            ),
            evidence_refs=[result.trace_ref, result.admission_receipt_ref],
            verified=True,
            confidence=1.0,
        ),
        _uao_claim(
            result=result,
            claim_type="closure",
            statement=(
                "Universal action closure state "
                f"{result.closure_state} recorded for {result.action_id}."
            ),
            evidence_refs=[receipt_refs["closure"], result.closure_state],
            verified=True,
            confidence=1.0,
        ),
    ]
    if result.execution_receipt_ref is not None and outcome_ref is not None:
        claims.append(
            _uao_claim(
                result=result,
                claim_type="execution",
                statement=f"Execution receipt emitted for {result.action_id}.",
                evidence_refs=[result.execution_receipt_ref, outcome_ref],
                verified=True,
                confidence=0.95,
            )
        )
    if reconciliation_ref is not None:
        reconciliation_receipt = receipt_refs.get("reconciliation")
        claims.append(
            _uao_claim(
                result=result,
                claim_type="reconciliation",
                statement=f"Reconciliation record linked for {result.action_id}.",
                evidence_refs=[
                    ref
                    for ref in (reconciliation_ref, reconciliation_receipt)
                    if ref
                ],
                verified=True,
                confidence=0.95,
            )
        )
    if memory_ref is not None:
        claims.append(
            _uao_claim(
                result=result,
                claim_type="memory",
                statement=f"Memory update linked for {result.action_id}.",
                evidence_refs=[memory_ref],
                verified=True,
                confidence=0.9,
            )
        )
    if recovery_plan.get("available") is True:
        claims.append(
            _uao_claim(
                result=result,
                claim_type="recovery",
                statement=f"Recovery path certified for {result.action_id}.",
                evidence_refs=_unique_text_list(
                    (
                        _optional_text_value(recovery_plan.get("recovery_plan_ref"))
                        or "",
                        _optional_text_value(recovery_plan.get("certificate_ref"))
                        or "",
                        _optional_text_value(recovery_plan.get("effect_plan_ref"))
                        or "",
                    )
                ),
                verified=True,
                confidence=0.95,
            )
        )
    return {
        "ledger_ref": f"claim-ledger://{ledger_ref}",
        "claims": claims,
        "unverified_claim_ids": [
            claim["claim_id"] for claim in claims if not claim["verified"]
        ],
    }


def _uao_record_fracture_report(
    *,
    result: UniversalActionResult,
    decision: Mapping[str, Any],
    claim_ledger: Mapping[str, Any],
    recovery_plan: Mapping[str, Any],
    capability_refs: list[str],
    policy_refs: list[str],
    evidence_refs: list[str],
) -> dict[str, Any]:
    report_ref = "fracture-report://" + stable_identifier(
        "universal-action-fracture-report",
        {
            "action_id": result.action_id,
            "trace_ref": result.trace_ref,
            "decision_status": str(decision["status"]),
        },
    )
    reason_code = str(decision["reason_code"])
    unverified_claim_ids = claim_ledger.get("unverified_claim_ids", [])
    capability_failed = (
        result.capability_decision is not None
        and result.capability_decision.status
        is not CommandCapabilityAdmissionStatus.ACCEPTED
    )
    missing_recovery = reason_code == "recovery_plan_missing" or (
        result.dispatched and recovery_plan.get("available") is not True
    )
    checks = [
        _uao_fracture_check(
            result=result,
            check_type="policy_conflict",
            failed="policy" in reason_code and reason_code != "policy_allows",
            reason_code="policy_conflict_absent",
            failure_reason_code=reason_code,
            evidence_refs=policy_refs,
        ),
        _uao_fracture_check(
            result=result,
            check_type="identity_conflict",
            failed="identity" in reason_code or "tenant" in reason_code,
            reason_code="identity_conflict_absent",
            failure_reason_code=reason_code,
            evidence_refs=[result.trace_ref],
        ),
        _uao_fracture_check(
            result=result,
            check_type="budget_conflict",
            failed="budget" in reason_code,
            reason_code="budget_conflict_absent",
            failure_reason_code=reason_code,
            evidence_refs=policy_refs,
        ),
        _uao_fracture_check(
            result=result,
            check_type="schema_conflict",
            failed="schema" in reason_code,
            reason_code="schema_conflict_absent",
            failure_reason_code=reason_code,
            evidence_refs=evidence_refs,
        ),
        _uao_fracture_check(
            result=result,
            check_type="capability_mismatch",
            failed=capability_failed,
            reason_code="capability_mismatch_absent",
            failure_reason_code=reason_code,
            evidence_refs=capability_refs,
        ),
        _uao_fracture_check(
            result=result,
            check_type="memory_contradiction",
            failed=False,
            reason_code="memory_contradiction_absent",
            failure_reason_code="memory_contradiction",
            evidence_refs=[result.trace_ref],
        ),
        _uao_fracture_check(
            result=result,
            check_type="unverified_claim",
            failed=bool(unverified_claim_ids),
            reason_code="unverified_claim_absent",
            failure_reason_code="unverified_claim_present",
            evidence_refs=list(unverified_claim_ids) or [str(claim_ledger["ledger_ref"])],
        ),
        _uao_fracture_check(
            result=result,
            check_type="missing_recovery",
            failed=missing_recovery,
            reason_code="recovery_path_available",
            failure_reason_code="recovery_plan_missing",
            evidence_refs=[
                ref
                for ref in (
                    recovery_plan.get("recovery_plan_ref"),
                    recovery_plan.get("certificate_ref"),
                    result.trace_ref,
                )
                if isinstance(ref, str) and ref
            ],
        ),
        _uao_fracture_check(
            result=result,
            check_type="authority_mismatch",
            failed="authority" in reason_code or "approval" in reason_code,
            reason_code="authority_mismatch_absent",
            failure_reason_code=reason_code,
            evidence_refs=policy_refs,
        ),
        _uao_fracture_check(
            result=result,
            check_type="duplicate_command",
            failed=False,
            reason_code="duplicate_command_absent",
            failure_reason_code="duplicate_command",
            evidence_refs=[result.action_id, result.trace_ref],
        ),
        _uao_fracture_check(
            result=result,
            check_type="prompt_injection",
            failed=False,
            reason_code="prompt_injection_absent",
            failure_reason_code="prompt_injection",
            evidence_refs=evidence_refs or [result.trace_ref],
        ),
    ]
    blocking_check_ids = [
        check["check_id"] for check in checks if check["blocking"] is True
    ]
    return {
        "report_ref": report_ref,
        "status": "failed" if blocking_check_ids else "passed",
        "checks": checks,
        "blocking_check_ids": blocking_check_ids,
        "risk_notes": _unique_text_list(
            (
                f"decision:{decision['status']}",
                f"reason:{reason_code}",
                f"closure:{result.closure_state}",
            )
        ),
    }


def _uao_fracture_check(
    *,
    result: UniversalActionResult,
    check_type: str,
    failed: bool,
    reason_code: str,
    failure_reason_code: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    status = "failed" if failed else "passed"
    return {
        "check_id": "fracture-check://"
        + stable_identifier(
            "universal-action-fracture-check",
            {
                "action_id": result.action_id,
                "check_type": check_type,
                "status": status,
            },
        ),
        "check_type": check_type,
        "status": status,
        "proof_state": "Fail" if failed else "Pass",
        "reason_code": failure_reason_code if failed else reason_code,
        "evidence_refs": _unique_text_list(evidence_refs or [result.trace_ref]),
        "blocking": failed,
    }


def _uao_record_life_meaning_judgment(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
    decision: Mapping[str, Any],
    effect_classes: list[str],
    evidence_refs: list[str],
    policy_refs: list[str],
) -> dict[str, Any]:
    """Build the canonical LifeMeaningJudgment for a UAO record."""
    if result.life_meaning_judgment is not None and not _result_requires_review(result):
        if result.life_meaning_judgment.action_id != result.action_id:
            raise RuntimeCoreInvariantError(
                "life_meaning_judgment action binding does not match result"
            )
        return result.life_meaning_judgment.as_dict()

    return _build_life_meaning_judgment(
        request=request,
        result=result,
        decision=decision,
        effect_classes=effect_classes,
        evidence_refs=evidence_refs,
        policy_refs=policy_refs,
    ).as_dict()


def _build_life_meaning_judgment(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
    decision: Mapping[str, Any],
    effect_classes: list[str],
    evidence_refs: list[str],
    policy_refs: list[str],
) -> LifeMeaningJudgment:
    """Build the canonical LifeMeaningJudgment object for runtime and UAO."""

    override = request.metadata.get("life_meaning_judgment", {})
    if override is None:
        override = {}
    if not isinstance(override, Mapping):
        raise RuntimeCoreInvariantError(
            "life_meaning_judgment metadata override must be a mapping"
        )

    default_life_decision = _uao_life_continuity_decision(decision)
    default_impact = _uao_life_continuity_default_impact(
        decision=decision,
        result=result,
        effect_classes=effect_classes,
    )
    default_meaning_impact = (
        "unknown" if str(decision.get("proof_state")) == "Unknown" else default_impact
    )
    reason_code = str(decision.get("reason_code", ""))
    default_domination_risk = "approval" in reason_code or "authority" in reason_code
    default_dignity_boundary = (
        "unknown"
        if default_domination_risk or default_meaning_impact == "unknown"
        else "pass"
    )
    default_continuity_delta = (
        "positive"
        if decision.get("status") == "allow"
        else "neutral"
        if decision.get("status") == "simulate"
        else "unknown"
    )
    default_resonance_delta = (
        "positive"
        if decision.get("status") == "allow"
        else "neutral"
        if decision.get("status") == "simulate"
        else "unknown"
    )
    default_evidence_refs = _uao_life_meaning_evidence_refs_override(
        override,
        (
            result.trace_ref,
            result.admission_receipt_ref,
            *(policy_refs[:2]),
            *(evidence_refs[:2]),
        ),
    )
    default_irreversible = _uao_life_meaning_bool_override(
        override,
        "irreversible",
        decision.get("status") == "escalate",
    )
    affected_symbols = _uao_life_meaning_affected_symbols_override(
        override,
        default_impact=default_impact,
        default_meaning_impact=default_meaning_impact,
        default_irreversible=default_irreversible,
        result=result,
    )
    consent_present = _uao_life_meaning_bool_override(
        override,
        "consent_present",
        default_life_decision == "pass" and default_meaning_impact != "unknown",
    )
    judgment = judge_life_meaning(
        action_id=result.action_id,
        affected_symbols=affected_symbols,
        life_impact=ImpactLevel(
            _uao_life_meaning_enum_override(
                override,
                "life_impact",
                {"none", "indirect", "direct", "unknown"},
                default_impact,
            )
        ),
        feeling_impact=ImpactLevel(
            _uao_life_meaning_enum_override(
                override,
                "feeling_impact",
                {"none", "indirect", "direct", "unknown"},
                default_meaning_impact,
            )
        ),
        meaning_impact=ImpactLevel(
            _uao_life_meaning_enum_override(
                override,
                "meaning_impact",
                {"none", "indirect", "direct", "unknown"},
                default_meaning_impact,
            )
        ),
        truth_preserved=_uao_life_meaning_bool_override(
            override,
            "truth_preserved",
            True,
        ),
        dignity_boundary=BoundaryState(
            _uao_life_meaning_enum_override(
                override,
                "dignity_boundary",
                {"pass", "fail", "unknown"},
                default_dignity_boundary,
            )
        ),
        consent_present=consent_present,
        love_delta=Delta(
            _uao_life_meaning_enum_override(
                override,
                "love_delta",
                {"positive", "neutral", "negative", "unknown"},
                "neutral",
            )
        ),
        resonance_delta=Delta(
            _uao_life_meaning_enum_override(
                override,
                "resonance_delta",
                {"positive", "neutral", "negative", "unknown"},
                default_resonance_delta,
            )
        ),
        domination_risk=_uao_life_meaning_bool_override(
            override,
            "domination_risk",
            default_domination_risk,
        ),
        continuity_delta=Delta(
            _uao_life_meaning_enum_override(
                override,
                "continuity_delta",
                {"positive", "neutral", "negative", "unknown"},
                default_continuity_delta,
            )
        ),
        irreversible=default_irreversible,
        evidence_refs=tuple(default_evidence_refs),
    )
    if "decision" in override and override["decision"] != judgment.decision.value:
        raise RuntimeCoreInvariantError(
            "life_meaning_judgment.decision override conflicts with deterministic judgment"
        )
    if decision.get("status") == "escalate" and judgment.decision.value != "escalate":
        raise RuntimeCoreInvariantError(
            "life_meaning_judgment must escalate when action decision escalates"
        )
    return judgment


def _uao_record_life_continuity_judgment(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
    decision: Mapping[str, Any],
    effect_classes: list[str],
    evidence_refs: list[str],
    policy_refs: list[str],
    life_meaning_judgment: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the life-continuity conflict-law judgment for a UAO record."""

    override = request.metadata.get("life_continuity_judgment", {})
    if override is None:
        override = {}
    if not isinstance(override, Mapping):
        raise RuntimeCoreInvariantError(
            "life_continuity_judgment metadata override must be a mapping"
        )

    default_life_decision = str(life_meaning_judgment["decision"])
    default_impact = str(life_meaning_judgment["life_impact"])
    default_meaning_impact = str(life_meaning_judgment["meaning_impact"])
    default_domination_risk = bool(life_meaning_judgment["domination_risk"])
    default_dignity_boundary = str(life_meaning_judgment["dignity_boundary"])
    default_lived_risk = _uao_lived_meaning_default_risk(
        decision=decision,
        result=result,
        domination_risk=default_domination_risk,
    )
    judgment_ref = "life-continuity://" + stable_identifier(
        "universal-action-life-continuity-judgment",
        {
            "action_id": result.action_id,
            "trace_ref": result.trace_ref,
            "decision_status": str(decision.get("status")),
        },
    )
    judgment_evidence_refs = _uao_life_evidence_refs_override(
        override,
        (
            result.trace_ref,
            result.admission_receipt_ref,
            *(policy_refs[:2]),
            *(evidence_refs[:2]),
        ),
    )
    if not judgment_evidence_refs:
        judgment_evidence_refs = [result.trace_ref]

    return {
        "judgment_ref": _uao_life_text_override(
            override,
            "judgment_ref",
            judgment_ref,
        ),
        "conflict_law_ref": _uao_life_text_override(
            override,
            "conflict_law_ref",
            "doctrine://life-continuity-conflict-law/v1",
        ),
        "life_impact": _uao_life_enum_override(
            override,
            "life_impact",
            {"none", "indirect", "direct", "unknown"},
            default_impact,
        ),
        "feeling_impact": _uao_life_enum_override(
            override,
            "feeling_impact",
            {"none", "indirect", "direct", "unknown"},
            str(life_meaning_judgment["feeling_impact"]),
        ),
        "feeling_observer_impact": _uao_life_enum_override(
            override,
            "feeling_observer_impact",
            {"none", "indirect", "direct", "unknown"},
            default_meaning_impact,
        ),
        "meaning_impact": _uao_life_enum_override(
            override,
            "meaning_impact",
            {"none", "indirect", "direct", "unknown"},
            default_meaning_impact,
        ),
        "meaning_continuity_delta": _uao_life_enum_override(
            override,
            "meaning_continuity_delta",
            {"positive", "neutral", "negative", "unknown"},
            str(life_meaning_judgment["continuity_delta"]),
        ),
        "value_bearing_symbol": _uao_life_bool_override(
            override,
            "value_bearing_symbol",
            default_impact != "none"
            or str(life_meaning_judgment["feeling_impact"]) != "none"
            or default_meaning_impact != "none",
        ),
        "lived_meaning_risk": _uao_life_enum_override(
            override,
            "lived_meaning_risk",
            {"none", "low", "medium", "high", "unknown"},
            default_lived_risk,
        ),
        "love_delta": _uao_life_enum_override(
            override,
            "love_delta",
            {"positive", "neutral", "negative", "unknown"},
            str(life_meaning_judgment["love_delta"]),
        ),
        "resonance_delta": _uao_life_enum_override(
            override,
            "resonance_delta",
            {"positive", "neutral", "negative", "unknown"},
            str(life_meaning_judgment["resonance_delta"]),
        ),
        "dignity_boundary": _uao_life_enum_override(
            override,
            "dignity_boundary",
            {"pass", "fail", "unknown"},
            default_dignity_boundary,
        ),
        "truth_preserved": _uao_life_bool_override(
            override,
            "truth_preserved",
            True,
        ),
        "domination_risk": _uao_life_bool_override(
            override,
            "domination_risk",
            default_domination_risk,
        ),
        "decision": _uao_life_enum_override(
            override,
            "decision",
            {"pass", "pause", "block", "escalate"},
            default_life_decision,
        ),
        "evidence_refs": judgment_evidence_refs,
        "review_required": _uao_life_bool_override(
            override,
            "review_required",
            default_life_decision != "pass",
        ),
    }


def _uao_life_continuity_decision(decision: Mapping[str, Any]) -> str:
    status = decision.get("status")
    if status == "allow":
        return "pass"
    if status == "escalate":
        return "escalate"
    if status == "defer":
        return "pause"
    if status == "simulate":
        return "pass"
    return "block"


def _uao_life_meaning_affected_symbols_override(
    override: Mapping[str, Any],
    *,
    default_impact: str,
    default_meaning_impact: str,
    default_irreversible: bool,
    result: UniversalActionResult,
) -> tuple[AffectedSymbol, ...]:
    value = override.get("affected_symbols")
    if value is None:
        life_status = (
            LifeStatus.UNKNOWN
            if default_impact != "none" or default_meaning_impact != "none"
            else LifeStatus.NOT_LIFE
        )
        feeling_status = (
            FeelingStatus.UNKNOWN
            if default_meaning_impact != "none"
            else FeelingStatus.NOT_FEELING
        )
        fragility_level = (
            9
            if default_irreversible and default_meaning_impact == "unknown"
            else 6
            if default_meaning_impact == "unknown"
            else 3
            if default_impact != "none" or default_meaning_impact != "none"
            else 1
        )
        return (
            AffectedSymbol(
                symbol_id=f"action-target:{result.action_id}",
                symbol_kind=(
                    "effect_bearing_action_target"
                    if default_impact != "none" or default_meaning_impact != "none"
                    else "local_artifact"
                ),
                life_status=life_status,
                feeling_status=feeling_status,
                meaning_bearing=ImpactLevel(default_meaning_impact),
                fragility_level=fragility_level,
                agency_level=2 if default_impact != "none" else 0,
            ),
        )
    if not isinstance(value, (list, tuple)) or not value:
        raise RuntimeCoreInvariantError(
            "life_meaning_judgment.affected_symbols must be a non-empty sequence"
        )
    affected_symbols: list[AffectedSymbol] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise RuntimeCoreInvariantError(
                f"life_meaning_judgment.affected_symbols[{index}] must be a mapping"
            )
        try:
            affected_symbols.append(
                AffectedSymbol(
                    symbol_id=_uao_life_meaning_required_text(
                        item,
                        "symbol_id",
                        f"life_meaning_judgment.affected_symbols[{index}]",
                    ),
                    symbol_kind=_uao_life_meaning_required_text(
                        item,
                        "symbol_kind",
                        f"life_meaning_judgment.affected_symbols[{index}]",
                    ),
                    life_status=LifeStatus(
                        _uao_life_meaning_required_text(
                            item,
                            "life_status",
                            f"life_meaning_judgment.affected_symbols[{index}]",
                        )
                    ),
                    feeling_status=FeelingStatus(
                        _uao_life_meaning_required_text(
                            item,
                            "feeling_status",
                            f"life_meaning_judgment.affected_symbols[{index}]",
                        )
                    ),
                    meaning_bearing=ImpactLevel(
                        _uao_life_meaning_required_text(
                            item,
                            "meaning_bearing",
                            f"life_meaning_judgment.affected_symbols[{index}]",
                        )
                    ),
                    fragility_level=_uao_life_meaning_required_int(
                        item,
                        "fragility_level",
                        f"life_meaning_judgment.affected_symbols[{index}]",
                    ),
                    agency_level=_uao_life_meaning_required_int(
                        item,
                        "agency_level",
                        f"life_meaning_judgment.affected_symbols[{index}]",
                    ),
                )
            )
        except ValueError as exc:
            raise RuntimeCoreInvariantError(str(exc)) from exc
    return tuple(affected_symbols)


def _uao_life_meaning_required_text(
    source: Mapping[str, Any],
    field_name: str,
    label: str,
) -> str:
    value = source.get(field_name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise RuntimeCoreInvariantError(f"{label}.{field_name} must be a non-empty string")


def _uao_life_meaning_required_int(
    source: Mapping[str, Any],
    field_name: str,
    label: str,
) -> int:
    value = source.get(field_name)
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10:
        return value
    raise RuntimeCoreInvariantError(f"{label}.{field_name} must be an integer in [0,10]")


def _uao_life_meaning_enum_override(
    override: Mapping[str, Any],
    field_name: str,
    allowed_values: set[str],
    default: str,
) -> str:
    value = override.get(field_name, default)
    if isinstance(value, str) and value in allowed_values:
        return value
    raise RuntimeCoreInvariantError(f"life_meaning_judgment.{field_name} is invalid")


def _uao_life_meaning_bool_override(
    override: Mapping[str, Any],
    field_name: str,
    default: bool,
) -> bool:
    value = override.get(field_name, default)
    if isinstance(value, bool):
        return value
    raise RuntimeCoreInvariantError(f"life_meaning_judgment.{field_name} must be boolean")


def _uao_life_meaning_evidence_refs_override(
    override: Mapping[str, Any],
    default: tuple[str, ...],
) -> list[str]:
    value = override.get("evidence_refs", default)
    if "evidence_refs" in override:
        if not isinstance(value, (list, tuple)):
            raise RuntimeCoreInvariantError(
                "life_meaning_judgment.evidence_refs must be a sequence of non-empty strings"
            )
        if not all(isinstance(ref, str) and ref.strip() for ref in value):
            raise RuntimeCoreInvariantError(
                "life_meaning_judgment.evidence_refs must be a sequence of non-empty strings"
            )
        return _unique_text_list(value)
    refs = _unique_text_list(value)
    if refs:
        return refs
    raise RuntimeCoreInvariantError(
        "life_meaning_judgment.evidence_refs must be a sequence"
    )


def _uao_life_continuity_default_impact(
    *,
    decision: Mapping[str, Any],
    result: UniversalActionResult,
    effect_classes: list[str],
) -> str:
    if str(decision.get("proof_state")) == "Unknown":
        return "unknown"
    if not effect_classes:
        return "none"
    if result.block_reason == "simulation_only":
        return "none"
    return "indirect"


def _uao_lived_meaning_default_risk(
    *,
    decision: Mapping[str, Any],
    result: UniversalActionResult,
    domination_risk: bool,
) -> str:
    if str(decision.get("proof_state")) == "Unknown":
        return "unknown"
    if decision.get("status") == "allow":
        return "low"
    if domination_risk:
        return "medium"
    if result.blocked:
        return "medium"
    return "low"


def _uao_life_text_override(
    override: Mapping[str, Any],
    field_name: str,
    default: str,
) -> str:
    value = override.get(field_name, default)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise RuntimeCoreInvariantError(
        f"life_continuity_judgment.{field_name} must be a non-empty string"
    )


def _uao_life_enum_override(
    override: Mapping[str, Any],
    field_name: str,
    allowed_values: set[str],
    default: str,
) -> str:
    value = override.get(field_name, default)
    if isinstance(value, str) and value in allowed_values:
        return value
    raise RuntimeCoreInvariantError(
        f"life_continuity_judgment.{field_name} is invalid"
    )


def _uao_life_bool_override(
    override: Mapping[str, Any],
    field_name: str,
    default: bool,
) -> bool:
    value = override.get(field_name, default)
    if isinstance(value, bool):
        return value
    raise RuntimeCoreInvariantError(
        f"life_continuity_judgment.{field_name} must be boolean"
    )


def _uao_life_evidence_refs_override(
    override: Mapping[str, Any],
    default: tuple[str, ...],
) -> list[str]:
    value = override.get("evidence_refs", default)
    refs = _unique_text_list(value)
    if refs:
        return refs
    raise RuntimeCoreInvariantError(
        "life_continuity_judgment.evidence_refs must contain at least one reference"
    )


def _uao_claim(
    *,
    result: UniversalActionResult,
    claim_type: str,
    statement: str,
    evidence_refs: list[str],
    verified: bool,
    confidence: float,
) -> dict[str, Any]:
    normalized_evidence_refs = _unique_text_list(evidence_refs)
    claim_id = stable_identifier(
        "universal-action-claim",
        {
            "action_id": result.action_id,
            "claim_type": claim_type,
            "statement": statement,
            "evidence_refs": normalized_evidence_refs,
        },
    )
    return {
        "claim_id": f"claim://{claim_id}",
        "claim_type": claim_type,
        "statement": statement,
        "evidence_refs": normalized_evidence_refs,
        "confidence": confidence,
        "verified": verified,
    }


def _uao_record_effect_classes(result: UniversalActionResult) -> list[str]:
    classes = ["external_capability", "world_state"]
    if result.recovery_plan_certificate is not None:
        classes.append("recovery_plan")
    if (
        result.dispatch_result is not None
        and result.dispatch_result.execution_result is not None
    ):
        for effect in result.dispatch_result.execution_result.actual_effects:
            classes.append(effect.name)
    if result.learning_decision is not None:
        classes.append("memory")
    return _unique_text_list(classes)


def _uao_record_decision(result: UniversalActionResult) -> dict[str, Any]:
    if _result_requires_review(result):
        return {
            "status": "escalate",
            "reason_code": "effect_reconciliation_mismatch",
            "proof_state": "Fail",
            "solver_outcome": "AwaitingEvidence",
            "next_action": "operator_review",
            "execution_allowed": False,
        }
    if result.life_meaning_judgment is not None and result.block_reason.startswith(
        "life_meaning_judgment_"
    ):
        judgment_decision = result.life_meaning_judgment.decision
        if judgment_decision is LifeMeaningDecision.ESCALATE:
            return {
                "status": "escalate",
                "reason_code": result.block_reason,
                "proof_state": "Unknown",
                "solver_outcome": "AwaitingEvidence",
                "next_action": "operator_review",
                "execution_allowed": False,
            }
        if judgment_decision is LifeMeaningDecision.PAUSE:
            return {
                "status": "defer",
                "reason_code": result.block_reason,
                "proof_state": "Unknown",
                "solver_outcome": "AwaitingEvidence",
                "next_action": "operator_review",
                "execution_allowed": False,
            }
        return {
            "status": "block",
            "reason_code": result.block_reason,
            "proof_state": "Fail",
            "solver_outcome": "GovernanceBlocked",
            "next_action": "operator_review",
            "execution_allowed": False,
        }
    if result.dispatched:
        return {
            "status": "allow",
            "reason_code": "execution_completed",
            "proof_state": "Pass",
            "solver_outcome": "SolvedVerified"
            if result.terminal_certificate is not None
            else "SolvedUnverified",
            "next_action": "retain_receipts",
            "execution_allowed": True,
        }
    if result.block_reason == "operating_substrate_self_model_missing":
        return {
            "status": "block",
            "reason_code": result.block_reason,
            "proof_state": "Unknown",
            "solver_outcome": "AwaitingEvidence",
            "next_action": "collect_operating_substrate_evidence",
            "execution_allowed": False,
        }
    return {
        "status": "block",
        "reason_code": result.block_reason or "execution_blocked",
        "proof_state": "Fail",
        "solver_outcome": "GovernanceBlocked",
        "next_action": "operator_review",
        "execution_allowed": False,
    }


def _uao_record_receipt_refs(
    *,
    result: UniversalActionResult,
    decision_status: str,
    reconciliation_ref: str | None,
    memory_ref: str | None,
    whqr_replay_binding: Mapping[str, str] | None,
) -> dict[str, str]:
    refs = {
        "trace": stable_identifier(
            "universal-action-trace-receipt",
            {"action_id": result.action_id, "trace_ref": result.trace_ref},
        ),
        "admission": result.admission_receipt_ref,
        "closure": stable_identifier(
            "universal-action-closure-receipt",
            {
                "action_id": result.action_id,
                "trace_ref": result.trace_ref,
                "closure_state": result.closure_state,
                "decision_status": decision_status,
                "reconciliation_ref": reconciliation_ref or "",
                "memory_ref": memory_ref or "",
                **_whqr_replay_confirmation_payload(whqr_replay_binding),
            },
        ),
        "reconciliation": stable_identifier(
            "universal-action-reconciliation-receipt",
            {
                "action_id": result.action_id,
                "trace_ref": result.trace_ref,
                "closure_state": result.closure_state,
            },
        ),
    }
    if result.execution_receipt_ref is not None:
        refs["execution"] = result.execution_receipt_ref
    return refs


def _uao_record_outcome_ref(result: UniversalActionResult) -> str | None:
    if (
        result.dispatch_result is None
        or result.dispatch_result.execution_result is None
    ):
        return None
    return f"outcome://{result.dispatch_result.execution_result.execution_id}"


def _uao_record_reconciliation_ref(result: UniversalActionResult) -> str | None:
    if not result.dispatched:
        return None
    return f"reconciliation://{result.action_id}"


def _uao_record_memory_ref(result: UniversalActionResult) -> str | None:
    if (
        result.terminal_certificate is not None
        and result.terminal_certificate.memory_entry_id is not None
    ):
        return f"memory://{result.terminal_certificate.memory_entry_id}"
    if result.learning_decision is not None:
        return f"memory://{result.learning_decision.knowledge_id}"
    return None


def _uao_record_whqr_replay_binding(result: UniversalActionResult) -> dict[str, str] | None:
    certificate = result.terminal_certificate
    if certificate is None:
        return None
    metadata = certificate.metadata
    canonical_json = metadata.get("whqr_canonical_json")
    canonical_hash = metadata.get("whqr_canonical_hash")
    semantics_hash = metadata.get("whqr_semantics_hash")
    whqr_version = metadata.get("whqr_version")
    if (
        canonical_json is None
        and canonical_hash is None
        and semantics_hash is None
        and whqr_version is None
    ):
        return None
    if not isinstance(canonical_json, str) or not canonical_json:
        raise RuntimeCoreInvariantError(
            "UAO closure requires WHQR canonical replay document"
        )
    if not isinstance(canonical_hash, str) or not canonical_hash:
        raise RuntimeCoreInvariantError("UAO closure requires WHQR canonical hash")
    try:
        document = WHQRDocument.from_canonical_json(
            canonical_json,
            expected_canonical_hash=canonical_hash,
        )
    except ValueError as exc:
        raise RuntimeCoreInvariantError(
            "UAO closure WHQR replay document is invalid"
        ) from exc
    if semantics_hash is not None and semantics_hash != document.semantics_hash:
        raise RuntimeCoreInvariantError("UAO closure WHQR semantics hash mismatch")
    if whqr_version is not None and whqr_version != document.whqr_version:
        raise RuntimeCoreInvariantError("UAO closure WHQR version mismatch")
    return {
        "replay_ref": f"whqr://replay/{canonical_hash}",
        "canonical_hash": canonical_hash,
        "semantics_hash": document.semantics_hash,
        "version": document.whqr_version,
    }


def _uao_record_pipeline_stages(
    *,
    result: UniversalActionResult,
    action_envelope: Mapping[str, Any],
    capability_refs: list[str],
    input_refs: list[str],
    receipt_refs: Mapping[str, str],
    fracture_report: Mapping[str, Any],
    outcome_ref: str | None,
    reconciliation_ref: str | None,
    memory_ref: str | None,
) -> list[dict[str, Any]]:
    blocked = result.blocked
    capability_bound = result.capability_decision is not None and (
        result.capability_decision.status is CommandCapabilityAdmissionStatus.ACCEPTED
    )
    execution_completed = result.dispatched and outcome_ref is not None
    reconciliation_completed = execution_completed
    failure_reason = result.block_reason or "execution_blocked"
    fracture_status = (
        "blocked" if fracture_report.get("status") == "failed" else "completed"
    )
    fracture_failure_reason = (
        "fracture_blocking_checks"
        if fracture_report.get("status") == "failed"
        else None
    )
    receipt_set_ref = f"receipt-set://{result.action_id}"
    memory_output_ref = memory_ref or f"memory://{result.action_id}/blocked"
    closure_ref = f"closure://{result.action_id}"
    return [
        _uao_stage(
            "stage_action",
            1,
            "action",
            "completed",
            [action_envelope["source"]],
            [f"envelope://{result.action_id}"],
        ),
        _uao_stage(
            "stage_evidence",
            2,
            "evidence",
            "completed",
            input_refs,
            [f"evidence-set://{result.action_id}"],
        ),
        _uao_stage(
            "stage_trace",
            3,
            "trace",
            "completed",
            [f"evidence-set://{result.action_id}"],
            [result.trace_ref],
            receipt_refs["trace"],
        ),
        _uao_stage(
            "stage_admission",
            4,
            "admission",
            "completed" if not blocked else "blocked",
            [result.trace_ref],
            [f"decision://{result.action_id}"],
            receipt_refs["admission"],
            None if not blocked else failure_reason,
        ),
        _uao_stage(
            "stage_capability",
            5,
            "capability",
            "completed" if capability_bound else "skipped",
            capability_refs,
            [f"capability-binding://{result.action_id}"] if capability_bound else [],
            None,
            None if capability_bound else failure_reason,
        ),
        _uao_stage(
            "stage_fracture",
            6,
            "fracture",
            fracture_status,
            [f"capability-binding://{result.action_id}"]
            if capability_bound
            else capability_refs,
            [str(fracture_report["report_ref"])],
            None,
            fracture_failure_reason,
        ),
        _uao_stage(
            "stage_execution",
            7,
            "execution",
            "completed" if execution_completed else "skipped",
            [f"capability-binding://{result.action_id}"]
            if capability_bound
            else capability_refs,
            [outcome_ref] if outcome_ref is not None else [],
            receipt_refs.get("execution"),
            None if execution_completed else failure_reason,
        ),
        _uao_stage(
            "stage_receipt",
            8,
            "receipt",
            "completed",
            [outcome_ref]
            if outcome_ref is not None
            else [f"decision://{result.action_id}"],
            [receipt_set_ref],
            receipt_refs.get("execution", receipt_refs["admission"]),
        ),
        _uao_stage(
            "stage_reconciliation",
            9,
            "reconciliation",
            "completed" if reconciliation_completed else "skipped",
            [receipt_set_ref],
            [reconciliation_ref] if reconciliation_ref is not None else [],
            receipt_refs.get("reconciliation") if reconciliation_completed else None,
            None if reconciliation_completed else failure_reason,
        ),
        _uao_stage(
            "stage_memory",
            10,
            "memory",
            "completed",
            [f"reconciliation://{result.action_id}"]
            if reconciliation_completed
            else [f"decision://{result.action_id}"],
            [memory_output_ref],
        ),
        _uao_stage(
            "stage_closure",
            11,
            "closure",
            "completed",
            [memory_output_ref],
            [closure_ref],
            receipt_refs["closure"],
        ),
    ]


def _uao_stage(
    stage_id: str,
    stage_order: int,
    stage_kind: str,
    status: str,
    input_refs: list[str],
    output_refs: list[str],
    receipt_ref: str | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "stage_order": stage_order,
        "stage_kind": stage_kind,
        "status": status,
        "input_refs": input_refs,
        "output_refs": output_refs,
        "receipt_ref": receipt_ref,
        "failure_reason": failure_reason,
    }


def _uao_record_admission_guards(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
    capability_refs: list[str],
    evidence_refs: list[str],
    policy_refs: list[str],
    temporal_refs: list[str],
    recovery_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blocked_guard = _uao_record_blocked_guard(result)
    recovery_refs = _unique_text_list(
        (
            _optional_text_value(recovery_plan.get("recovery_plan_ref")) or "",
            _optional_text_value(recovery_plan.get("rollback_plan_ref")) or "",
            _optional_text_value(recovery_plan.get("compensation_plan_ref")) or "",
        )
    )
    if not recovery_refs:
        recovery_refs = [f"recovery://{request.dispatch_request.route}"]
    guard_specs = (
        ("identity_valid", "actor_identity_bound", [f"actor://{request.actor_id}"]),
        ("tenant_valid", "tenant_scope_resolved", [f"tenant://{request.tenant_id}"]),
        ("authority_valid", "authority_proof_valid", capability_refs),
        ("policy_allows", "policy_allows_action", policy_refs),
        ("risk_acceptable", "risk_within_governed_threshold", policy_refs),
        (
            "budget_available",
            "estimated_budget_available",
            [f"budget://{request.tenant_id}/universal-action"],
        ),
        ("evidence_sufficient", "evidence_surface_available", evidence_refs),
        ("temporal_window_valid", "temporal_context_valid", temporal_refs),
        ("capability_certified", "capability_admitted", capability_refs),
        (
            "recovery_available",
            "rollback_or_review_path_available",
            recovery_refs,
        ),
        ("receipt_emittable", "receipt_refs_emitted", [result.admission_receipt_ref]),
    )
    guards: list[dict[str, Any]] = []
    for guard_name, reason_code, refs in guard_specs:
        if guard_name == blocked_guard:
            verdict = _blocked_admission_guard_verdict(result)
            proof_state = (
                "Unknown"
                if result.block_reason == "operating_substrate_self_model_missing"
                or verdict in {"deferred", "escalated"}
                else "Fail"
            )
            guards.append(
                {
                    "guard": guard_name,
                    "verdict": verdict,
                    "proof_state": proof_state,
                    "reason_code": (
                        "effect_reconciliation_mismatch"
                        if _result_requires_review(result)
                        else result.block_reason or "execution_blocked"
                    ),
                    "evidence_refs": _unique_text_list(refs),
                }
            )
            continue
        guards.append(
            {
                "guard": guard_name,
                "verdict": "passed",
                "proof_state": "Pass",
                "reason_code": reason_code,
                "evidence_refs": _unique_text_list(refs),
            }
        )
    return guards


def _blocked_admission_guard_verdict(result: UniversalActionResult) -> str:
    if _result_requires_review(result):
        return "escalated"
    if result.life_meaning_judgment is not None and result.block_reason.startswith(
        "life_meaning_judgment_"
    ):
        if result.life_meaning_judgment.decision is LifeMeaningDecision.PAUSE:
            return "deferred"
        if result.life_meaning_judgment.decision is LifeMeaningDecision.ESCALATE:
            return "escalated"
    return "blocked"


def _uao_record_blocked_guard(result: UniversalActionResult) -> str | None:
    if _result_requires_review(result):
        return "risk_acceptable"
    if result.dispatched:
        return None
    if result.block_reason == "open_world_contradictions":
        return "evidence_sufficient"
    if result.block_reason.startswith("operating_substrate_"):
        return "evidence_sufficient"
    if result.block_reason == "capability_admission_rejected":
        return "capability_certified"
    if result.block_reason == "recovery_plan_missing":
        return "recovery_available"
    if result.block_reason == "governed_action_admission_rejected":
        return "authority_valid"
    if result.block_reason.startswith("simulation_"):
        return "risk_acceptable"
    if result.block_reason:
        return "policy_allows"
    return "receipt_emittable"


def _uao_record_receipts(
    *,
    result: UniversalActionResult,
    receipt_refs: Mapping[str, str],
    outcome_ref: str | None,
    reconciliation_ref: str | None,
    memory_ref: str | None,
    whqr_replay_binding: Mapping[str, str] | None,
) -> list[dict[str, Any]]:
    receipts = [
        _uao_receipt(
            receipt_refs["trace"], "R1", "trace", "stage_trace", result.trace_ref, False
        ),
        _uao_receipt(
            receipt_refs["admission"],
            "R1",
            "admission",
            "stage_admission",
            "allow"
            if result.dispatched
            else result.block_reason or "execution_blocked",
            False,
        ),
    ]
    if (
        result.dispatched
        and result.execution_receipt_ref is not None
        and outcome_ref is not None
    ):
        receipts.append(
            _uao_receipt(
                result.execution_receipt_ref,
                "R2",
                "execution",
                "stage_execution",
                outcome_ref,
                True,
            )
        )
        receipts.append(
            _uao_receipt(
                receipt_refs["reconciliation"],
                "R2",
                "reconciliation",
                "stage_reconciliation",
                reconciliation_ref or outcome_ref,
                True,
            )
        )
    receipts.append(
        _uao_receipt(
            receipt_refs["closure"],
            "R3",
            "closure",
            "stage_closure",
            _uao_closure_confirmation(
                closure_state=result.closure_state,
                reconciliation_ref=reconciliation_ref,
                memory_ref=memory_ref,
                whqr_replay_binding=whqr_replay_binding,
            ),
            result.dispatched,
        )
    )
    return receipts


def _uao_receipt(
    receipt_id: str,
    tier: str,
    kind: str,
    stage_id: str,
    confirms: str,
    external_state_confirmed: bool,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "tier": tier,
        "kind": kind,
        "stage_id": stage_id,
        "confirms": confirms,
        "external_state_confirmed": external_state_confirmed,
    }


def _uao_record_reconciliation(
    *,
    result: UniversalActionResult,
    outcome_ref: str | None,
) -> dict[str, Any]:
    if _result_requires_review(result):
        return {
            "status": "mismatched",
            "observed_outcome_ref": outcome_ref,
            "required_for_closure": True,
            "mismatch_reason": "effect_reconciliation_mismatch",
        }
    if result.dispatched:
        return {
            "status": "matched",
            "observed_outcome_ref": outcome_ref,
            "required_for_closure": True,
            "mismatch_reason": None,
        }
    return {
        "status": "blocked",
        "observed_outcome_ref": None,
        "required_for_closure": False,
        "mismatch_reason": result.block_reason or "execution_blocked",
    }


def _uao_record_memory_update(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
    action_envelope: Mapping[str, Any],
    memory_ref: str | None,
) -> dict[str, Any]:
    if _result_requires_review(result):
        return {
            "status": "blocked",
            "memory_ref": None,
            "learning_allowed": False,
            "constitution": _uao_record_memory_constitution(
                request=request,
                result=result,
                action_envelope=action_envelope,
                memory_ref=None,
                status="blocked",
                learning_allowed=False,
            ),
        }
    if (
        result.learning_decision is not None
        and result.learning_decision.status is LearningAdmissionStatus.ADMIT
        and memory_ref is not None
    ):
        return {
            "status": "recorded",
            "memory_ref": memory_ref,
            "learning_allowed": True,
            "constitution": _uao_record_memory_constitution(
                request=request,
                result=result,
                action_envelope=action_envelope,
                memory_ref=memory_ref,
                status="recorded",
                learning_allowed=True,
            ),
        }
    if result.dispatched:
        return {
            "status": "not_required",
            "memory_ref": memory_ref,
            "learning_allowed": False,
            "constitution": _uao_record_memory_constitution(
                request=request,
                result=result,
                action_envelope=action_envelope,
                memory_ref=memory_ref,
                status="not_required",
                learning_allowed=False,
            ),
        }
    return {
        "status": "not_allowed",
        "memory_ref": None,
        "learning_allowed": False,
        "constitution": _uao_record_memory_constitution(
            request=request,
            result=result,
            action_envelope=action_envelope,
            memory_ref=None,
            status="not_allowed",
            learning_allowed=False,
        ),
    }


def _uao_record_memory_constitution(
    *,
    request: UniversalActionRequest,
    result: UniversalActionResult,
    action_envelope: Mapping[str, Any],
    memory_ref: str | None,
    status: str,
    learning_allowed: bool,
) -> dict[str, Any]:
    source_refs = _unique_text_list(
        (
            memory_ref,
            result.trace_ref,
            result.admission_receipt_ref,
            result.execution_receipt_ref,
            result.terminal_certificate.certificate_id
            if result.terminal_certificate is not None
            else None,
        )
    )
    if status == "recorded" and memory_ref is not None:
        allowed_uses = ["closure_audit", "planning", "learning"]
    elif memory_ref is not None:
        allowed_uses = ["closure_audit"]
    else:
        allowed_uses = []
    forbidden_uses = ["external_sharing", "model_training"]
    if not learning_allowed:
        forbidden_uses.append("learning")
    requested_at = str(action_envelope.get("requested_at") or "")
    sensitivity = request.metadata.get("memory_sensitivity", "operational")
    if sensitivity not in {
        "public",
        "operational",
        "tenant_confidential",
        "financial",
        "security",
        "personal",
        "regulated",
    }:
        sensitivity = "operational"
    expires_at = request.metadata.get("memory_expires_at")
    return {
        "constitution_ref": "memory-constitution://"
        + stable_identifier(
            "memory-constitution",
            {
                "action_id": result.action_id,
                "memory_ref": memory_ref or "none",
                "status": status,
            },
        ),
        "source_refs": source_refs,
        "owner_ref": f"tenant://{request.tenant_id}",
        "scope_ref": f"tenant://{request.tenant_id}",
        "confidence": 1.0 if status == "recorded" else 0.0,
        "sensitivity": sensitivity,
        "expires_at": expires_at if isinstance(expires_at, str) and expires_at else None,
        "allowed_uses": allowed_uses,
        "forbidden_uses": _unique_text_list(forbidden_uses),
        "evidence_refs": source_refs if status == "recorded" else [],
        "last_verified_at": requested_at if status == "recorded" else None,
        "mutation_history_refs": [result.trace_ref] if status == "recorded" else [],
    }


def _uao_closure_confirmation(
    *,
    closure_state: str,
    reconciliation_ref: str | None,
    memory_ref: str | None,
    whqr_replay_binding: Mapping[str, str] | None = None,
) -> str:
    payload = {
        "closure_state": closure_state,
        "reconciliation_ref": reconciliation_ref or "",
        "memory_ref": memory_ref or "",
    }
    payload.update(_whqr_replay_confirmation_payload(whqr_replay_binding))
    return stable_identifier("universal-action-closure-confirmation", payload)


def _whqr_replay_confirmation_payload(
    whqr_replay_binding: Mapping[str, str] | None,
) -> dict[str, str]:
    if whqr_replay_binding is None:
        return {}
    return {
        "whqr_replay_ref": whqr_replay_binding.get("replay_ref", ""),
        "whqr_canonical_hash": whqr_replay_binding.get("canonical_hash", ""),
        "whqr_semantics_hash": whqr_replay_binding.get("semantics_hash", ""),
        "whqr_version": whqr_replay_binding.get("version", ""),
    }


def _uao_record_lineage(result: UniversalActionResult) -> dict[str, Any]:
    delta_ref = stable_identifier(
        "universal-action-delta",
        {
            "action_id": result.action_id,
            "proof_hash": result.proof_hash,
            "closure_state": result.closure_state,
        },
    )
    delta = {
        "delta_id": delta_ref,
        "reason": _uao_lineage_reason(result),
        "logged_in_lineage": True,
    }
    accepted = result.dispatched and not _result_requires_review(result)
    return {
        "delta_ref": delta_ref,
        "logged_in_lineage": True,
        "accepted_deltas": [delta] if accepted else [],
        "rejected_deltas": [] if accepted else [delta],
    }


def _result_requires_review(result: UniversalActionResult) -> bool:
    return (
        result.terminal_certificate is not None
        and result.terminal_certificate.disposition
        is TerminalClosureDisposition.REQUIRES_REVIEW
    )


def _uao_lineage_reason(result: UniversalActionResult) -> str:
    if _result_requires_review(result):
        return "effect_reconciliation_mismatch"
    if result.dispatched:
        return "execution_allowed"
    return result.block_reason or "execution_blocked"


def _optional_text_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _text_iterable(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(
        item.strip() for item in value if isinstance(item, str) and item.strip()
    )


def _unique_text_list(values: Any) -> list[str]:
    result: list[str] = []
    for value in _text_iterable(values):
        if value not in result:
            result.append(value)
    return result
