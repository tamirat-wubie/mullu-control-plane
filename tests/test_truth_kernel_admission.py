"""Mullu Truth Kernel runtime admission tests.

Purpose: verify schema-bound truth commit admission before truth-state mutation.
Governance scope: exact-proof gating, deterministic replay, cross-reference
    integrity, Mfidel atomicity, and non-mutating adapter behavior.
Dependencies: mcoi_runtime.truth_kernel_adapter and truth-kernel examples.
Invariants:
  - Only exact passing proofs can support truth mutation.
  - Adapter admission is pure and does not write truth state.
  - Rejections carry explicit causal reason codes.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from mcoi_runtime.truth_kernel_adapter import (
    admit_truth_commit_candidate,
    build_truth_commit_candidate_from_proof,
)


ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = ROOT / "examples" / "truth_kernel"


def _load_example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLE_DIR / name).read_text(encoding="utf-8"))


def _example_triplet() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        _load_example("truth_candidate.exact_constraint_addition.json"),
        _load_example("kernel_proof.exact_projection.json"),
        _load_example("truth_commit_candidate.exact_constraint_addition.json"),
    )


def test_admits_exact_proof_backed_truth_commit_candidate_without_mutation() -> None:
    candidate, proof, commit = _example_triplet()
    original_candidate = deepcopy(candidate)
    original_proof = deepcopy(proof)
    original_commit = deepcopy(commit)

    admission = admit_truth_commit_candidate(
        truth_candidate=candidate,
        kernel_proof=proof,
        truth_commit_candidate=commit,
    )

    assert admission.accepted is True
    assert admission.reason == "truth_commit_candidate_admitted"
    assert admission.candidate_id == candidate["candidate_id"]
    assert admission.proof_id == proof["proof_id"]
    assert admission.commit_candidate_id == commit["commit_candidate_id"]
    assert admission.admission_id.startswith("truth-kernel-admission-")
    assert "reason:exact-proof-pass" in admission.reason_refs
    assert admission.violation_refs == ()
    assert candidate == original_candidate
    assert proof == original_proof
    assert commit == original_commit


def test_rejects_unknown_or_non_exact_proof_for_truth_mutation() -> None:
    candidate, proof, commit = _example_triplet()
    proof["proof_state"] = "Unknown"
    proof["result_kind"] = "UnknownResult"
    proof["conclusion"]["supports_truth_mutation"] = False
    proof["conclusion"]["required_next_action"] = "plan_sensing"

    admission = admit_truth_commit_candidate(
        truth_candidate=candidate,
        kernel_proof=proof,
        truth_commit_candidate=commit,
    )

    assert admission.accepted is False
    assert admission.reason == "proof_state_not_pass"
    assert "proof_state_not_pass" in admission.violation_refs
    assert "proof_result_not_exact" in admission.violation_refs
    assert "proof_does_not_support_truth_mutation" in admission.violation_refs
    assert "proof_next_action_not_commit_candidate" in admission.violation_refs
    assert admission.admission_id == ""


def test_rejects_cross_tenant_or_cross_candidate_proof_binding() -> None:
    candidate, proof, commit = _example_triplet()
    proof["tenant_id"] = "other-tenant"
    proof["subject_ref"] = "truth-candidate-other"
    commit["tenant_id"] = "other-tenant"
    commit["candidate_id"] = "truth-candidate-other"

    admission = admit_truth_commit_candidate(
        truth_candidate=candidate,
        kernel_proof=proof,
        truth_commit_candidate=commit,
    )

    assert admission.accepted is False
    assert admission.reason == "proof_tenant_mismatch"
    assert "proof_tenant_mismatch" in admission.violation_refs
    assert "commit_tenant_mismatch" in admission.violation_refs
    assert "proof_subject_ref_mismatch" in admission.violation_refs
    assert "commit_candidate_ref_mismatch" in admission.violation_refs
    assert admission.candidate_id == candidate["candidate_id"]


def test_rejects_missing_trace_rollback_or_journal_replay_binding() -> None:
    candidate, proof, commit = _example_triplet()
    commit["trace_ref"] = ""
    commit["rollback_ref"] = ""
    commit["journal"]["replay_required"] = False
    commit["journal"]["expected_replay_hash"] = ""

    admission = admit_truth_commit_candidate(
        truth_candidate=candidate,
        kernel_proof=proof,
        truth_commit_candidate=commit,
    )

    assert admission.accepted is False
    assert admission.reason == "trace_ref_required"
    assert "trace_ref_required" in admission.violation_refs
    assert "rollback_ref_required" in admission.violation_refs
    assert "journal_replay_required" in admission.violation_refs
    assert "journal_expected_replay_hash_required" in admission.violation_refs
    assert admission.admission_id == ""


def test_rejects_tampered_journal_replay_hash_before_mutation() -> None:
    candidate, proof, commit = _example_triplet()
    commit["journal"]["expected_replay_hash"] = "proof-expected-hash-tampered"

    admission = admit_truth_commit_candidate(
        truth_candidate=candidate,
        kernel_proof=proof,
        truth_commit_candidate=commit,
    )

    assert admission.accepted is False
    assert admission.reason == "journal_expected_replay_hash_mismatch"
    assert "journal_expected_replay_hash_mismatch" in admission.violation_refs
    assert admission.candidate_id == candidate["candidate_id"]
    assert admission.proof_id == proof["proof_id"]
    assert admission.admission_id == ""


def test_rejects_missing_sandbox_isolation_witness_before_mutation() -> None:
    candidate, proof, commit = _example_triplet()
    proof["witness_refs"] = ["witness:color-red", "witness:color-blue"]

    admission = admit_truth_commit_candidate(
        truth_candidate=candidate,
        kernel_proof=proof,
        truth_commit_candidate=commit,
    )

    assert admission.accepted is False
    assert admission.reason == "sandbox_isolation_witness_required"
    assert "sandbox_isolation_witness_required" in admission.violation_refs
    assert admission.candidate_id == candidate["candidate_id"]
    assert admission.proof_id == proof["proof_id"]
    assert admission.commit_candidate_id == commit["commit_candidate_id"]


def test_rejects_mfidel_delta_when_atomicity_is_not_preserved() -> None:
    candidate, proof, commit = _example_triplet()
    candidate["delta"]["includes_mfidel"] = True
    candidate["delta"]["mfidel_atomicity_preserved"] = False

    admission = admit_truth_commit_candidate(
        truth_candidate=candidate,
        kernel_proof=proof,
        truth_commit_candidate=commit,
    )

    assert admission.accepted is False
    assert admission.reason == "mfidel_atomicity_not_preserved"
    assert "mfidel_atomicity_not_preserved" in admission.violation_refs
    assert admission.candidate_id == candidate["candidate_id"]
    assert admission.proof_id == proof["proof_id"]
    assert admission.commit_candidate_id == commit["commit_candidate_id"]


def test_builds_commit_candidate_from_existing_exact_proof_payload() -> None:
    candidate, proof, _ = _example_triplet()
    candidate["parent_kernel_signature"] = proof["kernel_signature"]
    candidate["proof_obligations"][0]["proof_kind"] = proof["proof_kind"]

    commit = build_truth_commit_candidate_from_proof(
        truth_candidate=candidate,
        kernel_proof=proof,
        governance_ref="governance:builder-test",
        trace_ref="trace:builder-test",
        rollback_ref="rollback:builder-test",
        new_kernel_signature="kernel-signature-foundation-0002",
        journal_event_ref="journal:builder-test",
    )
    admission = admit_truth_commit_candidate(
        truth_candidate=candidate,
        kernel_proof=proof,
        truth_commit_candidate=commit,
    )

    assert commit["proof_ref"]["proof_id"] == proof["proof_id"]
    assert commit["proof_ref"]["proof_hash"] == proof["proof_hash"]
    assert commit["truth_admission"]["mutation_allowed"] is True
    assert commit["commit_hash"].startswith("truth-commit-candidate-")
    assert admission.accepted is True
    assert admission.admission_id.startswith("truth-kernel-admission-")


def test_admits_rust_emitted_schema_shaped_projection_proof() -> None:
    proof = _load_example("kernel_proof.rust_finite_projection.json")
    candidate = _load_example("truth_candidate.exact_constraint_addition.json")
    candidate["candidate_id"] = proof["subject_ref"]
    candidate["parent_kernel_signature"] = proof["kernel_signature"]
    candidate["proof_obligations"][0]["proof_kind"] = proof["proof_kind"]

    commit = build_truth_commit_candidate_from_proof(
        truth_candidate=candidate,
        kernel_proof=proof,
        governance_ref="governance:rust-finite-domain-proof-thread",
        trace_ref="trace:rust-finite-domain-color",
        rollback_ref="rollback:rust-finite-domain-color-parent",
        new_kernel_signature="truth-kernel-signature:rust-finite-domain-color-next",
        journal_event_ref="journal:rust-finite-domain-color",
    )
    admission = admit_truth_commit_candidate(
        truth_candidate=candidate,
        kernel_proof=proof,
        truth_commit_candidate=commit,
    )

    assert proof["proof_kind"] == "ProjectionProof"
    assert proof["conclusion"]["supports_truth_mutation"] is True
    assert "witness:sandbox-isolated" in proof["witness_refs"]
    assert commit["journal"]["expected_replay_hash"] == proof["replay"]["expected_hash"]
    assert commit["truth_admission"]["mutation_allowed"] is True
    assert admission.accepted is True
