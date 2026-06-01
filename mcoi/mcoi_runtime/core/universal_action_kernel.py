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
  - Abort, escalation, and missing capability decisions fail closed.
  - Successful dispatch can be closed and admitted to learning only through
    explicit verification, reconciliation, certificate, and memory binding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.effect_assurance import EffectReconciliation, ReconciliationStatus
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.governed_action import (
    AuthorityProofRecord,
    GovernedAction,
    GovernedActionState,
    TypedIntentRecord,
    build_capability_passport,
)
from mcoi_runtime.contracts.goal import GoalDescriptor, GoalPriority
from mcoi_runtime.contracts.governed_capability_fabric import (
    CommandCapabilityAdmissionDecision,
    CommandCapabilityAdmissionStatus,
)
from mcoi_runtime.contracts.learning import LearningAdmissionDecision
from mcoi_runtime.contracts.plan import Plan, PlanItem
from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationComparison,
    SimulationOption,
    SimulationRequest,
    SimulationVerdict,
    VerdictType,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureCertificate
from mcoi_runtime.contracts.verification import VerificationCheck, VerificationResult, VerificationStatus
from mcoi_runtime.contracts.world_state import WorldStateSnapshot
from mcoi_runtime.core.closure_learning import ClosureLearningAdmissionGate
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.governed_dispatcher import (
    GovernedDispatchContext,
    GovernedDispatchResult,
    GovernedDispatcher,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from mcoi_runtime.core.memory import MemoryEntry, MemoryTier
from mcoi_runtime.core.simulation import SimulationEngine
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.core.world_state import WorldStateEngine


_BLOCKING_SIMULATION_VERDICTS = frozenset({VerdictType.ABORT, VerdictType.ESCALATE})


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
            object.__setattr__(self, field_name, ensure_non_empty_text(field_name, getattr(self, field_name)))
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
class UniversalActionResult:
    """Terminal result for one universal governed action attempt."""

    action_id: str
    blocked: bool
    block_reason: str
    action_envelope: Mapping[str, Any]
    trace_ref: str
    admission_receipt_ref: str
    execution_receipt_ref: str
    closure_state: str
    goal_certificate: GoalCertificate
    world_certificate: WorldSupportCertificate
    plan_certificate: PlanCertificate | None = None
    simulation_certificate: SimulationCertificate | None = None
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
        clock: Callable[[], str],
    ) -> None:
        self._world_state = world_state
        self._simulator = simulator
        self._capability_admission = capability_admission
        self._governed_dispatcher = governed_dispatcher
        self._terminal_closure = terminal_closure
        self._learning_admission = learning_admission
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

        capability_decision = self._capability_admission.admit(
            command_id=request.intent_id,
            intent_name=request.dispatch_request.route,
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
                capability_decision=capability_decision,
            )

        try:
            governed_action = self._build_governed_action(
                request=request,
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
                capability_decision=capability_decision,
            )

        plan_certificate = self._build_plan_certificate(
            request=request,
            world_certificate=world_certificate,
            capability_decision=capability_decision,
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
            capability_decision=capability_decision,
            governed_action=governed_action,
            dispatch_result=dispatch_result,
            terminal_certificate=terminal_certificate,
            learning_decision=learning_decision,
        )
        return self._with_proof_hash(result)

    def _build_goal_certificate(self, request: UniversalActionRequest, issued_at: str) -> GoalCertificate:
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
            certificate_id=stable_identifier("goal-cert", {"goal_id": goal.goal_id, "issued_at": issued_at}),
            goal=goal,
            issued_at=issued_at,
        )

    def _build_world_certificate(self, request: UniversalActionRequest, issued_at: str) -> WorldSupportCertificate:
        snapshot = self._world_state.assemble_snapshot()
        allows_execution = len(snapshot.unresolved_contradictions) == 0
        reason = "world_state_supports_execution" if allows_execution else "open_world_contradictions"
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
            plan_id=stable_identifier("plan", {"intent_id": request.intent_id, "issued_at": issued_at}),
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
            certificate_id=stable_identifier("plan-cert", {"plan_id": plan.plan_id, "issued_at": issued_at}),
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
            request_id=stable_identifier("sim-request", {"plan_id": plan_certificate.plan.plan_id}),
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
        capability_decision: CommandCapabilityAdmissionDecision | None = None,
        governed_action: GovernedAction | None = None,
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
            execution_receipt_ref="",
            closure_state="blocked",
            goal_certificate=goal_certificate,
            world_certificate=world_certificate,
            plan_certificate=plan_certificate,
            simulation_certificate=simulation_certificate,
            capability_decision=capability_decision,
            governed_action=governed_action,
        )
        return self._with_proof_hash(result)

    def _build_governed_action(
        self,
        *,
        request: UniversalActionRequest,
        capability_decision: CommandCapabilityAdmissionDecision,
        issued_at: str,
    ) -> GovernedAction:
        capability_entry = self._capability_admission.capability_for_intent(
            request.dispatch_request.route
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
        typed_intent = TypedIntentRecord(
            command_id=request.intent_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            intent_name=request.dispatch_request.route,
            objective=request.objective,
            input_hash=stable_identifier(
                "typed-intent-input",
                {
                    "route": request.dispatch_request.route,
                    "template": request.dispatch_request.template,
                    "bindings": request.dispatch_request.bindings,
                },
            ),
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
            approval_refs=_text_tuple_from_metadata(request.metadata, "approval_refs"),
        )
        return GovernedAction(
            governed_action_id=stable_identifier(
                "governed-action",
                {
                    "tenant_id": request.tenant_id,
                    "actor_id": request.actor_id,
                    "intent_id": request.intent_id,
                    "capability_id": capability_decision.capability_id,
                    "passport_hash": passport_hash,
                },
            ),
            command_id=request.intent_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            typed_intent=typed_intent,
            capability_passport=capability_passport,
            authority_proof=authority_proof,
            state=GovernedActionState.ADMITTED,
            issued_at=issued_at,
            metadata={
                "capability_decision_reason": capability_decision.reason,
                "domain": capability_decision.domain,
                "owner_team": capability_decision.owner_team,
            },
        )

    def _close_and_admit_learning(
        self,
        *,
        request: UniversalActionRequest,
        dispatch_result: GovernedDispatchResult,
        capability_decision: CommandCapabilityAdmissionDecision,
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
            issued_at=issued_at,
        )
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
            evidence_refs=tuple(evidence.uri or evidence.description for evidence in verification_result.evidence),
            memory_entry=memory_entry,
            graph_refs=(request.dispatch_request.goal_id,),
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
            "plan_certificate_id": result.plan_certificate.certificate_id if result.plan_certificate else "",
            "simulation_certificate_id": (
                result.simulation_certificate.certificate_id if result.simulation_certificate else ""
            ),
            "capability_status": result.capability_decision.status.value if result.capability_decision else "",
            "capability_id": result.capability_decision.capability_id if result.capability_decision else "",
            "governed_action_id": result.governed_action.governed_action_id if result.governed_action else "",
            "dispatch_ledger_hash": result.dispatch_result.ledger_hash if result.dispatch_result else "",
            "terminal_certificate_id": (
                result.terminal_certificate.certificate_id if result.terminal_certificate else ""
            ),
            "learning_admission_id": result.learning_decision.admission_id if result.learning_decision else "",
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
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
        raise RuntimeCoreInvariantError("capability_admission must be a CommandCapabilityAdmissionGate")
    if not isinstance(governed_dispatcher, GovernedDispatcher):
        raise RuntimeCoreInvariantError("governed_dispatcher must be a GovernedDispatcher")
    return UniversalActionKernel(
        world_state=world_state,
        simulator=simulator,
        capability_admission=capability_admission,
        governed_dispatcher=governed_dispatcher,
        terminal_closure=terminal_closure,
        learning_admission=learning_admission,
        clock=clock,
    )


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
    capability_refs = (
        (capability_decision.capability_id,)
        if capability_decision is not None and capability_decision.capability_id
        else ()
    )
    return {
        "actor": request.actor_id,
        "tenant": request.tenant_id,
        "intent": request.intent_id,
        "target": request.dispatch_request.route,
        "risk": request.risk_level.value,
        "requested_at": issued_at,
        "approval_refs": _text_tuple_from_metadata(request.metadata, "approval_refs"),
        "evidence_refs": _text_tuple_from_metadata(request.metadata, "evidence_refs"),
        "capability_refs": capability_refs,
    }


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


def _build_admission_receipt_ref(*, action_id: str, trace_ref: str, decision_status: str) -> str:
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
) -> str:
    if dispatch_result.blocked or dispatch_result.execution_result is None:
        return ""
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
        return terminal_certificate.disposition.value
    if blocked:
        return "blocked"
    if dispatch_result is not None:
        return "dispatched"
    return "pending"


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
        metadata={"kernel": "universal_action", "intent_id": request.intent_id, "goal_id": execution_result.goal_id},
    )


def _build_reconciliation(
    *,
    request: UniversalActionRequest,
    execution_result: ExecutionResult,
    verification_result: VerificationResult,
    capability_decision: CommandCapabilityAdmissionDecision,
    issued_at: str,
) -> EffectReconciliation:
    effect_names = tuple(effect.name for effect in execution_result.actual_effects)
    return EffectReconciliation(
        reconciliation_id=stable_identifier(
            "universal-reconciliation",
            {
                "intent_id": request.intent_id,
                "execution_id": execution_result.execution_id,
                "verification_id": verification_result.verification_id,
            },
        ),
        command_id=request.intent_id,
        effect_plan_id=stable_identifier(
            "universal-effect-plan",
            {
                "intent_id": request.intent_id,
                "capability_id": capability_decision.capability_id,
            },
        ),
        status=ReconciliationStatus.MATCH,
        matched_effects=effect_names or ("execution_completed",),
        missing_effects=(),
        unexpected_effects=(),
        verification_result_id=verification_result.verification_id,
        case_id=None,
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
