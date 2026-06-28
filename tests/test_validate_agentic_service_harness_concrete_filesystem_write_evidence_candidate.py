"""Test concrete filesystem write evidence candidate validation.

Purpose: verify non-empty redacted write evidence can be represented without
granting live filesystem write, receipt append, PR creation, or terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_concrete_filesystem_write_evidence_candidate.
Invariants:
  - Source write and file-summary surfaces remain blocked.
  - Candidate refs are non-empty evidence refs, not raw file content.
  - Raw diffs, mutation routes, secret-like payloads, and terminal closure fail
    closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_concrete_filesystem_write_evidence_candidate as validator


def test_concrete_filesystem_write_evidence_candidate_passes() -> None:
    validation = validator.validate_agentic_service_harness_concrete_filesystem_write_evidence_candidate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.filesystem_write_admission_ref == validator.EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF
    assert validation.non_empty_diff_file_summary_ref == validator.EXPECTED_NON_EMPTY_DIFF_FILE_SUMMARY_REF


def test_concrete_filesystem_write_candidate_rejects_authority_drift() -> None:
    payload = validator.build_mutated_candidate(
        source_receipts__source_filesystem_write_admitted=True,
        source_receipts__source_non_empty_file_summary_emitted=True,
        admission_gates__filesystem_write_executed=True,
        admission_gates__branch_write_authority_verified=True,
        admission_gates__workspace_write_authority_verified=True,
        authority_denials__branch_write_enabled=True,
        authority_denials__filesystem_write_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__pr_creation_enabled=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_candidate_semantics(payload, _filesystem_preflight(), _file_summary_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_receipts.source_filesystem_write_admitted must be false" in serialized_errors
    assert "source_receipts.source_non_empty_file_summary_emitted must be false" in serialized_errors
    assert "admission_gates.filesystem_write_executed must be false" in serialized_errors
    assert "admission_gates.branch_write_authority_verified must be false" in serialized_errors
    assert "admission_gates.workspace_write_authority_verified must be false" in serialized_errors
    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.filesystem_write_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "authority_denials.pr_creation_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_concrete_filesystem_write_candidate_rejects_empty_candidate_refs() -> None:
    payload = validator.build_mutated_candidate(
        candidate_evidence__candidate_changed_file_count=0,
        candidate_evidence__changed_file_refs=[],
        candidate_evidence__diff_refs=[],
        candidate_evidence__redacted_diff_bundle_ref="digest://wrong",
        candidate_evidence__receipt_append_ref="receipt://forbidden-append",
    )

    errors: list[str] = []
    validator._validate_candidate_semantics(payload, _filesystem_preflight(), _file_summary_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "candidate_changed_file_count must be non-empty" in serialized_errors
    assert "candidate_evidence.changed_file_refs must be non-empty" in serialized_errors
    assert "candidate_evidence.diff_refs must be non-empty" in serialized_errors
    assert "redacted_diff_bundle_ref must be" in serialized_errors
    assert "receipt_append_ref must be" in serialized_errors


def test_concrete_filesystem_write_candidate_rejects_missing_refs() -> None:
    payload = validator.build_mutated_candidate(
        admission_gates__required_before_live_write_refs=[
            "approval://operator/filesystem-write-execution"
        ],
        admission_gates__blocked_reason_refs=[
            "blocked://operator-approval/not-collected"
        ],
        admission_gates__next_required_evidence_refs=[
            "witness://actual-filesystem-write-receipt"
        ],
        receipt_refs__receipt_store_write_path_ref="evidence://wrong-receipt-store",
    )

    errors: list[str] = []
    validator._validate_candidate_semantics(payload, _filesystem_preflight(), _file_summary_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "required_before_live_write_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors
    assert "next_required_evidence_refs missing required ref" in serialized_errors
    assert "receipt_refs.receipt_store_write_path_ref must be" in serialized_errors


def test_concrete_filesystem_write_candidate_rejects_source_drift() -> None:
    filesystem_source = _filesystem_preflight()
    filesystem_source["admission_gates"]["filesystem_write_admitted"] = True
    summary_source = _file_summary_receipt()
    summary_source["admission_gates"]["non_empty_file_summary_emitted"] = True

    errors: list[str] = []
    validator._validate_candidate_semantics(
        validator.build_mutated_candidate(),
        filesystem_source,
        summary_source,
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "source filesystem preflight must not admit filesystem writes" in serialized_errors
    assert "source non-empty file summary must not emit a summary" in serialized_errors


def test_concrete_filesystem_write_candidate_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_candidate(
        next_action="POST /api/harness/filesystem-write must remain blocked",
    )
    payload["receipt_refs"]["access_token_envelope"] = {"redacted": True}
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_candidate_semantics(payload, _filesystem_preflight(), _file_summary_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_concrete_filesystem_write_candidate_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "concrete-filesystem-write-candidate-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["filesystem_write_admission_ref"] == validator.EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF


def _filesystem_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_FILESYSTEM_WRITE_ADMISSION_EXAMPLES[0].read_text(encoding="utf-8"))


def _file_summary_receipt() -> dict[str, object]:
    return json.loads(validator.DEFAULT_NON_EMPTY_DIFF_FILE_SUMMARY_EXAMPLES[0].read_text(encoding="utf-8"))
