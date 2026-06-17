"""Worker failure receipt validator tests.

Purpose: prove the standalone worker failure validator catches terminal-closure,
unit-count, source-hash, and recovery-action drift.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: scripts.validate_worker_failure_receipt.
Invariants:
  - Failure receipts are not terminal closure certificates.
  - Partial completion must safe-halt by default.
  - Source receipt hashes are required.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_worker_failure_receipt as validator


def _example_payload() -> dict:
    return validator.load_json_object(validator.DEFAULT_EXAMPLE_PATH)


def test_worker_failure_receipt_example_passes() -> None:
    payload = _example_payload()
    errors = validator.validate_worker_failure_receipt(payload)

    assert errors == []
    assert payload["failure_state"] == "partial_completion"
    assert payload["recovery_action"] == "safe_halt"
    assert payload["receipt_is_not_terminal_closure"] is True


def test_worker_failure_receipt_rejects_terminal_closure_overclaim() -> None:
    payload = _example_payload()
    payload["receipt_is_not_terminal_closure"] = False
    payload["terminal_closure_required"] = False

    errors = validator.validate_worker_failure_receipt(payload)

    assert "$.terminal_closure_required: expected const True" in errors
    assert "$.receipt_is_not_terminal_closure: expected const True" in errors
    assert "terminal_closure_required must be true" in errors
    assert "receipt_is_not_terminal_closure must be true" in errors


def test_worker_failure_receipt_rejects_impossible_unit_drift() -> None:
    payload = _example_payload()
    payload["attempted_units"] = 1
    payload["completed_units"] = 2

    errors = validator.validate_worker_failure_receipt(payload)

    assert "completed_units cannot exceed attempted_units" in errors
    assert payload["completed_units"] > payload["attempted_units"]
    assert payload["failure_state"] == "partial_completion"


def test_worker_failure_receipt_rejects_partial_recovery_drift() -> None:
    payload = _example_payload()
    payload["recovery_action"] = "operator_review"
    payload["partial_completion"] = False

    errors = validator.validate_worker_failure_receipt(payload)

    assert "partial_completion state requires partial_completion true" in errors
    assert "partial_completion must default to safe_halt recovery" in errors
    assert payload["failure_state"] == "partial_completion"


def test_worker_failure_runtime_scenarios_cover_recovery_boundaries() -> None:
    errors = validator.validate_generated_worker_failure_scenarios()

    assert errors == []
    assert validator.WORKER_FAILURE_RECEIPT_SCHEMA_REF == "urn:mullusi:schema:worker-failure-receipt:1"
    assert validator.DEFAULT_SCHEMA_PATH.name == "worker_failure_receipt.schema.json"


def test_worker_failure_receipt_missing_file_error_is_bounded(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing-worker-failure.json"

    try:
        validator.load_json_object(missing_path)
    except FileNotFoundError as exc:
        message = str(exc)
    else:
        raise AssertionError("missing receipt should fail closed")

    assert "missing worker failure receipt artifact" in message
    assert str(missing_path) in message
    assert json.dumps({"path": str(missing_path)})
