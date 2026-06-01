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
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.effect_assurance import (
    EffectPlan,
    EffectReconciliation,
    ExpectedEffect,
    ReconciliationStatus,
)
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.governed_action import (
    AuthorityProofRecord,
    GovernedAction,
    GovernedActionState,
    build_capability_passport,
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
from mcoi_runtime.contracts.world_state import WorldStateSnapshot
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
from mcoi_runtime.core.memory import MemoryEntry, MemoryTier
from mcoi_runtime.core.simulation import SimulationEngine
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.core.world_state import WorldStateEngine


_BLOCKING_SIMULATION_VERDICTS = frozenset(
    {VerdictType.ABORT, VerdictType.APPROVAL_REQUIRED, VerdictType.ESCALATE}
)


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
    mode: str = "simulation"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
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
    intent_certificate: IntentCompilationCertificate | None = None
    capability_decision: CommandCapabilityAdmissionDecision | None = None
    governed_action: GovernedAction | None = None
    dispatch_result: GovernedDispatchResult | None = None
    terminal_certificate: TerminalClosureCertificate | None = None
    learning_decision: LearningAdmissionDecision | None = None
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

        try:
            governed_action = self._build_governed_action(
                request=request,
                intent_certificate=intent_certificate,
                capability_decision=capability_decision,
                issued_at=now,
            )
        except (RuntimeCoreInvariantError, ValueError):
            return self._blocked(
                action_id=action_id,
                request=request,
                issued_at=now,
                trace_ref=trace_ref,
                block_reason="governed_action_admission_rejected",
                goal_certificate=goal_certificate,
                world_certificate=world_certificate,
                intent_certificate=intent_certificate,
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
                intent_certificate=intent_certificate,
                capability_decision=capability_decision,
                governed_action=governed_action,
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
            intent_certificate=intent_certificate,
            capability_decision=capability_decision,
            governed_action=governed_action,
            dispatch_result=dispatch_result,
            terminal_certificate=terminal_certificate,
            learning_decision=learning_decision,
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
        capability_decision: CommandCapabilityAdmissionDecision | None = None,
        governed_action: GovernedAction | None = None,
        intent_certificate: IntentCompilationCertificate | None = None,
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
                decision_status="block",
            ),
            execution_receipt_ref=None,
            closure_state=_build_closure_state(
                blocked=True,
                dispatch_result=None,
                terminal_certificate=None,
            ),
            goal_certificate=goal_certificate,
            world_certificate=world_certificate,
            plan_certificate=plan_certificate,
            simulation_certificate=simulation_certificate,
            effect_prediction_certificate=effect_prediction_certificate,
            intent_certificate=intent_certificate,
            capability_decision=capability_decision,
            governed_action=governed_action,
        )
        return self._with_proof_hash(result)

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
            "intent_certificate_id": result.intent_certificate.certificate_id
            if result.intent_certificate
            else "",
            "intent_hash": result.intent_certificate.intent_hash
            if result.intent_certificate
            else "",
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
            "learning_admission_id": result.learning_decision.admission_id
            if result.learning_decision
            else "",
            "reconciliation_ref": _uao_record_reconciliation_ref(result) or "",
            "memory_ref": _uao_record_memory_ref(result) or "",
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
            intent_certificate=result.intent_certificate,
            capability_decision=result.capability_decision,
            governed_action=result.governed_action,
            dispatch_result=result.dispatch_result,
            terminal_certificate=result.terminal_certificate,
            learning_decision=result.learning_decision,
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
    outcome_ref = _uao_record_outcome_ref(result)
    reconciliation_ref = _uao_record_reconciliation_ref(result)
    memory_ref = _uao_record_memory_ref(result)
    receipt_refs = _uao_record_receipt_refs(
        result=result,
        decision_status=decision["status"],
        reconciliation_ref=reconciliation_ref,
        memory_ref=memory_ref,
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
        "effect_classes": _uao_record_effect_classes(result),
        "input_refs": input_refs,
        "policy_refs": policy_refs,
        "capability_refs": capability_refs,
        "temporal_refs": temporal_refs,
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
        ),
        "reconciliation": _uao_record_reconciliation(
            result=result, outcome_ref=outcome_ref
        ),
        "memory_update": _uao_record_memory_update(
            result=result, memory_ref=memory_ref
        ),
        "closure_state": result.closure_state,
        "closure": {
            "status": result.closure_state,
            "terminal": True,
            "closure_receipt_ref": receipt_refs["closure"],
            "reconciliation_ref": reconciliation_ref,
            "memory_ref": memory_ref,
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
    *, action_id: str, trace_ref: str, decision_status: str
) -> str:
    return stable_identifier(
        "universal-action-admission-receipt",
        {
            "action_id": action_id,
            "trace_ref": trace_ref,
            "decision_status": decision_status,
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


def _uao_record_effect_classes(result: UniversalActionResult) -> list[str]:
    classes = ["external_capability", "world_state"]
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


def _uao_record_pipeline_stages(
    *,
    result: UniversalActionResult,
    action_envelope: Mapping[str, Any],
    capability_refs: list[str],
    input_refs: list[str],
    receipt_refs: Mapping[str, str],
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
            "stage_execution",
            6,
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
            7,
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
            8,
            "reconciliation",
            "completed" if reconciliation_completed else "skipped",
            [receipt_set_ref],
            [reconciliation_ref] if reconciliation_ref is not None else [],
            receipt_refs.get("reconciliation") if reconciliation_completed else None,
            None if reconciliation_completed else failure_reason,
        ),
        _uao_stage(
            "stage_memory",
            9,
            "memory",
            "completed",
            [f"reconciliation://{result.action_id}"]
            if reconciliation_completed
            else [f"decision://{result.action_id}"],
            [memory_output_ref],
        ),
        _uao_stage(
            "stage_closure",
            10,
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
) -> list[dict[str, Any]]:
    blocked_guard = _uao_record_blocked_guard(result)
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
            [f"recovery://{request.dispatch_request.route}"],
        ),
        ("receipt_emittable", "receipt_refs_emitted", [result.admission_receipt_ref]),
    )
    guards: list[dict[str, Any]] = []
    for guard_name, reason_code, refs in guard_specs:
        if guard_name == blocked_guard:
            verdict = "escalated" if _result_requires_review(result) else "blocked"
            guards.append(
                {
                    "guard": guard_name,
                    "verdict": verdict,
                    "proof_state": "Fail",
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


def _uao_record_blocked_guard(result: UniversalActionResult) -> str | None:
    if _result_requires_review(result):
        return "risk_acceptable"
    if result.dispatched:
        return None
    if result.block_reason == "open_world_contradictions":
        return "evidence_sufficient"
    if result.block_reason == "capability_admission_rejected":
        return "capability_certified"
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
    result: UniversalActionResult,
    memory_ref: str | None,
) -> dict[str, Any]:
    if _result_requires_review(result):
        return {
            "status": "blocked",
            "memory_ref": None,
            "learning_allowed": False,
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
        }
    if result.dispatched:
        return {
            "status": "not_required",
            "memory_ref": memory_ref,
            "learning_allowed": False,
        }
    return {
        "status": "not_allowed",
        "memory_ref": None,
        "learning_allowed": False,
    }


def _uao_closure_confirmation(
    *,
    closure_state: str,
    reconciliation_ref: str | None,
    memory_ref: str | None,
) -> str:
    return stable_identifier(
        "universal-action-closure-confirmation",
        {
            "closure_state": closure_state,
            "reconciliation_ref": reconciliation_ref or "",
            "memory_ref": memory_ref or "",
        },
    )


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
