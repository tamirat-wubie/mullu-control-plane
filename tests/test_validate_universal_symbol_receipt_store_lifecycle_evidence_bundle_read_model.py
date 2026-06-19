"""Tests for lifecycle evidence bundle read-model validation.

Purpose: prove the lifecycle evidence bundle operator projection exposes
bounded status without lifecycle authority or raw detail visibility.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lifecycle evidence bundle read-model validator and schema.
Invariants:
  - Read model authority remains denied.
  - Every lifecycle evidence kind appears exactly once.
  - Raw detail visibility stays hidden by default.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model import (
    DEFAULT_READ_MODEL_PATH,
    DEFAULT_SCHEMA_PATH,
    UniversalSymbolReceiptStoreLifecycleEvidenceBundleReadModelError,
    validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model,
)


def _write_case(tmp_path: Path, value: dict[str, object]) -> Path:
    case_path = tmp_path / "lifecycle-evidence-bundle-read-model.json"
    case_path.write_text(json.dumps(value), encoding="utf-8")
    return case_path


def test_foundation_lifecycle_evidence_bundle_read_model_validates() -> None:
    report = validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model()

    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["primary_status"] == "Evidence bundle visible"
    assert report["evidence_kind_row_count"] == 7
    assert report["effective_denial_count"] == 11
    assert report["read_model_constraint_count"] == 7
    assert report["evidence_ref_count"] == 10
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    assert read_model["bundle_projection"]["content_verified_entry_count"] == 0
    assert all(row["operator_status"] == "Needs live content" for row in read_model["evidence_kind_rows"])
    assert all(row["content_verified"] is False for row in read_model["evidence_kind_rows"])


def test_lifecycle_evidence_bundle_read_model_rejects_authority_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["effective_denials"]["receipt_store_append_performed"] = True

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleReadModelError,
        match="effective_denials.receipt_store_append_performed",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["read_model_is_not_lifecycle_authority"] is True
    assert changed["effective_denials"]["receipt_store_append_performed"] is True
    assert len(changed["evidence_kind_rows"]) == 7


def test_lifecycle_evidence_bundle_read_model_rejects_raw_detail_visibility(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["evidence_kind_rows"][0]["raw_detail_visible"] = True

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleReadModelError,
        match="raw_detail_visible must remain false",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["evidence_kind_rows"][0]["evidence_kind"] == "active_grant_identity"
    assert changed["evidence_kind_rows"][0]["authority_granted"] is False
    assert changed["effective_denials"]["raw_payload_exposed"] is False


def test_lifecycle_evidence_bundle_read_model_rejects_missing_evidence_kind(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["evidence_kind_rows"] = [
        row for row in changed["evidence_kind_rows"] if row["evidence_kind"] != "revocation_request"
    ]
    changed["contract_summary"]["evidence_kind_row_count"] = len(changed["evidence_kind_rows"])

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleReadModelError,
        match="revocation_request",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert len(changed["evidence_kind_rows"]) == 6
    assert changed["contract_summary"]["evidence_kind_row_count"] == 6
    assert changed["effective_denials"]["terminal_closure_allowed"] is False


def test_lifecycle_evidence_bundle_read_model_rejects_placeholder_content_verified(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["evidence_kind_rows"][0]["placeholder_ref"] = True
    changed["evidence_kind_rows"][0]["content_verified"] = True

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleReadModelError,
        match="placeholder ref cannot be content verified",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["evidence_kind_rows"][0]["evidence_kind"] == "active_grant_identity"
    assert changed["evidence_kind_rows"][0]["authority_granted"] is False
    assert changed["evidence_kind_rows"][0]["raw_detail_visible"] is False


def test_lifecycle_evidence_bundle_read_model_rejects_source_count_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["bundle_projection"]["content_verified_entry_count"] = 7

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleReadModelError,
        match="content_verified_entry_count",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["bundle_projection"]["authority_granted"] is False
    assert changed["bundle_projection"]["placeholder_entry_count"] == 0
    assert len(changed["evidence_kind_rows"]) == 7


def test_lifecycle_evidence_bundle_read_model_rejects_row_source_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["evidence_kind_rows"][0]["content_verified"] = True
    changed["evidence_kind_rows"][0]["operator_status"] = "Verified ref"

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleReadModelError,
        match="content_verified must match source bundle",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["evidence_kind_rows"][0]["evidence_kind"] == "active_grant_identity"
    assert changed["evidence_kind_rows"][0]["authority_granted"] is False
    assert changed["effective_denials"]["lifecycle_authority_granted"] is False


def test_lifecycle_evidence_bundle_read_model_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    read_model = json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(read_model)
    changed["contract_summary"]["evidence_ref_count"] = 999

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleReadModelError,
        match="evidence_ref_count drift",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["contract_summary"]["evidence_ref_count"] == 999
    assert len(changed["evidence_refs"]) == 10
    assert changed["effective_denials"]["raw_secret_exposed"] is False
