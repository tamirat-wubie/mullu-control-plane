"""Tests for path confinement read-model validation.

Purpose: prove the path confinement operator projection exposes bounded status
without path authority, filesystem escape, raw detail visibility, or path
confinement binding.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: path confinement read-model validator and schema.
Invariants:
  - Read model authority remains denied.
  - Every confinement requirement appears exactly once.
  - Delta_reject logging remains required for blocked hard constraints.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_universal_symbol_receipt_store_path_confinement_read_model import (
    DEFAULT_READ_MODEL_PATH,
    DEFAULT_SCHEMA_PATH,
    UniversalSymbolReceiptStorePathConfinementReadModelError,
    validate_universal_symbol_receipt_store_path_confinement_read_model,
)


def _write_case(tmp_path: Path, value: dict[str, object]) -> Path:
    case_path = tmp_path / "path-confinement-read-model.json"
    case_path.write_text(json.dumps(value), encoding="utf-8")
    return case_path


def test_foundation_path_confinement_read_model_validates() -> None:
    report = validate_universal_symbol_receipt_store_path_confinement_read_model()

    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["primary_status"] == "Path confinement blocked"
    assert report["requirement_row_count"] == 8
    assert report["effective_denial_count"] == 11
    assert report["read_model_constraint_count"] == 8
    assert report["evidence_ref_count"] == 10


def test_path_confinement_read_model_rejects_authority_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["effective_denials"]["receipt_store_path_confinement_bound"] = True

    with pytest.raises(
        UniversalSymbolReceiptStorePathConfinementReadModelError,
        match="effective_denials.receipt_store_path_confinement_bound",
    ):
        validate_universal_symbol_receipt_store_path_confinement_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["read_model_is_not_path_authority"] is True
    assert changed["effective_denials"]["receipt_store_path_confinement_bound"] is True
    assert len(changed["requirement_rows"]) == 8


def test_path_confinement_read_model_rejects_filesystem_escape_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["effective_denials"]["filesystem_escape_allowed"] = True

    with pytest.raises(
        UniversalSymbolReceiptStorePathConfinementReadModelError,
        match="effective_denials.filesystem_escape_allowed",
    ):
        validate_universal_symbol_receipt_store_path_confinement_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["read_model_constraints"]["no_filesystem_escape"] is True
    assert changed["effective_denials"]["filesystem_escape_allowed"] is True
    assert changed["effective_denials"]["terminal_closure_allowed"] is False


def test_path_confinement_read_model_rejects_raw_detail_visibility(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["requirement_rows"][0]["raw_detail_visible"] = True

    with pytest.raises(
        UniversalSymbolReceiptStorePathConfinementReadModelError,
        match="raw_detail_visible must remain false",
    ):
        validate_universal_symbol_receipt_store_path_confinement_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["requirement_rows"][0]["requirement_id"] == "requirement://canonical-root"
    assert changed["requirement_rows"][0]["authority_granted"] is False
    assert changed["effective_denials"]["raw_payload_stored"] is False


def test_path_confinement_read_model_rejects_missing_requirement(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["requirement_rows"] = [
        row for row in changed["requirement_rows"] if row["requirement_id"] != "requirement://canonical-root"
    ]
    changed["contract_summary"]["requirement_row_count"] = len(changed["requirement_rows"])

    with pytest.raises(
        UniversalSymbolReceiptStorePathConfinementReadModelError,
        match="requirement://canonical-root",
    ):
        validate_universal_symbol_receipt_store_path_confinement_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert len(changed["requirement_rows"]) == 7
    assert changed["contract_summary"]["requirement_row_count"] == 7
    assert changed["effective_denials"]["terminal_closure_allowed"] is False


def test_path_confinement_read_model_rejects_duplicate_requirement_row(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["requirement_rows"][0]["requirement_id"] = changed["requirement_rows"][1]["requirement_id"]

    with pytest.raises(
        UniversalSymbolReceiptStorePathConfinementReadModelError,
        match="requirement_rows values must be unique",
    ):
        validate_universal_symbol_receipt_store_path_confinement_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert len(changed["requirement_rows"]) == 8
    assert changed["requirement_rows"][0]["authority_granted"] is False
    assert changed["effective_denials"]["receipt_store_append_performed"] is False


def test_path_confinement_read_model_rejects_missing_delta_reject_log(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["requirement_rows"][0]["delta_reject_logged"] = False

    with pytest.raises(
        UniversalSymbolReceiptStorePathConfinementReadModelError,
        match="delta_reject_logged must remain true",
    ):
        validate_universal_symbol_receipt_store_path_confinement_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["requirement_rows"][0]["proof_state"] == "Unknown"
    assert changed["requirement_rows"][0]["authority_granted"] is False
    assert changed["effective_denials"]["state_mutation_performed"] is False


def test_path_confinement_read_model_rejects_witness_projection_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["witness_projection"]["blocked_reason_count"] = 9

    with pytest.raises(
        UniversalSymbolReceiptStorePathConfinementReadModelError,
        match="witness_projection.blocked_reason_count",
    ):
        validate_universal_symbol_receipt_store_path_confinement_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["witness_projection"]["authority_granted"] is False
    assert changed["witness_projection"]["confinement_requirement_count"] == 8
    assert len(changed["requirement_rows"]) == 8


def test_path_confinement_read_model_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["contract_summary"]["evidence_ref_count"] = 999

    with pytest.raises(
        UniversalSymbolReceiptStorePathConfinementReadModelError,
        match="evidence_ref_count drift",
    ):
        validate_universal_symbol_receipt_store_path_confinement_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["contract_summary"]["evidence_ref_count"] == 999
    assert len(changed["evidence_refs"]) == 10
    assert changed["effective_denials"]["raw_secret_stored"] is False
