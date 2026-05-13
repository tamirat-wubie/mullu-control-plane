"""Tests for finance payment closure receipt validation.

Purpose: prove finance payment closure promotion requires provider receipt and
ledger reconciliation evidence bound to the same approval-controlled effect.
Governance scope: payment adapter evidence, approval-bound external write,
schema validation, and strict readiness gating.
Dependencies: scripts.validate_finance_approval_payment_closure_receipt.
Invariants:
  - Passed payment closure receipts are ready only when provider and ledger match.
  - Failed receipts remain valid blocked evidence in non-strict validation.
  - Unapproved writes, ledger drift, and raw response fields fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_finance_approval_payment_closure_receipt import (
    main,
    validate_finance_approval_payment_closure_receipt,
)


def test_validate_payment_closure_receipt_accepts_bound_provider_and_ledger(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    result = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path, require_ready=True)

    assert result.valid is True
    assert result.ready is True
    assert result.adapter_id == "finance.payment_adapter"
    assert result.status == "passed"
    assert result.verification_status == "passed"
    assert result.effect_type == "payment_sent_with_approval"
    assert result.capability_id == "payment.execute.with_approval"
    assert result.external_write is True
    assert result.approved_external_write is True
    assert result.payment_provider_receipt_ref == "provider:payment:receipt-001"
    assert result.ledger_reconciliation_ref == "ledger:reconciliation:receipt-001"
    assert result.blockers == ()


def test_validate_payment_closure_receipt_allows_blocked_failed_probe(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    payload = _ready_receipt() | {
        "status": "failed",
        "verification_status": "failed",
        "external_write": False,
        "approved_external_write": False,
        "payment_provider_receipt_ref": "",
        "ledger_reconciliation_ref": "",
        "blockers": ["adapter_receipt_missing"],
    }
    payload.pop("provider_receipt")
    payload.pop("ledger_reconciliation")
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)

    assert result.valid is True
    assert result.ready is False
    assert result.status == "failed"
    assert result.verification_status == "failed"
    assert result.blockers == ("adapter_receipt_missing",)


def test_validate_payment_closure_receipt_require_ready_blocks_failed_probe(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    payload = _ready_receipt() | {
        "status": "failed",
        "verification_status": "failed",
        "external_write": False,
        "approved_external_write": False,
        "payment_provider_receipt_ref": "",
        "ledger_reconciliation_ref": "",
        "blockers": ["adapter_receipt_missing"],
    }
    payload.pop("provider_receipt")
    payload.pop("ledger_reconciliation")
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path, require_ready=True)

    assert result.valid is False
    assert result.ready is False
    assert "finance payment closure receipt ready must be true" in result.errors


def test_validate_payment_closure_receipt_rejects_missing_ledger_evidence(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    payload = _ready_receipt()
    payload["evidence_refs"] = ["provider:payment:receipt-001"]
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)

    assert result.valid is False
    assert result.ready is False
    assert "evidence_refs must include ledger_reconciliation_ref" in result.errors


def test_validate_payment_closure_receipt_rejects_provider_receipt_drift(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    payload = _ready_receipt()
    payload["provider_receipt"] = dict(payload["provider_receipt"]) | {
        "idempotency_key": "idempotency:case-success-001:drift",
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)

    assert result.valid is False
    assert result.ready is False
    assert "provider_receipt idempotency_key must match receipt idempotency_key" in result.errors


def test_validate_payment_closure_receipt_accepts_non_sandbox_provider_binding(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    binding_ref = "provider-binding:stripe:acct-001"
    payload = _ready_receipt()
    payload["provider_receipt"] = dict(payload["provider_receipt"]) | {
        "provider": "stripe",
        "evidence_refs": ["provider:payment:receipt-001", binding_ref],
    }
    payload["evidence_refs"] = [
        "provider:payment:receipt-001",
        "ledger:reconciliation:receipt-001",
        binding_ref,
    ]
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path, require_ready=True)

    assert result.valid is True
    assert result.ready is True
    assert result.blockers == ()


def test_validate_payment_closure_receipt_rejects_non_sandbox_provider_without_binding(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    payload = _ready_receipt()
    payload["provider_receipt"] = dict(payload["provider_receipt"]) | {"provider": "stripe"}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path, require_ready=True)

    assert result.valid is False
    assert result.ready is False
    assert "evidence_refs must include provider binding receipt for non-sandbox provider" in result.errors
    assert "provider_receipt evidence_refs must include provider binding receipt for non-sandbox provider" in result.errors


def test_validate_payment_closure_receipt_rejects_unapproved_external_write(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    payload = _ready_receipt() | {"approved_external_write": False}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)

    assert result.valid is False
    assert result.ready is False
    assert any("approved_external_write" in error for error in result.errors)


def test_validate_payment_closure_receipt_rejects_raw_provider_response(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    payload = _ready_receipt() | {"raw_provider_response": {"secret": "do-not-export"}}
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)

    assert result.valid is False
    assert result.ready is False
    assert "$: unexpected property 'raw_provider_response'" in result.errors


def test_validate_payment_closure_receipt_cli_outputs_json(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    receipt_path.write_text(json.dumps(_ready_receipt()), encoding="utf-8")

    exit_code = main(["--receipt", str(receipt_path), "--require-ready", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert payload["payment_provider_receipt_ref"] == "provider:payment:receipt-001"


def _ready_receipt() -> dict[str, object]:
    return {
        "receipt_id": "finance-payment-closure-receipt-test",
        "adapter_id": "finance.payment_adapter",
        "status": "passed",
        "verification_status": "passed",
        "checked_at": "2026-05-01T12:00:00+00:00",
        "case_id": "case-success-001",
        "tenant_id": "tenant-demo",
        "invoice_id": "INV-OK-001",
        "amount": {"currency": "USD", "minor_units": 120000},
        "effect_type": "payment_sent_with_approval",
        "capability_id": "payment.execute.with_approval",
        "approval_id": "fin-approval-001",
        "idempotency_key": "idempotency:case-success-001:payment",
        "payment_provider_receipt_ref": "provider:payment:receipt-001",
        "ledger_reconciliation_ref": "ledger:reconciliation:receipt-001",
        "external_write": True,
        "approved_external_write": True,
        "provider_receipt": {
            "receipt_ref": "provider:payment:receipt-001",
            "provider": "sandbox",
            "provider_operation": "payment.execute.with_approval",
            "transaction_id_hash": "a" * 64,
            "amount": {"currency": "USD", "minor_units": 120000},
            "external_write": True,
            "approval_id": "fin-approval-001",
            "idempotency_key": "idempotency:case-success-001:payment",
            "evidence_refs": ["provider:payment:receipt-001"],
        },
        "ledger_reconciliation": {
            "receipt_ref": "ledger:reconciliation:receipt-001",
            "payment_provider_receipt_ref": "provider:payment:receipt-001",
            "ledger_system": "sandbox-ledger",
            "reconciliation_status": "matched",
            "amount_matched": True,
            "currency_matched": True,
            "invoice_id": "INV-OK-001",
            "evidence_refs": ["ledger:reconciliation:receipt-001"],
        },
        "evidence_refs": [
            "provider:payment:receipt-001",
            "ledger:reconciliation:receipt-001",
        ],
        "blockers": [],
    }
