"""Test non-authorizing production of lane runtime authority evidence values.

Purpose: verify generated lane evidence value receipts stay ref-only and
blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lane evidence value producer and validator.
Invariants: generated receipts do not grant lane authority, runtime admission,
dispatch, append, mutation, or terminal closure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.produce_universal_symbol_lane_runtime_authority_evidence_value_receipt import (
    REPO_ROOT,
    UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError,
    build_universal_symbol_lane_runtime_authority_evidence_value_receipt,
)
from scripts.validate_universal_symbol_lane_runtime_authority_evidence_value_receipt import (
    validate_lane_runtime_authority_evidence_value_receipt_object,
)


def _items_by_key(receipt: dict[str, object]) -> dict[str, dict[str, object]]:
    items = receipt["lane_value_items"]
    assert isinstance(items, list)
    return {
        f"{item['lane_ref']}|{item['evidence_kind']}": item
        for item in items
        if isinstance(item, dict)
    }


def test_lane_value_producer_builds_ref_only_blocked_receipt() -> None:
    receipt = build_universal_symbol_lane_runtime_authority_evidence_value_receipt()
    items = _items_by_key(receipt)
    denials = receipt["authority_denials"]

    assert receipt["foundation_mode"] is True
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["receipt_is_not_lane_authority"] is True
    assert len(items) == 24
    assert all(item["proof_state"] == "Unknown" for item in items.values())
    assert all(item["value_state"] == "operator_reference_recorded_not_verified" for item in items.values())
    assert all(item["current_decision"] == "lane_runtime_authority_blocked" for item in items.values())
    assert isinstance(denials, dict)
    assert len(denials) == 13
    assert all(value is False for value in denials.values())
    assert validate_lane_runtime_authority_evidence_value_receipt_object(receipt) == []


def test_lane_value_producer_accepts_ref_overrides_without_authority() -> None:
    key = "skill://software-dev|operator_approval"
    receipt = build_universal_symbol_lane_runtime_authority_evidence_value_receipt(
        {key: "input://operator/software-dev-approval-20260619"}
    )
    items = _items_by_key(receipt)
    denials = receipt["authority_denials"]

    assert items[key]["supplied_evidence_ref"] == "input://operator/software-dev-approval-20260619"
    assert items[key]["proof_state"] == "Unknown"
    assert items[key]["current_decision"] == "lane_runtime_authority_blocked"
    assert isinstance(denials, dict)
    assert denials["lane_runtime_authority_granted"] is False
    assert denials["runtime_admission_granted"] is False
    assert denials["terminal_closure_allowed"] is False


def test_lane_value_producer_rejects_unknown_empty_or_secret_refs() -> None:
    with pytest.raises(UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError):
        build_universal_symbol_lane_runtime_authority_evidence_value_receipt({"unknown|operator_approval": "input://x"})

    with pytest.raises(UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError):
        build_universal_symbol_lane_runtime_authority_evidence_value_receipt(
            {"skill://software-dev|operator_approval": " "}
        )

    with pytest.raises(UniversalSymbolLaneRuntimeAuthorityEvidenceValueProductionError):
        build_universal_symbol_lane_runtime_authority_evidence_value_receipt(
            {"skill://software-dev|operator_approval": "token=raw-secret"}
        )


def test_lane_value_cli_stdout_receipt_validates() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/produce_universal_symbol_lane_runtime_authority_evidence_value_receipt.py",
            "--value-ref",
            "receipt://worker-ledger|audit_receipt=input://operator/worker-ledger-audit",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    receipt = json.loads(result.stdout)
    items = _items_by_key(receipt)

    assert items["receipt://worker-ledger|audit_receipt"]["supplied_evidence_ref"] == (
        "input://operator/worker-ledger-audit"
    )
    assert items["receipt://worker-ledger|audit_receipt"]["proof_state"] == "Unknown"
    assert receipt["authority_denials"]["receipt_store_append_enabled"] is False
    assert validate_lane_runtime_authority_evidence_value_receipt_object(receipt) == []


def test_lane_value_cli_output_write_reports_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "lane-runtime-authority-evidence-values.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/produce_universal_symbol_lane_runtime_authority_evidence_value_receipt.py",
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    receipt = json.loads(output_path.read_text(encoding="utf-8"))

    assert report["valid"] is True
    assert report["lane_count"] == 4
    assert report["evidence_value_item_count"] == 24
    assert report["authority_denial_count"] == 13
    assert receipt["receipt_is_not_lane_authority"] is True
