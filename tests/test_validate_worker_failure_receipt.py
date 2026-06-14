"""Purpose: verify WorkerFailureReceipt validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_worker_failure_receipt and SDLC validator.
Invariants:
  - Worker failure receipts record failure and recovery obligations.
  - Partial or unknown effects do not become success claims.
  - Terminal closure, raw secrets, and execution-authority renewal are rejected.
  - The SDLC requirement and design artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts import validate_worker_failure_receipt as validator


def test_worker_failure_receipt_passes() -> None:
    errors = validator.validate_receipt()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "WorkerFailureReceipt")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["receipt_state"] == "PARTIAL_EXECUTION_RECORDED"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["rollback_required"] is True
    assert receipt["recovery_required"] is True
    assert validator.validate_receipt_record(receipt) == []


def test_receipt_rejects_success_and_terminal_claims() -> None:
    mutated = validator.build_mutated_receipt(
        governance_guards__terminal_closure=True,
        governance_guards__success_claim_allowed=True,
        governance_guards__execution_authority_renewal_allowed=True,
        governance_guards__raw_secret_material_included=True,
    )

    errors = validator.validate_receipt_record(mutated)

    assert any("terminal_closure" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)
    assert any("execution_authority_renewal_allowed" in error for error in errors)
    assert any("raw_secret_material_included" in error for error in errors)


def test_receipt_rejects_count_drift_and_raw_output() -> None:
    mutated = validator.build_mutated_receipt(
        failure_summary__failed_step_count=0,
        failure_summary__raw_output_included=True,
        failure_summary__raw_secret_material_included=True,
    )

    errors = validator.validate_receipt_record(mutated)

    assert any("failed_step_count" in error for error in errors)
    assert any("raw worker output must not be included" in error for error in errors)
    assert any("raw secret material must not be included" in error for error in errors)
    assert mutated["failure_summary"]["raw_output_included"] is True


def test_receipt_rejects_missing_failure_refs() -> None:
    mutated = validator.build_mutated_receipt(failed_step_refs=[])
    mutated["failure_summary"]["failed_step_count"] = 0

    errors = validator.validate_receipt_record(mutated)

    assert any("worker failure receipt requires failed_step_refs" in error for error in errors)
    assert any("failed_step_refs: expected at least 1 item" in error for error in errors)
    assert mutated["failed_step_refs"] == []
    assert mutated["failure_summary"]["failed_step_count"] == 0


def test_receipt_rejects_partial_or_unknown_without_recovery() -> None:
    mutated = validator.build_mutated_receipt(
        receipt_state="TIMEOUT_WITH_UNKNOWN_EFFECT",
        effect_status="effect_unknown",
        recovery_required=False,
        recovery_action_refs=[],
        blocked_reason_refs=[],
    )
    mutated["failure_summary"]["recovery_action_count"] = 0
    mutated["failure_summary"]["blocked_reason_count"] = 0

    errors = validator.validate_receipt_record(mutated)

    assert any("states require recovery_required true" in error for error in errors)
    assert mutated["effect_status"] == "effect_unknown"
    assert mutated["receipt_state"] == "TIMEOUT_WITH_UNKNOWN_EFFECT"
    assert mutated["recovery_required"] is False


def test_receipt_rejects_recovery_required_without_refs() -> None:
    mutated = validator.build_mutated_receipt(
        recovery_required=True,
        recovery_action_refs=[],
        blocked_reason_refs=[],
    )
    mutated["failure_summary"]["recovery_action_count"] = 0
    mutated["failure_summary"]["blocked_reason_count"] = 0

    errors = validator.validate_receipt_record(mutated)

    assert any("recovery_required requires recovery_action_refs or blocked_reason_refs" in error for error in errors)
    assert mutated["recovery_required"] is True
    assert mutated["recovery_action_refs"] == []
    assert mutated["blocked_reason_refs"] == []


def test_receipt_rejects_rollback_required_without_refs() -> None:
    mutated = validator.build_mutated_receipt(
        receipt_state="ROLLBACK_REQUIRED",
        effect_status="rollback_pending",
        rollback_required=True,
        rollback_action_refs=[],
    )
    mutated["failure_summary"]["rollback_action_count"] = 0

    errors = validator.validate_receipt_record(mutated)

    assert any("rollback_required requires rollback_action_refs" in error for error in errors)
    assert mutated["receipt_state"] == "ROLLBACK_REQUIRED"
    assert mutated["rollback_required"] is True
    assert mutated["rollback_action_refs"] == []


def test_receipt_accepts_failed_before_execution_no_effect_shape() -> None:
    mutated = validator.build_mutated_receipt(
        solver_outcome="GovernanceBlocked",
        receipt_state="FAILED_BEFORE_EXECUTION",
        failure_class="policy_denial",
        effect_status="no_effect_confirmed",
        rollback_required=False,
        recovery_required=False,
        completed_step_refs=[],
        partial_effect_refs=[],
        rollback_action_refs=[],
        recovery_action_refs=[],
        blocked_reason_refs=["blocked://worker/foundation/policy-denial"],
    )
    mutated["failure_summary"] = {
        "completed_step_count": 0,
        "failed_step_count": 1,
        "partial_effect_count": 0,
        "rollback_action_count": 0,
        "recovery_action_count": 0,
        "blocked_reason_count": 1,
        "raw_output_included": False,
        "raw_secret_material_included": False,
    }

    errors = validator.validate_receipt_record(mutated)

    assert errors == []
    assert mutated["effect_status"] == "no_effect_confirmed"
    assert mutated["rollback_required"] is False
    assert mutated["recovery_required"] is False


def test_receipt_accepts_safe_halt_record() -> None:
    mutated = validator.build_mutated_receipt(
        solver_outcome="SafeHalt",
        receipt_state="SAFE_HALT_RECORDED",
        failure_class="safety_floor",
        effect_status="recovery_pending",
        rollback_required=True,
        recovery_required=True,
    )

    errors = validator.validate_receipt_record(mutated)

    assert errors == []
    assert mutated["solver_outcome"] == "SafeHalt"
    assert mutated["receipt_state"] == "SAFE_HALT_RECORDED"
    assert mutated["governance_guards"]["terminal_closure"] is False


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/worker_failure_receipt.schema.json",
            "--receipt",
            "examples/worker_failure_receipt.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/worker_failure_receipt.schema.json"
    assert Path(payload["receipt_path"]).as_posix() == "examples/worker_failure_receipt.foundation.json"
    assert payload["errors"] == []


def test_malformed_receipt_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_receipt_record(None, schema)
    list_errors = validator.validate_receipt_record([], schema)

    assert any("worker failure receipt must be a JSON object" in error for error in none_errors)
    assert any("worker failure receipt must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_worker_failure_receipt() -> None:
    requirement_path = Path("examples/sdlc/requirement_worker_failure_receipt_contract_20260614.json")
    design_path = Path("examples/sdlc/design_worker_failure_receipt_contract_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "WorkerFailureReceipt requirement")
    design = sdlc_validator.load_json_object(design_path, "WorkerFailureReceipt design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/worker_failure_receipt.schema.json" in design["schema_changes"]
    assert "scripts/validate_worker_failure_receipt.py" in design["validator_changes"]
    assert "no live worker registration" in requirement["non_goals"]
    assert "WorkerFailureReceipt blocks terminal closure and success claims after worker failure" in requirement["success_criteria"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
