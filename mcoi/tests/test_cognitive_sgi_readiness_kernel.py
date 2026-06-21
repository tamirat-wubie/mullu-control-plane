"""Purpose: verify the governed cognitive SGI readiness kernel.
Governance scope: cross-domain transfer admission, concept-birth admission,
    self-question generation, autonomy classification, and reward/homeostasis
    validation.
Dependencies: pytest and mcoi_runtime cognitive SGI readiness contracts.
Invariants:
  - Reports may classify Proto-SGI readiness but must not claim achieved SGI.
  - Effect-bearing and core-mutation actions remain bounded by governance.
  - Blocked evidence lanes emit explicit blockers and self-questions.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.cognitive_sgi_readiness_kernel import (
    ActionClass,
    ActionProposal,
    AutonomyClass,
    AutonomyDecisionStatus,
    ConceptBirthCandidate,
    CrossDomainTransferCandidate,
    HomeostaticVector,
    ReadinessState,
    RewardSignal,
    Verdict,
    build_cognitive_sgi_readiness_report,
    classify_governed_autonomy,
)


def _stable_homeostasis() -> HomeostaticVector:
    return HomeostaticVector(
        stability=0.86,
        coherence=0.84,
        adaptability=0.78,
        energy_cost=0.20,
        prediction_accuracy=0.82,
        memory_integrity=0.88,
        governance_safety=0.91,
    )


def test_readiness_report_admits_level4_candidate_without_claiming_sgi() -> None:
    transfer = CrossDomainTransferCandidate(
        source_domain="physics",
        target_domain="software_architecture",
        source_pattern="equilibrium_under_constraints",
        target_mapping="bounded_service_mesh_stability",
        invariant_refs=("invariant:conservation_of_boundary",),
        confidence=0.82,
    )
    concept = ConceptBirthCandidate(
        concept_id="coherence_boundary_symbol",
        evidence_refs=("evidence:missing_boundary_symbol_failure",),
        necessity_score=0.86,
        overlap_score=0.12,
        governance_refs=("ontology_review_ref", "learning_admission_ref"),
    )
    action = ActionProposal(
        action_id="inspect_cognitive_trace",
        action_class=ActionClass.EPISTEMIC,
        reversible=True,
    )

    report = build_cognitive_sgi_readiness_report(
        homeostasis=_stable_homeostasis(),
        transfer_candidates=(transfer,),
        concept_birth_candidates=(concept,),
        action_proposals=(action,),
    )

    assert report.readiness_state is ReadinessState.LEVEL_4_CANDIDATE
    assert report.transfer_verdicts[0].verdict is Verdict.ADMITTED
    assert report.concept_birth_verdicts[0].verdict is Verdict.ADMITTED
    assert report.autonomy_decisions[0].status is AutonomyDecisionStatus.ALLOW
    assert report.blockers == ()
    assert "sgi" not in report.readiness_state.value.replace("proto_sgi", "proto")


def test_blocked_transfer_concept_and_autonomy_emit_questions_and_evidence() -> None:
    unstable_homeostasis = HomeostaticVector(
        stability=0.50,
        coherence=0.52,
        adaptability=0.61,
        energy_cost=0.80,
        prediction_accuracy=0.40,
        memory_integrity=0.50,
        governance_safety=0.60,
    )
    blocked_transfer = CrossDomainTransferCandidate(
        source_domain="physics",
        target_domain="physics",
        source_pattern="symmetry",
        target_mapping="same_domain_restatement",
        invariant_refs=("invariant:symmetry_ref",),
        contradiction_refs=("contradiction:target_not_distinct",),
        confidence=0.44,
    )
    blocked_concept = ConceptBirthCandidate(
        concept_id="duplicate_symbol_candidate",
        evidence_refs=("evidence:weak_failure_case",),
        necessity_score=0.30,
        overlap_score=0.90,
        governance_refs=(),
    )
    blocked_action = ActionProposal(
        action_id="send_external_effect_without_witness",
        action_class=ActionClass.EXTERNAL_EFFECT,
        reversible=False,
    )

    report = build_cognitive_sgi_readiness_report(
        homeostasis=unstable_homeostasis,
        transfer_candidates=(blocked_transfer,),
        concept_birth_candidates=(blocked_concept,),
        action_proposals=(blocked_action,),
    )
    reason_refs = {question.reason_ref for question in report.self_questions}

    assert report.readiness_state is ReadinessState.BLOCKED
    assert "transfer:source_and_target_domain_must_differ" in report.blockers
    assert "concept_birth:concept_overlap_above_threshold" in report.blockers
    assert "concept_birth:missing_governance:learning_admission_ref" in report.blockers
    assert "concept_birth:missing_governance:ontology_review_ref" in report.blockers
    assert "autonomy:missing_authority:uao_policy_ref" in report.blockers
    assert "contradiction_resolution_receipt" in report.required_next_evidence
    assert "learning_admission_ref" in report.required_next_evidence
    assert "ontology_review_ref" in report.required_next_evidence
    assert "prediction_accuracy_below_threshold" in reason_refs
    assert "governance_safety_below_threshold" in reason_refs


def test_core_mutation_is_restricted_and_prohibited_tags_override_authority() -> None:
    governed_core_mutation = ActionProposal(
        action_id="simulate_core_rule_update",
        action_class=ActionClass.CORE_MUTATION,
        reversible=True,
        authority_refs=("phi_gov_authority_ref",),
        evidence_refs=("mutation_sandbox_receipt", "rollback_ref", "invariant_check_passed"),
    )
    prohibited_action = ActionProposal(
        action_id="hidden_self_expansion",
        action_class=ActionClass.CORE_MUTATION,
        reversible=True,
        authority_refs=("phi_gov_authority_ref",),
        evidence_refs=("mutation_sandbox_receipt", "rollback_ref", "invariant_check_passed"),
        tags=("silent_self_expansion",),
    )

    governed_decision = classify_governed_autonomy(governed_core_mutation)
    prohibited_decision = classify_governed_autonomy(prohibited_action)

    assert governed_decision.autonomy_class is AutonomyClass.RESTRICTED
    assert governed_decision.status is AutonomyDecisionStatus.SIMULATION_ONLY
    assert governed_decision.blockers == ()
    assert prohibited_decision.autonomy_class is AutonomyClass.PROHIBITED
    assert prohibited_decision.status is AutonomyDecisionStatus.BLOCK
    assert "prohibited_tag:silent_self_expansion" in prohibited_decision.blockers


def test_reward_and_homeostasis_validation_are_bounded() -> None:
    reward = RewardSignal(
        immediate_utility=0.80,
        long_term_coherence=0.90,
        causal_accuracy=0.70,
        energy_efficiency=0.60,
        safety_compliance=1.00,
        reversibility=0.80,
    )
    homeostasis = _stable_homeostasis()

    assert 0.0 <= reward.weighted_score() <= 1.0
    assert reward.weighted_score() == pytest.approx(0.815)
    assert 0.0 <= homeostasis.balance_score() <= 1.0
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        HomeostaticVector(
            stability=1.20,
            coherence=0.80,
            adaptability=0.80,
            energy_cost=0.20,
            prediction_accuracy=0.80,
            memory_integrity=0.80,
            governance_safety=0.80,
        )
