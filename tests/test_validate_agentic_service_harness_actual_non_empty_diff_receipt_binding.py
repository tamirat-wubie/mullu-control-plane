"""Test actual non-empty diff receipt binding validation.

Purpose: verify redacted non-empty diff refs can be bound without raw content,
receipt append, PR, connector, mutation-route, secret, or terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_actual_non_empty_diff_receipt_binding.
Invariants:
  - Source redacted execution refs are preserved.
  - Source blocked non-empty file summary state is preserved.
  - Effect-bearing authority drift fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_actual_non_empty_diff_receipt_binding as validator


def test_actual_non_empty_diff_receipt_binding_passes() -> None:
    validation = validator.validate_agentic_service_harness_actual_non_empty_diff_receipt_binding()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.redacted_execution_ref == validator.EXPECTED_REDACTED_EXECUTION_REF
    assert validation.non_empty_summary_ref == validator.EXPECTED_NON_EMPTY_SUMMARY_REF


def test_actual_non_empty_diff_receipt_binding_rejects_authority_drift() -> None:
    payload = validator.build_mutated_receipt(
        source_receipts__source_non_empty_file_summary_emitted=True,
        admission_gates__non_empty_file_summary_emitted=True,
        admission_gates__actual_filesystem_write_receipt_emitted=True,
        admission_gates__receipt_store_appended=True,
        admission_gates__terminal_certificate_verified=True,
        effect_boundary__files_written=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__receipt_store_appended=True,
        effect_boundary__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _redacted_execution(), _non_empty_summary(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_receipts.source_non_empty_file_summary_emitted must be false" in serialized_errors
    assert "admission_gates.non_empty_file_summary_emitted must be false" in serialized_errors
    assert "admission_gates.actual_filesystem_write_receipt_emitted must be false" in serialized_errors
    assert "admission_gates.receipt_store_appended must be false" in serialized_errors
    assert "admission_gates.terminal_certificate_verified must be false" in serialized_errors
    assert "effect_boundary.files_written must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.receipt_store_appended must be false" in serialized_errors
    assert "effect_boundary.terminal_closure must be false" in serialized_errors


def test_actual_non_empty_diff_receipt_binding_rejects_ref_drift() -> None:
    payload = validator.build_mutated_receipt(
        source_redacted_filesystem_write_execution_receipt_ref="examples/wrong.json",
        actual_non_empty_diff_binding__actual_non_empty_diff_receipt_ref="witness://wrong",
        actual_non_empty_diff_binding__changed_file_refs=[],
        actual_non_empty_diff_binding__diff_refs=["raw://diff"],
        actual_non_empty_diff_binding__receipt_append_ref="receipt://append-enabled",
        receipt_refs__terminal_certificate_required_ref="evidence://wrong-terminal",
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _redacted_execution(), _non_empty_summary(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_redacted_filesystem_write_execution_receipt_ref must be" in serialized_errors
    assert "actual_non_empty_diff_receipt_ref must be" in serialized_errors
    assert "actual_non_empty_diff_binding.changed_file_refs must be non-empty" in serialized_errors
    assert "actual_non_empty_diff_binding.diff_refs entries must be evidence refs" in serialized_errors
    assert "receipt_append_ref must be" in serialized_errors
    assert "receipt_refs.terminal_certificate_required_ref must be" in serialized_errors


def test_actual_non_empty_diff_receipt_binding_rejects_missing_gate_refs() -> None:
    payload = validator.build_mutated_receipt(
        admission_gates__required_before_binding_refs=[
            "examples/agentic_service_harness_redacted_filesystem_write_execution_receipt.foundation.json"
        ],
        admission_gates__blocked_reason_refs=[
            "blocked://non-empty-file-summary/not-emitted"
        ],
        admission_gates__next_required_evidence_refs=[
            "witness://github-pr-admission-preflight"
        ],
    )

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _redacted_execution(), _non_empty_summary(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "required_before_binding_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors
    assert "next_required_evidence_refs missing required ref" in serialized_errors


def test_actual_non_empty_diff_receipt_binding_rejects_source_drift() -> None:
    redacted_source = _redacted_execution()
    redacted_source["redacted_execution_evidence"]["changed_file_count"] = 2
    summary_source = _non_empty_summary()
    summary_source["admission_gates"]["non_empty_file_summary_emitted"] = True
    summary_source["file_summary_receipt"]["changed_file_count"] = 1
    summary_source["file_summary_receipt"]["changed_file_refs"] = ["evidence://unexpected"]
    summary_source["file_summary_receipt"]["diff_refs"] = ["evidence://unexpected-diff"]

    errors: list[str] = []
    validator._validate_receipt_semantics(
        validator.build_mutated_receipt(),
        redacted_source,
        summary_source,
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "redacted_execution_changed_file_count must be 2" in serialized_errors
    assert "source non-empty file summary must remain blocked" in serialized_errors
    assert "source non-empty file summary changed_file_count must remain 0" in serialized_errors
    assert "source non-empty file summary changed_file_refs must remain empty" in serialized_errors
    assert "source non-empty file summary diff_refs must remain empty" in serialized_errors


def test_actual_non_empty_diff_receipt_binding_rejects_secret_and_route_drift() -> None:
    payload = validator.build_mutated_receipt(
        next_action="POST /api/harness/diff-binding must remain blocked",
    )
    payload["receipt_refs"]["access_token_envelope"] = "redacted"
    payload["receipt_refs"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_receipt_semantics(payload, _redacted_execution(), _non_empty_summary(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_actual_non_empty_diff_receipt_binding_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "actual-non-empty-diff-receipt-binding-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["redacted_execution_ref"] == validator.EXPECTED_REDACTED_EXECUTION_REF


def _redacted_execution() -> dict[str, object]:
    return json.loads(validator.DEFAULT_REDACTED_EXECUTION_EXAMPLES[0].read_text(encoding="utf-8"))


def _non_empty_summary() -> dict[str, object]:
    return json.loads(validator.DEFAULT_NON_EMPTY_SUMMARY_EXAMPLES[0].read_text(encoding="utf-8"))
