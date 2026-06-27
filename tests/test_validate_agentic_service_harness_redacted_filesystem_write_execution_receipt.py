"""Test redacted filesystem write execution receipt validation.

Purpose: verify redacted filesystem-write execution evidence remains bounded to
refs without admitting runtime writes or raw output.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_redacted_filesystem_write_execution_receipt.
Invariants:
  - Source admission and concrete candidate refs are preserved.
  - Live write, receipt append, raw output, mutation route, secret-like payload,
    and terminal closure drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_redacted_filesystem_write_execution_receipt as validator


def test_redacted_filesystem_write_execution_receipt_passes() -> None:
    validation = validator.validate_agentic_service_harness_redacted_filesystem_write_execution_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.actual_admission_ref == validator.EXPECTED_ACTUAL_ADMISSION_REF


def test_redacted_filesystem_write_execution_receipt_rejects_authority_drift() -> None:
    payload = validator.build_mutated_receipt(
        source_admission__source_receipt_admission_allowed=True,
        source_admission__source_filesystem_write_executed=True,
        admission_gates__filesystem_write_executed=True,
        admission_gates__filesystem_write_receipt_emitted=True,
        admission_gates__receipt_store_appended=True,
        admission_gates__terminal_certificate_verified=True,
        effect_boundary__files_written=True,
        effect_boundary__receipt_store_appended=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _actual_admission(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_admission.source_receipt_admission_allowed must be false" in serialized_errors
    assert "source_admission.source_filesystem_write_executed must be false" in serialized_errors
    assert "admission_gates.filesystem_write_executed must be false" in serialized_errors
    assert "admission_gates.filesystem_write_receipt_emitted must be false" in serialized_errors
    assert "admission_gates.receipt_store_appended must be false" in serialized_errors
    assert "effect_boundary.files_written must be false" in serialized_errors
    assert "effect_boundary.receipt_store_appended must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.terminal_closure must be false" in serialized_errors


def test_redacted_filesystem_write_execution_receipt_rejects_evidence_ref_drift() -> None:
    payload = validator.build_mutated_receipt(
        source_actual_filesystem_write_receipt_admission_ref="examples/wrong.json",
        source_admission__candidate_changed_file_count=2,
        redacted_execution_evidence__actual_execution_ref="witness://wrong",
        redacted_execution_evidence__redacted_output_ref="witness://wrong-output",
        redacted_execution_evidence__changed_file_refs=[],
        redacted_execution_evidence__diff_refs=["raw://diff"],
        receipt_refs__receipt_store_write_path_ref="evidence://wrong-receipt-store",
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _actual_admission(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_actual_filesystem_write_receipt_admission_ref must be" in serialized_errors
    assert "candidate_changed_file_count must be" in serialized_errors
    assert "actual_execution_ref must be" in serialized_errors
    assert "redacted_output_ref must be" in serialized_errors
    assert "redacted_execution_evidence.changed_file_refs must be non-empty" in serialized_errors
    assert "redacted_execution_evidence.diff_refs entries must be evidence refs" in serialized_errors
    assert "receipt_refs.receipt_store_write_path_ref must be" in serialized_errors


def test_redacted_filesystem_write_execution_receipt_rejects_missing_refs() -> None:
    payload = validator.build_mutated_receipt(
        admission_gates__required_before_execution_receipt_refs=[
            "examples/agentic_service_harness_actual_filesystem_write_receipt_admission.foundation.json"
        ],
        admission_gates__blocked_reason_refs=[
            "blocked://live-filesystem-write/not-executed"
        ],
        admission_gates__next_required_evidence_refs=[
            "witness://actual-filesystem-write-receipt"
        ],
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _actual_admission(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "required_before_execution_receipt_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors
    assert "next_required_evidence_refs missing required ref" in serialized_errors


def test_redacted_filesystem_write_execution_receipt_rejects_source_admission_drift() -> None:
    source = _actual_admission()
    source["filesystem_write_receipt_contract"]["candidate_changed_file_count"] = 0
    source["admission_gates"]["filesystem_write_receipt_admission_allowed"] = True
    source["admission_gates"]["filesystem_write_executed"] = True
    source["effect_boundary"]["receipt_store_appended"] = True

    errors: list[str] = []
    validator._validate_receipt_semantics(
        validator.build_mutated_receipt(),
        source,
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "candidate_changed_file_count must be 0" in serialized_errors
    assert "source admission must not allow filesystem write receipt admission" in serialized_errors
    assert "source admission must not execute filesystem writes" in serialized_errors
    assert "source admission must not append receipt store" in serialized_errors


def test_redacted_filesystem_write_execution_receipt_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_receipt(
        next_action="POST /api/harness/filesystem-write must remain blocked",
    )
    payload["receipt_refs"]["access_token_envelope"] = "redacted"
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _actual_admission(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_redacted_filesystem_write_execution_receipt_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "redacted-filesystem-write-execution-receipt-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["actual_admission_ref"] == validator.EXPECTED_ACTUAL_ADMISSION_REF


def _actual_admission() -> dict[str, object]:
    return json.loads(validator.DEFAULT_ACTUAL_ADMISSION_EXAMPLES[0].read_text(encoding="utf-8"))
