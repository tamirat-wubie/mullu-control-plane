"""Test GitHub PR terminal closure operator decision contract validation.

Purpose: verify terminal closure certificate minting requires an explicit typed
operator decision value.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_contract.
Invariants:
  - Approval-gate binding remains explicit.
  - Generic continuation is not a decision value.
  - Mutation authority and terminal closure claims fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_contract as validator


def test_github_pr_terminal_closure_operator_decision_contract_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_contract()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_approval_gate_ref == validator.EXPECTED_SOURCE_APPROVAL_GATE_REF


def test_github_pr_terminal_closure_operator_decision_contract_rejects_decision_overclaim() -> None:
    payload = validator.build_mutated_terminal_closure_operator_decision_contract(
        operator_decision_collected=True,
        terminal_closure_certificate_minted=True,
        terminal_closure_authorized=True,
        decision_contract__operator_decision_collected=True,
        decision_contract__terminal_closure_certificate_minted=True,
        decision_contract__terminal_closure_authorized=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_decision_contract_semantics(payload, _source_gate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "operator_decision_collected must be false" in serialized_errors
    assert "terminal_closure_certificate_minted must be false" in serialized_errors
    assert "terminal_closure_authorized must be false" in serialized_errors
    assert "decision_contract.operator_decision_collected must be false" in serialized_errors
    assert "decision_contract.terminal_closure_certificate_minted must be false" in serialized_errors
    assert "decision_contract.terminal_closure_authorized must be false" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_contract_rejects_gate_binding_drift() -> None:
    payload = validator.build_mutated_terminal_closure_operator_decision_contract(
        source_approval_gate_ref="examples/other-gate.json",
        decision_contract__source_approval_gate_binding_id="other_binding",
        decision_contract__source_approval_gate_ref="examples/other-gate.json",
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_decision_contract_semantics(payload, _source_gate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_approval_gate_ref expected" in serialized_errors
    assert "decision_contract.source_approval_gate_binding_id expected" in serialized_errors
    assert "decision_contract.source_approval_gate_ref expected" in serialized_errors
    assert len(errors) >= 3


def test_github_pr_terminal_closure_operator_decision_contract_rejects_actual_diff_approval_gate_drift() -> None:
    payload = validator.build_mutated_terminal_closure_operator_decision_contract(
        decision_contract__actual_diff_approval_gate_evidence__source_approval_gate_binding_id="other_gate",
        decision_contract__actual_diff_approval_gate_evidence__source_approval_gate_ref="examples/other-gate.json",
        decision_contract__actual_diff_approval_gate_evidence__operator_decision_ref="approval://other-decision",
        decision_contract__actual_diff_approval_gate_evidence__actual_diff_terminal_closure_certificate_witness_ref=(
            "examples/other-terminal-witness.json"
        ),
        decision_contract__actual_diff_approval_gate_evidence__actual_diff_effect_reconciliation_witness_ref=(
            "examples/other-effect-witness.json"
        ),
        decision_contract__actual_diff_approval_gate_evidence__actual_diff_operator_response_witness_ref=(
            "examples/other-response.json"
        ),
        decision_contract__actual_diff_approval_gate_evidence__actual_diff_approval_request_binding_ref=(
            "examples/other-approval.json"
        ),
        decision_contract__actual_diff_approval_gate_evidence__actual_non_empty_diff_receipt_ref=(
            "witness://other-diff-receipt"
        ),
        decision_contract__actual_diff_approval_gate_evidence__changed_file_refs=[
            "evidence://redacted-file-change-candidate/other"
        ],
        decision_contract__actual_diff_approval_gate_evidence__diff_refs=["evidence://redacted-diff-candidate/other"],
        decision_contract__actual_diff_approval_gate_evidence__redacted_diff_bundle_ref="digest://other-bundle",
        decision_contract__actual_diff_approval_gate_evidence__redacted_output_ref="witness://other-output",
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_decision_contract_semantics(payload, _source_gate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "decision_contract.actual_diff_approval_gate_evidence.source_approval_gate_binding_id expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.source_approval_gate_ref expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.operator_decision_ref expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.actual_diff_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.actual_diff_effect_reconciliation_witness_ref expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.actual_diff_operator_response_witness_ref expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.actual_diff_approval_request_binding_ref expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.changed_file_refs expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.diff_refs expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.redacted_diff_bundle_ref expected" in serialized_errors
    assert "decision_contract.actual_diff_approval_gate_evidence.redacted_output_ref expected" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_contract_rejects_bad_decision_shape() -> None:
    payload = validator.build_mutated_terminal_closure_operator_decision_contract(
        decision_contract__allowed_decision_values=["continue"],
        decision_contract__generic_continuation_rejected=False,
        decision_contract__decision_value_source="chat_continuation",
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_decision_contract_semantics(payload, _source_gate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "decision_contract.allowed_decision_values expected" in serialized_errors
    assert "decision_contract.generic_continuation_rejected must be true" in serialized_errors
    assert "decision_contract.decision_value_source expected 'operator_explicit_input_only'" in serialized_errors
    assert len(errors) >= 3


def test_github_pr_terminal_closure_operator_decision_contract_rejects_mutation_authority() -> None:
    payload = validator.build_mutated_terminal_closure_operator_decision_contract(
        authority_granted=True,
        terminal_closure=True,
        authority_denials__repository_write_enabled=True,
        authority_denials__terminal_closure=True,
        effect_boundary__repository_written_by_contract=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_decision_contract_semantics(payload, _source_gate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_granted must be false" in serialized_errors
    assert "terminal_closure expected False" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors
    assert "effect_boundary.repository_written_by_contract must be false" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_contract_rejects_remaining_witness_drift() -> None:
    payload = validator.build_mutated_terminal_closure_operator_decision_contract(
        remaining_witnesses=list(reversed(validator.EXPECTED_REMAINING_WITNESSES)),
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_decision_contract_semantics(payload, _source_gate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must require explicit decision value before certificate" in serialized_errors
    assert len(errors) >= 1
    assert payload["remaining_witnesses"][0]["witness_kind"] == "terminal_closure_certificate"


def test_github_pr_terminal_closure_operator_decision_contract_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_terminal_closure_operator_decision_contract(
        requested_operator_decision_ref="POST /api/github/terminal-closure decision",
    )
    payload["decision_contract"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_terminal_closure_operator_decision_contract_semantics(payload, _source_gate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_terminal_closure_operator_decision_contract_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-terminal-closure-operator-decision-contract-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_approval_gate_ref"] == validator.EXPECTED_SOURCE_APPROVAL_GATE_REF


def _source_gate() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_APPROVAL_GATE_EXAMPLES[0].read_text(encoding="utf-8"))
