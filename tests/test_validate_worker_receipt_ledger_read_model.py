"""Purpose: verify WorkerReceiptLedgerReadModel validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_worker_receipt_ledger_read_model and SDLC validator.
Invariants:
  - Worker receipt ledger projection is read-only.
  - Foundation Mode does not read a live receipt store or dispatch workers.
  - Worker receipts remain non-terminal and cannot become success claims.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts import validate_worker_receipt_ledger_read_model as validator


def test_worker_receipt_ledger_read_model_passes() -> None:
    errors = validator.validate_worker_receipt_ledger_read_model()
    read_model = validator.load_json_object(
        validator.DEFAULT_READ_MODEL_PATH,
        "WorkerReceiptLedgerReadModel",
    )

    assert errors == []
    assert read_model["read_model_version"] == validator.EXPECTED_READ_MODEL_VERSION
    assert read_model["source_scope"]["projection_mode"] == validator.EXPECTED_PROJECTION_MODE
    assert read_model["source_scope"]["source_receipt_store_live_read_performed"] is False
    assert read_model["status_summary"]["chain_count"] == 3
    assert read_model["status_summary"]["blocked_chain_count"] == 2
    assert read_model["status_summary"]["recovery_required_count"] == 1
    assert read_model["authority_denials"]["worker_dispatch_allowed"] is False
    assert read_model["authority_denials"]["terminal_closure_allowed"] is False
    assert validator.validate_worker_receipt_ledger_read_model_record(read_model) == []


def test_worker_receipt_ledger_read_model_rejects_live_authority() -> None:
    mutated = validator.build_mutated_worker_receipt_ledger_read_model(
        source_scope__source_receipt_store_live_read_performed=True,
        authority_denials__live_receipt_store_read_allowed=True,
        authority_denials__worker_dispatch_allowed=True,
        authority_denials__runtime_receipt_emission_allowed=True,
        authority_denials__connector_call_allowed=True,
        authority_denials__filesystem_write_allowed=True,
        authority_denials__terminal_closure_allowed=True,
        authority_denials__success_claim_allowed=True,
        authority_denials__raw_secret_material_included=True,
    )

    errors = validator.validate_worker_receipt_ledger_read_model_record(mutated)

    assert any("source_receipt_store_live_read_performed" in error for error in errors)
    assert any("live_receipt_store_read_allowed" in error for error in errors)
    assert any("worker_dispatch_allowed" in error for error in errors)
    assert any("runtime_receipt_emission_allowed" in error for error in errors)
    assert any("connector_call_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)
    assert any("raw_secret_material_included" in error for error in errors)


def test_worker_receipt_ledger_read_model_rejects_chain_guard_drift() -> None:
    mutated = validator.build_mutated_worker_receipt_ledger_read_model(
        receipt_chains__0__latest_solver_outcome="SolvedVerified",
        receipt_chains__0__governance_guards__terminal_closure_allowed=True,
        receipt_chains__0__governance_guards__success_claim_allowed=True,
        receipt_chains__0__governance_guards__raw_payload_included=True,
        receipt_chains__0__governance_guards__live_dispatch_allowed=True,
        receipt_chains__1__recovery_required=False,
        receipt_chains__1__recovery_obligation_refs=[],
    )

    errors = validator.validate_worker_receipt_ledger_read_model_record(mutated)

    assert any("latest_solver_outcome" in error for error in errors)
    assert any("governance_guards.terminal_closure_allowed" in error for error in errors)
    assert any("governance_guards.success_claim_allowed" in error for error in errors)
    assert any("governance_guards.raw_payload_included" in error for error in errors)
    assert any("governance_guards.live_dispatch_allowed" in error for error in errors)
    assert any("recovery_required must be true" in error for error in errors)
    assert any("recovery_obligation_refs required" in error for error in errors)


def test_worker_receipt_ledger_read_model_rejects_summary_drift() -> None:
    mutated = validator.build_mutated_worker_receipt_ledger_read_model(
        status_summary__chain_count=1,
        status_summary__blocked_chain_count=0,
        status_summary__recovery_required_count=0,
        contract_summary__receipt_chain_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
        contract_summary__blocked_reason_ref_count=1,
        contract_summary__recovery_obligation_ref_count=1,
    )

    errors = validator.validate_worker_receipt_ledger_read_model_record(mutated)

    assert any("status_summary.chain_count" in error for error in errors)
    assert any("status_summary.blocked_chain_count" in error for error in errors)
    assert any("status_summary.recovery_required_count" in error for error in errors)
    assert any("contract_summary.receipt_chain_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)
    assert any("contract_summary.blocked_reason_ref_count" in error for error in errors)
    assert any("contract_summary.recovery_obligation_ref_count" in error for error in errors)


def test_worker_receipt_ledger_read_model_rejects_missing_refs() -> None:
    mutated = validator.build_mutated_worker_receipt_ledger_read_model(
        receipt_refs__worker_receipt_ledger_read_model_schema="schemas/other.schema.json",
        receipt_refs__connector_action_promotion_gate_schema="schemas/other_connector.schema.json",
        evidence_refs=["schemas/worker_receipt_ledger_read_model.schema.json"],
    )

    errors = validator.validate_worker_receipt_ledger_read_model_record(mutated)

    assert any("receipt_refs.worker_receipt_ledger_read_model_schema" in error for error in errors)
    assert any("receipt_refs.connector_action_promotion_gate_schema" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/worker_receipt_ledger_read_model.schema.json",
            "--read-model",
            "examples/worker_receipt_ledger_read_model.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/worker_receipt_ledger_read_model.schema.json"
    assert Path(payload["read_model_path"]).as_posix() == "examples/worker_receipt_ledger_read_model.foundation.json"
    assert payload["errors"] == []


def test_malformed_worker_receipt_ledger_read_model_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_worker_receipt_ledger_read_model_record(None, schema)
    list_errors = validator.validate_worker_receipt_ledger_read_model_record([], schema)

    assert any("worker receipt ledger read model must be a JSON object" in error for error in none_errors)
    assert any("worker receipt ledger read model must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_worker_receipt_ledger_read_model() -> None:
    requirement_path = Path("examples/sdlc/requirement_worker_receipt_ledger_read_model_20260616.json")
    design_path = Path("examples/sdlc/design_worker_receipt_ledger_read_model_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "worker receipt ledger read model requirement")
    design = sdlc_validator.load_json_object(design_path, "worker receipt ledger read model design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/worker_receipt_ledger_read_model.schema.json" in requirement["affected_surfaces"]
    assert "schemas/worker_receipt_ledger_read_model.schema.json" in design["schema_changes"]
    assert "scripts/validate_worker_receipt_ledger_read_model.py" in design["validator_changes"]
    assert "tests/test_validate_worker_receipt_ledger_read_model.py" in design["validator_changes"]
    assert "no live receipt store reads" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
