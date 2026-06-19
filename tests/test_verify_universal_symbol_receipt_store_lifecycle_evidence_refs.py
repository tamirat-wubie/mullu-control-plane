"""Tests for non-authorizing lifecycle evidence reference verification.

Purpose: prove lifecycle evidence references can be structurally verified
without recording lifecycle state or granting runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lifecycle evidence producer and reference verifier.
Invariants:
  - Placeholder refs remain blocked.
  - Structurally verified refs keep ProofState Unknown.
  - Authority drift, missing local files, and secret-like refs fail closed.
"""

from __future__ import annotations

import copy
import json
from contextlib import suppress
from pathlib import Path

import pytest

from scripts.produce_universal_symbol_receipt_store_lifecycle_evidence_receipt import (
    EVIDENCE_KINDS,
    produce_lifecycle_evidence_receipt,
)
from scripts.validate_universal_symbol_receipt_store_lifecycle_evidence_receipt import DEFAULT_RECEIPT_PATH
from scripts.verify_universal_symbol_receipt_store_lifecycle_evidence_refs import (
    UniversalSymbolLifecycleEvidenceRefVerificationError,
    verify_lifecycle_evidence_refs,
)


def _write_receipt(tmp_path: Path, receipt: dict[str, object]) -> Path:
    receipt_path = tmp_path / "lifecycle-evidence.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt_path


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


def test_verifier_accepts_complete_refs_without_authority(tmp_path: Path) -> None:
    receipt_path = tmp_path / "lifecycle-evidence.json"
    produce_lifecycle_evidence_receipt(
        evidence_refs=_complete_refs(),
        output_path=receipt_path,
        clock=lambda: "2026-06-19T00:00:00Z",
    )

    report = verify_lifecycle_evidence_refs(receipt_path=receipt_path)

    assert report["valid"] is True
    assert report["status"] == "all_refs_structurally_verified_non_authorizing"
    assert set(report["verified_evidence_kinds"]) == set(EVIDENCE_KINDS)
    assert report["placeholder_evidence_kinds"] == []
    assert {item["content_verified"] for item in report["evidence_ref_reports"]} == {False}
    assert report["proof_state_after_verification"] == "Unknown"
    assert report["lifecycle_recording_allowed"] is False
    assert report["authority_granted"] is False


def test_verifier_blocks_template_placeholder_refs() -> None:
    report = verify_lifecycle_evidence_refs()

    assert report["valid"] is True
    assert report["status"] == "blocked_placeholder_or_missing_lifecycle_evidence"
    assert set(report["placeholder_evidence_kinds"]) == set(EVIDENCE_KINDS)
    assert report["verified_evidence_kinds"] == []
    assert report["authority_granted"] is False


def test_verifier_rejects_missing_repository_relative_ref(tmp_path: Path) -> None:
    result = produce_lifecycle_evidence_receipt(
        evidence_refs=_complete_refs(),
        output_path=tmp_path / "lifecycle-evidence.json",
    )
    receipt = copy.deepcopy(result["receipt"])
    receipt["required_live_evidence"][0]["required_evidence_ref"] = "missing/evidence.json"

    with pytest.raises(
        UniversalSymbolLifecycleEvidenceRefVerificationError,
        match="repository-relative evidence ref missing",
    ):
        verify_lifecycle_evidence_refs(receipt_path=_write_receipt(tmp_path, receipt))

    assert receipt["authority_denials"]["receipt_store_append_performed"] is False
    assert len(receipt["required_live_evidence"]) == 7
    assert receipt["required_live_evidence"][0]["proof_state"] == "Unknown"


def test_verifier_rejects_authority_drift(tmp_path: Path) -> None:
    receipt = json.loads(DEFAULT_RECEIPT_PATH.read_text(encoding="utf-8"))
    receipt["authority_denials"]["receipt_store_append_performed"] = True

    with pytest.raises(Exception, match="authority_denials.receipt_store_append_performed"):
        verify_lifecycle_evidence_refs(receipt_path=_write_receipt(tmp_path, receipt))

    assert receipt["lifecycle_evidence_receipt_is_not_lifecycle_authority"] is True
    assert receipt["authority_denials"]["receipt_store_append_performed"] is True
    assert len(receipt["required_live_evidence"]) == 7


def test_verifier_rejects_secret_like_ref(tmp_path: Path) -> None:
    result = produce_lifecycle_evidence_receipt(
        evidence_refs=_complete_refs(),
        output_path=tmp_path / "lifecycle-evidence.json",
    )
    receipt = copy.deepcopy(result["receipt"])
    receipt["required_live_evidence"][0]["required_evidence_ref"] = "access_token://raw-secret-marker"

    with pytest.raises(
        UniversalSymbolLifecycleEvidenceRefVerificationError,
        match="raw secret-like evidence ref",
    ):
        verify_lifecycle_evidence_refs(receipt_path=_write_receipt(tmp_path, receipt))

    assert receipt["authority_denials"]["raw_secret_stored"] is False
    assert receipt["required_live_evidence"][0]["current_decision"] == "lifecycle_recording_blocked"
    assert len(_complete_refs()) == 7


def test_verifier_rejects_wrong_scheme_for_evidence_kind(tmp_path: Path) -> None:
    result = produce_lifecycle_evidence_receipt(
        evidence_refs=_complete_refs(),
        output_path=tmp_path / "lifecycle-evidence.json",
    )
    receipt = copy.deepcopy(result["receipt"])
    receipt["required_live_evidence"][2]["required_evidence_ref"] = "revocation://wrong-kind"

    with pytest.raises(
        UniversalSymbolLifecycleEvidenceRefVerificationError,
        match="scheme does not match evidence kind",
    ):
        verify_lifecycle_evidence_refs(receipt_path=_write_receipt(tmp_path, receipt))

    assert receipt["required_live_evidence"][2]["evidence_kind"] == "expiry_evidence"
    assert receipt["authority_denials"]["state_mutation_performed"] is False
    assert len(receipt["required_live_evidence"]) == 7


def test_verifier_accepts_matching_local_json_ref_without_authority(tmp_path: Path) -> None:
    local_ref = Path("tmp") / "lifecycle-local-replacement-evidence.json"
    local_ref.parent.mkdir(exist_ok=True)
    local_ref.write_text(
        json.dumps(
            {
                "receipt_id": "receipt://universal-symbol/replacement-decision/local-test",
                "evidence_kind": "replacement_decision",
                "authority_denials": {"replacement_decision_recorded": False},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        refs = _complete_refs()
        refs["replacement_decision"] = local_ref.as_posix()
        receipt_path = tmp_path / "lifecycle-evidence.json"
        produce_lifecycle_evidence_receipt(evidence_refs=refs, output_path=receipt_path)

        report = verify_lifecycle_evidence_refs(receipt_path=receipt_path)
    finally:
        local_ref.unlink(missing_ok=True)
        with suppress(OSError):
            local_ref.parent.rmdir()

    replacement_report = [
        item for item in report["evidence_ref_reports"] if item["evidence_kind"] == "replacement_decision"
    ][0]
    assert replacement_report["local_file_ref"] is True
    assert replacement_report["content_verified"] is True
    assert report["authority_granted"] is False


def test_verifier_rejects_local_json_authority_drift(tmp_path: Path) -> None:
    local_ref = Path("tmp") / "lifecycle-local-audit-evidence.json"
    local_ref.parent.mkdir(exist_ok=True)
    local_ref.write_text(
        json.dumps(
            {
                "receipt_id": "receipt://universal-symbol/lifecycle-audit/local-test",
                "evidence_kind": "lifecycle_audit_receipt",
                "authority_denials": {"lifecycle_audit_committed": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        refs = _complete_refs()
        refs["lifecycle_audit_receipt"] = local_ref.as_posix()
        result = produce_lifecycle_evidence_receipt(
            evidence_refs=refs,
            output_path=tmp_path / "lifecycle-evidence.json",
        )
        with pytest.raises(
            UniversalSymbolLifecycleEvidenceRefVerificationError,
            match="local evidence authority denial drift",
        ):
            verify_lifecycle_evidence_refs(receipt_path=_write_receipt(tmp_path, result["receipt"]))
    finally:
        local_ref.unlink(missing_ok=True)
        with suppress(OSError):
            local_ref.parent.rmdir()

    assert local_ref.exists() is False
    assert refs["lifecycle_audit_receipt"].endswith("lifecycle-local-audit-evidence.json")
    assert len(refs) == 7
