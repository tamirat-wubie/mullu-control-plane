"""Test dry-run test runner plan receipt validation.

Purpose: verify selected test commands remain plan-only and cannot drift into
command execution, test result claims, filesystem writes, adapter execution, or
terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_dry_run_test_runner_plan_receipt.
Invariants:
  - The receipt binds to approved branch workspace preflight evidence.
  - Selected commands are exact allowlisted validator and pytest strings.
  - Mutation routes, secret-like payloads, command execution, and closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_dry_run_test_runner_plan_receipt as validator


def test_dry_run_test_runner_plan_receipt_passes() -> None:
    validation = validator.validate_agentic_service_harness_dry_run_test_runner_plan_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_validators_ok is True
    assert validation.selected_command_count == 4


def test_dry_run_test_runner_plan_rejects_execution_authority_drift() -> None:
    payload = validator.build_mutated_receipt(
        scope__test_execution_admitted=True,
        scope__commands_executed=True,
        scope__test_results_claimed=True,
        scope__coverage_claimed=True,
        test_plan__command_execution_enabled=True,
        test_plan__subprocess_execution_enabled=True,
        test_plan__test_result_claim_enabled=True,
        authority_denials__test_execution_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.test_execution_admitted must be false" in serialized_errors
    assert "scope.commands_executed must be false" in serialized_errors
    assert "scope.test_results_claimed must be false" in serialized_errors
    assert "scope.coverage_claimed must be false" in serialized_errors
    assert "test_plan.command_execution_enabled must be false" in serialized_errors
    assert "test_plan.subprocess_execution_enabled must be false" in serialized_errors
    assert "test_plan.test_result_claim_enabled must be false" in serialized_errors
    assert "authority_denials.test_execution_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors


def test_dry_run_test_runner_plan_rejects_command_drift() -> None:
    payload = validator.build_mutated_receipt()
    payload["test_plan"]["selected_commands"][0]["command"] = "pytest -q"
    payload["test_plan"]["selected_commands"][3]["path_scope"] = "repository_local"
    payload["test_plan"]["selected_commands"][3]["expected_result"] = "tests_passed"

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "test_plan.selected_commands must match the allowlisted command order" in serialized_errors
    assert "disallowed selected command: pytest -q" in serialized_errors
    assert "pytest command must use tests_only path_scope" in serialized_errors
    assert "selected command expected_result must deny result claims" in serialized_errors


def test_dry_run_test_runner_plan_rejects_missing_refs() -> None:
    payload = validator.build_mutated_receipt(
        source_contract_refs=["MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md"],
        test_plan__selection_reason_refs=["evidence://approved-branch-workspace-preflight-valid"],
        required_evidence__must_have_before_command_execution=[
            "approval://operator/test-command-execution"
        ],
        required_evidence__must_have_before_test_result_claim=[
            "evidence://commands-executed-in-approved-workspace"
        ],
        required_evidence__must_have_before_receipt_append=[
            "evidence://receipt-store-write-path"
        ],
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "missing source_contract_refs" in serialized_errors
    assert "test_plan.selection_reason_refs missing required ref" in serialized_errors
    assert "required_evidence.must_have_before_command_execution missing required ref" in serialized_errors
    assert "required_evidence.must_have_before_test_result_claim missing required ref" in serialized_errors
    assert "required_evidence.must_have_before_receipt_append missing required ref" in serialized_errors


def test_dry_run_test_runner_plan_rejects_mutation_route_and_secret_payload() -> None:
    payload = validator.build_mutated_receipt(
        next_action="POST /api/harness/test-runner should never be admitted",
    )
    payload["test_plan"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_dry_run_test_runner_plan_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "dry-run-test-runner-plan-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_validators_ok"] is True
    assert file_payload["selected_command_count"] == 4
