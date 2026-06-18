"""Tests for personal-assistant foundation evidence receipt validation.

Purpose: prove aggregate foundation evidence receipts are schema-backed and
fail closed on evidence, authority, gate, and secret-boundary drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: collector and validator scripts for foundation evidence receipts.
Invariants:
  - Closed receipts require console, public probe, component witness, and no-effect evidence.
  - Open receipts remain valid only when internally consistent.
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

from scripts.collect_personal_assistant_foundation_evidence import (  # noqa: E402
    collect_personal_assistant_foundation_evidence,
)
from scripts.validate_personal_assistant_foundation_evidence_receipt import (  # noqa: E402
    validate_personal_assistant_foundation_evidence_receipt,
    write_personal_assistant_foundation_evidence_validation_report,
)


FIXED_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _closed_receipt() -> dict[str, object]:
    return collect_personal_assistant_foundation_evidence(now_utc=FIXED_NOW)


def _write_receipt(tmp_path: Path, payload: dict[str, object]) -> Path:
    receipt_path = tmp_path / "personal_assistant_foundation_evidence.json"
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return receipt_path


def test_validation_accepts_schema_valid_closed_foundation_evidence(tmp_path: Path) -> None:
    receipt_path = _write_receipt(tmp_path, _closed_receipt())

    validation = validate_personal_assistant_foundation_evidence_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.foundation_evidence_closed is True
    assert validation.receipt_id.startswith("personal-assistant-foundation-evidence-")
    assert all(step.passed for step in validation.steps)


def test_validation_rejects_missing_evidence_item(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["evidence_items"] = receipt["evidence_items"][:2]  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_foundation_evidence_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and step.passed is False for step in validation.steps)
    assert any(step.name == "evidence items" and step.passed is False for step in validation.steps)


def test_validation_rejects_closed_summary_with_open_solver_outcome(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["proof_state"] = "Fail"
    receipt["solver_outcome"] = "AwaitingEvidence"
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_foundation_evidence_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert validation.foundation_evidence_closed is True
    assert any(step.name == "evidence gate" and step.passed is False for step in validation.steps)


def test_validation_rejects_live_authority_drift(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["effect_boundary"]["execution_allowed"] = True  # type: ignore[index]
    receipt["effect_boundary"]["external_effect_allowed"] = True  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_foundation_evidence_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "schema contract" and step.passed is False for step in validation.steps)
    assert any(step.name == "no-effect boundary" and step.passed is False for step in validation.steps)


def test_validation_rejects_secret_shaped_serialized_values(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt_copy = copy.deepcopy(receipt)
    receipt_copy["lineage"]["accepted_deltas"][0]["reason"] = "Bearer token"  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt_copy)

    validation = validate_personal_assistant_foundation_evidence_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "secret boundary" and step.passed is False for step in validation.steps)
    assert validation.receipt_id.startswith("personal-assistant-foundation-evidence-")


def test_validation_report_writer_outputs_bounded_summary(tmp_path: Path) -> None:
    receipt_path = _write_receipt(tmp_path, _closed_receipt())
    validation_path = tmp_path / "validation.json"
    validation = validate_personal_assistant_foundation_evidence_receipt(receipt_path=receipt_path)

    write_personal_assistant_foundation_evidence_validation_report(validation, validation_path)
    report = json.loads(validation_path.read_text(encoding="utf-8"))

    assert report["valid"] is True
    assert report["solver_outcome"] == "SolvedVerified"
    assert report["foundation_evidence_closed"] is True
    assert report["receipt_path"] == "provided_receipt"
    assert len(report["steps"]) >= 7
