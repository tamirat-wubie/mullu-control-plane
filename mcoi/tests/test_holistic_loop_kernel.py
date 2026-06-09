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

import pytest

from mcoi_runtime.contracts.holistic_loop import (
    LoopClosureReport,
    LoopMode,
    LoopPhase,
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
    assert "deployment_witness_published" in deployment_summary.missing_evidence
    assert "missing_evidence:deployment_witness_published" in deployment_summary.open_blockers


def test_complete_evidence_verifies_read_model_without_runtime_mutation() -> None:
    registry = build_default_loop_registry()
    evidence_refs = {
        manifest.loop_id: tuple(manifest.required_evidence)
        for manifest in registry.list_manifests()
    }
    read_model = build_default_loop_read_model(observed_evidence_refs=evidence_refs)

    assert {summary.loop_id for summary in read_model.loops} == EXPECTED_LOOP_IDS
    assert all(summary.status is LoopStatus.VERIFIED for summary in read_model.loops)
    assert all(summary.missing_evidence == () for summary in read_model.loops)
    assert all(summary.open_blockers == () for summary in read_model.loops)


def test_registry_preserves_explicit_blockers_even_when_evidence_exists() -> None:
    registry = build_default_loop_registry()
    manifest = registry.get_manifest("runtime_conformance_loop")
    blocked_state = LoopState(
        loop_id=manifest.loop_id,
        status=LoopStatus.OPEN,
        current_step=LoopPhase.VERIFY,
        mode=LoopMode.DRY_RUN,
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
    assert "accepted_conformance_status" in summary.closure_conditions


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
