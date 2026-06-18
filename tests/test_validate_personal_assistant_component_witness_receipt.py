"""Tests for personal-assistant component witness receipt validation.

Purpose: prove component witness receipts are schema-backed and fail closed on
authority, request-path, lifecycle, and secret-boundary drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: collector and validator scripts for component witness receipts.
Invariants:
  - Closed receipts require component, request-path, lifecycle, and no-effect evidence.
  - Open receipts remain valid unless closed evidence is required.
  - Secret-shaped serialized values are rejected.
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_component_witness import (  # noqa: E402
    collect_personal_assistant_component_witness,
)
from scripts.validate_personal_assistant_component_witness_receipt import (  # noqa: E402
    validate_personal_assistant_component_witness_receipt,
    write_personal_assistant_component_witness_validation_report,
)


FIXED_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _closed_receipt() -> dict[str, object]:
    return collect_personal_assistant_component_witness(now_utc=FIXED_NOW)


def _write_receipt(tmp_path: Path, payload: dict[str, object]) -> Path:
    receipt_path = tmp_path / "personal_assistant_component_witness.json"
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return receipt_path


def test_validation_accepts_schema_valid_closed_witness(tmp_path: Path) -> None:
    receipt_path = _write_receipt(tmp_path, _closed_receipt())

    validation = validate_personal_assistant_component_witness_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.witness_closed is True
    assert validation.receipt_id.startswith("personal-assistant-component-witness-")
    assert all(step.passed for step in validation.steps)


def test_validation_rejects_open_witness_with_request_path_drift(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["proof_state"] = "Fail"
    receipt["solver_outcome"] = "AwaitingEvidence"
    summary = receipt["summary"]
    assert isinstance(summary, dict)
    summary["witness_closed"] = False
    summary["request_path_witness_verified"] = False
    request_path = receipt["request_path_witness"]
    assert isinstance(request_path, dict)
    request_path["send_email_path_blocked"] = False
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_component_witness_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.witness_closed is False
    assert any(step.name == "request path witness" and step.passed is False for step in validation.steps)
    assert any(step.name == "witness gate" and step.passed is True for step in validation.steps)


def test_validation_require_closed_blocks_open_witness(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["proof_state"] = "Fail"
    receipt["solver_outcome"] = "AwaitingEvidence"
    summary = receipt["summary"]
    assert isinstance(summary, dict)
    summary["witness_closed"] = False
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_component_witness_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.witness_closed is False
    assert any(step.name == "require closed" and step.passed is False for step in validation.steps)


def test_validation_rejects_closed_summary_with_open_solver_outcome(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["proof_state"] = "Fail"
    receipt["solver_outcome"] = "AwaitingEvidence"
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_component_witness_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert validation.witness_closed is True
    assert any(step.name == "witness gate" and step.passed is False for step in validation.steps)


def test_validation_rejects_live_authority_drift(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["effect_boundary"]["can_execute"] = True  # type: ignore[index]
    receipt["effect_boundary"]["can_call_connector"] = True  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_component_witness_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert validation.witness_closed is True
    assert any(step.name == "schema contract" and step.passed is False for step in validation.steps)
    assert any(step.name == "no-effect boundary" and step.passed is False for step in validation.steps)


def test_validation_rejects_secret_shaped_serialized_values(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt_copy = copy.deepcopy(receipt)
    receipt_copy["lineage"]["accepted_deltas"][0]["reason"] = "Bearer token"  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt_copy)

    validation = validate_personal_assistant_component_witness_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "secret boundary" and step.passed is False for step in validation.steps)
    assert validation.receipt_id.startswith("personal-assistant-component-witness-")


def test_validation_report_writer_outputs_bounded_summary(tmp_path: Path) -> None:
    receipt_path = _write_receipt(tmp_path, _closed_receipt())
    validation_path = tmp_path / "validation.json"
    validation = validate_personal_assistant_component_witness_receipt(receipt_path=receipt_path)

    write_personal_assistant_component_witness_validation_report(validation, validation_path)
    report = json.loads(validation_path.read_text(encoding="utf-8"))

    assert report["valid"] is True
    assert report["solver_outcome"] == "SolvedVerified"
    assert report["witness_closed"] is True
    assert report["receipt_path"] == "provided_receipt"
    assert len(report["steps"]) >= 8
