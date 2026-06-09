"""Purpose: verify the holistic loop engineering kernel read model.
Governance scope: loop manifest contracts, blocker derivation, evidence
    requirements, closure conditions, and registry immutability.
Dependencies: pytest and mcoi_runtime holistic loop contracts.
Invariants:
  - First four loop manifests are registered without changing runtime behavior.
  - Missing evidence is exposed as blockers, never as verified closure.
  - Complete evidence can verify the read model without mutating loop behavior.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from mcoi_runtime.contracts.holistic_loop import (
    LoopAuthorityBinding,
    LoopClosureReport,
    LoopEvidenceBinding,
    LoopMode,
    LoopPhase,
    LoopSummary,
    LoopState,
    LoopStatus,
    LoopStepReceipt,
)
from mcoi_runtime.core.holistic_loop_registry import (
    build_default_loop_read_model,
    build_default_loop_registry,
)


EXPECTED_LOOP_IDS = {
    "deployment_witness_loop",
    "runtime_conformance_loop",
    "cognitive_outcome_loop",
    "governed_code_change_loop",
}
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_default_registry_exposes_first_four_loop_manifests() -> None:
    registry = build_default_loop_registry()
    loop_ids = {manifest.loop_id for manifest in registry.list_manifests()}

    assert loop_ids == EXPECTED_LOOP_IDS
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

    assert read_model.total_count == 4
    assert read_model.returned_count == 4
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
            status=summary.status,
            mode=summary.mode,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=(duplicate_binding, duplicate_binding),
            step_receipts=summary.step_receipts,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_report=summary.closure_report,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            learning_policy=summary.learning_policy,
            updated_at=summary.updated_at,
        )

    with pytest.raises(ValueError, match="cover required evidence exactly"):
        LoopSummary(
            loop_id=summary.loop_id,
            name=summary.name,
            purpose=summary.purpose,
            owner=summary.owner,
            risk_class=summary.risk_class,
            status=summary.status,
            mode=summary.mode,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings[:-1],
            step_receipts=summary.step_receipts,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_report=summary.closure_report,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            learning_policy=summary.learning_policy,
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
            status=summary.status,
            mode=summary.mode,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_report=terminal_report,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            learning_policy=summary.learning_policy,
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
            status=summary.status,
            mode=summary.mode,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=summary.step_receipts,
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_report=mismatched_report,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            learning_policy=summary.learning_policy,
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
            status=summary.status,
            mode=summary.mode,
            current_step=summary.current_step,
            required_authority=summary.required_authority,
            authority_bindings=summary.authority_bindings,
            authority_refs=summary.authority_refs,
            missing_authority=summary.missing_authority,
            required_evidence=summary.required_evidence,
            evidence_bindings=summary.evidence_bindings,
            step_receipts=(mismatched_receipt,),
            evidence_refs=summary.evidence_refs,
            missing_evidence=summary.missing_evidence,
            closure_conditions=summary.closure_conditions,
            closure_report=summary.closure_report,
            open_blockers=summary.open_blockers,
            rollback_policy=summary.rollback_policy,
            learning_policy=summary.learning_policy,
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
