"""Tests for operator plan receipt bundle read-model validation.

Purpose: prove bundle examples are schema-backed and fail closed on count drift,
raw payload exposure, execution authority, and write authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: operator plan receipt bundle validator and foundation example.
Invariants:
  - Valid fixtures pass schema and semantic replay checks.
  - Count drift is rejected.
  - Raw message exposure, execution authority, and write authority are rejected.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.validate_operator_plan_receipt_bundle_read_model import (
    DEFAULT_EXAMPLE,
    validate_operator_plan_receipt_bundle_read_model,
)


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "operator_plan_receipt_bundle_read_model.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _example_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def test_operator_plan_receipt_bundle_example_passes() -> None:
    result = validate_operator_plan_receipt_bundle_read_model()

    assert result.valid is True
    assert result.errors == ()
    assert result.plan_export_count == 1
    assert result.receipt_count == 2


def test_operator_plan_receipt_bundle_rejects_count_drift(tmp_path: Path) -> None:
    payload = _example_payload()
    payload["receipt_count"] = 99
    path = _write_payload(tmp_path, payload)

    result = validate_operator_plan_receipt_bundle_read_model(path=path)

    assert result.valid is False
    assert "receipt_count must replay from plan_exports" in result.errors
    assert result.plan_export_count == 1
    assert result.receipt_count == 99


def test_operator_plan_receipt_bundle_rejects_effect_flags(tmp_path: Path) -> None:
    payload = _example_payload()
    payload["raw_message_exposed"] = True
    payload["execution_allowed"] = True
    payload["write_allowed"] = True
    path = _write_payload(tmp_path, payload)

    result = validate_operator_plan_receipt_bundle_read_model(path=path)

    assert result.valid is False
    assert "raw_message_exposed must be false" in result.errors
    assert "execution_allowed must be false" in result.errors
    assert "write_allowed must be false" in result.errors


def test_operator_plan_receipt_bundle_rejects_nested_export_authority(tmp_path: Path) -> None:
    payload = _example_payload()
    exports = payload["plan_exports"]
    assert isinstance(exports, list)
    first_export = exports[0]
    assert isinstance(first_export, dict)
    first_export["raw_message_exposed"] = True
    first_export["execution_allowed"] = True
    first_export["write_allowed"] = True
    path = _write_payload(tmp_path, payload)

    result = validate_operator_plan_receipt_bundle_read_model(path=path)

    assert result.valid is False
    assert "plan_exports[0].raw_message_exposed must be false" in result.errors
    assert "plan_exports[0].execution_allowed must be false" in result.errors
    assert "plan_exports[0].write_allowed must be false" in result.errors


def test_operator_plan_receipt_bundle_validator_cli_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_operator_plan_receipt_bundle_read_model.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "[PASS] operator_plan_receipt_bundle_read_model" in completed.stdout
    assert "STATUS: passed" in completed.stdout
