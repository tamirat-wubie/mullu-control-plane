"""Tests for GitHub PR terminal closure operator decision value record.

Purpose: prove the explicit terminal closure decision value record satisfies
the operator decision gate without minting a certificate or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.
Invariants:
  - The default record validates.
  - Only approve_terminal_certificate is accepted for this record.
  - Certificate minting, terminal authority, mutation routes, and credentials
    fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_CERTIFICATE_MINTING_DECISION,
    EXPECTED_DECISION_VALUE,
    build_mutated_operator_decision_value_record,
    main,
    validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record,
)


def _write_payload(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "github-pr-terminal-closure-operator-decision-value-record.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_github_pr_terminal_closure_operator_decision_value_record_accepts_default_fixture() -> None:
    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.decision_value == EXPECTED_DECISION_VALUE
    assert validation.certificate_minting_decision == EXPECTED_CERTIFICATE_MINTING_DECISION
    assert validation.source_request_ref.endswith(
        "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.foundation.json"
    )


def test_github_pr_terminal_closure_operator_decision_value_record_rejects_denial_value(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_record(
        decision_value="deny_terminal_certificate",
        decision_text="deny_terminal_certificate",
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision_value" in serialized_errors
    assert "decision_text" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_record_rejects_certificate_minting(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_record(
        terminal_closure_certificate_minted=True,
        terminal_closure_authorized=True,
        decision_controls__certificate_minted_by_record=True,
        decision_controls__terminal_authority_on_record=True,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_closure_certificate_minted" in serialized_errors
    assert "terminal_closure_authorized" in serialized_errors
    assert "terminal_authority_on_record" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_record_rejects_missing_gate(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_record(
        operator_decision_gate_satisfied=False,
        explicit_operator_decision_value_present=False,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_decision_gate_satisfied" in serialized_errors
    assert "explicit_operator_decision_value_present" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_record_rejects_actual_diff_request_drift(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_record(
        actual_diff_decision_value_request_evidence__source_request_id="other-request",
        actual_diff_decision_value_request_evidence__source_request_ref="examples/other-request.json",
        actual_diff_decision_value_request_evidence__source_request_status="other-status",
        actual_diff_decision_value_request_evidence__source_rejection_binding_id="other-rejection",
        actual_diff_decision_value_request_evidence__operator_decision_ref="approval://other",
        actual_diff_decision_value_request_evidence__allowed_decision_values=["approve"],
        actual_diff_decision_value_request_evidence__actual_diff_terminal_closure_certificate_witness_ref="examples/other-certificate.json",
        actual_diff_decision_value_request_evidence__actual_diff_operator_response_witness_ref="examples/other-response.json",
        actual_diff_decision_value_request_evidence__actual_diff_approval_request_binding_ref="examples/other-approval.json",
        actual_diff_decision_value_request_evidence__actual_non_empty_diff_receipt_ref="witness://other",
        actual_diff_decision_value_request_evidence__changed_file_refs=["evidence://other-file"],
        actual_diff_decision_value_request_evidence__diff_refs=["evidence://other-diff"],
        actual_diff_decision_value_request_evidence__redacted_diff_bundle_ref="digest://other",
        actual_diff_decision_value_request_evidence__redacted_output_ref="witness://other-output",
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
        example_paths=(path,)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "actual_diff_decision_value_request_evidence.source_request_id expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.source_request_ref expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.source_request_status expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.source_rejection_binding_id expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.operator_decision_ref expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.allowed_decision_values expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.actual_diff_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.actual_diff_operator_response_witness_ref expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.actual_diff_approval_request_binding_ref expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.changed_file_refs expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.diff_refs expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.redacted_diff_bundle_ref expected" in serialized_errors
    assert "actual_diff_decision_value_request_evidence.redacted_output_ref expected" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_record_rejects_command_preview_request_drift(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_record(
        command_preview_decision_value_request_evidence__source_request_id="other-request",
        command_preview_decision_value_request_evidence__source_request_ref="examples/other-request.json",
        command_preview_decision_value_request_evidence__source_request_status="other-status",
        command_preview_decision_value_request_evidence__source_rejection_binding_id="other-rejection",
        command_preview_decision_value_request_evidence__operator_decision_ref="approval://other",
        command_preview_decision_value_request_evidence__allowed_decision_values=["approve"],
        command_preview_decision_value_request_evidence__command_preview_terminal_closure_certificate_witness_ref="examples/other-certificate.json",
        command_preview_decision_value_request_evidence__command_preview_operator_response_binding_ref="examples/other-response-binding.json",
        command_preview_decision_value_request_evidence__command_preview_operator_response_witness_ref="examples/other-response.json",
        command_preview_decision_value_request_evidence__command_preview_operator_approval_request_binding_ref="examples/other-approval.json",
        command_preview_decision_value_request_evidence__command_preview_ref="examples/other-command-preview.json",
        command_preview_decision_value_request_evidence__redacted_command_preview="gh pr create --body raw",
        command_preview_decision_value_request_evidence__command_preview_bound=False,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
        example_paths=(path,)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "command_preview_decision_value_request_evidence.source_request_id expected" in serialized_errors
    assert "command_preview_decision_value_request_evidence.source_request_ref expected" in serialized_errors
    assert "command_preview_decision_value_request_evidence.source_request_status expected" in serialized_errors
    assert "command_preview_decision_value_request_evidence.source_rejection_binding_id expected" in serialized_errors
    assert "command_preview_decision_value_request_evidence.operator_decision_ref expected" in serialized_errors
    assert "command_preview_decision_value_request_evidence.allowed_decision_values expected" in serialized_errors
    assert (
        "command_preview_decision_value_request_evidence.command_preview_terminal_closure_certificate_witness_ref expected"
        in serialized_errors
    )
    assert (
        "command_preview_decision_value_request_evidence.command_preview_operator_response_binding_ref expected"
        in serialized_errors
    )
    assert (
        "command_preview_decision_value_request_evidence.command_preview_operator_response_witness_ref expected"
        in serialized_errors
    )
    assert (
        "command_preview_decision_value_request_evidence.command_preview_operator_approval_request_binding_ref expected"
        in serialized_errors
    )
    assert "command_preview_decision_value_request_evidence.command_preview_ref expected" in serialized_errors
    assert "command_preview_decision_value_request_evidence.redacted_command_preview expected" in serialized_errors
    assert "command_preview_decision_value_request_evidence.command_preview_bound expected" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_record_rejects_mutation_route(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_record(
        witness_ref="POST /api/v1/harness/github-pr/terminal-decision-value-record"
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "witness_ref" in serialized_errors
    assert "mutation route string" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_record_rejects_secret_like_value(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_record(next_action="Mint with sk-forbiddencredential")
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_record_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json", "--example", str(DEFAULT_EXAMPLES[0])])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["example_count"] == 1
    assert payload["decision_value"] == EXPECTED_DECISION_VALUE
