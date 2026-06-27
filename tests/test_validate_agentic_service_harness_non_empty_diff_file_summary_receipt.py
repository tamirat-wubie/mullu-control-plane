"""Test non-empty diff file summary receipt validation.

Purpose: verify non-empty diff/file summary receipts stay blocked until
concrete filesystem-write receipt, redaction, UAO, and receipt-store evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_non_empty_diff_file_summary_receipt.
Invariants:
  - The receipt binds zero-diff, non-empty admission, and filesystem-write preflight sources.
  - Non-empty payloads, raw bodies, receipt-store append, mutation routes,
    secret-like payloads, and terminal closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_non_empty_diff_file_summary_receipt as validator


def test_non_empty_diff_file_summary_receipt_passes() -> None:
    validation = validator.validate_agentic_service_harness_non_empty_diff_file_summary_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.filesystem_write_receipt_ref == validator.EXPECTED_FILESYSTEM_WRITE_RECEIPT_REF


def test_non_empty_diff_file_summary_rejects_authority_drift() -> None:
    payload = validator.build_mutated_receipt(
        source_evidence__filesystem_write_receipt_verified=True,
        admission_gates__non_empty_diff_file_summary_receipt_admitted=True,
        admission_gates__filesystem_write_receipt_verified=True,
        admission_gates__redacted_diff_bundle_verified=True,
        admission_gates__branch_write_authority_verified=True,
        admission_gates__receipt_store_write_path_verified=True,
        authority_denials__filesystem_write_executed=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_evidence.filesystem_write_receipt_verified must be false" in serialized_errors
    assert "admission_gates.non_empty_diff_file_summary_receipt_admitted must be false" in serialized_errors
    assert "admission_gates.redacted_diff_bundle_verified must be false" in serialized_errors
    assert "admission_gates.branch_write_authority_verified must be false" in serialized_errors
    assert "authority_denials.filesystem_write_executed must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_non_empty_diff_file_summary_rejects_non_empty_payload() -> None:
    payload = validator.build_mutated_receipt(
        non_empty_summary__candidate_changed_file_count=2,
        non_empty_summary__changed_file_refs=["evidence://changed-file/src-app"],
        non_empty_summary__diff_refs=["evidence://diff/src-app"],
        non_empty_summary__redacted_summary_ref="summary://redacted",
        non_empty_summary__redacted_diff_bundle_ref="digest://redacted-diff-bundle",
        non_empty_summary__receipt_append_ref="receipt://diff-summary-appended",
        non_empty_summary__raw_diff_body_serialized=True,
        non_empty_summary__raw_file_content_serialized=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "candidate_changed_file_count must be 0" in serialized_errors
    assert "changed_file_refs must be empty" in serialized_errors
    assert "diff_refs must be empty" in serialized_errors
    assert "redacted_summary_ref must remain not-admitted" in serialized_errors
    assert "redacted_diff_bundle_ref must remain not-admitted" in serialized_errors
    assert "receipt_append_ref must remain blocked" in serialized_errors
    assert "raw_diff_body_serialized must be false" in serialized_errors
    assert "raw_file_content_serialized must be false" in serialized_errors


def test_non_empty_diff_file_summary_rejects_missing_refs() -> None:
    payload = validator.build_mutated_receipt(
        source_contract_refs=[
            "examples/agentic_service_harness_actual_diff_collection_receipt.foundation.json"
        ],
        admission_gates__required_before_non_empty_summary_refs=[
            "evidence://actual-filesystem-write-receipt"
        ],
        admission_gates__blocked_reason_refs=[
            "blocked://filesystem-write-receipt/not-verified"
        ],
        admission_gates__next_required_evidence_refs=[
            "witness://github-pr-admission-preflight"
        ],
        receipt_refs__receipt_store_write_path_ref="evidence://wrong-receipt-store",
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_contract_refs missing required ref" in serialized_errors
    assert "required_before_non_empty_summary_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors
    assert "next_required_evidence_refs missing required ref" in serialized_errors
    assert "receipt_refs.receipt_store_write_path_ref must be" in serialized_errors


def test_non_empty_diff_file_summary_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_receipt(
        next_action="POST /api/harness/non-empty-diff-file-summary must remain blocked",
    )
    payload["receipt_refs"]["access_token_envelope"] = {"redacted": True}
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_non_empty_diff_file_summary_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "non-empty-diff-file-summary-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["filesystem_write_receipt_ref"] == validator.EXPECTED_FILESYSTEM_WRITE_RECEIPT_REF
