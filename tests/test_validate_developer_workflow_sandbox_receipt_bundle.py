"""Tests for Developer Workflow sandbox receipt bundle validation.

Purpose: prove the local lab receipt bundle is source-bound, ordered, and
semantically consistent before PR preparation can consume it.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_developer_workflow_sandbox_receipt_bundle and
the receipt bundle schema/example pair.
Invariants: no external effects, canonical receipt order, and complete receipts
must carry concrete evidence plus rollback data.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_developer_workflow_sandbox_receipt_bundle import (
    DEFAULT_BUNDLE,
    DEFAULT_OUTPUT,
    validate_developer_workflow_sandbox_receipt_bundle,
    write_developer_workflow_sandbox_receipt_bundle_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_BUNDLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    bundle_path = tmp_path / "developer_workflow_sandbox_receipt_bundle.json"
    bundle_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bundle_path


def test_developer_workflow_sandbox_receipt_bundle_validates_and_writes_report(tmp_path: Path) -> None:
    validation = validate_developer_workflow_sandbox_receipt_bundle()
    output_path = tmp_path / "sandbox-receipt-bundle-validation.json"

    written_path = write_developer_workflow_sandbox_receipt_bundle_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.bundle_status == "awaiting_receipts"
    assert validation.completed_count == 0
    assert validation.required_count == 4
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "developer_workflow_sandbox_receipt_bundle_validation.json"


def test_developer_workflow_sandbox_receipt_bundle_rejects_external_effect_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["external_effects_allowed"] = True
    payload["execution_boundary"] = "production"

    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "external_effects_allowed must remain false" in serialized_errors
    assert "execution_boundary must be local_lab_only" in serialized_errors


def test_developer_workflow_sandbox_receipt_bundle_rejects_order_and_source_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    receipts = payload["receipts"]
    assert isinstance(receipts, list)
    receipts.reverse()
    receipts[0]["source"] = "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.other"  # type: ignore[index]

    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "receipts must list canonical receipt ids in order" in serialized_errors
    assert "source must be" in serialized_errors


def test_developer_workflow_sandbox_receipt_bundle_rejects_pending_receipt_with_concrete_evidence(tmp_path: Path) -> None:
    payload = _default_payload()
    receipts = payload["receipts"]
    assert isinstance(receipts, list)
    receipts[0]["evidence_refs"] = ["proof://sandbox-patch"]  # type: ignore[index]
    receipts[0]["diff_hash"] = "abc123"  # type: ignore[index]

    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "pending evidence_refs must be empty" in serialized_errors
    assert "diff_hash must be pending until receipt completion" in serialized_errors


def test_developer_workflow_sandbox_receipt_bundle_rejects_complete_receipt_without_concrete_evidence(tmp_path: Path) -> None:
    payload = _default_payload()
    receipts = payload["receipts"]
    assert isinstance(receipts, list)
    receipts[0]["status"] = "complete"  # type: ignore[index]
    payload["completed_count"] = 1

    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "complete evidence_refs must be non-empty" in serialized_errors
    assert "before_state_hash must be concrete when complete" in serialized_errors


def test_developer_workflow_sandbox_receipt_bundle_rejects_completed_count_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["completed_count"] = 2
    payload["bundle_status"] = "receipts_complete"

    validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "completed_count must match complete receipts" in serialized_errors
    assert "bundle_status must be 'awaiting_receipts'" in serialized_errors
