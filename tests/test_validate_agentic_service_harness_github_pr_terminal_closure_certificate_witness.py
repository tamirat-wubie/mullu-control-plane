"""Test GitHub PR terminal closure certificate witness validation.

Purpose: verify the PR terminal closure certificate witness remains read-only,
uncertified, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_witness.
Invariants:
  - Terminal closure certificate must consume command-preview effect reconciliation evidence.
  - Terminal closure certificate must consume actual-diff effect reconciliation evidence.
  - Missing effect reconciliation never grants terminal closure.
  - Remaining witnesses are empty because this is the final certificate request.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_terminal_closure_certificate_witness as validator


def test_github_pr_terminal_closure_certificate_witness_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_terminal_closure_certificate_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_effect_reconciliation_witness_ref == validator.EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF
    assert (
        validation.command_preview_effect_reconciliation_witness_ref
        == validator.EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF
    )
    assert (
        validation.actual_diff_effect_reconciliation_witness_ref
        == validator.EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF
    )


def test_github_pr_terminal_closure_certificate_witness_rejects_collected_authority() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_witness(
        terminal_closure_certificate_collected=True,
        authority_granted=True,
        terminal_closure_certificate__effect_reconciliation_collected=True,
        terminal_closure_certificate__requires_command_preview_effect_reconciliation_witness=False,
        terminal_closure_certificate__command_preview_bound=False,
        terminal_closure_certificate__operator_response_bound=False,
        terminal_closure_certificate__requires_actual_diff_effect_reconciliation_witness=False,
        terminal_closure_certificate__terminal_closure_certificate_collected=True,
        terminal_closure_certificate__terminal_closure_authorized=True,
        authority_denials__authority_granted=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_witness_semantics(
        payload, _source_effect_reconciliation_witness(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "terminal_closure_certificate_collected must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "terminal_closure_certificate.effect_reconciliation_collected must be false" in serialized_errors
    assert (
        "terminal_closure_certificate.requires_command_preview_effect_reconciliation_witness must be true"
        in serialized_errors
    )
    assert "terminal_closure_certificate.command_preview_bound must be true" in serialized_errors
    assert "terminal_closure_certificate.operator_response_bound must be true" in serialized_errors
    assert (
        "terminal_closure_certificate.requires_actual_diff_effect_reconciliation_witness must be true"
        in serialized_errors
    )
    assert "terminal_closure_certificate.terminal_closure_certificate_collected must be false" in serialized_errors
    assert "terminal_closure_certificate.terminal_closure_authorized must be false" in serialized_errors
    assert "authority_denials.authority_granted must be false" in serialized_errors


def test_github_pr_terminal_closure_certificate_witness_rejects_effect_authority() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_witness(
        authority_denials__pull_request_merge_enabled=True,
        authority_denials__repository_write_enabled=True,
        authority_denials__terminal_closure=True,
        effect_boundary__pull_request_merged=True,
        effect_boundary__branch_deleted=True,
        effect_boundary__repository_written=True,
        effect_boundary__connector_called=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_witness_semantics(
        payload, _source_effect_reconciliation_witness(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "authority_denials.pull_request_merge_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors
    assert "effect_boundary.pull_request_merged must be false" in serialized_errors
    assert "effect_boundary.branch_deleted must be false" in serialized_errors
    assert "effect_boundary.repository_written must be false" in serialized_errors
    assert "effect_boundary.connector_called must be false" in serialized_errors


def test_github_pr_terminal_closure_certificate_witness_rejects_remaining_witness_drift() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_witness(
        remaining_witnesses=[
            {
                "witness_kind": "terminal_closure_certificate",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://github-pr-terminal-closure-certificate",
                "authority_granted": False,
            }
        ],
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_witness_semantics(
        payload, _source_effect_reconciliation_witness(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must be empty after terminal closure certificate request" in serialized_errors
    assert len(errors) >= 1
    assert payload["remaining_witnesses"][0]["witness_kind"] == "terminal_closure_certificate"


def test_github_pr_terminal_closure_certificate_witness_rejects_command_preview_effect_reconciliation_drift() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_witness(
        terminal_closure_certificate__command_preview_effect_reconciliation_witness_ref="examples/drift.json",
        terminal_closure_certificate__command_preview_ci_gate_before_ready_for_review_witness_ref="examples/drift.json",
        terminal_closure_certificate__command_preview_repository_effect_rollback_plan_witness_ref="examples/drift.json",
        terminal_closure_certificate__command_preview_uao_admission_witness_ref="examples/drift.json",
        terminal_closure_certificate__command_preview_branch_write_binding_ref="examples/drift.json",
        terminal_closure_certificate__command_preview_operator_response_binding_ref="examples/drift.json",
        terminal_closure_certificate__command_preview_operator_response_witness_ref="examples/drift.json",
        terminal_closure_certificate__command_preview_operator_approval_request_binding_ref="examples/drift.json",
        terminal_closure_certificate__command_preview_ref="examples/drift.json",
        terminal_closure_certificate__redacted_command_preview="gh pr create --body leaked",
        terminal_closure_certificate__argument_vector_template=["gh", "pr", "create"],
        terminal_closure_certificate__placeholder_refs=["placeholder://drift"],
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_witness_semantics(
        payload, _source_effect_reconciliation_witness(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "terminal_closure_certificate.command_preview_effect_reconciliation_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.command_preview_ci_gate_before_ready_for_review_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.command_preview_repository_effect_rollback_plan_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.command_preview_uao_admission_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.command_preview_branch_write_binding_ref" in serialized_errors
    assert "terminal_closure_certificate.command_preview_operator_response_binding_ref" in serialized_errors
    assert "terminal_closure_certificate.command_preview_operator_response_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.command_preview_operator_approval_request_binding_ref" in serialized_errors
    assert "terminal_closure_certificate.command_preview_ref" in serialized_errors
    assert "terminal_closure_certificate.redacted_command_preview" in serialized_errors
    assert "terminal_closure_certificate.argument_vector_template" in serialized_errors
    assert "terminal_closure_certificate.placeholder_refs" in serialized_errors


def test_github_pr_terminal_closure_certificate_witness_rejects_actual_diff_effect_reconciliation_drift() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_witness(
        terminal_closure_certificate__actual_diff_effect_reconciliation_witness_ref="examples/drift.json",
        terminal_closure_certificate__actual_diff_ci_gate_before_ready_for_review_witness_ref="examples/drift.json",
        terminal_closure_certificate__actual_diff_repository_effect_rollback_plan_witness_ref="examples/drift.json",
        terminal_closure_certificate__actual_diff_uao_admission_witness_ref="examples/drift.json",
        terminal_closure_certificate__actual_diff_branch_write_binding_ref="examples/drift.json",
        terminal_closure_certificate__actual_diff_operator_response_witness_ref="examples/drift.json",
        terminal_closure_certificate__actual_diff_approval_request_binding_ref="examples/drift.json",
        terminal_closure_certificate__actual_non_empty_diff_receipt_ref="witness://drift",
        terminal_closure_certificate__changed_file_refs=["evidence://drift-file"],
        terminal_closure_certificate__diff_refs=["evidence://drift-diff"],
        terminal_closure_certificate__redacted_diff_bundle_ref="digest://drift-bundle",
        terminal_closure_certificate__redacted_output_ref="witness://drift-output",
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_witness_semantics(
        payload, _source_effect_reconciliation_witness(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "terminal_closure_certificate.actual_diff_effect_reconciliation_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.actual_diff_ci_gate_before_ready_for_review_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.actual_diff_repository_effect_rollback_plan_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.actual_diff_uao_admission_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.actual_diff_branch_write_binding_ref" in serialized_errors
    assert "terminal_closure_certificate.actual_diff_operator_response_witness_ref" in serialized_errors
    assert "terminal_closure_certificate.actual_diff_approval_request_binding_ref" in serialized_errors
    assert "terminal_closure_certificate.actual_non_empty_diff_receipt_ref" in serialized_errors
    assert "terminal_closure_certificate.changed_file_refs" in serialized_errors
    assert "terminal_closure_certificate.diff_refs" in serialized_errors
    assert "terminal_closure_certificate.redacted_diff_bundle_ref" in serialized_errors
    assert "terminal_closure_certificate.redacted_output_ref" in serialized_errors


def test_github_pr_terminal_closure_certificate_witness_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_witness(
        requested_evidence_ref="POST /api/github/terminal-closure authority",
    )
    payload["terminal_closure_certificate"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_witness_semantics(
        payload, _source_effect_reconciliation_witness(), errors, "mutated"
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_terminal_closure_certificate_witness_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-terminal-closure-certificate-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert (
        file_payload["source_effect_reconciliation_witness_ref"]
        == validator.EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF
    )
    assert (
        file_payload["command_preview_effect_reconciliation_witness_ref"]
        == validator.EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF
    )
    assert (
        file_payload["actual_diff_effect_reconciliation_witness_ref"]
        == validator.EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF
    )


def _source_effect_reconciliation_witness() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_EFFECT_RECONCILIATION_EXAMPLES[0].read_text(encoding="utf-8"))
