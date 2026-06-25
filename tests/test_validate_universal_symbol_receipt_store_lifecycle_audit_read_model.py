"""Tests for lifecycle audit read-model validation.

Purpose: prove the lifecycle audit operator projection exposes bounded status
without lifecycle authority, raw detail visibility, or audit recording.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lifecycle audit read-model validator and schema.
Invariants:
  - Read model authority remains denied.
  - Every lifecycle audit requirement appears exactly once.
  - Delta_reject logging remains required for blocked hard constraints.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_universal_symbol_receipt_store_lifecycle_audit_read_model import (
    DEFAULT_READ_MODEL_PATH,
    DEFAULT_SCHEMA_PATH,
    UniversalSymbolReceiptStoreLifecycleAuditReadModelError,
    validate_universal_symbol_receipt_store_lifecycle_audit_read_model,
)


def _write_case(tmp_path: Path, value: dict[str, object]) -> Path:
    case_path = tmp_path / "lifecycle-audit-read-model.json"
    case_path.write_text(json.dumps(value), encoding="utf-8")
    return case_path


def test_foundation_lifecycle_audit_read_model_validates() -> None:
    report = validate_universal_symbol_receipt_store_lifecycle_audit_read_model()

    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["primary_status"] == "Lifecycle audit blocked"
    assert report["requirement_row_count"] == 8
    assert report["effective_denial_count"] == 12
    assert report["read_model_constraint_count"] == 7
    assert report["evidence_ref_count"] == 10


def test_lifecycle_audit_read_model_rejects_authority_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["effective_denials"]["receipt_store_lifecycle_audit_recorded"] = True

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleAuditReadModelError,
        match="effective_denials.receipt_store_lifecycle_audit_recorded",
    ):
        validate_universal_symbol_receipt_store_lifecycle_audit_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["read_model_is_not_lifecycle_authority"] is True
    assert changed["effective_denials"]["receipt_store_lifecycle_audit_recorded"] is True
    assert len(changed["requirement_rows"]) == 8


def test_lifecycle_audit_read_model_rejects_raw_detail_visibility(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["requirement_rows"][0]["raw_detail_visible"] = True

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleAuditReadModelError,
        match="raw_detail_visible must remain false",
    ):
        validate_universal_symbol_receipt_store_lifecycle_audit_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["requirement_rows"][0]["requirement_id"] == "requirement://source-lifecycle-witness"
    assert changed["requirement_rows"][0]["authority_granted"] is False
    assert changed["effective_denials"]["raw_payload_stored"] is False


def test_lifecycle_audit_read_model_rejects_missing_requirement(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["requirement_rows"] = [
        row for row in changed["requirement_rows"] if row["requirement_id"] != "requirement://auditor-identity"
    ]
    changed["contract_summary"]["requirement_row_count"] = len(changed["requirement_rows"])

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleAuditReadModelError,
        match="requirement://auditor-identity",
    ):
        validate_universal_symbol_receipt_store_lifecycle_audit_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert len(changed["requirement_rows"]) == 7
    assert changed["contract_summary"]["requirement_row_count"] == 7
    assert changed["effective_denials"]["terminal_closure_allowed"] is False


def test_lifecycle_audit_read_model_rejects_duplicate_requirement_row(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["requirement_rows"][0]["requirement_id"] = changed["requirement_rows"][1]["requirement_id"]

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleAuditReadModelError,
        match="requirement_rows values must be unique",
    ):
        validate_universal_symbol_receipt_store_lifecycle_audit_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert len(changed["requirement_rows"]) == 8
    assert changed["requirement_rows"][0]["authority_granted"] is False
    assert changed["effective_denials"]["receipt_store_append_performed"] is False


def test_lifecycle_audit_read_model_rejects_missing_delta_reject_log(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["requirement_rows"][0]["delta_reject_logged"] = False

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleAuditReadModelError,
        match="delta_reject_logged must remain true",
    ):
        validate_universal_symbol_receipt_store_lifecycle_audit_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["requirement_rows"][0]["proof_state"] == "Unknown"
    assert changed["requirement_rows"][0]["authority_granted"] is False
    assert changed["effective_denials"]["state_mutation_performed"] is False


def test_lifecycle_audit_read_model_rejects_receipt_projection_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["receipt_projection"]["blocked_reason_count"] = 9

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleAuditReadModelError,
        match="receipt_projection.blocked_reason_count",
    ):
        validate_universal_symbol_receipt_store_lifecycle_audit_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["receipt_projection"]["authority_granted"] is False
    assert changed["receipt_projection"]["audit_requirement_count"] == 8
    assert len(changed["requirement_rows"]) == 8


def test_lifecycle_audit_read_model_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["contract_summary"]["evidence_ref_count"] = 999

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleAuditReadModelError,
        match="evidence_ref_count drift",
    ):
        validate_universal_symbol_receipt_store_lifecycle_audit_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["contract_summary"]["evidence_ref_count"] == 999
    assert len(changed["evidence_refs"]) == 10
    assert changed["effective_denials"]["raw_secret_stored"] is False
