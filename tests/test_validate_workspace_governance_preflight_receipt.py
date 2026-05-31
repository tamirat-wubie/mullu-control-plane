"""Purpose: verify saved workspace governance preflight receipt validation.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.validate_workspace_governance_preflight_receipt.
Invariants:
  - Example receipt evidence is accepted.
  - Malformed or contradictory receipt evidence is rejected.
  - The validator is read-only.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import validate_workspace_governance_preflight_receipt as validator


def test_example_receipt_passes() -> None:
    receipt = validator.load_receipt(validator.DEFAULT_RECEIPT_PATH)
    errors = validator.validate_receipt_file(validator.DEFAULT_RECEIPT_PATH)

    assert errors == []
    assert receipt["receipt_id"] == "workspace_governance_preflight_receipt"
    assert receipt["terminal_closure_required"] is True
    assert receipt["receipt_is_not_terminal_closure"] is True
    assert receipt["status"] == "passed"


def test_saved_receipt_status_mismatch_is_reported(tmp_path: Path) -> None:
    receipt = validator.load_receipt(validator.DEFAULT_RECEIPT_PATH)
    invalid_receipt = copy.deepcopy(receipt)
    invalid_receipt["status"] = "failed"
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(invalid_receipt), encoding="utf-8")

    errors = validator.validate_receipt_file(receipt_path)

    assert any("status must be passed" in error for error in errors)
    assert len(errors) >= 1
    assert invalid_receipt["status"] == "failed"


def test_saved_receipt_missing_check_field_is_reported(tmp_path: Path) -> None:
    receipt = validator.load_receipt(validator.DEFAULT_RECEIPT_PATH)
    invalid_receipt = copy.deepcopy(receipt)
    del invalid_receipt["checks"][0]["stdout"]
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(invalid_receipt), encoding="utf-8")

    errors = validator.validate_receipt_file(receipt_path)

    assert any("missing field: stdout" in error for error in errors)
    assert invalid_receipt["check_count"] == 1
    assert receipt_path.exists()


def test_load_receipt_rejects_non_object_json(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_receipt(receipt_path)

    assert receipt_path.exists()
    assert receipt_path.name == "receipt.json"
