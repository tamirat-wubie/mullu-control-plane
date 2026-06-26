"""Tests for dry-run test execution observation receipt validation.

Purpose: prove the dry-run test execution observation receipt remains bounded,
redacted, non-appendable, and non-terminal.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_dry_run_test_execution_observation_receipt.
Invariants:
  - The default fixture validates against schema and source contracts.
  - Command observation must match the selected dry-run plan commands.
  - Downstream execution authority, raw output, secrets, and terminal closure
    fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_dry_run_test_execution_observation_receipt as validator


def test_dry_run_test_execution_observation_receipt_passes() -> None:
    validation = validator.validate_agentic_service_harness_dry_run_test_execution_observation_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_plan_ok is True
    assert validation.source_workspace_observation_ok is True
    assert validation.source_executed_test_admission_ok is True


def test_dry_run_test_execution_observation_rejects_command_drift(tmp_path: Path) -> None:
    payload = validator.build_mutated_dry_run_test_execution_observation(
        execution_observation__observed_commands__0__command_id="wrong-command-id",
        execution_observation__observed_commands__1__exit_code=1,
    )
    example_path = tmp_path / "command-drift.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validator.validate_agentic_service_harness_dry_run_test_execution_observation_receipt(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert validation.example_count == 1
    assert "observed command ids must match selected command ids" in serialized_errors


def test_dry_run_test_execution_observation_rejects_downstream_authority(
    tmp_path: Path,
) -> None:
    payload = validator.build_mutated_dry_run_test_execution_observation(
        effect_boundary__receipt_store_appended=True,
        effect_boundary__filesystem_write_authority_granted=True,
        authority_denials__terminal_closure=True,
        execution_observation__raw_stdout_serialized=True,
    )
    example_path = tmp_path / "authority-drift.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validator.validate_agentic_service_harness_dry_run_test_execution_observation_receipt(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "receipt_store_appended" in serialized_errors
    assert "filesystem_write_authority_granted" in serialized_errors
    assert "terminal_closure" in serialized_errors
    assert "raw_stdout_serialized" in serialized_errors


def test_dry_run_test_execution_observation_rejects_missing_refs(tmp_path: Path) -> None:
    payload = validator.build_mutated_dry_run_test_execution_observation(
        required_next_evidence__before_filesystem_write=[
            "evidence://filesystem-write-rollback-plan"
        ],
        receipt_refs__dry_run_test_runner_plan_schema="schemas/wrong.schema.json",
    )
    example_path = tmp_path / "missing-refs.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validator.validate_agentic_service_harness_dry_run_test_execution_observation_receipt(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing evidence://workspace-write-authority" in serialized_errors
    assert "receipt_refs.dry_run_test_runner_plan_schema" in serialized_errors
    assert "schemas/agentic_service_harness_dry_run_test_runner_plan_receipt.schema.json" in serialized_errors


def test_dry_run_test_execution_observation_rejects_mutation_route_and_secret(
    tmp_path: Path,
) -> None:
    payload = validator.build_mutated_dry_run_test_execution_observation(
        next_action="POST /api/v1/harness/tests/execute with access_token=secret"
    )
    example_path = tmp_path / "forbidden-payload.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validator.validate_agentic_service_harness_dry_run_test_execution_observation_receipt(
        example_paths=(example_path,)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string is forbidden" in serialized_errors
    assert "credential-like value is forbidden" in serialized_errors


def test_dry_run_test_execution_observation_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "validation.json"

    exit_code = validator.main(["--strict", "--output", str(output_path)])
    captured = capsys.readouterr()
    report = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert report["ok"] is True
    assert report["source_plan_ok"] is True
    assert "DRY-RUN TEST EXECUTION OBSERVATION RECEIPT VALID" in captured.out
