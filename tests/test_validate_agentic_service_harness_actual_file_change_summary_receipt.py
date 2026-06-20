"""Test actual file-change summary receipt validation.

Purpose: verify actual file-change summary receipts stay zero-effect until
workspace write authority, cleanup receipt, redaction evidence, and UAO
admission are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_actual_file_change_summary_receipt.
Invariants:
  - The receipt binds to planned file-change collection preflight.
  - Changed-file refs, diff refs, raw content, approval grant, mutation routes,
    secret-like payloads, and closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_actual_file_change_summary_receipt as validator


def test_actual_file_change_summary_receipt_passes() -> None:
    validation = validator.validate_agentic_service_harness_actual_file_change_summary_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.planned_preflight_ref == validator.EXPECTED_PLANNED_PREFLIGHT_REF


def test_actual_file_change_summary_rejects_authority_drift() -> None:
    payload = validator.build_mutated_receipt(
        scope__actual_summary_allowed=True,
        admission_gates__branch_write_authority_collected=True,
        admission_gates__workspace_write_authority_granted=True,
        admission_gates__cleanup_receipt_emitted=True,
        admission_gates__uao_admission_verified=True,
        admission_gates__actual_summary_receipt_emission_allowed=True,
        effect_boundary__file_change_summary_emitted=True,
        effect_boundary__files_written=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _planned_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.actual_summary_allowed must be false" in serialized_errors
    assert "admission_gates.branch_write_authority_collected must be false" in serialized_errors
    assert "admission_gates.workspace_write_authority_granted must be false" in serialized_errors
    assert "admission_gates.cleanup_receipt_emitted must be false" in serialized_errors
    assert "admission_gates.uao_admission_verified must be false" in serialized_errors
    assert "admission_gates.actual_summary_receipt_emission_allowed must be false" in serialized_errors
    assert "effect_boundary.file_change_summary_emitted must be false" in serialized_errors
    assert "effect_boundary.files_written must be false" in serialized_errors


def test_actual_file_change_summary_rejects_non_empty_summary() -> None:
    payload = validator.build_mutated_receipt(
        file_change_summary__changed_file_count=1,
        file_change_summary__changed_file_refs=["evidence://changed-file/src-app"],
        file_change_summary__diff_refs=["evidence://diff/src-app"],
        file_change_summary__raw_file_content_serialized=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _planned_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "file_change_summary.changed_file_count must be 0 while authority is absent" in serialized_errors
    assert "file_change_summary.changed_file_refs must be empty while authority is absent" in serialized_errors
    assert "file_change_summary.diff_refs must be empty while authority is absent" in serialized_errors
    assert "file_change_summary.raw_file_content_serialized must be false" in serialized_errors


def test_actual_file_change_summary_rejects_missing_refs_and_path_drift() -> None:
    payload = validator.build_mutated_receipt(
        admission_gates__required_before_summary_refs=[
            "examples/agentic_service_harness_planned_file_change_collection_preflight.foundation.json"
        ],
        admission_gates__blocked_reason_refs=["blocked://branch-write-authority/not-collected"],
        path_policy__path_allowlist=["/"],
        redaction_policy__redaction_evidence_ref="evidence://wrong-redaction",
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _planned_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "admission_gates.required_before_summary_refs missing required ref" in serialized_errors
    assert "admission_gates.blocked_reason_refs missing required ref" in serialized_errors
    assert "path_policy.path_allowlist must match planned preflight" in serialized_errors
    assert "redaction_policy.redaction_evidence_ref must match planned preflight" in serialized_errors


def test_actual_file_change_summary_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_receipt(
        next_action="POST /api/harness/file-change-summary should never be admitted",
    )
    payload["receipt_refs"]["access_token_envelope"] = {"redacted": True}
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _planned_preflight(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_actual_file_change_summary_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "actual-file-change-summary-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["planned_preflight_ref"] == validator.EXPECTED_PLANNED_PREFLIGHT_REF


def _planned_preflight() -> dict[str, object]:
    return json.loads(validator.DEFAULT_PLANNED_PREFLIGHT_EXAMPLES[0].read_text(encoding="utf-8"))
