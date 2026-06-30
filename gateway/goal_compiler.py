"""Gateway goal compiler.

Purpose: Compile a natural-language message into a governed goal, subgoals,
    plan DAG steps, preconditions, postconditions, evidence obligations,
    rollback obligations, approval requirements, deterministic plan
    certificate, and USCCGC-R2 reflexive audit evidence.

Boundary (read before wiring this anywhere):
    This is the GATEWAY PLANNING / SIMULATION lineage. It produces a plan
    and a certificate; it never executes, dispatches, promotes, or commits
    anything. Its sole non-test consumer is `gateway.causal_simulator`,
    which uses the compiled plan for what-if analysis.

    It is NOT the live execution spine. The production acting path is
    `mcoi_runtime.whqr.goal_compiler.compile_goal_from_whqr` →
    `mcoi_runtime.core.whqr_mil_orchestrator.run_whqr_mil_orchestration`
    (WHQR expression → MIL program → governed dispatch → terminal
    certificate → learning → audit). That spine — not this module — is
    where meta-reasoning gating and complexity metering are wired.

    Do not import this module from a router or server-wiring module. The
    one-consumer boundary is enforced by
    `tests/test_gateway/test_goal_compiler.py`; wiring it into execution
    will fail that suite by design.
Governance scope: goal admission, plan-step gating, evidence projection,
    capability passport binding, rollback coverage, and world-state anchoring.
Dependencies: gateway.plan, gateway.command_spine, and optional world state
    projections.
Invariants:
  - No executable plan is emitted without a typed capability plan.
  - Every step carries preconditions, postconditions, required evidence, and
    recovery classification.
  - Mutating or high-risk steps require rollback, compensation, or review.
  - Medium and high risk steps carry explicit approval requirements.
  - The certificate hash is derived from the compiled goal and plan.
  - Goal Normal Form, observed-state facts, operator contracts, CCG+ proof
    graph, verification bundle, and compile receipt are emitted for audit.
  - This module emits plans only; it exposes no execute/dispatch/promote
    surface and is imported by exactly one non-test module
    (gateway.causal_simulator).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from gateway.command_spine import CapabilityPassport, canonical_hash, capability_passport_for
from gateway.plan import CapabilityPlan, CapabilityPlanBuilder
from gateway.world_state import WorldState


@dataclass(frozen=True, slots=True)
class Goal:
    """User or system objective with bounded success criteria."""

    goal_id: str
    tenant_id: str
    identity_id: str
    objective: str
    risk_tier: str
    success_criteria: tuple[str, ...]
    status: str = "compiled"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GoalNormalForm:
    """USCCGC-R2 normalized goal with target, metric, boundary, and evidence."""

    actor_id: str
    target_state: tuple[str, ...]
    constraints: tuple[str, ...]
    success_metrics: tuple[str, ...]
    failure_metrics: tuple[str, ...]
    boundaries: tuple[str, ...]
    reversibility_required: bool
    required_evidence: tuple[str, ...]
    temporal_conditions: tuple[str, ...]
    quality_thresholds: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorldFact:
    """Observed, inferred, assumed, stale, contradicted, or unknown fact."""

    fact_id: str
    value: str
    source: str
    status: str
    confidence: float
    freshness_ref: str = ""
    permission_ref: str = ""


@dataclass(frozen=True, slots=True)
class GapTheorem:
    """Proof-shaped gap between GNF target and reconstructed world state."""

    missing_facts: tuple[str, ...]
    missing_permissions: tuple[str, ...]
    missing_tools: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    missing_verifiers: tuple[str, ...]
    conflicts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OperatorContractProjection:
    """Registered operator contract projected from a capability passport."""

    operator_id: str
    version: str
    domain: str
    preconditions: tuple[str, ...]
    effects: tuple[str, ...]
    side_effects: tuple[str, ...]
    permissions: tuple[str, ...]
    risk_tier: str
    verifier: str
    rollback_type: str
    failure_modes: tuple[str, ...]
    evidence_required: tuple[str, ...]
    authority_required: tuple[str, ...]
    proof_type: str = "capability_passport"


@dataclass(frozen=True, slots=True)
class CausalGraphNode:
    """Node in CCG+ with kind, risk, status, and proof state."""

    node_id: str
    node_type: str
    ref: str
    status: str
    risk_tier: str = ""
    proof_state: str = "Unknown"


@dataclass(frozen=True, slots=True)
class CausalGraphEdge:
    """Typed proof edge between CCG+ nodes."""

    source: str
    target: str
    relation: str
    confidence: float
    proof_type: str


@dataclass(frozen=True, slots=True)
class CausalChainGraphPlus:
    """USCCGC-R2 graph with action, risk, verifier, receipt, and proof nodes."""

    graph_id: str
    nodes: tuple[CausalGraphNode, ...]
    edges: tuple[CausalGraphEdge, ...]
    risk_tier: str
    proof_state: str


@dataclass(frozen=True, slots=True)
class GoalCompilerVerificationBundle:
    """Compile-time proof obligations and unresolved execution blockers."""

    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]
    unresolved: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompileReceipt:
    """USCCGC-R2 compile receipt preserving causal continuity."""

    receipt_id: str
    goal_id: str
    judgment: str
    constructive_deltas: tuple[str, ...]
    fracture_deltas: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    assumptions: tuple[str, ...]
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class SubGoal:
    """Bounded portion of a goal assigned to one plan step."""

    subgoal_id: str
    goal_id: str
    step_id: str
    objective: str
    owner_id: str
    depends_on: tuple[str, ...]
    terminal_condition: str


@dataclass(frozen=True, slots=True)
class Precondition:
    """Condition that must hold before a plan step may execute."""

    precondition_id: str
    step_id: str
    condition_type: str
    required_ref: str
    satisfied: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Postcondition:
    """Condition that must hold after a plan step executes."""

    postcondition_id: str
    step_id: str
    condition_type: str
    expected_ref: str
    verification_required: bool = True


@dataclass(frozen=True, slots=True)
class RequiredEvidence:
    """Evidence required before or after a plan step."""

    evidence_id: str
    step_id: str
    evidence_type: str
    timing: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class RollbackStep:
    """Rollback, compensation, or review obligation for a plan step."""

    rollback_id: str
    step_id: str
    action_type: str
    capability_id: str = ""
    required: bool = False
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ApprovalRequirement:
    """Authority requirement for a plan step."""

    approval_id: str
    step_id: str
    risk_tier: str
    authority_required: tuple[str, ...]
    required: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class TerminalCondition:
    """Plan, goal, or subgoal closure condition."""

    terminal_condition_id: str
    scope: str
    ref_id: str
    condition: str


@dataclass(frozen=True, slots=True)
class PlanDAG:
    """Compiled DAG over governed plan steps."""

    plan_id: str
    goal_id: str
    step_ids: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    state_hash: str
    registry_hash: str


@dataclass(frozen=True, slots=True)
class GovernedPlanStep:
    """One executable or reviewable step with full governance obligations."""

    step_id: str
    subgoal_id: str
    capability_id: str
    params: dict[str, Any]
    depends_on: tuple[str, ...]
    preconditions: tuple[Precondition, ...]
    postconditions: tuple[Postcondition, ...]
    required_evidence: tuple[RequiredEvidence, ...]
    rollback: RollbackStep
    approval: ApprovalRequirement
    side_effects_bounded: bool


@dataclass(frozen=True, slots=True)
class GoalPlanCertificate:
    """Deterministic certificate for one compiled governed goal plan."""

    certificate_id: str
    goal_id: str
    plan_id: str
    tenant_id: str
    identity_id: str
    status: str
    risk_tier: str
    step_count: int
    state_hash: str
    registry_hash: str
    certificate_hash: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class CompiledGoalPlan:
    """Full compiled goal plan returned by the goal compiler."""

    goal: Goal
    subgoals: tuple[SubGoal, ...]
    plan_dag: PlanDAG
    steps: tuple[GovernedPlanStep, ...]
    terminal_conditions: tuple[TerminalCondition, ...]
    certificate: GoalPlanCertificate
    capability_plan: CapabilityPlan | None = None
    goal_normal_form: GoalNormalForm | None = None
    world_facts: tuple[WorldFact, ...] = ()
    gap_theorem: GapTheorem | None = None
    operator_contracts: tuple[OperatorContractProjection, ...] = ()
    causal_chain_graph: CausalChainGraphPlus | None = None
    verification_bundle: GoalCompilerVerificationBundle | None = None
    compile_receipt: CompileReceipt | None = None
    judgment: str = ""


@dataclass(frozen=True, slots=True)
class _R2CompileArtifacts:
    """Internal bundle for deterministic USCCGC-R2 projections."""

    goal_normal_form: GoalNormalForm
    world_facts: tuple[WorldFact, ...]
    gap_theorem: GapTheorem
    operator_contracts: tuple[OperatorContractProjection, ...]
    causal_chain_graph: CausalChainGraphPlus
    verification_bundle: GoalCompilerVerificationBundle
    compile_receipt: CompileReceipt
    judgment: str


class GoalCompiler:
    """Compile user intent into a governed plan and certificate."""

    def __init__(
        self,
        *,
        plan_builder: CapabilityPlanBuilder | None = None,
        capability_passport_loader: Callable[[str], CapabilityPassport] | None = None,
    ) -> None:
        self._capability_passport_loader = capability_passport_loader or capability_passport_for
        self._plan_builder = plan_builder or CapabilityPlanBuilder(
            capability_passport_loader=self._capability_passport_loader
        )

    def compile(
        self,
        *,
        message: str,
        tenant_id: str,
        identity_id: str,
        world_state: WorldState | None = None,
    ) -> CompiledGoalPlan:
        """Compile a user message into a governed goal plan."""
        state_hash = world_state.state_hash if world_state else "world-state:not-bound"
        capability_plan = self._plan_builder.build(
            message=message,
            tenant_id=tenant_id,
            identity_id=identity_id,
        )
        if capability_plan is None:
            goal_id = _stable_goal_id(tenant_id=tenant_id, identity_id=identity_id, objective=message)
            blocked_goal = Goal(
                goal_id=goal_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                objective=message,
                risk_tier="low",
                success_criteria=("typed_capability_plan_exists",),
                status="blocked",
                metadata={"compiler": "goal_compiler", "blocked_reason": "no_capability_plan"},
            )
            plan_dag = PlanDAG(
                plan_id=f"plan-blocked-{canonical_hash({'goal_id': goal_id})[:16]}",
                goal_id=goal_id,
                step_ids=(),
                edges=(),
                state_hash=state_hash,
                registry_hash="registry:not-bound",
            )
            certificate = _certificate(
                goal=blocked_goal,
                plan_dag=plan_dag,
                steps=(),
                status="blocked",
                reason="no_capability_plan",
            )
            terminal_conditions = (
                TerminalCondition(
                    terminal_condition_id=f"terminal-{goal_id}",
                    scope="goal",
                    ref_id=goal_id,
                    condition="typed_capability_plan_required",
                ),
            )
            r2_artifacts = _build_r2_artifacts(
                raw_goal=message,
                goal=blocked_goal,
                plan_dag=plan_dag,
                steps=(),
                terminal_conditions=terminal_conditions,
                capability_plan=None,
                world_state=world_state,
                certificate=certificate,
                capability_passport_loader=self._capability_passport_loader,
            )
            return CompiledGoalPlan(
                goal=blocked_goal,
                subgoals=(),
                plan_dag=plan_dag,
                steps=(),
                terminal_conditions=terminal_conditions,
                certificate=certificate,
                capability_plan=None,
                goal_normal_form=r2_artifacts.goal_normal_form,
                world_facts=r2_artifacts.world_facts,
                gap_theorem=r2_artifacts.gap_theorem,
                operator_contracts=r2_artifacts.operator_contracts,
                causal_chain_graph=r2_artifacts.causal_chain_graph,
                verification_bundle=r2_artifacts.verification_bundle,
                compile_receipt=r2_artifacts.compile_receipt,
                judgment=r2_artifacts.judgment,
            )

        registry_hash = _registry_hash(capability_plan.steps, self._capability_passport_loader)
        goal = Goal(
            goal_id=_stable_goal_id(
                tenant_id=tenant_id,
                identity_id=identity_id,
                objective=message,
            ),
            tenant_id=tenant_id,
            identity_id=identity_id,
            objective=message,
            risk_tier=capability_plan.risk_tier,
            success_criteria=tuple(
                f"terminal_certificate:{step.step_id}" for step in capability_plan.steps
            ),
            status="compiled",
            metadata={
                "compiler": "goal_compiler",
                "capability_plan_id": capability_plan.plan_id,
            },
        )
        subgoals: list[SubGoal] = []
        governed_steps: list[GovernedPlanStep] = []
        terminal_conditions: list[TerminalCondition] = []
        for step in capability_plan.steps:
            passport = self._capability_passport_loader(step.capability_id)
            subgoal_id = f"subgoal-{goal.goal_id}-{step.step_id}"
            subgoals.append(
                SubGoal(
                    subgoal_id=subgoal_id,
                    goal_id=goal.goal_id,
                    step_id=step.step_id,
                    objective=f"Execute {step.capability_id}",
                    owner_id=identity_id,
                    depends_on=tuple(step.depends_on),
                    terminal_condition=f"terminal_certificate:{step.step_id}",
                )
            )
            terminal_conditions.append(
                TerminalCondition(
                    terminal_condition_id=f"terminal-{step.step_id}",
                    scope="step",
                    ref_id=step.step_id,
                    condition="terminal_certificate_present",
                )
            )
            governed_steps.append(
                GovernedPlanStep(
                    step_id=step.step_id,
                    subgoal_id=subgoal_id,
                    capability_id=step.capability_id,
                    params=dict(step.params),
                    depends_on=tuple(step.depends_on),
                    preconditions=_preconditions(step.step_id, passport, state_hash),
                    postconditions=_postconditions(step.step_id, passport),
                    required_evidence=_required_evidence(step.step_id, passport),
                    rollback=_rollback_step(step.step_id, passport),
                    approval=_approval_requirement(step.step_id, passport),
                    side_effects_bounded=_side_effects_bounded(passport),
                )
            )
        terminal_conditions.append(
            TerminalCondition(
                terminal_condition_id=f"terminal-{goal.goal_id}",
                scope="goal",
                ref_id=goal.goal_id,
                condition="all_step_terminal_certificates_present",
            )
        )
        plan_dag = PlanDAG(
            plan_id=capability_plan.plan_id,
            goal_id=goal.goal_id,
            step_ids=tuple(step.step_id for step in capability_plan.steps),
            edges=tuple(
                (dependency, step.step_id)
                for step in capability_plan.steps
                for dependency in step.depends_on
            ),
            state_hash=state_hash,
            registry_hash=registry_hash,
        )
        status = "compiled" if all(step.side_effects_bounded for step in governed_steps) else "requires_review"
        certificate = _certificate(
            goal=goal,
            plan_dag=plan_dag,
            steps=tuple(governed_steps),
            status=status,
            reason="" if status == "compiled" else "unbounded_side_effects",
        )
        r2_artifacts = _build_r2_artifacts(
            raw_goal=message,
            goal=goal,
            plan_dag=plan_dag,
            steps=tuple(governed_steps),
            terminal_conditions=tuple(terminal_conditions),
            capability_plan=capability_plan,
            world_state=world_state,
            certificate=certificate,
            capability_passport_loader=self._capability_passport_loader,
        )
        return CompiledGoalPlan(
            goal=goal,
            subgoals=tuple(subgoals),
            plan_dag=plan_dag,
            steps=tuple(governed_steps),
            terminal_conditions=tuple(terminal_conditions),
            certificate=certificate,
            capability_plan=capability_plan,
            goal_normal_form=r2_artifacts.goal_normal_form,
            world_facts=r2_artifacts.world_facts,
            gap_theorem=r2_artifacts.gap_theorem,
            operator_contracts=r2_artifacts.operator_contracts,
            causal_chain_graph=r2_artifacts.causal_chain_graph,
            verification_bundle=r2_artifacts.verification_bundle,
            compile_receipt=r2_artifacts.compile_receipt,
            judgment=r2_artifacts.judgment,
        )


def _stable_goal_id(*, tenant_id: str, identity_id: str, objective: str) -> str:
    return f"goal-{canonical_hash({'tenant_id': tenant_id, 'identity_id': identity_id, 'objective': objective})[:16]}"


def _registry_hash(
    steps: tuple[Any, ...],
    capability_passport_loader: Callable[[str], CapabilityPassport],
) -> str:
    passports = []
    for step in steps:
        passport = capability_passport_loader(step.capability_id)
        passports.append({
            "capability": passport.capability,
            "version": passport.version,
            "risk_tier": passport.risk_tier,
            "requires": tuple(passport.requires),
            "authority_required": tuple(passport.authority_required),
            "evidence_required": tuple(passport.evidence_required),
        })
    return f"registry-{canonical_hash({'passports': passports})[:16]}"


def _preconditions(step_id: str, passport: CapabilityPassport, state_hash: str) -> tuple[Precondition, ...]:
    preconditions = [
        Precondition(
            precondition_id=f"pre-{step_id}-tenant-bound",
            step_id=step_id,
            condition_type="tenant_bound",
            required_ref="tenant_id",
            satisfied="tenant_bound" in passport.requires or bool(passport.capability),
            reason="capability_passport_bound",
        ),
        Precondition(
            precondition_id=f"pre-{step_id}-world-state",
            step_id=step_id,
            condition_type="world_state_bound",
            required_ref=state_hash,
            satisfied=state_hash != "world-state:not-bound",
            reason="world_state_projection_required",
        ),
    ]
    for requirement in passport.requires:
        preconditions.append(
            Precondition(
                precondition_id=f"pre-{step_id}-{_safe_id(requirement)}",
                step_id=step_id,
                condition_type="capability_requirement",
                required_ref=requirement,
                satisfied=not requirement.startswith("approval:"),
                reason="approval_requirement_projected" if requirement.startswith("approval:") else "passport_requirement",
            )
        )
    return tuple(preconditions)


def _postconditions(step_id: str, passport: CapabilityPassport) -> tuple[Postcondition, ...]:
    conditions = [
        Postcondition(
            postcondition_id=f"post-{step_id}-terminal-certificate",
            step_id=step_id,
            condition_type="terminal_certificate",
            expected_ref=f"terminal_certificate:{step_id}",
        )
    ]
    for effect in passport.declared_effects:
        conditions.append(
            Postcondition(
                postcondition_id=f"post-{step_id}-{_safe_id(effect)}",
                step_id=step_id,
                condition_type="declared_effect",
                expected_ref=effect,
            )
        )
    return tuple(conditions)


def _required_evidence(step_id: str, passport: CapabilityPassport) -> tuple[RequiredEvidence, ...]:
    evidence_items = passport.evidence_required or passport.proof_required_fields
    return tuple(
        RequiredEvidence(
            evidence_id=f"evidence-{step_id}-{_safe_id(evidence)}",
            step_id=step_id,
            evidence_type=evidence,
            timing="after_step",
            source_ref=passport.capability,
        )
        for evidence in evidence_items
    )


def _rollback_step(step_id: str, passport: CapabilityPassport) -> RollbackStep:
    if passport.rollback_capability:
        return RollbackStep(
            rollback_id=f"rollback-{step_id}",
            step_id=step_id,
            action_type="rollback_capability",
            capability_id=passport.rollback_capability,
            required=passport.mutates_world or passport.risk_tier == "high",
            reason="passport_rollback_capability",
        )
    if passport.compensation_capability:
        return RollbackStep(
            rollback_id=f"rollback-{step_id}",
            step_id=step_id,
            action_type="compensation_capability",
            capability_id=passport.compensation_capability,
            required=passport.mutates_world or passport.risk_tier == "high",
            reason="passport_compensation_capability",
        )
    if passport.rollback_type in {"review", "manual_review", "operator_review"}:
        return RollbackStep(
            rollback_id=f"rollback-{step_id}",
            step_id=step_id,
            action_type="review",
            required=passport.mutates_world or passport.risk_tier == "high",
            reason="review_required_for_unreversible_effect",
        )
    return RollbackStep(
        rollback_id=f"rollback-{step_id}",
        step_id=step_id,
        action_type=passport.rollback_type or "none",
        required=passport.mutates_world or passport.risk_tier == "high",
        reason="passport_rollback_type",
    )


def _approval_requirement(step_id: str, passport: CapabilityPassport) -> ApprovalRequirement:
    required = passport.risk_tier in {"medium", "high"} or any(
        requirement.startswith("approval:") for requirement in passport.requires
    )
    return ApprovalRequirement(
        approval_id=f"approval-{step_id}",
        step_id=step_id,
        risk_tier=passport.risk_tier,
        authority_required=tuple(passport.authority_required),
        required=required,
        reason="risk_or_passport_requirement" if required else "not_required",
    )


def _side_effects_bounded(passport: CapabilityPassport) -> bool:
    if not passport.mutates_world and passport.risk_tier != "high":
        return True
    return bool(
        passport.rollback_capability
        or passport.compensation_capability
        or passport.rollback_type in {"review", "manual_review", "operator_review"}
    )


def _build_r2_artifacts(
    *,
    raw_goal: str,
    goal: Goal,
    plan_dag: PlanDAG,
    steps: tuple[GovernedPlanStep, ...],
    terminal_conditions: tuple[TerminalCondition, ...],
    capability_plan: CapabilityPlan | None,
    world_state: WorldState | None,
    certificate: GoalPlanCertificate,
    capability_passport_loader: Callable[[str], CapabilityPassport],
) -> _R2CompileArtifacts:
    operator_contracts = _operator_contract_projections(
        steps=steps,
        capability_passport_loader=capability_passport_loader,
    )
    goal_normal_form = _goal_normal_form(
        raw_goal=raw_goal,
        goal=goal,
        steps=steps,
        operator_contracts=operator_contracts,
        capability_plan=capability_plan,
    )
    world_facts = _world_facts(world_state)
    gap_theorem = _gap_theorem(
        certificate=certificate,
        steps=steps,
        capability_plan=capability_plan,
        world_state=world_state,
        operator_contracts=operator_contracts,
    )
    causal_chain_graph = _causal_chain_graph(
        goal=goal,
        plan_dag=plan_dag,
        steps=steps,
        terminal_conditions=terminal_conditions,
        operator_contracts=operator_contracts,
        gap_theorem=gap_theorem,
        certificate=certificate,
    )
    verification_bundle = _r2_verification_bundle(
        certificate=certificate,
        world_state=world_state,
        gap_theorem=gap_theorem,
        operator_contracts=operator_contracts,
        causal_chain_graph=causal_chain_graph,
    )
    judgment = _r2_judgment(
        certificate=certificate,
        gap_theorem=gap_theorem,
        verification_bundle=verification_bundle,
    )
    compile_receipt = _compile_receipt(
        goal=goal,
        plan_dag=plan_dag,
        certificate=certificate,
        goal_normal_form=goal_normal_form,
        gap_theorem=gap_theorem,
        causal_chain_graph=causal_chain_graph,
        verification_bundle=verification_bundle,
        judgment=judgment,
    )
    return _R2CompileArtifacts(
        goal_normal_form=goal_normal_form,
        world_facts=world_facts,
        gap_theorem=gap_theorem,
        operator_contracts=operator_contracts,
        causal_chain_graph=causal_chain_graph,
        verification_bundle=verification_bundle,
        compile_receipt=compile_receipt,
        judgment=judgment,
    )


def _goal_normal_form(
    *,
    raw_goal: str,
    goal: Goal,
    steps: tuple[GovernedPlanStep, ...],
    operator_contracts: tuple[OperatorContractProjection, ...],
    capability_plan: CapabilityPlan | None,
) -> GoalNormalForm:
    effects = _dedupe(
        effect
        for contract in operator_contracts
        for effect in contract.effects
    )
    target_state = effects or tuple(goal.success_criteria)
    evidence_required = _dedupe(
        evidence
        for contract in operator_contracts
        for evidence in contract.evidence_required
    )
    if not evidence_required:
        evidence_required = ("typed_capability_plan",) if capability_plan is None else ("terminal_certificate",)
    approval_boundaries = _dedupe(
        f"authority_required:{authority}"
        for step in steps
        if step.approval.required
        for authority in (step.approval.authority_required or ("operator",))
    )
    boundaries = (
        "planning_simulation_only",
        "no_execution_dispatch_or_promotion",
        "no_irreversible_external_action_without_explicit_approval",
        *approval_boundaries,
    )
    return GoalNormalForm(
        actor_id=goal.identity_id,
        target_state=tuple(target_state),
        constraints=(
            "do_not_violate_laws",
            "do_not_exceed_permission",
            "registered_operator_required",
            "verified_effect_required",
            "produce_receipt",
        ),
        success_metrics=(
            *goal.success_criteria,
            "causal_chain_graph_plus_built",
            "compile_receipt_emitted",
        ),
        failure_metrics=(
            "constraint_violation",
            "missing_registered_operator",
            "missing_verifier",
            "unbounded_side_effect",
            "missing_receipt",
        ),
        boundaries=boundaries,
        reversibility_required=goal.risk_tier in {"medium", "high"} or any(
            step.rollback.required for step in steps
        ),
        required_evidence=tuple(evidence_required),
        temporal_conditions=("revalidate_fresh_state_before_execution",),
        quality_thresholds={
            "minimum_operator_confidence": 0.8,
            "minimum_edge_confidence": 0.8,
        },
    )


def _world_facts(world_state: WorldState | None) -> tuple[WorldFact, ...]:
    if world_state is None:
        return (
            WorldFact(
                fact_id="fact-world-state-projection",
                value="not_bound",
                source="goal_compiler",
                status="unknown",
                confidence=0.0,
                permission_ref="planning",
            ),
        )
    stale = _world_state_requires_refresh(world_state)
    observed_status = "stale" if stale else "observed"
    observed_confidence = 0.4 if stale else 1.0
    contradiction_status = "contradicted" if world_state.open_contradiction_count else "observed"
    contradiction_confidence = 1.0 if world_state.open_contradiction_count else 0.0
    return (
        WorldFact(
            fact_id="fact-world-state-hash",
            value=world_state.state_hash,
            source="world_state_projection",
            status=observed_status,
            confidence=observed_confidence,
            freshness_ref=world_state.projected_at,
            permission_ref="planning",
        ),
        WorldFact(
            fact_id="fact-world-state-tenant",
            value=world_state.tenant_id,
            source="world_state_projection",
            status=observed_status,
            confidence=observed_confidence,
            freshness_ref=world_state.projected_at,
            permission_ref="planning",
        ),
        WorldFact(
            fact_id="fact-world-open-contradictions",
            value=str(world_state.open_contradiction_count),
            source="world_state_projection",
            status=contradiction_status,
            confidence=contradiction_confidence,
            freshness_ref=world_state.projected_at,
            permission_ref="planning",
        ),
    )


def _world_state_requires_refresh(world_state: WorldState | None) -> bool:
    if world_state is None:
        return False
    freshness_status = str(world_state.metadata.get("freshness_status", "")).strip().lower()
    if freshness_status in {"stale", "expired", "requires_refresh"}:
        return True
    return world_state.metadata.get("requires_refresh") is True


def _operator_contract_projections(
    *,
    steps: tuple[GovernedPlanStep, ...],
    capability_passport_loader: Callable[[str], CapabilityPassport],
) -> tuple[OperatorContractProjection, ...]:
    projections: list[OperatorContractProjection] = []
    for step in steps:
        passport = capability_passport_loader(step.capability_id)
        evidence_required = passport.evidence_required or passport.proof_required_fields
        effects = passport.declared_effects or tuple(
            postcondition.expected_ref for postcondition in step.postconditions
        )
        side_effects = _operator_side_effects(passport)
        projections.append(
            OperatorContractProjection(
                operator_id=step.capability_id,
                version=passport.version,
                domain=_domain_for(step.capability_id),
                preconditions=tuple(
                    precondition.required_ref for precondition in step.preconditions
                ),
                effects=tuple(effects),
                side_effects=side_effects,
                permissions=_dedupe((*passport.requires, *passport.authority_required)),
                risk_tier=_r2_risk_tier(passport),
                verifier=_operator_verifier(passport, step),
                rollback_type=passport.rollback_type or step.rollback.action_type or "none",
                failure_modes=_operator_failure_modes(passport, step),
                evidence_required=tuple(evidence_required),
                authority_required=tuple(passport.authority_required),
            )
        )
    return tuple(projections)


def _gap_theorem(
    *,
    certificate: GoalPlanCertificate,
    steps: tuple[GovernedPlanStep, ...],
    capability_plan: CapabilityPlan | None,
    world_state: WorldState | None,
    operator_contracts: tuple[OperatorContractProjection, ...],
) -> GapTheorem:
    missing_facts = () if world_state is not None else ("world_state_projection",)
    if _world_state_requires_refresh(world_state):
        missing_facts = (*missing_facts, "fresh_world_state_projection")
    missing_tools = () if capability_plan is not None else ("typed_capability_plan",)
    missing_permissions = _dedupe(
        f"approval:{authority}"
        for step in steps
        if step.approval.required
        for authority in (step.approval.authority_required or ("operator",))
    )
    missing_evidence = _dedupe(
        evidence
        for contract in operator_contracts
        for evidence in contract.evidence_required
    )
    missing_verifiers = tuple(
        contract.operator_id for contract in operator_contracts if not contract.verifier
    )
    conflicts: list[str] = []
    if certificate.status == "blocked":
        conflicts.append(certificate.reason or "plan_blocked")
    if certificate.status == "requires_review":
        conflicts.append(certificate.reason or "requires_review")
    if world_state is not None and world_state.open_contradiction_count > 0:
        conflicts.append("open_world_contradictions")
    for step in steps:
        if not step.side_effects_bounded:
            conflicts.append(f"unbounded_side_effect:{step.step_id}")
    return GapTheorem(
        missing_facts=tuple(missing_facts),
        missing_permissions=tuple(missing_permissions),
        missing_tools=tuple(missing_tools),
        missing_evidence=tuple(missing_evidence),
        missing_verifiers=tuple(missing_verifiers),
        conflicts=tuple(conflicts),
    )


def _causal_chain_graph(
    *,
    goal: Goal,
    plan_dag: PlanDAG,
    steps: tuple[GovernedPlanStep, ...],
    terminal_conditions: tuple[TerminalCondition, ...],
    operator_contracts: tuple[OperatorContractProjection, ...],
    gap_theorem: GapTheorem,
    certificate: GoalPlanCertificate,
) -> CausalChainGraphPlus:
    nodes: list[CausalGraphNode] = [
        CausalGraphNode(
            node_id=f"goal:{goal.goal_id}",
            node_type="StateNode",
            ref=goal.goal_id,
            status=goal.status,
            risk_tier=goal.risk_tier,
            proof_state="Pass" if certificate.status != "blocked" else "Fail",
        )
    ]
    edges: list[CausalGraphEdge] = []
    contract_by_operator = {contract.operator_id: contract for contract in operator_contracts}

    if not steps:
        nodes.append(
            CausalGraphNode(
                node_id="assumption:typed-capability-plan",
                node_type="AssumptionNode",
                ref="typed_capability_plan",
                status="missing",
                proof_state="Fail",
            )
        )
        edges.append(
            CausalGraphEdge(
                source="assumption:typed-capability-plan",
                target=f"goal:{goal.goal_id}",
                relation="BLOCKS",
                confidence=1.0,
                proof_type="capability_plan_absent",
            )
        )

    for terminal_condition in terminal_conditions:
        terminal_node_id = f"terminal:{terminal_condition.terminal_condition_id}"
        nodes.append(
            CausalGraphNode(
                node_id=terminal_node_id,
                node_type="VerifierNode",
                ref=terminal_condition.condition,
                status="required",
                proof_state="Unknown",
            )
        )
        edges.append(
            CausalGraphEdge(
                source=terminal_node_id,
                target=f"goal:{goal.goal_id}",
                relation="PROVES",
                confidence=0.8,
                proof_type="terminal_condition",
            )
        )

    for step in steps:
        action_node_id = f"action:{step.step_id}"
        contract = contract_by_operator.get(step.capability_id)
        risk_tier = contract.risk_tier if contract is not None else step.approval.risk_tier
        nodes.append(
            CausalGraphNode(
                node_id=action_node_id,
                node_type="ActionNode",
                ref=step.capability_id,
                status="planned",
                risk_tier=risk_tier,
                proof_state="Pass" if contract is not None else "Fail",
            )
        )
        for dependency in step.depends_on:
            edges.append(
                CausalGraphEdge(
                    source=f"action:{dependency}",
                    target=action_node_id,
                    relation="ENABLES",
                    confidence=0.8,
                    proof_type="capability_plan_dag",
                )
            )
        if contract is not None:
            for effect in contract.effects:
                effect_node_id = f"state:{_safe_id(effect)}"
                nodes.append(
                    CausalGraphNode(
                        node_id=effect_node_id,
                        node_type="StateNode",
                        ref=effect,
                        status="target",
                        risk_tier=risk_tier,
                        proof_state="Unknown",
                    )
                )
                edges.append(
                    CausalGraphEdge(
                        source=action_node_id,
                        target=effect_node_id,
                        relation="CAUSES",
                        confidence=0.8,
                        proof_type=contract.proof_type,
                    )
                )
                edges.append(
                    CausalGraphEdge(
                        source=effect_node_id,
                        target=f"goal:{goal.goal_id}",
                        relation="REFINES",
                        confidence=0.8,
                        proof_type="goal_normal_form_target",
                    )
                )
        if step.approval.required:
            gate_node_id = f"risk-gate:{step.step_id}"
            nodes.append(
                CausalGraphNode(
                    node_id=gate_node_id,
                    node_type="RiskGateNode",
                    ref=step.approval.approval_id,
                    status="required",
                    risk_tier=risk_tier,
                    proof_state="Unknown",
                )
            )
            edges.append(
                CausalGraphEdge(
                    source=action_node_id,
                    target=gate_node_id,
                    relation="REQUIRES_PERMISSION",
                    confidence=1.0,
                    proof_type="approval_requirement",
                )
            )
            edges.append(
                CausalGraphEdge(
                    source=gate_node_id,
                    target=action_node_id,
                    relation="MITIGATES",
                    confidence=1.0,
                    proof_type="risk_gate",
                )
            )
        verifier_node_id = f"verifier:{step.step_id}"
        receipt_node_id = f"receipt:{step.step_id}"
        nodes.append(
            CausalGraphNode(
                node_id=verifier_node_id,
                node_type="VerifierNode",
                ref=",".join(evidence.evidence_type for evidence in step.required_evidence)
                or "terminal_certificate",
                status="required",
                risk_tier=risk_tier,
                proof_state="Unknown",
            )
        )
        nodes.append(
            CausalGraphNode(
                node_id=receipt_node_id,
                node_type="ReceiptNode",
                ref=f"terminal_certificate:{step.step_id}",
                status="required",
                risk_tier=risk_tier,
                proof_state="Unknown",
            )
        )
        edges.append(
            CausalGraphEdge(
                source=verifier_node_id,
                target=action_node_id,
                relation="PROVES",
                confidence=0.8,
                proof_type="evidence_obligation",
            )
        )
        edges.append(
            CausalGraphEdge(
                source=action_node_id,
                target=receipt_node_id,
                relation="PROVES",
                confidence=0.8,
                proof_type="receipt_obligation",
            )
        )

    proof_state = "Fail" if certificate.status == "blocked" else (
        "Unknown" if (
            gap_theorem.conflicts
            or gap_theorem.missing_permissions
            or gap_theorem.missing_facts
        ) else "Pass"
    )
    graph_payload = {
        "goal_id": goal.goal_id,
        "plan_id": plan_dag.plan_id,
        "nodes": [asdict(node) for node in nodes],
        "edges": [asdict(edge) for edge in edges],
        "proof_state": proof_state,
    }
    return CausalChainGraphPlus(
        graph_id=f"ccg-plus-{canonical_hash(graph_payload)[:16]}",
        nodes=tuple(nodes),
        edges=tuple(edges),
        risk_tier=goal.risk_tier,
        proof_state=proof_state,
    )


def _r2_verification_bundle(
    *,
    certificate: GoalPlanCertificate,
    world_state: WorldState | None,
    gap_theorem: GapTheorem,
    operator_contracts: tuple[OperatorContractProjection, ...],
    causal_chain_graph: CausalChainGraphPlus,
) -> GoalCompilerVerificationBundle:
    checks = [
        "goal_normal_form_present",
        "world_state_reconstructed",
        "gap_theorem_computed",
        "causal_chain_graph_plus_built",
        "compile_receipt_required",
    ]
    checks.extend(f"registered_operator:{contract.operator_id}" for contract in operator_contracts)
    failures: list[str] = []
    unresolved: list[str] = []
    if certificate.status == "blocked":
        failures.append(certificate.reason or "plan_blocked")
    if certificate.status == "requires_review":
        failures.append(certificate.reason or "requires_review")
    if world_state is None:
        unresolved.append("world_state_projection_unknown")
    if _world_state_requires_refresh(world_state):
        unresolved.append("world_state_projection_stale")
    unresolved.extend(f"permission_pending:{permission}" for permission in gap_theorem.missing_permissions)
    unresolved.extend(f"post_step_evidence_pending:{evidence}" for evidence in gap_theorem.missing_evidence)
    unresolved.extend(f"conflict_pending:{conflict}" for conflict in gap_theorem.conflicts if conflict not in failures)
    if not causal_chain_graph.nodes:
        failures.append("causal_chain_graph_empty")
    return GoalCompilerVerificationBundle(
        passed=not failures,
        checks=tuple(checks),
        failures=tuple(failures),
        unresolved=tuple(_dedupe(unresolved)),
    )


def _r2_judgment(
    *,
    certificate: GoalPlanCertificate,
    gap_theorem: GapTheorem,
    verification_bundle: GoalCompilerVerificationBundle,
) -> str:
    if verification_bundle.failures:
        if certificate.reason == "no_capability_plan":
            return "blocked"
        if certificate.status == "requires_review":
            return "unsafe"
        return "unverifiable"
    if gap_theorem.conflicts:
        return "needs_more_evidence"
    if gap_theorem.missing_permissions:
        return "needs_permission"
    if gap_theorem.missing_facts:
        return "needs_more_evidence"
    if verification_bundle.unresolved:
        return "executable_with_assumptions"
    return "executable"


def _compile_receipt(
    *,
    goal: Goal,
    plan_dag: PlanDAG,
    certificate: GoalPlanCertificate,
    goal_normal_form: GoalNormalForm,
    gap_theorem: GapTheorem,
    causal_chain_graph: CausalChainGraphPlus,
    verification_bundle: GoalCompilerVerificationBundle,
    judgment: str,
) -> CompileReceipt:
    constructive_deltas = (
        "goal_normal_form_created",
        "world_state_reconstructed",
        "gap_theorem_computed",
        "operator_registry_bound",
        "causal_chain_graph_plus_built",
        "verification_bundle_emitted",
    )
    fracture_deltas = tuple(
        _dedupe(
            (
                *gap_theorem.missing_facts,
                *gap_theorem.missing_permissions,
                *gap_theorem.missing_tools,
                *gap_theorem.missing_evidence,
                *gap_theorem.missing_verifiers,
                *gap_theorem.conflicts,
                *verification_bundle.failures,
                *verification_bundle.unresolved,
            )
        )
    )
    assumptions = tuple(
        item
        for item in (
            "world_state_projection_absent" if gap_theorem.missing_facts else "",
            "post_step_evidence_pending_until_execution" if gap_theorem.missing_evidence else "",
        )
        if item
    )
    payload = {
        "goal_id": goal.goal_id,
        "plan_id": plan_dag.plan_id,
        "certificate_id": certificate.certificate_id,
        "judgment": judgment,
        "gnf": asdict(goal_normal_form),
        "gap": asdict(gap_theorem),
        "graph_id": causal_chain_graph.graph_id,
        "verification": asdict(verification_bundle),
        "constructive_deltas": constructive_deltas,
        "fracture_deltas": fracture_deltas,
        "assumptions": assumptions,
    }
    receipt_hash = canonical_hash(payload)
    return CompileReceipt(
        receipt_id=f"goal-compile-receipt-{receipt_hash[:16]}",
        goal_id=goal.goal_id,
        judgment=judgment,
        constructive_deltas=constructive_deltas,
        fracture_deltas=fracture_deltas,
        blocked_reasons=tuple(verification_bundle.failures),
        assumptions=assumptions,
        receipt_hash=receipt_hash,
    )


def _operator_side_effects(passport: CapabilityPassport) -> tuple[str, ...]:
    side_effects: list[str] = list(passport.forbidden_effects)
    if passport.external_system:
        side_effects.append(f"external_system:{passport.external_system}")
    if passport.mutates_world:
        side_effects.append("world_state_mutation")
    return tuple(_dedupe(side_effects))


def _operator_verifier(passport: CapabilityPassport, step: GovernedPlanStep) -> str:
    evidence = passport.evidence_required or passport.proof_required_fields
    if evidence:
        return f"evidence:{','.join(evidence)}"
    if step.postconditions:
        return "postcondition_verifier"
    return ""


def _operator_failure_modes(
    passport: CapabilityPassport,
    step: GovernedPlanStep,
) -> tuple[str, ...]:
    failure_modes = ["precondition_failure"]
    if passport.authority_required or step.approval.required:
        failure_modes.append("permission_missing")
    if passport.external_system:
        failure_modes.append("external_effect_drift")
    if passport.mutates_world and not _side_effects_bounded(passport):
        failure_modes.append("unbounded_side_effect")
    if not (passport.evidence_required or passport.proof_required_fields or step.postconditions):
        failure_modes.append("missing_verifier")
    return tuple(_dedupe(failure_modes))


def _r2_risk_tier(passport: CapabilityPassport) -> str:
    if passport.capability.startswith(("financial.send_payment", "physical.")):
        return "tier_5_high_stakes"
    if passport.risk_tier == "critical":
        return "tier_5_high_stakes"
    if passport.risk_tier == "high" and (passport.external_system or passport.mutates_world):
        return "tier_4_external_irreversible"
    if passport.risk_tier == "medium" and passport.external_system:
        return "tier_3_external_draft"
    if passport.mutates_world:
        return "tier_2_local_reversible_write"
    if passport.external_system:
        return "tier_1_read_only"
    return "tier_0_reasoning"


def _domain_for(capability_id: str) -> str:
    if "." not in capability_id:
        return "gateway"
    return capability_id.split(".", 1)[0]


def _dedupe(values: Any) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in items:
            items.append(text)
    return tuple(items)


def _certificate(
    *,
    goal: Goal,
    plan_dag: PlanDAG,
    steps: tuple[GovernedPlanStep, ...],
    status: str,
    reason: str,
) -> GoalPlanCertificate:
    payload = {
        "goal": asdict(goal),
        "plan_dag": asdict(plan_dag),
        "steps": [asdict(step) for step in steps],
        "status": status,
        "reason": reason,
    }
    certificate_hash = canonical_hash(payload)
    return GoalPlanCertificate(
        certificate_id=f"goal-plan-cert-{certificate_hash[:16]}",
        goal_id=goal.goal_id,
        plan_id=plan_dag.plan_id,
        tenant_id=goal.tenant_id,
        identity_id=goal.identity_id,
        status=status,
        risk_tier=goal.risk_tier,
        step_count=len(steps),
        state_hash=plan_dag.state_hash,
        registry_hash=plan_dag.registry_hash,
        certificate_hash=certificate_hash,
        reason=reason,
    )


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-").lower()
