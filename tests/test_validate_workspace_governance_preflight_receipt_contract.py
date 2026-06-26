"""Purpose: verify workspace governance preflight receipt contract validation.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.validate_workspace_governance_preflight_receipt_contract.
Invariants:
  - The schema artifact carries all required receipt and check fields.
  - Synthetic receipts carry the canonical preflight check order and command tails.
  - Contradictory status and return-code evidence is rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import validate_workspace_governance_preflight_receipt_contract as validator


def test_current_receipt_contract_passes() -> None:
    errors = validator.validate_contract()
    schema = validator.load_schema(validator.DEFAULT_SCHEMA_PATH)
    check_name_enum = schema["$defs"]["check_result"]["properties"]["name"]["enum"]

    assert errors == []
    assert tuple(check_name_enum) == validator.REQUIRED_PREFLIGHT_CHECK_NAMES
    assert "foundation_source_control_review_checklist_boundary" in check_name_enum
    assert "phi_gps_v3_platform_spec" in check_name_enum
    assert "governance_normalization_map" in check_name_enum
    assert "universal_action_orchestration_validation_receipt_example" in check_name_enum
    assert "governed_code_change_loop_sandbox_probe_example" in check_name_enum
    assert "governed_code_change_loop_sandbox_readiness_runbook" in check_name_enum
    assert "intelligence_coordination_episode_receipt" in check_name_enum
    assert "engineering_puzzle_universality_witness" in check_name_enum
    assert "mil_audit_runbook_operator_checklist" in check_name_enum
    assert "general_agent_promotion_handoff_packet" in check_name_enum
    assert "general_agent_promotion_operator_checklist" in check_name_enum
    assert "general_agent_promotion_environment_bindings" in check_name_enum
    assert "general_agent_promotion_handoff_preflight" in check_name_enum
    assert "general_agent_promotion_closure_chain" in check_name_enum
    assert "finance_approval_live_handoff_closure_run" in check_name_enum
    assert "finance_approval_live_handoff_chain" in check_name_enum
    assert "route_receipt_coverage" in check_name_enum
    assert "route_guard_chain_coverage" in check_name_enum
    assert "reflective_contract_guard" in check_name_enum
    assert "doc_code_consistency" in check_name_enum
    assert "tenant_scope_coverage" in check_name_enum
    assert "persistence_tenant_guard_coverage" in check_name_enum
    assert "mcp_capability_manifest" in check_name_enum
    assert "mcp_operator_checklist" in check_name_enum
    assert "public_naming_readiness" in check_name_enum
    assert "public_demo_surfaces" in check_name_enum
    assert "strict_schema_validation" in check_name_enum
    assert "strict_artifact_validation" in check_name_enum
    assert "terminal_closure_certificate" in check_name_enum
    assert validator.DEFAULT_SCHEMA_PATH.exists()
    assert validator.DEFAULT_SCHEMA_PATH.name == "workspace_governance_preflight_receipt.schema.json"


def test_sample_receipts_have_expected_statuses() -> None:
    passed_receipt, failed_receipt = validator.build_sample_receipts()
    passed_names = [check["name"] for check in passed_receipt["checks"]]

    assert passed_receipt["status"] == "passed"
    assert failed_receipt["status"] == "failed"
    assert tuple(passed_names) == validator.REQUIRED_PREFLIGHT_CHECK_NAMES
    assert passed_receipt["check_count"] == len(validator.REQUIRED_PREFLIGHT_CHECK_NAMES)
    assert passed_receipt["terminal_closure_required"] is True
    assert failed_receipt["receipt_is_not_terminal_closure"] is True
    assert passed_receipt["checks"][0]["termination_reason"] == "completed"
    assert passed_receipt["checks"][0]["termination_signal"] is None


def test_invalid_receipt_status_and_check_flag_are_reported() -> None:
    passed_receipt, _failed_receipt = validator.build_sample_receipts()
    invalid_status = copy.deepcopy(passed_receipt)
    invalid_status["status"] = "failed"
    invalid_check = copy.deepcopy(passed_receipt)
    invalid_check["checks"][0]["passed"] = False

    status_errors = validator.validate_receipt(invalid_status)
    check_errors = validator.validate_receipt(invalid_check)

    assert any("status must be passed" in error for error in status_errors)
    assert any("passed does not match return_code" in error for error in check_errors)
    assert len(status_errors) >= 1


def test_unexpected_receipt_fields_are_reported() -> None:
    passed_receipt, _failed_receipt = validator.build_sample_receipts()
    invalid_receipt = copy.deepcopy(passed_receipt)
    invalid_receipt["execution_receipt_ref"] = "receipt:forbidden"
    invalid_receipt["checks"][0]["unexpected_payload"] = "forbidden"

    errors = validator.validate_receipt(invalid_receipt)

    assert "receipt has unexpected field: execution_receipt_ref" in errors
    assert "check 0 has unexpected field: unexpected_payload" in errors
    assert len(errors) >= 2


def test_optional_termination_diagnosis_is_validated() -> None:
    passed_receipt, _failed_receipt = validator.build_sample_receipts()
    terminated_receipt = copy.deepcopy(passed_receipt)
    terminated_receipt["checks"][0]["return_code"] = -15
    terminated_receipt["checks"][0]["passed"] = False
    terminated_receipt["checks"][0]["termination_reason"] = "terminated"
    terminated_receipt["checks"][0]["termination_signal"] = 15
    terminated_receipt["status"] = "failed"
    invalid_reason = copy.deepcopy(passed_receipt)
    invalid_reason["checks"][0]["termination_reason"] = "unknown"
    invalid_signal = copy.deepcopy(passed_receipt)
    invalid_signal["checks"][0]["termination_signal"] = 15
    exception_receipt = copy.deepcopy(passed_receipt)
    exception_receipt["checks"][0]["return_code"] = 126
    exception_receipt["checks"][0]["passed"] = False
    exception_receipt["checks"][0]["termination_reason"] = "exception"
    exception_receipt["status"] = "failed"

    terminated_errors = validator.validate_receipt(terminated_receipt)
    reason_errors = validator.validate_receipt(invalid_reason)
    signal_errors = validator.validate_receipt(invalid_signal)
    exception_errors = validator.validate_receipt(exception_receipt)

    assert terminated_errors == []
    assert exception_errors == []
    assert "check 0 termination_reason is invalid" in reason_errors
    assert "check 0 non-terminated checks must not set termination_signal" in signal_errors


def test_check_count_type_drift_is_reported() -> None:
    passed_receipt, _failed_receipt = validator.build_sample_receipts()
    invalid_receipt = copy.deepcopy(passed_receipt)
    invalid_receipt["check_count"] = "11"

    errors = validator.validate_receipt(invalid_receipt)

    assert "check_count must be integer" in errors
    assert invalid_receipt["status"] == "passed"
    assert invalid_receipt["checks"]


def test_missing_required_preflight_gate_is_reported() -> None:
    passed_receipt, _failed_receipt = validator.build_sample_receipts()
    invalid_receipt = copy.deepcopy(passed_receipt)
    invalid_receipt["checks"] = [
        check
        for check in invalid_receipt["checks"]
        if check["name"] != "universal_action_orchestration_validation_receipt_example"
    ]
    invalid_receipt["check_count"] = len(invalid_receipt["checks"])

    errors = validator.validate_receipt(invalid_receipt)

    assert any("checks must preserve the canonical workspace governance check order" in error for error in errors)
    assert any("universal_action_orchestration_validation_receipt_example" in error for error in errors)
    assert len(errors) >= 2


def test_receipt_command_tail_drift_is_reported() -> None:
    passed_receipt, _failed_receipt = validator.build_sample_receipts()
    invalid_receipt = copy.deepcopy(passed_receipt)
    target_index = next(
        index
        for index, check in enumerate(invalid_receipt["checks"])
        if check["name"] == "universal_action_orchestration_validation_receipt_example"
    )
    invalid_receipt["checks"][target_index]["args"] = ["python", "scripts/validate_universal_action_orchestration.py"]

    errors = validator.validate_receipt(invalid_receipt)

    assert any("args do not match canonical preflight command" in error for error in errors)
    assert invalid_receipt["checks"][target_index]["name"] == "universal_action_orchestration_validation_receipt_example"
    assert invalid_receipt["checks"][target_index]["return_code"] == 0


def test_load_schema_rejects_non_object_json(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_schema(schema_path)

    assert schema_path.exists()
    assert schema_path.name == "schema.json"
