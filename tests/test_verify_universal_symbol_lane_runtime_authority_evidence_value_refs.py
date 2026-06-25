"""Tests for non-authorizing lane evidence value reference verification.

Purpose: prove lane runtime authority evidence value refs can be structurally
verified without granting lane authority, runtime admission, receipt append, or
terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lane evidence value producer, validator, and reference verifier.
Invariants:
  - Placeholder refs remain blocked.
  - Structurally verified refs keep ProofState Unknown.
  - Wrong schemes, secret-like refs, and local authority drift fail closed.
"""

from __future__ import annotations

import copy
import json
from contextlib import suppress
from pathlib import Path

import pytest

from scripts.produce_universal_symbol_lane_runtime_authority_evidence_value_receipt import (
    build_universal_symbol_lane_runtime_authority_evidence_value_receipt,
)
from scripts.validate_universal_symbol_lane_runtime_authority_evidence_value_receipt import (
    DEFAULT_RECEIPT_PATH,
    EVIDENCE_KINDS,
    LANES,
)
from scripts.verify_universal_symbol_lane_runtime_authority_evidence_value_refs import (
    UniversalSymbolLaneEvidenceValueRefVerificationError,
    verify_lane_evidence_value_refs,
)


def _write_receipt(tmp_path: Path, receipt: dict[str, object]) -> Path:
    receipt_path = tmp_path / "lane-evidence-values.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt_path


def _complete_refs() -> dict[str, str]:
    refs: dict[str, str] = {}
    for lane_ref in LANES:
        lane_key = lane_ref.split("://", 1)[1]
        refs[f"{lane_ref}|operator_approval"] = f"approval://{lane_key}/runtime-authority"
        refs[f"{lane_ref}|receipt_store_authority"] = f"receipt-store-authority://{lane_key}/runtime-authority"
        refs[f"{lane_ref}|recovery_evidence"] = f"recovery://{lane_key}/runtime-authority"
        refs[f"{lane_ref}|audit_receipt"] = f"audit://{lane_key}/runtime-authority"
        refs[f"{lane_ref}|live_runtime_witness"] = f"witness://{lane_key}/live-runtime"
        refs[f"{lane_ref}|blocked_action_refs"] = f"blocked://{lane_key}/runtime-authority-actions"
    return refs


def test_verifier_blocks_template_placeholder_refs() -> None:
    report = verify_lane_evidence_value_refs()

    assert report["valid"] is True
    assert report["status"] == "blocked_placeholder_or_missing_lane_evidence_values"
    assert len(report["placeholder_value_pairs"]) == len(LANES) * len(EVIDENCE_KINDS)
    assert report["verified_value_pairs"] == []
    assert report["proof_state_after_verification"] == "Unknown"
    assert report["lane_runtime_authority_allowed"] is False
    assert report["terminal_closure_allowed"] is False


def test_verifier_accepts_complete_refs_without_authority(tmp_path: Path) -> None:
    receipt = build_universal_symbol_lane_runtime_authority_evidence_value_receipt(_complete_refs())
    report = verify_lane_evidence_value_refs(receipt_path=_write_receipt(tmp_path, receipt))

    assert report["valid"] is True
    assert report["status"] == "all_refs_structurally_verified_non_authorizing"
    assert len(report["verified_value_pairs"]) == len(LANES) * len(EVIDENCE_KINDS)
    assert report["placeholder_value_pairs"] == []
    assert {item["content_verified"] for item in report["value_ref_reports"]} == {False}
    assert report["runtime_admission_allowed"] is False
    assert report["receipt_append_allowed"] is False
    assert report["terminal_closure_allowed"] is False


def test_verifier_rejects_wrong_scheme_for_evidence_kind(tmp_path: Path) -> None:
    refs = _complete_refs()
    refs["skill://software-dev|audit_receipt"] = "recovery://software-dev/wrong-kind"
    receipt = build_universal_symbol_lane_runtime_authority_evidence_value_receipt(refs)

    with pytest.raises(
        UniversalSymbolLaneEvidenceValueRefVerificationError,
        match="scheme does not match evidence kind",
    ):
        verify_lane_evidence_value_refs(receipt_path=_write_receipt(tmp_path, receipt))

    assert receipt["authority_denials"]["lane_runtime_authority_granted"] is False
    assert receipt["authority_denials"]["terminal_closure_allowed"] is False
    assert len(receipt["lane_value_items"]) == len(LANES) * len(EVIDENCE_KINDS)


def test_verifier_rejects_secret_like_ref(tmp_path: Path) -> None:
    receipt = json.loads(DEFAULT_RECEIPT_PATH.read_text(encoding="utf-8"))
    receipt["lane_value_items"][0]["supplied_evidence_ref"] = "approval://x/access_token/raw"

    with pytest.raises(
        UniversalSymbolLaneEvidenceValueRefVerificationError,
        match="raw secret-like evidence ref",
    ):
        verify_lane_evidence_value_refs(receipt_path=_write_receipt(tmp_path, receipt))

    assert receipt["authority_denials"]["raw_secret_stored"] is False
    assert receipt["lane_value_items"][0]["current_decision"] == "lane_runtime_authority_blocked"
    assert receipt["receipt_is_not_lane_authority"] is True


def test_verifier_accepts_matching_local_json_ref_without_authority(tmp_path: Path) -> None:
    local_ref = Path("tmp") / "lane-local-audit-evidence.json"
    local_ref.parent.mkdir(exist_ok=True)
    local_ref.write_text(
        json.dumps(
            {
                "receipt_id": "audit://skill/software-dev/runtime-authority/local-test",
                "evidence_kind": "audit_receipt",
                "authority_denials": {"audit_committed": False},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        refs = _complete_refs()
        refs["skill://software-dev|audit_receipt"] = local_ref.as_posix()
        receipt = build_universal_symbol_lane_runtime_authority_evidence_value_receipt(refs)
        report = verify_lane_evidence_value_refs(receipt_path=_write_receipt(tmp_path, receipt))
    finally:
        local_ref.unlink(missing_ok=True)
        with suppress(OSError):
            local_ref.parent.rmdir()

    local_report = [
        item
        for item in report["value_ref_reports"]
        if item["lane_ref"] == "skill://software-dev" and item["evidence_kind"] == "audit_receipt"
    ][0]
    assert local_report["local_file_ref"] is True
    assert local_report["content_verified"] is True
    assert report["lane_runtime_authority_allowed"] is False


def test_verifier_rejects_local_json_authority_drift(tmp_path: Path) -> None:
    local_ref = Path("tmp") / "lane-local-authority-drift.json"
    local_ref.parent.mkdir(exist_ok=True)
    local_ref.write_text(
        json.dumps(
            {
                "receipt_id": "audit://skill/software-dev/runtime-authority/local-test",
                "evidence_kind": "audit_receipt",
                "authority_denials": {"audit_committed": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        refs = _complete_refs()
        refs["skill://software-dev|audit_receipt"] = local_ref.as_posix()
        receipt = build_universal_symbol_lane_runtime_authority_evidence_value_receipt(refs)
        with pytest.raises(
            UniversalSymbolLaneEvidenceValueRefVerificationError,
            match="local evidence authority denial drift",
        ):
            verify_lane_evidence_value_refs(receipt_path=_write_receipt(tmp_path, receipt))
    finally:
        local_ref.unlink(missing_ok=True)
        with suppress(OSError):
            local_ref.parent.rmdir()

    assert local_ref.exists() is False
    assert refs["skill://software-dev|audit_receipt"].endswith("lane-local-authority-drift.json")
    assert len(refs) == len(LANES) * len(EVIDENCE_KINDS)
