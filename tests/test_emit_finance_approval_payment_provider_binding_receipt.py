"""Tests for finance payment-provider binding receipts.

Purpose: prove payment-provider credential presence is recorded without
serializing credential values.
Governance scope: finance payment binding, redacted receipts, schema
validation, provider scope, and strict CLI behavior.
Dependencies: scripts.emit_finance_approval_payment_provider_binding_receipt.
Invariants:
  - A provider-scoped or shared binding is sufficient for readiness.
  - Credential values never appear in the receipt.
  - Strict mode fails when no accepted provider binding is present.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_finance_approval_payment_provider_binding_receipt import (
    ACCEPTED_PAYMENT_PROVIDER_BINDING_NAMES,
    PROVIDER_BINDING_NAMES,
    emit_finance_approval_payment_provider_binding_receipt,
    main,
    write_finance_payment_provider_binding_receipt,
)


def test_payment_provider_binding_receipt_records_presence_without_values() -> None:
    receipt, errors = emit_finance_approval_payment_provider_binding_receipt(
        provider="stripe",
        env_reader=lambda name: "secret-provider-value" if name == "STRIPE_API_KEY" else "",
    )
    payload = receipt.as_dict()
    serialized = json.dumps(payload, sort_keys=True)

    assert errors == ()
    assert receipt.ready is True
    assert receipt.provider == "stripe"
    assert receipt.provider_binding_ref.startswith("provider-binding:stripe:")
    assert receipt.provider_binding_names == PROVIDER_BINDING_NAMES["stripe"]
    assert receipt.accepted_binding_names == ACCEPTED_PAYMENT_PROVIDER_BINDING_NAMES
    assert receipt.present_binding_names == ("STRIPE_API_KEY",)
    assert "secret-provider-value" not in serialized
    assert all(binding.value_serialized is False for binding in receipt.bindings)


def test_payment_provider_binding_receipt_allows_shared_connector_binding() -> None:
    receipt, errors = emit_finance_approval_payment_provider_binding_receipt(
        provider="bank_ach",
        env_reader=lambda name: "shared-secret-value" if name == "PAYMENT_PROVIDER_CONNECTOR_TOKEN" else "",
    )
    serialized = json.dumps(receipt.as_dict(), sort_keys=True)

    assert errors == ()
    assert receipt.ready is True
    assert receipt.provider == "bank_ach"
    assert receipt.present_binding_names == ("PAYMENT_PROVIDER_CONNECTOR_TOKEN",)
    assert "shared-secret-value" not in serialized


def test_payment_provider_binding_receipt_blocks_wrong_provider_binding() -> None:
    receipt, errors = emit_finance_approval_payment_provider_binding_receipt(
        provider="stripe",
        env_reader=lambda name: "bank-secret-value" if name == "BANK_ACH_CONNECTOR_TOKEN" else "",
    )
    serialized = json.dumps(receipt.as_dict(), sort_keys=True)

    assert errors == ()
    assert receipt.ready is False
    assert receipt.provider == "stripe"
    assert receipt.present_binding_names == ("BANK_ACH_CONNECTOR_TOKEN",)
    assert "bank-secret-value" not in serialized


def test_payment_provider_binding_receipt_writer_and_cli_strict(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    for env_name in ACCEPTED_PAYMENT_PROVIDER_BINDING_NAMES:
        monkeypatch.delenv(env_name, raising=False)
    output_path = tmp_path / "finance-payment-provider-binding.json"
    receipt, errors = emit_finance_approval_payment_provider_binding_receipt(
        provider="manual_bank_portal",
        env_reader=lambda name: "",
    )

    written = write_finance_payment_provider_binding_receipt(receipt, output_path)
    exit_code = main(["--provider", "manual_bank_portal", "--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert errors == ()
    assert written == output_path
    assert exit_code == 2
    assert payload["ready"] is False
    assert stdout_payload["ready"] is False
    assert payload["provider"] == "manual_bank_portal"
    assert payload["present_binding_names"] == []


def test_payment_provider_binding_receipt_schema_error_is_bounded(tmp_path: Path) -> None:
    schema_path = tmp_path / "secret-schema-path.json"

    receipt, errors = emit_finance_approval_payment_provider_binding_receipt(
        schema_path=schema_path,
        env_reader=lambda name: "",
    )
    serialized_errors = json.dumps(errors, sort_keys=True)

    assert receipt.ready is False
    assert "finance payment provider binding receipt schema could not be read" in errors
    assert "secret-schema-path" not in serialized_errors
