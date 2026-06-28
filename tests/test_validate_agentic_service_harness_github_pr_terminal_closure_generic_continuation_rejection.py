"""Test GitHub PR terminal closure generic continuation rejection validation.

Purpose: verify generic continuation is rejected as a terminal closure decision
value and cannot authorize certificate minting.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection.
Invariants:
  - Generic continuation is not accepted as operator approval.
  - The source decision contract binding remains explicit.
  - Mutation authority and terminal closure claims fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection as validator


def test_github_pr_terminal_closure_generic_continuation_rejection_passes() -> None:
    validation = (
        validator.validate_agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection()
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_decision_contract_ref == validator.EXPECTED_SOURCE_DECISION_CONTRACT_REF


def test_github_pr_terminal_closure_generic_continuation_rejection_rejects_approval_overclaim() -> None:
    payload = validator.build_mutated_generic_continuation_rejection(
        operator_decision_value_present=True,
        accepted_as_operator_approval=True,
        terminal_closure_certificate_minted=True,
        terminal_closure_authorized=True,
        continuation_rejection__operator_decision_value_present=True,
        continuation_rejection__accepted_as_operator_approval=True,
        continuation_rejection__terminal_closure_certificate_minted=True,
        continuation_rejection__terminal_closure_authorized=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_generic_continuation_rejection_semantics(
        payload, _source_contract(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "operator_decision_value_present must be false" in serialized_errors
    assert "accepted_as_operator_approval must be false" in serialized_errors
    assert "terminal_closure_certificate_minted must be false" in serialized_errors
    assert "terminal_closure_authorized must be false" in serialized_errors
    assert "continuation_rejection.operator_decision_value_present must be false" in serialized_errors
    assert "continuation_rejection.accepted_as_operator_approval must be false" in serialized_errors
    assert "continuation_rejection.terminal_closure_certificate_minted must be false" in serialized_errors
    assert "continuation_rejection.terminal_closure_authorized must be false" in serialized_errors


def test_github_pr_terminal_closure_generic_continuation_rejection_rejects_source_contract_drift() -> None:
    payload = validator.build_mutated_generic_continuation_rejection(
        source_decision_contract_ref="examples/other-contract.json",
        continuation_rejection__source_decision_contract_binding_id="other_binding",
        continuation_rejection__source_decision_contract_ref="examples/other-contract.json",
    )

    errors: list[str] = []
    validator._validate_terminal_closure_generic_continuation_rejection_semantics(
        payload, _source_contract(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "source_decision_contract_ref expected" in serialized_errors
    assert "continuation_rejection.source_decision_contract_binding_id expected" in serialized_errors
    assert "continuation_rejection.source_decision_contract_ref expected" in serialized_errors
    assert len(errors) >= 3


def test_github_pr_terminal_closure_generic_continuation_rejection_rejects_command_preview_decision_contract_drift() -> None:
    payload = validator.build_mutated_generic_continuation_rejection(
        continuation_rejection__command_preview_decision_contract_evidence__source_decision_contract_binding_id="other_binding",
        continuation_rejection__command_preview_decision_contract_evidence__source_decision_contract_ref="examples/other-contract.json",
        continuation_rejection__command_preview_decision_contract_evidence__operator_decision_ref="approval://other",
        continuation_rejection__command_preview_decision_contract_evidence__command_preview_terminal_closure_certificate_witness_ref="examples/other-certificate.json",
        continuation_rejection__command_preview_decision_contract_evidence__command_preview_effect_reconciliation_witness_ref="examples/other-effect.json",
        continuation_rejection__command_preview_decision_contract_evidence__command_preview_operator_response_binding_ref="examples/other-response-binding.json",
        continuation_rejection__command_preview_decision_contract_evidence__command_preview_operator_response_witness_ref="examples/other-response.json",
        continuation_rejection__command_preview_decision_contract_evidence__command_preview_operator_approval_request_binding_ref="examples/other-approval.json",
        continuation_rejection__command_preview_decision_contract_evidence__command_preview_ref="examples/other-command-preview.json",
        continuation_rejection__command_preview_decision_contract_evidence__redacted_command_preview="gh pr merge --delete-branch",
        continuation_rejection__command_preview_decision_contract_evidence__command_preview_bound=False,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_generic_continuation_rejection_semantics(
        payload, _source_contract(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "command_preview_decision_contract_evidence.source_decision_contract_binding_id expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.source_decision_contract_ref expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.operator_decision_ref expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.command_preview_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.command_preview_effect_reconciliation_witness_ref expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.command_preview_operator_response_binding_ref expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.command_preview_operator_response_witness_ref expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.command_preview_operator_approval_request_binding_ref expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.command_preview_ref expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.redacted_command_preview expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.command_preview_bound expected" in serialized_errors
    assert "command_preview_decision_contract_evidence.command_preview_bound must be true" in serialized_errors


def test_github_pr_terminal_closure_generic_continuation_rejection_rejects_actual_diff_decision_contract_drift() -> None:
    payload = validator.build_mutated_generic_continuation_rejection(
        continuation_rejection__actual_diff_decision_contract_evidence__source_decision_contract_binding_id="other_binding",
        continuation_rejection__actual_diff_decision_contract_evidence__source_decision_contract_ref="examples/other-contract.json",
        continuation_rejection__actual_diff_decision_contract_evidence__operator_decision_ref="approval://other",
        continuation_rejection__actual_diff_decision_contract_evidence__actual_diff_terminal_closure_certificate_witness_ref="examples/other-certificate.json",
        continuation_rejection__actual_diff_decision_contract_evidence__actual_diff_effect_reconciliation_witness_ref="examples/other-effect.json",
        continuation_rejection__actual_diff_decision_contract_evidence__actual_diff_operator_response_witness_ref="examples/other-response.json",
        continuation_rejection__actual_diff_decision_contract_evidence__actual_diff_approval_request_binding_ref="examples/other-approval.json",
        continuation_rejection__actual_diff_decision_contract_evidence__actual_non_empty_diff_receipt_ref="witness://other",
        continuation_rejection__actual_diff_decision_contract_evidence__changed_file_refs=["evidence://other-file"],
        continuation_rejection__actual_diff_decision_contract_evidence__diff_refs=["evidence://other-diff"],
        continuation_rejection__actual_diff_decision_contract_evidence__redacted_diff_bundle_ref="digest://other",
        continuation_rejection__actual_diff_decision_contract_evidence__redacted_output_ref="witness://other-output",
    )

    errors: list[str] = []
    validator._validate_terminal_closure_generic_continuation_rejection_semantics(
        payload, _source_contract(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "actual_diff_decision_contract_evidence.source_decision_contract_binding_id expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.source_decision_contract_ref expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.operator_decision_ref expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.actual_diff_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.actual_diff_effect_reconciliation_witness_ref expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.actual_diff_operator_response_witness_ref expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.actual_diff_approval_request_binding_ref expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.changed_file_refs expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.diff_refs expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.redacted_diff_bundle_ref expected" in serialized_errors
    assert "actual_diff_decision_contract_evidence.redacted_output_ref expected" in serialized_errors


def test_github_pr_terminal_closure_generic_continuation_rejection_rejects_decision_value_drift() -> None:
    payload = validator.build_mutated_generic_continuation_rejection(
        generic_continuation_rejected=False,
        continuation_rejection__observed_input_class="approval",
        continuation_rejection__required_decision_values=["continue"],
        continuation_rejection__generic_continuation_rejected=False,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_generic_continuation_rejection_semantics(
        payload, _source_contract(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "generic_continuation_rejected must be true" in serialized_errors
    assert "continuation_rejection.observed_input_class expected 'generic_continuation'" in serialized_errors
    assert "continuation_rejection.required_decision_values expected" in serialized_errors
    assert "continuation_rejection.generic_continuation_rejected must be true" in serialized_errors


def test_github_pr_terminal_closure_generic_continuation_rejection_rejects_mutation_authority() -> None:
    payload = validator.build_mutated_generic_continuation_rejection(
        authority_granted=True,
        terminal_closure=True,
        authority_denials__branch_write_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__ready_for_review_enabled=True,
        authority_denials__pull_request_merge_enabled=True,
        authority_denials__repository_write_enabled=True,
        authority_denials__terminal_closure=True,
        effect_boundary__repository_written_by_rejection=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_generic_continuation_rejection_semantics(
        payload, _source_contract(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "authority_granted must be false" in serialized_errors
    assert "terminal_closure expected False" in serialized_errors
    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.ready_for_review_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_merge_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors
    assert "effect_boundary.repository_written_by_rejection must be false" in serialized_errors


def test_github_pr_terminal_closure_generic_continuation_rejection_rejects_remaining_witness_drift() -> None:
    payload = validator.build_mutated_generic_continuation_rejection(
        remaining_witnesses=list(reversed(validator.EXPECTED_REMAINING_WITNESSES)),
    )

    errors: list[str] = []
    validator._validate_terminal_closure_generic_continuation_rejection_semantics(
        payload, _source_contract(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must preserve explicit decision before certificate" in serialized_errors
    assert len(errors) >= 1
    assert payload["remaining_witnesses"][0]["witness_kind"] == "terminal_closure_certificate"


def test_github_pr_terminal_closure_generic_continuation_rejection_rejects_mutation_route_and_secret_payload() -> None:
    payload = validator.build_mutated_generic_continuation_rejection(
        rejected_input_ref="POST /api/github/terminal-closure continue",
    )
    payload["continuation_rejection"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_terminal_closure_generic_continuation_rejection_semantics(
        payload, _source_contract(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_terminal_closure_generic_continuation_rejection_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "github-pr-terminal-closure-generic-continuation-rejection-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_decision_contract_ref"] == validator.EXPECTED_SOURCE_DECISION_CONTRACT_REF


def _source_contract() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_DECISION_CONTRACT_EXAMPLES[0].read_text(encoding="utf-8"))
