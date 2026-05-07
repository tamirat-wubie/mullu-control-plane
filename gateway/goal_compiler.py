"""Gateway goal compiler.

Purpose: Compile user intent into governed goals, subgoals, plan DAG steps,
    preconditions, postconditions, evidence obligations, rollback obligations,
    approval requirements, and a deterministic plan certificate.
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
            return CompiledGoalPlan(
                goal=blocked_goal,
                subgoals=(),
                plan_dag=plan_dag,
                steps=(),
                terminal_conditions=(
                    TerminalCondition(
                        terminal_condition_id=f"terminal-{goal_id}",
                        scope="goal",
                        ref_id=goal_id,
                        condition="typed_capability_plan_required",
                    ),
                ),
                certificate=certificate,
                capability_plan=None,
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
        return CompiledGoalPlan(
            goal=goal,
            subgoals=tuple(subgoals),
            plan_dag=plan_dag,
            steps=tuple(governed_steps),
            terminal_conditions=tuple(terminal_conditions),
            certificate=certificate,
            capability_plan=capability_plan,
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
