"""Tests for Universal Symbol lifecycle evidence receipt production.

Purpose: prove lifecycle evidence reference intake can collect refs or fail
closed without granting receipt-store lifecycle authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.produce_universal_symbol_receipt_store_lifecycle_evidence_receipt.
Invariants:
  - Collected references do not change ProofState to Pass.
  - Missing references keep lifecycle recording blocked.
  - Raw secret-like material is rejected before receipt write.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.produce_universal_symbol_receipt_store_lifecycle_evidence_receipt import (
    EVIDENCE_KINDS,
    UniversalSymbolLifecycleEvidenceProducerError,
    produce_lifecycle_evidence_receipt,
)


def _complete_refs() -> dict[str, str]:
    return {
        evidence_kind: f"evidence://universal-symbol/lifecycle/{evidence_kind}"
        for evidence_kind in EVIDENCE_KINDS
    }


def test_lifecycle_evidence_producer_collects_refs_without_authority(tmp_path: Path) -> None:
    output_path = tmp_path / "lifecycle-evidence.json"

    result = produce_lifecycle_evidence_receipt(
        evidence_refs=_complete_refs(),
        output_path=output_path,
        clock=lambda: "2026-06-18T00:00:00Z",
    )
    receipt = result["receipt"]

    assert result["admission_report"]["status"] == "collected_non_authorizing"
    assert result["admission_report"]["missing_evidence_kinds"] == []
    assert result["validation"]["valid"] is True
    assert output_path.exists()
    assert {item["proof_state"] for item in receipt["required_live_evidence"]} == {"Unknown"}
    assert {item["current_decision"] for item in receipt["required_live_evidence"]} == {
        "lifecycle_recording_blocked"
    }
    assert all(value is False for value in receipt["authority_denials"].values())
    assert "scripts/produce_universal_symbol_receipt_store_lifecycle_evidence_receipt.py" in receipt["evidence_refs"]


def test_lifecycle_evidence_producer_reports_missing_refs(tmp_path: Path) -> None:
    partial_refs = {
        "active_grant_identity": "grant://universal-symbol/receipt-store/live-active-approval",
        "reapproval_window": "temporal://universal-symbol/receipt-store/live-reapproval-window",
    }

    result = produce_lifecycle_evidence_receipt(
        evidence_refs=partial_refs,
        output_path=tmp_path / "lifecycle-evidence.json",
    )
    receipt = result["receipt"]

    assert result["admission_report"]["status"] == "blocked_missing_live_evidence"
    assert result["admission_report"]["collected_evidence_kinds"] == ["active_grant_identity", "reapproval_window"]
    assert "expiry_evidence" in result["admission_report"]["missing_evidence_kinds"]
    assert result["validation"]["solver_outcome"] == "AwaitingEvidence"
    assert receipt["required_live_evidence"][0]["required_evidence_ref"] == partial_refs["active_grant_identity"]
    assert receipt["required_live_evidence"][1]["required_evidence_ref"] == partial_refs["reapproval_window"]
    assert receipt["lifecycle_evidence_receipt_is_not_lifecycle_authority"] is True
    assert receipt["authority_denials"]["receipt_store_append_performed"] is False


def test_lifecycle_evidence_producer_rejects_unknown_evidence_kind(tmp_path: Path) -> None:
    output_path = tmp_path / "lifecycle-evidence.json"

    with pytest.raises(
        UniversalSymbolLifecycleEvidenceProducerError,
        match="unknown lifecycle evidence kinds",
    ):
        produce_lifecycle_evidence_receipt(
            evidence_refs={"unregistered_kind": "evidence://universal-symbol/lifecycle/unregistered"},
            output_path=output_path,
        )

    assert output_path.exists() is False
    assert len(EVIDENCE_KINDS) == 7
    assert "active_grant_identity" in EVIDENCE_KINDS


def test_lifecycle_evidence_producer_rejects_raw_secret_like_ref(tmp_path: Path) -> None:
    output_path = tmp_path / "lifecycle-evidence.json"

    with pytest.raises(
        UniversalSymbolLifecycleEvidenceProducerError,
        match="raw secret-like material",
    ):
        produce_lifecycle_evidence_receipt(
            evidence_refs={"active_grant_identity": "access_token=raw-secret-value"},
            output_path=output_path,
        )

    assert output_path.exists() is False
    assert len(_complete_refs()) == 7
    assert _complete_refs()["replacement_decision"].startswith("evidence://")
