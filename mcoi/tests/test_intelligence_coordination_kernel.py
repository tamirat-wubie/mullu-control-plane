"""Tests for deterministic intelligence coordination kernels."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.intelligence_coordination import (
    AbstractionControlStatus,
    AbstractionScale,
    CausalDynamicsStatus,
    CoordinationAbstractionLayer,
    CoordinationCausalEdge,
    CoordinationCausalNode,
    CoordinationConstraint,
    CoordinationConstraintKind,
    CorrectionRepairStatus,
    CoordinationGroundingClaim,
    CoordinationPerspective,
    CoordinationPatternCandidate,
    CoordinationResourceKind,
    CoordinationResourceLimit,
    CoordinationTemporalEvent,
    MethodCandidate,
    MethodFamily,
    MethodProblemSignature,
    OrchestrationReadinessVerdict,
    PerspectiveComparisonStatus,
    PerspectiveKind,
    PatternDiscoveryStatus,
    ProofState,
    SolverTerminalOutcome,
    ResourceBoundStatus,
    SemanticGroundingKind,
    SemanticGroundingStatus,
    TemporalCheckStatus,
    TradeoffOption,
    WorldContinuityStatus,
    WorldIdentityContinuityCheck,
    WorldSnapshotLineageLink,
)
from mcoi_runtime.core.intelligence_coordination import (
    AbstractionControlKernel,
    AdaptivePlanningKernel,
    CausalGraphDynamicsKernel,
    ConstraintReasoningKernel,
    CounterfactualEngine,
    CounterfactualInterventionSpec,
    FailureReasoningKernel,
    IntelligenceCoordinationEpisodeBuilder,
    MethodArbiter,
    MultiPerspectiveReasoningKernel,
    CompressionPatternDiscoveryKernel,
    CorrectionRepairKernel,
    DynamicWorldModelContinuityKernel,
    OrchestrationReadinessKernel,
    ResourceBoundedControlKernel,
    SemanticGroundingKernel,
    SelfDiagnosisKernel,
    TemporalStateEvolutionKernel,
    TradeoffReasoningKernel,
    UncertaintyPropagationKernel,
    WorldModelDeltaProposalSpec,
    WorldModelDeltaBuilder,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


TS = "2026-05-17T00:00:00+00:00"
TS_LATER = "2026-05-17T00:10:00+00:00"
TS_DEADLINE = "2026-05-17T00:20:00+00:00"


def _constraint(
    constraint_id: str,
    kind: CoordinationConstraintKind,
    proof_state: ProofState,
    dependency_ids: tuple[str, ...] = (),
) -> CoordinationConstraint:
    return CoordinationConstraint(
        constraint_id=constraint_id,
        kind=kind,
        proof_state=proof_state,
        statement=f"{constraint_id} statement",
        source_refs=(f"source-{constraint_id}",),
        dependency_ids=dependency_ids,
        evaluated_at=TS,
    )


def _candidate(
    method_id: str,
    family: MethodFamily,
    signatures: tuple[MethodProblemSignature, ...],
    confidence: float,
    resource_requirement: float,
    estimated_cost: float = 1.0,
) -> MethodCandidate:
    return MethodCandidate(
        method_id=method_id,
        family=family,
        compatible_signatures=signatures,
        estimated_cost=estimated_cost,
        confidence=confidence,
        resource_requirement=resource_requirement,
    )


def _temporal_event(
    event_id: str,
    occurred_at: str,
    predecessor_event_ids: tuple[str, ...] = (),
) -> CoordinationTemporalEvent:
    return CoordinationTemporalEvent(
        event_id=event_id,
        occurred_at=occurred_at,
        state_ref=f"state-{event_id}",
        predecessor_event_ids=predecessor_event_ids,
        delayed_effect_refs=(f"effect-{event_id}",),
        persistence_refs=(f"persistence-{event_id}",),
    )


def _causal_node(node_id: str, *, protected: bool = False) -> CoordinationCausalNode:
    return CoordinationCausalNode(
        node_id=node_id,
        label=f"{node_id} label",
        role_refs=(f"role-{node_id}",),
        protected=protected,
    )


def _causal_edge(edge_id: str, cause_node_id: str, effect_node_id: str) -> CoordinationCausalEdge:
    return CoordinationCausalEdge(
        edge_id=edge_id,
        cause_node_id=cause_node_id,
        effect_node_id=effect_node_id,
        strength=0.8,
        evidence_refs=(f"evidence-{edge_id}",),
    )


def _abstraction_layer(
    layer_id: str,
    scale: AbstractionScale,
    parent_layer_ids: tuple[str, ...] = (),
    symbol_refs: tuple[str, ...] | None = None,
) -> CoordinationAbstractionLayer:
    return CoordinationAbstractionLayer(
        layer_id=layer_id,
        scale=scale,
        symbol_refs=symbol_refs or (f"symbol-{layer_id}",),
        evidence_refs=(f"evidence-{layer_id}",),
        parent_layer_ids=parent_layer_ids,
    )


def _resource_limit(
    limit_id: str,
    kind: CoordinationResourceKind,
    budget: float,
    used: float,
    *,
    hard_limit: bool = True,
) -> CoordinationResourceLimit:
    return CoordinationResourceLimit(
        limit_id=limit_id,
        kind=kind,
        budget=budget,
        used=used,
        unit="units",
        hard_limit=hard_limit,
    )


def _grounding_claim(
    claim_id: str,
    symbol_ref: str,
    confidence: float = 0.9,
) -> CoordinationGroundingClaim:
    return CoordinationGroundingClaim(
        claim_id=claim_id,
        symbol_ref=symbol_ref,
        kind=SemanticGroundingKind.OBSERVABLE_STATE,
        target_ref=f"target-{symbol_ref}",
        confidence=confidence,
        evidence_refs=(f"evidence-{claim_id}",),
    )


def _perspective(
    perspective_id: str,
    kind: PerspectiveKind,
    conclusion_refs: tuple[str, ...],
    confidence: float = 0.9,
) -> CoordinationPerspective:
    return CoordinationPerspective(
        perspective_id=perspective_id,
        kind=kind,
        model_ref=f"model-{perspective_id}",
        assumption_refs=(f"assumption-{perspective_id}",),
        incentive_refs=(f"incentive-{perspective_id}",),
        scale_refs=(kind.value,),
        conclusion_refs=conclusion_refs,
        confidence=confidence,
    )


def _pattern(
    pattern_id: str,
    symbol_refs: tuple[str, ...],
    invariant_refs: tuple[str, ...] = (),
    motif_refs: tuple[str, ...] = (),
    reusable_structure_refs: tuple[str, ...] = (),
    redundancy_refs: tuple[str, ...] = (),
) -> CoordinationPatternCandidate:
    return CoordinationPatternCandidate(
        pattern_id=pattern_id,
        symbol_refs=symbol_refs,
        invariant_refs=invariant_refs,
        motif_refs=motif_refs,
        reusable_structure_refs=reusable_structure_refs,
        redundancy_refs=redundancy_refs,
    )


def _lineage_link(link_id: str, prior_snapshot_ref: str, next_snapshot_ref: str) -> WorldSnapshotLineageLink:
    return WorldSnapshotLineageLink(
        link_id=link_id,
        prior_snapshot_ref=prior_snapshot_ref,
        next_snapshot_ref=next_snapshot_ref,
        delta_ref=f"delta-{link_id}",
    )


def _identity_check(
    check_id: str,
    prior_snapshot_ref: str,
    next_snapshot_ref: str,
    *,
    preserved: bool = True,
) -> WorldIdentityContinuityCheck:
    return WorldIdentityContinuityCheck(
        check_id=check_id,
        entity_ref=f"entity-{check_id}",
        prior_snapshot_ref=prior_snapshot_ref,
        next_snapshot_ref=next_snapshot_ref,
        preserved=preserved,
        evidence_refs=(f"evidence-{check_id}",),
    )


def _readiness_inputs(
    *,
    constraints: tuple[CoordinationConstraint, ...] | None = None,
    resource_limits: tuple[CoordinationResourceLimit, ...] = (),
    replan_uncertainty_threshold: float = 0.5,
) -> dict[str, object]:
    active_constraints = constraints or (_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),)
    constraint_report = ConstraintReasoningKernel().evaluate(
        report_id="constraint-report-1",
        constraints=active_constraints,
        generated_at=TS,
    )
    method_arbitration = MethodArbiter().arbitrate(
        proof_id="method-proof-1",
        problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
        candidates=(_candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),),
        resource_budget=5.0,
        decided_at=TS,
    )
    failure_map = FailureReasoningKernel().analyze(
        map_id="failure-map-1",
        source_episode_id="episode-1",
        constraints=active_constraints,
        generated_at=TS,
    )
    temporal_report = TemporalStateEvolutionKernel().evaluate(
        report_id="temporal-report-1",
        source_episode_id="episode-1",
        events=(),
        generated_at=TS,
    )
    resource_report = ResourceBoundedControlKernel().evaluate(
        report_id="resource-report-1",
        source_episode_id="episode-1",
        limits=resource_limits,
        generated_at=TS,
    )
    grounding_report = SemanticGroundingKernel().evaluate(
        report_id="grounding-report-1",
        source_episode_id="episode-1",
        claims=(),
        generated_at=TS,
    )
    correction_report = CorrectionRepairKernel().evaluate(
        report_id="correction-report-1",
        source_episode_id="episode-1",
        failure_map=failure_map,
        generated_at=TS,
    )
    continuity_report = DynamicWorldModelContinuityKernel().evaluate(
        report_id="continuity-report-1",
        source_episode_id="episode-1",
        lineage_links=(),
        identity_checks=(),
        generated_at=TS,
    )
    tradeoff_report = TradeoffReasoningKernel().evaluate(
        report_id="tradeoff-1",
        source_episode_id="episode-1",
        options=(TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),),
        generated_at=TS,
        constraint_report=constraint_report,
        resource_report=resource_report,
        grounding_report=grounding_report,
    )
    uncertainty_report = UncertaintyPropagationKernel().propagate(
        report_id="uncertainty-1",
        source_episode_id="episode-1",
        constraint_report=constraint_report,
        method_arbitration=method_arbitration,
        failure_map=failure_map,
        tradeoff_report=tradeoff_report,
        generated_at=TS,
        resource_report=resource_report,
        correction_report=correction_report,
        continuity_report=continuity_report,
    )
    self_diagnosis = SelfDiagnosisKernel().diagnose(
        report_id="diagnosis-1",
        source_episode_id="episode-1",
        uncertainty_report=uncertainty_report,
        failure_map=failure_map,
        tradeoff_report=tradeoff_report,
        resource_budget=5.0,
        resource_used=1.0,
        generated_at=TS,
        resource_report=resource_report,
        correction_report=correction_report,
        continuity_report=continuity_report,
    )
    replan_recommendation = AdaptivePlanningKernel().recommend(
        recommendation_id="replan-1",
        source_episode_id="episode-1",
        current_plan_ref="plan-1",
        uncertainty_report=uncertainty_report,
        self_diagnosis=self_diagnosis,
        failure_map=failure_map,
        tradeoff_report=tradeoff_report,
        generated_at=TS,
        uncertainty_threshold=replan_uncertainty_threshold,
    )
    terminal_outcome = IntelligenceCoordinationEpisodeBuilder._episode_terminal_outcome(
        constraint_report=constraint_report,
        failure_map=failure_map,
        temporal_report=temporal_report,
        resource_report=resource_report,
    )
    return {
        "terminal_outcome": terminal_outcome,
        "constraint_report": constraint_report,
        "method_arbitration": method_arbitration,
        "failure_map": failure_map,
        "tradeoff_report": tradeoff_report,
        "uncertainty_report": uncertainty_report,
        "self_diagnosis": self_diagnosis,
        "replan_recommendation": replan_recommendation,
        "temporal_report": temporal_report,
        "resource_report": resource_report,
        "grounding_report": grounding_report,
        "correction_report": correction_report,
        "continuity_report": continuity_report,
    }


class TestConstraintReasoningKernel:
    def test_pass_constraints_emit_solved_unverified(self) -> None:
        kernel = ConstraintReasoningKernel()
        report = kernel.evaluate(
            report_id="report-1",
            constraints=(
                _constraint("constraint-1", CoordinationConstraintKind.HARD_LAW, ProofState.PASS),
                _constraint("constraint-2", CoordinationConstraintKind.SOFT_UTILITY, ProofState.UNKNOWN),
            ),
            generated_at=TS,
        )
        assert report.proof_state == ProofState.PASS
        assert report.terminal_outcome == SolverTerminalOutcome.SOLVED_UNVERIFIED
        assert report.blocked_branch_ids == ()

    def test_hard_fail_blocks_branch_and_proves_impossible(self) -> None:
        kernel = ConstraintReasoningKernel()
        report = kernel.evaluate(
            report_id="report-1",
            constraints=(
                _constraint("constraint-1", CoordinationConstraintKind.HARD_LAW, ProofState.PASS),
                _constraint("constraint-2", CoordinationConstraintKind.CAUSAL, ProofState.FAIL, ("dep-1", "dep-2")),
            ),
            generated_at=TS,
            contradiction_record_ids=("contradiction-1",),
        )
        assert report.proof_state == ProofState.FAIL
        assert report.terminal_outcome == SolverTerminalOutcome.IMPOSSIBLE_PROVED
        assert len(report.blocked_branch_ids) == 1
        assert report.propagated_dependencies == ("dep-1", "dep-2")

    def test_hard_unknown_blocks_for_evidence(self) -> None:
        kernel = ConstraintReasoningKernel()
        report = kernel.evaluate(
            report_id="report-1",
            constraints=(
                _constraint("constraint-1", CoordinationConstraintKind.HARD_PHYSICAL, ProofState.UNKNOWN),
                _constraint("constraint-2", CoordinationConstraintKind.SOFT_UTILITY, ProofState.FAIL),
            ),
            generated_at=TS,
        )
        assert report.proof_state == ProofState.UNKNOWN
        assert report.terminal_outcome == SolverTerminalOutcome.AWAITING_EVIDENCE
        assert report.unknown_constraint_ids == ("constraint-1",)
        assert report.violated_constraint_ids == ("constraint-2",)

    def test_budget_unknown_maps_to_budget_exhausted(self) -> None:
        kernel = ConstraintReasoningKernel()
        report = kernel.evaluate(
            report_id="report-1",
            constraints=(
                _constraint("constraint-1", CoordinationConstraintKind.RESOURCE, ProofState.BUDGET_UNKNOWN),
            ),
            generated_at=TS,
        )
        assert report.proof_state == ProofState.BUDGET_UNKNOWN
        assert report.terminal_outcome == SolverTerminalOutcome.BUDGET_EXHAUSTED
        assert len(report.blocked_branch_ids) == 1

    def test_duplicate_constraint_id_rejected(self) -> None:
        kernel = ConstraintReasoningKernel()
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate constraint_id"):
            kernel.evaluate(
                report_id="report-1",
                constraints=(
                    _constraint("constraint-1", CoordinationConstraintKind.HARD_LAW, ProofState.PASS),
                    _constraint("constraint-1", CoordinationConstraintKind.HARD_LAW, ProofState.PASS),
                ),
                generated_at=TS,
            )


class TestMethodArbiter:
    def test_selects_highest_ranked_viable_method(self) -> None:
        arbiter = MethodArbiter()
        proof = arbiter.arbitrate(
            proof_id="proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 2.0),
                _candidate("method-sat", MethodFamily.SAT, (MethodProblemSignature.BOOLEAN_FEASIBILITY,), 1.0, 1.0),
                _candidate("method-heavy", MethodFamily.CAUSAL_GRAPH, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.95, 99.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        assert proof.selected_method_id == "method-graph"
        assert set(proof.rejected_method_ids) == {"method-sat", "method-heavy"}
        assert proof.rejection_reasons["method-sat"] == "incompatible_problem_signature"
        assert proof.rejection_reasons["method-heavy"] == "resource_requirement_exceeds_budget"

    def test_tie_breaks_by_cost_then_id(self) -> None:
        arbiter = MethodArbiter()
        proof = arbiter.arbitrate(
            proof_id="proof-1",
            problem_signature=MethodProblemSignature.BOOLEAN_FEASIBILITY,
            candidates=(
                _candidate("method-b", MethodFamily.SAT, (MethodProblemSignature.BOOLEAN_FEASIBILITY,), 0.8, 1.0, 2.0),
                _candidate("method-a", MethodFamily.SAT, (MethodProblemSignature.BOOLEAN_FEASIBILITY,), 0.8, 1.0, 2.0),
            ),
            resource_budget=4.0,
            decided_at=TS,
        )
        assert proof.selected_method_id == "method-a"
        assert proof.rejected_method_ids == ("method-b",)
        assert proof.rejection_reasons["method-b"] == "lower_ranked_viable_method"

    def test_no_viable_candidate_rejected(self) -> None:
        arbiter = MethodArbiter()
        with pytest.raises(RuntimeCoreInvariantError, match="no viable method candidate"):
            arbiter.arbitrate(
                proof_id="proof-1",
                problem_signature=MethodProblemSignature.CAUSAL_DIAGNOSIS,
                candidates=(
                    _candidate("method-sat", MethodFamily.SAT, (MethodProblemSignature.BOOLEAN_FEASIBILITY,), 0.8, 1.0),
                ),
                resource_budget=5.0,
                decided_at=TS,
            )


class TestCounterfactualEngine:
    def test_simulates_branch_from_pass_constraint_report(self) -> None:
        report = ConstraintReasoningKernel().evaluate(
            report_id="report-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        branch = CounterfactualEngine().simulate(
            branch_id="branch-1",
            baseline_snapshot_ref="snapshot-1",
            intervention="remove dependency edge",
            constraint_report=report,
            affected_entity_ids=("entity-1",),
            affected_relation_ids=("relation-1",),
            predicted_delta_refs=("delta-ref-1",),
            reversible_step_ids=("step-1",),
            irreversible_risk_ids=(),
            confidence_lower=0.4,
            confidence_upper=0.8,
        )
        assert branch.baseline_snapshot_ref == "snapshot-1"
        assert branch.affected_entity_ids == ("entity-1",)
        assert branch.predicted_delta_refs == ("delta-ref-1",)
        assert branch.confidence_lower == 0.4
        assert branch.confidence_upper == 0.8

    def test_blocks_counterfactual_when_hard_constraint_unknown(self) -> None:
        report = ConstraintReasoningKernel().evaluate(
            report_id="report-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.HARD_LAW, ProofState.UNKNOWN),),
            generated_at=TS,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="non-pass hard constraint"):
            CounterfactualEngine().simulate(
                branch_id="branch-1",
                baseline_snapshot_ref="snapshot-1",
                intervention="remove dependency edge",
                constraint_report=report,
                affected_entity_ids=("entity-1",),
                confidence_lower=0.4,
                confidence_upper=0.8,
            )

    def test_rejects_counterfactual_without_affected_surface(self) -> None:
        report = ConstraintReasoningKernel().evaluate(
            report_id="report-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="affected entity, relation, or delta"):
            CounterfactualEngine().simulate(
                branch_id="branch-1",
                baseline_snapshot_ref="snapshot-1",
                intervention="remove dependency edge",
                constraint_report=report,
                confidence_lower=0.4,
                confidence_upper=0.8,
            )

    def test_irreversible_risk_reduces_confidence_envelope(self) -> None:
        report = ConstraintReasoningKernel().evaluate(
            report_id="report-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        branch = CounterfactualEngine().simulate(
            branch_id="branch-1",
            baseline_snapshot_ref="snapshot-1",
            intervention="remove dependency edge",
            constraint_report=report,
            affected_entity_ids=("entity-1",),
            irreversible_risk_ids=("risk-1", "risk-2"),
            confidence_lower=0.4,
            confidence_upper=0.8,
        )
        assert branch.irreversible_risk_ids == ("risk-1", "risk-2")
        assert branch.confidence_lower == pytest.approx(0.2)
        assert branch.confidence_upper == pytest.approx(0.6)


class TestWorldModelDeltaBuilder:
    def test_proposes_evidence_bound_delta_from_branch(self) -> None:
        report = ConstraintReasoningKernel().evaluate(
            report_id="report-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        branch = CounterfactualEngine().simulate(
            branch_id="branch-1",
            baseline_snapshot_ref="snapshot-1",
            intervention="remove dependency edge",
            constraint_report=report,
            affected_entity_ids=("entity-1",),
            affected_relation_ids=("relation-1",),
            predicted_delta_refs=("confidence-change-1",),
            confidence_lower=0.4,
            confidence_upper=0.8,
        )
        delta = WorldModelDeltaBuilder().propose_from_branch(
            delta_id="delta-1",
            source_episode_id="episode-1",
            source_evidence_ids=("evidence-1",),
            branch=branch,
            governance_decision_ref="gov-1",
            contradictions_created=(),
            contradictions_resolved=("contradiction-1",),
        )
        assert delta.prior_snapshot_ref == "snapshot-1"
        assert delta.proposed_entity_change_refs == ("entity-1",)
        assert delta.proposed_relation_change_refs == ("relation-1",)
        assert delta.proposed_confidence_change_refs == ("confidence-change-1",)
        assert delta.contradictions_resolved == ("contradiction-1",)

    def test_delta_requires_source_evidence(self) -> None:
        report = ConstraintReasoningKernel().evaluate(
            report_id="report-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        branch = CounterfactualEngine().simulate(
            branch_id="branch-1",
            baseline_snapshot_ref="snapshot-1",
            intervention="remove dependency edge",
            constraint_report=report,
            affected_entity_ids=("entity-1",),
            confidence_lower=0.4,
            confidence_upper=0.8,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="source_evidence_ids is required"):
            WorldModelDeltaBuilder().propose_from_branch(
                delta_id="delta-1",
                source_episode_id="episode-1",
                source_evidence_ids=(),
                branch=branch,
                governance_decision_ref="gov-1",
            )

    def test_irreversible_branch_requires_explicit_governance_allowance(self) -> None:
        report = ConstraintReasoningKernel().evaluate(
            report_id="report-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        branch = CounterfactualEngine().simulate(
            branch_id="branch-1",
            baseline_snapshot_ref="snapshot-1",
            intervention="remove dependency edge",
            constraint_report=report,
            affected_entity_ids=("entity-1",),
            irreversible_risk_ids=("risk-1",),
            confidence_lower=0.4,
            confidence_upper=0.8,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="irreversible counterfactual risk"):
            WorldModelDeltaBuilder().propose_from_branch(
                delta_id="delta-1",
                source_episode_id="episode-1",
                source_evidence_ids=("evidence-1",),
                branch=branch,
                governance_decision_ref="gov-1",
            )


class TestFailureReasoningKernel:
    def test_non_pass_hard_constraints_become_failure_modes(self) -> None:
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=(
                _constraint("constraint-pass", CoordinationConstraintKind.SOFT_UTILITY, ProofState.UNKNOWN),
                _constraint("constraint-fail", CoordinationConstraintKind.HARD_LAW, ProofState.FAIL, ("dep-1",)),
                _constraint("constraint-unknown", CoordinationConstraintKind.CAUSAL, ProofState.UNKNOWN),
            ),
            generated_at=TS,
        )
        assert len(failure_map.failure_modes) == 2
        assert len(failure_map.blocked_failure_ids) == 1
        assert failure_map.dominant_failure_id == failure_map.failure_modes[0].failure_id
        assert failure_map.residual_risk == 1.0

    def test_irreversible_branch_risks_become_blocked_failures(self) -> None:
        report = ConstraintReasoningKernel().evaluate(
            report_id="report-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        branch = CounterfactualEngine().simulate(
            branch_id="branch-1",
            baseline_snapshot_ref="snapshot-1",
            intervention="remove dependency edge",
            constraint_report=report,
            affected_entity_ids=("entity-1",),
            irreversible_risk_ids=("risk-1",),
            confidence_lower=0.4,
            confidence_upper=0.8,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            branches=(branch,),
            generated_at=TS,
        )
        assert len(failure_map.failure_modes) == 1
        assert failure_map.failure_modes[0].source_ref == "branch-1"
        assert failure_map.failure_modes[0].affected_entity_ids == ("entity-1",)
        assert failure_map.failure_modes[0].reversible is False

    def test_empty_failure_surface_returns_zero_risk_map(self) -> None:
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        assert failure_map.failure_modes == ()
        assert failure_map.blocked_failure_ids == ()
        assert failure_map.dominant_failure_id is None
        assert failure_map.residual_risk == 0.0


class TestTradeoffReasoningKernel:
    def test_selects_highest_utility_option_above_safety_floor(self) -> None:
        report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(
                TradeoffOption("option-fast", "fast", 0.8, 0.2, 0.6, 0.8, ("constraint-1",)),
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
                TradeoffOption("option-weak", "weak", 0.5, 0.4, 0.2, 0.6, ("constraint-1",)),
            ),
            safety_floor=0.5,
            generated_at=TS,
        )
        assert report.selected_option_id == "option-safe"
        assert report.safety_margin == pytest.approx(0.9)
        assert "option-weak" not in report.pareto_frontier_option_ids
        assert report.dominated_option_ids == ("option-weak",)
        assert report.utility_tension > 0.0
        assert set(report.rejected_option_ids) == {"option-fast", "option-weak"}

    def test_exposes_tradeoff_tension_from_runtime_reports(self) -> None:
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=(_constraint("constraint-unknown", CoordinationConstraintKind.CAUSAL, ProofState.UNKNOWN),),
            generated_at=TS,
        )
        resource_report = ResourceBoundedControlKernel().evaluate(
            report_id="resource-report-1",
            source_episode_id="episode-1",
            limits=(_resource_limit("limit-compute", CoordinationResourceKind.COMPUTE, 10.0, 8.0),),
            generated_at=TS,
        )
        grounding_report = SemanticGroundingKernel().evaluate(
            report_id="grounding-report-1",
            source_episode_id="episode-1",
            claims=(_grounding_claim("grounding-1", "symbol-1", 0.9),),
            expected_symbol_refs=("symbol-1", "symbol-2"),
            generated_at=TS,
        )
        perspective_report = MultiPerspectiveReasoningKernel().evaluate(
            report_id="perspective-report-1",
            source_episode_id="episode-1",
            perspectives=(
                _perspective("perspective-model", PerspectiveKind.MODEL, ("conclusion-a",)),
                _perspective("perspective-scale", PerspectiveKind.SCALE, ("conclusion-b",)),
            ),
            required_kinds=(PerspectiveKind.MODEL, PerspectiveKind.SCALE),
            generated_at=TS,
        )
        report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-unknown",)),
                TradeoffOption("option-weak", "weak", 0.5, 0.4, 0.2, 0.6, ("constraint-unknown",)),
            ),
            generated_at=TS,
            constraint_report=constraint_report,
            resource_report=resource_report,
            grounding_report=grounding_report,
            perspective_report=perspective_report,
        )
        assert report.constraint_tension == 1.0
        assert report.resource_tension == 0.8
        assert report.grounding_tension == 0.5
        assert report.perspective_tension == 1.0
        assert report.dominated_option_ids == ("option-weak",)

    def test_rejects_when_no_option_clears_safety_floor(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="no tradeoff option clears safety floor"):
            TradeoffReasoningKernel().evaluate(
                report_id="tradeoff-1",
                source_episode_id="episode-1",
                options=(
                    TradeoffOption("option-risky", "risky", 1.0, 0.1, 0.9, 0.9, ("constraint-1",)),
                ),
                safety_floor=0.5,
                generated_at=TS,
            )

    def test_rejects_duplicate_option_ids(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate option_id"):
            TradeoffReasoningKernel().evaluate(
                report_id="tradeoff-1",
                source_episode_id="episode-1",
                options=(
                    TradeoffOption("option-1", "safe", 0.8, 0.3, 0.2, 0.9, ("constraint-1",)),
                    TradeoffOption("option-1", "duplicate", 0.7, 0.2, 0.1, 0.8, ("constraint-1",)),
                ),
                generated_at=TS,
            )


class TestUncertaintyAndSelfDiagnosisKernels:
    def test_propagates_uncertainty_from_unknowns_failures_and_tradeoffs(self) -> None:
        constraints = (
            _constraint("constraint-unknown", CoordinationConstraintKind.CAUSAL, ProofState.UNKNOWN),
        )
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.7, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.7, 0.2, 0.1, 0.8, ("constraint-unknown",)),),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
        )
        assert "constraint-unknown" in uncertainty.uncertainty_source_refs
        assert uncertainty.evidence_gap_refs == ("constraint-unknown",)
        assert uncertainty.accumulated_uncertainty > 0.0
        assert uncertainty.confidence_lower <= uncertainty.confidence_upper

    def test_causal_feedback_raises_uncertainty_without_hard_blocking(self) -> None:
        constraints = (_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),),
            generated_at=TS,
        )
        causal_report = CausalGraphDynamicsKernel().evaluate(
            report_id="causal-report-1",
            source_episode_id="episode-1",
            nodes=(
                _causal_node("node-1"),
                _causal_node("node-2"),
                _causal_node("node-3"),
            ),
            edges=(
                _causal_edge("edge-1", "node-1", "node-2"),
                _causal_edge("edge-2", "node-2", "node-3"),
                _causal_edge("edge-3", "node-3", "node-1"),
            ),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
            causal_dynamics_report=causal_report,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=1.0,
            generated_at=TS,
            causal_dynamics_report=causal_report,
        )
        assert causal_report.status == CausalDynamicsStatus.FEEDBACK_PRESENT
        assert "causal-report-1" in uncertainty.uncertainty_source_refs
        assert "edge-1" in uncertainty.uncertainty_source_refs
        assert "node-1" in uncertainty.ambiguity_refs
        assert uncertainty.accumulated_uncertainty >= 0.20
        assert "causal_feedback_present" in diagnosis.finding_refs

    def test_abstraction_gap_raises_uncertainty_and_diagnosis_finding(self) -> None:
        constraints = (_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),),
            generated_at=TS,
        )
        abstraction_report = AbstractionControlKernel().evaluate(
            report_id="abstraction-report-1",
            source_episode_id="episode-1",
            layers=(
                _abstraction_layer("layer-micro", AbstractionScale.MICRO),
                _abstraction_layer("layer-macro", AbstractionScale.MACRO),
            ),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
            abstraction_report=abstraction_report,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=1.0,
            generated_at=TS,
            abstraction_report=abstraction_report,
        )
        assert abstraction_report.status == AbstractionControlStatus.GAP_PRESENT
        assert "abstraction-report-1" in uncertainty.uncertainty_source_refs
        assert "meso" in uncertainty.uncertainty_source_refs
        assert uncertainty.accumulated_uncertainty >= 0.10
        assert "abstraction_scale_gap" in diagnosis.finding_refs

    def test_resource_exhaustion_raises_uncertainty_and_diagnosis_finding(self) -> None:
        constraints = (_constraint("constraint-1", CoordinationConstraintKind.RESOURCE, ProofState.PASS),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),),
            generated_at=TS,
        )
        resource_report = ResourceBoundedControlKernel().evaluate(
            report_id="resource-report-1",
            source_episode_id="episode-1",
            limits=(_resource_limit("limit-time", CoordinationResourceKind.TIME, 10.0, 10.0),),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
            resource_report=resource_report,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=1.0,
            generated_at=TS,
            resource_report=resource_report,
        )
        assert resource_report.status == ResourceBoundStatus.EXHAUSTED
        assert "resource-report-1" in uncertainty.uncertainty_source_refs
        assert "limit-time" in uncertainty.uncertainty_source_refs
        assert uncertainty.accumulated_uncertainty >= 0.35
        assert "resource_exhausted" in diagnosis.finding_refs

    def test_missing_grounding_raises_uncertainty_and_diagnosis_finding(self) -> None:
        constraints = (_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),),
            generated_at=TS,
        )
        grounding_report = SemanticGroundingKernel().evaluate(
            report_id="grounding-report-1",
            source_episode_id="episode-1",
            claims=(),
            expected_symbol_refs=("symbol-1",),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
            grounding_report=grounding_report,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=1.0,
            generated_at=TS,
            grounding_report=grounding_report,
        )
        assert grounding_report.status == SemanticGroundingStatus.UNGROUNDED
        assert "grounding-report-1" in uncertainty.uncertainty_source_refs
        assert "symbol-1" in uncertainty.uncertainty_source_refs
        assert uncertainty.accumulated_uncertainty >= 0.35
        assert "semantic_grounding_absent" in diagnosis.finding_refs

    def test_perspective_divergence_raises_uncertainty_and_diagnosis_finding(self) -> None:
        constraints = (_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),),
            generated_at=TS,
        )
        perspective_report = MultiPerspectiveReasoningKernel().evaluate(
            report_id="perspective-report-1",
            source_episode_id="episode-1",
            perspectives=(
                _perspective("perspective-model", PerspectiveKind.MODEL, ("conclusion-a",)),
                _perspective("perspective-scale", PerspectiveKind.SCALE, ("conclusion-b",)),
            ),
            required_kinds=(PerspectiveKind.MODEL, PerspectiveKind.SCALE),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
            perspective_report=perspective_report,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=1.0,
            generated_at=TS,
            perspective_report=perspective_report,
        )
        assert perspective_report.status == PerspectiveComparisonStatus.DIVERGENT
        assert "perspective-report-1" in uncertainty.uncertainty_source_refs
        assert "perspective-model" in uncertainty.ambiguity_refs
        assert uncertainty.accumulated_uncertainty >= 0.25
        assert "perspective_divergence" in diagnosis.finding_refs

    def test_undercompressed_patterns_raise_uncertainty_and_diagnosis_finding(self) -> None:
        constraints = (_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),),
            generated_at=TS,
        )
        compression_report = CompressionPatternDiscoveryKernel().evaluate(
            report_id="compression-report-1",
            source_episode_id="episode-1",
            patterns=(),
            expected_symbol_refs=("symbol-1", "symbol-2"),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
            compression_report=compression_report,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=1.0,
            generated_at=TS,
            compression_report=compression_report,
        )
        assert compression_report.status == PatternDiscoveryStatus.UNDERCOMPRESSED
        assert "compression-report-1" in uncertainty.uncertainty_source_refs
        assert uncertainty.accumulated_uncertainty >= 0.20
        assert "pattern_undercompressed" in diagnosis.finding_refs

    def test_rollback_repair_raises_uncertainty_and_diagnosis_finding(self) -> None:
        constraints = (_constraint("constraint-fail", CoordinationConstraintKind.CAUSAL, ProofState.FAIL),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-fail",)),),
            generated_at=TS,
        )
        correction_report = CorrectionRepairKernel().evaluate(
            report_id="correction-report-1",
            source_episode_id="episode-1",
            failure_map=failure_map,
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
            correction_report=correction_report,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=1.0,
            generated_at=TS,
            correction_report=correction_report,
        )
        assert correction_report.status == CorrectionRepairStatus.ROLLBACK_RECOMMENDED
        assert "correction-report-1" in uncertainty.uncertainty_source_refs
        assert "correction_rollback_recommended" in diagnosis.finding_refs
        assert uncertainty.accumulated_uncertainty >= 0.5

    def test_identity_drift_raises_uncertainty_and_diagnosis_finding(self) -> None:
        constraints = (_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),),
            generated_at=TS,
        )
        continuity_report = DynamicWorldModelContinuityKernel().evaluate(
            report_id="continuity-report-1",
            source_episode_id="episode-1",
            lineage_links=(_lineage_link("link-1", "snapshot-1", "snapshot-2"),),
            identity_checks=(_identity_check("identity-1", "snapshot-1", "snapshot-2", preserved=False),),
            expected_snapshot_ref="snapshot-1",
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
            continuity_report=continuity_report,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=1.0,
            generated_at=TS,
            continuity_report=continuity_report,
        )
        assert continuity_report.status == WorldContinuityStatus.IDENTITY_DRIFT
        assert "continuity-report-1" in uncertainty.uncertainty_source_refs
        assert "identity-1" in uncertainty.uncertainty_source_refs
        assert "world_identity_drift" in diagnosis.finding_refs
        assert uncertainty.accumulated_uncertainty >= 0.25

    def test_self_diagnosis_escalates_blocking_failure(self) -> None:
        constraints = (
            _constraint("constraint-fail", CoordinationConstraintKind.CAUSAL, ProofState.FAIL),
        )
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.7, 0.2, 0.1, 0.8, ("constraint-fail",)),),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=5.0,
            generated_at=TS,
        )
        assert diagnosis.escalation_required is True
        assert diagnosis.severity.value == "blocking"
        assert "blocked_failure_present" in diagnosis.finding_refs
        assert diagnosis.resource_pressure == 1.0


class TestAdaptivePlanningKernel:
    def test_recommends_replan_for_blocking_diagnosis(self) -> None:
        constraints = (_constraint("constraint-fail", CoordinationConstraintKind.CAUSAL, ProofState.FAIL),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.7, 0.2, 0.1, 0.8, ("constraint-fail",)),),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=5.0,
            generated_at=TS,
        )
        recommendation = AdaptivePlanningKernel().recommend(
            recommendation_id="replan-1",
            source_episode_id="episode-1",
            current_plan_ref="plan-1",
            uncertainty_report=uncertainty,
            self_diagnosis=diagnosis,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
        )
        assert recommendation.replan_required is True
        assert recommendation.trigger.value == "diagnosis_blocking"
        assert recommendation.blocked_plan_ref == "plan-1"
        assert recommendation.recommended_plan_ref == "episode-1:replan"
        assert recommendation.urgency == 1.0

    def test_no_replan_when_diagnostics_are_stable(self) -> None:
        constraints = (_constraint("constraint-pass", CoordinationConstraintKind.CAUSAL, ProofState.PASS),)
        constraint_report = ConstraintReasoningKernel().evaluate(
            report_id="constraint-report-1",
            constraints=constraints,
            generated_at=TS,
        )
        method_arbitration = MethodArbiter().arbitrate(
            proof_id="method-proof-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.95, 1.0),
            ),
            resource_budget=5.0,
            decided_at=TS,
        )
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=constraints,
            generated_at=TS,
        )
        tradeoff_report = TradeoffReasoningKernel().evaluate(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            options=(TradeoffOption("option-safe", "safe", 0.9, 0.1, 0.05, 0.95, ("constraint-pass",)),),
            generated_at=TS,
        )
        uncertainty = UncertaintyPropagationKernel().propagate(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            constraint_report=constraint_report,
            method_arbitration=method_arbitration,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
        )
        diagnosis = SelfDiagnosisKernel().diagnose(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report=uncertainty,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            resource_budget=5.0,
            resource_used=1.0,
            generated_at=TS,
        )
        recommendation = AdaptivePlanningKernel().recommend(
            recommendation_id="replan-1",
            source_episode_id="episode-1",
            current_plan_ref="plan-1",
            uncertainty_report=uncertainty,
            self_diagnosis=diagnosis,
            failure_map=failure_map,
            tradeoff_report=tradeoff_report,
            generated_at=TS,
        )
        assert recommendation.replan_required is False
        assert recommendation.trigger.value == "none"
        assert recommendation.blocked_plan_ref is None
        assert recommendation.recommended_plan_ref == "plan-1"
        assert recommendation.urgency == 0.0


class TestTemporalStateEvolutionKernel:
    def test_orders_temporal_events_and_accumulates_state_refs(self) -> None:
        report = TemporalStateEvolutionKernel().evaluate(
            report_id="temporal-1",
            source_episode_id="episode-1",
            events=(
                _temporal_event("event-1", TS),
                _temporal_event("event-2", TS_LATER, ("event-1",)),
            ),
            generated_at=TS_LATER,
            deadline_at=TS_DEADLINE,
        )
        assert report.status == TemporalCheckStatus.ORDERED
        assert report.ordered_event_ids == ("event-1", "event-2")
        assert report.violated_event_ids == ()
        assert report.incomplete_event_ids == ()
        assert report.delayed_effect_refs == ("effect-event-1", "effect-event-2")
        assert report.persistence_refs == ("persistence-event-1", "persistence-event-2")
        assert report.deadline_pressure == pytest.approx(0.5)

    def test_detects_temporal_predecessor_violation(self) -> None:
        report = TemporalStateEvolutionKernel().evaluate(
            report_id="temporal-1",
            source_episode_id="episode-1",
            events=(
                _temporal_event("event-1", TS_LATER),
                _temporal_event("event-2", TS, ("event-1",)),
            ),
            generated_at=TS_LATER,
        )
        assert report.status == TemporalCheckStatus.VIOLATED
        assert report.violated_event_ids == ("event-2",)
        assert report.ordered_event_ids == ("event-1",)

    def test_detects_incomplete_temporal_predecessor(self) -> None:
        report = TemporalStateEvolutionKernel().evaluate(
            report_id="temporal-1",
            source_episode_id="episode-1",
            events=(_temporal_event("event-1", TS, ("missing-event",)),),
            generated_at=TS,
        )
        assert report.status == TemporalCheckStatus.INCOMPLETE
        assert report.incomplete_event_ids == ("event-1",)
        assert report.ordered_event_ids == ()


class TestCausalGraphDynamicsKernel:
    def test_detects_acyclic_bottleneck_and_bridge_nodes(self) -> None:
        report = CausalGraphDynamicsKernel().evaluate(
            report_id="causal-report-1",
            source_episode_id="episode-1",
            nodes=(
                _causal_node("node-1"),
                _causal_node("node-2"),
                _causal_node("node-3"),
                _causal_node("node-4"),
            ),
            edges=(
                _causal_edge("edge-1", "node-1", "node-2"),
                _causal_edge("edge-2", "node-2", "node-3"),
                _causal_edge("edge-3", "node-2", "node-4"),
            ),
            generated_at=TS,
        )
        assert report.status == CausalDynamicsStatus.ACYCLIC
        assert report.feedback_cycle_node_ids == ()
        assert report.feedback_edge_ids == ()
        assert report.bottleneck_node_ids == ("node-2",)
        assert report.bridge_node_ids == ("node-2",)
        assert report.structural_fragility == pytest.approx(0.1875)

    def test_detects_feedback_cycles_and_protected_fragility(self) -> None:
        report = CausalGraphDynamicsKernel().evaluate(
            report_id="causal-report-1",
            source_episode_id="episode-1",
            nodes=(
                _causal_node("node-1", protected=True),
                _causal_node("node-2"),
                _causal_node("node-3"),
            ),
            edges=(
                _causal_edge("edge-1", "node-1", "node-2"),
                _causal_edge("edge-2", "node-2", "node-3"),
                _causal_edge("edge-3", "node-3", "node-1"),
            ),
            generated_at=TS,
        )
        assert report.status == CausalDynamicsStatus.FEEDBACK_PRESENT
        assert report.feedback_cycle_node_ids == ("node-1", "node-2", "node-3")
        assert report.feedback_edge_ids == ("edge-1", "edge-2", "edge-3")
        assert report.protected_node_ids == ("node-1",)
        assert report.structural_fragility == 1.0

    def test_rejects_unknown_causal_edge_endpoint(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="endpoints"):
            CausalGraphDynamicsKernel().evaluate(
                report_id="causal-report-1",
                source_episode_id="episode-1",
                nodes=(_causal_node("node-1"),),
                edges=(_causal_edge("edge-1", "node-1", "missing-node"),),
                generated_at=TS,
            )


class TestAbstractionControlKernel:
    def test_validates_complete_scale_path(self) -> None:
        report = AbstractionControlKernel().evaluate(
            report_id="abstraction-report-1",
            source_episode_id="episode-1",
            layers=(
                _abstraction_layer("layer-micro", AbstractionScale.MICRO),
                _abstraction_layer("layer-meso", AbstractionScale.MESO, ("layer-micro",), ("symbol-shared",)),
                _abstraction_layer("layer-macro", AbstractionScale.MACRO, ("layer-meso",), ("symbol-shared",)),
            ),
            generated_at=TS,
        )
        assert report.status == AbstractionControlStatus.CONSISTENT
        assert report.scale_coverage == 1.0
        assert report.missing_scale_refs == ()
        assert report.orphan_layer_ids == ()
        assert report.compression_ratio == pytest.approx(1.0 / 3.0)

    def test_detects_missing_scale_gap_and_orphan_layer(self) -> None:
        report = AbstractionControlKernel().evaluate(
            report_id="abstraction-report-1",
            source_episode_id="episode-1",
            layers=(
                _abstraction_layer("layer-micro", AbstractionScale.MICRO),
                _abstraction_layer("layer-macro", AbstractionScale.MACRO, ("missing-layer",)),
            ),
            generated_at=TS,
        )
        assert report.status == AbstractionControlStatus.GAP_PRESENT
        assert report.missing_scale_refs == ("meso",)
        assert report.orphan_layer_ids == ("layer-macro",)
        assert report.scale_coverage == pytest.approx(2.0 / 3.0)

    def test_detects_boundary_collapse_when_parent_has_same_scale(self) -> None:
        report = AbstractionControlKernel().evaluate(
            report_id="abstraction-report-1",
            source_episode_id="episode-1",
            layers=(
                _abstraction_layer("layer-micro", AbstractionScale.MICRO),
                _abstraction_layer("layer-meso-1", AbstractionScale.MESO, ("layer-micro",)),
                _abstraction_layer("layer-meso-2", AbstractionScale.MESO, ("layer-meso-1",)),
                _abstraction_layer("layer-macro", AbstractionScale.MACRO, ("layer-meso-2",)),
            ),
            generated_at=TS,
        )
        assert report.status == AbstractionControlStatus.COLLAPSED
        assert report.collapsed_layer_ids == ("layer-meso-2",)
        assert report.scale_coverage == 1.0


class TestResourceBoundedControlKernel:
    def test_classifies_degraded_resource_pressure(self) -> None:
        report = ResourceBoundedControlKernel().evaluate(
            report_id="resource-report-1",
            source_episode_id="episode-1",
            limits=(
                _resource_limit("limit-compute", CoordinationResourceKind.COMPUTE, 10.0, 8.0),
                _resource_limit("limit-memory", CoordinationResourceKind.MEMORY, 10.0, 2.0),
            ),
            generated_at=TS,
        )
        assert report.status == ResourceBoundStatus.DEGRADED
        assert report.degraded_limit_ids == ("limit-compute",)
        assert report.exhausted_limit_ids == ()
        assert report.hard_block_limit_ids == ()
        assert report.max_pressure == 0.8

    def test_classifies_exhausted_hard_resource(self) -> None:
        report = ResourceBoundedControlKernel().evaluate(
            report_id="resource-report-1",
            source_episode_id="episode-1",
            limits=(_resource_limit("limit-time", CoordinationResourceKind.TIME, 10.0, 10.0),),
            generated_at=TS,
        )
        assert report.status == ResourceBoundStatus.EXHAUSTED
        assert report.exhausted_limit_ids == ("limit-time",)
        assert report.hard_block_limit_ids == ("limit-time",)
        assert report.max_pressure == 1.0

    def test_rejects_duplicate_resource_limits(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate resource limit_id"):
            ResourceBoundedControlKernel().evaluate(
                report_id="resource-report-1",
                source_episode_id="episode-1",
                limits=(
                    _resource_limit("limit-time", CoordinationResourceKind.TIME, 10.0, 1.0),
                    _resource_limit("limit-time", CoordinationResourceKind.TIME, 10.0, 2.0),
                ),
                generated_at=TS,
            )


class TestSemanticGroundingKernel:
    def test_validates_complete_grounding_coverage(self) -> None:
        report = SemanticGroundingKernel().evaluate(
            report_id="grounding-report-1",
            source_episode_id="episode-1",
            claims=(
                _grounding_claim("grounding-1", "symbol-1", 0.9),
                _grounding_claim("grounding-2", "symbol-2", 0.8),
            ),
            expected_symbol_refs=("symbol-1", "symbol-2"),
            confidence_floor=0.5,
            generated_at=TS,
        )
        assert report.status == SemanticGroundingStatus.GROUNDED
        assert report.grounded_claim_ids == ("grounding-1", "grounding-2")
        assert report.weak_claim_ids == ()
        assert report.missing_symbol_refs == ()
        assert report.grounding_coverage == 1.0

    def test_detects_partial_grounding_and_missing_symbols(self) -> None:
        report = SemanticGroundingKernel().evaluate(
            report_id="grounding-report-1",
            source_episode_id="episode-1",
            claims=(_grounding_claim("grounding-1", "symbol-1", 0.3),),
            expected_symbol_refs=("symbol-1", "symbol-2"),
            confidence_floor=0.5,
            generated_at=TS,
        )
        assert report.status == SemanticGroundingStatus.UNGROUNDED
        assert report.weak_claim_ids == ("grounding-1",)
        assert report.missing_symbol_refs == ("symbol-2",)
        assert report.grounding_coverage == 0.0

    def test_rejects_duplicate_grounding_claims(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate grounding claim_id"):
            SemanticGroundingKernel().evaluate(
                report_id="grounding-report-1",
                source_episode_id="episode-1",
                claims=(
                    _grounding_claim("grounding-1", "symbol-1", 0.9),
                    _grounding_claim("grounding-1", "symbol-2", 0.9),
                ),
                generated_at=TS,
            )


class TestMultiPerspectiveReasoningKernel:
    def test_detects_aligned_perspectives(self) -> None:
        report = MultiPerspectiveReasoningKernel().evaluate(
            report_id="perspective-report-1",
            source_episode_id="episode-1",
            perspectives=(
                _perspective("perspective-model", PerspectiveKind.MODEL, ("conclusion-1",)),
                _perspective("perspective-assumption", PerspectiveKind.ASSUMPTION, ("conclusion-1",)),
                _perspective("perspective-incentive", PerspectiveKind.INCENTIVE, ("conclusion-1",)),
                _perspective("perspective-scale", PerspectiveKind.SCALE, ("conclusion-1",)),
            ),
            generated_at=TS,
        )
        assert report.status == PerspectiveComparisonStatus.ALIGNED
        assert report.missing_kind_refs == ()
        assert report.divergent_perspective_ids == ()
        assert report.shared_conclusion_refs == ("conclusion-1",)
        assert report.agreement_score == 1.0

    def test_detects_divergent_perspectives(self) -> None:
        report = MultiPerspectiveReasoningKernel().evaluate(
            report_id="perspective-report-1",
            source_episode_id="episode-1",
            perspectives=(
                _perspective("perspective-model", PerspectiveKind.MODEL, ("conclusion-a",)),
                _perspective("perspective-assumption", PerspectiveKind.ASSUMPTION, ("conclusion-b",)),
            ),
            required_kinds=(PerspectiveKind.MODEL, PerspectiveKind.ASSUMPTION),
            generated_at=TS,
        )
        assert report.status == PerspectiveComparisonStatus.DIVERGENT
        assert report.divergent_perspective_ids == ("perspective-model", "perspective-assumption")
        assert report.shared_conclusion_refs == ()
        assert report.agreement_score == 0.0

    def test_detects_undercovered_perspectives(self) -> None:
        report = MultiPerspectiveReasoningKernel().evaluate(
            report_id="perspective-report-1",
            source_episode_id="episode-1",
            perspectives=(
                _perspective("perspective-model", PerspectiveKind.MODEL, ("conclusion-1",), confidence=0.4),
            ),
            required_kinds=(PerspectiveKind.MODEL, PerspectiveKind.SCALE),
            confidence_floor=0.5,
            generated_at=TS,
        )
        assert report.status == PerspectiveComparisonStatus.UNDERCOVERED
        assert report.missing_kind_refs == ("scale",)
        assert report.low_confidence_perspective_ids == ("perspective-model",)
        assert report.agreement_score == 1.0


class TestCompressionPatternDiscoveryKernel:
    def test_detects_reusable_stable_patterns(self) -> None:
        report = CompressionPatternDiscoveryKernel().evaluate(
            report_id="compression-report-1",
            source_episode_id="episode-1",
            patterns=(
                _pattern(
                    "pattern-1",
                    ("symbol-1", "symbol-2"),
                    invariant_refs=("invariant-1",),
                    motif_refs=("motif-1",),
                    reusable_structure_refs=("structure-1",),
                ),
                _pattern(
                    "pattern-2",
                    ("symbol-3",),
                    invariant_refs=("invariant-2",),
                    motif_refs=("motif-2",),
                    reusable_structure_refs=("structure-2",),
                ),
            ),
            expected_symbol_refs=("symbol-1", "symbol-2", "symbol-3"),
            generated_at=TS,
        )
        assert report.status == PatternDiscoveryStatus.STABLE
        assert report.invariant_refs == ("invariant-1", "invariant-2")
        assert report.motif_refs == ("motif-1", "motif-2")
        assert report.reuse_score == 1.0
        assert report.compression_ratio == pytest.approx(2.0 / 3.0)

    def test_detects_redundant_symbols(self) -> None:
        report = CompressionPatternDiscoveryKernel().evaluate(
            report_id="compression-report-1",
            source_episode_id="episode-1",
            patterns=(
                _pattern("pattern-1", ("symbol-1", "symbol-2"), reusable_structure_refs=("structure-1",)),
                _pattern("pattern-2", ("symbol-2", "symbol-3"), redundancy_refs=("symbol-3",)),
            ),
            expected_symbol_refs=("symbol-1", "symbol-2", "symbol-3"),
            generated_at=TS,
        )
        assert report.status == PatternDiscoveryStatus.REDUNDANT
        assert report.redundant_symbol_refs == ("symbol-3", "symbol-2")
        assert report.reuse_score == 0.5
        assert report.compression_ratio == pytest.approx(2.0 / 3.0)

    def test_detects_undercompressed_empty_pattern_surface(self) -> None:
        report = CompressionPatternDiscoveryKernel().evaluate(
            report_id="compression-report-1",
            source_episode_id="episode-1",
            patterns=(),
            expected_symbol_refs=("symbol-1", "symbol-2"),
            generated_at=TS,
        )
        assert report.status == PatternDiscoveryStatus.UNDERCOMPRESSED
        assert report.pattern_ids == ()
        assert report.compression_ratio == 0.0
        assert report.reuse_score == 1.0


class TestCorrectionRepairKernel:
    def test_recommends_repair_for_unresolved_contradictions(self) -> None:
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        report = CorrectionRepairKernel().evaluate(
            report_id="correction-report-1",
            source_episode_id="episode-1",
            failure_map=failure_map,
            contradictions_created=("contradiction-1", "contradiction-2"),
            contradictions_resolved=("contradiction-2",),
            generated_at=TS,
        )
        assert report.status == CorrectionRepairStatus.REPAIR_RECOMMENDED
        assert report.contradiction_refs == ("contradiction-1",)
        assert len(report.repair_action_ids) == 1
        assert report.rollback_action_ids == ()
        assert report.repair_pressure > 0.0

    def test_recommends_rollback_for_blocked_failures(self) -> None:
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=(_constraint("constraint-fail", CoordinationConstraintKind.CAUSAL, ProofState.FAIL),),
            generated_at=TS,
        )
        report = CorrectionRepairKernel().evaluate(
            report_id="correction-report-1",
            source_episode_id="episode-1",
            failure_map=failure_map,
            generated_at=TS,
        )
        assert report.status == CorrectionRepairStatus.ROLLBACK_RECOMMENDED
        assert report.rollback_action_ids == (f"correction-report-1:rollback:{failure_map.blocked_failure_ids[0]}",)
        assert report.repair_action_ids == ()
        assert report.repair_pressure == 1.0

    def test_clean_when_no_repair_surface_exists(self) -> None:
        failure_map = FailureReasoningKernel().analyze(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            generated_at=TS,
        )
        report = CorrectionRepairKernel().evaluate(
            report_id="correction-report-1",
            source_episode_id="episode-1",
            failure_map=failure_map,
            generated_at=TS,
        )
        assert report.status == CorrectionRepairStatus.CLEAN
        assert report.action_ids == ()
        assert report.repair_pressure == 0.0


class TestDynamicWorldModelContinuityKernel:
    def test_validates_continuous_lineage_and_identity(self) -> None:
        report = DynamicWorldModelContinuityKernel().evaluate(
            report_id="continuity-report-1",
            source_episode_id="episode-1",
            lineage_links=(
                _lineage_link("link-1", "snapshot-1", "snapshot-2"),
                _lineage_link("link-2", "snapshot-2", "snapshot-3"),
            ),
            identity_checks=(
                _identity_check("identity-1", "snapshot-1", "snapshot-2"),
            ),
            expected_snapshot_ref="snapshot-1",
            persistent_causal_chain_refs=("chain-1",),
            generated_at=TS,
        )
        assert report.status == WorldContinuityStatus.CONTINUOUS
        assert report.broken_lineage_link_ids == ()
        assert report.drifted_identity_check_ids == ()
        assert report.continuity_score == 1.0
        assert report.persistent_causal_chain_refs == ("chain-1",)

    def test_detects_fragmented_lineage(self) -> None:
        report = DynamicWorldModelContinuityKernel().evaluate(
            report_id="continuity-report-1",
            source_episode_id="episode-1",
            lineage_links=(
                _lineage_link("link-1", "snapshot-1", "snapshot-2"),
                _lineage_link("link-2", "snapshot-x", "snapshot-3"),
            ),
            identity_checks=(),
            expected_snapshot_ref="snapshot-1",
            generated_at=TS,
        )
        assert report.status == WorldContinuityStatus.FRAGMENTED
        assert report.broken_lineage_link_ids == ("link-2",)
        assert report.continuity_score == 0.5

    def test_detects_identity_drift(self) -> None:
        report = DynamicWorldModelContinuityKernel().evaluate(
            report_id="continuity-report-1",
            source_episode_id="episode-1",
            lineage_links=(_lineage_link("link-1", "snapshot-1", "snapshot-2"),),
            identity_checks=(
                _identity_check("identity-1", "snapshot-1", "snapshot-2", preserved=False),
            ),
            expected_snapshot_ref="snapshot-1",
            generated_at=TS,
        )
        assert report.status == WorldContinuityStatus.IDENTITY_DRIFT
        assert report.drifted_identity_check_ids == ("identity-1",)
        assert report.continuity_score == 0.5


class TestOrchestrationReadinessKernel:
    def test_reports_ready_when_no_blockers_or_replan_refs(self) -> None:
        inputs = _readiness_inputs()
        report = OrchestrationReadinessKernel().evaluate(
            report_id="readiness-report-1",
            source_episode_id="episode-1",
            generated_at=TS,
            **inputs,
        )
        assert report.verdict == OrchestrationReadinessVerdict.READY
        assert report.hard_block_refs == ()
        assert report.replan_refs == ()
        assert report.readiness_score > 0.0

    def test_reports_replan_required_when_adaptive_plan_requests_it(self) -> None:
        inputs = _readiness_inputs(replan_uncertainty_threshold=0.01)
        report = OrchestrationReadinessKernel().evaluate(
            report_id="readiness-report-1",
            source_episode_id="episode-1",
            generated_at=TS,
            **inputs,
        )
        assert report.verdict == OrchestrationReadinessVerdict.REPLAN_REQUIRED
        assert report.hard_block_refs == ()
        assert report.replan_refs != ()
        assert report.readiness_score <= 0.49

    def test_reports_blocked_when_terminal_outcome_is_hard_blocked(self) -> None:
        inputs = _readiness_inputs(
            resource_limits=(_resource_limit("limit-time", CoordinationResourceKind.TIME, 10.0, 10.0),)
        )
        report = OrchestrationReadinessKernel().evaluate(
            report_id="readiness-report-1",
            source_episode_id="episode-1",
            generated_at=TS,
            **inputs,
        )
        assert report.verdict == OrchestrationReadinessVerdict.BLOCKED
        assert "limit-time" in report.hard_block_refs
        assert "BudgetExhausted" in report.hard_block_refs
        assert report.readiness_score == 0.0


class TestIntelligenceCoordinationEpisodeBuilder:
    def test_builds_complete_episode_with_delta_and_proof_refs(self) -> None:
        result = IntelligenceCoordinationEpisodeBuilder().build(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            method_candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
                _candidate("method-heavy", MethodFamily.CAUSAL_GRAPH, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.7, 4.0),
            ),
            resource_budget=5.0,
            tradeoff_options=(
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
                TradeoffOption("option-fast", "fast", 0.8, 0.2, 0.6, 0.8, ("constraint-1",)),
            ),
            temporal_events=(
                _temporal_event("event-1", TS),
                _temporal_event("event-2", TS_LATER, ("event-1",)),
            ),
            temporal_deadline_at=TS_DEADLINE,
            causal_nodes=(
                _causal_node("node-1", protected=True),
                _causal_node("node-2"),
                _causal_node("node-3"),
            ),
            causal_edges=(
                _causal_edge("edge-1", "node-1", "node-2"),
                _causal_edge("edge-2", "node-2", "node-3"),
            ),
            abstraction_layers=(
                _abstraction_layer("layer-micro", AbstractionScale.MICRO),
                _abstraction_layer("layer-meso", AbstractionScale.MESO, ("layer-micro",)),
                _abstraction_layer("layer-macro", AbstractionScale.MACRO, ("layer-meso",)),
            ),
            resource_limits=(
                _resource_limit("limit-compute", CoordinationResourceKind.COMPUTE, 10.0, 2.0),
            ),
            grounding_claims=(
                _grounding_claim("grounding-entity", "entity-1", 0.9),
                _grounding_claim("grounding-relation", "relation-1", 0.9),
            ),
            expected_grounding_symbol_refs=("entity-1", "relation-1"),
            perspectives=(
                _perspective("perspective-model", PerspectiveKind.MODEL, ("plan-valid",)),
                _perspective("perspective-assumption", PerspectiveKind.ASSUMPTION, ("plan-valid",)),
                _perspective("perspective-incentive", PerspectiveKind.INCENTIVE, ("plan-valid",)),
                _perspective("perspective-scale", PerspectiveKind.SCALE, ("plan-valid",)),
            ),
            pattern_candidates=(
                _pattern(
                    "pattern-1",
                    ("entity-1", "relation-1"),
                    invariant_refs=("invariant-1",),
                    motif_refs=("motif-1",),
                    reusable_structure_refs=("structure-1",),
                ),
            ),
            expected_pattern_symbol_refs=("entity-1", "relation-1"),
            world_lineage_links=(
                _lineage_link("link-1", "snapshot-1", "snapshot-2"),
            ),
            world_identity_checks=(
                _identity_check("identity-1", "snapshot-1", "snapshot-2"),
            ),
            persistent_causal_chain_refs=("chain-1",),
            counterfactual_specs=(
                CounterfactualInterventionSpec(
                    branch_id="branch-1",
                    intervention="remove dependency edge",
                    affected_entity_ids=("entity-1",),
                    affected_relation_ids=("relation-1",),
                    predicted_delta_refs=("confidence-change-1",),
                    confidence_lower=0.4,
                    confidence_upper=0.8,
                ),
            ),
            delta_spec=WorldModelDeltaProposalSpec(
                delta_id="delta-1",
                source_evidence_ids=("evidence-1",),
                branch_id="branch-1",
                governance_decision_ref="gov-1",
            ),
            created_at=TS_LATER,
            safety_floor=0.5,
            metadata={"tenant_id": "tenant-1"},
        )
        assert result.episode.selected_method_id == "method-graph"
        assert result.episode.counterfactual_branches[0].branch_id == "branch-1"
        assert result.episode.failure_map_ref == result.failure_map.map_id
        assert result.episode.tradeoff_report_ref == result.tradeoff_report.report_id
        assert result.episode.world_model_delta_ref == "delta-1"
        assert result.world_model_delta is not None
        assert result.world_model_delta.prior_snapshot_ref == "snapshot-1"
        assert result.episode.terminal_outcome == SolverTerminalOutcome.SOLVED_UNVERIFIED
        assert result.episode.metadata["constraint_report_ref"] == result.constraint_report.report_id
        assert result.episode.metadata["selected_tradeoff_option_id"] == "option-safe"
        assert result.episode.metadata["tradeoff_dominated_option_count"] == 0
        assert result.episode.metadata["tradeoff_utility_tension"] == 0.0
        assert result.episode.metadata["tradeoff_resource_tension"] == pytest.approx(0.2)
        assert result.episode.metadata["tradeoff_grounding_tension"] == 0.0
        assert result.episode.metadata["tradeoff_perspective_tension"] == 0.0
        assert result.episode.diagnosis_report_ref == result.self_diagnosis.report_id
        assert result.episode.metadata["uncertainty_report_ref"] == result.uncertainty_report.report_id
        assert result.self_diagnosis.escalation_required is False
        assert result.replan_recommendation.replan_required is False
        assert result.episode.metadata["replan_trigger"] == "none"
        assert result.temporal_report.status == TemporalCheckStatus.ORDERED
        assert result.episode.metadata["temporal_status"] == "ordered"
        assert result.episode.metadata["temporal_deadline_pressure"] == pytest.approx(0.5)
        assert result.causal_dynamics_report.status == CausalDynamicsStatus.ACYCLIC
        assert result.episode.metadata["causal_dynamics_status"] == "acyclic"
        assert result.episode.metadata["causal_feedback_cycle_count"] == 0
        assert result.episode.metadata["causal_structural_fragility"] == pytest.approx(1.0 / 12.0)
        assert result.abstraction_report.status == AbstractionControlStatus.CONSISTENT
        assert result.episode.metadata["abstraction_status"] == "consistent"
        assert result.episode.metadata["abstraction_scale_coverage"] == 1.0
        assert result.resource_report.status == ResourceBoundStatus.NORMAL
        assert result.episode.metadata["resource_status"] == "normal"
        assert result.episode.metadata["resource_hard_block_count"] == 0
        assert result.grounding_report.status == SemanticGroundingStatus.GROUNDED
        assert result.episode.metadata["grounding_status"] == "grounded"
        assert result.episode.metadata["grounding_coverage"] == 1.0
        assert result.perspective_report.status == PerspectiveComparisonStatus.ALIGNED
        assert result.episode.metadata["perspective_status"] == "aligned"
        assert result.episode.metadata["perspective_agreement_score"] == 1.0
        assert result.compression_report.status == PatternDiscoveryStatus.STABLE
        assert result.episode.metadata["compression_status"] == "stable"
        assert result.episode.metadata["compression_reuse_score"] == 1.0
        assert result.correction_report.status == CorrectionRepairStatus.CLEAN
        assert result.episode.metadata["correction_status"] == "clean"
        assert result.episode.metadata["correction_rollback_action_count"] == 0
        assert result.continuity_report.status == WorldContinuityStatus.CONTINUOUS
        assert result.episode.metadata["continuity_status"] == "continuous"
        assert result.episode.metadata["continuity_score"] == 1.0
        assert result.readiness_report.verdict == OrchestrationReadinessVerdict.READY
        assert result.episode.metadata["readiness_verdict"] == "ready"
        assert result.episode.metadata["readiness_hard_block_count"] == 0

    def test_branch_irreversible_risk_blocks_episode_terminal_outcome(self) -> None:
        result = IntelligenceCoordinationEpisodeBuilder().build(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            method_candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            tradeoff_options=(
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
            ),
            counterfactual_specs=(
                CounterfactualInterventionSpec(
                    branch_id="branch-risk",
                    intervention="force irreversible edge removal",
                    affected_entity_ids=("entity-1",),
                    irreversible_risk_ids=("risk-1",),
                    confidence_lower=0.4,
                    confidence_upper=0.8,
                ),
            ),
            created_at=TS,
        )
        assert result.failure_map.blocked_failure_ids == (result.failure_map.failure_modes[0].failure_id,)
        assert result.episode.terminal_outcome == SolverTerminalOutcome.GOVERNANCE_BLOCKED
        assert result.episode.world_model_delta_ref is None
        assert result.self_diagnosis.escalation_required is True
        assert result.episode.metadata["self_diagnosis_severity"] == "blocking"
        assert result.replan_recommendation.replan_required is True
        assert result.episode.metadata["replan_trigger"] == "diagnosis_blocking"

    def test_temporal_violation_blocks_episode_terminal_outcome(self) -> None:
        result = IntelligenceCoordinationEpisodeBuilder().build(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.TEMPORAL, ProofState.PASS),),
            method_candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            tradeoff_options=(
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
            ),
            temporal_events=(
                _temporal_event("event-1", TS_LATER),
                _temporal_event("event-2", TS, ("event-1",)),
            ),
            created_at=TS_LATER,
        )
        assert result.temporal_report.status == TemporalCheckStatus.VIOLATED
        assert result.temporal_report.violated_event_ids == ("event-2",)
        assert result.episode.terminal_outcome == SolverTerminalOutcome.GOVERNANCE_BLOCKED
        assert result.episode.metadata["temporal_status"] == "violated"

    def test_causal_feedback_requests_replan_without_terminal_block(self) -> None:
        result = IntelligenceCoordinationEpisodeBuilder().build(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            method_candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            tradeoff_options=(
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
            ),
            causal_nodes=(
                _causal_node("node-1"),
                _causal_node("node-2"),
                _causal_node("node-3"),
            ),
            causal_edges=(
                _causal_edge("edge-1", "node-1", "node-2"),
                _causal_edge("edge-2", "node-2", "node-3"),
                _causal_edge("edge-3", "node-3", "node-1"),
            ),
            replan_uncertainty_threshold=0.2,
            created_at=TS,
        )
        assert result.causal_dynamics_report.status == CausalDynamicsStatus.FEEDBACK_PRESENT
        assert result.episode.terminal_outcome == SolverTerminalOutcome.SOLVED_UNVERIFIED
        assert result.replan_recommendation.replan_required is True
        assert result.episode.metadata["replan_trigger"] == "uncertainty_high"
        assert result.episode.metadata["causal_feedback_cycle_count"] == 3
        assert result.uncertainty_report.accumulated_uncertainty >= 0.25

    def test_abstraction_collapse_requests_replan_without_terminal_block(self) -> None:
        result = IntelligenceCoordinationEpisodeBuilder().build(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            method_candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            tradeoff_options=(
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
            ),
            abstraction_layers=(
                _abstraction_layer("layer-micro", AbstractionScale.MICRO),
                _abstraction_layer("layer-meso-1", AbstractionScale.MESO, ("layer-micro",)),
                _abstraction_layer("layer-meso-2", AbstractionScale.MESO, ("layer-meso-1",)),
                _abstraction_layer("layer-macro", AbstractionScale.MACRO, ("layer-meso-2",)),
            ),
            replan_uncertainty_threshold=0.2,
            created_at=TS,
        )
        assert result.abstraction_report.status == AbstractionControlStatus.COLLAPSED
        assert result.episode.terminal_outcome == SolverTerminalOutcome.SOLVED_UNVERIFIED
        assert result.replan_recommendation.replan_required is True
        assert result.episode.metadata["replan_trigger"] == "uncertainty_high"
        assert result.episode.metadata["abstraction_status"] == "collapsed"
        assert "abstraction_boundary_collapsed" in result.self_diagnosis.finding_refs

    def test_perspective_divergence_requests_replan_without_terminal_block(self) -> None:
        result = IntelligenceCoordinationEpisodeBuilder().build(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            method_candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            tradeoff_options=(
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
            ),
            perspectives=(
                _perspective("perspective-model", PerspectiveKind.MODEL, ("conclusion-a",)),
                _perspective("perspective-scale", PerspectiveKind.SCALE, ("conclusion-b",)),
            ),
            required_perspective_kinds=(PerspectiveKind.MODEL, PerspectiveKind.SCALE),
            replan_uncertainty_threshold=0.2,
            created_at=TS,
        )
        assert result.perspective_report.status == PerspectiveComparisonStatus.DIVERGENT
        assert result.episode.terminal_outcome == SolverTerminalOutcome.SOLVED_UNVERIFIED
        assert result.replan_recommendation.replan_required is True
        assert result.episode.metadata["replan_trigger"] == "uncertainty_high"
        assert result.episode.metadata["perspective_status"] == "divergent"
        assert "perspective_divergence" in result.self_diagnosis.finding_refs

    def test_resource_exhaustion_returns_budget_exhausted_terminal_outcome(self) -> None:
        result = IntelligenceCoordinationEpisodeBuilder().build(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.RESOURCE, ProofState.PASS),),
            method_candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            tradeoff_options=(
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
            ),
            resource_limits=(
                _resource_limit("limit-time", CoordinationResourceKind.TIME, 10.0, 10.0),
            ),
            created_at=TS,
        )
        assert result.resource_report.status == ResourceBoundStatus.EXHAUSTED
        assert result.episode.terminal_outcome == SolverTerminalOutcome.BUDGET_EXHAUSTED
        assert result.replan_recommendation.replan_required is True
        assert result.episode.metadata["replan_trigger"] == "resource_exhausted"
        assert result.episode.metadata["resource_hard_block_count"] == 1
        assert "resource_exhausted" in result.self_diagnosis.finding_refs

    def test_contradiction_repair_requests_replan_without_terminal_block(self) -> None:
        result = IntelligenceCoordinationEpisodeBuilder().build(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
            constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
            method_candidates=(
                _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
            ),
            resource_budget=5.0,
            tradeoff_options=(
                TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
            ),
            contradiction_record_ids=("contradiction-1",),
            replan_uncertainty_threshold=0.2,
            created_at=TS,
        )
        assert result.correction_report.status == CorrectionRepairStatus.REPAIR_RECOMMENDED
        assert result.episode.terminal_outcome == SolverTerminalOutcome.SOLVED_UNVERIFIED
        assert result.replan_recommendation.replan_required is True
        assert result.episode.metadata["replan_trigger"] == "uncertainty_high"
        assert result.episode.metadata["correction_status"] == "repair_recommended"
        assert "correction_repair_recommended" in result.self_diagnosis.finding_refs

    def test_ungrounded_symbols_block_world_model_delta(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="world-model delta requires grounded semantic report"):
            IntelligenceCoordinationEpisodeBuilder().build(
                episode_id="episode-1",
                goal_id="goal-1",
                input_symbol_mesh_ref="mesh-1",
                world_snapshot_ref="snapshot-1",
                active_constraints_ref="constraints-1",
                causal_graph_ref="causal-1",
                uncertainty_envelope_ref="uncertainty-1",
                problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
                constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
                method_candidates=(
                    _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
                ),
                resource_budget=5.0,
                tradeoff_options=(
                    TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
                ),
                counterfactual_specs=(
                    CounterfactualInterventionSpec(
                        branch_id="branch-1",
                        intervention="remove dependency edge",
                        affected_entity_ids=("entity-1",),
                        confidence_lower=0.4,
                        confidence_upper=0.8,
                    ),
                ),
                delta_spec=WorldModelDeltaProposalSpec(
                    delta_id="delta-1",
                    source_evidence_ids=("evidence-1",),
                    branch_id="branch-1",
                    governance_decision_ref="gov-1",
                ),
                expected_grounding_symbol_refs=("entity-1",),
                created_at=TS,
            )

    def test_non_pass_constraints_block_counterfactual_specs(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="counterfactual specs require pass"):
            IntelligenceCoordinationEpisodeBuilder().build(
                episode_id="episode-1",
                goal_id="goal-1",
                input_symbol_mesh_ref="mesh-1",
                world_snapshot_ref="snapshot-1",
                active_constraints_ref="constraints-1",
                causal_graph_ref="causal-1",
                uncertainty_envelope_ref="uncertainty-1",
                problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
                constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.UNKNOWN),),
                method_candidates=(
                    _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
                ),
                resource_budget=5.0,
                tradeoff_options=(
                    TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
                ),
                counterfactual_specs=(
                    CounterfactualInterventionSpec(
                        branch_id="branch-1",
                        intervention="remove dependency edge",
                        affected_entity_ids=("entity-1",),
                        confidence_lower=0.4,
                        confidence_upper=0.8,
                    ),
                ),
                created_at=TS,
            )

    def test_delta_spec_must_reference_simulated_branch(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="delta_spec branch_id"):
            IntelligenceCoordinationEpisodeBuilder().build(
                episode_id="episode-1",
                goal_id="goal-1",
                input_symbol_mesh_ref="mesh-1",
                world_snapshot_ref="snapshot-1",
                active_constraints_ref="constraints-1",
                causal_graph_ref="causal-1",
                uncertainty_envelope_ref="uncertainty-1",
                problem_signature=MethodProblemSignature.GRAPH_DEPENDENCY,
                constraints=(_constraint("constraint-1", CoordinationConstraintKind.CAUSAL, ProofState.PASS),),
                method_candidates=(
                    _candidate("method-graph", MethodFamily.GRAPH_METHOD, (MethodProblemSignature.GRAPH_DEPENDENCY,), 0.9, 1.0),
                ),
                resource_budget=5.0,
                tradeoff_options=(
                    TradeoffOption("option-safe", "safe", 0.75, 0.3, 0.1, 0.9, ("constraint-1",)),
                ),
                delta_spec=WorldModelDeltaProposalSpec(
                    delta_id="delta-1",
                    source_evidence_ids=("evidence-1",),
                    branch_id="missing-branch",
                    governance_decision_ref="gov-1",
                ),
                created_at=TS,
            )
