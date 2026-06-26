"""Test task record write UAO admission preflight validation.

Purpose: verify AgentTask record writes remain blocked until operator approval,
UAO, rollback, idempotency, and receipt-store evidence are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_task_record_write_uao_admission_preflight.
Invariants:
  - Source dry-run test runner plan receipt passes before this preflight.
  - Task records are not persisted.
  - Mutation routes, write claims, and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_agentic_service_harness_task_record_write_uao_admission_preflight as validator,
)


def test_task_record_write_uao_admission_preflight_passes() -> None:
    validation = (
        validator.validate_agentic_service_harness_task_record_write_uao_admission_preflight()
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_validators_ok is True


def test_task_record_write_uao_admission_preflight_rejects_write_authority_drift() -> None:
    payload = validator.build_mutated_preflight(
        scope__task_record_write_admitted=True,
        scope__task_record_persisted=True,
        uao_admission__task_record_write_admitted=True,
        authority_denials__task_record_write_enabled=True,
        authority_denials__runtime_state_write_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.task_record_write_admitted must be false" in serialized_errors
    assert "scope.task_record_persisted must be false" in serialized_errors
    assert "uao_admission.task_record_write_admitted must be false" in serialized_errors
    assert "authority_denials.task_record_write_enabled must be false" in serialized_errors
    assert "authority_denials.runtime_state_write_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors


def test_task_record_write_uao_admission_preflight_rejects_missing_refs() -> None:
    payload = validator.build_mutated_preflight(
        source_contract_refs=["MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md"],
        uao_admission__required_before_write_refs=["approval://operator/task-record-write"],
        uao_admission__blocked_reason_refs=["blocked://operator-approval/not-collected"],
        uao_admission__next_required_evidence_refs=[
            "evidence://receipt-store-append-admission"
        ],
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "missing source_contract_refs" in serialized_errors
    assert "uao_admission.required_before_write_refs missing required ref" in serialized_errors
    assert "uao_admission.blocked_reason_refs missing required ref" in serialized_errors
    assert "uao_admission.next_required_evidence_refs missing required ref" in serialized_errors


def test_task_record_write_uao_admission_preflight_rejects_record_contract_drift() -> None:
    payload = validator.build_mutated_preflight(
        task_record_contract__allowed_field_refs=["field://agent-task/id"],
        task_record_contract__forbidden_inline_fields=["field://agent-task/raw-secret"],
        task_record_contract__write_result_claimed=True,
        task_record_contract__stored_record_ref="task-record://written",
    )

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "task_record_contract.allowed_field_refs incomplete" in serialized_errors
    assert "task_record_contract.forbidden_inline_fields incomplete" in serialized_errors
    assert "task_record_contract.write_result_claimed must be false" in serialized_errors
    assert "stored_record_ref must remain not-written" in serialized_errors


def test_task_record_write_uao_admission_preflight_rejects_mutation_route_and_secret() -> None:
    payload = validator.build_mutated_preflight(
        next_action="POST /api/harness/tasks should never be admitted",
    )
    payload["uao_admission"]["api_key"] = "sk-test-not-allowed"

    errors: list[str] = []
    validator._validate_semantics(payload, errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_task_record_write_uao_admission_preflight_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "task-record-write-uao-admission-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_validators_ok"] is True
