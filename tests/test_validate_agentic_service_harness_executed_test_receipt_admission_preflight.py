"""Test Agentic Service Harness executed-test receipt admission preflight.

Purpose: verify executed-test receipt admission remains blocked until command
execution and result evidence are explicitly admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_executed_test_receipt_admission_preflight.
Invariants:
  - Source dry-run plan, approved workspace, and receipt append preflight pass.
  - Executed-test receipt admission is not granted.
  - Mutation routes, result claims, raw test output, and secrets fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_agentic_service_harness_executed_test_receipt_admission_preflight as validator,
)


def test_executed_test_receipt_admission_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_executed_test_receipt_admission_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_validators_ok is True


def test_executed_test_receipt_admission_preflight_rejects_execution_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__test_execution_admitted=True,
        scope__commands_executed=True,
        scope__test_results_claimed=True,
        test_execution_admission__command_execution_performed=True,
        test_execution_admission__executed_test_receipt_admitted=True,
        authority_denials__test_execution_enabled=True,
        authority_denials__command_execution_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.test_execution_admitted must be false" in serialized_errors
    assert "scope.commands_executed must be false" in serialized_errors
    assert "scope.test_results_claimed must be false" in serialized_errors
    assert "test_execution_admission.command_execution_performed must be false" in serialized_errors
    assert "test_execution_admission.executed_test_receipt_admitted must be false" in serialized_errors
    assert "authority_denials.test_execution_enabled must be false" in serialized_errors
    assert "authority_denials.command_execution_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors


def test_executed_test_receipt_admission_preflight_rejects_missing_refs() -> None:
    payload = validator.build_mutated_preflight(
        source_contract_refs=["MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md"],
        test_execution_admission__required_before_execution_refs=[
            "approval://operator/test-command-execution"
        ],
        test_execution_admission__blocked_reason_refs=[
            "blocked://test-execution/operator-approval-missing"
        ],
        test_execution_admission__next_required_evidence_refs=[
            "evidence://non-empty-diff-receipt-admission"
        ],
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "missing source_contract_refs" in serialized_errors
    assert "required_before_execution_refs missing required ref" in serialized_errors
    assert "blocked_reason_refs missing required ref" in serialized_errors
    assert "next_required_evidence_refs missing required ref" in serialized_errors


def test_executed_test_receipt_admission_preflight_rejects_receipt_contract_drift() -> None:
    payload = validator.build_mutated_preflight(
        executed_test_receipt_contract__allowed_metadata_refs=[
            "field://executed-test-receipt/id"
        ],
        executed_test_receipt_contract__forbidden_inline_fields=[
            "field://executed-test-receipt/raw-secret"
        ],
        executed_test_receipt_contract__test_result_claimed=True,
        executed_test_receipt_contract__stored_receipt_ref="executed-test-receipt://admitted",
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "allowed_metadata_refs missing required ref" in serialized_errors
    assert "forbidden_inline_fields missing required ref" in serialized_errors
    assert "executed_test_receipt_contract.test_result_claimed must be false" in serialized_errors
    assert "stored_receipt_ref must remain not-admitted" in serialized_errors


def test_executed_test_receipt_admission_preflight_rejects_mutation_route_and_secret() -> None:
    payload = validator.build_mutated_preflight(
        next_action="POST /api/harness/tests must never be admitted",
    )
    payload["test_execution_admission"]["api_key"] = "sk-test-not-allowed"

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_executed_test_receipt_admission_preflight_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "executed-test-receipt-admission-preflight-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_validators_ok"] is True
