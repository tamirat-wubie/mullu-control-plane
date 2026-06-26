"""Test filesystem write admission preflight validation.

Purpose: verify filesystem write admission stays blocked until authority,
cleanup, redaction, UAO, and receipt-store evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_filesystem_write_admission_preflight.
Invariants:
  - The preflight binds to a dry-run actual diff collection receipt.
  - Filesystem write refs, raw bodies, branch writes, receipt append, mutation
    routes, secret-like payloads, and terminal closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_filesystem_write_admission_preflight as validator


def test_filesystem_write_admission_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_filesystem_write_admission_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.dry_run_receipt_ref == validator.EXPECTED_DRY_RUN_RECEIPT_REF


def test_filesystem_write_admission_rejects_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        admission_gates__filesystem_write_admitted=True,
        admission_gates__branch_write_authority_verified=True,
        admission_gates__workspace_write_authority_verified=True,
        admission_gates__cleanup_receipt_verified=True,
        admission_gates__uao_filesystem_write_admission_verified=True,
        admission_gates__receipt_store_write_path_verified=True,
        authority_denials__branch_write_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _dry_run_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "admission_gates.filesystem_write_admitted must be false" in serialized_errors
    assert "admission_gates.branch_write_authority_verified must be false" in serialized_errors
    assert "admission_gates.workspace_write_authority_verified must be false" in serialized_errors
    assert "admission_gates.cleanup_receipt_verified must be false" in serialized_errors
    assert "admission_gates.uao_filesystem_write_admission_verified must be false" in serialized_errors
    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_filesystem_write_admission_rejects_non_empty_payload() -> None:
    payload = validator.build_mutated_preflight(
        filesystem_write_contract__candidate_changed_file_count=2,
        filesystem_write_contract__changed_file_refs=["evidence://changed-file/src-app"],
        filesystem_write_contract__diff_refs=["evidence://diff/src-app"],
        filesystem_write_contract__redacted_diff_bundle_ref="digest://redacted-diff-bundle",
        filesystem_write_contract__receipt_append_ref="receipt://diff-receipt-appended",
        filesystem_write_contract__raw_diff_body_serialized=True,
        filesystem_write_contract__raw_file_content_serialized=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _dry_run_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "candidate_changed_file_count must be 0" in serialized_errors
    assert "changed_file_refs must be empty" in serialized_errors
    assert "diff_refs must be empty" in serialized_errors
    assert "redacted_diff_bundle_ref must remain not-admitted" in serialized_errors
    assert "receipt_append_ref must remain blocked" in serialized_errors
    assert "raw_diff_body_serialized must be false" in serialized_errors
    assert "raw_file_content_serialized must be false" in serialized_errors


def test_filesystem_write_admission_rejects_missing_refs() -> None:
    payload = validator.build_mutated_preflight(
        source_contract_refs=[
            "examples/agentic_service_harness_actual_diff_collection_receipt.foundation.json"
        ],
        admission_gates__required_before_filesystem_write_refs=[
            "approval://operator/non-empty-diff-receipt"
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
    validator._validate_preflight_semantics(payload, _dry_run_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_contract_refs missing required ref" in serialized_errors
    assert "required_before_filesystem_write_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors
    assert "next_required_evidence_refs missing required ref" in serialized_errors
    assert "receipt_refs.receipt_store_write_path_ref must be" in serialized_errors


def test_filesystem_write_admission_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_preflight(
        next_action="POST /api/harness/non-empty-diff-receipts must remain blocked",
    )
    payload["receipt_refs"]["access_token_envelope"] = {"redacted": True}
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _dry_run_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_filesystem_write_admission_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "filesystem-write-admission-preflight-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["dry_run_receipt_ref"] == validator.EXPECTED_DRY_RUN_RECEIPT_REF


def _dry_run_receipt() -> dict[str, object]:
    return json.loads(validator.DEFAULT_DRY_RUN_RECEIPT_EXAMPLES[0].read_text(encoding="utf-8"))
