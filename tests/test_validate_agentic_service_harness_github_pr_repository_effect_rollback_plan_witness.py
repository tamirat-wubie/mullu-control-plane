"""Test GitHub PR repository-effect rollback-plan witness validation.

Purpose: verify the PR repository-effect rollback plan witness remains read-only,
uncollected, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_repository_effect_rollback_plan_witness.
Invariants:
  - Repository-effect rollback planning must consume command-preview UAO evidence.
  - Repository-effect rollback planning must consume actual-diff UAO evidence.
  - Missing repository-effect rollback plan never grants branch or PR effects.
  - Remaining witnesses block PR admission.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_repository_effect_rollback_plan_witness as validator


def test_github_pr_repository_effect_rollback_plan_witness_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_repository_effect_rollback_plan_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_uao_admission_witness_ref == validator.EXPECTED_SOURCE_UAO_ADMISSION_WITNESS_REF
    assert validation.command_preview_uao_admission_witness_ref == validator.EXPECTED_SOURCE_UAO_ADMISSION_WITNESS_REF
    assert validation.actual_diff_uao_admission_witness_ref == validator.EXPECTED_SOURCE_UAO_ADMISSION_WITNESS_REF


def test_github_pr_repository_effect_rollback_plan_witness_rejects_collected_authority() -> None:
    payload = validator.build_mutated_repository_effect_rollback_plan_witness(
        rollback_plan_collected=True,
        authority_granted=True,
        rollback_plan__requires_command_preview_uao_admission_witness=False,
        rollback_plan__requires_actual_diff_uao_admission_witness=False,
        rollback_plan__command_preview_bound=False,
        rollback_plan__operator_response_bound=False,
        rollback_plan__uao_admission_witness_satisfied=True,
        rollback_plan__repository_effect_rollback_plan_collected=True,
        rollback_plan__pr_creation_authorized_after_rollback_plan=True,
        authority_denials__authority_granted=True,
    )

    errors: list[str] = []
    validator._validate_repository_effect_rollback_plan_witness_semantics(payload, _source_uao_admission_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "rollback_plan_collected must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "rollback_plan.requires_command_preview_uao_admission_witness must be true" in serialized_errors
    assert "rollback_plan.requires_actual_diff_uao_admission_witness must be true" in serialized_errors
    assert "rollback_plan.command_preview_bound must be true" in serialized_errors
    assert "rollback_plan.operator_response_bound must be true" in serialized_errors
    assert "rollback_plan.uao_admission_witness_satisfied must be false" in serialized_errors
    assert "rollback_plan.repository_effect_rollback_plan_collected must be false" in serialized_errors
    assert "rollback_plan.pr_creation_authorized_after_rollback_plan must be false" in serialized_errors
    assert "authority_denials.authority_granted must be false" in serialized_errors


def test_github_pr_repository_effect_rollback_plan_witness_rejects_effect_authority() -> None:
    payload = validator.build_mutated_repository_effect_rollback_plan_witness(
        authority_denials__branch_write_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__repository_write_enabled=True,
        effect_boundary__branch_created=True,
        effect_boundary__pull_request_opened=True,
        effect_boundary__repository_written=True,
        effect_boundary__connector_called=True,
    )

    errors: list[str] = []
    validator._validate_repository_effect_rollback_plan_witness_semantics(payload, _source_uao_admission_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "effect_boundary.branch_created must be false" in serialized_errors
    assert "effect_boundary.pull_request_opened must be false" in serialized_errors
    assert "effect_boundary.repository_written must be false" in serialized_errors
    assert "effect_boundary.connector_called must be false" in serialized_errors


def test_github_pr_repository_effect_rollback_plan_witness_rejects_witness_drift() -> None:
    payload = validator.build_mutated_repository_effect_rollback_plan_witness(
        remaining_witnesses=[
            {
                "witness_kind": "ci_gate_before_ready_for_review",
                "status": "AwaitingEvidence",
                "evidence_ref": "evidence://ci-gate-before-ready-for-review",
                "blocks_pr_admission": False,
                "authority_granted": False,
            }
        ],
    )

    errors: list[str] = []
    validator._validate_repository_effect_rollback_plan_witness_semantics(payload, _source_uao_admission_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must preserve canonical witness order" in serialized_errors
    assert "remaining_witnesses.0.blocks_pr_admission must be true" in serialized_errors


def test_github_pr_repository_effect_rollback_plan_witness_rejects_actual_diff_uao_drift() -> None:
    payload = validator.build_mutated_repository_effect_rollback_plan_witness(
        rollback_plan__actual_diff_branch_write_binding_ref="examples/drifted-branch-write.json",
        rollback_plan__actual_diff_operator_response_witness_ref="examples/drifted-response.json",
        rollback_plan__actual_diff_approval_request_binding_ref="examples/drifted-approval-binding.json",
        rollback_plan__actual_non_empty_diff_receipt_ref="witness://drifted-actual-diff-receipt",
        rollback_plan__changed_file_refs=["evidence://drifted-file"],
        rollback_plan__diff_refs=["evidence://drifted-diff"],
        rollback_plan__redacted_diff_bundle_ref="digest://drifted-bundle",
        rollback_plan__redacted_output_ref="witness://drifted-output",
    )

    errors: list[str] = []
    validator._validate_repository_effect_rollback_plan_witness_semantics(payload, _source_uao_admission_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "rollback_plan.actual_diff_branch_write_binding_ref" in serialized_errors
    assert "rollback_plan.actual_diff_operator_response_witness_ref" in serialized_errors
    assert "rollback_plan.actual_diff_approval_request_binding_ref" in serialized_errors
    assert "rollback_plan.actual_non_empty_diff_receipt_ref" in serialized_errors
    assert "rollback_plan.changed_file_refs" in serialized_errors
    assert "rollback_plan.diff_refs" in serialized_errors
    assert "rollback_plan.redacted_diff_bundle_ref" in serialized_errors
    assert "rollback_plan.redacted_output_ref" in serialized_errors


def test_github_pr_repository_effect_rollback_plan_witness_rejects_command_preview_uao_drift() -> None:
    payload = validator.build_mutated_repository_effect_rollback_plan_witness(
        rollback_plan__command_preview_branch_write_binding_ref="examples/drifted-branch-write.json",
        rollback_plan__command_preview_operator_response_binding_ref="examples/drifted-command-response.json",
        rollback_plan__command_preview_operator_response_witness_ref="examples/drifted-response.json",
        rollback_plan__command_preview_operator_approval_request_binding_ref="examples/drifted-command-approval.json",
        rollback_plan__command_preview_ref="examples/drifted-command-preview.json",
        rollback_plan__redacted_command_preview="gh pr create --body leaked",
        rollback_plan__argument_vector_template=["gh", "pr", "create"],
        rollback_plan__placeholder_refs=["placeholder://drifted"],
    )

    errors: list[str] = []
    validator._validate_repository_effect_rollback_plan_witness_semantics(
        payload,
        _source_uao_admission_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "rollback_plan.command_preview_branch_write_binding_ref" in serialized_errors
    assert "rollback_plan.command_preview_operator_response_binding_ref" in serialized_errors
    assert "rollback_plan.command_preview_operator_response_witness_ref" in serialized_errors
    assert "rollback_plan.command_preview_operator_approval_request_binding_ref" in serialized_errors
    assert "rollback_plan.command_preview_ref" in serialized_errors
    assert "rollback_plan.redacted_command_preview" in serialized_errors
    assert "rollback_plan.argument_vector_template" in serialized_errors
    assert "rollback_plan.placeholder_refs" in serialized_errors


def test_github_pr_repository_effect_rollback_plan_witness_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_repository_effect_rollback_plan_witness(
        requested_evidence_ref="POST /api/github/repository-effect rollback plan-authority",
    )
    payload["rollback_plan"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_repository_effect_rollback_plan_witness_semantics(payload, _source_uao_admission_witness(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_repository_effect_rollback_plan_witness_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-uao-pr-admission-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_uao_admission_witness_ref"] == validator.EXPECTED_SOURCE_UAO_ADMISSION_WITNESS_REF
    assert file_payload["command_preview_uao_admission_witness_ref"] == validator.EXPECTED_SOURCE_UAO_ADMISSION_WITNESS_REF
    assert file_payload["actual_diff_uao_admission_witness_ref"] == validator.EXPECTED_SOURCE_UAO_ADMISSION_WITNESS_REF


def _source_uao_admission_witness() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_UAO_ADMISSION_WITNESS_EXAMPLES[0].read_text(encoding="utf-8"))
