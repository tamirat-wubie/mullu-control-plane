"""Test GitHub PR terminal closure certificate candidate validation.

Purpose: verify live effect reconciliation evidence can be bound into a
terminal closure candidate without minting terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_candidate.
Invariants:
  - Live evidence binding remains explicit.
  - Terminal closure stays AwaitingEvidence.
  - Mutation authority and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_terminal_closure_certificate_candidate as validator


def test_github_pr_terminal_closure_certificate_candidate_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_terminal_closure_certificate_candidate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_live_evidence_ref == validator.EXPECTED_SOURCE_LIVE_EVIDENCE_REF
    assert (
        validation.source_terminal_closure_certificate_witness_ref
        == validator.EXPECTED_SOURCE_TERMINAL_CLOSURE_CERTIFICATE_WITNESS_REF
    )


def test_github_pr_terminal_closure_certificate_candidate_rejects_terminal_closure_overclaim() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_candidate(
        terminal_closure=True,
        terminal_closure_certificate_minted=True,
        terminal_closure_authorized=True,
        certificate_candidate__terminal_closure_certificate_minted=True,
        certificate_candidate__terminal_closure_authorized=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_candidate_semantics(
        payload,
        _source_live_evidence(),
        _source_terminal_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "terminal_closure expected False" in serialized_errors
    assert "terminal_closure_certificate_minted must be false" in serialized_errors
    assert "terminal_closure_authorized must be false" in serialized_errors
    assert "certificate_candidate.terminal_closure_certificate_minted must be false" in serialized_errors
    assert "certificate_candidate.terminal_closure_authorized must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_github_pr_terminal_closure_certificate_candidate_rejects_live_evidence_binding_drift() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_candidate(
        source_live_evidence_ref="examples/other-live-evidence.json",
        certificate_candidate__source_live_evidence_binding_id="other_binding",
        certificate_candidate__source_effect_reconciliation_evidence_ref="evidence://other",
        effect_reconciliation_collected=False,
        certificate_candidate__effect_reconciliation_collected=False,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_candidate_semantics(
        payload,
        _source_live_evidence(),
        _source_terminal_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "source_live_evidence_ref expected" in serialized_errors
    assert "certificate_candidate.source_live_evidence_binding_id expected" in serialized_errors
    assert "certificate_candidate.source_effect_reconciliation_evidence_ref expected" in serialized_errors
    assert "effect_reconciliation_collected must be true" in serialized_errors
    assert "certificate_candidate.effect_reconciliation_collected must be true" in serialized_errors


def test_github_pr_terminal_closure_certificate_candidate_rejects_actual_diff_terminal_witness_drift() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_candidate(
        source_terminal_closure_certificate_witness_ref="examples/other-terminal-witness.json",
        certificate_candidate__source_terminal_closure_certificate_witness_ref="examples/other-terminal-witness.json",
        certificate_candidate__actual_diff_terminal_closure_certificate_witness_ref="examples/other-terminal-witness.json",
        certificate_candidate__actual_diff_effect_reconciliation_witness_ref="examples/other-effect-witness.json",
        certificate_candidate__actual_diff_ci_gate_before_ready_for_review_witness_ref="examples/other-ci-witness.json",
        certificate_candidate__actual_diff_repository_effect_rollback_plan_witness_ref="examples/other-rollback.json",
        certificate_candidate__actual_diff_uao_admission_witness_ref="examples/other-uao.json",
        certificate_candidate__actual_diff_branch_write_binding_ref="examples/other-branch-write.json",
        certificate_candidate__actual_diff_operator_response_witness_ref="examples/other-response.json",
        certificate_candidate__actual_diff_approval_request_binding_ref="examples/other-approval.json",
        certificate_candidate__actual_non_empty_diff_receipt_ref="witness://other-non-empty-diff",
        certificate_candidate__changed_file_refs=["evidence://other-file"],
        certificate_candidate__diff_refs=["evidence://other-diff"],
        certificate_candidate__redacted_diff_bundle_ref="digest://other-bundle",
        certificate_candidate__redacted_output_ref="witness://other-output",
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_candidate_semantics(
        payload,
        _source_live_evidence(),
        _source_terminal_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "source_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "certificate_candidate.source_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "certificate_candidate.actual_diff_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "certificate_candidate.actual_diff_effect_reconciliation_witness_ref expected" in serialized_errors
    assert "certificate_candidate.actual_diff_ci_gate_before_ready_for_review_witness_ref expected" in serialized_errors
    assert "certificate_candidate.actual_diff_repository_effect_rollback_plan_witness_ref expected" in serialized_errors
    assert "certificate_candidate.actual_diff_uao_admission_witness_ref expected" in serialized_errors
    assert "certificate_candidate.actual_diff_branch_write_binding_ref expected" in serialized_errors
    assert "certificate_candidate.actual_diff_operator_response_witness_ref expected" in serialized_errors
    assert "certificate_candidate.actual_diff_approval_request_binding_ref expected" in serialized_errors
    assert "certificate_candidate.actual_non_empty_diff_receipt_ref expected" in serialized_errors
    assert "certificate_candidate.changed_file_refs expected" in serialized_errors
    assert "certificate_candidate.diff_refs expected" in serialized_errors
    assert "certificate_candidate.redacted_diff_bundle_ref expected" in serialized_errors
    assert "certificate_candidate.redacted_output_ref expected" in serialized_errors


def test_github_pr_terminal_closure_certificate_candidate_rejects_command_preview_certificate_drift() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_candidate(
        certificate_candidate__requires_command_preview_terminal_closure_certificate_witness=False,
        certificate_candidate__command_preview_terminal_closure_certificate_witness_ref="examples/other-terminal.json",
        certificate_candidate__command_preview_effect_reconciliation_witness_ref="examples/other-effect.json",
        certificate_candidate__command_preview_ci_gate_before_ready_for_review_witness_ref="examples/other-ci.json",
        certificate_candidate__command_preview_repository_effect_rollback_plan_witness_ref="examples/other-rollback.json",
        certificate_candidate__command_preview_uao_admission_witness_ref="examples/other-uao.json",
        certificate_candidate__command_preview_branch_write_binding_ref="examples/other-branch.json",
        certificate_candidate__command_preview_operator_response_binding_ref="examples/other-command-response.json",
        certificate_candidate__command_preview_operator_response_witness_ref="examples/other-response.json",
        certificate_candidate__command_preview_operator_approval_request_binding_ref="examples/other-command-approval.json",
        certificate_candidate__command_preview_ref="examples/other-command-preview.json",
        certificate_candidate__redacted_command_preview="gh pr create --body leaked",
        certificate_candidate__command_preview_bound=False,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_candidate_semantics(
        payload,
        _source_live_evidence(),
        _source_terminal_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "certificate_candidate.requires_command_preview_terminal_closure_certificate_witness must be true" in serialized_errors
    assert "certificate_candidate.command_preview_terminal_closure_certificate_witness_ref expected" in serialized_errors
    assert "certificate_candidate.command_preview_effect_reconciliation_witness_ref expected" in serialized_errors
    assert "certificate_candidate.command_preview_ci_gate_before_ready_for_review_witness_ref expected" in serialized_errors
    assert "certificate_candidate.command_preview_repository_effect_rollback_plan_witness_ref expected" in serialized_errors
    assert "certificate_candidate.command_preview_uao_admission_witness_ref expected" in serialized_errors
    assert "certificate_candidate.command_preview_branch_write_binding_ref expected" in serialized_errors
    assert "certificate_candidate.command_preview_operator_response_binding_ref expected" in serialized_errors
    assert "certificate_candidate.command_preview_operator_response_witness_ref expected" in serialized_errors
    assert "certificate_candidate.command_preview_operator_approval_request_binding_ref expected" in serialized_errors
    assert "certificate_candidate.command_preview_ref expected" in serialized_errors
    assert "certificate_candidate.redacted_command_preview expected" in serialized_errors
    assert "certificate_candidate.command_preview_bound must be true" in serialized_errors


def test_github_pr_terminal_closure_certificate_candidate_rejects_command_preview_certificate_evidence_capsule_drift() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_candidate(
        command_preview_terminal_closure_certificate_evidence__source_binding_id=(
            "agentic_service_harness_github_pr_drift"
        ),
        command_preview_terminal_closure_certificate_evidence__source_effect_reconciliation_binding_id=(
            "agentic_service_harness_github_pr_drift"
        ),
        command_preview_terminal_closure_certificate_evidence__source_ci_gate_binding_id=(
            "agentic_service_harness_github_pr_drift"
        ),
        command_preview_terminal_closure_certificate_evidence__source_repository_effect_rollback_plan_witness_id=(
            "agentic_service_harness_github_pr_drift"
        ),
        command_preview_terminal_closure_certificate_evidence__source_uao_admission_witness_id=(
            "agentic_service_harness_github_pr_drift"
        ),
        command_preview_terminal_closure_certificate_evidence__source_branch_write_binding_id=(
            "agentic_service_harness_github_pr_drift"
        ),
        command_preview_terminal_closure_certificate_evidence__source_terminal_closure_certificate_collected=True,
        command_preview_terminal_closure_certificate_evidence__source_terminal_closure_authorized=True,
        command_preview_terminal_closure_certificate_evidence__source_effect_reconciliation_collected=True,
        command_preview_terminal_closure_certificate_evidence__source_authority_granted=True,
        command_preview_terminal_closure_certificate_evidence__candidate_consumes_command_preview_terminal_closure_certificate_evidence=False,
        command_preview_terminal_closure_certificate_evidence__candidate_consumes_command_preview_effect_reconciliation_evidence=False,
        command_preview_terminal_closure_certificate_evidence__operator_approval_required=False,
        command_preview_terminal_closure_certificate_evidence__certificate_minting_remains_blocked=False,
        command_preview_terminal_closure_certificate_evidence__terminal_closure_remains_blocked=False,
        command_preview_terminal_closure_certificate_evidence__repository_write_remains_blocked=False,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_candidate_semantics(
        payload,
        _source_live_evidence(),
        _source_terminal_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "command_preview_terminal_closure_certificate_evidence.source_binding_id" in serialized_errors
    assert (
        "command_preview_terminal_closure_certificate_evidence.source_effect_reconciliation_binding_id"
        in serialized_errors
    )
    assert "command_preview_terminal_closure_certificate_evidence.source_ci_gate_binding_id" in serialized_errors
    assert (
        "command_preview_terminal_closure_certificate_evidence.source_repository_effect_rollback_plan_witness_id"
        in serialized_errors
    )
    assert "command_preview_terminal_closure_certificate_evidence.source_uao_admission_witness_id" in serialized_errors
    assert "command_preview_terminal_closure_certificate_evidence.source_branch_write_binding_id" in serialized_errors
    assert (
        "command_preview_terminal_closure_certificate_evidence.source_terminal_closure_certificate_collected"
        " must be false"
    ) in serialized_errors
    assert (
        "command_preview_terminal_closure_certificate_evidence.source_terminal_closure_authorized must be false"
        in serialized_errors
    )
    assert (
        "command_preview_terminal_closure_certificate_evidence.source_effect_reconciliation_collected must be false"
        in serialized_errors
    )
    assert "command_preview_terminal_closure_certificate_evidence.source_authority_granted must be false" in serialized_errors
    assert (
        "command_preview_terminal_closure_certificate_evidence."
        "candidate_consumes_command_preview_terminal_closure_certificate_evidence must be true"
    ) in serialized_errors
    assert (
        "command_preview_terminal_closure_certificate_evidence."
        "candidate_consumes_command_preview_effect_reconciliation_evidence must be true"
    ) in serialized_errors
    assert "command_preview_terminal_closure_certificate_evidence.operator_approval_required must be true" in serialized_errors
    assert (
        "command_preview_terminal_closure_certificate_evidence.certificate_minting_remains_blocked must be true"
        in serialized_errors
    )
    assert "command_preview_terminal_closure_certificate_evidence.terminal_closure_remains_blocked must be true" in serialized_errors
    assert "command_preview_terminal_closure_certificate_evidence.repository_write_remains_blocked must be true" in serialized_errors


def test_github_pr_terminal_closure_certificate_candidate_rejects_mutation_authority() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_candidate(
        authority_granted=True,
        authority_denials__repository_write_enabled=True,
        authority_denials__pull_request_merge_enabled=True,
        effect_boundary__repository_written_by_candidate=True,
        effect_boundary__connector_called_by_candidate=True,
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_candidate_semantics(
        payload,
        _source_live_evidence(),
        _source_terminal_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "authority_granted must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_merge_enabled must be false" in serialized_errors
    assert "effect_boundary.repository_written_by_candidate must be false" in serialized_errors
    assert "effect_boundary.connector_called_by_candidate must be false" in serialized_errors


def test_github_pr_terminal_closure_certificate_candidate_rejects_remaining_witness_drift() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_candidate(
        remaining_witnesses=[
            {
                "witness_kind": "effect_reconciliation_live_evidence",
                "status": "SolvedVerified",
                "evidence_ref": "evidence://effect-reconciliation-before-terminal-closure",
                "authority_granted": False,
            }
        ],
    )

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_candidate_semantics(
        payload,
        _source_live_evidence(),
        _source_terminal_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "remaining_witnesses must contain only the terminal closure certificate witness" in serialized_errors
    assert len(errors) >= 1
    assert payload["remaining_witnesses"][0]["witness_kind"] == "effect_reconciliation_live_evidence"


def test_github_pr_terminal_closure_certificate_candidate_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_terminal_closure_certificate_candidate(
        requested_certificate_ref="POST /api/github/terminal-closure certificate",
    )
    payload["certificate_candidate"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_terminal_closure_certificate_candidate_semantics(
        payload,
        _source_live_evidence(),
        _source_terminal_witness(),
        errors,
        "mutated",
    )
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_terminal_closure_certificate_candidate_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-terminal-closure-certificate-candidate-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_live_evidence_ref"] == validator.EXPECTED_SOURCE_LIVE_EVIDENCE_REF
    assert (
        file_payload["source_terminal_closure_certificate_witness_ref"]
        == validator.EXPECTED_SOURCE_TERMINAL_CLOSURE_CERTIFICATE_WITNESS_REF
    )


def _source_live_evidence() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_LIVE_EVIDENCE_EXAMPLES[0].read_text(encoding="utf-8"))


def _source_terminal_witness() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_TERMINAL_WITNESS_EXAMPLES[0].read_text(encoding="utf-8"))
