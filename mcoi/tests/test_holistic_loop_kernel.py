"""Purpose: verify the holistic loop engineering kernel read model.
Governance scope: loop manifest contracts, blocker derivation, evidence
    requirements, closure conditions, and registry immutability.
Dependencies: pytest and mcoi_runtime holistic loop contracts.
Invariants:
  - Default loop manifests are registered without changing runtime behavior.
  - Missing evidence is exposed as blockers, never as verified closure.
  - Complete evidence can verify the read model without mutating loop behavior.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from mcoi_runtime.contracts.holistic_loop import (
    LoopAuditEvolutionView,
    LoopAuthorityBinding,
    LoopClosureConditionBinding,
    LoopClosureEvidencePack,
    LoopClosureReport,
    LoopEvidenceBinding,
    LoopLearningBinding,
    LoopMode,
    LoopModeBinding,
    LoopOperatorClosureReadinessView,
    LoopPhase,
    LoopProofObligationView,
    LoopReceiptLineageBinding,
    LoopRecoveryReadinessView,
    LoopRiskBinding,
    LoopRollbackBinding,
    LoopSummary,
    LoopState,
    LoopStatus,
    LoopStatusBinding,
    LoopStepReceipt,
    LoopTransitionBinding,
)
from mcoi_runtime.core.holistic_loop_registry import (
    build_default_loop_read_model,
    build_default_loop_registry,
)


EXPECTED_LOOP_IDS = {
    "audit_proof_verification_loop",
    "authority_obligation_loop",
    "universal_action_orchestration_loop",
    "deployment_witness_loop",
    "runtime_conformance_loop",
    "cognitive_outcome_loop",
    "governed_code_change_loop",
}
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_default_registry_exposes_governed_loop_manifests() -> None:
    registry = build_default_loop_registry()
    loop_ids = {manifest.loop_id for manifest in registry.list_manifests()}

    assert loop_ids == EXPECTED_LOOP_IDS
    assert registry.get_manifest("audit_proof_verification_loop").owner == "proof_governance"
    assert "proof_verifier_ref" in registry.get_manifest(
        "audit_proof_verification_loop"
    ).required_authority
    assert "trust_ledger_anchor_verified" in registry.get_manifest(
        "audit_proof_verification_loop"
    ).required_evidence
    assert registry.get_manifest("authority_obligation_loop").owner == "governance"
    assert "authority_operator_ref" in registry.get_manifest(
        "authority_obligation_loop"
    ).required_authority
    assert "overdue_obligation_resolution_receipt" in registry.get_manifest(
        "authority_obligation_loop"
    ).required_evidence
    assert registry.get_manifest("universal_action_orchestration_loop").owner == "action_governance"
    assert "uao_policy_ref" in registry.get_manifest(
        "universal_action_orchestration_loop"
    ).required_authority
    assert "no_bypass_detector_passed" in registry.get_manifest(
        "universal_action_orchestration_loop"
    ).required_evidence
    assert registry.get_manifest("deployment_witness_loop").purpose.startswith("Describe endpoint publication")
    assert "runtime_conformance_verified" in registry.get_manifest(
        "deployment_witness_loop"
    ).required_evidence
    assert "mechanical_verification_completed" in registry.get_manifest(
        "cognitive_outcome_loop"
    ).closure_conditions
    assert "uao_ref" in registry.get_manifest("governed_code_change_loop").required_authority


def test_missing_evidence_is_reported_as_blocker_not_success() -> None:
    read_model = build_default_loop_read_model()
    deployment_summary = next(
        loop for loop in read_model.loops if loop.loop_id == "deployment_witness_loop"
    )

    assert read_model.total_count == 7
    assert read_model.returned_count == 7
    assert read_model.truncated is False
    assert deployment_summary.status is LoopStatus.BLOCKED
    assert "operator_approval_ref" in deployment_summary.missing_authority
    assert "missing_authority:operator_approval_ref" in deployment_summary.open_blockers
    assert "deployment_witness_published" in deployment_summary.missing_evidence
    assert "missing_evidence:deployment_witness_published" in deployment_summary.open_blockers
    assert deployment_summary.closure_report.closed is False
    assert deployment_summary.closure_report.evidence_complete is False
    assert set(deployment_summary.closure_report.unresolved_gaps) == set(
        deployment_summary.open_blockers
    )


def test_audit_proof_loop_is_registered_read_only_and_blocked() -> None:
    registry = build_default_loop_registry()
    manifest = registry.get_manifest("audit_proof_verification_loop")
    summary = registry.summarize("audit_proof_verification_loop")

    assert manifest.owner == "proof_governance"
    assert manifest.metadata["behavior_rewrite"] is False
    assert "proof_verifier_ref" in manifest.required_authority
    assert "trust_ledger_anchor_verified" in manifest.required_evidence
    assert summary.status is LoopStatus.BLOCKED
    assert "missing_authority:proof_verifier_ref" in summary.open_blockers
    assert "missing_evidence:trust_ledger_anchor_verified" in summary.open_blockers
    assert summary.status_binding.read_only is True
    assert summary.closure_report.closed is False


def test_authority_obligation_loop_is_registered_read_only_and_blocked() -> None:
    registry = build_default_loop_registry()
    manifest = registry.get_manifest("authority_obligation_loop")
    summary = registry.summarize("authority_obligation_loop")

    assert manifest.owner == "governance"
    assert manifest.metadata["behavior_rewrite"] is False
    assert "authority_operator_ref" in manifest.required_authority
    assert "overdue_obligation_resolution_receipt" in manifest.required_evidence
    assert summary.status is LoopStatus.BLOCKED
    assert "missing_authority:authority_operator_ref" in summary.open_blockers
    assert "missing_evidence:overdue_obligation_resolution_receipt" in summary.open_blockers
    assert summary.status_binding.read_only is True
    assert summary.closure_report.closed is False


def test_universal_action_orchestration_loop_is_registered_read_only_and_blocked() -> None:
    registry = build_default_loop_registry()
    manifest = registry.get_manifest("universal_action_orchestration_loop")
    summary = registry.summarize("universal_action_orchestration_loop")

    assert manifest.owner == "action_governance"
    assert manifest.metadata["behavior_rewrite"] is False
    assert "uao_policy_ref" in manifest.required_authority
    assert "no_bypass_detector_passed" in manifest.required_evidence
    assert summary.status is LoopStatus.BLOCKED
    assert "missing_authority:uao_policy_ref" in summary.open_blockers
    assert "missing_evidence:no_bypass_detector_passed" in summary.open_blockers
    assert summary.status_binding.read_only is True
    assert summary.closure_report.closed is False


def test_complete_evidence_verifies_read_model_without_runtime_mutation() -> None:
    registry = build_default_loop_registry()
    authority_refs = {
        manifest.loop_id: tuple(manifest.required_authority)
        for manifest in registry.list_manifests()
    }
    evidence_refs = {
        manifest.loop_id: tuple(manifest.required_evidence)
        for manifest in registry.list_manifests()
    }
    read_model = build_default_loop_read_model(
        observed_authority_refs=authority_refs,
        observed_evidence_refs=evidence_refs,
    )

    assert {summary.loop_id for summary in read_model.loops} == EXPECTED_LOOP_IDS
    assert all(summary.status is LoopStatus.VERIFIED for summary in read_model.loops)
    assert all(summary.missing_authority == () for summary in read_model.loops)
    assert all(summary.missing_evidence == () for summary in read_model.loops)
    assert all(summary.open_blockers == () for summary in read_model.loops)
    assert all(summary.closure_report.closed is False for summary in read_model.loops)
    assert all(summary.closure_report.evidence_complete is True for summary in read_model.loops)
    assert all(summary.closure_report.unresolved_gaps == () for summary in read_model.loops)


def test_loop_evidence_bindings_cover_required_evidence_without_execution() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        binding_refs = {binding.evidence_ref for binding in summary.evidence_bindings}
        required_refs = set(summary.required_evidence)

        assert binding_refs == required_refs
        assert len(summary.evidence_bindings) == len(summary.required_evidence)
        assert all(binding.read_only is True for binding in summary.evidence_bindings)
        assert all(binding.terminal_closure is False for binding in summary.evidence_bindings)
        assert all(binding.proof_surface_refs for binding in summary.evidence_bindings)


def test_loop_authority_bindings_cover_required_authority_without_execution() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        binding_refs = {binding.authority_ref for binding in summary.authority_bindings}
        required_refs = set(summary.required_authority)

        assert binding_refs == required_refs
        assert len(summary.authority_bindings) == len(summary.required_authority)
        assert all(binding.read_only is True for binding in summary.authority_bindings)
        assert all(binding.terminal_closure is False for binding in summary.authority_bindings)
        assert all(binding.proof_surface_refs for binding in summary.authority_bindings)


def test_loop_risk_bindings_cover_risk_class_without_execution() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        binding = summary.risk_binding

        assert binding.risk_ref == summary.risk_class
        assert binding.read_only is True
        assert binding.terminal_closure is False
        assert binding.hazard_refs
        assert binding.mitigation_refs
        assert binding.monitor_refs
        assert binding.source_refs
        assert binding.validator_refs
        assert binding.proof_surface_refs


def test_loop_risk_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for ref in (*summary.risk_binding.source_refs, *summary.risk_binding.validator_refs)
        if "/" in ref
    }

    assert "schemas/gateway_publication_readiness.schema.json" in file_refs
    assert "schemas/sdlc_recovery_handoff_receipt.schema.json" in file_refs
    assert "mcoi/mcoi_runtime/core/cognitive_loop.py" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_authority_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for binding in summary.authority_bindings
        for ref in (*binding.source_refs, *binding.validator_refs)
        if "/" in ref
    }

    assert "scripts/emit_deployment_publication_operator_input_request.py" in file_refs
    assert "schemas/universal_action_orchestration.schema.json" in file_refs
    assert "mcoi/mcoi_runtime/swarm/lease_manager.py" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_rollback_bindings_cover_recovery_policy_without_execution() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        binding = summary.rollback_binding

        assert binding.rollback_ref == summary.rollback_policy
        assert binding.read_only is True
        assert binding.terminal_closure is False
        assert binding.source_refs
        assert binding.validator_refs
        assert binding.proof_surface_refs


def test_loop_learning_bindings_cover_learning_policy_without_execution() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        binding = summary.learning_binding

        assert binding.learning_ref == summary.learning_policy
        assert binding.read_only is True
        assert binding.terminal_closure is False
        assert binding.evidence_input_refs
        assert binding.admission_refs
        assert binding.retention_refs
        assert binding.source_refs
        assert binding.validator_refs
        assert binding.proof_surface_refs


def test_loop_mode_bindings_cover_allowed_modes_without_execution() -> None:
    registry = build_default_loop_registry()

    for manifest in registry.list_manifests():
        summary = registry.summarize(manifest.loop_id)
        binding = summary.mode_binding

        assert binding.projected_mode == summary.mode
        assert binding.allowed_modes == manifest.allowed_modes
        assert summary.mode in binding.allowed_modes
        assert binding.read_only is True
        assert binding.mode_transition is False
        assert binding.terminal_closure is False
        assert binding.separation_refs
        assert binding.real_execution_guard_refs
        assert binding.source_refs
        assert binding.validator_refs
        assert binding.proof_surface_refs


def test_loop_mode_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for ref in (*summary.mode_binding.source_refs, *summary.mode_binding.validator_refs)
        if "/" in ref
    }

    assert "scripts/preflight_deployment_witness.py" in file_refs
    assert "mcoi/mcoi_runtime/core/governed_code_change_loop.py" in file_refs
    assert "schemas/runtime_conformance_certificate.schema.json" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_status_bindings_explain_projected_status_without_execution() -> None:
    blocked_model = build_default_loop_read_model()

    for summary in blocked_model.loops:
        binding = summary.status_binding

        assert binding.projected_status is summary.status
        assert set(binding.blocker_refs) == set(summary.open_blockers)
        assert binding.status_reason == "read_model_blocked_by_unresolved_gaps"
        assert binding.read_only is True
        assert binding.status_transition is False
        assert binding.terminal_closure is False
        assert binding.verification_refs
        assert binding.closure_gate_refs
        assert binding.source_refs
        assert binding.validator_refs
        assert binding.proof_surface_refs

    registry = build_default_loop_registry()
    authority_refs = {
        manifest.loop_id: tuple(manifest.required_authority)
        for manifest in registry.list_manifests()
    }
    evidence_refs = {
        manifest.loop_id: tuple(manifest.required_evidence)
        for manifest in registry.list_manifests()
    }
    verified_model = build_default_loop_read_model(
        observed_authority_refs=authority_refs,
        observed_evidence_refs=evidence_refs,
    )

    assert all(summary.status is LoopStatus.VERIFIED for summary in verified_model.loops)
    assert all(summary.status_binding.projected_status is LoopStatus.VERIFIED for summary in verified_model.loops)
    assert all(summary.status_binding.blocker_refs == () for summary in verified_model.loops)
    assert all(
        summary.status_binding.status_reason == "read_model_verified_terminal_closure_required"
        for summary in verified_model.loops
    )


def test_loop_status_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for ref in (*summary.status_binding.source_refs, *summary.status_binding.validator_refs)
        if "/" in ref
    }

    assert "scripts/preflight_deployment_witness.py" in file_refs
    assert "mcoi/mcoi_runtime/core/cognitive_loop.py" in file_refs
    assert "schemas/runtime_conformance_certificate.schema.json" in file_refs
    assert "mcoi/mcoi_runtime/core/governed_code_change_loop.py" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_transition_bindings_describe_allowed_transitions_without_execution() -> None:
    read_model = build_default_loop_read_model()
    expected_transitions = {
        "open_to_blocked_on_missing_requirements",
        "blocked_to_verified_after_requirements",
        "verified_to_closed_requires_terminal_closure",
    }

    for summary in read_model.loops:
        binding_refs = {binding.transition_ref for binding in summary.transition_bindings}

        assert binding_refs == expected_transitions
        assert len(summary.transition_bindings) == 3
        assert all(set(binding.blocker_refs) == set(summary.open_blockers) for binding in summary.transition_bindings)
        assert all(set(binding.required_authority_refs) <= set(summary.required_authority) for binding in summary.transition_bindings)
        assert all(set(binding.required_evidence_refs) <= set(summary.required_evidence) for binding in summary.transition_bindings)
        assert all(summary.rollback_policy in binding.rollback_refs for binding in summary.transition_bindings)
        assert all(binding.receipt_refs for binding in summary.transition_bindings)
        assert all(binding.read_only is True for binding in summary.transition_bindings)
        assert all(binding.executes_transition is False for binding in summary.transition_bindings)
        assert all(binding.terminal_closure is False for binding in summary.transition_bindings)


def test_loop_transition_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for binding in summary.transition_bindings
        for ref in (*binding.source_refs, *binding.validator_refs)
        if "/" in ref
    }

    assert "scripts/preflight_deployment_witness.py" in file_refs
    assert "schemas/runtime_conformance_certificate.schema.json" in file_refs
    assert "mcoi/mcoi_runtime/core/cognitive_loop.py" in file_refs
    assert "schemas/sdlc_verification_receipt.schema.json" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_receipt_lineage_bindings_cover_step_receipts_without_emission() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        receipts_by_step = {receipt.step: receipt for receipt in summary.step_receipts}
        lineage_by_step = {binding.step: binding for binding in summary.receipt_lineage_bindings}

        assert set(lineage_by_step) == set(receipts_by_step)
        assert len(summary.receipt_lineage_bindings) == len(summary.step_receipts)
        assert all(binding.receipt_hash == receipts_by_step[binding.step].output_hash for binding in summary.receipt_lineage_bindings)
        assert all(set(binding.required_evidence_refs) <= set(summary.required_evidence) for binding in summary.receipt_lineage_bindings)
        assert all(set(binding.observed_evidence_refs) == set(summary.evidence_refs) for binding in summary.receipt_lineage_bindings)
        assert all(set(binding.blocker_refs) == set(summary.open_blockers) for binding in summary.receipt_lineage_bindings)
        assert all(binding.receipt_ref in binding.source_receipt_refs for binding in summary.receipt_lineage_bindings)
        assert all(binding.read_only is True for binding in summary.receipt_lineage_bindings)
        assert all(binding.emits_receipt is False for binding in summary.receipt_lineage_bindings)
        assert all(binding.terminal_closure is False for binding in summary.receipt_lineage_bindings)


def test_loop_closure_evidence_pack_aggregates_required_closure_inputs() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        pack = summary.closure_evidence_pack
        assert pack.loop_id == summary.loop_id
        assert set(pack.required_evidence_refs) == set(summary.required_evidence)
        assert set(pack.observed_evidence_refs) == set(summary.evidence_refs)
        assert set(pack.missing_evidence_refs) == set(summary.missing_evidence)
        assert set(pack.required_authority_refs) == set(summary.required_authority)
        assert set(pack.observed_authority_refs) == set(summary.authority_refs)
        assert set(pack.missing_authority_refs) == set(summary.missing_authority)
        assert set(pack.blocker_refs) == set(summary.open_blockers)
        assert set(pack.closure_condition_refs) == set(summary.closure_conditions)
        assert set(pack.receipt_lineage_refs) == {
            binding.lineage_ref for binding in summary.receipt_lineage_bindings
        }
        assert pack.evidence_complete is summary.closure_report.evidence_complete
        assert pack.authority_complete is False
        assert pack.closure_blocked is True
        assert pack.rollback_available is summary.closure_report.rollback_available
        assert pack.rollback_ref == summary.rollback_policy
        assert pack.read_only is True
        assert pack.emits_receipt is False
        assert pack.terminal_closure is False


def test_loop_closure_evidence_pack_rejects_emission_or_terminal_closure_claim() -> None:
    summary = build_default_loop_read_model().loops[0]
    kwargs = dataclasses.asdict(summary.closure_evidence_pack)

    with pytest.raises(ValueError, match="read-only"):
        LoopClosureEvidencePack(**{**kwargs, "read_only": False})
    with pytest.raises(ValueError, match="emit receipt"):
        LoopClosureEvidencePack(**{**kwargs, "emits_receipt": True})
    with pytest.raises(ValueError, match="terminal closure"):
        LoopClosureEvidencePack(**{**kwargs, "terminal_closure": True})


def test_loop_operator_closure_readiness_view_summarizes_blockers_and_next_action() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        view = summary.operator_closure_readiness_view
        assert view.loop_id == summary.loop_id
        assert view.projected_status is summary.status
        assert set(view.blocker_refs) == set(summary.open_blockers)
        assert set(view.evidence_gap_refs) == set(summary.missing_evidence)
        assert set(view.authority_gap_refs) == set(summary.missing_authority)
        assert set(view.closure_condition_refs) == set(summary.closure_conditions)
        assert view.rollback_ref == summary.rollback_policy
        assert view.rollback_available is summary.closure_report.rollback_available
        assert view.readiness_state == "blocked_by_unresolved_gaps"
        assert view.next_proof_action == "resolve_blockers_before_terminal_closure_review"
        assert "closure_evidence_pack" in view.next_proof_refs
        assert "closure_report" in view.next_proof_refs
        assert set(summary.open_blockers) <= set(view.next_proof_refs)
        assert view.read_only is True
        assert view.mutation_route is False
        assert view.terminal_closure is False


def test_loop_operator_closure_readiness_view_marks_complete_loops_for_review_only() -> None:
    registry = build_default_loop_registry()
    authority_refs = {
        manifest.loop_id: tuple(manifest.required_authority)
        for manifest in registry.list_manifests()
    }
    evidence_refs = {
        manifest.loop_id: tuple(manifest.required_evidence)
        for manifest in registry.list_manifests()
    }
    read_model = build_default_loop_read_model(
        observed_authority_refs=authority_refs,
        observed_evidence_refs=evidence_refs,
    )

    for summary in read_model.loops:
        view = summary.operator_closure_readiness_view
        assert summary.status is LoopStatus.VERIFIED
        assert view.readiness_state == "ready_for_terminal_closure_review"
        assert view.next_proof_action == "run_loop_specific_terminal_closure_workflow"
        assert view.blocker_refs == ()
        assert view.evidence_gap_refs == ()
        assert view.authority_gap_refs == ()
        assert "terminal_closure_certificate" in view.next_proof_refs
        assert view.terminal_closure is False


def test_loop_operator_closure_readiness_view_rejects_mutation_or_closure_claim() -> None:
    summary = build_default_loop_read_model().loops[0]
    kwargs = dataclasses.asdict(summary.operator_closure_readiness_view)

    with pytest.raises(ValueError, match="read-only"):
        LoopOperatorClosureReadinessView(**{**kwargs, "read_only": False})
    with pytest.raises(ValueError, match="mutation route"):
        LoopOperatorClosureReadinessView(**{**kwargs, "mutation_route": True})
    with pytest.raises(ValueError, match="terminal closure"):
        LoopOperatorClosureReadinessView(**{**kwargs, "terminal_closure": True})


def test_loop_proof_obligation_view_groups_required_proof_inputs() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        view = summary.proof_obligation_view
        assert view.loop_id == summary.loop_id
        assert view.obligation_state == "blocked_by_missing_proof"
        assert set(view.required_evidence_refs) == set(summary.required_evidence)
        assert set(view.satisfied_evidence_refs) == set(summary.evidence_refs)
        assert set(view.missing_evidence_refs) == set(summary.missing_evidence)
        assert set(view.required_authority_refs) == set(summary.required_authority)
        assert set(view.satisfied_authority_refs) == set(summary.authority_refs)
        assert set(view.missing_authority_refs) == set(summary.missing_authority)
        assert set(view.closure_condition_refs) == set(summary.closure_conditions)
        assert set(view.validator_refs) == set(summary.closure_evidence_pack.validator_refs)
        assert set(view.proof_surface_refs) == set(summary.closure_evidence_pack.proof_surface_refs)
        assert set(view.blocker_refs) == set(summary.open_blockers)
        assert view.read_only is True
        assert view.executes_validator is False
        assert view.terminal_closure is False


def test_loop_proof_obligation_view_marks_complete_proof_for_terminal_review_only() -> None:
    registry = build_default_loop_registry()
    authority_refs = {
        manifest.loop_id: tuple(manifest.required_authority)
        for manifest in registry.list_manifests()
    }
    evidence_refs = {
        manifest.loop_id: tuple(manifest.required_evidence)
        for manifest in registry.list_manifests()
    }
    read_model = build_default_loop_read_model(
        observed_authority_refs=authority_refs,
        observed_evidence_refs=evidence_refs,
    )

    for summary in read_model.loops:
        view = summary.proof_obligation_view
        assert summary.status is LoopStatus.VERIFIED
        assert view.obligation_state == "proof_obligations_satisfied_terminal_review_required"
        assert view.missing_evidence_refs == ()
        assert view.missing_authority_refs == ()
        assert view.blocker_refs == ()
        assert view.read_only is True
        assert view.executes_validator is False
        assert view.terminal_closure is False


def test_loop_proof_obligation_view_rejects_validator_execution_or_closure_claim() -> None:
    summary = build_default_loop_read_model().loops[0]
    kwargs = dataclasses.asdict(summary.proof_obligation_view)

    with pytest.raises(ValueError, match="read-only"):
        LoopProofObligationView(**{**kwargs, "read_only": False})
    with pytest.raises(ValueError, match="execute validators"):
        LoopProofObligationView(**{**kwargs, "executes_validator": True})
    with pytest.raises(ValueError, match="terminal closure"):
        LoopProofObligationView(**{**kwargs, "terminal_closure": True})


def test_loop_audit_evolution_view_groups_receipts_blockers_and_learning_refs() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        view = summary.audit_evolution_view
        assert view.loop_id == summary.loop_id
        assert view.audit_state == "audit_blocked_by_unresolved_gaps"
        assert set(view.receipt_refs) == {receipt.output_hash for receipt in summary.step_receipts}
        assert set(view.receipt_lineage_refs) == {
            binding.lineage_ref for binding in summary.receipt_lineage_bindings
        }
        assert set(view.audit_blocker_refs) == set(summary.open_blockers)
        assert view.learning_policy_ref == summary.learning_policy
        assert set(view.learning_candidate_refs) == set(summary.closure_report.learning_candidates)
        assert summary.learning_policy in view.learning_candidate_refs
        assert set(view.learning_evidence_input_refs) == set(
            summary.learning_binding.evidence_input_refs
        )
        assert set(view.learning_admission_refs) == set(summary.learning_binding.admission_refs)
        assert set(view.learning_retention_refs) == set(summary.learning_binding.retention_refs)
        assert set(view.proof_surface_refs) == set(summary.closure_evidence_pack.proof_surface_refs) | set(
            summary.learning_binding.proof_surface_refs
        )
        assert view.read_only is True
        assert view.emits_receipt is False
        assert view.admits_learning is False
        assert view.terminal_closure is False


def test_loop_audit_evolution_view_marks_complete_audit_for_review_only() -> None:
    registry = build_default_loop_registry()
    authority_refs = {
        manifest.loop_id: tuple(manifest.required_authority)
        for manifest in registry.list_manifests()
    }
    evidence_refs = {
        manifest.loop_id: tuple(manifest.required_evidence)
        for manifest in registry.list_manifests()
    }
    read_model = build_default_loop_read_model(
        observed_authority_refs=authority_refs,
        observed_evidence_refs=evidence_refs,
    )

    for summary in read_model.loops:
        view = summary.audit_evolution_view
        assert summary.status is LoopStatus.VERIFIED
        assert view.audit_state == "audit_ready_for_terminal_review"
        assert view.audit_blocker_refs == ()
        assert view.learning_candidate_refs == ()
        assert view.read_only is True
        assert view.emits_receipt is False
        assert view.admits_learning is False
        assert view.terminal_closure is False


def test_loop_audit_evolution_view_rejects_receipt_emission_learning_or_closure_claim() -> None:
    summary = build_default_loop_read_model().loops[0]
    kwargs = dataclasses.asdict(summary.audit_evolution_view)

    with pytest.raises(ValueError, match="read-only"):
        LoopAuditEvolutionView(**{**kwargs, "read_only": False})
    with pytest.raises(ValueError, match="emit receipts"):
        LoopAuditEvolutionView(**{**kwargs, "emits_receipt": True})
    with pytest.raises(ValueError, match="admit learning"):
        LoopAuditEvolutionView(**{**kwargs, "admits_learning": True})
    with pytest.raises(ValueError, match="terminal closure"):
        LoopAuditEvolutionView(**{**kwargs, "terminal_closure": True})


def test_loop_recovery_readiness_view_groups_rollback_blockers_and_lineage_refs() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        view = summary.recovery_readiness_view
        assert view.loop_id == summary.loop_id
        assert view.recovery_state == "recovery_blocked_by_unresolved_gaps"
        assert view.rollback_ref == summary.rollback_policy
        assert view.rollback_available == summary.closure_report.rollback_available
        assert view.closure_report_ref == "closure_report"
        assert view.closure_evidence_pack_ref == summary.closure_evidence_pack.pack_ref
        assert set(view.blocker_refs) == set(summary.open_blockers)
        assert set(view.receipt_lineage_refs) == set(
            summary.closure_evidence_pack.receipt_lineage_refs
        )
        assert set(view.recovery_source_refs) == set(summary.rollback_binding.source_refs)
        assert set(view.recovery_validator_refs) == set(summary.rollback_binding.validator_refs)
        assert set(view.recovery_proof_surface_refs) == set(
            summary.closure_evidence_pack.proof_surface_refs
        ) | set(summary.rollback_binding.proof_surface_refs)
        assert view.next_recovery_action == "resolve_blockers_before_recovery_or_terminal_review"
        assert view.read_only is True
        assert view.executes_rollback is False
        assert view.opens_incident is False
        assert view.terminal_closure is False


def test_loop_recovery_readiness_view_marks_complete_recovery_for_review_only() -> None:
    registry = build_default_loop_registry()
    authority_refs = {
        manifest.loop_id: tuple(manifest.required_authority)
        for manifest in registry.list_manifests()
    }
    evidence_refs = {
        manifest.loop_id: tuple(manifest.required_evidence)
        for manifest in registry.list_manifests()
    }
    read_model = build_default_loop_read_model(
        observed_authority_refs=authority_refs,
        observed_evidence_refs=evidence_refs,
    )

    for summary in read_model.loops:
        view = summary.recovery_readiness_view
        assert summary.status is LoopStatus.VERIFIED
        assert view.recovery_state == "recovery_ready_for_terminal_review"
        assert view.blocker_refs == ()
        assert view.next_recovery_action == "keep_recovery_evidence_available_for_terminal_review"
        assert view.read_only is True
        assert view.executes_rollback is False
        assert view.opens_incident is False
        assert view.terminal_closure is False


def test_loop_recovery_readiness_view_rejects_rollback_incident_or_closure_claim() -> None:
    summary = build_default_loop_read_model().loops[0]
    kwargs = dataclasses.asdict(summary.recovery_readiness_view)

    with pytest.raises(ValueError, match="read-only"):
        LoopRecoveryReadinessView(**{**kwargs, "read_only": False})
    with pytest.raises(ValueError, match="execute rollback"):
        LoopRecoveryReadinessView(**{**kwargs, "executes_rollback": True})
    with pytest.raises(ValueError, match="open incidents"):
        LoopRecoveryReadinessView(**{**kwargs, "opens_incident": True})
    with pytest.raises(ValueError, match="terminal closure"):
        LoopRecoveryReadinessView(**{**kwargs, "terminal_closure": True})


def test_loop_summary_rejects_mismatched_recovery_readiness_view() -> None:
    summary = build_default_loop_read_model().loops[0]
    view_kwargs = dataclasses.asdict(summary.recovery_readiness_view)
    mismatched_view = LoopRecoveryReadinessView(
        **{
            **view_kwargs,
            "rollback_ref": "different_rollback",
        }
    )

    with pytest.raises(ValueError, match="rollback ref"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=mismatched_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_summary_rejects_mismatched_audit_evolution_view() -> None:
    summary = build_default_loop_read_model().loops[0]
    view_kwargs = dataclasses.asdict(summary.audit_evolution_view)
    mismatched_view = LoopAuditEvolutionView(
        **{
            **view_kwargs,
            "receipt_refs": ("different_receipt",),
        }
    )

    with pytest.raises(ValueError, match="receipt refs"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=mismatched_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_summary_rejects_mismatched_proof_obligation_view() -> None:
    summary = build_default_loop_read_model().loops[0]
    view_kwargs = dataclasses.asdict(summary.proof_obligation_view)
    mismatched_view = LoopProofObligationView(
        **{
            **view_kwargs,
            "missing_evidence_refs": ("different_evidence",),
        }
    )

    with pytest.raises(ValueError, match="missing evidence refs"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=mismatched_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_summary_rejects_mismatched_operator_closure_readiness_view() -> None:
    summary = build_default_loop_read_model().loops[0]
    view_kwargs = dataclasses.asdict(summary.operator_closure_readiness_view)
    mismatched_view = LoopOperatorClosureReadinessView(
        **{
            **view_kwargs,
            "blocker_refs": ("different_gap",),
        }
    )

    with pytest.raises(ValueError, match="blocker refs"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=mismatched_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_summary_rejects_mismatched_closure_evidence_pack() -> None:
    summary = build_default_loop_read_model().loops[0]
    pack_kwargs = dataclasses.asdict(summary.closure_evidence_pack)
    mismatched_pack = LoopClosureEvidencePack(
        **{
            **pack_kwargs,
            "blocker_refs": ("different_gap",),
            "closure_blocked": True,
        }
    )

    with pytest.raises(ValueError, match="blocker refs"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=mismatched_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_receipt_lineage_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for binding in summary.receipt_lineage_bindings
        for ref in (*binding.source_refs, *binding.validator_refs)
        if "/" in ref
    }

    assert "scripts/collect_deployment_witness.py" in file_refs
    assert "schemas/runtime_conformance_certificate.schema.json" in file_refs
    assert "mcoi/mcoi_runtime/persistence/cognitive_outcome_ledger.py" in file_refs
    assert "schemas/sdlc_verification_receipt.schema.json" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_closure_condition_bindings_cover_conditions_without_execution() -> None:
    read_model = build_default_loop_read_model()

    for summary in read_model.loops:
        binding_refs = {binding.closure_ref for binding in summary.closure_condition_bindings}

        assert binding_refs == set(summary.closure_conditions)
        assert len(summary.closure_condition_bindings) == len(summary.closure_conditions)
        assert all(binding.read_only is True for binding in summary.closure_condition_bindings)
        assert all(binding.terminal_closure is False for binding in summary.closure_condition_bindings)
        assert all(binding.required_evidence_refs for binding in summary.closure_condition_bindings)
        assert all(binding.required_authority_refs for binding in summary.closure_condition_bindings)
        assert all(
            set(binding.required_evidence_refs) <= set(summary.required_evidence)
            for binding in summary.closure_condition_bindings
        )
        assert all(
            set(binding.required_authority_refs) <= set(summary.required_authority)
            for binding in summary.closure_condition_bindings
        )
        assert all(binding.source_refs for binding in summary.closure_condition_bindings)
        assert all(binding.validator_refs for binding in summary.closure_condition_bindings)
        assert all(binding.proof_surface_refs for binding in summary.closure_condition_bindings)


def test_loop_closure_condition_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for binding in summary.closure_condition_bindings
        for ref in (*binding.source_refs, *binding.validator_refs)
        if "/" in ref
    }

    assert "scripts/preflight_deployment_witness.py" in file_refs
    assert "schemas/runtime_conformance_certificate.schema.json" in file_refs
    assert "mcoi/mcoi_runtime/core/cognitive_loop.py" in file_refs
    assert "schemas/sdlc_verification_receipt.schema.json" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_learning_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for ref in (*summary.learning_binding.source_refs, *summary.learning_binding.validator_refs)
        if "/" in ref
    }

    assert "scripts/preflight_deployment_witness.py" in file_refs
    assert "mcoi/mcoi_runtime/persistence/cognitive_outcome_ledger.py" in file_refs
    assert "schemas/sdlc_verification_receipt.schema.json" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_rollback_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for ref in (*summary.rollback_binding.source_refs, *summary.rollback_binding.validator_refs)
        if "/" in ref
    }

    assert "scripts/apply_deployment_publication_status.py" in file_refs
    assert "schemas/sdlc_recovery_handoff_receipt.schema.json" in file_refs
    assert "mcoi/mcoi_runtime/core/mil_learning_admission.py" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_evidence_binding_local_refs_resolve_to_existing_artifacts() -> None:
    read_model = build_default_loop_read_model()
    file_refs = {
        ref
        for summary in read_model.loops
        for binding in summary.evidence_bindings
        for ref in (*binding.source_refs, *binding.validator_refs)
        if "/" in ref
    }

    assert "scripts/collect_deployment_witness.py" in file_refs
    assert "schemas/runtime_conformance_certificate.schema.json" in file_refs
    assert "mcoi/mcoi_runtime/core/governed_code_change_loop.py" in file_refs
    assert all((REPO_ROOT / ref).exists() for ref in file_refs)


def test_loop_summary_rejects_duplicate_or_missing_evidence_bindings() -> None:
    summary = build_default_loop_read_model().loops[0]
    duplicate_binding = summary.evidence_bindings[0]

    with pytest.raises(ValueError, match="duplicate evidence refs"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=(duplicate_binding, duplicate_binding),
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )

    with pytest.raises(ValueError, match="cover required evidence exactly"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings[:-1],
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_evidence_binding_rejects_mutation_or_terminal_closure_claim() -> None:
    kwargs = {
        "evidence_ref": "runtime_witness_valid",
        "purpose": "bind runtime witness proof surface",
        "source_refs": ("scripts/collect_deployment_witness.py",),
        "validator_refs": ("tests/test_collect_deployment_witness.py",),
        "proof_surface_refs": ("gateway_runtime_witness",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopEvidenceBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopEvidenceBinding(**kwargs, terminal_closure=True)


def test_loop_authority_binding_rejects_mutation_or_terminal_closure_claim() -> None:
    kwargs = {
        "authority_ref": "operator_approval_ref",
        "purpose": "bind operator approval authority",
        "source_refs": ("scripts/emit_deployment_publication_operator_input_request.py",),
        "validator_refs": ("tests/test_emit_deployment_publication_operator_input_request.py",),
        "proof_surface_refs": ("authority_obligation_mesh",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopAuthorityBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopAuthorityBinding(**kwargs, terminal_closure=True)


def test_loop_rollback_binding_rejects_mutation_or_terminal_closure_claim() -> None:
    kwargs = {
        "rollback_ref": "restore_workspace_snapshot_or_open_recovery_handoff",
        "purpose": "bind governed code-change recovery policy",
        "source_refs": ("schemas/sdlc_recovery_handoff_receipt.schema.json",),
        "validator_refs": ("scripts/validate_sdlc_artifact.py",),
        "proof_surface_refs": ("software_dev_capability_pack",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopRollbackBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopRollbackBinding(**kwargs, terminal_closure=True)


def test_loop_risk_binding_rejects_mutation_or_terminal_closure_claim() -> None:
    kwargs = {
        "risk_ref": "repository_mutation",
        "purpose": "bind repository mutation risk proof surface",
        "hazard_refs": ("unorchestrated_repository_mutation",),
        "mitigation_refs": ("require_uao_reference",),
        "monitor_refs": ("sdlc_recovery_handoff_receipt",),
        "source_refs": ("schemas/sdlc_recovery_handoff_receipt.schema.json",),
        "validator_refs": ("scripts/validate_sdlc_artifact.py",),
        "proof_surface_refs": ("software_dev_capability_pack",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopRiskBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopRiskBinding(**kwargs, terminal_closure=True)


def test_loop_learning_binding_rejects_mutation_or_terminal_closure_claim() -> None:
    kwargs = {
        "learning_ref": "promote failure diagnosis into tests or SDLC gate evidence",
        "purpose": "bind code-change failure diagnosis to later SDLC proof",
        "evidence_input_refs": ("verification_receipt",),
        "admission_refs": ("diagnosis_requires_worker_or_verification_receipt",),
        "retention_refs": ("sdlc_verification_receipt",),
        "source_refs": ("schemas/sdlc_verification_receipt.schema.json",),
        "validator_refs": ("scripts/validate_sdlc_artifact.py",),
        "proof_surface_refs": ("software_dev_capability_pack",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopLearningBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopLearningBinding(**kwargs, terminal_closure=True)


def test_loop_mode_binding_rejects_transition_or_terminal_closure_claim() -> None:
    kwargs = {
        "projected_mode": LoopMode.DRY_RUN,
        "allowed_modes": (LoopMode.DRY_RUN, LoopMode.REPLAY),
        "purpose": "bind dry-run and replay mode separation",
        "separation_refs": ("dry_run_without_effect",),
        "real_execution_guard_refs": ("real_mode_not_registered",),
        "source_refs": ("scripts/run_governed_code_change_loop.py",),
        "validator_refs": ("tests/test_run_governed_code_change_loop_script.py",),
        "proof_surface_refs": ("software_dev_capability_pack",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopModeBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="mode transition"):
        LoopModeBinding(**kwargs, mode_transition=True)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopModeBinding(**kwargs, terminal_closure=True)

    mismatched_kwargs = {**kwargs, "projected_mode": LoopMode.REAL}
    with pytest.raises(ValueError, match="projected_mode"):
        LoopModeBinding(**mismatched_kwargs)


def test_loop_status_binding_rejects_transition_or_terminal_closure_claim() -> None:
    kwargs = {
        "projected_status": LoopStatus.BLOCKED,
        "status_reason": "read_model_blocked_by_unresolved_gaps",
        "blocker_refs": ("missing_evidence:verification_receipt",),
        "verification_refs": ("required_evidence_observed",),
        "closure_gate_refs": ("verification_receipt_present",),
        "source_refs": ("schemas/sdlc_verification_receipt.schema.json",),
        "validator_refs": ("scripts/validate_sdlc_artifact.py",),
        "proof_surface_refs": ("software_dev_capability_pack",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopStatusBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="status transition"):
        LoopStatusBinding(**kwargs, status_transition=True)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopStatusBinding(**kwargs, terminal_closure=True)

    mismatched_kwargs = {**kwargs, "projected_status": "blocked"}
    with pytest.raises(ValueError, match="projected_status"):
        LoopStatusBinding(**mismatched_kwargs)


def test_loop_transition_binding_rejects_execution_or_terminal_closure_claim() -> None:
    kwargs = {
        "transition_ref": "blocked_to_verified_after_requirements",
        "from_status": LoopStatus.BLOCKED,
        "to_status": LoopStatus.VERIFIED,
        "from_step": LoopPhase.VERIFY,
        "to_step": LoopPhase.RECORD_RECEIPT,
        "required_authority_refs": ("sdlc_closure_authority",),
        "required_evidence_refs": ("verification_receipt",),
        "blocker_refs": ("missing_evidence:verification_receipt",),
        "receipt_refs": ("verification_receipt", "closure_report"),
        "rollback_refs": ("restore_workspace_snapshot_or_open_recovery_handoff",),
        "source_refs": ("schemas/sdlc_verification_receipt.schema.json",),
        "validator_refs": ("scripts/validate_sdlc_artifact.py",),
        "proof_surface_refs": ("software_dev_capability_pack",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopTransitionBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="execute transition"):
        LoopTransitionBinding(**kwargs, executes_transition=True)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopTransitionBinding(**kwargs, terminal_closure=True)

    mismatched_kwargs = {**kwargs, "from_status": "blocked"}
    with pytest.raises(ValueError, match="from_status"):
        LoopTransitionBinding(**mismatched_kwargs)


def test_loop_receipt_lineage_binding_rejects_emission_or_terminal_closure_claim() -> None:
    kwargs = {
        "lineage_ref": "verification_receipt_lineage",
        "step": LoopPhase.VERIFY,
        "receipt_ref": "verification_receipt",
        "receipt_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        "required_evidence_refs": ("verification_receipt",),
        "observed_evidence_refs": (),
        "blocker_refs": ("missing_evidence:verification_receipt",),
        "source_receipt_refs": ("verification_receipt", "action_projection_receipt"),
        "source_refs": ("schemas/sdlc_verification_receipt.schema.json",),
        "validator_refs": ("scripts/validate_sdlc_artifact.py",),
        "proof_surface_refs": ("software_dev_capability_pack",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopReceiptLineageBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="emit receipt"):
        LoopReceiptLineageBinding(**kwargs, emits_receipt=True)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopReceiptLineageBinding(**kwargs, terminal_closure=True)

    missing_receipt_ref = {**kwargs, "source_receipt_refs": ("action_projection_receipt",)}
    with pytest.raises(ValueError, match="include receipt_ref"):
        LoopReceiptLineageBinding(**missing_receipt_ref)

    mismatched_step = {**kwargs, "step": "verify"}
    with pytest.raises(ValueError, match="step"):
        LoopReceiptLineageBinding(**mismatched_step)


def test_loop_closure_condition_binding_rejects_mutation_or_terminal_closure_claim() -> None:
    kwargs = {
        "closure_ref": "verification_receipt_present",
        "purpose": "bind verification receipt closure condition",
        "required_evidence_refs": ("verification_receipt",),
        "required_authority_refs": ("sdlc_closure_authority",),
        "source_refs": ("schemas/sdlc_verification_receipt.schema.json",),
        "validator_refs": ("scripts/validate_sdlc_artifact.py",),
        "proof_surface_refs": ("software_dev_capability_pack",),
    }

    with pytest.raises(ValueError, match="read-only"):
        LoopClosureConditionBinding(**kwargs, read_only=False)

    with pytest.raises(ValueError, match="terminal closure"):
        LoopClosureConditionBinding(**kwargs, terminal_closure=True)


def test_loop_summary_rejects_mismatched_status_binding() -> None:
    summary = build_default_loop_read_model().loops[0]
    mismatched_binding = LoopStatusBinding(
        projected_status=summary.status,
        status_reason=summary.status_binding.status_reason,
        blocker_refs=("different_blocker",),
        verification_refs=summary.status_binding.verification_refs,
        closure_gate_refs=summary.status_binding.closure_gate_refs,
        source_refs=summary.status_binding.source_refs,
        validator_refs=summary.status_binding.validator_refs,
        proof_surface_refs=summary.status_binding.proof_surface_refs,
    )

    with pytest.raises(ValueError, match="status_binding blocker_refs"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=mismatched_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_summary_rejects_mismatched_transition_binding() -> None:
    summary = build_default_loop_read_model().loops[0]
    mismatched_binding = LoopTransitionBinding(
        transition_ref="blocked_to_verified_after_requirements",
        from_status=LoopStatus.BLOCKED,
        to_status=LoopStatus.VERIFIED,
        from_step=LoopPhase.VERIFY,
        to_step=LoopPhase.RECORD_RECEIPT,
        required_authority_refs=summary.required_authority,
        required_evidence_refs=summary.required_evidence,
        blocker_refs=("different_blocker",),
        receipt_refs=("verification_receipt", "closure_report"),
        rollback_refs=(summary.rollback_policy,),
        source_refs=summary.transition_bindings[0].source_refs,
        validator_refs=summary.transition_bindings[0].validator_refs,
        proof_surface_refs=summary.transition_bindings[0].proof_surface_refs,
    )

    with pytest.raises(ValueError, match="transition binding blocker_refs"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=(mismatched_binding,),
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_summary_rejects_mismatched_receipt_lineage_binding() -> None:
    summary = build_default_loop_read_model().loops[0]
    original_binding = summary.receipt_lineage_bindings[0]
    mismatched_binding = LoopReceiptLineageBinding(
        lineage_ref=original_binding.lineage_ref,
        step=original_binding.step,
        receipt_ref=original_binding.receipt_ref,
        receipt_hash="sha256:9999999999999999999999999999999999999999999999999999999999999999",
        required_evidence_refs=original_binding.required_evidence_refs,
        observed_evidence_refs=original_binding.observed_evidence_refs,
        blocker_refs=original_binding.blocker_refs,
        source_receipt_refs=original_binding.source_receipt_refs,
        source_refs=original_binding.source_refs,
        validator_refs=original_binding.validator_refs,
        proof_surface_refs=original_binding.proof_surface_refs,
    )

    with pytest.raises(ValueError, match="receipt_hash"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=(mismatched_binding, *summary.receipt_lineage_bindings[1:]),
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_summary_rejects_terminal_or_mismatched_closure_report() -> None:
    summary = build_default_loop_read_model().loops[0]
    terminal_report = LoopClosureReport(
        loop_id=summary.loop_id,
        closed=True,
        closure_reason="terminal_claim_forbidden",
        evidence_complete=True,
        unresolved_gaps=(),
        rollback_available=True,
        learning_candidates=(),
    )

    with pytest.raises(ValueError, match="terminal closure"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=terminal_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )

    mismatched_report = LoopClosureReport(
        loop_id=summary.loop_id,
        closed=False,
        closure_reason="missing_gap",
        evidence_complete=False,
        unresolved_gaps=("different_gap",),
        rollback_available=True,
        learning_candidates=(),
    )

    with pytest.raises(ValueError, match="unresolved gaps"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=mismatched_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_registry_preserves_explicit_blockers_even_when_evidence_exists() -> None:
    registry = build_default_loop_registry()
    manifest = registry.get_manifest("runtime_conformance_loop")
    blocked_state = LoopState(
        loop_id=manifest.loop_id,
        status=LoopStatus.OPEN,
        current_step=LoopPhase.VERIFY,
        mode=LoopMode.DRY_RUN,
        authority_refs=manifest.required_authority,
        evidence_refs=manifest.required_evidence,
        open_blockers=("signature_key_rotation_pending",),
        updated_at="2026-06-08T00:00:00+00:00",
    )
    registry_with_blocker = type(registry)(
        manifests=registry.manifests,
        states={**dict(registry.states), manifest.loop_id: blocked_state},
    )
    summary = registry_with_blocker.summarize("runtime_conformance_loop")

    assert summary.status is LoopStatus.BLOCKED
    assert summary.missing_evidence == ()
    assert summary.open_blockers == ("signature_key_rotation_pending",)
    assert summary.closure_report.closed is False
    assert summary.closure_report.unresolved_gaps == ("signature_key_rotation_pending",)
    assert "accepted_conformance_status" in summary.closure_conditions


def test_loop_summary_exposes_read_only_step_receipt_trail() -> None:
    read_model = build_default_loop_read_model()
    expected_steps = (
        LoopPhase.OBSERVE,
        LoopPhase.DECIDE,
        LoopPhase.ACT,
        LoopPhase.VERIFY,
        LoopPhase.RECORD_RECEIPT,
        LoopPhase.UPDATE_STATE,
        LoopPhase.LEARN,
        LoopPhase.AUDIT,
    )

    for summary in read_model.loops:
        assert tuple(receipt.step for receipt in summary.step_receipts) == expected_steps
        assert len(summary.step_receipts) == 8
        assert all(receipt.loop_id == summary.loop_id for receipt in summary.step_receipts)
        assert all(receipt.status is LoopStatus.BLOCKED for receipt in summary.step_receipts)
        assert all(set(receipt.errors) == set(summary.open_blockers) for receipt in summary.step_receipts)
        assert all(receipt.metadata["read_only"] is True for receipt in summary.step_receipts)
        assert all(receipt.metadata["synthetic_projection"] is True for receipt in summary.step_receipts)
        assert all(receipt.metadata["terminal_closure"] is False for receipt in summary.step_receipts)
        assert all(receipt.metadata["behavior_rewrite"] is False for receipt in summary.step_receipts)


def test_loop_summary_rejects_terminal_or_mismatched_step_receipts() -> None:
    summary = build_default_loop_read_model().loops[0]

    with pytest.raises(ValueError, match="terminal_closure"):
        LoopStepReceipt(
            loop_id=summary.loop_id,
            step=LoopPhase.VERIFY,
            input_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            output_hash="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            decision="terminal_step_claim_forbidden",
            evidence_refs=(),
            status=LoopStatus.VERIFIED,
            errors=(),
            timestamp=summary.updated_at,
            metadata={"read_only": True, "terminal_closure": True},
        )

    mismatched_receipt = LoopStepReceipt(
        loop_id="different_loop",
        step=LoopPhase.OBSERVE,
        input_hash="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        output_hash="sha256:3333333333333333333333333333333333333333333333333333333333333333",
        decision="mismatched_loop_forbidden",
        evidence_refs=(),
        status=LoopStatus.BLOCKED,
        errors=summary.open_blockers,
        timestamp=summary.updated_at,
        metadata={"read_only": True, "terminal_closure": False},
    )

    with pytest.raises(ValueError, match="step receipt loop_id"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            risk_binding=summary.risk_binding,
            status=summary.status,
            status_binding=summary.status_binding,
            transition_bindings=summary.transition_bindings,
            mode=summary.mode,
            mode_binding=summary.mode_binding,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=(mismatched_receipt,),
            receipt_lineage_bindings=summary.receipt_lineage_bindings,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_condition_bindings=summary.closure_condition_bindings,
            closure_report=summary.closure_report,
            closure_evidence_pack=summary.closure_evidence_pack,
            operator_closure_readiness_view=summary.operator_closure_readiness_view,
            proof_obligation_view=summary.proof_obligation_view,
            audit_evolution_view=summary.audit_evolution_view,
            recovery_readiness_view=summary.recovery_readiness_view,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            rollback_binding=summary.rollback_binding,
            learning_policy=summary.learning_policy,
            learning_binding=summary.learning_binding,
            updated_at=summary.updated_at,
        )


def test_loop_registry_rejects_duplicate_loop_ids() -> None:
    registry = build_default_loop_registry()
    manifest = registry.get_manifest("deployment_witness_loop")
    duplicate_manifests = {
        manifest.loop_id: manifest,
        "duplicate_deployment_witness_loop": manifest,
    }

    with pytest.raises(ValueError, match="manifest key must match loop_id"):
        type(registry)(manifests=duplicate_manifests)

    assert manifest.loop_id == "deployment_witness_loop"
    assert duplicate_manifests["duplicate_deployment_witness_loop"].loop_id == manifest.loop_id
    assert registry.get_manifest("deployment_witness_loop") is manifest


def test_loop_receipt_and_closure_report_contracts_are_explicit() -> None:
    receipt = LoopStepReceipt(
        loop_id="governed_code_change_loop",
        step=LoopPhase.VERIFY,
        input_hash="sha256:input",
        output_hash="sha256:output",
        decision="block_until_sdlc_receipts_exist",
        evidence_refs=("code_worker_receipt",),
        status=LoopStatus.BLOCKED,
        errors=("missing_evidence:verification_receipt",),
        timestamp="2026-06-08T00:00:00+00:00",
        metadata={"read_only": True, "terminal_closure": False},
    )
    report = LoopClosureReport(
        loop_id="governed_code_change_loop",
        closed=False,
        closure_reason="sdlc_receipts_missing",
        evidence_complete=False,
        unresolved_gaps=("verification_receipt", "recovery_handoff"),
        rollback_available=True,
        learning_candidates=("add_test_for_missing_receipts",),
    )

    assert receipt.status is LoopStatus.BLOCKED
    assert receipt.to_json_dict()["step"] == "verify"
    assert report.closed is False
    assert report.rollback_available is True
    assert "verification_receipt" in report.unresolved_gaps


def test_contract_records_are_immutable() -> None:
    summary = build_default_loop_read_model().loops[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        summary.status = LoopStatus.CLOSED  # type: ignore[misc]
