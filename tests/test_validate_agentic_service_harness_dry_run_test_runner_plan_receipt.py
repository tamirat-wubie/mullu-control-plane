"""Test dry-run test runner plan receipt validation.

Purpose: verify selected harness test commands remain planned evidence only,
without command execution, raw output capture, receipt append, or terminal
closure authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_dry_run_test_runner_plan_receipt.
Invariants:
  - Source preflight validators pass before this receipt is accepted.
  - Planned commands remain allowlisted and non-executing.
  - Mutation routes, raw output capture, and secret-like payloads fail closed.
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


def test_dry_run_test_runner_plan_receipt_rejects_authority_drift() -> None:
    payload = validator.build_mutated_receipt(
        scope__command_execution_enabled=True,
        scope__test_execution_enabled=True,
        authority_denials__test_execution_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__terminal_closure=True,
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.command_execution_enabled must be false" in serialized_errors
    assert "scope.test_execution_enabled must be false" in serialized_errors
    assert "authority_denials.test_execution_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_dry_run_test_runner_plan_receipt_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_receipt(
        source_contract_refs=["MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md"],
        test_runner_plan__required_before_execution_refs=[
            "approval://operator/test-runner-execution"
        ],
        test_runner_plan__blocked_reason_refs=["blocked://operator-approval/not-collected"],
        test_runner_plan__next_required_evidence_refs=[
            "evidence://task-record-write-uao-admission"
        ],
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "missing source_contract_refs" in serialized_errors
    assert "test_runner_plan.required_before_execution_refs missing required ref" in serialized_errors
    assert "test_runner_plan.blocked_reason_refs missing required ref" in serialized_errors
    assert "test_runner_plan.next_required_evidence_refs missing required ref" in serialized_errors


def test_dry_run_test_runner_plan_receipt_rejects_non_allowlisted_command() -> None:
    payload = validator.build_mutated_receipt()
    payload["test_runner_plan"]["selected_commands"][0]["command"] = "cmd /c pytest"
    payload["test_runner_plan"]["selected_commands"][0]["execution_admitted"] = True

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "selected_commands[0].command is not allowlisted" in serialized_errors
    assert "selected_commands[0].execution_admitted must be false" in serialized_errors


def test_dry_run_test_runner_plan_receipt_rejects_raw_output_capture() -> None:
    payload = validator.build_mutated_receipt(
        redaction_policy__raw_stdout_stored=True,
        redaction_policy__raw_stderr_stored=True,
        redaction_policy__environment_values_stored=True,
        redaction_policy__allowed_receipt_fields=["command_id", "command"],
    )
    payload["test_runner_plan"]["selected_commands"][1]["raw_output_capture_allowed"] = True

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "redaction_policy.raw_stdout_stored must be false" in serialized_errors
    assert "redaction_policy.raw_stderr_stored must be false" in serialized_errors
    assert "redaction_policy.environment_values_stored must be false" in serialized_errors
    assert "redaction_policy.allowed_receipt_fields must be exact" in serialized_errors
    assert "selected_commands[1].raw_output_capture_allowed must be false" in serialized_errors


def test_dry_run_test_runner_plan_receipt_rejects_mutation_route_and_secret_payload() -> None:
    payload = validator.build_mutated_receipt(
        next_action="POST /api/harness/test-runner/run should never be admitted",
    )
    payload["test_runner_plan"]["api_key"] = "sk-test-not-allowed"

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_dry_run_test_runner_plan_receipt_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "dry-run-test-runner-plan-receipt-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_validators_ok"] is True
