"""Purpose: verify saved Universal Action Orchestration receipt replay validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_universal_action_orchestration_receipt.
Invariants:
  - Example UAO validation receipt evidence is accepted.
  - Malformed or contradictory persisted receipt evidence is rejected.
  - The validator is read-only.
"""

from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from scripts import validate_universal_action_orchestration_receipt as validator


def test_example_universal_action_orchestration_receipt_passes() -> None:
    receipt = validator.load_receipt(validator.DEFAULT_RECEIPT_PATH)
    errors = validator.validate_receipt_file(validator.DEFAULT_RECEIPT_PATH)

    assert errors == []
    assert receipt["receipt_id"] == "universal_action_orchestration_validation_receipt"
    assert receipt["terminal_closure_required"] is True
    assert receipt["receipt_is_not_terminal_closure"] is True
    assert receipt["status"] == "passed"


def test_saved_receipt_status_mismatch_is_reported(tmp_path: Path) -> None:
    receipt = validator.load_receipt(validator.DEFAULT_RECEIPT_PATH)
    invalid_receipt = copy.deepcopy(receipt)
    invalid_receipt["status"] = "failed"
    receipt_path = tmp_path / "uao-validation-receipt.json"
    receipt_path.write_text(json.dumps(invalid_receipt), encoding="utf-8")

    errors = validator.validate_receipt_file(receipt_path)

    assert any("receipt status must be passed for valid=True" in error for error in errors)
    assert any("failed receipt must carry at least one error" in error for error in errors)
    assert invalid_receipt["status"] == "failed"
    assert receipt_path.exists()


def test_saved_receipt_missing_check_field_is_reported(tmp_path: Path) -> None:
    receipt = validator.load_receipt(validator.DEFAULT_RECEIPT_PATH)
    invalid_receipt = copy.deepcopy(receipt)
    del invalid_receipt["checks"][0]["passed"]
    receipt_path = tmp_path / "uao-validation-receipt.json"
    receipt_path.write_text(json.dumps(invalid_receipt), encoding="utf-8")

    errors = validator.validate_receipt_file(receipt_path)

    assert any("checks[0] missing field: passed" in error for error in errors)
    assert len(errors) >= 1
    assert invalid_receipt["check_count"] == 5
    assert receipt_path.name == "uao-validation-receipt.json"


def test_saved_failed_receipt_is_not_admitted_as_replay_witness(tmp_path: Path) -> None:
    receipt = validator.load_receipt(validator.DEFAULT_RECEIPT_PATH)
    failed_receipt = copy.deepcopy(receipt)
    failed_receipt["valid"] = False
    failed_receipt["status"] = "failed"
    failed_receipt["errors"] = ["example failure"]
    failed_receipt["error_count"] = 1
    for check in failed_receipt["checks"]:
        check["passed"] = False
    receipt_path = tmp_path / "uao-validation-receipt.json"
    receipt_path.write_text(json.dumps(failed_receipt), encoding="utf-8")

    errors = validator.validate_receipt_file(receipt_path)

    assert errors == ["receipt status must be passed for replay witness"]
    assert failed_receipt["status"] == "failed"
    assert failed_receipt["error_count"] == 1
    assert receipt_path.exists()


def test_load_receipt_rejects_non_object_json(tmp_path: Path) -> None:
    receipt_path = tmp_path / "uao-validation-receipt.json"
    receipt_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_receipt(receipt_path)

    assert receipt_path.exists()
    assert receipt_path.suffix == ".json"
    assert receipt_path.read_text(encoding="utf-8").startswith("[")


def test_receipt_validator_cli_reports_passed() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main([])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "universal_action_orchestration_validation_receipt_file" in output
    assert "universal_action_orchestration_validation_receipt_status" in output
    assert "STATUS: passed" in output
