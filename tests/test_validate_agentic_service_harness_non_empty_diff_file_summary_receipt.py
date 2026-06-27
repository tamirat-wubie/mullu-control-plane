"""Test non-empty diff file summary receipt validation.

Purpose: verify non-empty diff file summary receipt remains blocked until
filesystem-write evidence, cleanup, redaction, UAO, and receipt-store evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_non_empty_diff_file_summary_receipt.
Invariants:
  - The receipt binds non-empty diff admission, filesystem-write admission, and
    zero-diff actual diff receipt evidence.
  - Non-empty file refs, raw bodies, branch writes, receipt append, mutation
    routes, PR creation, secret-like payloads, and terminal closure fail closed.
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
    assert validation.non_empty_diff_admission_ref == validator.EXPECTED_NON_EMPTY_DIFF_ADMISSION_REF
    assert validation.filesystem_write_admission_ref == validator.EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF
    assert validation.zero_diff_receipt_ref == validator.EXPECTED_ZERO_DIFF_RECEIPT_REF


def test_non_empty_diff_file_summary_rejects_authority_drift() -> None:
    payload = validator.build_mutated_receipt(
        admission_gates__non_empty_file_summary_emitted=True,
        admission_gates__filesystem_write_evidence_collected=True,
        admission_gates__branch_write_authority_verified=True,
        admission_gates__workspace_write_authority_verified=True,
        admission_gates__cleanup_receipt_verified=True,
        admission_gates__uao_non_empty_diff_file_summary_verified=True,
        admission_gates__receipt_store_write_path_verified=True,
        authority_denials__branch_write_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__pr_creation_enabled=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(
        payload,
        _non_empty_preflight(),
        _filesystem_preflight(),
        _zero_diff_receipt(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "admission_gates.non_empty_file_summary_emitted must be false" in serialized_errors
    assert "admission_gates.filesystem_write_evidence_collected must be false" in serialized_errors
    assert "admission_gates.branch_write_authority_verified must be false" in serialized_errors
    assert "admission_gates.workspace_write_authority_verified must be false" in serialized_errors
    assert "admission_gates.uao_non_empty_diff_file_summary_verified must be false" in serialized_errors
    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "authority_denials.pr_creation_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_non_empty_diff_file_summary_rejects_non_empty_payload() -> None:
    payload = validator.build_mutated_receipt(
        file_summary_receipt__changed_file_count=2,
        file_summary_receipt__changed_file_refs=["evidence://changed-file/src-app"],
        file_summary_receipt__diff_refs=["evidence://diff/src-app"],
        file_summary_receipt__redacted_diff_bundle_ref="digest://redacted-diff-bundle",
        file_summary_receipt__receipt_append_ref="receipt://diff-summary-appended",
        file_summary_receipt__raw_diff_body_serialized=True,
        file_summary_receipt__raw_file_content_serialized=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(
        payload,
        _non_empty_preflight(),
        _filesystem_preflight(),
        _zero_diff_receipt(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "changed_file_count must be 0" in serialized_errors
    assert "changed_file_refs must be empty" in serialized_errors
    assert "diff_refs must be empty" in serialized_errors
    assert "redacted_diff_bundle_ref must remain not-collected" in serialized_errors
    assert "receipt_append_ref must remain blocked" in serialized_errors
    assert "raw_diff_body_serialized must be false" in serialized_errors
    assert "raw_file_content_serialized must be false" in serialized_errors


def test_non_empty_diff_file_summary_rejects_missing_refs() -> None:
    payload = validator.build_mutated_receipt(
        admission_gates__required_before_file_summary_refs=[
            "approval://operator/non-empty-diff-file-summary"
        ],
        admission_gates__blocked_reason_refs=[
            "blocked://operator-approval/not-collected"
        ],
        admission_gates__next_required_evidence_refs=[
            "witness://github-pr-admission-preflight"
        ],
        receipt_refs__receipt_store_write_path_ref="evidence://wrong-receipt-store",
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(
        payload,
        _non_empty_preflight(),
        _filesystem_preflight(),
        _zero_diff_receipt(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "required_before_file_summary_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors
    assert "next_required_evidence_refs missing required ref" in serialized_errors
    assert "receipt_refs.receipt_store_write_path_ref must be" in serialized_errors


def test_non_empty_diff_file_summary_rejects_source_drift() -> None:
    source = _zero_diff_receipt()
    source["diff_collection_receipt"]["changed_file_count"] = 1
    source["diff_collection_receipt"]["changed_file_refs"] = ["evidence://changed-file/src-app"]
    source["diff_collection_receipt"]["diff_refs"] = ["evidence://diff/src-app"]

    errors: list[str] = []
    validator._validate_receipt_semantics(
        validator.build_mutated_receipt(),
        _non_empty_preflight(),
        _filesystem_preflight(),
        source,
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "zero-diff source changed_file_count must be 0" in serialized_errors
    assert "zero-diff source changed_file_refs must be empty" in serialized_errors
    assert "zero-diff source diff_refs must be empty" in serialized_errors


def test_non_empty_diff_file_summary_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_receipt(
        next_action="POST /api/harness/non-empty-diff-file-summary must remain blocked",
    )
    payload["receipt_refs"]["access_token_envelope"] = {"redacted": True}
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_receipt_semantics(
        payload,
        _non_empty_preflight(),
        _filesystem_preflight(),
        _zero_diff_receipt(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_non_empty_diff_file_summary_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "non-empty-diff-file-summary-receipt-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["zero_diff_receipt_ref"] == validator.EXPECTED_ZERO_DIFF_RECEIPT_REF


def _non_empty_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_NON_EMPTY_DIFF_ADMISSION_EXAMPLES[0].read_text(encoding="utf-8"))


def _filesystem_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_FILESYSTEM_WRITE_ADMISSION_EXAMPLES[0].read_text(encoding="utf-8"))


def _zero_diff_receipt() -> dict[str, object]:
    return json.loads(validator.DEFAULT_ZERO_DIFF_RECEIPT_EXAMPLES[0].read_text(encoding="utf-8"))
