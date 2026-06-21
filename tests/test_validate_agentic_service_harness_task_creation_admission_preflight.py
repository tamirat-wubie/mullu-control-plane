"""Test Agentic Service Harness task creation admission preflight.

Purpose: verify task creation remains admission-blocked until route, approval,
rollback, UAO, receipt append, and terminal closure evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_task_creation_admission_preflight.
Invariants:
  - Task creation admission is evidence-bound and not a runtime route.
  - Runtime writes, adapter execution, repository effects, receipt append,
    secrets, and terminal closure fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_task_creation_admission_preflight as validator


def test_task_creation_admission_preflight_passes() -> None:
    validation = validator.validate_agentic_service_harness_task_creation_admission_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_contracts_ok is True
    assert validation.schema_path == "schemas/agentic_service_harness_task_creation_admission_preflight.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_task_creation_admission_preflight.foundation.json",
    )


def test_task_creation_admission_preflight_rejects_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__task_creation_route_admitted=True,
        scope__task_record_write_enabled=True,
        scope__runtime_state_write_enabled=True,
        admission_decision__task_creation_admitted=True,
        admission_decision__route_creation_admitted=True,
        admission_decision__runtime_state_write_admitted=True,
        authority_denials__task_creation_route_enabled=True,
        authority_denials__task_record_write_enabled=True,
        authority_denials__runtime_state_write_enabled=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.task_creation_route_admitted must be false" in serialized_errors
    assert "scope.task_record_write_enabled must be false" in serialized_errors
    assert "scope.runtime_state_write_enabled must be false" in serialized_errors
    assert "admission_decision.task_creation_admitted must be false" in serialized_errors
    assert "admission_decision.route_creation_admitted must be false" in serialized_errors
    assert "authority_denials.task_creation_route_enabled must be false" in serialized_errors


def test_task_creation_admission_preflight_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_preflight(
        source_contract_refs=["examples/agentic_service_harness_github_repo_task_intake.foundation.json"],
        admission_request__required_policy_refs=["policy://harness/no-secret-serialization"],
        admission_decision__blocked_reason_refs=["blocked://task-creation-route/not-admitted"],
        admission_decision__missing_evidence_refs=["evidence://task-creation-route-contract"],
        required_before_task_creation_refs=["evidence://task-creation-route-contract"],
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "source_contract_refs missing required ref" in serialized_errors
    assert "admission_request.required_policy_refs missing required ref" in serialized_errors
    assert "admission_decision.blocked_reason_refs missing required ref" in serialized_errors
    assert "admission_decision.missing_evidence_refs missing required ref" in serialized_errors
    assert "required_before_task_creation_refs missing required ref" in serialized_errors


def test_task_creation_admission_preflight_rejects_terminal_and_effect_authority() -> None:
    payload = validator.build_mutated_preflight(
        scope__terminal_closure_granted=True,
        admission_decision__terminal_closure_allowed=True,
        admission_decision__adapter_execution_admitted=True,
        admission_decision__branch_creation_admitted=True,
        admission_decision__pull_request_creation_admitted=True,
        admission_decision__receipt_store_append_admitted=True,
        authority_denials__terminal_closure=True,
        authority_denials__adapter_execution_enabled=True,
        authority_denials__branch_creation_enabled=True,
        authority_denials__pull_request_creation_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
    )

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.terminal_closure_granted must be false" in serialized_errors
    assert "admission_decision.terminal_closure_allowed must be false" in serialized_errors
    assert "admission_decision.adapter_execution_admitted must be false" in serialized_errors
    assert "admission_decision.branch_creation_admitted must be false" in serialized_errors
    assert "admission_decision.receipt_store_append_admitted must be false" in serialized_errors
    assert "authority_denials.terminal_closure must be false" in serialized_errors


def test_task_creation_admission_preflight_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_preflight(next_action="POST /api/harness/tasks must remain blocked")
    payload["receipt_refs"]["access_token_task_creation"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_preflight_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_task_creation_admission_preflight_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "task-creation-admission-preflight-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert file_payload["source_contracts_ok"] is True
    assert stdout_payload["errors"] == []
