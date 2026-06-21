"""Test actual diff collection receipt validation.

Purpose: verify actual diff collection receipts stay zero-effect until
admission, authority, cleanup, redaction, UAO, and receipt-store evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_actual_diff_collection_receipt.
Invariants:
  - The receipt binds to actual diff collection admission preflight.
  - Non-empty diffs, raw diff bodies, receipt-store append, mutation routes,
    secret-like payloads, and closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_actual_diff_collection_receipt as validator


def test_actual_diff_collection_receipt_passes() -> None:
    validation = validator.validate_agentic_service_harness_actual_diff_collection_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.admission_preflight_ref == validator.EXPECTED_ADMISSION_PREFLIGHT_REF


def test_actual_diff_collection_receipt_rejects_authority_drift() -> None:
    payload = validator.build_mutated_receipt(
        scope__actual_diff_collection_receipt_allowed=True,
        admission_gates__branch_write_authority_collected=True,
        admission_gates__workspace_write_authority_granted=True,
        admission_gates__cleanup_receipt_emitted=True,
        admission_gates__uao_diff_collection_admission_verified=True,
        admission_gates__receipt_store_write_path_verified=True,
        admission_gates__actual_diff_collection_receipt_emission_allowed=True,
        effect_boundary__actual_diff_collected=True,
        effect_boundary__diff_receipt_emitted=True,
        effect_boundary__receipt_store_appended=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _admission_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.actual_diff_collection_receipt_allowed must be false" in serialized_errors
    assert "admission_gates.branch_write_authority_collected must be false" in serialized_errors
    assert "admission_gates.workspace_write_authority_granted must be false" in serialized_errors
    assert "admission_gates.cleanup_receipt_emitted must be false" in serialized_errors
    assert "admission_gates.uao_diff_collection_admission_verified must be false" in serialized_errors
    assert "admission_gates.receipt_store_write_path_verified must be false" in serialized_errors
    assert "effect_boundary.actual_diff_collected must be false" in serialized_errors
    assert "effect_boundary.diff_receipt_emitted must be false" in serialized_errors
    assert "effect_boundary.receipt_store_appended must be false" in serialized_errors


def test_actual_diff_collection_receipt_rejects_non_empty_diff_payload() -> None:
    payload = validator.build_mutated_receipt(
        diff_collection_receipt__changed_file_count=1,
        diff_collection_receipt__changed_file_refs=["evidence://changed-file/src-app"],
        diff_collection_receipt__diff_refs=["evidence://diff/src-app"],
        diff_collection_receipt__raw_diff_body_serialized=True,
        diff_collection_receipt__raw_file_content_serialized=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _admission_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "diff_collection_receipt.changed_file_count must be 0 while authority is absent" in serialized_errors
    assert "diff_collection_receipt.changed_file_refs must be empty while authority is absent" in serialized_errors
    assert "diff_collection_receipt.diff_refs must be empty while authority is absent" in serialized_errors
    assert "diff_collection_receipt.raw_diff_body_serialized must be false" in serialized_errors
    assert "diff_collection_receipt.raw_file_content_serialized must be false" in serialized_errors


def test_actual_diff_collection_receipt_rejects_missing_refs_and_path_drift() -> None:
    payload = validator.build_mutated_receipt(
        admission_gates__required_before_diff_receipt_refs=[
            "examples/agentic_service_harness_actual_diff_collection_admission_preflight.foundation.json"
        ],
        admission_gates__blocked_reason_refs=["blocked://branch-write-authority/not-collected"],
        diff_collection_receipt__receipt_append_ref="receipt://appended-diff-receipt",
        path_policy__path_allowlist=["/"],
        redaction_policy__redaction_evidence_ref="evidence://wrong-redaction",
        receipt_refs__receipt_store_write_path_ref="evidence://wrong-receipt-store",
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _admission_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "admission_gates.required_before_diff_receipt_refs missing required ref" in serialized_errors
    assert "admission_gates.blocked_reason_refs missing required ref" in serialized_errors
    assert "diff_collection_receipt.receipt_append_ref must remain blocked" in serialized_errors
    assert "path_policy.path_allowlist must match admission preflight" in serialized_errors
    assert "redaction_policy.redaction_evidence_ref must match admission preflight" in serialized_errors
    assert "receipt_refs.receipt_store_write_path_ref must be" in serialized_errors


def test_actual_diff_collection_receipt_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_receipt(
        next_action="POST /api/harness/actual-diff-receipts should never be admitted",
    )
    payload["receipt_refs"]["access_token_envelope"] = {"redacted": True}
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _admission_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_actual_diff_collection_receipt_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "actual-diff-collection-receipt-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["admission_preflight_ref"] == validator.EXPECTED_ADMISSION_PREFLIGHT_REF


def _admission_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_ADMISSION_PREFLIGHT_EXAMPLES[0].read_text(encoding="utf-8"))
