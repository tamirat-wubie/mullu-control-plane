"""Gateway causal simulator.

Purpose: Dry-run compiled governed plans before approval or execution and
    produce a deterministic simulation receipt.
Governance scope: precondition checking, high-risk execution blocking,
    required-control projection, failure-mode projection, and compensation
    path verification.
Dependencies: gateway.goal_compiler and gateway.command_spine hashing.
Invariants:
  - Blocked or uncompiled plans never simulate as executable.
  - Failed preconditions block execution.
  - High-risk steps cannot execute directly before required controls are named.
  - Mutating or high-risk steps require a rollback, compensation, or review path.
  - The simulation receipt hash is derived from the complete simulation result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.goal_compiler import CompiledGoalPlan, GovernedPlanStep
from gateway.world_state import WorldState


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True, slots=True)
class SimulationStepResult:
    """Dry-run result for one governed plan step."""

    step_id: str
    capability_id: str
    risk: str
    would_execute: bool
    reason: str
    required_controls: tuple[str, ...] = ()
    failed_preconditions: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    compensation_path: str = ""
    evidence_required: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CausalSimulationReceipt:
    """Deterministic dry-run proof for one compiled goal plan."""

    simulation_id: str
    goal_id: str
    plan_id: str
    tenant_id: str
    action: str
    risk: str
    would_execute: bool
    reason: str
    required_controls: tuple[str, ...]
    failure_modes: tuple[str, ...]
    compensation_path: str
    step_results: tuple[SimulationStepResult, ...]
    plan_certificate_id: str
    state_hash: str
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class CausalSimulator:
    """Dry-run compiled plans without causing side effects."""

    def simulate(
        self,
        compiled_plan: CompiledGoalPlan,
        *,
        world_state: WorldState | None = None,
    ) -> CausalSimulationReceipt:
        """Simulate a compiled goal plan and return a receipt."""
        if compiled_plan.certificate.status == "blocked" or not compiled_plan.steps:
            return _receipt(
                goal_id=compiled_plan.goal.goal_id,
                plan_id=compiled_plan.plan_dag.plan_id,
                tenant_id=compiled_plan.goal.tenant_id,
                action=compiled_plan.goal.objective,
                risk=compiled_plan.goal.risk_tier,
                would_execute=False,
                reason=compiled_plan.certificate.reason or "plan_not_executable",
                required_controls=("typed_capability_plan",),
                failure_modes=("plan_compilation_blocked",),
                compensation_path="not_applicable",
                step_results=(),
                plan_certificate_id=compiled_plan.certificate.certificate_id,
                state_hash=compiled_plan.plan_dag.state_hash,
                metadata={"simulator": "causal_simulator"},
            )

        step_results = tuple(
            _simulate_step(step, world_state=world_state)
            for step in compiled_plan.steps
        )
        required_controls = _dedupe(
            control
            for result in step_results
            for control in result.required_controls
        )
        failure_modes = _dedupe(
            failure_mode
            for result in step_results
            for failure_mode in result.failure_modes
        )
        risk = _max_risk((compiled_plan.goal.risk_tier,) + tuple(result.risk for result in step_results))
        would_execute = all(result.would_execute for result in step_results)
        reason = "simulation_passed" if would_execute else _first_blocking_reason(step_results)
        compensation_path = _join_compensation_paths(step_results)
        if world_state and world_state.open_contradiction_count > 0:
            would_execute = False
            reason = "open_world_contradictions"
            required_controls = _dedupe((*required_controls, "resolve_world_contradictions"))
            failure_modes = _dedupe((*failure_modes, "world_state_contradiction"))
        return _receipt(
            goal_id=compiled_plan.goal.goal_id,
            plan_id=compiled_plan.plan_dag.plan_id,
            tenant_id=compiled_plan.goal.tenant_id,
            action=compiled_plan.goal.objective,
            risk=risk,
            would_execute=would_execute,
            reason=reason,
            required_controls=required_controls,
            failure_modes=failure_modes,
            compensation_path=compensation_path,
            step_results=step_results,
            plan_certificate_id=compiled_plan.certificate.certificate_id,
            state_hash=compiled_plan.plan_dag.state_hash,
            metadata={"simulator": "causal_simulator"},
        )


def _simulate_step(
    step: GovernedPlanStep,
    *,
    world_state: WorldState | None,
) -> SimulationStepResult:
    failed_preconditions = tuple(
        precondition.precondition_id
        for precondition in step.preconditions
        if not precondition.satisfied and not precondition.required_ref.startswith("approval:")
    )
    required_controls: list[str] = []
    failure_modes: list[str] = []
    if any(precondition.required_ref.startswith("approval:") for precondition in step.preconditions):
        required_controls.append(_approval_control(step))
    if step.approval.required:
        required_controls.append(_approval_control(step))
    if failed_preconditions:
        failure_modes.append("precondition_failure")
    if step.required_evidence:
        failure_modes.append("evidence_missing_until_execution")
    if step.approval.required:
        failure_modes.append("approval_pending")
    if not step.side_effects_bounded:
        required_controls.append("operator_review")
        failure_modes.append("unbounded_side_effect")
    if world_state and world_state.open_contradiction_count > 0:
        required_controls.append("resolve_world_contradictions")
        failure_modes.append("world_state_contradiction")

    risk = step.approval.risk_tier
    compensation_path = _step_compensation_path(step)
    if risk == "high" and compensation_path in {"", "none"}:
        required_controls.append("compensation_or_review_path")
        failure_modes.append("missing_compensation_path")

    would_execute = not failed_preconditions and not required_controls
    reason = "simulation_passed" if would_execute else _step_reason(
        failed_preconditions=failed_preconditions,
        required_controls=tuple(required_controls),
    )
    return SimulationStepResult(
        step_id=step.step_id,
        capability_id=step.capability_id,
        risk=risk,
        would_execute=would_execute,
        reason=reason,
        required_controls=_dedupe(required_controls),
        failed_preconditions=failed_preconditions,
        failure_modes=_dedupe(failure_modes),
        compensation_path=compensation_path,
        evidence_required=tuple(evidence.evidence_type for evidence in step.required_evidence),
    )


def _approval_control(step: GovernedPlanStep) -> str:
    if step.approval.authority_required:
        return f"{step.approval.authority_required[0]}_approval"
    if step.approval.risk_tier == "high":
        return "high_risk_approval"
    return "operator_approval"


def _step_compensation_path(step: GovernedPlanStep) -> str:
    if not step.rollback.required:
        return "none"
    if step.rollback.capability_id:
        return step.rollback.capability_id
    if step.rollback.action_type:
        return step.rollback.action_type
    return "none"


def _step_reason(
    *,
    failed_preconditions: tuple[str, ...],
    required_controls: tuple[str, ...],
) -> str:
    if failed_preconditions:
        return "preconditions_failed"
    if required_controls:
        return "required_controls_pending"
    return "simulation_blocked"


def _first_blocking_reason(step_results: tuple[SimulationStepResult, ...]) -> str:
    for result in step_results:
        if not result.would_execute:
            return result.reason
    return "simulation_blocked"


def _join_compensation_paths(step_results: tuple[SimulationStepResult, ...]) -> str:
    paths = _dedupe(
        result.compensation_path
        for result in step_results
        if result.compensation_path and result.compensation_path != "none"
    )
    return ",".join(paths) if paths else "none"


def _max_risk(risks: tuple[str, ...]) -> str:
    winner = "low"
    for risk in risks:
        if _RISK_ORDER.get(risk, 0) > _RISK_ORDER.get(winner, 0):
            winner = risk
    return winner


def _dedupe(values: Any) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in items:
            items.append(text)
    return tuple(items)


def _receipt(
    *,
    goal_id: str,
    plan_id: str,
    tenant_id: str,
    action: str,
    risk: str,
    would_execute: bool,
    reason: str,
    required_controls: tuple[str, ...],
    failure_modes: tuple[str, ...],
    compensation_path: str,
    step_results: tuple[SimulationStepResult, ...],
    plan_certificate_id: str,
    state_hash: str,
    metadata: dict[str, Any],
) -> CausalSimulationReceipt:
    receipt = CausalSimulationReceipt(
        simulation_id="pending",
        goal_id=goal_id,
        plan_id=plan_id,
        tenant_id=tenant_id,
        action=action,
        risk=risk,
        would_execute=would_execute,
        reason=reason,
        required_controls=required_controls,
        failure_modes=failure_modes,
        compensation_path=compensation_path,
        step_results=step_results,
        plan_certificate_id=plan_certificate_id,
        state_hash=state_hash,
        receipt_hash="",
        metadata=metadata,
    )
    payload = asdict(receipt)
    receipt_hash = canonical_hash(payload)
    return replace(
        receipt,
        simulation_id=f"sim-{receipt_hash[:16]}",
        receipt_hash=receipt_hash,
    )
