"""Purpose: verify the Universal Action Orchestration validation receipt contract.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_universal_action_orchestration_receipt_contract.
Invariants:
  - UAO validation receipts are schema-backed non-terminal witnesses.
  - Pass and fail receipt shapes remain causally consistent.
  - Host-local path ancestry is rejected from receipt path labels.
"""

from __future__ import annotations

import copy
import io
from contextlib import redirect_stdout

from scripts import validate_universal_action_orchestration_receipt_contract as validator


def test_universal_action_orchestration_validation_receipt_contract_passes() -> None:
    errors = validator.validate_contract()
    schema = validator.load_schema(validator.DEFAULT_SCHEMA_PATH)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:universal-action-orchestration-validation-receipt:1"
    assert schema["title"] == "Universal Action Orchestration Validation Receipt"
    assert "safe_path_label" in schema["$defs"]
    assert "check_result" in schema["$defs"]


def test_sample_receipts_are_non_terminal_and_count_consistent() -> None:
    passed_receipt, failed_receipt = validator.build_sample_receipts()

    assert validator.validate_receipt(passed_receipt) == []
    assert validator.validate_receipt(failed_receipt) == []
    assert passed_receipt["terminal_closure_required"] is True
    assert passed_receipt["receipt_is_not_terminal_closure"] is True
    assert passed_receipt["check_count"] == len(passed_receipt["checks"])
    assert failed_receipt["error_count"] == len(failed_receipt["errors"])
    assert failed_receipt["schema_path"] == "missing.schema.json"


def test_receipt_contract_rejects_identity_and_status_drift() -> None:
    passed_receipt, _ = validator.build_sample_receipts()
    invalid_receipt = copy.deepcopy(passed_receipt)
    invalid_receipt["receipt_id"] = "wrong"
    invalid_receipt["valid"] = False
    invalid_receipt["status"] = "passed"
    invalid_receipt["check_count"] = 999

    errors = validator.validate_receipt(invalid_receipt)

    assert len(errors) >= 4
    assert "receipt_id is invalid" in errors
    assert "receipt status must be failed for valid=False" in errors
    assert "check_count does not match checks length" in errors
    assert "valid must match aggregate check outcomes" in errors


def test_receipt_contract_rejects_host_local_path_labels() -> None:
    passed_receipt, _ = validator.build_sample_receipts()
    invalid_receipt = copy.deepcopy(passed_receipt)
    invalid_receipt["schema_path"] = "C:\\Users\\operator\\secret.schema.json"
    invalid_receipt["example_paths"] = ["../outside.json"]
    invalid_receipt["errors"] = ["leaked path C:\\Users\\operator\\private.json"]
    invalid_receipt["error_count"] = 1
    invalid_receipt["valid"] = False
    invalid_receipt["status"] = "failed"
    for check in invalid_receipt["checks"]:
        check["passed"] = False

    errors = validator.validate_receipt(invalid_receipt)

    assert len(errors) >= 3
    assert "schema_path must not contain a host-local absolute path" in errors
    assert "example_paths[0] must not contain parent-directory traversal" in errors
    assert "errors[0] must not contain a host-local absolute path" in errors


def test_receipt_contract_cli_reports_passed() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main([])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "universal_action_orchestration_validation_receipt_schema" in output
    assert "STATUS: passed" in output
