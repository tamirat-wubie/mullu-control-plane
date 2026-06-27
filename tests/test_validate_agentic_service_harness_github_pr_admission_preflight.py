"""Test GitHub PR admission preflight validation.

Purpose: verify the harness GitHub PR admission path remains preflight-only
until approval and branch-write authority evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_github_pr_admission_preflight.
Invariants:
  - PR admission never creates branches or pull requests.
  - Operator approval and branch-write authority remain absent.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_github_pr_admission_preflight as validator


def test_github_pr_admission_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_github_pr_admission_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_receipt_ref == validator.EXPECTED_SOURCE_RECEIPT_REF
    assert (
        validation.non_empty_diff_file_summary_receipt_ref
        == validator.EXPECTED_NON_EMPTY_DIFF_FILE_SUMMARY_RECEIPT_REF
    )


def test_github_pr_admission_preflight_rejects_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__operator_approval_present=True,
        scope__branch_write_authority_enabled=True,
        scope__pull_request_creation_enabled=True,
        simulated_pr_admission__operator_approval_observed=True,
        simulated_pr_admission__branch_created=True,
        simulated_pr_admission__pull_request_opened=True,
        simulated_pr_admission__repository_written=True,
        authority_denials__branch_write_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__repository_write_enabled=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.operator_approval_present must be false" in serialized_errors
    assert "scope.branch_write_authority_enabled must be false" in serialized_errors
    assert "scope.pull_request_creation_enabled must be false" in serialized_errors
    assert "simulated_pr_admission.operator_approval_observed must be false" in serialized_errors
    assert "simulated_pr_admission.branch_created must be false" in serialized_errors
    assert "simulated_pr_admission.pull_request_opened must be false" in serialized_errors
    assert "simulated_pr_admission.repository_written must be false" in serialized_errors
    assert "authority_denials.branch_write_enabled must be false" in serialized_errors
    assert "authority_denials.pull_request_creation_enabled must be false" in serialized_errors
    assert "authority_denials.repository_write_enabled must be false" in serialized_errors


def test_github_pr_admission_preflight_rejects_gate_drift() -> None:
    payload = validator.build_mutated_preflight(
        approval_admission_gate__decision="PR_ADMITTED",
        approval_admission_gate__pr_admitted=True,
        approval_admission_gate__terminal_closure_allowed=True,
        simulated_pr_admission__success_claim_allowed=True,
        simulated_pr_admission__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "approval_admission_gate.decision" in serialized_errors
    assert "approval_admission_gate.pr_admitted must be false" in serialized_errors
    assert "approval_admission_gate.terminal_closure_allowed must be false" in serialized_errors
    assert "simulated_pr_admission.success_claim_allowed must be false" in serialized_errors
    assert "simulated_pr_admission.terminal_closure must be false" in serialized_errors


def test_github_pr_admission_preflight_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_preflight(
        preflight_contract__allowed_action_classes=["dry_run"],
        preflight_contract__forbidden_action_classes=["open_pr"],
        preflight_contract__required_source_refs=[
            "examples/agentic_service_harness_github_task_receipt_emitter_dry_run.foundation.json"
        ],
        preflight_contract__required_gate_refs=["gate://harness/no-pr-creation"],
        preflight_contract__admission_obligations_checked=["obligation://record-pr-admission-preflight"],
        preflight_contract__validation_refs=[
            "scripts/validate_agentic_service_harness_github_pr_admission_preflight.py"
        ],
        approval_admission_gate__required_before_pr_refs=["evidence://uao-pr-admission"],
        approval_admission_gate__blocked_reason_refs=["blocked://pr-creation/not-admitted"],
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "preflight_contract.allowed_action_classes missing required ref" in serialized_errors
    assert "preflight_contract.forbidden_action_classes missing required ref" in serialized_errors
    assert "preflight_contract.required_source_refs missing required ref" in serialized_errors
    assert "preflight_contract.required_gate_refs missing required ref" in serialized_errors
    assert "preflight_contract.admission_obligations_checked missing required ref" in serialized_errors
    assert "preflight_contract.validation_refs missing required ref" in serialized_errors
    assert "approval_admission_gate.required_before_pr_refs missing required ref" in serialized_errors
    assert "approval_admission_gate.blocked_reason_refs missing required ref" in serialized_errors


def test_github_pr_admission_preflight_rejects_missing_non_empty_diff_file_summary_binding() -> None:
    payload = validator.build_mutated_preflight(
        source_non_empty_diff_file_summary_receipt_ref="examples/missing-non-empty-diff-file-summary.json",
    )
    payload["receipt_refs"]["non_empty_diff_file_summary_receipt_example"] = "examples/missing.json"
    payload["receipt_refs"]["non_empty_diff_file_summary_receipt_schema"] = "schemas/missing.json"

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_non_empty_diff_file_summary_receipt_ref expected" in serialized_errors
    assert "receipt_refs.non_empty_diff_file_summary_receipt_example expected" in serialized_errors
    assert "receipt_refs.non_empty_diff_file_summary_receipt_schema expected" in serialized_errors


def test_github_pr_admission_preflight_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_preflight(next_action="POST /api/github/prs should never be admitted")
    payload["simulated_pr_admission"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, _source_receipt(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_github_pr_admission_preflight_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "github-pr-admission-preflight-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_receipt_ref"] == validator.EXPECTED_SOURCE_RECEIPT_REF
    assert (
        file_payload["non_empty_diff_file_summary_receipt_ref"]
        == validator.EXPECTED_NON_EMPTY_DIFF_FILE_SUMMARY_RECEIPT_REF
    )


def _source_receipt() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_RECEIPT_EXAMPLES[0].read_text(encoding="utf-8"))
