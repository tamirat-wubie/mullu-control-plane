"""Tests for redacted general-agent promotion environment binding receipts.

Purpose: prove operator environment presence receipts never serialize secret
values and fail closed when bindings are absent.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.emit_general_agent_promotion_environment_binding_receipt.
Invariants:
  - Receipt entries record name and presence only.
  - Strict CLI emission fails while required bindings are absent.
  - Written receipts remain schema-compatible and redacted.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_general_agent_promotion_environment_binding_receipt import (
    emit_general_agent_promotion_environment_binding_receipt,
    main,
    write_environment_binding_receipt,
)


REQUIRED_ENV = {
    "MULLU_BROWSER_SANDBOX_EVIDENCE",
    "MULLU_VOICE_PROBE_AUDIO",
    "MULLU_GATEWAY_URL",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_AUTHORITY_OPERATOR_SECRET",
}


def test_environment_binding_receipt_records_presence_without_values() -> None:
    receipt, errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: f"secret-value-for-{name}" if name in REQUIRED_ENV else "",
    )
    payload = receipt.as_dict()
    serialized = json.dumps(payload)

    assert errors == ()
    assert receipt.ready is True
    assert receipt.binding_count == 6
    assert receipt.missing_bindings == ()
    assert all(binding.present for binding in receipt.bindings)
    assert all(binding.value_serialized is False for binding in receipt.bindings)
    assert "secret-value-for-" not in serialized


def test_environment_binding_receipt_blocks_missing_bindings() -> None:
    receipt, errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: "present" if name == "MULLU_GATEWAY_URL" else "",
    )

    assert errors == ()
    assert receipt.ready is False
    assert receipt.binding_count == 6
    assert "MULLU_GATEWAY_URL" not in receipt.missing_bindings
    assert "MULLU_RUNTIME_WITNESS_SECRET" in receipt.missing_bindings
    assert sum(1 for binding in receipt.bindings if binding.present) == 1


def test_environment_binding_receipt_writer_and_cli_strict(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    for env_name in REQUIRED_ENV:
        monkeypatch.delenv(env_name, raising=False)
    output_path = tmp_path / "binding-receipt.json"
    receipt, errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: "",
    )

    written = write_environment_binding_receipt(receipt, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert errors == ()
    assert written == output_path
    assert exit_code == 2
    assert payload["ready"] is False
    assert stdout_payload["ready"] is False
    assert "MULLU_AUTHORITY_OPERATOR_SECRET" in payload["missing_bindings"]


def test_environment_binding_receipt_missing_contract_error_is_bounded(tmp_path: Path) -> None:
    contract_path = tmp_path / "secret-contract-path.json"

    receipt, errors = emit_general_agent_promotion_environment_binding_receipt(
        contract_path=contract_path,
    )
    serialized_errors = json.dumps(errors, sort_keys=True)

    assert receipt.ready is False
    assert "environment binding contract could not be read" in errors
    assert "secret-contract-path" not in serialized_errors


def test_environment_binding_receipt_contract_json_error_is_bounded(tmp_path: Path) -> None:
    contract_path = tmp_path / "environment-bindings.json"
    contract_path.write_text('{"contract_id": "secret-json-token"', encoding="utf-8")

    receipt, errors = emit_general_agent_promotion_environment_binding_receipt(
        contract_path=contract_path,
    )
    serialized_errors = json.dumps(errors, sort_keys=True)

    assert receipt.ready is False
    assert "environment binding contract must be JSON" in errors
    assert "secret-json-token" not in serialized_errors
