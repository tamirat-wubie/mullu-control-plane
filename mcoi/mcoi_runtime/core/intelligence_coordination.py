"""Purpose: deterministic coordination kernels for constraint-first reasoning.
Governance scope: pre-planning constraint pruning, explicit method arbitration,
    counterfactual branch simulation, and governed world-model delta proposals.
Dependencies: intelligence coordination contracts and runtime invariant errors.
Invariants:
  - Hard constraints with Fail or Unknown block execution.
  - Soft utility Unknown degrades without blocking.
  - Candidate methods are rejected before scoring if incompatible or over budget.
  - Counterfactual branches never mutate their baseline snapshot.
  - World-model deltas require evidence and an explicit governance decision.
  - Kernel outputs are immutable proof-carrying contract records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Iterable, Mapping

from ..contracts.intelligence_coordination import (
    AbstractionControlReport,
    AbstractionControlStatus,
    AbstractionScale,
    AdaptiveReplanRecommendation,
    CausalDynamicsStatus,
    CausalGraphDynamicsReport,
    CoordinationAbstractionLayer,
    CompressionPatternDiscoveryReport,
    ConstraintSatisfiabilityReport,
    CorrectionActionKind,
    CorrectionRepairAction,
    CorrectionRepairReport,
    CorrectionRepairStatus,
    CoordinationCausalEdge,
    CoordinationCausalNode,
    CoordinationConstraint,
    CoordinationGroundingClaim,
    CoordinationPerspective,
    CoordinationPatternCandidate,
    CoordinationResourceLimit,
    CoordinationTemporalEvent,
    CounterfactualBranch,
    DiagnosisSeverity,
    DynamicWorldModelContinuityReport,
    FailureMode,
    FailureReasoningMap,
    FailureSeverity,
    GovernedWorldModelDelta,
    IntelligenceCoordinationEpisode,
    MethodArbitrationProof,
    MethodCandidate,
    MethodProblemSignature,
    MultiPerspectiveReasoningReport,
    OrchestrationReadinessReport,
    OrchestrationReadinessVerdict,
    PerspectiveComparisonStatus,
    PerspectiveKind,
    PatternDiscoveryStatus,
    ProofState,
    ReplanTrigger,
    ResourceBoundedControlReport,
    ResourceBoundStatus,
    SemanticGroundingReport,
    SemanticGroundingStatus,
    SelfDiagnosisReport,
    SolverTerminalOutcome,
    TemporalCheckStatus,
    TemporalStateEvolutionReport,
    TradeoffOption,
    TradeoffReasoningReport,
    UncertaintyPropagationReport,
    WorldContinuityStatus,
    WorldIdentityContinuityCheck,
    WorldSnapshotLineageLink,
)
from .invariants import RuntimeCoreInvariantError


@dataclass(frozen=True, slots=True)
class CounterfactualInterventionSpec:
    """Typed input for one episode-local counterfactual simulation."""

    branch_id: str
    intervention: str
    affected_entity_ids: tuple[str, ...] = ()
    affected_relation_ids: tuple[str, ...] = ()
    predicted_delta_refs: tuple[str, ...] = ()
    reversible_step_ids: tuple[str, ...] = ()
    irreversible_risk_ids: tuple[str, ...] = ()
    confidence_lower: float = 0.0
    confidence_upper: float = 1.0


@dataclass(frozen=True, slots=True)
class WorldModelDeltaProposalSpec:
    """Typed input for optional world-model delta proposal from a branch."""

    delta_id: str
    source_evidence_ids: tuple[str, ...]
    branch_id: str
    governance_decision_ref: str
    proposed_confidence_change_refs: tuple[str, ...] = ()
    contradictions_created: tuple[str, ...] = ()
    contradictions_resolved: tuple[str, ...] = ()
    allow_irreversible_risk: bool = False


@dataclass(frozen=True, slots=True)
class IntelligenceCoordinationBuildResult:
    """Complete episode plus proof artifacts emitted by the orchestration builder."""

    episode: IntelligenceCoordinationEpisode
    constraint_report: ConstraintSatisfiabilityReport
    method_arbitration: MethodArbitrationProof
    failure_map: FailureReasoningMap
    tradeoff_report: TradeoffReasoningReport
    uncertainty_report: UncertaintyPropagationReport
    self_diagnosis: SelfDiagnosisReport
    replan_recommendation: AdaptiveReplanRecommendation
    temporal_report: TemporalStateEvolutionReport
    causal_dynamics_report: CausalGraphDynamicsReport
    abstraction_report: AbstractionControlReport
    resource_report: ResourceBoundedControlReport
    grounding_report: SemanticGroundingReport
    perspective_report: MultiPerspectiveReasoningReport
    compression_report: CompressionPatternDiscoveryReport
    correction_report: CorrectionRepairReport
    continuity_report: DynamicWorldModelContinuityReport
    readiness_report: OrchestrationReadinessReport
    world_model_delta: GovernedWorldModelDelta | None = None


def _unique_text_tuple(values: Iterable[str], field_name: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    """Return a deterministic unique tuple of non-empty text values."""
    ordered_values = tuple(values)
    if not allow_empty and not ordered_values:
        raise RuntimeCoreInvariantError(f"{field_name} is required")
    for value in ordered_values:
        if not isinstance(value, str) or not value:
            raise RuntimeCoreInvariantError(f"{field_name} must contain non-empty text values")
    if len(set(ordered_values)) != len(ordered_values):
        raise RuntimeCoreInvariantError(f"{field_name} must contain unique values")
    return ordered_values


class ConstraintReasoningKernel:
    """Pure kernel for satisfiability reports over explicit proof-state constraints."""

    def evaluate(
        self,
        *,
        report_id: str,
        constraints: Iterable[CoordinationConstraint],
        generated_at: str,
        contradiction_record_ids: Iterable[str] = (),
    ) -> ConstraintSatisfiabilityReport:
        """Evaluate constraints into a proof-state report.

        Input contract: all constraints are already typed `CoordinationConstraint`
        instances carrying explicit proof states.
        Output contract: returns one immutable `ConstraintSatisfiabilityReport`.
        Error contract: raises `RuntimeCoreInvariantError` for duplicate or invalid
        constraint objects; dataclass validators raise `ValueError` for invalid
        report fields.
        """
        ordered_constraints = tuple(constraints)
        self._require_unique_constraints(ordered_constraints)

        evaluated: list[str] = []
        satisfied: list[str] = []
        violated: list[str] = []
        unknown: list[str] = []
        dependencies: list[str] = []
        blocked: list[str] = []

        for constraint in ordered_constraints:
            if not isinstance(constraint, CoordinationConstraint):
                raise RuntimeCoreInvariantError("constraints must contain CoordinationConstraint records")
            evaluated.append(constraint.constraint_id)
            dependencies.extend(constraint.dependency_ids)

            if constraint.proof_state == ProofState.PASS:
                satisfied.append(constraint.constraint_id)
                continue
            if constraint.proof_state == ProofState.FAIL:
                violated.append(constraint.constraint_id)
                if constraint.is_hard:
                    blocked.append(self._blocked_branch_id(report_id, constraint.constraint_id, "fail"))
                continue
            if constraint.proof_state in (ProofState.UNKNOWN, ProofState.BUDGET_UNKNOWN):
                unknown.append(constraint.constraint_id)
                if constraint.is_hard:
                    reason = "budget_unknown" if constraint.proof_state == ProofState.BUDGET_UNKNOWN else "unknown"
                    blocked.append(self._blocked_branch_id(report_id, constraint.constraint_id, reason))
                continue
            raise RuntimeCoreInvariantError("unsupported proof state")

        proof_state = self._aggregate_proof_state(ordered_constraints)
        terminal_outcome = self._terminal_outcome(proof_state)

        return ConstraintSatisfiabilityReport(
            report_id=report_id,
            evaluated_constraint_ids=tuple(evaluated),
            satisfied_constraint_ids=tuple(satisfied),
            violated_constraint_ids=tuple(violated),
            unknown_constraint_ids=tuple(unknown),
            propagated_dependencies=tuple(dict.fromkeys(dependencies)),
            contradiction_record_ids=tuple(contradiction_record_ids),
            blocked_branch_ids=tuple(blocked),
            proof_state=proof_state,
            terminal_outcome=terminal_outcome,
            generated_at=generated_at,
        )

    @staticmethod
    def _require_unique_constraints(constraints: tuple[CoordinationConstraint, ...]) -> None:
        seen: set[str] = set()
        for constraint in constraints:
            if not isinstance(constraint, CoordinationConstraint):
                raise RuntimeCoreInvariantError("constraints must contain CoordinationConstraint records")
            if constraint.constraint_id in seen:
                raise RuntimeCoreInvariantError("duplicate constraint_id")
            seen.add(constraint.constraint_id)

    @staticmethod
    def _aggregate_proof_state(constraints: tuple[CoordinationConstraint, ...]) -> ProofState:
        hard_constraints = tuple(constraint for constraint in constraints if constraint.is_hard)
        if any(constraint.proof_state == ProofState.FAIL for constraint in hard_constraints):
            return ProofState.FAIL
        if any(constraint.proof_state == ProofState.BUDGET_UNKNOWN for constraint in hard_constraints):
            return ProofState.BUDGET_UNKNOWN
        if any(constraint.proof_state == ProofState.UNKNOWN for constraint in hard_constraints):
            return ProofState.UNKNOWN
        return ProofState.PASS

    @staticmethod
    def _terminal_outcome(proof_state: ProofState) -> SolverTerminalOutcome:
        if proof_state == ProofState.PASS:
            return SolverTerminalOutcome.SOLVED_UNVERIFIED
        if proof_state == ProofState.FAIL:
            return SolverTerminalOutcome.IMPOSSIBLE_PROVED
        if proof_state == ProofState.BUDGET_UNKNOWN:
            return SolverTerminalOutcome.BUDGET_EXHAUSTED
        return SolverTerminalOutcome.AWAITING_EVIDENCE

    @staticmethod
    def _blocked_branch_id(report_id: str, constraint_id: str, reason: str) -> str:
        digest = sha256(f"{report_id}|{constraint_id}|{reason}".encode("utf-8")).hexdigest()[:16]
        return f"blocked-{digest}"


class MethodArbiter:
    """Deterministic method selector based on compatibility, resource bounds, and confidence."""

    def arbitrate(
        self,
        *,
        proof_id: str,
        problem_signature: MethodProblemSignature,
        candidates: Iterable[MethodCandidate],
        resource_budget: float,
        decided_at: str,
    ) -> MethodArbitrationProof:
        """Select a method and return an immutable arbitration proof.

        Input contract: candidates are typed `MethodCandidate` records.
        Output contract: returns one `MethodArbitrationProof` with selected and
        rejected method IDs.
        Error contract: raises `RuntimeCoreInvariantError` when no candidate can
        satisfy the hard compatibility/resource filters.
        """
        ordered_candidates = tuple(candidates)
        if not ordered_candidates:
            raise RuntimeCoreInvariantError("method candidates are required")
        candidate_ids = [candidate.method_id for candidate in ordered_candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise RuntimeCoreInvariantError("duplicate method_id")

        rejected: dict[str, str] = {}
        viable: list[tuple[float, MethodCandidate]] = []
        for candidate in ordered_candidates:
            if not isinstance(candidate, MethodCandidate):
                raise RuntimeCoreInvariantError("candidates must contain MethodCandidate records")
            if problem_signature not in candidate.compatible_signatures:
                rejected[candidate.method_id] = "incompatible_problem_signature"
                continue
            if candidate.resource_requirement > resource_budget:
                rejected[candidate.method_id] = "resource_requirement_exceeds_budget"
                continue
            score = self._score(candidate, resource_budget)
            viable.append((score, candidate))

        if not viable:
            raise RuntimeCoreInvariantError("no viable method candidate")

        selected_score, selected = sorted(
            viable,
            key=lambda item: (-item[0], item[1].estimated_cost, item[1].method_id),
        )[0]

        for _, candidate in viable:
            if candidate.method_id != selected.method_id:
                rejected[candidate.method_id] = "lower_ranked_viable_method"

        return MethodArbitrationProof(
            proof_id=proof_id,
            problem_signature=problem_signature,
            selected_method_id=selected.method_id,
            candidate_method_ids=tuple(candidate_ids),
            rejected_method_ids=tuple(rejected.keys()),
            rejection_reasons=rejected,
            selected_score=selected_score,
            resource_budget=resource_budget,
            decided_at=decided_at,
        )

    @staticmethod
    def _score(candidate: MethodCandidate, resource_budget: float) -> float:
        if resource_budget <= 0.0:
            headroom = 1.0 if candidate.resource_requirement == 0.0 else 0.0
        else:
            headroom = max(0.0, min(1.0, 1.0 - (candidate.resource_requirement / resource_budget)))
        cost_penalty = 1.0 / (1.0 + candidate.estimated_cost)
        return max(0.0, min(1.0, (0.65 * candidate.confidence) + (0.25 * headroom) + (0.10 * cost_penalty)))


class CounterfactualEngine:
    """Pure branch simulator for intervention reasoning over frozen snapshots."""

    def simulate(
        self,
        *,
        branch_id: str,
        baseline_snapshot_ref: str,
        intervention: str,
        constraint_report: ConstraintSatisfiabilityReport,
        affected_entity_ids: Iterable[str] = (),
        affected_relation_ids: Iterable[str] = (),
        predicted_delta_refs: Iterable[str] = (),
        reversible_step_ids: Iterable[str] = (),
        irreversible_risk_ids: Iterable[str] = (),
        confidence_lower: float,
        confidence_upper: float,
    ) -> CounterfactualBranch:
        """Build an immutable branch when hard constraints permit simulation.

        Input contract: `constraint_report` must have a pass proof state; affected
        entities, relations, or predicted deltas must identify the branch surface.
        Output contract: returns one `CounterfactualBranch` referencing the frozen
        baseline snapshot.
        Error contract: raises `RuntimeCoreInvariantError` for blocked hard
        constraints, empty branch surfaces, duplicate refs, or invalid report
        objects; dataclass validators reject malformed confidence envelopes.
        """
        if not isinstance(constraint_report, ConstraintSatisfiabilityReport):
            raise RuntimeCoreInvariantError("constraint_report must be a ConstraintSatisfiabilityReport")
        if constraint_report.proof_state != ProofState.PASS:
            raise RuntimeCoreInvariantError("counterfactual branch blocked by non-pass hard constraint proof state")
        if constraint_report.blocked_branch_ids:
            raise RuntimeCoreInvariantError("counterfactual branch blocked by existing blocked branches")

        entity_ids = _unique_text_tuple(affected_entity_ids, "affected_entity_ids")
        relation_ids = _unique_text_tuple(affected_relation_ids, "affected_relation_ids")
        delta_refs = _unique_text_tuple(predicted_delta_refs, "predicted_delta_refs")
        reversible_steps = _unique_text_tuple(reversible_step_ids, "reversible_step_ids")
        irreversible_risks = _unique_text_tuple(irreversible_risk_ids, "irreversible_risk_ids")
        if not entity_ids and not relation_ids and not delta_refs:
            raise RuntimeCoreInvariantError("counterfactual branch requires an affected entity, relation, or delta")

        adjusted_lower, adjusted_upper = self._adjust_confidence(
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            irreversible_risk_count=len(irreversible_risks),
        )
        return CounterfactualBranch(
            branch_id=branch_id,
            baseline_snapshot_ref=baseline_snapshot_ref,
            intervention=intervention,
            affected_entity_ids=entity_ids,
            affected_relation_ids=relation_ids,
            predicted_delta_refs=delta_refs,
            reversible_step_ids=reversible_steps,
            irreversible_risk_ids=irreversible_risks,
            confidence_lower=adjusted_lower,
            confidence_upper=adjusted_upper,
        )

    @staticmethod
    def _adjust_confidence(
        *,
        confidence_lower: float,
        confidence_upper: float,
        irreversible_risk_count: int,
    ) -> tuple[float, float]:
        risk_penalty = min(0.5, 0.1 * irreversible_risk_count)
        return (
            max(0.0, min(1.0, confidence_lower - risk_penalty)),
            max(0.0, min(1.0, confidence_upper - risk_penalty)),
        )


class WorldModelDeltaBuilder:
    """Pure builder for evidence-bound governed world-model delta proposals."""

    def propose_from_branch(
        self,
        *,
        delta_id: str,
        source_episode_id: str,
        source_evidence_ids: Iterable[str],
        branch: CounterfactualBranch,
        governance_decision_ref: str,
        proposed_confidence_change_refs: Iterable[str] = (),
        contradictions_created: Iterable[str] = (),
        contradictions_resolved: Iterable[str] = (),
        allow_irreversible_risk: bool = False,
    ) -> GovernedWorldModelDelta:
        """Propose a world-model delta from a simulated branch.

        Input contract: branch must be a `CounterfactualBranch`, evidence must be
        non-empty, and irreversible-risk branches require explicit allowance.
        Output contract: returns one immutable `GovernedWorldModelDelta`; no
        snapshot mutation occurs here.
        Error contract: raises `RuntimeCoreInvariantError` for missing evidence,
        unsafe irreversible risk, empty proposed change surface, or malformed refs.
        """
        if not isinstance(branch, CounterfactualBranch):
            raise RuntimeCoreInvariantError("branch must be a CounterfactualBranch")
        evidence_ids = _unique_text_tuple(source_evidence_ids, "source_evidence_ids", allow_empty=False)
        confidence_refs = _unique_text_tuple(proposed_confidence_change_refs, "proposed_confidence_change_refs")
        created = _unique_text_tuple(contradictions_created, "contradictions_created")
        resolved = _unique_text_tuple(contradictions_resolved, "contradictions_resolved")
        if branch.irreversible_risk_ids and not allow_irreversible_risk:
            raise RuntimeCoreInvariantError("irreversible counterfactual risk requires explicit governance allowance")
        if not branch.affected_entity_ids and not branch.affected_relation_ids and not confidence_refs:
            raise RuntimeCoreInvariantError("world-model delta requires an entity, relation, or confidence change")

        return GovernedWorldModelDelta(
            delta_id=delta_id,
            source_episode_id=source_episode_id,
            source_evidence_ids=evidence_ids,
            prior_snapshot_ref=branch.baseline_snapshot_ref,
            proposed_entity_change_refs=branch.affected_entity_ids,
            proposed_relation_change_refs=branch.affected_relation_ids,
            proposed_confidence_change_refs=confidence_refs or branch.predicted_delta_refs,
            contradictions_created=created,
            contradictions_resolved=resolved,
            governance_decision_ref=governance_decision_ref,
        )


class FailureReasoningKernel:
    """Deterministic failure-path extractor for constraints and counterfactual branches."""

    def analyze(
        self,
        *,
        map_id: str,
        source_episode_id: str,
        constraints: Iterable[CoordinationConstraint],
        branches: Iterable[CounterfactualBranch] = (),
        generated_at: str,
    ) -> FailureReasoningMap:
        """Build a failure map before execution planning.

        Input contract: constraints and branches must be typed coordination
        records. Non-pass hard constraints and irreversible branch risks become
        explicit failure modes.
        Output contract: returns one immutable `FailureReasoningMap`.
        Error contract: raises `RuntimeCoreInvariantError` for duplicate IDs or
        invalid objects; an empty failure surface returns a zero-risk map.
        """
        ordered_constraints = tuple(constraints)
        ConstraintReasoningKernel._require_unique_constraints(ordered_constraints)
        ordered_branches = tuple(branches)
        self._require_unique_branches(ordered_branches)

        failure_modes: list[FailureMode] = []
        for constraint in ordered_constraints:
            if not constraint.is_hard or constraint.proof_state == ProofState.PASS:
                continue
            failure_modes.append(
                FailureMode(
                    failure_id=self._failure_id(map_id, constraint.constraint_id),
                    source_ref=constraint.constraint_id,
                    severity=self._severity_for_constraint(constraint.proof_state),
                    trigger_constraint_ids=(constraint.constraint_id,),
                    affected_entity_ids=(),
                    cascade_failure_ids=constraint.dependency_ids,
                    hidden_assumption_ids=(constraint.constraint_id,) if constraint.proof_state == ProofState.UNKNOWN else (),
                    invariant_violation_ids=(
                        constraint.constraint_id,
                    )
                    if constraint.proof_state in (ProofState.FAIL, ProofState.BUDGET_UNKNOWN)
                    else (),
                    mitigation_refs=(),
                    likelihood=self._likelihood_for_constraint(constraint.proof_state),
                    impact=self._impact_for_constraint(constraint.proof_state),
                    reversible=constraint.proof_state == ProofState.UNKNOWN,
                    detected_at=generated_at,
                )
            )

        for branch in ordered_branches:
            if not isinstance(branch, CounterfactualBranch):
                raise RuntimeCoreInvariantError("branches must contain CounterfactualBranch records")
            for risk_id in branch.irreversible_risk_ids:
                failure_modes.append(
                    FailureMode(
                        failure_id=self._failure_id(map_id, risk_id),
                        source_ref=branch.branch_id,
                        severity=FailureSeverity.HIGH,
                        trigger_constraint_ids=(),
                        affected_entity_ids=branch.affected_entity_ids,
                        cascade_failure_ids=(),
                        hidden_assumption_ids=(),
                        invariant_violation_ids=(risk_id,),
                        mitigation_refs=branch.reversible_step_ids,
                        likelihood=max(0.0, min(1.0, 1.0 - branch.confidence_lower)),
                        impact=0.8,
                        reversible=False,
                        detected_at=generated_at,
                    )
                )

        blocked_failure_ids = tuple(failure.failure_id for failure in failure_modes if not failure.reversible)
        dominant_failure = self._dominant_failure(failure_modes)
        residual_risk = max((failure.likelihood * failure.impact for failure in failure_modes), default=0.0)
        return FailureReasoningMap(
            map_id=map_id,
            source_episode_id=source_episode_id,
            failure_modes=tuple(failure_modes),
            blocked_failure_ids=blocked_failure_ids,
            dominant_failure_id=dominant_failure.failure_id if dominant_failure is not None else None,
            residual_risk=max(0.0, min(1.0, residual_risk)),
            generated_at=generated_at,
        )

    @staticmethod
    def _require_unique_branches(branches: tuple[CounterfactualBranch, ...]) -> None:
        branch_ids: set[str] = set()
        for branch in branches:
            if not isinstance(branch, CounterfactualBranch):
                raise RuntimeCoreInvariantError("branches must contain CounterfactualBranch records")
            if branch.branch_id in branch_ids:
                raise RuntimeCoreInvariantError("duplicate branch_id")
            branch_ids.add(branch.branch_id)

    @staticmethod
    def _failure_id(map_id: str, source_id: str) -> str:
        digest = sha256(f"{map_id}|{source_id}".encode("utf-8")).hexdigest()[:16]
        return f"failure-{digest}"

    @staticmethod
    def _severity_for_constraint(proof_state: ProofState) -> FailureSeverity:
        if proof_state == ProofState.FAIL:
            return FailureSeverity.CRITICAL
        if proof_state == ProofState.BUDGET_UNKNOWN:
            return FailureSeverity.HIGH
        return FailureSeverity.MODERATE

    @staticmethod
    def _likelihood_for_constraint(proof_state: ProofState) -> float:
        if proof_state == ProofState.FAIL:
            return 1.0
        if proof_state == ProofState.BUDGET_UNKNOWN:
            return 0.75
        return 0.5

    @staticmethod
    def _impact_for_constraint(proof_state: ProofState) -> float:
        if proof_state == ProofState.FAIL:
            return 1.0
        if proof_state == ProofState.BUDGET_UNKNOWN:
            return 0.85
        return 0.6

    @staticmethod
    def _dominant_failure(failure_modes: list[FailureMode]) -> FailureMode | None:
        if not failure_modes:
            return None
        return sorted(
            failure_modes,
            key=lambda failure: (-(failure.likelihood * failure.impact), failure.failure_id),
        )[0]


class TradeoffReasoningKernel:
    """Deterministic tradeoff evaluator for bounded coordination options."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        options: Iterable[TradeoffOption],
        generated_at: str,
        safety_floor: float = 0.0,
        constraint_report: ConstraintSatisfiabilityReport | None = None,
        resource_report: ResourceBoundedControlReport | None = None,
        grounding_report: SemanticGroundingReport | None = None,
        perspective_report: MultiPerspectiveReasoningReport | None = None,
    ) -> TradeoffReasoningReport:
        """Select an option under benefit, cost, risk, confidence, and safety bounds.

        Input contract: options must be typed `TradeoffOption` records and safety
        floor must be within [0.0, 1.0].
        Output contract: returns one immutable `TradeoffReasoningReport`.
        Error contract: raises `RuntimeCoreInvariantError` when no option clears
        the safety floor, IDs are duplicated, or inputs are malformed.
        """
        if safety_floor < 0.0 or safety_floor > 1.0:
            raise RuntimeCoreInvariantError("safety_floor must be within [0.0, 1.0]")
        if constraint_report is not None and not isinstance(constraint_report, ConstraintSatisfiabilityReport):
            raise RuntimeCoreInvariantError("constraint_report must be a ConstraintSatisfiabilityReport")
        if resource_report is not None and not isinstance(resource_report, ResourceBoundedControlReport):
            raise RuntimeCoreInvariantError("resource_report must be a ResourceBoundedControlReport")
        if grounding_report is not None and not isinstance(grounding_report, SemanticGroundingReport):
            raise RuntimeCoreInvariantError("grounding_report must be a SemanticGroundingReport")
        if perspective_report is not None and not isinstance(perspective_report, MultiPerspectiveReasoningReport):
            raise RuntimeCoreInvariantError("perspective_report must be a MultiPerspectiveReasoningReport")
        ordered_options = tuple(options)
        if not ordered_options:
            raise RuntimeCoreInvariantError("tradeoff options are required")
        option_ids = [option.option_id for option in ordered_options]
        if len(set(option_ids)) != len(option_ids):
            raise RuntimeCoreInvariantError("duplicate option_id")
        for option in ordered_options:
            if not isinstance(option, TradeoffOption):
                raise RuntimeCoreInvariantError("options must contain TradeoffOption records")

        viable = tuple(option for option in ordered_options if (1.0 - option.risk) >= safety_floor)
        if not viable:
            raise RuntimeCoreInvariantError("no tradeoff option clears safety floor")
        scored = sorted(
            ((self._utility(option), option) for option in viable),
            key=lambda item: (-item[0], item[1].risk, item[1].cost, item[1].option_id),
        )
        selected_utility, selected = scored[0]
        rejected = tuple(option.option_id for option in ordered_options if option.option_id != selected.option_id)
        pareto_frontier = self._pareto_frontier(ordered_options)
        dominated = tuple(option_id for option_id in option_ids if option_id not in pareto_frontier)
        return TradeoffReasoningReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            option_ids=tuple(option_ids),
            selected_option_id=selected.option_id,
            rejected_option_ids=rejected,
            pareto_frontier_option_ids=pareto_frontier,
            selection_rationale="max_utility_with_safety_floor",
            selected_utility=selected_utility,
            safety_margin=max(0.0, min(1.0, 1.0 - selected.risk)),
            generated_at=generated_at,
            dominated_option_ids=dominated,
            utility_tension=self._utility_tension(scored),
            constraint_tension=self._constraint_tension(constraint_report),
            resource_tension=0.0 if resource_report is None else resource_report.max_pressure,
            grounding_tension=self._grounding_tension(grounding_report),
            perspective_tension=self._perspective_tension(perspective_report),
        )

    @staticmethod
    def _utility(option: TradeoffOption) -> float:
        return max(
            0.0,
            min(
                1.0,
                (0.45 * option.benefit)
                + (0.25 * option.confidence)
                + (0.15 * (1.0 - option.cost))
                + (0.15 * (1.0 - option.risk)),
            ),
        )

    @staticmethod
    def _pareto_frontier(options: tuple[TradeoffOption, ...]) -> tuple[str, ...]:
        frontier: list[str] = []
        for option in options:
            dominated = False
            for competitor in options:
                if competitor.option_id == option.option_id:
                    continue
                no_worse = (
                    competitor.benefit >= option.benefit
                    and competitor.confidence >= option.confidence
                    and competitor.cost <= option.cost
                    and competitor.risk <= option.risk
                )
                strictly_better = (
                    competitor.benefit > option.benefit
                    or competitor.confidence > option.confidence
                    or competitor.cost < option.cost
                    or competitor.risk < option.risk
                )
                if no_worse and strictly_better:
                    dominated = True
                    break
            if not dominated:
                frontier.append(option.option_id)
        return tuple(frontier)

    @staticmethod
    def _utility_tension(scored_options: list[tuple[float, TradeoffOption]]) -> float:
        if len(scored_options) < 2:
            return 0.0
        return max(0.0, min(1.0, 1.0 - (scored_options[0][0] - scored_options[1][0])))

    @staticmethod
    def _constraint_tension(report: ConstraintSatisfiabilityReport | None) -> float:
        if report is None or not report.evaluated_constraint_ids:
            return 0.0
        blocked_count = len(report.blocked_branch_ids) + len(report.unknown_constraint_ids)
        return max(0.0, min(1.0, blocked_count / len(report.evaluated_constraint_ids)))

    @staticmethod
    def _grounding_tension(report: SemanticGroundingReport | None) -> float:
        if report is None:
            return 0.0
        return max(0.0, min(1.0, 1.0 - report.grounding_coverage))

    @staticmethod
    def _perspective_tension(report: MultiPerspectiveReasoningReport | None) -> float:
        if report is None:
            return 0.0
        return max(0.0, min(1.0, 1.0 - report.agreement_score))


class UncertaintyPropagationKernel:
    """Deterministic uncertainty propagator for coordination artifacts."""

    def propagate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        constraint_report: ConstraintSatisfiabilityReport,
        method_arbitration: MethodArbitrationProof,
        failure_map: FailureReasoningMap,
        tradeoff_report: TradeoffReasoningReport,
        generated_at: str,
        causal_dynamics_report: CausalGraphDynamicsReport | None = None,
        abstraction_report: AbstractionControlReport | None = None,
        resource_report: ResourceBoundedControlReport | None = None,
        grounding_report: SemanticGroundingReport | None = None,
        perspective_report: MultiPerspectiveReasoningReport | None = None,
        compression_report: CompressionPatternDiscoveryReport | None = None,
        correction_report: CorrectionRepairReport | None = None,
        continuity_report: DynamicWorldModelContinuityReport | None = None,
    ) -> UncertaintyPropagationReport:
        """Propagate uncertainty from constraints, failures, methods, and tradeoffs."""
        if not isinstance(constraint_report, ConstraintSatisfiabilityReport):
            raise RuntimeCoreInvariantError("constraint_report must be a ConstraintSatisfiabilityReport")
        if not isinstance(method_arbitration, MethodArbitrationProof):
            raise RuntimeCoreInvariantError("method_arbitration must be a MethodArbitrationProof")
        if not isinstance(failure_map, FailureReasoningMap):
            raise RuntimeCoreInvariantError("failure_map must be a FailureReasoningMap")
        if not isinstance(tradeoff_report, TradeoffReasoningReport):
            raise RuntimeCoreInvariantError("tradeoff_report must be a TradeoffReasoningReport")
        if causal_dynamics_report is not None and not isinstance(causal_dynamics_report, CausalGraphDynamicsReport):
            raise RuntimeCoreInvariantError("causal_dynamics_report must be a CausalGraphDynamicsReport")
        if abstraction_report is not None and not isinstance(abstraction_report, AbstractionControlReport):
            raise RuntimeCoreInvariantError("abstraction_report must be an AbstractionControlReport")
        if resource_report is not None and not isinstance(resource_report, ResourceBoundedControlReport):
            raise RuntimeCoreInvariantError("resource_report must be a ResourceBoundedControlReport")
        if grounding_report is not None and not isinstance(grounding_report, SemanticGroundingReport):
            raise RuntimeCoreInvariantError("grounding_report must be a SemanticGroundingReport")
        if perspective_report is not None and not isinstance(perspective_report, MultiPerspectiveReasoningReport):
            raise RuntimeCoreInvariantError("perspective_report must be a MultiPerspectiveReasoningReport")
        if compression_report is not None and not isinstance(compression_report, CompressionPatternDiscoveryReport):
            raise RuntimeCoreInvariantError("compression_report must be a CompressionPatternDiscoveryReport")
        if correction_report is not None and not isinstance(correction_report, CorrectionRepairReport):
            raise RuntimeCoreInvariantError("correction_report must be a CorrectionRepairReport")
        if continuity_report is not None and not isinstance(continuity_report, DynamicWorldModelContinuityReport):
            raise RuntimeCoreInvariantError("continuity_report must be a DynamicWorldModelContinuityReport")

        causal_source_refs = ()
        causal_ambiguity_refs = ()
        causal_feedback_pressure = 0.0
        causal_fragility_pressure = 0.0
        if causal_dynamics_report is not None:
            causal_source_refs = (
                (causal_dynamics_report.report_id,)
                + causal_dynamics_report.feedback_edge_ids
                + causal_dynamics_report.bottleneck_node_ids
            )
            causal_ambiguity_refs = (
                causal_dynamics_report.feedback_cycle_node_ids
                + causal_dynamics_report.bridge_node_ids
            )
            causal_feedback_pressure = (
                0.10 if causal_dynamics_report.status == CausalDynamicsStatus.FEEDBACK_PRESENT else 0.0
            )
            causal_fragility_pressure = 0.15 * causal_dynamics_report.structural_fragility
        abstraction_source_refs = ()
        abstraction_ambiguity_refs = ()
        abstraction_pressure = 0.0
        if abstraction_report is not None:
            abstraction_source_refs = (
                (abstraction_report.report_id,)
                + abstraction_report.missing_scale_refs
                + abstraction_report.collapsed_layer_ids
            )
            abstraction_ambiguity_refs = abstraction_report.orphan_layer_ids
            abstraction_pressure = (
                (0.20 if abstraction_report.status == AbstractionControlStatus.COLLAPSED else 0.0)
                + (0.10 if abstraction_report.status == AbstractionControlStatus.GAP_PRESENT else 0.0)
                + (0.10 * (1.0 - abstraction_report.scale_coverage))
            )
        resource_source_refs = ()
        resource_pressure = 0.0
        if resource_report is not None:
            resource_source_refs = (
                (resource_report.report_id,)
                + resource_report.degraded_limit_ids
                + resource_report.exhausted_limit_ids
                + resource_report.overrun_limit_ids
            )
            resource_pressure = (
                (0.25 if resource_report.status in (ResourceBoundStatus.EXHAUSTED, ResourceBoundStatus.OVERRUN) else 0.0)
                + (0.10 if resource_report.status == ResourceBoundStatus.DEGRADED else 0.0)
                + (0.10 * resource_report.max_pressure)
            )
        grounding_source_refs = ()
        grounding_pressure = 0.0
        if grounding_report is not None:
            grounding_source_refs = (
                (grounding_report.report_id,)
                + grounding_report.weak_claim_ids
                + grounding_report.missing_symbol_refs
            )
            grounding_pressure = (
                (0.25 if grounding_report.status == SemanticGroundingStatus.UNGROUNDED else 0.0)
                + (0.10 if grounding_report.status == SemanticGroundingStatus.PARTIAL else 0.0)
                + (0.10 * (1.0 - grounding_report.grounding_coverage))
            )
        perspective_source_refs = ()
        perspective_ambiguity_refs = ()
        perspective_pressure = 0.0
        if perspective_report is not None:
            perspective_source_refs = (
                (perspective_report.report_id,)
                + perspective_report.missing_kind_refs
                + perspective_report.divergent_perspective_ids
                + perspective_report.low_confidence_perspective_ids
            )
            perspective_ambiguity_refs = perspective_report.divergent_perspective_ids
            perspective_pressure = (
                (0.15 if perspective_report.status == PerspectiveComparisonStatus.DIVERGENT else 0.0)
                + (0.10 if perspective_report.status == PerspectiveComparisonStatus.UNDERCOVERED else 0.0)
                + (0.10 * (1.0 - perspective_report.agreement_score))
            )
        compression_source_refs = ()
        compression_pressure = 0.0
        if compression_report is not None:
            compression_source_refs = (
                (compression_report.report_id,)
                + compression_report.redundant_symbol_refs
                + compression_report.invariant_refs
            )
            compression_pressure = (
                (0.10 if compression_report.status == PatternDiscoveryStatus.REDUNDANT else 0.0)
                + (0.15 if compression_report.status == PatternDiscoveryStatus.UNDERCOMPRESSED else 0.0)
                + (0.10 * (1.0 - compression_report.reuse_score))
            )
        correction_source_refs = ()
        correction_pressure = 0.0
        if correction_report is not None:
            correction_source_refs = (
                (correction_report.report_id,)
                + correction_report.contradiction_refs
                + correction_report.rollback_action_ids
                + correction_report.repair_action_ids
            )
            correction_pressure = (
                (0.15 if correction_report.status == CorrectionRepairStatus.REPAIR_RECOMMENDED else 0.0)
                + (0.25 if correction_report.status == CorrectionRepairStatus.ROLLBACK_RECOMMENDED else 0.0)
                + (0.10 * correction_report.repair_pressure)
            )
        continuity_source_refs = ()
        continuity_pressure = 0.0
        if continuity_report is not None:
            continuity_source_refs = (
                (continuity_report.report_id,)
                + continuity_report.broken_lineage_link_ids
                + continuity_report.drifted_identity_check_ids
            )
            continuity_pressure = (
                (0.15 if continuity_report.status == WorldContinuityStatus.FRAGMENTED else 0.0)
                + (0.20 if continuity_report.status == WorldContinuityStatus.IDENTITY_DRIFT else 0.0)
                + (0.10 * (1.0 - continuity_report.continuity_score))
            )

        source_refs = tuple(
            dict.fromkeys(
                constraint_report.unknown_constraint_ids
                + tuple(failure.failure_id for failure in failure_map.failure_modes)
                + tuple(method_arbitration.rejected_method_ids)
                + causal_source_refs
                + abstraction_source_refs
                + resource_source_refs
                + grounding_source_refs
                + perspective_source_refs
                + compression_source_refs
                + correction_source_refs
                + continuity_source_refs
            )
        )
        evidence_gap_refs = constraint_report.unknown_constraint_ids
        ambiguity_refs = tuple(
            dict.fromkeys(
                tuple(failure.hidden_assumption_ids[0] for failure in failure_map.failure_modes if failure.hidden_assumption_ids)
                + tradeoff_report.pareto_frontier_option_ids
                + causal_ambiguity_refs
                + abstraction_ambiguity_refs
                + perspective_ambiguity_refs
            )
        )
        accumulated = max(
            0.0,
            min(
                1.0,
                (0.35 * (1.0 - method_arbitration.selected_score))
                + (0.25 * failure_map.residual_risk)
                + (0.15 * (1.0 - tradeoff_report.safety_margin))
                + (0.05 * tradeoff_report.utility_tension)
                + (0.05 * tradeoff_report.constraint_tension)
                + (0.05 * tradeoff_report.resource_tension)
                + (0.05 * tradeoff_report.grounding_tension)
                + (0.05 * tradeoff_report.perspective_tension)
                + (0.15 if evidence_gap_refs else 0.0)
                + causal_feedback_pressure
                + causal_fragility_pressure
                + abstraction_pressure
                + resource_pressure
                + grounding_pressure
                + perspective_pressure
                + compression_pressure
                + correction_pressure
                + continuity_pressure
            ),
        )
        center = max(0.0, min(1.0, 1.0 - accumulated))
        spread = min(0.5, 0.1 + (0.4 * accumulated))
        return UncertaintyPropagationReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            uncertainty_source_refs=source_refs,
            ambiguity_refs=ambiguity_refs,
            confidence_lower=max(0.0, center - spread),
            confidence_upper=min(1.0, center + spread),
            accumulated_uncertainty=accumulated,
            evidence_gap_refs=evidence_gap_refs,
            generated_at=generated_at,
        )


class SelfDiagnosisKernel:
    """Deterministic self-diagnosis for episode-local reasoning quality."""

    def diagnose(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        uncertainty_report: UncertaintyPropagationReport,
        failure_map: FailureReasoningMap,
        tradeoff_report: TradeoffReasoningReport,
        resource_budget: float,
        resource_used: float,
        generated_at: str,
        causal_dynamics_report: CausalGraphDynamicsReport | None = None,
        abstraction_report: AbstractionControlReport | None = None,
        resource_report: ResourceBoundedControlReport | None = None,
        grounding_report: SemanticGroundingReport | None = None,
        perspective_report: MultiPerspectiveReasoningReport | None = None,
        compression_report: CompressionPatternDiscoveryReport | None = None,
        correction_report: CorrectionRepairReport | None = None,
        continuity_report: DynamicWorldModelContinuityReport | None = None,
    ) -> SelfDiagnosisReport:
        """Emit reasoning-quality findings and escalation state."""
        if not isinstance(uncertainty_report, UncertaintyPropagationReport):
            raise RuntimeCoreInvariantError("uncertainty_report must be an UncertaintyPropagationReport")
        if not isinstance(failure_map, FailureReasoningMap):
            raise RuntimeCoreInvariantError("failure_map must be a FailureReasoningMap")
        if not isinstance(tradeoff_report, TradeoffReasoningReport):
            raise RuntimeCoreInvariantError("tradeoff_report must be a TradeoffReasoningReport")
        if causal_dynamics_report is not None and not isinstance(causal_dynamics_report, CausalGraphDynamicsReport):
            raise RuntimeCoreInvariantError("causal_dynamics_report must be a CausalGraphDynamicsReport")
        if abstraction_report is not None and not isinstance(abstraction_report, AbstractionControlReport):
            raise RuntimeCoreInvariantError("abstraction_report must be an AbstractionControlReport")
        if resource_report is not None and not isinstance(resource_report, ResourceBoundedControlReport):
            raise RuntimeCoreInvariantError("resource_report must be a ResourceBoundedControlReport")
        if grounding_report is not None and not isinstance(grounding_report, SemanticGroundingReport):
            raise RuntimeCoreInvariantError("grounding_report must be a SemanticGroundingReport")
        if perspective_report is not None and not isinstance(perspective_report, MultiPerspectiveReasoningReport):
            raise RuntimeCoreInvariantError("perspective_report must be a MultiPerspectiveReasoningReport")
        if compression_report is not None and not isinstance(compression_report, CompressionPatternDiscoveryReport):
            raise RuntimeCoreInvariantError("compression_report must be a CompressionPatternDiscoveryReport")
        if correction_report is not None and not isinstance(correction_report, CorrectionRepairReport):
            raise RuntimeCoreInvariantError("correction_report must be a CorrectionRepairReport")
        if continuity_report is not None and not isinstance(continuity_report, DynamicWorldModelContinuityReport):
            raise RuntimeCoreInvariantError("continuity_report must be a DynamicWorldModelContinuityReport")
        if resource_budget < 0.0 or resource_used < 0.0:
            raise RuntimeCoreInvariantError("resource budget and usage must be non-negative")

        scalar_resource_pressure = 0.0 if resource_budget == 0.0 else max(0.0, min(1.0, resource_used / resource_budget))
        report_resource_pressure = 0.0 if resource_report is None else resource_report.max_pressure
        resource_pressure = max(scalar_resource_pressure, report_resource_pressure)
        causal_fragility = 0.0 if causal_dynamics_report is None else causal_dynamics_report.structural_fragility
        causal_feedback_pressure = (
            0.10
            if causal_dynamics_report is not None
            and causal_dynamics_report.status == CausalDynamicsStatus.FEEDBACK_PRESENT
            else 0.0
        )
        hallucination_risk = max(
            0.0,
            min(
                1.0,
                (0.45 * uncertainty_report.accumulated_uncertainty)
                + (0.25 * failure_map.residual_risk)
                + (0.20 if uncertainty_report.evidence_gap_refs else 0.0)
                + (0.10 * resource_pressure)
                + (0.10 * causal_fragility)
                + causal_feedback_pressure
                + (
                    0.10
                    if abstraction_report is not None
                    and abstraction_report.status == AbstractionControlStatus.COLLAPSED
                    else 0.0
                )
                + (
                    0.10
                    if grounding_report is not None
                    and grounding_report.status == SemanticGroundingStatus.UNGROUNDED
                    else 0.0
                )
                + (
                    0.10
                    if perspective_report is not None
                    and perspective_report.status == PerspectiveComparisonStatus.DIVERGENT
                    else 0.0
                )
                + (
                    0.10
                    if compression_report is not None
                    and compression_report.status == PatternDiscoveryStatus.UNDERCOMPRESSED
                    else 0.0
                )
                + (
                    0.10
                    if correction_report is not None
                    and correction_report.status == CorrectionRepairStatus.ROLLBACK_RECOMMENDED
                    else 0.0
                )
                + (
                    0.10
                    if continuity_report is not None
                    and continuity_report.status != WorldContinuityStatus.CONTINUOUS
                    else 0.0
                )
            ),
        )
        finding_refs: list[str] = []
        if uncertainty_report.accumulated_uncertainty >= 0.5:
            finding_refs.append("uncertainty_high")
        if failure_map.blocked_failure_ids:
            finding_refs.append("blocked_failure_present")
        if tradeoff_report.safety_margin < 0.5:
            finding_refs.append("low_safety_margin")
        if resource_pressure >= 0.8:
            finding_refs.append("resource_pressure_high")
        if resource_report is not None and resource_report.status in (ResourceBoundStatus.EXHAUSTED, ResourceBoundStatus.OVERRUN):
            finding_refs.append("resource_exhausted")
        if grounding_report is not None and grounding_report.status == SemanticGroundingStatus.UNGROUNDED:
            finding_refs.append("semantic_grounding_absent")
        if grounding_report is not None and grounding_report.status == SemanticGroundingStatus.PARTIAL:
            finding_refs.append("semantic_grounding_partial")
        if perspective_report is not None and perspective_report.status == PerspectiveComparisonStatus.DIVERGENT:
            finding_refs.append("perspective_divergence")
        if perspective_report is not None and perspective_report.status == PerspectiveComparisonStatus.UNDERCOVERED:
            finding_refs.append("perspective_undercovered")
        if compression_report is not None and compression_report.status == PatternDiscoveryStatus.UNDERCOMPRESSED:
            finding_refs.append("pattern_undercompressed")
        if compression_report is not None and compression_report.status == PatternDiscoveryStatus.REDUNDANT:
            finding_refs.append("pattern_redundancy_present")
        if correction_report is not None and correction_report.status == CorrectionRepairStatus.REPAIR_RECOMMENDED:
            finding_refs.append("correction_repair_recommended")
        if correction_report is not None and correction_report.status == CorrectionRepairStatus.ROLLBACK_RECOMMENDED:
            finding_refs.append("correction_rollback_recommended")
        if continuity_report is not None and continuity_report.status == WorldContinuityStatus.FRAGMENTED:
            finding_refs.append("world_lineage_fragmented")
        if continuity_report is not None and continuity_report.status == WorldContinuityStatus.IDENTITY_DRIFT:
            finding_refs.append("world_identity_drift")
        if causal_dynamics_report is not None and causal_dynamics_report.status == CausalDynamicsStatus.FEEDBACK_PRESENT:
            finding_refs.append("causal_feedback_present")
        if causal_fragility >= 0.5:
            finding_refs.append("causal_fragility_high")
        if abstraction_report is not None and abstraction_report.status == AbstractionControlStatus.COLLAPSED:
            finding_refs.append("abstraction_boundary_collapsed")
        if abstraction_report is not None and abstraction_report.status == AbstractionControlStatus.GAP_PRESENT:
            finding_refs.append("abstraction_scale_gap")
        broken_assumptions = tuple(uncertainty_report.evidence_gap_refs)
        severity = self._severity(
            hallucination_risk=hallucination_risk,
            blocked_failure_count=len(failure_map.blocked_failure_ids),
            resource_pressure=resource_pressure,
        )
        return SelfDiagnosisReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            uncertainty_report_ref=uncertainty_report.report_id,
            failure_map_ref=failure_map.map_id,
            tradeoff_report_ref=tradeoff_report.report_id,
            finding_refs=tuple(finding_refs),
            broken_assumption_refs=broken_assumptions,
            resource_pressure=resource_pressure,
            hallucination_risk=hallucination_risk,
            severity=severity,
            escalation_required=severity == DiagnosisSeverity.BLOCKING,
            generated_at=generated_at,
        )

    @staticmethod
    def _severity(
        *,
        hallucination_risk: float,
        blocked_failure_count: int,
        resource_pressure: float,
    ) -> DiagnosisSeverity:
        if blocked_failure_count > 0 or hallucination_risk >= 0.7:
            return DiagnosisSeverity.BLOCKING
        if hallucination_risk >= 0.35 or resource_pressure >= 0.8:
            return DiagnosisSeverity.WARNING
        return DiagnosisSeverity.INFO


class AdaptivePlanningKernel:
    """Deterministic replan recommender for episode-local adaptive planning."""

    def recommend(
        self,
        *,
        recommendation_id: str,
        source_episode_id: str,
        current_plan_ref: str,
        uncertainty_report: UncertaintyPropagationReport,
        self_diagnosis: SelfDiagnosisReport,
        failure_map: FailureReasoningMap,
        tradeoff_report: TradeoffReasoningReport,
        generated_at: str,
        uncertainty_threshold: float = 0.5,
        safety_margin_threshold: float = 0.5,
        resource_pressure_threshold: float = 0.8,
    ) -> AdaptiveReplanRecommendation:
        """Emit an adaptive planning recommendation with explicit trigger priority."""
        if not isinstance(uncertainty_report, UncertaintyPropagationReport):
            raise RuntimeCoreInvariantError("uncertainty_report must be an UncertaintyPropagationReport")
        if not isinstance(self_diagnosis, SelfDiagnosisReport):
            raise RuntimeCoreInvariantError("self_diagnosis must be a SelfDiagnosisReport")
        if not isinstance(failure_map, FailureReasoningMap):
            raise RuntimeCoreInvariantError("failure_map must be a FailureReasoningMap")
        if not isinstance(tradeoff_report, TradeoffReasoningReport):
            raise RuntimeCoreInvariantError("tradeoff_report must be a TradeoffReasoningReport")
        for threshold_name, threshold_value in (
            ("uncertainty_threshold", uncertainty_threshold),
            ("safety_margin_threshold", safety_margin_threshold),
            ("resource_pressure_threshold", resource_pressure_threshold),
        ):
            if threshold_value < 0.0 or threshold_value > 1.0:
                raise RuntimeCoreInvariantError(f"{threshold_name} must be within [0.0, 1.0]")

        trigger = self._trigger(
            uncertainty_report=uncertainty_report,
            self_diagnosis=self_diagnosis,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            uncertainty_threshold=uncertainty_threshold,
            safety_margin_threshold=safety_margin_threshold,
            resource_pressure_threshold=resource_pressure_threshold,
        )
        reason_refs = self._reason_refs(
            trigger=trigger,
            uncertainty_report=uncertainty_report,
            self_diagnosis=self_diagnosis,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
        )
        replan_required = trigger != ReplanTrigger.NONE
        urgency = self._urgency(
            trigger=trigger,
            uncertainty_report=uncertainty_report,
            self_diagnosis=self_diagnosis,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
        )
        return AdaptiveReplanRecommendation(
            recommendation_id=recommendation_id,
            source_episode_id=source_episode_id,
            uncertainty_report_ref=uncertainty_report.report_id,
            self_diagnosis_ref=self_diagnosis.report_id,
            failure_map_ref=failure_map.map_id,
            tradeoff_report_ref=tradeoff_report.report_id,
            trigger=trigger,
            recommended_plan_ref=f"{source_episode_id}:replan" if replan_required else current_plan_ref,
            blocked_plan_ref=current_plan_ref if replan_required else None,
            reason_refs=reason_refs,
            urgency=urgency,
            replan_required=replan_required,
            generated_at=generated_at,
        )

    @staticmethod
    def _trigger(
        *,
        uncertainty_report: UncertaintyPropagationReport,
        self_diagnosis: SelfDiagnosisReport,
        failure_map: FailureReasoningMap,
        tradeoff_report: TradeoffReasoningReport,
        uncertainty_threshold: float,
        safety_margin_threshold: float,
        resource_pressure_threshold: float,
    ) -> ReplanTrigger:
        if self_diagnosis.severity == DiagnosisSeverity.BLOCKING:
            return ReplanTrigger.DIAGNOSIS_BLOCKING
        if failure_map.blocked_failure_ids:
            return ReplanTrigger.FAILURE_BLOCKED
        if "resource_exhausted" in self_diagnosis.finding_refs:
            return ReplanTrigger.RESOURCE_EXHAUSTED
        if uncertainty_report.accumulated_uncertainty >= uncertainty_threshold:
            return ReplanTrigger.UNCERTAINTY_HIGH
        if tradeoff_report.safety_margin < safety_margin_threshold:
            return ReplanTrigger.SAFETY_MARGIN_LOW
        if self_diagnosis.resource_pressure >= resource_pressure_threshold:
            return ReplanTrigger.RESOURCE_PRESSURE_HIGH
        return ReplanTrigger.NONE

    @staticmethod
    def _reason_refs(
        *,
        trigger: ReplanTrigger,
        uncertainty_report: UncertaintyPropagationReport,
        self_diagnosis: SelfDiagnosisReport,
        failure_map: FailureReasoningMap,
        tradeoff_report: TradeoffReasoningReport,
    ) -> tuple[str, ...]:
        if trigger == ReplanTrigger.DIAGNOSIS_BLOCKING:
            return (self_diagnosis.report_id,) + self_diagnosis.finding_refs
        if trigger == ReplanTrigger.FAILURE_BLOCKED:
            return failure_map.blocked_failure_ids
        if trigger == ReplanTrigger.RESOURCE_EXHAUSTED:
            return (self_diagnosis.report_id, "resource_exhausted")
        if trigger == ReplanTrigger.UNCERTAINTY_HIGH:
            return (uncertainty_report.report_id,) + uncertainty_report.uncertainty_source_refs
        if trigger == ReplanTrigger.SAFETY_MARGIN_LOW:
            return (tradeoff_report.report_id, tradeoff_report.selected_option_id)
        if trigger == ReplanTrigger.RESOURCE_PRESSURE_HIGH:
            return (self_diagnosis.report_id, "resource_pressure_high")
        return ()

    @staticmethod
    def _urgency(
        *,
        trigger: ReplanTrigger,
        uncertainty_report: UncertaintyPropagationReport,
        self_diagnosis: SelfDiagnosisReport,
        failure_map: FailureReasoningMap,
        tradeoff_report: TradeoffReasoningReport,
    ) -> float:
        if trigger == ReplanTrigger.NONE:
            return 0.0
        return max(
            0.0,
            min(
                1.0,
                max(
                    uncertainty_report.accumulated_uncertainty,
                    self_diagnosis.hallucination_risk,
                    failure_map.residual_risk,
                    1.0 - tradeoff_report.safety_margin,
                    self_diagnosis.resource_pressure,
                ),
            ),
        )


class TemporalStateEvolutionKernel:
    """Deterministic temporal ordering and state-evolution checker."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        events: Iterable[CoordinationTemporalEvent],
        generated_at: str,
        deadline_at: str | None = None,
    ) -> TemporalStateEvolutionReport:
        """Validate temporal predecessor order, delayed effects, and persistence refs."""
        ordered_events = tuple(events)
        event_ids = [event.event_id for event in ordered_events]
        if len(set(event_ids)) != len(event_ids):
            raise RuntimeCoreInvariantError("duplicate temporal event_id")
        for event in ordered_events:
            if not isinstance(event, CoordinationTemporalEvent):
                raise RuntimeCoreInvariantError("events must contain CoordinationTemporalEvent records")

        occurred_by_id = {event.event_id: self._parse_datetime(event.occurred_at, "occurred_at") for event in ordered_events}
        event_id_set = set(event_ids)
        ordered: list[str] = []
        violated: list[str] = []
        incomplete: list[str] = []
        delayed_effect_refs: list[str] = []
        persistence_refs: list[str] = []

        for event in sorted(ordered_events, key=lambda item: (item.occurred_at, item.event_id)):
            delayed_effect_refs.extend(event.delayed_effect_refs)
            persistence_refs.extend(event.persistence_refs)
            missing_predecessors = tuple(
                predecessor_id for predecessor_id in event.predecessor_event_ids if predecessor_id not in event_id_set
            )
            if missing_predecessors:
                incomplete.append(event.event_id)
                continue
            predecessor_violations = tuple(
                predecessor_id
                for predecessor_id in event.predecessor_event_ids
                if occurred_by_id[predecessor_id] > occurred_by_id[event.event_id]
            )
            if predecessor_violations:
                violated.append(event.event_id)
                continue
            ordered.append(event.event_id)

        status = self._status(violated_event_ids=violated, incomplete_event_ids=incomplete)
        return TemporalStateEvolutionReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            event_ids=tuple(event_ids),
            ordered_event_ids=tuple(ordered),
            violated_event_ids=tuple(violated),
            incomplete_event_ids=tuple(incomplete),
            delayed_effect_refs=tuple(dict.fromkeys(delayed_effect_refs)),
            persistence_refs=tuple(dict.fromkeys(persistence_refs)),
            status=status,
            deadline_pressure=self._deadline_pressure(
                events=ordered_events,
                generated_at=generated_at,
                deadline_at=deadline_at,
            ),
            generated_at=generated_at,
        )

    @staticmethod
    def _status(
        *,
        violated_event_ids: list[str],
        incomplete_event_ids: list[str],
    ) -> TemporalCheckStatus:
        if violated_event_ids:
            return TemporalCheckStatus.VIOLATED
        if incomplete_event_ids:
            return TemporalCheckStatus.INCOMPLETE
        return TemporalCheckStatus.ORDERED

    @staticmethod
    def _deadline_pressure(
        *,
        events: tuple[CoordinationTemporalEvent, ...],
        generated_at: str,
        deadline_at: str | None,
    ) -> float:
        if deadline_at is None:
            return 0.0
        generated = TemporalStateEvolutionKernel._parse_datetime(generated_at, "generated_at")
        deadline = TemporalStateEvolutionKernel._parse_datetime(deadline_at, "deadline_at")
        if generated >= deadline:
            return 1.0
        if not events:
            return 0.0
        start = min(TemporalStateEvolutionKernel._parse_datetime(event.occurred_at, "occurred_at") for event in events)
        total_seconds = (deadline - start).total_seconds()
        if total_seconds <= 0.0:
            return 1.0
        elapsed_seconds = max(0.0, (generated - start).total_seconds())
        return max(0.0, min(1.0, elapsed_seconds / total_seconds))

    @staticmethod
    def _parse_datetime(value: str, field_name: str) -> datetime:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeCoreInvariantError(f"{field_name} must be valid ISO 8601 datetime text") from exc


class CausalGraphDynamicsKernel:
    """Deterministic causal graph dynamics checker for episode-local graphs."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        nodes: Iterable[CoordinationCausalNode],
        edges: Iterable[CoordinationCausalEdge],
        generated_at: str,
    ) -> CausalGraphDynamicsReport:
        """Analyze influence flow, feedback cycles, bottlenecks, and bridges."""
        ordered_nodes = tuple(nodes)
        ordered_edges = tuple(edges)
        self._require_unique_records(ordered_nodes, ordered_edges)
        node_ids = tuple(node.node_id for node in ordered_nodes)
        node_id_set = set(node_ids)
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        incoming: dict[str, list[str]] = {node_id: [] for node_id in node_ids}

        for edge in ordered_edges:
            if not isinstance(edge, CoordinationCausalEdge):
                raise RuntimeCoreInvariantError("edges must contain CoordinationCausalEdge records")
            if edge.cause_node_id not in node_id_set or edge.effect_node_id not in node_id_set:
                raise RuntimeCoreInvariantError("causal edge endpoints must reference known nodes")
            adjacency[edge.cause_node_id].append(edge.effect_node_id)
            incoming[edge.effect_node_id].append(edge.cause_node_id)

        feedback_edge_ids = tuple(
            edge.edge_id
            for edge in ordered_edges
            if self._has_path(adjacency, start=edge.effect_node_id, target=edge.cause_node_id)
        )
        feedback_cycle_node_ids = tuple(
            node_id
            for node_id in node_ids
            if self._has_path(adjacency, start=node_id, target=node_id, require_traversal=True)
        )
        bottleneck_node_ids = tuple(
            node_id
            for node_id in node_ids
            if len(adjacency[node_id]) >= 2 or len(incoming[node_id]) >= 2
        )
        bridge_node_ids = tuple(
            node_id
            for node_id in node_ids
            if adjacency[node_id] and incoming[node_id]
        )
        orphan_node_ids = tuple(
            node_id
            for node_id in node_ids
            if not adjacency[node_id] and not incoming[node_id]
        )
        protected_node_ids = tuple(node.node_id for node in ordered_nodes if node.protected)
        status = self._status(
            feedback_cycle_node_ids=feedback_cycle_node_ids,
            orphan_node_ids=orphan_node_ids,
        )
        return CausalGraphDynamicsReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            node_ids=node_ids,
            edge_ids=tuple(edge.edge_id for edge in ordered_edges),
            feedback_cycle_node_ids=feedback_cycle_node_ids,
            feedback_edge_ids=feedback_edge_ids,
            bottleneck_node_ids=bottleneck_node_ids,
            bridge_node_ids=bridge_node_ids,
            orphan_node_ids=orphan_node_ids,
            protected_node_ids=protected_node_ids,
            status=status,
            structural_fragility=self._structural_fragility(
                node_count=len(node_ids),
                feedback_cycle_count=len(feedback_cycle_node_ids),
                bottleneck_count=len(bottleneck_node_ids),
                bridge_count=len(bridge_node_ids),
                protected_cycle_count=len(set(protected_node_ids) & set(feedback_cycle_node_ids)),
            ),
            generated_at=generated_at,
        )

    @staticmethod
    def _require_unique_records(
        nodes: tuple[CoordinationCausalNode, ...],
        edges: tuple[CoordinationCausalEdge, ...],
    ) -> None:
        node_ids: list[str] = []
        for node in nodes:
            if not isinstance(node, CoordinationCausalNode):
                raise RuntimeCoreInvariantError("nodes must contain CoordinationCausalNode records")
            node_ids.append(node.node_id)
        if len(set(node_ids)) != len(node_ids):
            raise RuntimeCoreInvariantError("duplicate causal node_id")
        edge_ids = [edge.edge_id for edge in edges if isinstance(edge, CoordinationCausalEdge)]
        if len(edge_ids) != len(edges):
            raise RuntimeCoreInvariantError("edges must contain CoordinationCausalEdge records")
        if len(set(edge_ids)) != len(edge_ids):
            raise RuntimeCoreInvariantError("duplicate causal edge_id")

    @staticmethod
    def _has_path(
        adjacency: Mapping[str, list[str]],
        *,
        start: str,
        target: str,
        require_traversal: bool = False,
    ) -> bool:
        stack = list(adjacency.get(start, ()))
        visited: set[str] = set()
        if not require_traversal and start == target:
            return True
        while stack:
            node_id = stack.pop()
            if node_id == target:
                return True
            if node_id in visited:
                continue
            visited.add(node_id)
            stack.extend(adjacency.get(node_id, ()))
        return False

    @staticmethod
    def _status(
        *,
        feedback_cycle_node_ids: tuple[str, ...],
        orphan_node_ids: tuple[str, ...],
    ) -> CausalDynamicsStatus:
        if feedback_cycle_node_ids:
            return CausalDynamicsStatus.FEEDBACK_PRESENT
        if orphan_node_ids:
            return CausalDynamicsStatus.DISCONNECTED
        return CausalDynamicsStatus.ACYCLIC

    @staticmethod
    def _structural_fragility(
        *,
        node_count: int,
        feedback_cycle_count: int,
        bottleneck_count: int,
        bridge_count: int,
        protected_cycle_count: int,
    ) -> float:
        if node_count <= 0:
            return 0.0
        weighted_exposure = (
            feedback_cycle_count * 1.0
            + bottleneck_count * 0.5
            + bridge_count * 0.25
            + protected_cycle_count * 1.0
        )
        return max(0.0, min(1.0, weighted_exposure / node_count))


class AbstractionControlKernel:
    """Deterministic checker for micro, meso, and macro abstraction coverage."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        layers: Iterable[CoordinationAbstractionLayer],
        generated_at: str,
    ) -> AbstractionControlReport:
        """Evaluate scale coverage, parent validity, and boundary collapse."""
        ordered_layers = tuple(layers)
        self._require_unique_layers(ordered_layers)
        if not ordered_layers:
            return AbstractionControlReport(
                report_id=report_id,
                source_episode_id=source_episode_id,
                layer_ids=(),
                micro_layer_ids=(),
                meso_layer_ids=(),
                macro_layer_ids=(),
                missing_scale_refs=(),
                collapsed_layer_ids=(),
                orphan_layer_ids=(),
                status=AbstractionControlStatus.CONSISTENT,
                scale_coverage=1.0,
                compression_ratio=0.0,
                generated_at=generated_at,
            )
        layer_ids = tuple(layer.layer_id for layer in ordered_layers)
        layer_by_id = {layer.layer_id: layer for layer in ordered_layers}
        micro_layer_ids = tuple(layer.layer_id for layer in ordered_layers if layer.scale == AbstractionScale.MICRO)
        meso_layer_ids = tuple(layer.layer_id for layer in ordered_layers if layer.scale == AbstractionScale.MESO)
        macro_layer_ids = tuple(layer.layer_id for layer in ordered_layers if layer.scale == AbstractionScale.MACRO)
        missing_scale_refs = tuple(
            scale.value
            for scale, ids in (
                (AbstractionScale.MICRO, micro_layer_ids),
                (AbstractionScale.MESO, meso_layer_ids),
                (AbstractionScale.MACRO, macro_layer_ids),
            )
            if not ids
        )
        collapsed_layer_ids: list[str] = []
        orphan_layer_ids: list[str] = []
        for layer in ordered_layers:
            missing_parents = tuple(parent_id for parent_id in layer.parent_layer_ids if parent_id not in layer_by_id)
            if missing_parents:
                orphan_layer_ids.append(layer.layer_id)
                continue
            if any(layer_by_id[parent_id].scale == layer.scale for parent_id in layer.parent_layer_ids):
                collapsed_layer_ids.append(layer.layer_id)

        status = self._status(
            collapsed_layer_ids=tuple(collapsed_layer_ids),
            missing_scale_refs=missing_scale_refs,
            orphan_layer_ids=tuple(orphan_layer_ids),
        )
        return AbstractionControlReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            layer_ids=layer_ids,
            micro_layer_ids=micro_layer_ids,
            meso_layer_ids=meso_layer_ids,
            macro_layer_ids=macro_layer_ids,
            missing_scale_refs=missing_scale_refs,
            collapsed_layer_ids=tuple(collapsed_layer_ids),
            orphan_layer_ids=tuple(orphan_layer_ids),
            status=status,
            scale_coverage=(3.0 - float(len(missing_scale_refs))) / 3.0,
            compression_ratio=self._compression_ratio(ordered_layers),
            generated_at=generated_at,
        )

    @staticmethod
    def _require_unique_layers(layers: tuple[CoordinationAbstractionLayer, ...]) -> None:
        layer_ids: list[str] = []
        for layer in layers:
            if not isinstance(layer, CoordinationAbstractionLayer):
                raise RuntimeCoreInvariantError("layers must contain CoordinationAbstractionLayer records")
            layer_ids.append(layer.layer_id)
        if len(set(layer_ids)) != len(layer_ids):
            raise RuntimeCoreInvariantError("duplicate abstraction layer_id")

    @staticmethod
    def _status(
        *,
        collapsed_layer_ids: tuple[str, ...],
        missing_scale_refs: tuple[str, ...],
        orphan_layer_ids: tuple[str, ...],
    ) -> AbstractionControlStatus:
        if collapsed_layer_ids:
            return AbstractionControlStatus.COLLAPSED
        if missing_scale_refs or orphan_layer_ids:
            return AbstractionControlStatus.GAP_PRESENT
        return AbstractionControlStatus.CONSISTENT

    @staticmethod
    def _compression_ratio(layers: tuple[CoordinationAbstractionLayer, ...]) -> float:
        symbol_count = sum(len(layer.symbol_refs) for layer in layers)
        if symbol_count == 0:
            return 0.0
        unique_symbol_count = len({symbol_ref for layer in layers for symbol_ref in layer.symbol_refs})
        return max(0.0, min(1.0, 1.0 - (unique_symbol_count / symbol_count)))


class ResourceBoundedControlKernel:
    """Deterministic checker for resource-bounded coordination limits."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        limits: Iterable[CoordinationResourceLimit],
        generated_at: str,
        degradation_threshold: float = 0.8,
    ) -> ResourceBoundedControlReport:
        """Classify resource usage as normal, degraded, exhausted, or overrun."""
        if degradation_threshold < 0.0 or degradation_threshold > 1.0:
            raise RuntimeCoreInvariantError("degradation_threshold must be within [0.0, 1.0]")
        ordered_limits = tuple(limits)
        self._require_unique_limits(ordered_limits)
        degraded: list[str] = []
        exhausted: list[str] = []
        overrun: list[str] = []
        hard_block: list[str] = []
        max_pressure = 0.0
        for limit in ordered_limits:
            pressure = self._pressure(limit)
            max_pressure = max(max_pressure, pressure)
            if limit.budget == 0.0 and limit.used > 0.0:
                overrun.append(limit.limit_id)
            elif limit.budget > 0.0 and limit.used > limit.budget:
                overrun.append(limit.limit_id)
            elif limit.budget > 0.0 and limit.used == limit.budget:
                exhausted.append(limit.limit_id)
            elif pressure >= degradation_threshold:
                degraded.append(limit.limit_id)
            if limit.hard_limit and (limit.limit_id in exhausted or limit.limit_id in overrun):
                hard_block.append(limit.limit_id)

        return ResourceBoundedControlReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            limit_ids=tuple(limit.limit_id for limit in ordered_limits),
            degraded_limit_ids=tuple(degraded),
            exhausted_limit_ids=tuple(exhausted),
            overrun_limit_ids=tuple(overrun),
            hard_block_limit_ids=tuple(hard_block),
            status=self._status(exhausted_limit_ids=tuple(exhausted), overrun_limit_ids=tuple(overrun), degraded_limit_ids=tuple(degraded)),
            max_pressure=max_pressure,
            generated_at=generated_at,
        )

    @staticmethod
    def _require_unique_limits(limits: tuple[CoordinationResourceLimit, ...]) -> None:
        limit_ids: list[str] = []
        for limit in limits:
            if not isinstance(limit, CoordinationResourceLimit):
                raise RuntimeCoreInvariantError("limits must contain CoordinationResourceLimit records")
            limit_ids.append(limit.limit_id)
        if len(set(limit_ids)) != len(limit_ids):
            raise RuntimeCoreInvariantError("duplicate resource limit_id")

    @staticmethod
    def _pressure(limit: CoordinationResourceLimit) -> float:
        if limit.budget == 0.0:
            return 1.0 if limit.used > 0.0 else 0.0
        return max(0.0, min(1.0, limit.used / limit.budget))

    @staticmethod
    def _status(
        *,
        exhausted_limit_ids: tuple[str, ...],
        overrun_limit_ids: tuple[str, ...],
        degraded_limit_ids: tuple[str, ...],
    ) -> ResourceBoundStatus:
        if overrun_limit_ids:
            return ResourceBoundStatus.OVERRUN
        if exhausted_limit_ids:
            return ResourceBoundStatus.EXHAUSTED
        if degraded_limit_ids:
            return ResourceBoundStatus.DEGRADED
        return ResourceBoundStatus.NORMAL


class SemanticGroundingKernel:
    """Deterministic checker for symbol grounding claims."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        claims: Iterable[CoordinationGroundingClaim],
        generated_at: str,
        expected_symbol_refs: Iterable[str] = (),
        confidence_floor: float = 0.5,
    ) -> SemanticGroundingReport:
        """Validate observable, executable, or measurable symbol bindings."""
        if confidence_floor < 0.0 or confidence_floor > 1.0:
            raise RuntimeCoreInvariantError("confidence_floor must be within [0.0, 1.0]")
        ordered_claims = tuple(claims)
        self._require_unique_claims(ordered_claims)
        expected_symbols = _unique_text_tuple(expected_symbol_refs, "expected_symbol_refs")
        grounded_claim_ids = tuple(claim.claim_id for claim in ordered_claims if claim.confidence >= confidence_floor)
        weak_claim_ids = tuple(claim.claim_id for claim in ordered_claims if claim.confidence < confidence_floor)
        grounded_symbols = {claim.symbol_ref for claim in ordered_claims if claim.confidence >= confidence_floor}
        claimed_symbols = {claim.symbol_ref for claim in ordered_claims}
        missing_symbol_refs = tuple(symbol_ref for symbol_ref in expected_symbols if symbol_ref not in claimed_symbols)
        grounding_coverage = self._coverage(
            expected_symbols=expected_symbols,
            grounded_symbols=grounded_symbols,
            claim_count=len(ordered_claims),
            grounded_claim_count=len(grounded_claim_ids),
        )
        status = self._status(
            claim_count=len(ordered_claims),
            weak_claim_ids=weak_claim_ids,
            missing_symbol_refs=missing_symbol_refs,
            grounding_coverage=grounding_coverage,
        )
        return SemanticGroundingReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            claim_ids=tuple(claim.claim_id for claim in ordered_claims),
            grounded_claim_ids=grounded_claim_ids,
            weak_claim_ids=weak_claim_ids,
            missing_symbol_refs=missing_symbol_refs,
            status=status,
            grounding_coverage=grounding_coverage,
            min_confidence=min((claim.confidence for claim in ordered_claims), default=1.0),
            generated_at=generated_at,
        )

    @staticmethod
    def _require_unique_claims(claims: tuple[CoordinationGroundingClaim, ...]) -> None:
        claim_ids: list[str] = []
        for claim in claims:
            if not isinstance(claim, CoordinationGroundingClaim):
                raise RuntimeCoreInvariantError("claims must contain CoordinationGroundingClaim records")
            claim_ids.append(claim.claim_id)
        if len(set(claim_ids)) != len(claim_ids):
            raise RuntimeCoreInvariantError("duplicate grounding claim_id")

    @staticmethod
    def _coverage(
        *,
        expected_symbols: tuple[str, ...],
        grounded_symbols: set[str],
        claim_count: int,
        grounded_claim_count: int,
    ) -> float:
        if expected_symbols:
            return len(set(expected_symbols) & grounded_symbols) / len(expected_symbols)
        if claim_count == 0:
            return 1.0
        return grounded_claim_count / claim_count

    @staticmethod
    def _status(
        *,
        claim_count: int,
        weak_claim_ids: tuple[str, ...],
        missing_symbol_refs: tuple[str, ...],
        grounding_coverage: float,
    ) -> SemanticGroundingStatus:
        if claim_count == 0 and missing_symbol_refs:
            return SemanticGroundingStatus.UNGROUNDED
        if grounding_coverage == 0.0 and (weak_claim_ids or missing_symbol_refs):
            return SemanticGroundingStatus.UNGROUNDED
        if weak_claim_ids or missing_symbol_refs or grounding_coverage < 1.0:
            return SemanticGroundingStatus.PARTIAL
        return SemanticGroundingStatus.GROUNDED


class MultiPerspectiveReasoningKernel:
    """Deterministic comparison of assumptions, incentives, scales, and models."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        perspectives: Iterable[CoordinationPerspective],
        generated_at: str,
        required_kinds: Iterable[PerspectiveKind] = (),
        confidence_floor: float = 0.5,
    ) -> MultiPerspectiveReasoningReport:
        """Compare perspective coverage and conclusion agreement."""
        if confidence_floor < 0.0 or confidence_floor > 1.0:
            raise RuntimeCoreInvariantError("confidence_floor must be within [0.0, 1.0]")
        ordered_perspectives = tuple(perspectives)
        self._require_unique_perspectives(ordered_perspectives)
        ordered_required_kinds = tuple(required_kinds) or (
            PerspectiveKind.MODEL,
            PerspectiveKind.ASSUMPTION,
            PerspectiveKind.INCENTIVE,
            PerspectiveKind.SCALE,
        )
        for kind in ordered_required_kinds:
            if not isinstance(kind, PerspectiveKind):
                raise RuntimeCoreInvariantError("required_kinds must contain PerspectiveKind values")
        represented_kinds = tuple(dict.fromkeys(perspective.kind.value for perspective in ordered_perspectives))
        missing_kind_refs = tuple(kind.value for kind in ordered_required_kinds if kind.value not in represented_kinds)
        low_confidence_ids = tuple(
            perspective.perspective_id for perspective in ordered_perspectives if perspective.confidence < confidence_floor
        )
        shared_conclusions = self._shared_conclusions(ordered_perspectives)
        divergent_ids = self._divergent_perspective_ids(
            perspectives=ordered_perspectives,
            shared_conclusions=shared_conclusions,
        )
        agreement_score = self._agreement_score(
            perspectives=ordered_perspectives,
            shared_conclusions=shared_conclusions,
        )
        status = self._status(
            missing_kind_refs=missing_kind_refs,
            divergent_perspective_ids=divergent_ids,
            low_confidence_perspective_ids=low_confidence_ids,
        )
        return MultiPerspectiveReasoningReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            perspective_ids=tuple(perspective.perspective_id for perspective in ordered_perspectives),
            represented_kind_refs=represented_kinds,
            missing_kind_refs=missing_kind_refs,
            divergent_perspective_ids=divergent_ids,
            low_confidence_perspective_ids=low_confidence_ids,
            shared_conclusion_refs=shared_conclusions,
            status=status,
            agreement_score=agreement_score,
            generated_at=generated_at,
        )

    @staticmethod
    def _require_unique_perspectives(perspectives: tuple[CoordinationPerspective, ...]) -> None:
        perspective_ids: list[str] = []
        for perspective in perspectives:
            if not isinstance(perspective, CoordinationPerspective):
                raise RuntimeCoreInvariantError("perspectives must contain CoordinationPerspective records")
            perspective_ids.append(perspective.perspective_id)
        if len(set(perspective_ids)) != len(perspective_ids):
            raise RuntimeCoreInvariantError("duplicate perspective_id")

    @staticmethod
    def _shared_conclusions(perspectives: tuple[CoordinationPerspective, ...]) -> tuple[str, ...]:
        if not perspectives:
            return ()
        shared = set(perspectives[0].conclusion_refs)
        for perspective in perspectives[1:]:
            shared &= set(perspective.conclusion_refs)
        return tuple(conclusion for conclusion in perspectives[0].conclusion_refs if conclusion in shared)

    @staticmethod
    def _divergent_perspective_ids(
        *,
        perspectives: tuple[CoordinationPerspective, ...],
        shared_conclusions: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(perspectives) < 2:
            return ()
        if shared_conclusions:
            return ()
        return tuple(perspective.perspective_id for perspective in perspectives)

    @staticmethod
    def _agreement_score(
        *,
        perspectives: tuple[CoordinationPerspective, ...],
        shared_conclusions: tuple[str, ...],
    ) -> float:
        if not perspectives:
            return 1.0
        total_conclusion_count = sum(len(perspective.conclusion_refs) for perspective in perspectives)
        if total_conclusion_count == 0:
            return 0.0
        return max(0.0, min(1.0, (len(shared_conclusions) * len(perspectives)) / total_conclusion_count))

    @staticmethod
    def _status(
        *,
        missing_kind_refs: tuple[str, ...],
        divergent_perspective_ids: tuple[str, ...],
        low_confidence_perspective_ids: tuple[str, ...],
    ) -> PerspectiveComparisonStatus:
        if divergent_perspective_ids:
            return PerspectiveComparisonStatus.DIVERGENT
        if missing_kind_refs or low_confidence_perspective_ids:
            return PerspectiveComparisonStatus.UNDERCOVERED
        return PerspectiveComparisonStatus.ALIGNED


class CompressionPatternDiscoveryKernel:
    """Deterministic pattern discovery and compression checker."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        patterns: Iterable[CoordinationPatternCandidate],
        generated_at: str,
        expected_symbol_refs: Iterable[str] = (),
    ) -> CompressionPatternDiscoveryReport:
        """Extract reusable invariants, motifs, and redundancy from pattern candidates."""
        ordered_patterns = tuple(patterns)
        self._require_unique_patterns(ordered_patterns)
        expected_symbols = _unique_text_tuple(expected_symbol_refs, "expected_symbol_refs")
        invariant_refs = self._unique_refs(pattern.invariant_refs for pattern in ordered_patterns)
        motif_refs = self._unique_refs(pattern.motif_refs for pattern in ordered_patterns)
        reusable_structure_refs = self._unique_refs(pattern.reusable_structure_refs for pattern in ordered_patterns)
        redundant_symbol_refs = self._redundant_symbol_refs(ordered_patterns)
        compression_ratio = self._compression_ratio(
            expected_symbol_refs=expected_symbols,
            patterns=ordered_patterns,
            redundant_symbol_refs=redundant_symbol_refs,
        )
        reuse_score = self._reuse_score(
            pattern_count=len(ordered_patterns),
            reusable_structure_count=len(reusable_structure_refs),
        )
        status = self._status(
            pattern_count=len(ordered_patterns),
            redundant_symbol_refs=redundant_symbol_refs,
            compression_ratio=compression_ratio,
            reuse_score=reuse_score,
        )
        return CompressionPatternDiscoveryReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            pattern_ids=tuple(pattern.pattern_id for pattern in ordered_patterns),
            invariant_refs=invariant_refs,
            motif_refs=motif_refs,
            reusable_structure_refs=reusable_structure_refs,
            redundant_symbol_refs=redundant_symbol_refs,
            status=status,
            compression_ratio=compression_ratio,
            reuse_score=reuse_score,
            generated_at=generated_at,
        )

    @staticmethod
    def _require_unique_patterns(patterns: tuple[CoordinationPatternCandidate, ...]) -> None:
        pattern_ids: list[str] = []
        for pattern in patterns:
            if not isinstance(pattern, CoordinationPatternCandidate):
                raise RuntimeCoreInvariantError("patterns must contain CoordinationPatternCandidate records")
            pattern_ids.append(pattern.pattern_id)
        if len(set(pattern_ids)) != len(pattern_ids):
            raise RuntimeCoreInvariantError("duplicate pattern_id")

    @staticmethod
    def _unique_refs(ref_groups: Iterable[tuple[str, ...]]) -> tuple[str, ...]:
        refs: list[str] = []
        for group in ref_groups:
            refs.extend(group)
        return tuple(dict.fromkeys(refs))

    @staticmethod
    def _redundant_symbol_refs(patterns: tuple[CoordinationPatternCandidate, ...]) -> tuple[str, ...]:
        explicit_redundancy = tuple(dict.fromkeys(ref for pattern in patterns for ref in pattern.redundancy_refs))
        symbol_counts: dict[str, int] = {}
        for pattern in patterns:
            for symbol_ref in pattern.symbol_refs:
                symbol_counts[symbol_ref] = symbol_counts.get(symbol_ref, 0) + 1
        repeated_symbols = tuple(symbol_ref for symbol_ref, count in symbol_counts.items() if count > 1)
        return tuple(dict.fromkeys(explicit_redundancy + repeated_symbols))

    @staticmethod
    def _compression_ratio(
        *,
        expected_symbol_refs: tuple[str, ...],
        patterns: tuple[CoordinationPatternCandidate, ...],
        redundant_symbol_refs: tuple[str, ...],
    ) -> float:
        symbol_refs = tuple(dict.fromkeys(ref for pattern in patterns for ref in pattern.symbol_refs))
        denominator = len(expected_symbol_refs) if expected_symbol_refs else len(symbol_refs)
        if denominator == 0:
            return 1.0
        compressed_count = len(redundant_symbol_refs) + sum(1 for pattern in patterns if pattern.invariant_refs or pattern.motif_refs)
        return max(0.0, min(1.0, compressed_count / denominator))

    @staticmethod
    def _reuse_score(*, pattern_count: int, reusable_structure_count: int) -> float:
        if pattern_count == 0:
            return 1.0
        return max(0.0, min(1.0, reusable_structure_count / pattern_count))

    @staticmethod
    def _status(
        *,
        pattern_count: int,
        redundant_symbol_refs: tuple[str, ...],
        compression_ratio: float,
        reuse_score: float,
    ) -> PatternDiscoveryStatus:
        if pattern_count == 0 or (compression_ratio < 0.25 and reuse_score < 0.5):
            return PatternDiscoveryStatus.UNDERCOMPRESSED
        if redundant_symbol_refs:
            return PatternDiscoveryStatus.REDUNDANT
        return PatternDiscoveryStatus.STABLE


class CorrectionRepairKernel:
    """Deterministic correction and rollback recommendation kernel."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        failure_map: FailureReasoningMap,
        generated_at: str,
        contradictions_created: Iterable[str] = (),
        contradictions_resolved: Iterable[str] = (),
    ) -> CorrectionRepairReport:
        """Create post-episode repair actions from contradictions and failures."""
        if not isinstance(failure_map, FailureReasoningMap):
            raise RuntimeCoreInvariantError("failure_map must be a FailureReasoningMap")
        created = _unique_text_tuple(contradictions_created, "contradictions_created")
        resolved = _unique_text_tuple(contradictions_resolved, "contradictions_resolved")
        actions: list[CorrectionRepairAction] = []
        unresolved_contradictions = tuple(ref for ref in created if ref not in set(resolved))
        for contradiction_ref in unresolved_contradictions:
            actions.append(
                CorrectionRepairAction(
                    action_id=f"{report_id}:repair:{contradiction_ref}",
                    kind=CorrectionActionKind.CONTRADICTION_REPAIR,
                    target_ref=contradiction_ref,
                    reason_refs=(contradiction_ref,),
                    reversible=True,
                )
            )
        for failure_id in failure_map.blocked_failure_ids:
            actions.append(
                CorrectionRepairAction(
                    action_id=f"{report_id}:rollback:{failure_id}",
                    kind=CorrectionActionKind.ROLLBACK,
                    target_ref=failure_id,
                    reason_refs=(failure_id,),
                    reversible=True,
                )
            )
        if failure_map.dominant_failure_id is not None and not failure_map.blocked_failure_ids:
            actions.append(
                CorrectionRepairAction(
                    action_id=f"{report_id}:evidence:{failure_map.dominant_failure_id}",
                    kind=CorrectionActionKind.EVIDENCE_REQUEST,
                    target_ref=failure_map.dominant_failure_id,
                    reason_refs=(failure_map.dominant_failure_id,),
                    reversible=True,
                )
            )
        action_ids = tuple(action.action_id for action in actions)
        rollback_action_ids = tuple(action.action_id for action in actions if action.kind == CorrectionActionKind.ROLLBACK)
        repair_action_ids = tuple(
            action.action_id for action in actions if action.kind == CorrectionActionKind.CONTRADICTION_REPAIR
        )
        evidence_action_ids = tuple(
            action.action_id for action in actions if action.kind == CorrectionActionKind.EVIDENCE_REQUEST
        )
        return CorrectionRepairReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            action_ids=action_ids,
            contradiction_refs=unresolved_contradictions,
            rollback_action_ids=rollback_action_ids,
            repair_action_ids=repair_action_ids,
            evidence_request_action_ids=evidence_action_ids,
            status=self._status(rollback_action_ids=rollback_action_ids, repair_action_ids=repair_action_ids),
            repair_pressure=self._repair_pressure(
                action_count=len(actions),
                rollback_count=len(rollback_action_ids),
                failure_risk=failure_map.residual_risk,
            ),
            generated_at=generated_at,
        )

    @staticmethod
    def _status(
        *,
        rollback_action_ids: tuple[str, ...],
        repair_action_ids: tuple[str, ...],
    ) -> CorrectionRepairStatus:
        if rollback_action_ids:
            return CorrectionRepairStatus.ROLLBACK_RECOMMENDED
        if repair_action_ids:
            return CorrectionRepairStatus.REPAIR_RECOMMENDED
        return CorrectionRepairStatus.CLEAN

    @staticmethod
    def _repair_pressure(*, action_count: int, rollback_count: int, failure_risk: float) -> float:
        if action_count == 0:
            return max(0.0, min(1.0, failure_risk))
        return max(0.0, min(1.0, failure_risk + (0.15 * action_count) + (0.25 * rollback_count)))


class DynamicWorldModelContinuityKernel:
    """Deterministic world-model lineage and identity continuity checker."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        lineage_links: Iterable[WorldSnapshotLineageLink],
        identity_checks: Iterable[WorldIdentityContinuityCheck],
        generated_at: str,
        expected_snapshot_ref: str | None = None,
        persistent_causal_chain_refs: Iterable[str] = (),
    ) -> DynamicWorldModelContinuityReport:
        """Evaluate snapshot lineage, identity preservation, and causal persistence."""
        ordered_links = tuple(lineage_links)
        ordered_checks = tuple(identity_checks)
        self._require_unique_links(ordered_links)
        self._require_unique_checks(ordered_checks)
        persistent_refs = _unique_text_tuple(persistent_causal_chain_refs, "persistent_causal_chain_refs")
        broken_links = self._broken_lineage_links(
            links=ordered_links,
            expected_snapshot_ref=expected_snapshot_ref,
        )
        drifted_checks = tuple(check.check_id for check in ordered_checks if not check.preserved)
        status = self._status(broken_lineage_link_ids=broken_links, drifted_identity_check_ids=drifted_checks)
        continuity_score = self._continuity_score(
            link_count=len(ordered_links),
            check_count=len(ordered_checks),
            broken_count=len(broken_links),
            drifted_count=len(drifted_checks),
        )
        return DynamicWorldModelContinuityReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            lineage_link_ids=tuple(link.link_id for link in ordered_links),
            identity_check_ids=tuple(check.check_id for check in ordered_checks),
            broken_lineage_link_ids=broken_links,
            drifted_identity_check_ids=drifted_checks,
            persistent_causal_chain_refs=persistent_refs,
            status=status,
            continuity_score=continuity_score,
            generated_at=generated_at,
        )

    @staticmethod
    def _require_unique_links(links: tuple[WorldSnapshotLineageLink, ...]) -> None:
        link_ids: list[str] = []
        for link in links:
            if not isinstance(link, WorldSnapshotLineageLink):
                raise RuntimeCoreInvariantError("lineage_links must contain WorldSnapshotLineageLink records")
            link_ids.append(link.link_id)
        if len(set(link_ids)) != len(link_ids):
            raise RuntimeCoreInvariantError("duplicate lineage link_id")

    @staticmethod
    def _require_unique_checks(checks: tuple[WorldIdentityContinuityCheck, ...]) -> None:
        check_ids: list[str] = []
        for check in checks:
            if not isinstance(check, WorldIdentityContinuityCheck):
                raise RuntimeCoreInvariantError("identity_checks must contain WorldIdentityContinuityCheck records")
            check_ids.append(check.check_id)
        if len(set(check_ids)) != len(check_ids):
            raise RuntimeCoreInvariantError("duplicate identity check_id")

    @staticmethod
    def _broken_lineage_links(
        *,
        links: tuple[WorldSnapshotLineageLink, ...],
        expected_snapshot_ref: str | None,
    ) -> tuple[str, ...]:
        if not links:
            return ()
        broken: list[str] = []
        if expected_snapshot_ref is not None and links[0].prior_snapshot_ref != expected_snapshot_ref:
            broken.append(links[0].link_id)
        previous_next = links[0].next_snapshot_ref
        for link in links[1:]:
            if link.prior_snapshot_ref != previous_next:
                broken.append(link.link_id)
            previous_next = link.next_snapshot_ref
        return tuple(dict.fromkeys(broken))

    @staticmethod
    def _status(
        *,
        broken_lineage_link_ids: tuple[str, ...],
        drifted_identity_check_ids: tuple[str, ...],
    ) -> WorldContinuityStatus:
        if drifted_identity_check_ids:
            return WorldContinuityStatus.IDENTITY_DRIFT
        if broken_lineage_link_ids:
            return WorldContinuityStatus.FRAGMENTED
        return WorldContinuityStatus.CONTINUOUS

    @staticmethod
    def _continuity_score(*, link_count: int, check_count: int, broken_count: int, drifted_count: int) -> float:
        total = link_count + check_count
        if total == 0:
            return 1.0
        intact = max(0, total - broken_count - drifted_count)
        return max(0.0, min(1.0, intact / total))


class OrchestrationReadinessKernel:
    """Deterministic aggregate readiness checker before execution."""

    def evaluate(
        self,
        *,
        report_id: str,
        source_episode_id: str,
        terminal_outcome: SolverTerminalOutcome,
        constraint_report: ConstraintSatisfiabilityReport,
        method_arbitration: MethodArbitrationProof,
        failure_map: FailureReasoningMap,
        tradeoff_report: TradeoffReasoningReport,
        uncertainty_report: UncertaintyPropagationReport,
        self_diagnosis: SelfDiagnosisReport,
        replan_recommendation: AdaptiveReplanRecommendation,
        temporal_report: TemporalStateEvolutionReport,
        resource_report: ResourceBoundedControlReport,
        grounding_report: SemanticGroundingReport,
        correction_report: CorrectionRepairReport,
        continuity_report: DynamicWorldModelContinuityReport,
        generated_at: str,
    ) -> OrchestrationReadinessReport:
        """Aggregate hard blockers, replan refs, and soft risks into one verdict."""
        self._validate_inputs(
            terminal_outcome=terminal_outcome,
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            uncertainty_report=uncertainty_report,
            self_diagnosis=self_diagnosis,
            replan_recommendation=replan_recommendation,
            temporal_report=temporal_report,
            resource_report=resource_report,
            grounding_report=grounding_report,
            correction_report=correction_report,
            continuity_report=continuity_report,
        )
        hard_block_refs = self._hard_block_refs(
            terminal_outcome=terminal_outcome,
            constraint_report=constraint_report,
            failure_map=failure_map,
            temporal_report=temporal_report,
            resource_report=resource_report,
        )
        replan_refs = replan_recommendation.reason_refs if replan_recommendation.replan_required else ()
        soft_risk_refs = tuple(
            dict.fromkeys(
                uncertainty_report.uncertainty_source_refs
                + self_diagnosis.finding_refs
                + correction_report.repair_action_ids
                + continuity_report.broken_lineage_link_ids
            )
        )
        verdict = self._verdict(hard_block_refs=hard_block_refs, replan_refs=replan_refs)
        return OrchestrationReadinessReport(
            report_id=report_id,
            source_episode_id=source_episode_id,
            report_refs=(
                constraint_report.report_id,
                method_arbitration.proof_id,
                failure_map.map_id,
                tradeoff_report.report_id,
                uncertainty_report.report_id,
                self_diagnosis.report_id,
                replan_recommendation.recommendation_id,
                temporal_report.report_id,
                resource_report.report_id,
                grounding_report.report_id,
                correction_report.report_id,
                continuity_report.report_id,
            ),
            hard_block_refs=hard_block_refs,
            replan_refs=replan_refs,
            soft_risk_refs=soft_risk_refs,
            verdict=verdict,
            readiness_score=self._readiness_score(
                verdict=verdict,
                uncertainty=uncertainty_report.accumulated_uncertainty,
                hallucination_risk=self_diagnosis.hallucination_risk,
                soft_risk_count=len(soft_risk_refs),
            ),
            generated_at=generated_at,
        )

    @staticmethod
    def _validate_inputs(
        *,
        terminal_outcome: SolverTerminalOutcome,
        constraint_report: ConstraintSatisfiabilityReport,
        method_arbitration: MethodArbitrationProof,
        failure_map: FailureReasoningMap,
        tradeoff_report: TradeoffReasoningReport,
        uncertainty_report: UncertaintyPropagationReport,
        self_diagnosis: SelfDiagnosisReport,
        replan_recommendation: AdaptiveReplanRecommendation,
        temporal_report: TemporalStateEvolutionReport,
        resource_report: ResourceBoundedControlReport,
        grounding_report: SemanticGroundingReport,
        correction_report: CorrectionRepairReport,
        continuity_report: DynamicWorldModelContinuityReport,
    ) -> None:
        expected_types: tuple[tuple[object, type[object], str], ...] = (
            (constraint_report, ConstraintSatisfiabilityReport, "constraint_report"),
            (method_arbitration, MethodArbitrationProof, "method_arbitration"),
            (failure_map, FailureReasoningMap, "failure_map"),
            (tradeoff_report, TradeoffReasoningReport, "tradeoff_report"),
            (uncertainty_report, UncertaintyPropagationReport, "uncertainty_report"),
            (self_diagnosis, SelfDiagnosisReport, "self_diagnosis"),
            (replan_recommendation, AdaptiveReplanRecommendation, "replan_recommendation"),
            (temporal_report, TemporalStateEvolutionReport, "temporal_report"),
            (resource_report, ResourceBoundedControlReport, "resource_report"),
            (grounding_report, SemanticGroundingReport, "grounding_report"),
            (correction_report, CorrectionRepairReport, "correction_report"),
            (continuity_report, DynamicWorldModelContinuityReport, "continuity_report"),
        )
        if not isinstance(terminal_outcome, SolverTerminalOutcome):
            raise RuntimeCoreInvariantError("terminal_outcome must be a SolverTerminalOutcome")
        for value, expected_type, field_name in expected_types:
            if not isinstance(value, expected_type):
                raise RuntimeCoreInvariantError(f"{field_name} must be a {expected_type.__name__}")

    @staticmethod
    def _hard_block_refs(
        *,
        terminal_outcome: SolverTerminalOutcome,
        constraint_report: ConstraintSatisfiabilityReport,
        failure_map: FailureReasoningMap,
        temporal_report: TemporalStateEvolutionReport,
        resource_report: ResourceBoundedControlReport,
    ) -> tuple[str, ...]:
        if terminal_outcome == SolverTerminalOutcome.SOLVED_UNVERIFIED:
            return ()
        return tuple(
            dict.fromkeys(
                constraint_report.blocked_branch_ids
                + failure_map.blocked_failure_ids
                + temporal_report.violated_event_ids
                + resource_report.hard_block_limit_ids
                + (terminal_outcome.value,)
            )
        )

    @staticmethod
    def _verdict(*, hard_block_refs: tuple[str, ...], replan_refs: tuple[str, ...]) -> OrchestrationReadinessVerdict:
        if hard_block_refs:
            return OrchestrationReadinessVerdict.BLOCKED
        if replan_refs:
            return OrchestrationReadinessVerdict.REPLAN_REQUIRED
        return OrchestrationReadinessVerdict.READY

    @staticmethod
    def _readiness_score(
        *,
        verdict: OrchestrationReadinessVerdict,
        uncertainty: float,
        hallucination_risk: float,
        soft_risk_count: int,
    ) -> float:
        if verdict == OrchestrationReadinessVerdict.BLOCKED:
            return 0.0
        penalty = min(1.0, max(uncertainty, hallucination_risk) + (0.02 * soft_risk_count))
        score = max(0.0, min(1.0, 1.0 - penalty))
        if verdict == OrchestrationReadinessVerdict.REPLAN_REQUIRED:
            return min(score, 0.49)
        return score


class IntelligenceCoordinationEpisodeBuilder:
    """Deterministic orchestrator that emits a complete coordination episode."""

    def build(
        self,
        *,
        episode_id: str,
        goal_id: str,
        input_symbol_mesh_ref: str,
        world_snapshot_ref: str,
        active_constraints_ref: str,
        causal_graph_ref: str,
        uncertainty_envelope_ref: str,
        problem_signature: MethodProblemSignature,
        constraints: Iterable[CoordinationConstraint],
        method_candidates: Iterable[MethodCandidate],
        resource_budget: float,
        tradeoff_options: Iterable[TradeoffOption],
        created_at: str,
        temporal_events: Iterable[CoordinationTemporalEvent] = (),
        temporal_deadline_at: str | None = None,
        causal_nodes: Iterable[CoordinationCausalNode] = (),
        causal_edges: Iterable[CoordinationCausalEdge] = (),
        abstraction_layers: Iterable[CoordinationAbstractionLayer] = (),
        resource_limits: Iterable[CoordinationResourceLimit] = (),
        grounding_claims: Iterable[CoordinationGroundingClaim] = (),
        expected_grounding_symbol_refs: Iterable[str] = (),
        grounding_confidence_floor: float = 0.5,
        perspectives: Iterable[CoordinationPerspective] = (),
        required_perspective_kinds: Iterable[PerspectiveKind] = (),
        perspective_confidence_floor: float = 0.5,
        pattern_candidates: Iterable[CoordinationPatternCandidate] = (),
        expected_pattern_symbol_refs: Iterable[str] = (),
        world_lineage_links: Iterable[WorldSnapshotLineageLink] = (),
        world_identity_checks: Iterable[WorldIdentityContinuityCheck] = (),
        persistent_causal_chain_refs: Iterable[str] = (),
        counterfactual_specs: Iterable[CounterfactualInterventionSpec] = (),
        delta_spec: WorldModelDeltaProposalSpec | None = None,
        contradiction_record_ids: Iterable[str] = (),
        safety_floor: float = 0.0,
        resource_used: float | None = None,
        replan_uncertainty_threshold: float = 0.5,
        replan_safety_margin_threshold: float = 0.5,
        replan_resource_pressure_threshold: float = 0.8,
        execution_plan_ref: str | None = None,
        coordination_depth: int = 0,
        metadata: Mapping[str, object] | None = None,
    ) -> IntelligenceCoordinationBuildResult:
        """Run the coordination kernels and return the episode with its proofs.

        Input contract: all candidate, constraint, tradeoff, and counterfactual
        inputs are typed records/specs. Optional delta proposals must reference a
        simulated branch by ID.
        Output contract: returns `IntelligenceCoordinationBuildResult` containing
        an immutable episode and every artifact referenced by the episode.
        Error contract: raises `RuntimeCoreInvariantError` for malformed specs,
        no viable method/tradeoff, duplicate branch specs, or unresolved delta
        branch references.
        """
        ordered_constraints = tuple(constraints)
        ordered_candidates = tuple(method_candidates)
        ordered_tradeoffs = tuple(tradeoff_options)
        ordered_temporal_events = tuple(temporal_events)
        ordered_causal_nodes = tuple(causal_nodes)
        ordered_causal_edges = tuple(causal_edges)
        ordered_abstraction_layers = tuple(abstraction_layers)
        ordered_resource_limits = tuple(resource_limits)
        ordered_grounding_claims = tuple(grounding_claims)
        ordered_expected_grounding_symbols = tuple(expected_grounding_symbol_refs)
        ordered_perspectives = tuple(perspectives)
        ordered_required_perspective_kinds = tuple(required_perspective_kinds)
        ordered_pattern_candidates = tuple(pattern_candidates)
        ordered_expected_pattern_symbols = tuple(expected_pattern_symbol_refs)
        ordered_world_lineage_links = tuple(world_lineage_links)
        ordered_world_identity_checks = tuple(world_identity_checks)
        ordered_persistent_causal_chains = tuple(persistent_causal_chain_refs)
        ordered_counterfactual_specs = tuple(counterfactual_specs)
        active_execution_plan_ref = execution_plan_ref or f"{episode_id}:execution-plan"
        self._require_unique_counterfactual_specs(ordered_counterfactual_specs)

        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id=f"{episode_id}:constraint-report",
            constraints=ordered_constraints,
            generated_at=created_at,
            contradiction_record_ids=contradiction_record_ids,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id=f"{episode_id}:method-arbitration",
            problem_signature=problem_signature,
            candidates=ordered_candidates,
            resource_budget=resource_budget,
            decided_at=created_at,
        )
        selected_method = self._selected_method(
            candidates=ordered_candidates,
            selected_method_id=method_arbitration.selected_method_id,
        )
        observed_resource_used = selected_method.resource_requirement if resource_used is None else resource_used
        counterfactual_branches = self._simulate_counterfactuals(
            baseline_snapshot_ref=world_snapshot_ref,
            constraint_report=constraint_report,
            specs=ordered_counterfactual_specs,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id=f"{episode_id}:failure-map",
            source_episode_id=episode_id,
            constraints=ordered_constraints,
            branches=counterfactual_branches,
            generated_at=created_at,
        )
        temporal_report = TemporalStateEvolutionKernel().evaluate(
            report_id=f"{episode_id}:temporal-report",
            source_episode_id=episode_id,
            events=ordered_temporal_events,
            generated_at=created_at,
            deadline_at=temporal_deadline_at,
        )
        causal_dynamics_report = CausalGraphDynamicsKernel().evaluate(
            report_id=f"{episode_id}:causal-dynamics-report",
            source_episode_id=episode_id,
            nodes=ordered_causal_nodes,
            edges=ordered_causal_edges,
            generated_at=created_at,
        )
        abstraction_report = AbstractionControlKernel().evaluate(
            report_id=f"{episode_id}:abstraction-report",
            source_episode_id=episode_id,
            layers=ordered_abstraction_layers,
            generated_at=created_at,
        )
        resource_report = ResourceBoundedControlKernel().evaluate(
            report_id=f"{episode_id}:resource-report",
            source_episode_id=episode_id,
            limits=ordered_resource_limits,
            generated_at=created_at,
        )
        grounding_report = SemanticGroundingKernel().evaluate(
            report_id=f"{episode_id}:grounding-report",
            source_episode_id=episode_id,
            claims=ordered_grounding_claims,
            expected_symbol_refs=ordered_expected_grounding_symbols,
            confidence_floor=grounding_confidence_floor,
            generated_at=created_at,
        )
        perspective_report = MultiPerspectiveReasoningKernel().evaluate(
            report_id=f"{episode_id}:perspective-report",
            source_episode_id=episode_id,
            perspectives=ordered_perspectives,
            required_kinds=ordered_required_perspective_kinds,
            confidence_floor=perspective_confidence_floor,
            generated_at=created_at,
        )
        compression_report = CompressionPatternDiscoveryKernel().evaluate(
            report_id=f"{episode_id}:compression-report",
            source_episode_id=episode_id,
            patterns=ordered_pattern_candidates,
            expected_symbol_refs=ordered_expected_pattern_symbols,
            generated_at=created_at,
        )
        correction_report = CorrectionRepairKernel().evaluate(
            report_id=f"{episode_id}:correction-report",
            source_episode_id=episode_id,
            failure_map=failure_map,
            contradictions_created=contradiction_record_ids,
            generated_at=created_at,
        )
        continuity_report = DynamicWorldModelContinuityKernel().evaluate(
            report_id=f"{episode_id}:continuity-report",
            source_episode_id=episode_id,
            lineage_links=ordered_world_lineage_links,
            identity_checks=ordered_world_identity_checks,
            expected_snapshot_ref=world_snapshot_ref,
            persistent_causal_chain_refs=ordered_persistent_causal_chains,
            generated_at=created_at,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id=f"{episode_id}:tradeoff-report",
            source_episode_id=episode_id,
            options=ordered_tradeoffs,
            generated_at=created_at,
            safety_floor=safety_floor,
            constraint_report=constraint_report,
            resource_report=resource_report,
            grounding_report=grounding_report,
            perspective_report=perspective_report,
        )
        uncertainty_report = UncertaintyPropagationKernel().propagate(
            report_id=f"{episode_id}:uncertainty-report",
            source_episode_id=episode_id,
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=created_at,
            causal_dynamics_report=causal_dynamics_report,
            abstraction_report=abstraction_report,
            resource_report=resource_report,
            grounding_report=grounding_report,
            perspective_report=perspective_report,
            compression_report=compression_report,
            correction_report=correction_report,
            continuity_report=continuity_report,
        )
        self_diagnosis = SelfDiagnosisKernel().diagnose(
            report_id=f"{episode_id}:self-diagnosis",
            source_episode_id=episode_id,
            uncertainty_report=uncertainty_report,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=resource_budget,
            resource_used=observed_resource_used,
            generated_at=created_at,
            causal_dynamics_report=causal_dynamics_report,
            abstraction_report=abstraction_report,
            resource_report=resource_report,
            grounding_report=grounding_report,
            perspective_report=perspective_report,
            compression_report=compression_report,
            correction_report=correction_report,
            continuity_report=continuity_report,
        )
        replan_recommendation = AdaptivePlanningKernel().recommend(
            recommendation_id=f"{episode_id}:replan-recommendation",
            source_episode_id=episode_id,
            current_plan_ref=active_execution_plan_ref,
            uncertainty_report=uncertainty_report,
            self_diagnosis=self_diagnosis,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=created_at,
            uncertainty_threshold=replan_uncertainty_threshold,
            safety_margin_threshold=replan_safety_margin_threshold,
            resource_pressure_threshold=replan_resource_pressure_threshold,
        )
        world_model_delta = self._propose_world_model_delta(
            episode_id=episode_id,
            branches=counterfactual_branches,
            delta_spec=delta_spec,
            grounding_report=grounding_report,
        )
        terminal_outcome = self._episode_terminal_outcome(
            constraint_report=constraint_report,
            failure_map=failure_map,
            temporal_report=temporal_report,
            resource_report=resource_report,
        )
        readiness_report = OrchestrationReadinessKernel().evaluate(
            report_id=f"{episode_id}:readiness-report",
            source_episode_id=episode_id,
            terminal_outcome=terminal_outcome,
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            uncertainty_report=uncertainty_report,
            self_diagnosis=self_diagnosis,
            replan_recommendation=replan_recommendation,
            temporal_report=temporal_report,
            resource_report=resource_report,
            grounding_report=grounding_report,
            correction_report=correction_report,
            continuity_report=continuity_report,
            generated_at=created_at,
        )
        episode_metadata = dict(metadata or {})
        episode_metadata.update(
            {
                "constraint_report_ref": constraint_report.report_id,
                "method_arbitration_ref": method_arbitration.proof_id,
                "selected_tradeoff_option_id": tradeoff_report.selected_option_id,
                "selected_tradeoff_utility": tradeoff_report.selected_utility,
                "tradeoff_dominated_option_count": len(tradeoff_report.dominated_option_ids),
                "tradeoff_utility_tension": tradeoff_report.utility_tension,
                "tradeoff_constraint_tension": tradeoff_report.constraint_tension,
                "tradeoff_resource_tension": tradeoff_report.resource_tension,
                "tradeoff_grounding_tension": tradeoff_report.grounding_tension,
                "tradeoff_perspective_tension": tradeoff_report.perspective_tension,
                "residual_failure_risk": failure_map.residual_risk,
                "uncertainty_report_ref": uncertainty_report.report_id,
                "accumulated_uncertainty": uncertainty_report.accumulated_uncertainty,
                "self_diagnosis_ref": self_diagnosis.report_id,
                "self_diagnosis_severity": self_diagnosis.severity.value,
                "hallucination_risk": self_diagnosis.hallucination_risk,
                "replan_recommendation_ref": replan_recommendation.recommendation_id,
                "replan_required": replan_recommendation.replan_required,
                "replan_trigger": replan_recommendation.trigger.value,
                "replan_urgency": replan_recommendation.urgency,
                "temporal_report_ref": temporal_report.report_id,
                "temporal_status": temporal_report.status.value,
                "temporal_deadline_pressure": temporal_report.deadline_pressure,
                "causal_dynamics_report_ref": causal_dynamics_report.report_id,
                "causal_dynamics_status": causal_dynamics_report.status.value,
                "causal_feedback_cycle_count": len(causal_dynamics_report.feedback_cycle_node_ids),
                "causal_structural_fragility": causal_dynamics_report.structural_fragility,
                "abstraction_report_ref": abstraction_report.report_id,
                "abstraction_status": abstraction_report.status.value,
                "abstraction_scale_coverage": abstraction_report.scale_coverage,
                "abstraction_compression_ratio": abstraction_report.compression_ratio,
                "resource_report_ref": resource_report.report_id,
                "resource_status": resource_report.status.value,
                "resource_max_pressure": resource_report.max_pressure,
                "resource_hard_block_count": len(resource_report.hard_block_limit_ids),
                "grounding_report_ref": grounding_report.report_id,
                "grounding_status": grounding_report.status.value,
                "grounding_coverage": grounding_report.grounding_coverage,
                "grounding_min_confidence": grounding_report.min_confidence,
                "perspective_report_ref": perspective_report.report_id,
                "perspective_status": perspective_report.status.value,
                "perspective_agreement_score": perspective_report.agreement_score,
                "perspective_divergence_count": len(perspective_report.divergent_perspective_ids),
                "compression_report_ref": compression_report.report_id,
                "compression_status": compression_report.status.value,
                "compression_ratio": compression_report.compression_ratio,
                "compression_reuse_score": compression_report.reuse_score,
                "compression_redundant_symbol_count": len(compression_report.redundant_symbol_refs),
                "correction_report_ref": correction_report.report_id,
                "correction_status": correction_report.status.value,
                "correction_repair_pressure": correction_report.repair_pressure,
                "correction_rollback_action_count": len(correction_report.rollback_action_ids),
                "continuity_report_ref": continuity_report.report_id,
                "continuity_status": continuity_report.status.value,
                "continuity_score": continuity_report.continuity_score,
                "continuity_persistent_causal_chain_count": len(continuity_report.persistent_causal_chain_refs),
                "readiness_report_ref": readiness_report.report_id,
                "readiness_verdict": readiness_report.verdict.value,
                "readiness_score": readiness_report.readiness_score,
                "readiness_hard_block_count": len(readiness_report.hard_block_refs),
            }
        )
        episode = IntelligenceCoordinationEpisode(
            episode_id=episode_id,
            goal_id=goal_id,
            input_symbol_mesh_ref=input_symbol_mesh_ref,
            world_snapshot_ref=world_snapshot_ref,
            active_constraints_ref=active_constraints_ref,
            causal_graph_ref=causal_graph_ref,
            uncertainty_envelope_ref=uncertainty_envelope_ref,
            problem_signature=problem_signature,
            method_candidates=ordered_candidates,
            selected_method_id=method_arbitration.selected_method_id,
            rejected_method_ids=method_arbitration.rejected_method_ids,
            counterfactual_branches=counterfactual_branches,
            failure_map_ref=failure_map.map_id,
            tradeoff_report_ref=tradeoff_report.report_id,
            execution_plan_ref=active_execution_plan_ref,
            diagnosis_report_ref=self_diagnosis.report_id,
            world_model_delta_ref=world_model_delta.delta_id if world_model_delta is not None else None,
            proof_record_ref=method_arbitration.proof_id,
            terminal_outcome=terminal_outcome,
            created_at=created_at,
            coordination_depth=coordination_depth,
            metadata=episode_metadata,
        )
        return IntelligenceCoordinationBuildResult(
            episode=episode,
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            uncertainty_report=uncertainty_report,
            self_diagnosis=self_diagnosis,
            replan_recommendation=replan_recommendation,
            temporal_report=temporal_report,
            causal_dynamics_report=causal_dynamics_report,
            abstraction_report=abstraction_report,
            resource_report=resource_report,
            grounding_report=grounding_report,
            perspective_report=perspective_report,
            compression_report=compression_report,
            correction_report=correction_report,
            continuity_report=continuity_report,
            readiness_report=readiness_report,
            world_model_delta=world_model_delta,
        )

    @staticmethod
    def _selected_method(
        *,
        candidates: tuple[MethodCandidate, ...],
        selected_method_id: str,
    ) -> MethodCandidate:
        for candidate in candidates:
            if candidate.method_id == selected_method_id:
                return candidate
        raise RuntimeCoreInvariantError("selected method must reference a candidate")

    @staticmethod
    def _require_unique_counterfactual_specs(specs: tuple[CounterfactualInterventionSpec, ...]) -> None:
        seen: set[str] = set()
        for spec in specs:
            if not isinstance(spec, CounterfactualInterventionSpec):
                raise RuntimeCoreInvariantError("counterfactual_specs must contain CounterfactualInterventionSpec records")
            if spec.branch_id in seen:
                raise RuntimeCoreInvariantError("duplicate counterfactual branch_id")
            seen.add(spec.branch_id)

    @staticmethod
    def _simulate_counterfactuals(
        *,
        baseline_snapshot_ref: str,
        constraint_report: ConstraintSatisfiabilityReport,
        specs: tuple[CounterfactualInterventionSpec, ...],
    ) -> tuple[CounterfactualBranch, ...]:
        if constraint_report.proof_state != ProofState.PASS and specs:
            raise RuntimeCoreInvariantError("counterfactual specs require pass constraint proof state")
        engine = CounterfactualEngine()
        return tuple(
            engine.simulate(
                branch_id=spec.branch_id,
                baseline_snapshot_ref=baseline_snapshot_ref,
                intervention=spec.intervention,
                constraint_report=constraint_report,
                affected_entity_ids=spec.affected_entity_ids,
                affected_relation_ids=spec.affected_relation_ids,
                predicted_delta_refs=spec.predicted_delta_refs,
                reversible_step_ids=spec.reversible_step_ids,
                irreversible_risk_ids=spec.irreversible_risk_ids,
                confidence_lower=spec.confidence_lower,
                confidence_upper=spec.confidence_upper,
            )
            for spec in specs
        )

    @staticmethod
    def _propose_world_model_delta(
        *,
        episode_id: str,
        branches: tuple[CounterfactualBranch, ...],
        delta_spec: WorldModelDeltaProposalSpec | None,
        grounding_report: SemanticGroundingReport,
    ) -> GovernedWorldModelDelta | None:
        if delta_spec is None:
            return None
        if not isinstance(delta_spec, WorldModelDeltaProposalSpec):
            raise RuntimeCoreInvariantError("delta_spec must be a WorldModelDeltaProposalSpec")
        branch_by_id = {branch.branch_id: branch for branch in branches}
        branch = branch_by_id.get(delta_spec.branch_id)
        if branch is None:
            raise RuntimeCoreInvariantError("delta_spec branch_id must reference a simulated branch")
        if grounding_report.status != SemanticGroundingStatus.GROUNDED:
            raise RuntimeCoreInvariantError("world-model delta requires grounded semantic report")
        return WorldModelDeltaBuilder().propose_from_branch(
            delta_id=delta_spec.delta_id,
            source_episode_id=episode_id,
            source_evidence_ids=delta_spec.source_evidence_ids,
            branch=branch,
            governance_decision_ref=delta_spec.governance_decision_ref,
            proposed_confidence_change_refs=delta_spec.proposed_confidence_change_refs,
            contradictions_created=delta_spec.contradictions_created,
            contradictions_resolved=delta_spec.contradictions_resolved,
            allow_irreversible_risk=delta_spec.allow_irreversible_risk,
        )

    @staticmethod
    def _episode_terminal_outcome(
        *,
        constraint_report: ConstraintSatisfiabilityReport,
        failure_map: FailureReasoningMap,
        temporal_report: TemporalStateEvolutionReport,
        resource_report: ResourceBoundedControlReport,
    ) -> SolverTerminalOutcome:
        if constraint_report.terminal_outcome != SolverTerminalOutcome.SOLVED_UNVERIFIED:
            return constraint_report.terminal_outcome
        if resource_report.hard_block_limit_ids:
            return SolverTerminalOutcome.BUDGET_EXHAUSTED
        if temporal_report.status == TemporalCheckStatus.VIOLATED:
            return SolverTerminalOutcome.GOVERNANCE_BLOCKED
        if failure_map.blocked_failure_ids:
            return SolverTerminalOutcome.GOVERNANCE_BLOCKED
        return SolverTerminalOutcome.SOLVED_UNVERIFIED
