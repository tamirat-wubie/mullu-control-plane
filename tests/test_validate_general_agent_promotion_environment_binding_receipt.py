"""Tests for redacted environment binding receipt validation."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_general_agent_promotion_environment_binding_receipt import (
    emit_general_agent_promotion_environment_binding_receipt,
    write_environment_binding_receipt,
)
from scripts.validate_general_agent_promotion_environment_binding_receipt import (
    main,
    validate_general_agent_promotion_environment_binding_receipt,
)


REQUIRED_ENV = {
    "MULLU_BROWSER_SANDBOX_EVIDENCE",
    "MULLU_VOICE_PROBE_AUDIO",
    "MULLU_GATEWAY_URL",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_AUTHORITY_OPERATOR_SECRET",
}


def test_validate_environment_binding_receipt_accepts_ready_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding-receipt.json"
    receipt, emit_errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )
    write_environment_binding_receipt(receipt, receipt_path)

    result = validate_general_agent_promotion_environment_binding_receipt(receipt_path=receipt_path)

    assert emit_errors == ()
    assert result.valid is True
    assert result.ready is True
    assert result.binding_count == 6
    assert result.missing_bindings == ()


def test_validate_environment_binding_receipt_allows_blocked_non_strict_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding-receipt.json"
    receipt, emit_errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: "",
    )
    write_environment_binding_receipt(receipt, receipt_path)

    result = validate_general_agent_promotion_environment_binding_receipt(receipt_path=receipt_path)

    assert emit_errors == ()
    assert result.valid is True
    assert result.ready is False
    assert result.binding_count == 6
    assert "MULLU_GATEWAY_URL" in result.missing_bindings


def test_validate_environment_binding_receipt_require_ready_blocks_missing(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding-receipt.json"
    receipt, emit_errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: "",
    )
    write_environment_binding_receipt(receipt, receipt_path)

    result = validate_general_agent_promotion_environment_binding_receipt(
        receipt_path=receipt_path,
        require_ready=True,
    )

    assert emit_errors == ()
    assert result.valid is False
    assert result.ready is False
    assert any("ready must be true" in error for error in result.errors)


def test_validate_environment_binding_receipt_rejects_value_serialization(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding-receipt.json"
    receipt, emit_errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )
    payload = receipt.as_dict()
    payload["bindings"][0]["value_serialized"] = True
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_environment_binding_receipt(receipt_path=receipt_path)

    assert emit_errors == ()
    assert result.valid is False
    assert any("value_serialized" in error for error in result.errors)


def test_validate_environment_binding_receipt_cli_outputs_json(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "binding-receipt.json"
    receipt, emit_errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )
    write_environment_binding_receipt(receipt, receipt_path)

    exit_code = main(["--receipt", str(receipt_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert emit_errors == ()
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert payload["binding_count"] == 6
