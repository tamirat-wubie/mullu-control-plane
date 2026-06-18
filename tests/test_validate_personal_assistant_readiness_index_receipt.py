"""Tests for personal-assistant readiness index receipt validation.

Purpose: prove readiness index receipts are schema-backed and fail closed on
source evidence, lane, authority, gate, and secret-boundary drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: collector and validator scripts for readiness index receipts.
Invariants:
  - Closed receipts require closed foundation evidence and no-effect lanes.
  - Production and customer-readiness claims remain false.
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

from scripts.collect_personal_assistant_readiness_index import (  # noqa: E402
    collect_personal_assistant_readiness_index,
)
from scripts.validate_personal_assistant_readiness_index_receipt import (  # noqa: E402
    validate_personal_assistant_readiness_index_receipt,
    write_personal_assistant_readiness_index_validation_report,
)


FIXED_NOW = datetime(2026, 6, 16, 14, 0, tzinfo=UTC)


def _closed_receipt() -> dict[str, object]:
    return collect_personal_assistant_readiness_index(now_utc=FIXED_NOW)


def _write_receipt(tmp_path: Path, payload: dict[str, object]) -> Path:
    receipt_path = tmp_path / "personal_assistant_readiness_index.json"
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return receipt_path


def test_validation_accepts_schema_valid_closed_readiness_index(tmp_path: Path) -> None:
    receipt_path = _write_receipt(tmp_path, _closed_receipt())

    validation = validate_personal_assistant_readiness_index_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.readiness_index_closed is True
    assert validation.receipt_id.startswith("personal-assistant-readiness-index-")
    assert all(step.passed for step in validation.steps)


def test_validation_rejects_missing_lane_record(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["lane_records"] = receipt["lane_records"][:11]  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_readiness_index_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "readiness counts" and step.passed is False for step in validation.steps)
    assert validation.readiness_index_closed is True


def test_validation_rejects_live_authority_drift(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["effect_boundary"]["execution_allowed"] = True  # type: ignore[index]
    receipt["authority_blocks"]["live_execution_blocked"] = False  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_readiness_index_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and step.passed is False for step in validation.steps)
    assert any(step.name == "no-effect boundary" and step.passed is False for step in validation.steps)
    assert any(step.name == "authority blocks" and step.passed is False for step in validation.steps)


def test_validation_rejects_production_ready_overclaim(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["summary"]["production_ready"] = True  # type: ignore[index]
    receipt["readiness_index"]["production_ready_capability_count"] = 1  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_readiness_index_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and step.passed is False for step in validation.steps)
    assert any(step.name == "readiness counts" and step.passed is False for step in validation.steps)


def test_validation_rejects_secret_shaped_serialized_values(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt_copy = copy.deepcopy(receipt)
    receipt_copy["lineage"]["accepted_deltas"][0]["reason"] = "client_secret marker"  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt_copy)

    validation = validate_personal_assistant_readiness_index_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "secret boundary" and step.passed is False for step in validation.steps)
    assert validation.receipt_id.startswith("personal-assistant-readiness-index-")


def test_validation_report_writer_outputs_bounded_summary(tmp_path: Path) -> None:
    receipt_path = _write_receipt(tmp_path, _closed_receipt())
    validation_path = tmp_path / "validation.json"
    validation = validate_personal_assistant_readiness_index_receipt(receipt_path=receipt_path)

    write_personal_assistant_readiness_index_validation_report(validation, validation_path)
    report = json.loads(validation_path.read_text(encoding="utf-8"))

    assert report["valid"] is True
    assert report["solver_outcome"] == "SolvedVerified"
    assert report["readiness_index_closed"] is True
    assert report["receipt_path"] == "provided_receipt"
    assert len(report["steps"]) >= 10
