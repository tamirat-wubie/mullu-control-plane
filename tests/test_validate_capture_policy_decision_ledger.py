"""Purpose: verify CapturePolicyDecisionLedger validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_capture_policy_decision_ledger and SDLC validator.
Invariants:
  - Capture policy decisions are recorded before capture.
  - Raw observed content and raw secret material are never serialized.
  - Connector, execution, memory-write, and terminal closure authority remain denied.
  - The SDLC requirement and design artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_capture_policy_decision_ledger as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_capture_policy_decision_ledger_passes() -> None:
    errors = validator.validate_ledger()
    ledger = validator.load_json_object(validator.DEFAULT_LEDGER_PATH, "CapturePolicyDecisionLedger")

    assert errors == []
    assert ledger["ledger_version"] == validator.EXPECTED_LEDGER_VERSION
    assert ledger["solver_outcome"] == "SolvedVerified"
    assert ledger["governance_guards"]["capture_performed"] is False
    assert ledger["governance_guards"]["raw_observed_content_serialized"] is False
    assert ledger["decisions"][0]["decision_state"] == "CAPTURE_BLOCKED_BY_SENSITIVITY"
    assert validator.validate_ledger_record(ledger) == []


def test_ledger_rejects_authority_and_capture_claims() -> None:
    mutated = validator.build_mutated_ledger(
        governance_guards__capture_performed=True,
        governance_guards__raw_observed_content_serialized=True,
        governance_guards__raw_secret_material_included=True,
        governance_guards__connector_authority_granted=True,
        governance_guards__execution_authority_granted=True,
        governance_guards__memory_write_authority_granted=True,
        governance_guards__terminal_closure=True,
    )

    errors = validator.validate_ledger_record(mutated)

    assert any("capture_performed" in error for error in errors)
    assert any("raw_observed_content_serialized" in error for error in errors)
    assert any("raw_secret_material_included" in error for error in errors)
    assert any("connector_authority_granted" in error for error in errors)
    assert any("execution_authority_granted" in error for error in errors)
    assert any("memory_write_authority_granted" in error for error in errors)
    assert any("terminal_closure" in error for error in errors)
    assert mutated["governance_guards"]["mfidel_atomicity_preserved"] is True


def test_ledger_rejects_sensitivity_floor_drift() -> None:
    mutated = validator.build_mutated_ledger(
        sensitivity_floor__blocked_classifications=["payment"],
        sensitivity_floor__raw_value_serialization_allowed=True,
        sensitivity_floor__credential_capture_allowed=True,
        decisions__0__capture_class="REDACT",
        decisions__0__decision_state="CAPTURE_REDACTED",
        decisions__0__stored_payload_ref="redacted://bad/credential",
    )

    errors = validator.validate_ledger_record(mutated)

    assert any("must block credential, secret, and payment" in error for error in errors)
    assert any("raw_value_serialization_allowed must be false" in error for error in errors)
    assert any("credential_capture_allowed must be false" in error for error in errors)
    assert any("blocked sensitivity classification must use capture_class BLOCK" in error for error in errors)
    assert any("cannot carry stored_payload_ref" in error for error in errors)


def test_ledger_rejects_budget_and_policy_alignment_drift() -> None:
    mutated = validator.build_mutated_ledger(
        policy_scope__allowed_event_kinds=["document_text"],
        policy_scope__allowed_capture_classes=["BLOCK"],
        decisions__1__capture_class="REDACT",
        decisions__1__decision_state="CAPTURE_BLOCKED_BY_POLICY",
        decisions__1__policy_ref="policy://wrong/capture",
        budget_window__proof_state="BudgetUnknown",
        decisions__1__budget__scope_ref="budget://wrong/window",
        decisions__1__budget__budget_exceeded=True,
    )

    errors = validator.validate_ledger_record(mutated)

    assert any("event_kind must be allowed" in error for error in errors)
    assert any("capture_class must be allowed" in error for error in errors)
    assert any("policy_ref must match" in error for error in errors)
    assert any("proof_state must pass before REDACT" in error for error in errors)
    assert any("decision_state must match capture_class" in error for error in errors)
    assert any("budget.scope_ref must match" in error for error in errors)
    assert any("budget-exceeded decision" in error for error in errors)


def test_ledger_rejects_bad_prefix_and_evidence_drift() -> None:
    mutated = validator.build_mutated_ledger(
        receipt_envelope__uao_ref="trace://wrong/capture",
        receipt_envelope__causal_decision_trace_ref="receipt://wrong/capture",
        receipt_envelope__receipt_ref="uao://wrong/capture",
        decisions__1__stored_payload_ref="raw://bad/payload",
    )
    mutated["evidence_refs"] = [
        ref
        for ref in mutated["evidence_refs"]
        if ref != "tests/test_validate_capture_policy_decision_ledger.py"
    ]

    errors = validator.validate_ledger_record(mutated)

    assert any("receipt_envelope.uao_ref" in error for error in errors)
    assert any("receipt_envelope.causal_decision_trace_ref" in error for error in errors)
    assert any("receipt_envelope.receipt_ref" in error for error in errors)
    assert any("stored_payload_ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert mutated["governance_guards"]["capture_performed"] is False


def test_saved_ledger_file_validation(tmp_path: Path) -> None:
    ledger_path = tmp_path / "capture_policy_decision_ledger.json"
    ledger = validator.load_json_object(validator.DEFAULT_LEDGER_PATH, "CapturePolicyDecisionLedger")
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

    loaded = validator.load_json_object(ledger_path, "saved CapturePolicyDecisionLedger")
    errors = validator.validate_ledger_record(loaded)

    assert errors == []
    assert loaded["ledger_id"] == "capture-policy-ledger-foundation-browser-20260615"
    assert loaded["receipt_envelope"]["uao_ref"].startswith("uao://")
    assert loaded["receipt_envelope"]["causal_decision_trace_ref"].startswith("trace://")
    assert loaded["receipt_envelope"]["receipt_ref"].startswith("receipt://")
    assert loaded["decisions"][0]["stored_payload_ref"] is None


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/capture_policy_decision_ledger.schema.json",
            "--ledger",
            "examples/capture_policy_decision_ledger.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/capture_policy_decision_ledger.schema.json"
    assert Path(payload["ledger_path"]).as_posix() == "examples/capture_policy_decision_ledger.foundation.json"
    assert payload["errors"] == []


def test_malformed_ledger_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_ledger_record(None, schema)
    list_errors = validator.validate_ledger_record([], schema)

    assert any("capture policy decision ledger must be a JSON object" in error for error in none_errors)
    assert any("capture policy decision ledger must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_capture_policy_decision_ledger() -> None:
    requirement_path = Path("examples/sdlc/requirement_capture_policy_decision_ledger_20260615.json")
    design_path = Path("examples/sdlc/design_capture_policy_decision_ledger_20260615.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "CapturePolicyDecisionLedger requirement")
    design = sdlc_validator.load_json_object(design_path, "CapturePolicyDecisionLedger design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/capture_policy_decision_ledger.schema.json" in design["schema_changes"]
    assert "scripts/validate_capture_policy_decision_ledger.py" in design["validator_changes"]
    assert "no live capture execution" in requirement["non_goals"]
    assert "Credential, secret, and payment classifications are blocked" in requirement["success_criteria"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
