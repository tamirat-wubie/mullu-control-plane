"""Test actual filesystem write receipt admission validation.

Purpose: verify actual filesystem-write receipt admission remains blocked while
binding concrete redacted candidate refs.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_actual_filesystem_write_receipt_admission.
Invariants:
  - Concrete candidate refs are preserved.
  - Live write, receipt append, raw content, mutation route, secret-like payload,
    and terminal closure drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_actual_filesystem_write_receipt_admission as validator


def test_actual_filesystem_write_receipt_admission_passes() -> None:
    validation = validator.validate_agentic_service_harness_actual_filesystem_write_receipt_admission()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.concrete_candidate_ref == validator.EXPECTED_CONCRETE_CANDIDATE_REF


def test_actual_filesystem_write_receipt_admission_rejects_authority_drift() -> None:
    payload = validator.build_mutated_admission(
        source_candidate__source_filesystem_write_executed=True,
        source_candidate__source_filesystem_write_admitted=True,
        source_candidate__source_receipt_append_enabled=True,
        admission_gates__filesystem_write_receipt_admission_allowed=True,
        admission_gates__filesystem_write_executed=True,
        admission_gates__branch_write_authority_verified=True,
        admission_gates__workspace_write_authority_verified=True,
        filesystem_write_receipt_contract__filesystem_write_receipt_emitted=True,
        effect_boundary__files_written=True,
        effect_boundary__receipt_store_appended=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_admission_semantics(payload, _concrete_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_candidate.source_filesystem_write_executed must be false" in serialized_errors
    assert "source_candidate.source_filesystem_write_admitted must be false" in serialized_errors
    assert "source_candidate.source_receipt_append_enabled must be false" in serialized_errors
    assert "admission_gates.filesystem_write_receipt_admission_allowed must be false" in serialized_errors
    assert "admission_gates.filesystem_write_executed must be false" in serialized_errors
    assert "admission_gates.branch_write_authority_verified must be false" in serialized_errors
    assert "filesystem_write_receipt_contract.filesystem_write_receipt_emitted must be false" in serialized_errors
    assert "effect_boundary.files_written must be false" in serialized_errors
    assert "effect_boundary.receipt_store_appended must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.terminal_closure must be false" in serialized_errors


def test_actual_filesystem_write_receipt_admission_rejects_candidate_ref_drift() -> None:
    payload = validator.build_mutated_admission(
        source_concrete_filesystem_write_evidence_candidate_ref="examples/missing-candidate.json",
        source_candidate__candidate_changed_file_count=2,
        source_candidate__changed_file_refs=["evidence://wrong-file"],
        filesystem_write_receipt_contract__changed_file_refs=[],
        filesystem_write_receipt_contract__diff_refs=[],
        filesystem_write_receipt_contract__redacted_diff_bundle_ref="digest://wrong",
    )

    errors: list[str] = []
    validator._validate_admission_semantics(payload, _concrete_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_concrete_filesystem_write_evidence_candidate_ref must be" in serialized_errors
    assert "filesystem_write_receipt_contract.changed_file_refs must be" in serialized_errors
    assert "filesystem_write_receipt_contract.diff_refs must be" in serialized_errors
    assert "redacted_diff_bundle_ref must be" in serialized_errors


def test_actual_filesystem_write_receipt_admission_rejects_missing_refs() -> None:
    payload = validator.build_mutated_admission(
        admission_gates__required_before_actual_write_receipt_refs=[
            "examples/agentic_service_harness_concrete_filesystem_write_evidence_candidate.foundation.json"
        ],
        admission_gates__blocked_reason_refs=[
            "blocked://actual-filesystem-write-receipt-admission/not-granted"
        ],
        admission_gates__next_required_evidence_refs=[
            "witness://actual-non-empty-diff-receipt"
        ],
        receipt_refs__receipt_store_write_path_ref="evidence://wrong-receipt-store",
    )

    errors: list[str] = []
    validator._validate_admission_semantics(payload, _concrete_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "required_before_actual_write_receipt_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors
    assert "next_required_evidence_refs missing required ref" in serialized_errors
    assert "receipt_refs.receipt_store_write_path_ref must be" in serialized_errors


def test_actual_filesystem_write_receipt_admission_rejects_source_candidate_drift() -> None:
    source = _concrete_candidate()
    source["candidate_evidence"]["candidate_changed_file_count"] = 0
    source["admission_gates"]["filesystem_write_executed"] = True
    source["authority_denials"]["filesystem_write_enabled"] = True
    source["authority_denials"]["receipt_store_append_enabled"] = True

    errors: list[str] = []
    validator._validate_admission_semantics(
        validator.build_mutated_admission(),
        source,
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "concrete candidate must have non-empty candidate refs" in serialized_errors
    assert "concrete candidate source must not execute filesystem writes" in serialized_errors
    assert "concrete candidate source must not enable filesystem writes" in serialized_errors
    assert "concrete candidate source must not enable receipt append" in serialized_errors


def test_actual_filesystem_write_receipt_admission_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_admission(
        next_action="POST /api/harness/filesystem-write must remain blocked",
    )
    payload["receipt_refs"]["access_token_envelope"] = "redacted"
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_admission_semantics(payload, _concrete_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_actual_filesystem_write_receipt_admission_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "actual-filesystem-write-receipt-admission-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["concrete_candidate_ref"] == validator.EXPECTED_CONCRETE_CANDIDATE_REF


def _concrete_candidate() -> dict[str, object]:
    return json.loads(validator.DEFAULT_CONCRETE_CANDIDATE_EXAMPLES[0].read_text(encoding="utf-8"))
