"""Tests for provider credential binding receipt validation.

Purpose: prove provider credential binding receipt validation is redacted,
strict, and readiness-aware.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.bind_general_agent_provider_credentials and
scripts.validate_general_agent_provider_credential_binding_receipt.
Invariants:
  - Secret-shaped values are rejected before JSON interpretation.
  - Missing credentials remain explicit blockers.
  - Require-ready mode fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.bind_general_agent_provider_credentials import (
    bind_general_agent_provider_credentials,
    write_provider_credential_binding_receipt,
)
from scripts.validate_general_agent_provider_credential_binding_receipt import (
    main,
    validate_general_agent_provider_credential_binding_receipt,
)


def test_validate_provider_credential_receipt_accepts_ready_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "provider-binding.json"
    receipt = bind_general_agent_provider_credentials(
        env_reader=lambda _name: "plain-token",
        checked_at="2026-07-02T00:00:00+00:00",
    )
    write_provider_credential_binding_receipt(receipt, receipt_path)

    result = validate_general_agent_provider_credential_binding_receipt(receipt_path=receipt_path)

    assert result.valid is True
    assert result.ready is True
    assert result.binding_count == 2
    assert result.missing_credentials == ()
    assert result.receipt_path == "provider-binding.json"


def test_validate_provider_credential_receipt_allows_blocked_non_strict_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "provider-binding.json"
    receipt = bind_general_agent_provider_credentials(
        env_reader=lambda _name: "",
        checked_at="2026-07-02T00:00:00+00:00",
    )
    write_provider_credential_binding_receipt(receipt, receipt_path)

    result = validate_general_agent_provider_credential_binding_receipt(receipt_path=receipt_path)

    assert result.valid is True
    assert result.ready is False
    assert result.binding_count == 2
    assert "OPENAI_API_KEY" in result.missing_credentials
    assert "EMAIL_CALENDAR_CONNECTOR_TOKEN" in result.missing_credentials


def test_validate_provider_credential_receipt_require_ready_blocks_missing(tmp_path: Path) -> None:
    receipt_path = tmp_path / "provider-binding.json"
    receipt = bind_general_agent_provider_credentials(
        env_reader=lambda _name: "",
        checked_at="2026-07-02T00:00:00+00:00",
    )
    write_provider_credential_binding_receipt(receipt, receipt_path)

    result = validate_general_agent_provider_credential_binding_receipt(
        receipt_path=receipt_path,
        require_ready=True,
    )

    assert result.valid is False
    assert result.ready is False
    assert "receipt ready must be true" in result.errors


def test_validate_provider_credential_receipt_rejects_value_serialization(tmp_path: Path) -> None:
    receipt_path = tmp_path / "provider-binding.json"
    receipt = bind_general_agent_provider_credentials(
        env_reader=lambda _name: "plain-token",
        checked_at="2026-07-02T00:00:00+00:00",
    )
    payload = receipt.as_dict()
    payload["bindings"][0]["value_serialized"] = True
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_provider_credential_binding_receipt(receipt_path=receipt_path)

    assert result.valid is False
    assert result.ready is True
    assert any("value_serialized" in error for error in result.errors)
    assert "plain-token" not in json.dumps(result.as_dict(), sort_keys=True)


def test_validate_provider_credential_receipt_rejects_secret_shaped_material(tmp_path: Path) -> None:
    receipt_path = tmp_path / "provider-binding.json"
    receipt_path.write_text(
        '{"receipt_id": "general-agent-provider-credential-binding-receipt-v1", "leak": "sk-secret"}',
        encoding="utf-8",
    )

    result = validate_general_agent_provider_credential_binding_receipt(receipt_path=receipt_path)
    serialized_result = json.dumps(result.as_dict(), sort_keys=True)

    assert result.valid is False
    assert result.ready is False
    assert any("prohibited secret-shaped material" in error for error in result.errors)
    assert "sk-secret" not in serialized_result


def test_validate_provider_credential_receipt_rejects_inconsistent_missing_set(tmp_path: Path) -> None:
    receipt_path = tmp_path / "provider-binding.json"
    receipt = bind_general_agent_provider_credentials(
        env_reader=lambda name: "plain-token" if name == "OPENAI_API_KEY" else "",
        checked_at="2026-07-02T00:00:00+00:00",
    )
    payload = receipt.as_dict()
    payload["missing_credentials"] = []
    payload["ready"] = True
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_provider_credential_binding_receipt(receipt_path=receipt_path)

    assert result.valid is False
    assert result.ready is True
    assert any("missing_credentials must match" in error for error in result.errors)
    assert any("ready must be False" in error for error in result.errors)


def test_validate_provider_credential_receipt_cli_outputs_json(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "provider-binding.json"
    receipt = bind_general_agent_provider_credentials(
        env_reader=lambda _name: "plain-token",
        checked_at="2026-07-02T00:00:00+00:00",
    )
    write_provider_credential_binding_receipt(receipt, receipt_path)

    exit_code = main(["--receipt", str(receipt_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert payload["binding_count"] == 2
    assert str(tmp_path) not in json.dumps(payload, sort_keys=True)


def test_validate_provider_credential_receipt_missing_file_error_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "secret-path-provider-binding.json"

    result = validate_general_agent_provider_credential_binding_receipt(receipt_path=receipt_path)
    serialized = json.dumps(result.as_dict(), sort_keys=True)

    assert result.valid is False
    assert result.receipt_path == "secret-path-provider-binding.json"
    assert "provider credential binding receipt could not be read" in result.errors
    assert str(tmp_path) not in serialized
    assert "secret-path-provider-binding" not in json.dumps(result.errors, sort_keys=True)


def test_validate_provider_credential_receipt_rejects_nonfinite_json_constants(tmp_path: Path) -> None:
    receipt_path = tmp_path / "provider-binding.json"
    receipt_path.write_text(
        '{"receipt_id": "general-agent-provider-credential-binding-receipt-v1", "score": Infinity}',
        encoding="utf-8",
    )

    result = validate_general_agent_provider_credential_binding_receipt(receipt_path=receipt_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "provider credential binding receipt must be JSON" in result.errors
    assert "Infinity" not in serialized_errors
