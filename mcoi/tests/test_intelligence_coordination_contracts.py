"""Tests for intelligence coordination contracts.

Covers episode, constraint report, method arbitration proof, counterfactual
branch, governed world-model delta, validation failures, and immutability.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.intelligence_coordination import (
    AbstractionControlReport,
    AbstractionControlStatus,
    AbstractionScale,
    AdaptiveReplanRecommendation,
    CausalDynamicsStatus,
    CausalGraphDynamicsReport,
    CoordinationAbstractionLayer,
    ConstraintSatisfiabilityReport,
    CoordinationCausalEdge,
    CoordinationCausalNode,
    CoordinationConstraint,
    CoordinationConstraintKind,
    CorrectionActionKind,
    CorrectionRepairAction,
    CorrectionRepairReport,
    CorrectionRepairStatus,
    CoordinationGroundingClaim,
    CoordinationPerspective,
    CoordinationPatternCandidate,
    CoordinationResourceKind,
    CoordinationResourceLimit,
    CoordinationTemporalEvent,
    CounterfactualBranch,
    DiagnosisSeverity,
    FailureMode,
    FailureReasoningMap,
    FailureSeverity,
    GovernedWorldModelDelta,
    DynamicWorldModelContinuityReport,
    IntelligenceCoordinationEpisode,
    MethodArbitrationProof,
    MethodCandidate,
    MethodFamily,
    MethodProblemSignature,
    CompressionPatternDiscoveryReport,
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
    SemanticGroundingKind,
    SemanticGroundingReport,
    SemanticGroundingStatus,
    SelfDiagnosisReport,
    SolverTerminalOutcome,
    TradeoffOption,
    TemporalCheckStatus,
    TemporalStateEvolutionReport,
    TradeoffReasoningReport,
    UncertaintyPropagationReport,
    WorldContinuityStatus,
    WorldIdentityContinuityCheck,
    WorldSnapshotLineageLink,
)


TS = "2026-05-17T00:00:00+00:00"


def _candidate(method_id: str = "method-sat") -> MethodCandidate:
    return MethodCandidate(
        method_id=method_id,
        family=MethodFamily.SAT,
        compatible_signatures=(MethodProblemSignature.BOOLEAN_FEASIBILITY,),
        estimated_cost=1.0,
        confidence=0.9,
        resource_requirement=2.0,
    )


def _branch() -> CounterfactualBranch:
    return CounterfactualBranch(
        branch_id="branch-1",
        baseline_snapshot_ref="snapshot-1",
        intervention="remove dependency edge",
        affected_entity_ids=("entity-1",),
        affected_relation_ids=("relation-1",),
        predicted_delta_refs=("delta-1",),
        reversible_step_ids=("step-1",),
        irreversible_risk_ids=(),
        confidence_lower=0.4,
        confidence_upper=0.8,
    )


class TestCoordinationConstraint:
    def test_valid_hard_constraint(self) -> None:
        constraint = CoordinationConstraint(
            constraint_id="constraint-1",
            kind=CoordinationConstraintKind.HARD_LAW,
            proof_state=ProofState.PASS,
            statement="policy gate allows planning",
            source_refs=("policy-1",),
            dependency_ids=("dep-1",),
            evaluated_at=TS,
        )
        assert constraint.constraint_id == "constraint-1"
        assert constraint.is_hard is True
        assert constraint.dependency_ids == ("dep-1",)

    def test_source_refs_require_non_empty_array(self) -> None:
        with pytest.raises(ValueError, match="source_refs"):
            CoordinationConstraint(
                constraint_id="constraint-1",
                kind=CoordinationConstraintKind.HARD_LAW,
                proof_state=ProofState.PASS,
                statement="policy gate allows planning",
                source_refs=(),
            )
        with pytest.raises(ValueError, match="source_refs must be an array"):
            CoordinationConstraint(
                constraint_id="constraint-1",
                kind=CoordinationConstraintKind.HARD_LAW,
                proof_state=ProofState.PASS,
                statement="policy gate allows planning",
                source_refs="policy-1",
            )
        with pytest.raises(ValueError, match="source_refs must contain unique values"):
            CoordinationConstraint(
                constraint_id="constraint-1",
                kind=CoordinationConstraintKind.HARD_LAW,
                proof_state=ProofState.PASS,
                statement="policy gate allows planning",
                source_refs=("policy-1", "policy-1"),
            )


class TestConstraintSatisfiabilityReport:
    def test_valid_report(self) -> None:
        report = ConstraintSatisfiabilityReport(
            report_id="report-1",
            evaluated_constraint_ids=("constraint-1", "constraint-2"),
            satisfied_constraint_ids=("constraint-1",),
            violated_constraint_ids=(),
            unknown_constraint_ids=("constraint-2",),
            propagated_dependencies=("dep-1",),
            contradiction_record_ids=(),
            blocked_branch_ids=("blocked-1",),
            proof_state=ProofState.UNKNOWN,
            terminal_outcome=SolverTerminalOutcome.AWAITING_EVIDENCE,
            generated_at=TS,
        )
        assert report.proof_state == ProofState.UNKNOWN
        assert report.terminal_outcome == SolverTerminalOutcome.AWAITING_EVIDENCE
        assert report.blocked_branch_ids == ("blocked-1",)

    def test_invalid_terminal_outcome_rejected(self) -> None:
        with pytest.raises(ValueError, match="terminal_outcome"):
            ConstraintSatisfiabilityReport(
                report_id="report-1",
                evaluated_constraint_ids=(),
                satisfied_constraint_ids=(),
                violated_constraint_ids=(),
                unknown_constraint_ids=(),
                propagated_dependencies=(),
                contradiction_record_ids=(),
                blocked_branch_ids=(),
                proof_state=ProofState.PASS,
                terminal_outcome="bad",  # type: ignore[arg-type]
                generated_at=TS,
            )


class TestMethodArbitrationContracts:
    def test_method_candidate_validates_and_freezes(self) -> None:
        candidate = _candidate()
        assert candidate.method_id == "method-sat"
        assert candidate.confidence == 0.9
        assert candidate.compatible_signatures == (MethodProblemSignature.BOOLEAN_FEASIBILITY,)

    def test_candidate_rejects_invalid_signature_list(self) -> None:
        with pytest.raises(ValueError, match="compatible_signatures"):
            MethodCandidate(
                method_id="method-bad",
                family=MethodFamily.SAT,
                compatible_signatures=(),
                estimated_cost=1.0,
                confidence=0.5,
            )

    def test_arbitration_proof_requires_rejection_reasons(self) -> None:
        with pytest.raises(ValueError, match="every rejected method"):
            MethodArbitrationProof(
                proof_id="proof-1",
                problem_signature=MethodProblemSignature.BOOLEAN_FEASIBILITY,
                selected_method_id="method-sat",
                candidate_method_ids=("method-sat", "method-graph"),
                rejected_method_ids=("method-graph",),
                rejection_reasons={},
                selected_score=0.8,
                resource_budget=3.0,
                decided_at=TS,
            )


class TestCounterfactualAndDelta:
    def test_counterfactual_branch_confidence_bounds(self) -> None:
        branch = _branch()
        assert branch.baseline_snapshot_ref == "snapshot-1"
        assert branch.affected_entity_ids == ("entity-1",)
        assert branch.confidence_lower <= branch.confidence_upper

    def test_counterfactual_rejects_inverted_confidence(self) -> None:
        with pytest.raises(ValueError, match="confidence_lower"):
            CounterfactualBranch(
                branch_id="branch-1",
                baseline_snapshot_ref="snapshot-1",
                intervention="remove dependency edge",
                affected_entity_ids=(),
                affected_relation_ids=(),
                predicted_delta_refs=(),
                reversible_step_ids=(),
                irreversible_risk_ids=(),
                confidence_lower=0.9,
                confidence_upper=0.4,
            )

    def test_world_model_delta_requires_evidence(self) -> None:
        delta = GovernedWorldModelDelta(
            delta_id="delta-1",
            source_episode_id="episode-1",
            source_evidence_ids=("evidence-1",),
            prior_snapshot_ref="snapshot-1",
            proposed_entity_change_refs=("entity-change-1",),
            proposed_relation_change_refs=(),
            proposed_confidence_change_refs=(),
            contradictions_created=(),
            contradictions_resolved=(),
            governance_decision_ref="gov-1",
        )
        assert delta.source_evidence_ids == ("evidence-1",)
        assert delta.prior_snapshot_ref == "snapshot-1"
        assert delta.governance_decision_ref == "gov-1"


class TestFailureAndTradeoffContracts:
    def test_failure_mode_and_map_validate_references(self) -> None:
        failure = FailureMode(
            failure_id="failure-1",
            source_ref="constraint-1",
            severity=FailureSeverity.CRITICAL,
            trigger_constraint_ids=("constraint-1",),
            affected_entity_ids=("entity-1",),
            cascade_failure_ids=("failure-2",),
            hidden_assumption_ids=(),
            invariant_violation_ids=("invariant-1",),
            mitigation_refs=("mitigation-1",),
            likelihood=0.9,
            impact=1.0,
            reversible=False,
            detected_at=TS,
        )
        failure_map = FailureReasoningMap(
            map_id="failure-map-1",
            source_episode_id="episode-1",
            failure_modes=(failure,),
            blocked_failure_ids=("failure-1",),
            dominant_failure_id="failure-1",
            residual_risk=0.9,
            generated_at=TS,
        )
        assert failure_map.dominant_failure_id == "failure-1"
        assert failure_map.blocked_failure_ids == ("failure-1",)
        assert failure_map.residual_risk == 0.9

    def test_failure_map_rejects_unknown_dominant_failure(self) -> None:
        failure = FailureMode(
            failure_id="failure-1",
            source_ref="constraint-1",
            severity=FailureSeverity.MODERATE,
            trigger_constraint_ids=("constraint-1",),
            affected_entity_ids=(),
            cascade_failure_ids=(),
            hidden_assumption_ids=(),
            invariant_violation_ids=(),
            mitigation_refs=(),
            likelihood=0.5,
            impact=0.6,
            reversible=True,
            detected_at=TS,
        )
        with pytest.raises(ValueError, match="dominant_failure_id"):
            FailureReasoningMap(
                map_id="failure-map-1",
                source_episode_id="episode-1",
                failure_modes=(failure,),
                blocked_failure_ids=(),
                dominant_failure_id="missing",
                residual_risk=0.3,
                generated_at=TS,
            )

    def test_tradeoff_option_and_report_validate_references(self) -> None:
        option = TradeoffOption(
            option_id="option-1",
            label="safe option",
            benefit=0.8,
            cost=0.3,
            risk=0.2,
            confidence=0.9,
            constraint_refs=("constraint-1",),
        )
        report = TradeoffReasoningReport(
            report_id="tradeoff-1",
            source_episode_id="episode-1",
            option_ids=(option.option_id, "option-2"),
            selected_option_id=option.option_id,
            rejected_option_ids=("option-2",),
            pareto_frontier_option_ids=(option.option_id,),
            selection_rationale="max_utility_with_safety_floor",
            selected_utility=0.8,
            safety_margin=0.8,
            generated_at=TS,
        )
        assert option.constraint_refs == ("constraint-1",)
        assert report.selected_option_id == "option-1"
        assert report.rejected_option_ids == ("option-2",)

    def test_tradeoff_report_rejects_selected_rejected_overlap(self) -> None:
        with pytest.raises(ValueError, match="selected_option_id must not be rejected"):
            TradeoffReasoningReport(
                report_id="tradeoff-1",
                source_episode_id="episode-1",
                option_ids=("option-1", "option-2"),
                selected_option_id="option-1",
                rejected_option_ids=("option-1",),
                pareto_frontier_option_ids=("option-1",),
                selection_rationale="max_utility_with_safety_floor",
                selected_utility=0.8,
                safety_margin=0.8,
                generated_at=TS,
            )

    def test_uncertainty_and_self_diagnosis_reports_validate(self) -> None:
        uncertainty = UncertaintyPropagationReport(
            report_id="uncertainty-1",
            source_episode_id="episode-1",
            uncertainty_source_refs=("constraint-1",),
            ambiguity_refs=("option-1",),
            confidence_lower=0.3,
            confidence_upper=0.7,
            accumulated_uncertainty=0.4,
            evidence_gap_refs=("constraint-1",),
            generated_at=TS,
        )
        diagnosis = SelfDiagnosisReport(
            report_id="diagnosis-1",
            source_episode_id="episode-1",
            uncertainty_report_ref=uncertainty.report_id,
            failure_map_ref="failure-map-1",
            tradeoff_report_ref="tradeoff-1",
            finding_refs=("uncertainty_high",),
            broken_assumption_refs=("constraint-1",),
            resource_pressure=0.5,
            hallucination_risk=0.4,
            severity=DiagnosisSeverity.WARNING,
            escalation_required=False,
            generated_at=TS,
        )
        assert uncertainty.confidence_lower <= uncertainty.confidence_upper
        assert diagnosis.uncertainty_report_ref == "uncertainty-1"
        assert diagnosis.severity == DiagnosisSeverity.WARNING

    def test_uncertainty_rejects_inverted_confidence(self) -> None:
        with pytest.raises(ValueError, match="confidence_lower"):
            UncertaintyPropagationReport(
                report_id="uncertainty-1",
                source_episode_id="episode-1",
                uncertainty_source_refs=(),
                ambiguity_refs=(),
                confidence_lower=0.8,
                confidence_upper=0.2,
                accumulated_uncertainty=0.4,
                evidence_gap_refs=(),
                generated_at=TS,
            )

    def test_adaptive_replan_recommendation_validates_trigger_state(self) -> None:
        recommendation = AdaptiveReplanRecommendation(
            recommendation_id="replan-1",
            source_episode_id="episode-1",
            uncertainty_report_ref="uncertainty-1",
            self_diagnosis_ref="diagnosis-1",
            failure_map_ref="failure-map-1",
            tradeoff_report_ref="tradeoff-1",
            trigger=ReplanTrigger.UNCERTAINTY_HIGH,
            recommended_plan_ref="episode-1:replan",
            blocked_plan_ref="episode-1:execution-plan",
            reason_refs=("uncertainty-1",),
            urgency=0.7,
            replan_required=True,
            generated_at=TS,
        )
        assert recommendation.replan_required is True
        assert recommendation.trigger == ReplanTrigger.UNCERTAINTY_HIGH
        assert recommendation.blocked_plan_ref == "episode-1:execution-plan"

    def test_replan_required_needs_non_none_trigger_and_blocked_plan(self) -> None:
        with pytest.raises(ValueError, match="blocked_plan_ref"):
            AdaptiveReplanRecommendation(
                recommendation_id="replan-1",
                source_episode_id="episode-1",
                uncertainty_report_ref="uncertainty-1",
                self_diagnosis_ref="diagnosis-1",
                failure_map_ref="failure-map-1",
                tradeoff_report_ref="tradeoff-1",
                trigger=ReplanTrigger.UNCERTAINTY_HIGH,
                recommended_plan_ref="episode-1:replan",
                blocked_plan_ref=None,
                reason_refs=("uncertainty-1",),
                urgency=0.7,
                replan_required=True,
                generated_at=TS,
            )


class TestTemporalCoordinationContracts:
    def test_temporal_event_and_report_validate_references(self) -> None:
        event = CoordinationTemporalEvent(
            event_id="event-1",
            occurred_at=TS,
            state_ref="state-1",
            predecessor_event_ids=(),
            delayed_effect_refs=("effect-1",),
            persistence_refs=("persistence-1",),
        )
        report = TemporalStateEvolutionReport(
            report_id="temporal-1",
            source_episode_id="episode-1",
            event_ids=(event.event_id,),
            ordered_event_ids=(event.event_id,),
            violated_event_ids=(),
            incomplete_event_ids=(),
            delayed_effect_refs=("effect-1",),
            persistence_refs=("persistence-1",),
            status=TemporalCheckStatus.ORDERED,
            deadline_pressure=0.2,
            generated_at=TS,
        )
        assert event.state_ref == "state-1"
        assert report.status == TemporalCheckStatus.ORDERED
        assert report.deadline_pressure == 0.2

    def test_temporal_report_rejects_unknown_ordered_event(self) -> None:
        with pytest.raises(ValueError, match="ordered_event_ids"):
            TemporalStateEvolutionReport(
                report_id="temporal-1",
                source_episode_id="episode-1",
                event_ids=("event-1",),
                ordered_event_ids=("missing-event",),
                violated_event_ids=(),
                incomplete_event_ids=(),
                delayed_effect_refs=(),
                persistence_refs=(),
                status=TemporalCheckStatus.ORDERED,
                deadline_pressure=0.0,
                generated_at=TS,
            )


class TestCausalGraphDynamicsContracts:
    def test_causal_node_edge_and_report_validate_references(self) -> None:
        node = CoordinationCausalNode(
            node_id="node-1",
            label="constraint source",
            role_refs=("constraint-1",),
            protected=True,
        )
        edge = CoordinationCausalEdge(
            edge_id="edge-1",
            cause_node_id="node-1",
            effect_node_id="node-2",
            strength=0.7,
            evidence_refs=("evidence-1",),
            delay_ref="delay-1",
        )
        report = CausalGraphDynamicsReport(
            report_id="causal-report-1",
            source_episode_id="episode-1",
            node_ids=("node-1", "node-2"),
            edge_ids=(edge.edge_id,),
            feedback_cycle_node_ids=(),
            feedback_edge_ids=(),
            bottleneck_node_ids=(),
            bridge_node_ids=(),
            orphan_node_ids=(),
            protected_node_ids=(node.node_id,),
            status=CausalDynamicsStatus.ACYCLIC,
            structural_fragility=0.1,
            generated_at=TS,
        )
        assert node.protected is True
        assert edge.strength == 0.7
        assert report.status == CausalDynamicsStatus.ACYCLIC
        assert report.protected_node_ids == ("node-1",)

    def test_causal_report_rejects_unknown_cycle_node(self) -> None:
        with pytest.raises(ValueError, match="feedback_cycle_node_ids"):
            CausalGraphDynamicsReport(
                report_id="causal-report-1",
                source_episode_id="episode-1",
                node_ids=("node-1",),
                edge_ids=("edge-1",),
                feedback_cycle_node_ids=("missing-node",),
                feedback_edge_ids=(),
                bottleneck_node_ids=(),
                bridge_node_ids=(),
                orphan_node_ids=(),
                protected_node_ids=(),
                status=CausalDynamicsStatus.FEEDBACK_PRESENT,
                structural_fragility=0.0,
                generated_at=TS,
            )


class TestAbstractionControlContracts:
    def test_abstraction_layer_and_report_validate_references(self) -> None:
        layer = CoordinationAbstractionLayer(
            layer_id="layer-micro",
            scale=AbstractionScale.MICRO,
            symbol_refs=("symbol-1",),
            evidence_refs=("evidence-1",),
        )
        report = AbstractionControlReport(
            report_id="abstraction-report-1",
            source_episode_id="episode-1",
            layer_ids=("layer-micro", "layer-meso", "layer-macro"),
            micro_layer_ids=(layer.layer_id,),
            meso_layer_ids=("layer-meso",),
            macro_layer_ids=("layer-macro",),
            missing_scale_refs=(),
            collapsed_layer_ids=(),
            orphan_layer_ids=(),
            status=AbstractionControlStatus.CONSISTENT,
            scale_coverage=1.0,
            compression_ratio=0.2,
            generated_at=TS,
        )
        assert layer.scale == AbstractionScale.MICRO
        assert report.status == AbstractionControlStatus.CONSISTENT
        assert report.scale_coverage == 1.0
        assert report.micro_layer_ids == ("layer-micro",)

    def test_abstraction_report_rejects_unknown_collapsed_layer(self) -> None:
        with pytest.raises(ValueError, match="collapsed_layer_ids"):
            AbstractionControlReport(
                report_id="abstraction-report-1",
                source_episode_id="episode-1",
                layer_ids=("layer-1",),
                micro_layer_ids=("layer-1",),
                meso_layer_ids=(),
                macro_layer_ids=(),
                missing_scale_refs=("meso", "macro"),
                collapsed_layer_ids=("missing-layer",),
                orphan_layer_ids=(),
                status=AbstractionControlStatus.COLLAPSED,
                scale_coverage=0.33,
                compression_ratio=0.0,
                generated_at=TS,
            )


class TestResourceBoundedControlContracts:
    def test_resource_limit_and_report_validate_references(self) -> None:
        limit = CoordinationResourceLimit(
            limit_id="limit-compute",
            kind=CoordinationResourceKind.COMPUTE,
            budget=10.0,
            used=8.0,
            unit="steps",
            hard_limit=True,
        )
        report = ResourceBoundedControlReport(
            report_id="resource-report-1",
            source_episode_id="episode-1",
            limit_ids=(limit.limit_id,),
            degraded_limit_ids=(limit.limit_id,),
            exhausted_limit_ids=(),
            overrun_limit_ids=(),
            hard_block_limit_ids=(),
            status=ResourceBoundStatus.DEGRADED,
            max_pressure=0.8,
            generated_at=TS,
        )
        assert limit.kind == CoordinationResourceKind.COMPUTE
        assert limit.hard_limit is True
        assert report.status == ResourceBoundStatus.DEGRADED
        assert report.max_pressure == 0.8

    def test_resource_report_rejects_unknown_hard_block_limit(self) -> None:
        with pytest.raises(ValueError, match="hard_block_limit_ids"):
            ResourceBoundedControlReport(
                report_id="resource-report-1",
                source_episode_id="episode-1",
                limit_ids=("limit-1",),
                degraded_limit_ids=(),
                exhausted_limit_ids=(),
                overrun_limit_ids=(),
                hard_block_limit_ids=("missing-limit",),
                status=ResourceBoundStatus.EXHAUSTED,
                max_pressure=1.0,
                generated_at=TS,
            )


class TestSemanticGroundingContracts:
    def test_grounding_claim_and_report_validate_references(self) -> None:
        claim = CoordinationGroundingClaim(
            claim_id="grounding-1",
            symbol_ref="symbol-1",
            kind=SemanticGroundingKind.OBSERVABLE_STATE,
            target_ref="state-1",
            confidence=0.9,
            evidence_refs=("evidence-1",),
        )
        report = SemanticGroundingReport(
            report_id="grounding-report-1",
            source_episode_id="episode-1",
            claim_ids=(claim.claim_id,),
            grounded_claim_ids=(claim.claim_id,),
            weak_claim_ids=(),
            missing_symbol_refs=(),
            status=SemanticGroundingStatus.GROUNDED,
            grounding_coverage=1.0,
            min_confidence=0.9,
            generated_at=TS,
        )
        assert claim.kind == SemanticGroundingKind.OBSERVABLE_STATE
        assert claim.confidence == 0.9
        assert report.status == SemanticGroundingStatus.GROUNDED
        assert report.grounding_coverage == 1.0

    def test_grounding_report_rejects_unknown_grounded_claim(self) -> None:
        with pytest.raises(ValueError, match="grounded_claim_ids"):
            SemanticGroundingReport(
                report_id="grounding-report-1",
                source_episode_id="episode-1",
                claim_ids=("claim-1",),
                grounded_claim_ids=("missing-claim",),
                weak_claim_ids=(),
                missing_symbol_refs=(),
                status=SemanticGroundingStatus.GROUNDED,
                grounding_coverage=1.0,
                min_confidence=1.0,
                generated_at=TS,
            )


class TestMultiPerspectiveReasoningContracts:
    def test_perspective_and_report_validate_references(self) -> None:
        perspective = CoordinationPerspective(
            perspective_id="perspective-model",
            kind=PerspectiveKind.MODEL,
            model_ref="model-1",
            assumption_refs=("assumption-1",),
            incentive_refs=("incentive-1",),
            scale_refs=("macro",),
            conclusion_refs=("conclusion-1",),
            confidence=0.9,
        )
        report = MultiPerspectiveReasoningReport(
            report_id="perspective-report-1",
            source_episode_id="episode-1",
            perspective_ids=(perspective.perspective_id,),
            represented_kind_refs=("model",),
            missing_kind_refs=("assumption",),
            divergent_perspective_ids=(),
            low_confidence_perspective_ids=(),
            shared_conclusion_refs=("conclusion-1",),
            status=PerspectiveComparisonStatus.UNDERCOVERED,
            agreement_score=1.0,
            generated_at=TS,
        )
        assert perspective.kind == PerspectiveKind.MODEL
        assert perspective.confidence == 0.9
        assert report.status == PerspectiveComparisonStatus.UNDERCOVERED
        assert report.shared_conclusion_refs == ("conclusion-1",)

    def test_perspective_report_rejects_unknown_divergent_perspective(self) -> None:
        with pytest.raises(ValueError, match="divergent_perspective_ids"):
            MultiPerspectiveReasoningReport(
                report_id="perspective-report-1",
                source_episode_id="episode-1",
                perspective_ids=("perspective-1",),
                represented_kind_refs=("model",),
                missing_kind_refs=(),
                divergent_perspective_ids=("missing-perspective",),
                low_confidence_perspective_ids=(),
                shared_conclusion_refs=(),
                status=PerspectiveComparisonStatus.DIVERGENT,
                agreement_score=0.0,
                generated_at=TS,
            )


class TestCompressionPatternDiscoveryContracts:
    def test_pattern_candidate_and_report_validate_fields(self) -> None:
        pattern = CoordinationPatternCandidate(
            pattern_id="pattern-1",
            symbol_refs=("symbol-1", "symbol-2"),
            invariant_refs=("invariant-1",),
            motif_refs=("motif-1",),
            reusable_structure_refs=("structure-1",),
            redundancy_refs=("symbol-2",),
        )
        report = CompressionPatternDiscoveryReport(
            report_id="compression-report-1",
            source_episode_id="episode-1",
            pattern_ids=(pattern.pattern_id,),
            invariant_refs=("invariant-1",),
            motif_refs=("motif-1",),
            reusable_structure_refs=("structure-1",),
            redundant_symbol_refs=("symbol-2",),
            status=PatternDiscoveryStatus.REDUNDANT,
            compression_ratio=0.5,
            reuse_score=1.0,
            generated_at=TS,
        )
        assert pattern.pattern_id == "pattern-1"
        assert report.status == PatternDiscoveryStatus.REDUNDANT
        assert report.compression_ratio == 0.5
        assert report.reusable_structure_refs == ("structure-1",)

    def test_pattern_report_rejects_invalid_status(self) -> None:
        with pytest.raises(ValueError, match="status"):
            CompressionPatternDiscoveryReport(
                report_id="compression-report-1",
                source_episode_id="episode-1",
                pattern_ids=("pattern-1",),
                invariant_refs=(),
                motif_refs=(),
                reusable_structure_refs=(),
                redundant_symbol_refs=(),
                status="stable",
                compression_ratio=1.0,
                reuse_score=1.0,
                generated_at=TS,
            )


class TestCorrectionRepairContracts:
    def test_correction_action_and_report_validate_references(self) -> None:
        action = CorrectionRepairAction(
            action_id="action-1",
            kind=CorrectionActionKind.CONTRADICTION_REPAIR,
            target_ref="contradiction-1",
            reason_refs=("contradiction-1",),
            reversible=True,
        )
        report = CorrectionRepairReport(
            report_id="correction-report-1",
            source_episode_id="episode-1",
            action_ids=(action.action_id,),
            contradiction_refs=("contradiction-1",),
            rollback_action_ids=(),
            repair_action_ids=(action.action_id,),
            evidence_request_action_ids=(),
            status=CorrectionRepairStatus.REPAIR_RECOMMENDED,
            repair_pressure=0.4,
            generated_at=TS,
        )
        assert action.kind == CorrectionActionKind.CONTRADICTION_REPAIR
        assert action.reversible is True
        assert report.status == CorrectionRepairStatus.REPAIR_RECOMMENDED
        assert report.repair_action_ids == ("action-1",)

    def test_correction_report_rejects_unknown_rollback_action(self) -> None:
        with pytest.raises(ValueError, match="rollback_action_ids"):
            CorrectionRepairReport(
                report_id="correction-report-1",
                source_episode_id="episode-1",
                action_ids=("action-1",),
                contradiction_refs=(),
                rollback_action_ids=("missing-action",),
                repair_action_ids=(),
                evidence_request_action_ids=(),
                status=CorrectionRepairStatus.ROLLBACK_RECOMMENDED,
                repair_pressure=1.0,
                generated_at=TS,
            )


class TestDynamicWorldModelContinuityContracts:
    def test_lineage_identity_and_report_validate_references(self) -> None:
        link = WorldSnapshotLineageLink(
            link_id="link-1",
            prior_snapshot_ref="snapshot-1",
            next_snapshot_ref="snapshot-2",
            delta_ref="delta-1",
        )
        check = WorldIdentityContinuityCheck(
            check_id="identity-1",
            entity_ref="entity-1",
            prior_snapshot_ref="snapshot-1",
            next_snapshot_ref="snapshot-2",
            preserved=True,
            evidence_refs=("evidence-1",),
        )
        report = DynamicWorldModelContinuityReport(
            report_id="continuity-report-1",
            source_episode_id="episode-1",
            lineage_link_ids=(link.link_id,),
            identity_check_ids=(check.check_id,),
            broken_lineage_link_ids=(),
            drifted_identity_check_ids=(),
            persistent_causal_chain_refs=("chain-1",),
            status=WorldContinuityStatus.CONTINUOUS,
            continuity_score=1.0,
            generated_at=TS,
        )
        assert link.delta_ref == "delta-1"
        assert check.preserved is True
        assert report.status == WorldContinuityStatus.CONTINUOUS
        assert report.persistent_causal_chain_refs == ("chain-1",)

    def test_continuity_report_rejects_unknown_drift_check(self) -> None:
        with pytest.raises(ValueError, match="drifted_identity_check_ids"):
            DynamicWorldModelContinuityReport(
                report_id="continuity-report-1",
                source_episode_id="episode-1",
                lineage_link_ids=(),
                identity_check_ids=("identity-1",),
                broken_lineage_link_ids=(),
                drifted_identity_check_ids=("missing-identity",),
                persistent_causal_chain_refs=(),
                status=WorldContinuityStatus.IDENTITY_DRIFT,
                continuity_score=0.0,
                generated_at=TS,
            )


class TestOrchestrationReadinessContracts:
    def test_readiness_report_validates_fields(self) -> None:
        report = OrchestrationReadinessReport(
            report_id="readiness-report-1",
            source_episode_id="episode-1",
            report_refs=("constraint-report-1", "uncertainty-1"),
            hard_block_refs=(),
            replan_refs=(),
            soft_risk_refs=("risk-1",),
            verdict=OrchestrationReadinessVerdict.READY,
            readiness_score=0.9,
            generated_at=TS,
        )
        assert report.verdict == OrchestrationReadinessVerdict.READY
        assert report.report_refs == ("constraint-report-1", "uncertainty-1")
        assert report.readiness_score == 0.9

    def test_readiness_report_rejects_invalid_verdict(self) -> None:
        with pytest.raises(ValueError, match="verdict"):
            OrchestrationReadinessReport(
                report_id="readiness-report-1",
                source_episode_id="episode-1",
                report_refs=(),
                hard_block_refs=(),
                replan_refs=(),
                soft_risk_refs=(),
                verdict="ready",
                readiness_score=1.0,
                generated_at=TS,
            )


class TestIntelligenceCoordinationEpisode:
    def test_valid_episode(self) -> None:
        episode = IntelligenceCoordinationEpisode(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.BOOLEAN_FEASIBILITY,
            method_candidates=(_candidate(),),
            selected_method_id="method-sat",
            rejected_method_ids=(),
            counterfactual_branches=(_branch(),),
            failure_map_ref="failure-map-1",
            tradeoff_report_ref="tradeoff-1",
            execution_plan_ref="plan-1",
            diagnosis_report_ref="diagnosis-1",
            world_model_delta_ref=None,
            proof_record_ref="proof-1",
            terminal_outcome=SolverTerminalOutcome.SOLVED_UNVERIFIED,
            created_at=TS,
            metadata={"tenant_id": "tenant-1"},
        )
        assert episode.selected_method_id == "method-sat"
        assert isinstance(episode.metadata, MappingProxyType)
        assert episode.counterfactual_branches[0].branch_id == "branch-1"

    def test_selected_method_must_reference_candidate(self) -> None:
        with pytest.raises(ValueError, match="selected_method_id"):
            IntelligenceCoordinationEpisode(
                episode_id="episode-1",
                goal_id="goal-1",
                input_symbol_mesh_ref="mesh-1",
                world_snapshot_ref="snapshot-1",
                active_constraints_ref="constraints-1",
                causal_graph_ref="causal-1",
                uncertainty_envelope_ref="uncertainty-1",
                problem_signature=MethodProblemSignature.BOOLEAN_FEASIBILITY,
                method_candidates=(_candidate(),),
                selected_method_id="missing-method",
                rejected_method_ids=(),
                counterfactual_branches=(),
                failure_map_ref="failure-map-1",
                tradeoff_report_ref="tradeoff-1",
                execution_plan_ref="plan-1",
                diagnosis_report_ref="diagnosis-1",
                world_model_delta_ref=None,
                proof_record_ref="proof-1",
                terminal_outcome=SolverTerminalOutcome.SOLVED_UNVERIFIED,
                created_at=TS,
            )

    def test_episode_is_frozen(self) -> None:
        episode = IntelligenceCoordinationEpisode(
            episode_id="episode-1",
            goal_id="goal-1",
            input_symbol_mesh_ref="mesh-1",
            world_snapshot_ref="snapshot-1",
            active_constraints_ref="constraints-1",
            causal_graph_ref="causal-1",
            uncertainty_envelope_ref="uncertainty-1",
            problem_signature=MethodProblemSignature.BOOLEAN_FEASIBILITY,
            method_candidates=(_candidate(),),
            selected_method_id="method-sat",
            rejected_method_ids=(),
            counterfactual_branches=(),
            failure_map_ref="failure-map-1",
            tradeoff_report_ref="tradeoff-1",
            execution_plan_ref="plan-1",
            diagnosis_report_ref="diagnosis-1",
            world_model_delta_ref=None,
            proof_record_ref="proof-1",
            terminal_outcome=SolverTerminalOutcome.SOLVED_UNVERIFIED,
            created_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            episode.goal_id = "changed"  # type: ignore[misc]
