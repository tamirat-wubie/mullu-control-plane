from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_universal_symbol_receipt_store_lifecycle_evidence_receipt import (
    DEFAULT_RECEIPT_PATH,
    DEFAULT_SCHEMA_PATH,
    UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError,
    validate_universal_symbol_receipt_store_lifecycle_evidence_receipt,
)


def _write_case(tmp_path: Path, value: dict[str, object]) -> Path:
    case_path = tmp_path / "lifecycle-evidence-receipt.json"
    case_path.write_text(json.dumps(value), encoding="utf-8")
    return case_path


def test_foundation_universal_symbol_receipt_store_lifecycle_evidence_receipt_validates() -> None:
    report = validate_universal_symbol_receipt_store_lifecycle_evidence_receipt()

    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["lifecycle_evidence_decision"]
        == "blocked_pending_live_grant_temporal_revocation_replacement_and_audit_evidence"
    )
    assert report["authority_denial_count"] == 12
    assert report["live_evidence_requirement_count"] == 7
    assert report["evidence_ref_count"] == 14


def test_lifecycle_evidence_receipt_rejects_lifecycle_authority_drift(tmp_path: Path) -> None:
    receipt = json.loads(DEFAULT_RECEIPT_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(receipt)
    changed["lifecycle_evidence_receipt_is_not_lifecycle_authority"] = False
    changed["authority_denials"]["approval_grant_extended"] = True

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError,
        match="lifecycle authority",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_receipt(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )


def test_lifecycle_evidence_receipt_rejects_missing_live_evidence_kind(tmp_path: Path) -> None:
    receipt = json.loads(DEFAULT_RECEIPT_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(receipt)
    changed["required_live_evidence"] = [
        item
        for item in changed["required_live_evidence"]
        if item["evidence_kind"] != "revocation_request"
    ]
    changed["contract_summary"]["live_evidence_requirement_count"] = len(changed["required_live_evidence"])

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError,
        match="revocation_request",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_receipt(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )


def test_lifecycle_evidence_receipt_rejects_missing_delta_reject(tmp_path: Path) -> None:
    receipt = json.loads(DEFAULT_RECEIPT_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(receipt)
    changed["required_live_evidence"][0]["delta_reject_ref"] = "missing-delta"

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError,
        match="delta_reject_ref",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_receipt(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )


def test_lifecycle_evidence_receipt_rejects_consistency_drift(tmp_path: Path) -> None:
    receipt = json.loads(DEFAULT_RECEIPT_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(receipt)
    changed["evidence_consistency_constraints"]["replacement_decision_links_revoked_grant_required"] = False

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError,
        match="replacement_decision_links_revoked_grant_required",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_receipt(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )


def test_lifecycle_evidence_receipt_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    receipt = json.loads(DEFAULT_RECEIPT_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(receipt)
    changed["contract_summary"]["evidence_ref_count"] = 999

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError,
        match="evidence_ref_count drift",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_receipt(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )
