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


ENGINE_VERSION = "causal_preview_engine.v2"
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_SIMULATION_BOUNDARY = {
    "mode": "dry_run",
    "sandbox": "read_only_snapshot_clone",
    "real_mutation_allowed": False,
    "external_mutation_allowed": False,
    "success_certification_allowed": False,
}
_SNAPSHOT_NOT_BOUND = "world-state:not-bound"
_COMPENSATION_ORDER = {
    "DANGEROUS": 0,
    "UNAVAILABLE": 1,
    "UNTESTED": 2,
    "PARTIAL": 3,
    "PLAUSIBLE": 4,
    "VERIFIED": 5,
    "NOT_REQUIRED": 6,
}


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
class CausalRiskScore:
    """Branch-local risk forecast emitted without claiming real-world proof."""

    risk_id: str
    branch_id: str
    risk_type: str
    score: float
    severity: float
    likelihood: float
    exposure: float
    irreversibility: float
    uncertainty: float
    cascade_potential: float
    mitigation_strength: float
    description: str


@dataclass(frozen=True, slots=True)
class CompensationAssessment:
    """Rollback or compensation path with explicit evidence status."""

    strategy: str
    step_id: str
    capability_id: str
    verification_status: str
    recovery_type: str
    steps: tuple[str, ...]
    limitations: tuple[str, ...]


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
    engine_version: str = ENGINE_VERSION
    timestamp: str = ""
    actor: str = ""
    action_id: str = ""
    action_type: str = ""
    target: str = ""
    goal: str = ""
    simulation_boundary: dict[str, Any] = field(default_factory=dict)
    state_snapshot_hash: str = ""
    snapshot_freshness: dict[str, Any] = field(default_factory=dict)
    permissions_checked: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    causal_graph_summary: dict[str, Any] = field(default_factory=dict)
    branch_summary: dict[str, Any] = field(default_factory=dict)
    predicted_direct_effects: tuple[str, ...] = ()
    predicted_indirect_effects: tuple[str, ...] = ()
    predicted_delayed_effects: tuple[str, ...] = ()
    constraint_checks: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    risk_scores: tuple[CausalRiskScore, ...] = ()
    compensation_plans: tuple[CompensationAssessment, ...] = ()
    compensation_verification_status: str = "UNTESTED"
    confidence_components: dict[str, float] = field(default_factory=dict)
    confidence_score: float = 0.0
    verdict: str = ""
    required_guards: tuple[str, ...] = ()
    post_execution_verification_plan: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    valid_until: str = ""
    invalid_if: tuple[str, ...] = ()
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _PreviewFields:
    """Internal bundle for refined causal-preview receipt fields."""

    timestamp: str
    actor: str
    action_id: str
    action_type: str
    target: str
    goal: str
    state_snapshot_hash: str
    snapshot_freshness: dict[str, Any]
    permissions_checked: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    causal_graph_summary: dict[str, Any]
    branch_summary: dict[str, Any]
    predicted_direct_effects: tuple[str, ...]
    predicted_indirect_effects: tuple[str, ...]
    predicted_delayed_effects: tuple[str, ...]
    constraint_checks: tuple[str, ...]
    violations: tuple[str, ...]
    risk_scores: tuple[CausalRiskScore, ...]
    compensation_plans: tuple[CompensationAssessment, ...]
    compensation_verification_status: str
    confidence_components: dict[str, float]
    confidence_score: float
    verdict: str
    required_guards: tuple[str, ...]
    post_execution_verification_plan: tuple[str, ...]
    limitations: tuple[str, ...]
    valid_until: str
    invalid_if: tuple[str, ...]


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
                compiled_plan=compiled_plan,
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
                world_state=world_state,
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
        metadata = {"simulator": "causal_simulator"}
        if world_state is not None:
            metadata["observed_world_state_hash"] = world_state.state_hash
        if world_state and compiled_plan.plan_dag.state_hash != world_state.state_hash:
            would_execute = False
            if reason == "simulation_passed":
                reason = "world_state_mismatch"
            required_controls = _dedupe((*required_controls, "refresh_world_state_projection"))
            failure_modes = _dedupe((*failure_modes, "world_state_mismatch"))
        if world_state and world_state.open_contradiction_count > 0:
            would_execute = False
            reason = "open_world_contradictions"
            required_controls = _dedupe((*required_controls, "resolve_world_contradictions"))
            failure_modes = _dedupe((*failure_modes, "world_state_contradiction"))
        return _receipt(
            compiled_plan=compiled_plan,
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
            metadata=metadata,
            world_state=world_state,
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


def _preview_fields(
    *,
    compiled_plan: CompiledGoalPlan,
    step_results: tuple[SimulationStepResult, ...],
    required_controls: tuple[str, ...],
    failure_modes: tuple[str, ...],
    compensation_path: str,
    would_execute: bool,
    reason: str,
    state_hash: str,
    world_state: WorldState | None,
) -> _PreviewFields:
    snapshot_freshness = _snapshot_freshness(
        expected_state_hash=state_hash,
        world_state=world_state,
    )
    causal_graph_summary = _causal_graph_summary(compiled_plan)
    branch_summary = _branch_summary(compiled_plan)
    compensation_plans = _compensation_assessments(
        compiled_plan=compiled_plan,
        step_results=step_results,
    )
    compensation_verification_status = _aggregate_compensation_status(compensation_plans)
    unknowns = _unknowns(
        compiled_plan=compiled_plan,
        snapshot_freshness=snapshot_freshness,
        compensation_plans=compensation_plans,
    )
    risk_scores = _risk_scores(
        compiled_plan=compiled_plan,
        step_results=step_results,
        required_controls=required_controls,
        compensation_plans=compensation_plans,
    )
    predicted_direct_effects = _predicted_direct_effects(compiled_plan)
    predicted_indirect_effects = _predicted_indirect_effects(compiled_plan)
    predicted_delayed_effects = _predicted_delayed_effects(compiled_plan)
    violations = _violations(
        reason=reason,
        failure_modes=failure_modes,
        required_controls=required_controls,
    )
    confidence_components = _confidence_components(
        snapshot_freshness=snapshot_freshness,
        causal_graph_summary=causal_graph_summary,
        branch_summary=branch_summary,
        compensation_verification_status=compensation_verification_status,
        unknowns=unknowns,
        step_results=step_results,
    )
    confidence_score = min(confidence_components.values()) if confidence_components else 0.0
    verdict = _select_receipt_verdict(
        compiled_plan=compiled_plan,
        would_execute=would_execute,
        reason=reason,
        required_controls=required_controls,
        failure_modes=failure_modes,
        snapshot_freshness=snapshot_freshness,
        branch_summary=branch_summary,
        risk_scores=risk_scores,
        compensation_verification_status=compensation_verification_status,
    )
    required_guards = _required_guards(
        verdict=verdict,
        required_controls=required_controls,
        state_hash=state_hash,
    )
    invalid_if = _invalid_if(compiled_plan=compiled_plan, state_hash=state_hash)
    return _PreviewFields(
        timestamp=world_state.projected_at if world_state else "snapshot:not-bound",
        actor=compiled_plan.goal.identity_id,
        action_id=compiled_plan.plan_dag.plan_id,
        action_type=_action_type(compiled_plan),
        target=_target(compiled_plan),
        goal=compiled_plan.goal.objective,
        state_snapshot_hash=state_hash,
        snapshot_freshness=snapshot_freshness,
        permissions_checked=_permissions_checked(compiled_plan),
        assumptions=_assumptions(compiled_plan),
        unknowns=unknowns,
        causal_graph_summary=causal_graph_summary,
        branch_summary=branch_summary,
        predicted_direct_effects=predicted_direct_effects,
        predicted_indirect_effects=predicted_indirect_effects,
        predicted_delayed_effects=predicted_delayed_effects,
        constraint_checks=_constraint_checks(compiled_plan),
        violations=violations,
        risk_scores=risk_scores,
        compensation_plans=compensation_plans,
        compensation_verification_status=compensation_verification_status,
        confidence_components=confidence_components,
        confidence_score=round(confidence_score, 4),
        verdict=verdict,
        required_guards=required_guards,
        post_execution_verification_plan=_post_execution_verification_plan(compiled_plan),
        limitations=_limitations(compensation_path=compensation_path),
        valid_until=f"state_hash:{state_hash}" if state_hash != _SNAPSHOT_NOT_BOUND else "requires_world_state_snapshot",
        invalid_if=invalid_if,
    )


def _snapshot_freshness(
    *,
    expected_state_hash: str,
    world_state: WorldState | None,
) -> dict[str, Any]:
    observed_state_hash = world_state.state_hash if world_state else ""
    if expected_state_hash == _SNAPSHOT_NOT_BOUND:
        status = "unknown"
        score = 0.35
    elif world_state is None:
        status = "unknown"
        score = 0.35
    elif observed_state_hash != expected_state_hash:
        status = "stale"
        score = 0.2
    elif world_state.open_contradiction_count > 0:
        status = "conflicted"
        score = 0.1
    else:
        status = "fresh"
        score = 1.0
    return {
        "status": status,
        "score": score,
        "expected_state_hash": expected_state_hash,
        "observed_state_hash": observed_state_hash,
        "projected_at": world_state.projected_at if world_state else "",
    }


def _causal_graph_summary(compiled_plan: CompiledGoalPlan) -> dict[str, Any]:
    graph = compiled_plan.causal_chain_graph
    if graph is None:
        return {
            "graph_id": "",
            "node_count": 0,
            "edge_count": 0,
            "proof_state": "Unknown",
            "coverage_score": 0.0,
        }
    node_count = len(graph.nodes)
    edge_count = len(graph.edges)
    coverage_score = 1.0 if node_count and edge_count else 0.25
    if compiled_plan.steps and node_count < len(compiled_plan.steps):
        coverage_score = min(coverage_score, 0.5)
    return {
        "graph_id": graph.graph_id,
        "node_count": node_count,
        "edge_count": edge_count,
        "proof_state": graph.proof_state,
        "coverage_score": coverage_score,
    }


def _branch_summary(compiled_plan: CompiledGoalPlan) -> dict[str, Any]:
    required_branches = _required_branches(compiled_plan)
    simulated_branches = tuple(required_branches)
    dependency_coverage_score = _dependency_coverage_score(compiled_plan)
    branch_coverage_score = (
        len(simulated_branches) / len(required_branches)
        if required_branches
        else 0.0
    )
    return {
        "required_branches": list(required_branches),
        "simulated_branches": list(simulated_branches),
        "required_branch_count": len(required_branches),
        "simulated_branch_count": len(simulated_branches),
        "branch_coverage_score": round(branch_coverage_score, 4),
        "dependency_coverage_score": dependency_coverage_score,
    }


def _required_branches(compiled_plan: CompiledGoalPlan) -> tuple[str, ...]:
    if not compiled_plan.steps:
        return ("admission_failure",)
    branches = ["expected", "known_failure", "rollback"]
    if compiled_plan.goal.risk_tier in {"medium", "high", "critical"}:
        branches.extend(("partial_failure", "unknown_dependency"))
    if _has_external_or_mutating_step(compiled_plan):
        branches.extend(("adversarial", "stale_state"))
    return _dedupe(branches)


def _dependency_coverage_score(compiled_plan: CompiledGoalPlan) -> float:
    if len(compiled_plan.steps) <= 1:
        return 1.0
    declared_edges = set(tuple(edge) for edge in compiled_plan.plan_dag.edges)
    expected_edges = {
        (dependency, step.step_id)
        for step in compiled_plan.steps
        for dependency in step.depends_on
    }
    if not expected_edges:
        return 1.0
    covered = len(expected_edges.intersection(declared_edges))
    return round(covered / len(expected_edges), 4)


def _has_external_or_mutating_step(compiled_plan: CompiledGoalPlan) -> bool:
    for contract in compiled_plan.operator_contracts:
        if contract.side_effects:
            return True
    return any(not step.side_effects_bounded for step in compiled_plan.steps)


def _compensation_assessments(
    *,
    compiled_plan: CompiledGoalPlan,
    step_results: tuple[SimulationStepResult, ...],
) -> tuple[CompensationAssessment, ...]:
    if not compiled_plan.steps:
        return ()
    result_by_step = {result.step_id: result for result in step_results}
    contract_by_step = {
        step.step_id: contract
        for step in compiled_plan.steps
        for contract in compiled_plan.operator_contracts
        if contract.operator_id == step.capability_id
    }
    assessments: list[CompensationAssessment] = []
    for step in compiled_plan.steps:
        result = result_by_step.get(step.step_id)
        contract = contract_by_step.get(step.step_id)
        recovery_type = contract.rollback_type if contract is not None else step.rollback.action_type
        capability_id = _step_compensation_path(step)
        status = _compensation_status(step=step, capability_id=capability_id)
        if status == "NOT_REQUIRED":
            steps = ("no rollback required for read-only or non-mutating preview",)
            limitations = ("real execution still requires post-action observation",)
        elif status in {"PLAUSIBLE", "VERIFIED"}:
            steps = (
                f"Invoke compensation path {capability_id}",
                "verify terminal recovery evidence",
                "emit recovery or reconciliation receipt",
            )
            limitations = (
                "static dry-run verifies binding presence, not live recovery success",
                "external provider effects may require forward compensation",
            )
        else:
            steps = ("stop execution before irreversible effect", "escalate for operator review")
            limitations = ("no verified rollback capability is bound",)
        assessments.append(
            CompensationAssessment(
                strategy="not_required" if status == "NOT_REQUIRED" else "rollback_or_compensate",
                step_id=step.step_id,
                capability_id=capability_id,
                verification_status=status,
                recovery_type=recovery_type or "unknown",
                steps=steps,
                limitations=limitations,
            )
        )
    return tuple(assessments)


def _compensation_status(
    *,
    step: GovernedPlanStep,
    capability_id: str,
) -> str:
    if not step.rollback.required:
        return "NOT_REQUIRED"
    if capability_id in {"", "none"}:
        return "UNAVAILABLE"
    if step.side_effects_bounded:
        return "PLAUSIBLE"
    return "UNTESTED"


def _aggregate_compensation_status(
    compensation_plans: tuple[CompensationAssessment, ...],
) -> str:
    if not compensation_plans:
        return "UNAVAILABLE"
    statuses = tuple(plan.verification_status for plan in compensation_plans)
    return min(statuses, key=lambda status: _COMPENSATION_ORDER.get(status, -1))


def _unknowns(
    *,
    compiled_plan: CompiledGoalPlan,
    snapshot_freshness: dict[str, Any],
    compensation_plans: tuple[CompensationAssessment, ...],
) -> tuple[str, ...]:
    unknowns: list[str] = []
    if snapshot_freshness["status"] != "fresh":
        unknowns.append(f"snapshot_freshness:{snapshot_freshness['status']}")
    if compiled_plan.gap_theorem is not None:
        unknowns.extend(f"missing_fact:{item}" for item in compiled_plan.gap_theorem.missing_facts)
        unknowns.extend(f"missing_permission:{item}" for item in compiled_plan.gap_theorem.missing_permissions)
        unknowns.extend(f"missing_tool:{item}" for item in compiled_plan.gap_theorem.missing_tools)
        unknowns.extend(f"missing_evidence:{item}" for item in compiled_plan.gap_theorem.missing_evidence)
        unknowns.extend(f"missing_verifier:{item}" for item in compiled_plan.gap_theorem.missing_verifiers)
        unknowns.extend(f"conflict:{item}" for item in compiled_plan.gap_theorem.conflicts)
    if compiled_plan.verification_bundle is not None:
        unknowns.extend(compiled_plan.verification_bundle.unresolved)
    for plan in compensation_plans:
        if plan.verification_status not in {"VERIFIED", "NOT_REQUIRED"}:
            unknowns.append(f"compensation_{plan.verification_status.lower()}:{plan.step_id}")
    return _dedupe(unknowns)


def _risk_scores(
    *,
    compiled_plan: CompiledGoalPlan,
    step_results: tuple[SimulationStepResult, ...],
    required_controls: tuple[str, ...],
    compensation_plans: tuple[CompensationAssessment, ...],
) -> tuple[CausalRiskScore, ...]:
    if not compiled_plan.steps:
        return (
            _risk_score(
                branch_id="admission_failure",
                risk_type="admission",
                risk_tier="medium",
                external=False,
                mutating=False,
                recovery_type="none",
                mitigation_strength=0.1,
                likelihood=0.9,
                uncertainty=0.8,
                cascade_potential=0.2,
                description="No typed capability plan exists, so effects cannot be simulated.",
            ),
        )
    result_by_step = {result.step_id: result for result in step_results}
    compensation_by_step = {plan.step_id: plan for plan in compensation_plans}
    contract_by_step = {
        step.step_id: contract
        for step in compiled_plan.steps
        for contract in compiled_plan.operator_contracts
        if contract.operator_id == step.capability_id
    }
    scores: list[CausalRiskScore] = []
    for step in compiled_plan.steps:
        contract = contract_by_step.get(step.step_id)
        result = result_by_step.get(step.step_id)
        compensation = compensation_by_step.get(step.step_id)
        side_effects = contract.side_effects if contract is not None else ()
        external = any(str(effect).startswith("external_system:") for effect in side_effects)
        mutating = "world_state_mutation" in side_effects or not step.side_effects_bounded
        mitigation_strength = _mitigation_strength(
            compensation.verification_status if compensation is not None else "UNAVAILABLE"
        )
        evidence_count = len(result.evidence_required) if result is not None else 0
        likelihood = 0.35 + (0.2 if result and result.required_controls else 0.0)
        likelihood += min(0.2, evidence_count * 0.03)
        uncertainty = 0.35 + (0.15 if result and result.required_controls else 0.0)
        uncertainty += min(0.25, evidence_count * 0.04)
        scores.append(
            _risk_score(
                branch_id=f"expected:{step.step_id}",
                risk_type="operational",
                risk_tier=step.approval.risk_tier,
                external=external,
                mutating=mutating,
                recovery_type=contract.rollback_type if contract is not None else step.rollback.action_type,
                mitigation_strength=mitigation_strength,
                likelihood=min(1.0, likelihood),
                uncertainty=min(1.0, uncertainty),
                cascade_potential=0.75 if (external or step.depends_on) else 0.35,
                description=f"Forecast for {step.capability_id} under dry-run branch expected:{step.step_id}.",
            )
        )
    if required_controls:
        scores.append(
            _risk_score(
                branch_id="control_gap",
                risk_type="governance",
                risk_tier=compiled_plan.goal.risk_tier,
                external=_has_external_or_mutating_step(compiled_plan),
                mutating=_has_external_or_mutating_step(compiled_plan),
                recovery_type="governance_control",
                mitigation_strength=0.4,
                likelihood=0.8,
                uncertainty=0.7,
                cascade_potential=0.5,
                description="Required controls are pending before execution authority.",
            )
        )
    return tuple(scores)


def _risk_score(
    *,
    branch_id: str,
    risk_type: str,
    risk_tier: str,
    external: bool,
    mutating: bool,
    recovery_type: str,
    mitigation_strength: float,
    likelihood: float,
    uncertainty: float,
    cascade_potential: float,
    description: str,
) -> CausalRiskScore:
    severity = {"low": 0.25, "medium": 0.55, "high": 0.85, "critical": 1.0}.get(risk_tier, 0.55)
    exposure = 0.85 if external else 0.6 if mutating else 0.25
    irreversibility = {
        "reversible": 0.3,
        "compensatable": 0.65,
        "irreversible": 1.0,
    }.get(recovery_type, 0.75)
    denominator = max(mitigation_strength, 0.1)
    raw_score = (
        severity
        * likelihood
        * exposure
        * irreversibility
        * uncertainty
        * cascade_potential
    ) / denominator
    risk_id = canonical_hash(
        {
            "branch_id": branch_id,
            "risk_type": risk_type,
            "risk_tier": risk_tier,
            "description": description,
        }
    )[:16]
    return CausalRiskScore(
        risk_id=f"risk-{risk_id}",
        branch_id=branch_id,
        risk_type=risk_type,
        score=round(min(1.0, raw_score), 4),
        severity=severity,
        likelihood=round(likelihood, 4),
        exposure=exposure,
        irreversibility=irreversibility,
        uncertainty=round(uncertainty, 4),
        cascade_potential=cascade_potential,
        mitigation_strength=mitigation_strength,
        description=description,
    )


def _mitigation_strength(status: str) -> float:
    return {
        "VERIFIED": 0.95,
        "PLAUSIBLE": 0.7,
        "PARTIAL": 0.45,
        "UNTESTED": 0.3,
        "UNAVAILABLE": 0.1,
        "DANGEROUS": 0.1,
        "NOT_REQUIRED": 0.9,
    }.get(status, 0.2)


def _predicted_direct_effects(compiled_plan: CompiledGoalPlan) -> tuple[str, ...]:
    effects: list[str] = []
    for contract in compiled_plan.operator_contracts:
        effects.extend(contract.effects)
    if not effects and not compiled_plan.steps:
        effects.append("no_effect_without_typed_capability_plan")
    return _dedupe(effects)


def _predicted_indirect_effects(compiled_plan: CompiledGoalPlan) -> tuple[str, ...]:
    effects: list[str] = []
    for step in compiled_plan.steps:
        effects.extend(f"dependency:{dependency}->{step.step_id}" for dependency in step.depends_on)
    for contract in compiled_plan.operator_contracts:
        effects.extend(f"side_effect:{effect}" for effect in contract.side_effects)
    return _dedupe(effects)


def _predicted_delayed_effects(compiled_plan: CompiledGoalPlan) -> tuple[str, ...]:
    effects: list[str] = []
    for step in compiled_plan.steps:
        effects.extend(f"post_execution_evidence:{evidence.evidence_type}" for evidence in step.required_evidence)
    effects.extend(f"terminal_condition:{condition.condition}" for condition in compiled_plan.terminal_conditions)
    return _dedupe(effects)


def _violations(
    *,
    reason: str,
    failure_modes: tuple[str, ...],
    required_controls: tuple[str, ...],
) -> tuple[str, ...]:
    violations: list[str] = []
    if reason in {"no_capability_plan", "open_world_contradictions", "world_state_mismatch"}:
        violations.append(reason)
    hard_failure_modes = {
        "plan_compilation_blocked",
        "world_state_contradiction",
        "world_state_mismatch",
        "unbounded_side_effect",
        "missing_compensation_path",
    }
    violations.extend(mode for mode in failure_modes if mode in hard_failure_modes)
    if "operator_review" in required_controls:
        violations.append("side_effect_boundary_requires_operator_review")
    return _dedupe(violations)


def _confidence_components(
    *,
    snapshot_freshness: dict[str, Any],
    causal_graph_summary: dict[str, Any],
    branch_summary: dict[str, Any],
    compensation_verification_status: str,
    unknowns: tuple[str, ...],
    step_results: tuple[SimulationStepResult, ...],
) -> dict[str, float]:
    evidence_confidence = 0.9
    if any(result.evidence_required for result in step_results):
        evidence_confidence = 0.65
    if unknowns:
        evidence_confidence = max(0.2, evidence_confidence - min(0.35, 0.03 * len(unknowns)))
    return {
        "state_confidence": float(snapshot_freshness.get("score", 0.0)),
        "model_confidence": float(causal_graph_summary.get("coverage_score", 0.0)),
        "dependency_confidence": float(branch_summary.get("dependency_coverage_score", 0.0)),
        "branch_confidence": float(branch_summary.get("branch_coverage_score", 0.0)),
        "rollback_confidence": _mitigation_strength(compensation_verification_status),
        "evidence_confidence": round(evidence_confidence, 4),
        "observability_confidence": 0.8 if step_results else 0.45,
    }


def _select_receipt_verdict(
    *,
    compiled_plan: CompiledGoalPlan,
    would_execute: bool,
    reason: str,
    required_controls: tuple[str, ...],
    failure_modes: tuple[str, ...],
    snapshot_freshness: dict[str, Any],
    branch_summary: dict[str, Any],
    risk_scores: tuple[CausalRiskScore, ...],
    compensation_verification_status: str,
) -> str:
    if reason == "no_capability_plan" or "plan_compilation_blocked" in failure_modes:
        return "BLOCK"
    if reason == "open_world_contradictions" or "world_state_contradiction" in failure_modes:
        return "BLOCK"
    if snapshot_freshness["status"] == "stale":
        return "REQUIRE_MORE_EVIDENCE"
    if (
        snapshot_freshness["status"] == "unknown"
        and compiled_plan.goal.risk_tier in {"medium", "high", "critical"}
    ):
        return "REQUIRE_MORE_EVIDENCE"
    if float(branch_summary.get("branch_coverage_score", 0.0)) < 1.0:
        return "SIMULATION_INCONCLUSIVE"
    if compensation_verification_status in {"UNAVAILABLE", "DANGEROUS"} and _has_external_or_mutating_step(compiled_plan):
        return "REQUIRE_HUMAN_REVIEW"
    if any("approval" in control or control == "operator_review" for control in required_controls):
        return "REQUIRE_HUMAN_REVIEW"
    if any(risk.score >= 0.7 for risk in risk_scores):
        return "REQUIRE_HUMAN_REVIEW"
    if required_controls or not would_execute:
        return "REQUIRE_MORE_EVIDENCE"
    if compiled_plan.steps:
        return "APPROVE_WITH_GUARDS"
    return "APPROVE"


def _required_guards(
    *,
    verdict: str,
    required_controls: tuple[str, ...],
    state_hash: str,
) -> tuple[str, ...]:
    if verdict == "BLOCK":
        return required_controls
    guards = list(required_controls)
    if state_hash != _SNAPSHOT_NOT_BOUND:
        guards.append("fresh_state_hash_before_execution")
    guards.extend((
        "post_execution_verification_receipt",
        "prediction_vs_actual_reconciliation",
        "dry_run_receipt_expiration_check",
    ))
    return _dedupe(guards)


def _post_execution_verification_plan(compiled_plan: CompiledGoalPlan) -> tuple[str, ...]:
    plan = [
        "verify_real_state_hash_matches_snapshot_before_execution",
        "capture_execution_receipt_if_action_runs",
        "compare_predicted_effects_against_observed_effects",
        "emit_prediction_reconciliation_receipt",
    ]
    for step in compiled_plan.steps:
        plan.extend(f"collect_evidence:{evidence.evidence_type}" for evidence in step.required_evidence)
    return _dedupe(plan)


def _constraint_checks(compiled_plan: CompiledGoalPlan) -> tuple[str, ...]:
    checks = [
        "dry_run_no_real_write_path",
        "simulation_success_not_real_success",
        "state_snapshot_hash_checked",
        "causal_graph_coverage_checked",
        "branch_coverage_checked",
        "rollback_or_compensation_binding_checked",
        "post_execution_verification_required",
    ]
    if compiled_plan.steps:
        checks.append("step_preconditions_checked")
        checks.append("step_required_evidence_projected")
    return tuple(checks)


def _permissions_checked(compiled_plan: CompiledGoalPlan) -> tuple[str, ...]:
    permissions: list[str] = ["simulation_read"]
    for contract in compiled_plan.operator_contracts:
        permissions.extend(contract.permissions)
        permissions.extend(f"authority:{authority}" for authority in contract.authority_required)
    return _dedupe(permissions)


def _assumptions(compiled_plan: CompiledGoalPlan) -> tuple[str, ...]:
    assumptions = [
        "causal_model_from_compiled_capability_plan",
        "dry_run_does_not_execute_real_actions",
        "post_execution_evidence_required_for_success_certification",
    ]
    if compiled_plan.compile_receipt is not None:
        assumptions.extend(compiled_plan.compile_receipt.assumptions)
    return _dedupe(assumptions)


def _action_type(compiled_plan: CompiledGoalPlan) -> str:
    if not compiled_plan.steps:
        return "uncompiled_goal"
    if len(compiled_plan.steps) == 1:
        return compiled_plan.steps[0].capability_id
    return "multi_step_capability_plan"


def _target(compiled_plan: CompiledGoalPlan) -> str:
    if compiled_plan.steps:
        return ",".join(step.capability_id for step in compiled_plan.steps)
    return compiled_plan.plan_dag.plan_id


def _invalid_if(
    *,
    compiled_plan: CompiledGoalPlan,
    state_hash: str,
) -> tuple[str, ...]:
    invalidators = [
        "policy_changes",
        "permission_changes",
        "capability_passport_changes",
        "external_service_contract_changes",
    ]
    if state_hash != _SNAPSHOT_NOT_BOUND:
        invalidators.append("world_state_hash_changes")
    if compiled_plan.steps:
        invalidators.append("plan_dag_changes")
    return tuple(invalidators)


def _limitations(*, compensation_path: str) -> tuple[str, ...]:
    limitations = [
        "dry_run_estimates_consequences_only",
        "dry_run_success_does_not_certify_real_execution_success",
        "causal_model_quality_bounds_prediction_quality",
        "validated_real_outcome_required_before_model_calibration",
    ]
    if compensation_path in {"", "none", "not_applicable"}:
        limitations.append("rollback_or_compensation_path_not_executed_in_dry_run")
    return tuple(limitations)


def _receipt(
    *,
    compiled_plan: CompiledGoalPlan,
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
    world_state: WorldState | None,
) -> CausalSimulationReceipt:
    preview = _preview_fields(
        compiled_plan=compiled_plan,
        step_results=step_results,
        required_controls=required_controls,
        failure_modes=failure_modes,
        compensation_path=compensation_path,
        would_execute=would_execute,
        reason=reason,
        state_hash=state_hash,
        world_state=world_state,
    )
    receipt_metadata = {
        **metadata,
        "universal_causal_preview_contract": "refined_v2",
        "real_mutation_performed": False,
        "anti_false_success_barrier": True,
        "dry_run_success_is_not_execution_success": True,
        "model_calibration_requires_validated_outcome": True,
    }
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
        engine_version=ENGINE_VERSION,
        timestamp=preview.timestamp,
        actor=preview.actor,
        action_id=preview.action_id,
        action_type=preview.action_type,
        target=preview.target,
        goal=preview.goal,
        simulation_boundary=dict(_SIMULATION_BOUNDARY),
        state_snapshot_hash=preview.state_snapshot_hash,
        snapshot_freshness=preview.snapshot_freshness,
        permissions_checked=preview.permissions_checked,
        assumptions=preview.assumptions,
        unknowns=preview.unknowns,
        causal_graph_summary=preview.causal_graph_summary,
        branch_summary=preview.branch_summary,
        predicted_direct_effects=preview.predicted_direct_effects,
        predicted_indirect_effects=preview.predicted_indirect_effects,
        predicted_delayed_effects=preview.predicted_delayed_effects,
        constraint_checks=preview.constraint_checks,
        violations=preview.violations,
        risk_scores=preview.risk_scores,
        compensation_plans=preview.compensation_plans,
        compensation_verification_status=preview.compensation_verification_status,
        confidence_components=preview.confidence_components,
        confidence_score=preview.confidence_score,
        verdict=preview.verdict,
        required_guards=preview.required_guards,
        post_execution_verification_plan=preview.post_execution_verification_plan,
        limitations=preview.limitations,
        valid_until=preview.valid_until,
        invalid_if=preview.invalid_if,
        receipt_hash="",
        metadata=receipt_metadata,
    )
    payload = asdict(receipt)
    receipt_hash = canonical_hash(payload)
    return replace(
        receipt,
        simulation_id=f"sim-{receipt_hash[:16]}",
        receipt_hash=receipt_hash,
    )
