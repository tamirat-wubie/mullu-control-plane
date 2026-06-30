"""Test GitHub PR effect reconciliation witness validation.

Purpose: verify the PR effect reconciliation witness remains read-only,
uncollected, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_effect_reconciliation_witness.
Invariants:
  - Effect reconciliation must consume command-preview CI gate evidence.
  - Effect reconciliation must consume actual-diff CI gate evidence.
  - Missing effect reconciliation never grants terminal closure or merge effects.
  - Remaining witnesses are empty because this is the final missing-evidence request.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_effect_reconciliation_witness as validator


def test_github_pr_effect_reconciliation_witness_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_effect_reconciliation_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_ci_gate_before_ready_for_review_witness_ref == validator.EXPECTED_SOURCE_CI_GATE_WITNESS_REF
    assert (
        validation.command_preview_ci_gate_before_ready_for_review_witness_ref
        == validator.EXPECTED_SOURCE_CI_GATE_WITNESS_REF
    )
    assert validation.actual_diff_ci_gate_before_ready_for_review_witness_ref == validator.EXPECTED_SOURCE_CI_GATE_WITNESS_REF


def test_github_pr_effect_reconciliation_witness_rejects_collected_authority() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        effect_reconciliation_collected=True,
        authority_granted=True,
        effect_reconciliation__requires_command_preview_ci_gate_before_ready_for_review_witness=False,
        effect_reconciliation__command_preview_bound=False,
        effect_reconciliation__operator_response_bound=False,
        effect_reconciliation__requires_actual_diff_ci_gate_before_ready_for_review_witness=False,
        effect_reconciliation__ci_gate_before_ready_for_review_satisfied=True,
        effect_reconciliation__effect_reconciliation_collected=True,
        effect_reconciliation__terminal_closure_authorized_after_reconciliation=True,
        authority_denials__authority_granted=True,
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "effect_reconciliation_collected must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "effect_reconciliation.requires_command_preview_ci_gate_before_ready_for_review_witness must be true" in serialized_errors
    assert "effect_reconciliation.command_preview_bound must be true" in serialized_errors
    assert "effect_reconciliation.operator_response_bound must be true" in serialized_errors
    assert "effect_reconciliation.requires_actual_diff_ci_gate_before_ready_for_review_witness must be true" in serialized_errors
    assert "effect_reconciliation.ci_gate_before_ready_for_review_satisfied must be false" in serialized_errors
    assert "effect_reconciliation.effect_reconciliation_collected must be false" in serialized_errors
    assert "effect_reconciliation.terminal_closure_authorized_after_reconciliation must be false" in serialized_errors
    assert "authority_denials.authority_granted must be false" in serialized_errors


def test_github_pr_effect_reconciliation_witness_rejects_effect_authority() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        authority_denials__pull_request_merge_enabled=True,
        authority_denials__repository_write_enabled=True,
        authority_denials__terminal_closure=True,
        effect_boundary__pull_request_merged=True,
        effect_boundary__branch_deleted=True,
        effect_boundary__repository_written=True,
        effect_boundary__connector_called=True,
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_denials.pull_request_merge_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors
    assert "effect_boundary.pull_request_merged must be false" in serialized_errors
    assert "effect_boundary.branch_deleted must be false" in serialized_errors
    assert "effect_boundary.repository_written must be false" in serialized_errors
    assert "effect_boundary.connector_called must be false" in serialized_errors


def test_github_pr_effect_reconciliation_witness_rejects_actual_diff_ci_gate_drift() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        effect_reconciliation__actual_diff_ci_gate_before_ready_for_review_witness_ref="examples/drift.json",
        effect_reconciliation__actual_diff_repository_effect_rollback_plan_witness_ref="examples/drift.json",
        effect_reconciliation__actual_diff_uao_admission_witness_ref="examples/drift.json",
        effect_reconciliation__actual_diff_branch_write_binding_ref="examples/drift.json",
        effect_reconciliation__actual_diff_operator_response_witness_ref="examples/drift.json",
        effect_reconciliation__actual_diff_approval_request_binding_ref="examples/drift.json",
        effect_reconciliation__actual_non_empty_diff_receipt_ref="witness://drift",
        effect_reconciliation__changed_file_refs=["evidence://drift-file"],
        effect_reconciliation__diff_refs=["evidence://drift-diff"],
        effect_reconciliation__redacted_diff_bundle_ref="digest://drift-bundle",
        effect_reconciliation__redacted_output_ref="witness://drift-output",
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "effect_reconciliation.actual_diff_ci_gate_before_ready_for_review_witness_ref" in serialized_errors
    assert "effect_reconciliation.actual_diff_repository_effect_rollback_plan_witness_ref" in serialized_errors
    assert "effect_reconciliation.actual_diff_uao_admission_witness_ref" in serialized_errors
    assert "effect_reconciliation.actual_diff_branch_write_binding_ref" in serialized_errors
    assert "effect_reconciliation.actual_diff_operator_response_witness_ref" in serialized_errors
    assert "effect_reconciliation.actual_diff_approval_request_binding_ref" in serialized_errors
    assert "effect_reconciliation.actual_non_empty_diff_receipt_ref" in serialized_errors
    assert "effect_reconciliation.changed_file_refs" in serialized_errors
    assert "effect_reconciliation.diff_refs" in serialized_errors
    assert "effect_reconciliation.redacted_diff_bundle_ref" in serialized_errors
    assert "effect_reconciliation.redacted_output_ref" in serialized_errors


def test_github_pr_effect_reconciliation_witness_rejects_command_preview_ci_gate_drift() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        effect_reconciliation__command_preview_ci_gate_before_ready_for_review_witness_ref="examples/drift.json",
        effect_reconciliation__command_preview_repository_effect_rollback_plan_witness_ref="examples/drift.json",
        effect_reconciliation__command_preview_uao_admission_witness_ref="examples/drift.json",
        effect_reconciliation__command_preview_branch_write_binding_ref="examples/drift.json",
        effect_reconciliation__command_preview_operator_response_binding_ref="examples/drift.json",
        effect_reconciliation__command_preview_operator_response_witness_ref="examples/drift.json",
        effect_reconciliation__command_preview_operator_approval_request_binding_ref="examples/drift.json",
        effect_reconciliation__command_preview_ref="examples/drift.json",
        effect_reconciliation__redacted_command_preview="gh pr create --body leaked",
        effect_reconciliation__argument_vector_template=["gh", "pr", "create"],
        effect_reconciliation__placeholder_refs=["placeholder://drift"],
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "effect_reconciliation.command_preview_ci_gate_before_ready_for_review_witness_ref" in serialized_errors
    assert "effect_reconciliation.command_preview_repository_effect_rollback_plan_witness_ref" in serialized_errors
    assert "effect_reconciliation.command_preview_uao_admission_witness_ref" in serialized_errors
    assert "effect_reconciliation.command_preview_branch_write_binding_ref" in serialized_errors
    assert "effect_reconciliation.command_preview_operator_response_binding_ref" in serialized_errors
    assert "effect_reconciliation.command_preview_operator_response_witness_ref" in serialized_errors
    assert "effect_reconciliation.command_preview_operator_approval_request_binding_ref" in serialized_errors
    assert "effect_reconciliation.command_preview_ref" in serialized_errors
    assert "effect_reconciliation.redacted_command_preview" in serialized_errors
    assert "effect_reconciliation.argument_vector_template" in serialized_errors
    assert "effect_reconciliation.placeholder_refs" in serialized_errors


def test_github_pr_effect_reconciliation_witness_rejects_ci_gate_evidence_capsule_drift() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        command_preview_ci_gate_evidence__source_binding_id="agentic_service_harness_github_pr_drifted",
        command_preview_ci_gate_evidence__source_repository_effect_rollback_plan_witness_id="drifted_rollback",
        command_preview_ci_gate_evidence__source_uao_admission_witness_id="drifted_uao",
        command_preview_ci_gate_evidence__source_branch_write_binding_id="drifted_branch_write",
        command_preview_ci_gate_evidence__source_ci_gate_before_ready_for_review_collected=True,
        command_preview_ci_gate_evidence__source_ready_for_review_authorized_after_ci_gate=True,
        command_preview_ci_gate_evidence__source_pull_request_creation_authorized_after_ci_gate=True,
        command_preview_ci_gate_evidence__effect_reconciliation_consumes_command_preview_ci_gate_evidence=False,
        command_preview_ci_gate_evidence__effect_reconciliation_remains_non_authorizing=False,
        command_preview_ci_gate_evidence__terminal_closure_remains_blocked=False,
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "command_preview_ci_gate_evidence.source_binding_id" in serialized_errors
    assert "command_preview_ci_gate_evidence.source_repository_effect_rollback_plan_witness_id" in serialized_errors
    assert "command_preview_ci_gate_evidence.source_uao_admission_witness_id" in serialized_errors
    assert "command_preview_ci_gate_evidence.source_branch_write_binding_id" in serialized_errors
    assert (
        "command_preview_ci_gate_evidence.source_ci_gate_before_ready_for_review_collected must be false"
        in serialized_errors
    )
    assert (
        "command_preview_ci_gate_evidence.source_ready_for_review_authorized_after_ci_gate must be false"
        in serialized_errors
    )
    assert (
        "command_preview_ci_gate_evidence.source_pull_request_creation_authorized_after_ci_gate must be false"
        in serialized_errors
    )
    assert (
        "command_preview_ci_gate_evidence.effect_reconciliation_consumes_command_preview_ci_gate_evidence must be true"
        in serialized_errors
    )
    assert (
        "command_preview_ci_gate_evidence.effect_reconciliation_remains_non_authorizing must be true"
        in serialized_errors
    )
    assert "command_preview_ci_gate_evidence.terminal_closure_remains_blocked must be true" in serialized_errors


def test_github_pr_effect_reconciliation_witness_rejects_remaining_witness_drift() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        remaining_witnesses=[
            {
                "witness_kind": "effect_reconciliation",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://effect-reconciliation-before-terminal-closure",
                "authority_granted": False,
            }
        ],
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must be empty after effect reconciliation request" in serialized_errors
    assert len(errors) >= 1
    assert payload["remaining_witnesses"][0]["witness_kind"] == "effect_reconciliation"


def test_github_pr_effect_reconciliation_witness_rejects_actual_diff_ci_gate_drift() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        effect_reconciliation__requires_actual_diff_ci_gate_before_ready_for_review_witness=False,
        effect_reconciliation__actual_diff_ci_gate_before_ready_for_review_witness_ref="examples/wrong-ci-gate.json",
        effect_reconciliation__actual_diff_repository_effect_rollback_plan_witness_ref="examples/wrong-rollback.json",
        effect_reconciliation__actual_diff_uao_admission_witness_ref="examples/wrong-uao.json",
        effect_reconciliation__actual_diff_branch_write_binding_ref="examples/wrong-branch-write.json",
        effect_reconciliation__actual_diff_operator_response_witness_ref="examples/wrong-response.json",
        effect_reconciliation__actual_diff_approval_request_binding_ref="examples/wrong-approval.json",
        effect_reconciliation__actual_non_empty_diff_receipt_ref="witness://wrong-diff",
        effect_reconciliation__changed_file_refs=["evidence://wrong-file"],
        effect_reconciliation__diff_refs=["evidence://wrong-diff"],
        effect_reconciliation__redacted_diff_bundle_ref="digest://wrong-bundle",
        effect_reconciliation__redacted_output_ref="witness://wrong-output",
    )

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "effect_reconciliation.requires_actual_diff_ci_gate_before_ready_for_review_witness must be true" in serialized_errors
    assert "effect_reconciliation.actual_diff_ci_gate_before_ready_for_review_witness_ref expected" in serialized_errors
    assert "effect_reconciliation.actual_diff_repository_effect_rollback_plan_witness_ref expected" in serialized_errors
    assert "effect_reconciliation.actual_diff_uao_admission_witness_ref expected" in serialized_errors
    assert "effect_reconciliation.actual_diff_branch_write_binding_ref expected" in serialized_errors
    assert "effect_reconciliation.actual_diff_operator_response_witness_ref expected" in serialized_errors
    assert "effect_reconciliation.actual_diff_approval_request_binding_ref expected" in serialized_errors
    assert "effect_reconciliation.actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "effect_reconciliation.changed_file_refs expected" in serialized_errors
    assert "effect_reconciliation.diff_refs expected" in serialized_errors
    assert "effect_reconciliation.redacted_diff_bundle_ref expected" in serialized_errors
    assert "effect_reconciliation.redacted_output_ref expected" in serialized_errors


def test_github_pr_effect_reconciliation_witness_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_effect_reconciliation_witness(
        requested_evidence_ref="POST /api/github/effect-reconciliation authority",
    )
    payload["effect_reconciliation"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_effect_reconciliation_witness_semantics(payload, _source_ci_gate_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_effect_reconciliation_witness_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-effect-reconciliation-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_ci_gate_before_ready_for_review_witness_ref"] == validator.EXPECTED_SOURCE_CI_GATE_WITNESS_REF
    assert (
        file_payload["command_preview_ci_gate_before_ready_for_review_witness_ref"]
        == validator.EXPECTED_SOURCE_CI_GATE_WITNESS_REF
    )
    assert (
        file_payload["actual_diff_ci_gate_before_ready_for_review_witness_ref"]
        == validator.EXPECTED_SOURCE_CI_GATE_WITNESS_REF
    )


def _source_ci_gate_witness() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_CI_GATE_WITNESS_EXAMPLES[0].read_text(encoding="utf-8"))
