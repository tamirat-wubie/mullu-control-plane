"""Test GitHub PR terminal closure operator approval gate validation.

Purpose: verify terminal closure certificate minting is blocked until an
explicit operator approval decision exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_approval_gate.
Invariants:
  - Candidate binding remains explicit.
  - Operator approval remains AwaitingEvidence.
  - Mutation authority and terminal closure claims fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_terminal_closure_operator_approval_gate as validator


def test_github_pr_terminal_closure_operator_approval_gate_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_terminal_closure_operator_approval_gate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_candidate_ref == validator.EXPECTED_SOURCE_CANDIDATE_REF


def test_github_pr_terminal_closure_operator_approval_gate_rejects_approval_overclaim() -> None:
    payload = validator.build_mutated_terminal_closure_operator_approval_gate(
        operator_approval_collected=True,
        terminal_closure_certificate_minted=True,
        terminal_closure_authorized=True,
        approval_gate__operator_approval_collected=True,
        approval_gate__terminal_closure_certificate_minted=True,
        approval_gate__terminal_closure_authorized=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_approval_gate_semantics(payload, _source_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "operator_approval_collected must be false" in serialized_errors
    assert "terminal_closure_certificate_minted must be false" in serialized_errors
    assert "terminal_closure_authorized must be false" in serialized_errors
    assert "approval_gate.operator_approval_collected must be false" in serialized_errors
    assert "approval_gate.terminal_closure_certificate_minted must be false" in serialized_errors
    assert "approval_gate.terminal_closure_authorized must be false" in serialized_errors


def test_github_pr_terminal_closure_operator_approval_gate_rejects_candidate_binding_drift() -> None:
    payload = validator.build_mutated_terminal_closure_operator_approval_gate(
        source_candidate_ref="examples/other-candidate.json",
        approval_gate__source_candidate_binding_id="other_binding",
        terminal_closure_certificate_candidate_ready=False,
        approval_gate__candidate_ready=False,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_approval_gate_semantics(payload, _source_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_candidate_ref expected" in serialized_errors
    assert "approval_gate.source_candidate_binding_id expected" in serialized_errors
    assert "terminal_closure_certificate_candidate_ready must be true" in serialized_errors
    assert "approval_gate.candidate_ready must be true" in serialized_errors


def test_github_pr_terminal_closure_operator_approval_gate_rejects_actual_diff_candidate_evidence_drift() -> None:
    payload = validator.build_mutated_terminal_closure_operator_approval_gate(
        approval_gate__actual_diff_candidate_evidence__actual_diff_terminal_closure_certificate_witness_ref=(
            "examples/other-terminal-witness.json"
        ),
        approval_gate__actual_diff_candidate_evidence__actual_diff_effect_reconciliation_witness_ref=(
            "examples/other-effect-witness.json"
        ),
        approval_gate__actual_diff_candidate_evidence__actual_diff_operator_response_witness_ref=(
            "examples/other-response.json"
        ),
        approval_gate__actual_diff_candidate_evidence__actual_diff_approval_request_binding_ref=(
            "examples/other-approval.json"
        ),
        approval_gate__actual_diff_candidate_evidence__actual_non_empty_diff_receipt_ref=(
            "witness://other-diff-receipt"
        ),
        approval_gate__actual_diff_candidate_evidence__changed_file_refs=["evidence://redacted-file-change-candidate/other"],
        approval_gate__actual_diff_candidate_evidence__diff_refs=["evidence://redacted-diff-candidate/other"],
        approval_gate__actual_diff_candidate_evidence__redacted_diff_bundle_ref="digest://other-bundle",
        approval_gate__actual_diff_candidate_evidence__redacted_output_ref="witness://other-output",
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_approval_gate_semantics(payload, _source_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "approval_gate.actual_diff_candidate_evidence.actual_diff_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "approval_gate.actual_diff_candidate_evidence.actual_diff_effect_reconciliation_witness_ref expected" in serialized_errors
    assert "approval_gate.actual_diff_candidate_evidence.actual_diff_operator_response_witness_ref expected" in serialized_errors
    assert "approval_gate.actual_diff_candidate_evidence.actual_diff_approval_request_binding_ref expected" in serialized_errors
    assert "approval_gate.actual_diff_candidate_evidence.actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "approval_gate.actual_diff_candidate_evidence.changed_file_refs expected" in serialized_errors
    assert "approval_gate.actual_diff_candidate_evidence.diff_refs expected" in serialized_errors
    assert "approval_gate.actual_diff_candidate_evidence.redacted_diff_bundle_ref expected" in serialized_errors
    assert "approval_gate.actual_diff_candidate_evidence.redacted_output_ref expected" in serialized_errors


def test_github_pr_terminal_closure_operator_approval_gate_rejects_mutation_authority() -> None:
    payload = validator.build_mutated_terminal_closure_operator_approval_gate(
        authority_granted=True,
        terminal_closure=True,
        authority_denials__repository_write_enabled=True,
        authority_denials__terminal_closure=True,
        effect_boundary__repository_written_by_gate=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_approval_gate_semantics(payload, _source_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_granted must be false" in serialized_errors
    assert "terminal_closure expected False" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors
    assert "effect_boundary.repository_written_by_gate must be false" in serialized_errors


def test_github_pr_terminal_closure_operator_approval_gate_rejects_remaining_witness_drift() -> None:
    payload = validator.build_mutated_terminal_closure_operator_approval_gate(
        remaining_witnesses=list(reversed(validator.EXPECTED_REMAINING_WITNESSES)),
    )

    errors: list[str] = []
    validator._validate_terminal_closure_operator_approval_gate_semantics(payload, _source_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must require operator decision before certificate" in serialized_errors
    assert len(errors) >= 1
    assert payload["remaining_witnesses"][0]["witness_kind"] == "terminal_closure_certificate"


def test_github_pr_terminal_closure_operator_approval_gate_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_terminal_closure_operator_approval_gate(
        requested_operator_decision_ref="POST /api/github/terminal-closure approval",
    )
    payload["approval_gate"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_terminal_closure_operator_approval_gate_semantics(payload, _source_candidate(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_terminal_closure_operator_approval_gate_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-terminal-closure-operator-approval-gate-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_candidate_ref"] == validator.EXPECTED_SOURCE_CANDIDATE_REF


def _source_candidate() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_CANDIDATE_EXAMPLES[0].read_text(encoding="utf-8"))
