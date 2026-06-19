"""Purpose: verify no-effect production of runtime live witness input receipts.

Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime live witness input receipt producer and validator.
Invariants: generated receipts remain Foundation Mode blocked receipts and do
not grant runtime authority.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.produce_universal_symbol_runtime_live_witness_input_receipt import (
    DEFAULT_INPUT_REFS,
    REPO_ROOT,
    UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError,
    build_universal_symbol_runtime_live_witness_input_receipt,
    validate_runtime_live_witness_input_receipt_object,
)


def _channels_by_kind(receipt: dict[str, object]) -> dict[str, dict[str, object]]:
    channels = receipt["required_input_channels"]
    assert isinstance(channels, list)
    return {
        str(channel["input_kind"]): channel
        for channel in channels
        if isinstance(channel, dict)
    }


def test_producer_builds_foundation_receipt_without_authority() -> None:
    receipt = build_universal_symbol_runtime_live_witness_input_receipt()
    channels = _channels_by_kind(receipt)
    denials = receipt["authority_denials"]

    assert receipt["foundation_mode"] is True
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["receipt_is_not_runtime_authority"] is True
    assert len(channels) == 8
    assert all(channel["proof_state"] == "Unknown" for channel in channels.values())
    assert all(channel["current_decision"] == "live_runtime_witness_blocked" for channel in channels.values())
    assert isinstance(denials, dict)
    assert len(denials) == 12
    assert all(value is False for value in denials.values())
    assert validate_runtime_live_witness_input_receipt_object(receipt) == []


def test_producer_accepts_reference_overrides_without_accepting_live_witness() -> None:
    receipt = build_universal_symbol_runtime_live_witness_input_receipt(
        {
            "runtime_endpoint": "input://operator/runtime-endpoint-capture-20260619",
            "operator_observation": "input://operator/runtime-observation-20260619",
            "freshness_window": "input://runtime/freshness-window-300s",
        }
    )
    channels = _channels_by_kind(receipt)
    denials = receipt["authority_denials"]

    assert channels["runtime_endpoint"]["required_input_ref"] == "input://operator/runtime-endpoint-capture-20260619"
    assert channels["operator_observation"]["required_input_ref"] == "input://operator/runtime-observation-20260619"
    assert channels["freshness_window"]["required_input_ref"] == "input://runtime/freshness-window-300s"
    assert channels["runtime_endpoint"]["proof_state"] == "Unknown"
    assert channels["operator_observation"]["current_decision"] == "live_runtime_witness_blocked"
    assert isinstance(denials, dict)
    assert denials["live_runtime_witness_accepted"] is False
    assert denials["runtime_admission_granted"] is False
    assert denials["terminal_closure_allowed"] is False


def test_producer_rejects_empty_or_unknown_input_refs() -> None:
    with pytest.raises(UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError):
        build_universal_symbol_runtime_live_witness_input_receipt({"runtime_endpoint": " "})

    with pytest.raises(UniversalSymbolRuntimeLiveWitnessInputReceiptProductionError):
        build_universal_symbol_runtime_live_witness_input_receipt({"unregistered_input": "input://x"})

    receipt = build_universal_symbol_runtime_live_witness_input_receipt(DEFAULT_INPUT_REFS)
    assert receipt["contract_summary"]["input_channel_count"] == 8
    assert receipt["contract_summary"]["authority_denial_count"] == 12
    assert receipt["contract_summary"]["evidence_ref_count"] == len(receipt["evidence_refs"])


def test_cli_stdout_receipt_validates_without_writing() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/produce_universal_symbol_runtime_live_witness_input_receipt.py",
            "--runtime-health-probe-ref",
            "input://operator/no-effect-health-probe-capture",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    receipt = json.loads(result.stdout)
    channels = _channels_by_kind(receipt)

    assert channels["runtime_health_probe"]["required_input_ref"] == "input://operator/no-effect-health-probe-capture"
    assert channels["runtime_health_probe"]["proof_state"] == "Unknown"
    assert receipt["authority_denials"]["connector_call_enabled"] is False
    assert validate_runtime_live_witness_input_receipt_object(receipt) == []


def test_cli_output_write_reports_bounded_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "runtime-live-witness-input-receipt.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/produce_universal_symbol_runtime_live_witness_input_receipt.py",
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
    assert report["input_channel_count"] == 8
    assert report["authority_denial_count"] == 12
    assert receipt["receipt_is_not_runtime_authority"] is True
    assert receipt["authority_denials"]["receipt_store_append_enabled"] is False
