"""Tests for GitHub PR terminal closure operator decision value request.

Purpose: prove the request asks for an explicit terminal closure decision value
without collecting a value or granting certificate/terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.
Invariants:
  - The default request validates.
  - Collected decision values fail closed.
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

from scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_ALLOWED_VALUES,
    build_mutated_operator_decision_value_request,
    main,
    validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request,
)


def _write_payload(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "github-pr-terminal-closure-operator-decision-value-request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_github_pr_terminal_closure_operator_decision_value_request_accepts_default_fixture() -> None:
    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.allowed_decision_values == EXPECTED_ALLOWED_VALUES
    assert validation.source_rejection_witness_ref.endswith(
        "agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection.foundation.json"
    )


def test_github_pr_terminal_closure_operator_decision_value_request_rejects_collected_value(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_request(
        operator_decision_value_collected=True,
        explicit_operator_decision_value_present=True,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_decision_value_collected" in serialized_errors
    assert "explicit_operator_decision_value_present" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_request_rejects_certificate_minting(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_request(
        terminal_closure_certificate_minted=True,
        terminal_closure_authorized=True,
        request_controls__certificate_minting_on_request=True,
        request_controls__terminal_authority_on_request=True,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_closure_certificate_minted" in serialized_errors
    assert "terminal_closure_authorized" in serialized_errors
    assert "terminal_authority_on_request" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_request_rejects_bad_decision_values(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_request()
    payload["allowed_decision_values"] = ["approve", "deny"]
    payload["decision_value_requirements"][0]["decision_value"] = "approve"
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "allowed_decision_values" in serialized_errors
    assert "decision values must match required order" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_request_rejects_command_preview_generic_rejection_drift(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_request(
        command_preview_generic_rejection_evidence__source_rejection_binding_id="other_rejection",
        command_preview_generic_rejection_evidence__source_rejection_witness_ref="examples/other-rejection.json",
        command_preview_generic_rejection_evidence__source_decision_contract_binding_id="other_contract",
        command_preview_generic_rejection_evidence__source_decision_contract_ref="examples/other-contract.json",
        command_preview_generic_rejection_evidence__rejection_id="other-rejection",
        command_preview_generic_rejection_evidence__operator_decision_ref="approval://other",
        command_preview_generic_rejection_evidence__requires_command_preview_generic_rejection_evidence=False,
        command_preview_generic_rejection_evidence__requires_command_preview_operator_approval_gate_evidence=False,
        command_preview_generic_rejection_evidence__requires_command_preview_terminal_closure_certificate_witness=False,
        command_preview_generic_rejection_evidence__command_preview_terminal_closure_certificate_witness_ref="examples/other-certificate.json",
        command_preview_generic_rejection_evidence__command_preview_operator_response_binding_ref="examples/other-response-binding.json",
        command_preview_generic_rejection_evidence__command_preview_operator_response_witness_ref="examples/other-response.json",
        command_preview_generic_rejection_evidence__command_preview_operator_approval_request_binding_ref="examples/other-approval.json",
        command_preview_generic_rejection_evidence__command_preview_ref="examples/other-command-preview.json",
        command_preview_generic_rejection_evidence__redacted_command_preview="gh pr merge --delete-branch",
        command_preview_generic_rejection_evidence__command_preview_bound=False,
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
        example_paths=(path,)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "command_preview_generic_rejection_evidence.source_rejection_binding_id expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.source_rejection_witness_ref expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.source_decision_contract_binding_id expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.source_decision_contract_ref expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.rejection_id expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.operator_decision_ref expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.requires_command_preview_generic_rejection_evidence must be true" in serialized_errors
    assert "command_preview_generic_rejection_evidence.requires_command_preview_operator_approval_gate_evidence must be true" in serialized_errors
    assert "command_preview_generic_rejection_evidence.requires_command_preview_terminal_closure_certificate_witness must be true" in serialized_errors
    assert "command_preview_generic_rejection_evidence.command_preview_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.command_preview_operator_response_binding_ref expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.command_preview_operator_response_witness_ref expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.command_preview_operator_approval_request_binding_ref expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.command_preview_ref expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.redacted_command_preview expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.command_preview_bound expected" in serialized_errors
    assert "command_preview_generic_rejection_evidence.command_preview_bound must be true" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_request_rejects_actual_diff_generic_rejection_drift(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_request(
        actual_diff_generic_rejection_evidence__source_rejection_binding_id="other_rejection",
        actual_diff_generic_rejection_evidence__source_rejection_witness_ref="examples/other-rejection.json",
        actual_diff_generic_rejection_evidence__source_decision_contract_binding_id="other_contract",
        actual_diff_generic_rejection_evidence__source_decision_contract_ref="examples/other-contract.json",
        actual_diff_generic_rejection_evidence__rejection_id="other-rejection",
        actual_diff_generic_rejection_evidence__operator_decision_ref="approval://other",
        actual_diff_generic_rejection_evidence__actual_diff_terminal_closure_certificate_witness_ref="examples/other-certificate.json",
        actual_diff_generic_rejection_evidence__actual_diff_operator_response_witness_ref="examples/other-response.json",
        actual_diff_generic_rejection_evidence__actual_diff_approval_request_binding_ref="examples/other-approval.json",
        actual_diff_generic_rejection_evidence__actual_non_empty_diff_receipt_ref="witness://other",
        actual_diff_generic_rejection_evidence__changed_file_refs=["evidence://other-file"],
        actual_diff_generic_rejection_evidence__diff_refs=["evidence://other-diff"],
        actual_diff_generic_rejection_evidence__redacted_diff_bundle_ref="digest://other",
        actual_diff_generic_rejection_evidence__redacted_output_ref="witness://other-output",
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
        example_paths=(path,)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "actual_diff_generic_rejection_evidence.source_rejection_binding_id expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.source_rejection_witness_ref expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.source_decision_contract_binding_id expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.source_decision_contract_ref expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.rejection_id expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.operator_decision_ref expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.actual_diff_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.actual_diff_operator_response_witness_ref expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.actual_diff_approval_request_binding_ref expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.changed_file_refs expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.diff_refs expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.redacted_diff_bundle_ref expected" in serialized_errors
    assert "actual_diff_generic_rejection_evidence.redacted_output_ref expected" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_request_rejects_mutation_route(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_request(
        source_rejection_witness_ref="POST /api/v1/harness/github-pr/terminal-decision"
    )
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_rejection_witness_ref" in serialized_errors
    assert "mutation route string" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_request_rejects_secret_like_value(
    tmp_path: Path,
) -> None:
    payload = build_mutated_operator_decision_value_request(next_action="Provide sk-forbiddencredential")
    path = _write_payload(tmp_path, payload)

    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
        example_paths=(path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors


def test_github_pr_terminal_closure_operator_decision_value_request_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json", "--example", str(DEFAULT_EXAMPLES[0])])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["example_count"] == 1
    assert payload["allowed_decision_values"] == list(EXPECTED_ALLOWED_VALUES)
