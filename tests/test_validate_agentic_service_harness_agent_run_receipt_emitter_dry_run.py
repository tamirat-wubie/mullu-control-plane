"""Test AgentRun receipt-emitter dry-run validation.

Purpose: verify the harness AgentRun receipt-emitter dry-run remains
contract-only and append-denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_agent_run_receipt_emitter_dry_run.
Invariants:
  - Dry-run receipt emission never executes adapters or writes runtime state.
  - Receipt-store append remains denied until future approval evidence exists.
  - Mutation routes and secret-like payloads fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_agentic_service_harness_agent_run_receipt_emitter_dry_run as validator


def test_agent_run_receipt_emitter_dry_run_passes() -> None:
    validation = validator.validate_agentic_service_harness_agent_run_receipt_emitter_dry_run()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.source_contract_ref == validator.EXPECTED_SOURCE_CONTRACT_REF


def test_agent_run_receipt_emitter_rejects_authority_drift() -> None:
    payload = validator.build_mutated_dry_run(
        scope__receipt_store_append_enabled=True,
        scope__external_adapter_integrated=True,
        simulated_receipt_emission__adapter_executed=True,
        simulated_receipt_emission__branch_created=True,
        simulated_receipt_emission__pull_request_opened=True,
        simulated_receipt_emission__runtime_state_written=True,
        authority_denials__live_adapter_execution_enabled=True,
        authority_denials__receipt_store_append_enabled=True,
        authority_denials__runtime_state_write_enabled=True,
    )

    errors: list[str] = []
    validator._validate_dry_run_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "scope.receipt_store_append_enabled must be false" in serialized_errors
    assert "scope.external_adapter_integrated must be false" in serialized_errors
    assert "simulated_receipt_emission.adapter_executed must be false" in serialized_errors
    assert "simulated_receipt_emission.branch_created must be false" in serialized_errors
    assert "simulated_receipt_emission.pull_request_opened must be false" in serialized_errors
    assert "simulated_receipt_emission.runtime_state_written must be false" in serialized_errors
    assert "authority_denials.live_adapter_execution_enabled must be false" in serialized_errors
    assert "authority_denials.receipt_store_append_enabled must be false" in serialized_errors
    assert "authority_denials.runtime_state_write_enabled must be false" in serialized_errors


def test_agent_run_receipt_emitter_rejects_append_gate_drift() -> None:
    payload = validator.build_mutated_dry_run(
        append_admission_gate__decision="APPEND_ADMITTED",
        append_admission_gate__append_admitted=True,
        append_admission_gate__terminal_closure_allowed=True,
        simulated_receipt_emission__receipt_store_appended=True,
        simulated_receipt_emission__runtime_receipt_emitted=True,
    )

    errors: list[str] = []
    validator._validate_dry_run_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "append_admission_gate.decision" in serialized_errors
    assert "append_admission_gate.append_admitted must be false" in serialized_errors
    assert "append_admission_gate.terminal_closure_allowed must be false" in serialized_errors
    assert "simulated_receipt_emission.receipt_store_appended must be false" in serialized_errors
    assert "simulated_receipt_emission.runtime_receipt_emitted must be false" in serialized_errors


def test_agent_run_receipt_emitter_rejects_missing_required_refs() -> None:
    payload = validator.build_mutated_dry_run(
        dry_run_contract__required_source_refs=["examples/agentic_service_harness_read_models.foundation.json"],
        dry_run_contract__required_gate_refs=["gate://harness/no-branch-write"],
        dry_run_contract__emission_obligations_checked=["obligation://record-dry-run-envelope"],
        dry_run_contract__validation_refs=[
            "scripts/validate_agentic_service_harness_agent_run_receipt_emitter_dry_run.py"
        ],
        append_admission_gate__required_before_append_refs=["evidence://uao-append-admission"],
        append_admission_gate__blocked_reason_refs=["blocked://uao/append-not-admitted"],
    )

    errors: list[str] = []
    validator._validate_dry_run_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "dry_run_contract.required_source_refs missing required ref" in serialized_errors
    assert "dry_run_contract.required_gate_refs missing required ref" in serialized_errors
    assert "dry_run_contract.emission_obligations_checked missing required ref" in serialized_errors
    assert "dry_run_contract.validation_refs missing required ref" in serialized_errors
    assert "append_admission_gate.required_before_append_refs missing required ref" in serialized_errors
    assert "append_admission_gate.blocked_reason_refs missing required ref" in serialized_errors


def test_agent_run_receipt_emitter_rejects_mutation_route_and_secret_like_payload() -> None:
    payload = validator.build_mutated_dry_run(
        next_action="POST /api/agent-runs/append should never be admitted",
    )
    payload["simulated_receipt_emission"]["serialized_token_value"] = "github_pat_forbiddencredential"

    errors: list[str] = []
    validator._validate_dry_run_semantics(payload, _source_contract(), errors, "mutated")
    serialized_errors = "\n".join(errors)

    assert "mutation route string" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_agent_run_receipt_emitter_cli_writes_report(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "agent-run-receipt-emitter-dry-run-validation.json"

    exit_code = validator.main(["--output", str(output_path), "--json", "--strict"])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert stdout_payload["ok"] is True
    assert file_payload["ok"] is True
    assert stdout_payload["errors"] == []
    assert file_payload["source_contract_ref"] == validator.EXPECTED_SOURCE_CONTRACT_REF


def _source_contract() -> dict[str, object]:
    return json.loads(validator.DEFAULT_SOURCE_CONTRACT_EXAMPLES[0].read_text(encoding="utf-8"))
