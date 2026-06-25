"""Tests for Universal Symbol lifecycle evidence bundle validation.

Purpose: prove lifecycle evidence bundles carry verified refs without granting
lifecycle authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lifecycle evidence bundle validator and lifecycle ref verifier.
Invariants:
  - Bundle authority remains denied.
  - Every lifecycle evidence kind appears exactly once.
  - Placeholder refs cannot be content verified.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.produce_universal_symbol_receipt_store_lifecycle_evidence_receipt import (
    EVIDENCE_KINDS,
    produce_lifecycle_evidence_receipt,
)
from scripts.validate_universal_symbol_receipt_store_lifecycle_evidence_bundle import (
    DEFAULT_BUNDLE_PATH,
    DEFAULT_SCHEMA_PATH,
    UniversalSymbolReceiptStoreLifecycleEvidenceBundleError,
    build_lifecycle_evidence_bundle_payload,
    validate_universal_symbol_receipt_store_lifecycle_evidence_bundle,
)
from scripts.verify_universal_symbol_receipt_store_lifecycle_evidence_refs import verify_lifecycle_evidence_refs


def _write_case(tmp_path: Path, value: dict[str, object]) -> Path:
    case_path = tmp_path / "lifecycle-evidence-bundle.json"
    case_path.write_text(json.dumps(value), encoding="utf-8")
    return case_path


def _complete_refs() -> dict[str, str]:
    return {
        "active_grant_identity": "grant://universal-symbol/lifecycle/active-grant-identity",
        "reapproval_window": "temporal://universal-symbol/lifecycle/reapproval-window",
        "expiry_evidence": "expiry://universal-symbol/lifecycle/expiry-evidence",
        "revocation_request": "revocation://universal-symbol/lifecycle/revocation-request",
        "revocation_effect_boundary": "effect-boundary://universal-symbol/lifecycle/revocation-effect-boundary",
        "replacement_decision": "approval-decision://universal-symbol/lifecycle/replacement-decision",
        "lifecycle_audit_receipt": "audit://universal-symbol/lifecycle/lifecycle-audit-receipt",
    }


def test_foundation_lifecycle_evidence_bundle_validates() -> None:
    report = validate_universal_symbol_receipt_store_lifecycle_evidence_bundle()

    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["verifier_status"] == "all_refs_structurally_verified_non_authorizing"
    assert report["evidence_entry_count"] == 7
    assert report["authority_denial_count"] == 12
    assert report["evidence_ref_count"] == 10
    bundle = json.loads(DEFAULT_BUNDLE_PATH.read_text(encoding="utf-8"))
    assert bundle["contract_summary"]["content_verified_entry_count"] == 0
    assert all(entry["content_verified"] is False for entry in bundle["evidence_entries"])


def test_build_lifecycle_evidence_bundle_from_verifier_report(tmp_path: Path) -> None:
    receipt_path = tmp_path / "lifecycle-evidence.json"
    produce_lifecycle_evidence_receipt(
        evidence_refs=_complete_refs(),
        output_path=receipt_path,
        clock=lambda: "2026-06-19T00:00:00Z",
    )
    verifier_report = verify_lifecycle_evidence_refs(receipt_path=receipt_path)

    bundle = build_lifecycle_evidence_bundle_payload(
        verifier_report,
        source_receipt_ref="tmp/lifecycle-evidence.json",
        generated_at="2026-06-19T00:00:00Z",
    )
    report = validate_universal_symbol_receipt_store_lifecycle_evidence_bundle(
        _write_case(tmp_path, bundle),
        DEFAULT_SCHEMA_PATH,
    )

    assert report["valid"] is True
    assert bundle["contract_summary"]["content_verified_entry_count"] == 0
    assert bundle["contract_summary"]["placeholder_entry_count"] == 0
    assert {entry["evidence_kind"] for entry in bundle["evidence_entries"]} == set(EVIDENCE_KINDS)
    assert all(entry["structurally_verified"] is True for entry in bundle["evidence_entries"])
    assert all(entry["authority_granted"] is False for entry in bundle["evidence_entries"])
    assert bundle["authority_denials"]["receipt_store_append_performed"] is False


def test_lifecycle_evidence_bundle_rejects_authority_drift(tmp_path: Path) -> None:
    bundle = json.loads(DEFAULT_BUNDLE_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(bundle)
    changed["authority_denials"]["receipt_store_append_performed"] = True

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleError,
        match="authority_denials.receipt_store_append_performed",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["bundle_is_not_lifecycle_authority"] is True
    assert changed["authority_denials"]["receipt_store_append_performed"] is True
    assert len(changed["evidence_entries"]) == 7


def test_lifecycle_evidence_bundle_rejects_missing_evidence_kind(tmp_path: Path) -> None:
    bundle = json.loads(DEFAULT_BUNDLE_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(bundle)
    changed["evidence_entries"] = [
        entry for entry in changed["evidence_entries"] if entry["evidence_kind"] != "revocation_request"
    ]
    changed["contract_summary"]["evidence_entry_count"] = len(changed["evidence_entries"])

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleError,
        match="revocation_request",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert len(changed["evidence_entries"]) == 6
    assert changed["contract_summary"]["evidence_entry_count"] == 6
    assert changed["authority_denials"]["terminal_closure_allowed"] is False


def test_lifecycle_evidence_bundle_rejects_placeholder_content_verified(tmp_path: Path) -> None:
    bundle = json.loads(DEFAULT_BUNDLE_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(bundle)
    changed["evidence_entries"][0]["placeholder_ref"] = True
    changed["evidence_entries"][0]["content_verified"] = True
    changed["contract_summary"]["placeholder_entry_count"] = 1

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleError,
        match="placeholder ref cannot be content verified",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["evidence_entries"][0]["evidence_kind"] == "active_grant_identity"
    assert changed["evidence_entries"][0]["authority_granted"] is False
    assert changed["contract_summary"]["placeholder_entry_count"] == 1


def test_lifecycle_evidence_bundle_rejects_scheme_content_verified(tmp_path: Path) -> None:
    bundle = json.loads(DEFAULT_BUNDLE_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(bundle)
    changed["evidence_entries"][0]["content_verified"] = True
    changed["contract_summary"]["content_verified_entry_count"] = 1

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleError,
        match="content verified requires local file ref",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["evidence_entries"][0]["local_file_ref"] is False
    assert changed["evidence_entries"][0]["structurally_verified"] is True
    assert changed["evidence_entries"][0]["authority_granted"] is False


def test_lifecycle_evidence_bundle_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    bundle = json.loads(DEFAULT_BUNDLE_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(bundle)
    changed["contract_summary"]["evidence_ref_count"] = 999

    with pytest.raises(
        UniversalSymbolReceiptStoreLifecycleEvidenceBundleError,
        match="evidence_ref_count drift",
    ):
        validate_universal_symbol_receipt_store_lifecycle_evidence_bundle(
            _write_case(tmp_path, changed),
            DEFAULT_SCHEMA_PATH,
        )

    assert changed["contract_summary"]["evidence_ref_count"] == 999
    assert len(changed["evidence_refs"]) == 10
    assert changed["authority_denials"]["raw_secret_stored"] is False
