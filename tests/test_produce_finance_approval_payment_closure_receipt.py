"""Tests for finance payment closure receipt production.

Purpose: prove the producer emits deterministic sandbox payment closure
receipts that validate against the public contract without invoking a live
provider.
Governance scope: provider receipt refs, ledger reconciliation refs, blocked
failure evidence, and strict CLI promotion behavior.
Dependencies: scripts.produce_finance_approval_payment_closure_receipt and the
payment closure receipt validator.
Invariants:
  - Default production emits a ready sandbox receipt.
  - Failure modes remain valid blocked evidence.
  - Strict CLI mode fails when a produced receipt is not ready.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_finance_approval_payment_provider_binding_receipt import (
    emit_finance_approval_payment_provider_binding_receipt,
    write_finance_payment_provider_binding_receipt,
)
from scripts.produce_finance_approval_payment_closure_receipt import (
    main,
    produce_finance_approval_payment_closure_receipt,
)
from scripts.validate_finance_approval_payment_closure_receipt import (
    validate_finance_approval_payment_closure_receipt,
)


def test_produce_payment_closure_receipt_emits_ready_sandbox_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"

    write = produce_finance_approval_payment_closure_receipt(output_path=receipt_path)
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path, require_ready=True)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert write.passed is True
    assert write.ready is True
    assert write.blockers == ()
    assert write.validation_errors == ()
    assert validation.valid is True
    assert validation.ready is True
    assert payload["provider_receipt"]["provider"] == "sandbox"
    assert payload["payment_provider_receipt_ref"].startswith("provider:payment:")
    assert payload["ledger_reconciliation_ref"].startswith("ledger:reconciliation:")
    assert payload["provider_receipt"]["receipt_ref"] == payload["payment_provider_receipt_ref"]
    assert payload["ledger_reconciliation"]["receipt_ref"] == payload["ledger_reconciliation_ref"]


def test_produce_payment_closure_receipt_emits_ready_non_sandbox_with_binding(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    binding_ref = "provider-binding:stripe:acct-001"

    write = produce_finance_approval_payment_closure_receipt(
        output_path=receipt_path,
        provider="stripe",
        provider_binding_ref=binding_ref,
    )
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path, require_ready=True)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert write.passed is True
    assert write.provider_binding_ref == binding_ref
    assert validation.valid is True
    assert validation.ready is True
    assert payload["provider_receipt"]["provider"] == "stripe"
    assert binding_ref in payload["evidence_refs"]
    assert binding_ref in payload["provider_receipt"]["evidence_refs"]


def test_produce_payment_closure_receipt_derives_binding_ref_from_ready_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    binding_path = tmp_path / "finance-payment-provider-binding.json"
    binding_receipt, binding_errors = emit_finance_approval_payment_provider_binding_receipt(
        provider="stripe",
        env_reader=lambda name: "present" if name == "STRIPE_API_KEY" else "",
    )
    write_finance_payment_provider_binding_receipt(binding_receipt, binding_path)

    write = produce_finance_approval_payment_closure_receipt(
        output_path=receipt_path,
        provider="stripe",
        provider_binding_receipt_path=binding_path,
    )
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path, require_ready=True)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert binding_errors == ()
    assert write.passed is True
    assert write.provider_binding_ref == binding_receipt.provider_binding_ref
    assert write.provider_binding_receipt_path == str(binding_path)
    assert write.binding_validation_errors == ()
    assert validation.valid is True
    assert validation.ready is True
    assert binding_receipt.provider_binding_ref in payload["evidence_refs"]
    assert binding_receipt.provider_binding_ref in payload["provider_receipt"]["evidence_refs"]


def test_produce_payment_closure_receipt_blocks_unready_binding_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    binding_path = tmp_path / "finance-payment-provider-binding.json"
    binding_receipt, binding_errors = emit_finance_approval_payment_provider_binding_receipt(
        provider="stripe",
        env_reader=lambda name: "",
    )
    write_finance_payment_provider_binding_receipt(binding_receipt, binding_path)

    write = produce_finance_approval_payment_closure_receipt(
        output_path=receipt_path,
        provider="stripe",
        provider_binding_receipt_path=binding_path,
    )
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert binding_errors == ()
    assert write.passed is False
    assert write.ready is False
    assert write.blockers == ("provider_binding_receipt_required",)
    assert "finance payment provider binding receipt ready must be true" in write.binding_validation_errors
    assert validation.valid is True
    assert validation.ready is False
    assert "provider_receipt" not in payload
    assert "ledger_reconciliation" not in payload


def test_produce_payment_closure_receipt_blocks_binding_receipt_provider_drift(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    binding_path = tmp_path / "finance-payment-provider-binding.json"
    binding_receipt, binding_errors = emit_finance_approval_payment_provider_binding_receipt(
        provider="bank_ach",
        env_reader=lambda name: "present" if name == "BANK_ACH_CONNECTOR_TOKEN" else "",
    )
    write_finance_payment_provider_binding_receipt(binding_receipt, binding_path)

    write = produce_finance_approval_payment_closure_receipt(
        output_path=receipt_path,
        provider="stripe",
        provider_binding_receipt_path=binding_path,
    )
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert binding_errors == ()
    assert write.passed is False
    assert write.ready is False
    assert write.provider_binding_ref == binding_receipt.provider_binding_ref
    assert write.blockers == ("provider_binding_receipt_mismatch",)
    assert write.binding_validation_errors == ()
    assert validation.valid is True
    assert validation.ready is False
    assert payload["evidence_refs"] == [binding_receipt.provider_binding_ref]


def test_produce_payment_closure_receipt_requires_non_sandbox_provider_binding(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"

    write = produce_finance_approval_payment_closure_receipt(
        output_path=receipt_path,
        provider="stripe",
    )
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert write.passed is False
    assert write.status == "failed"
    assert write.ready is False
    assert write.payment_provider_receipt_ref == ""
    assert write.blockers == ("provider_binding_receipt_required",)
    assert validation.valid is True
    assert validation.ready is False
    assert "provider_receipt" not in payload
    assert "ledger_reconciliation" not in payload
    assert payload["recovery_actions"] == ["collect_provider_binding_receipt"]


def test_produce_payment_closure_receipt_rejects_provider_binding_mismatch(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    binding_ref = "provider-binding:bank_ach:acct-001"

    write = produce_finance_approval_payment_closure_receipt(
        output_path=receipt_path,
        provider="stripe",
        provider_binding_ref=binding_ref,
    )
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert write.passed is False
    assert write.status == "failed"
    assert write.ready is False
    assert write.provider_binding_ref == binding_ref
    assert write.blockers == ("provider_binding_receipt_mismatch",)
    assert validation.valid is True
    assert validation.ready is False
    assert payload["evidence_refs"] == [binding_ref]
    assert payload["failure_class"] == "provider_binding_receipt_mismatch"


def test_produce_payment_closure_receipt_missing_provider_writes_blocked_evidence(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"

    write = produce_finance_approval_payment_closure_receipt(
        output_path=receipt_path,
        missing_provider_receipt=True,
    )
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert write.passed is False
    assert write.status == "failed"
    assert write.ready is False
    assert write.blockers == ("adapter_receipt_missing",)
    assert validation.valid is True
    assert validation.ready is False
    assert "provider_receipt" not in payload
    assert "ledger_reconciliation" not in payload
    assert payload["recovery_actions"] == ["collect_payment_provider_receipt"]


def test_produce_payment_closure_receipt_ledger_mismatch_writes_blocked_evidence(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"

    write = produce_finance_approval_payment_closure_receipt(
        output_path=receipt_path,
        ledger_mismatch=True,
    )
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert write.passed is False
    assert write.status == "failed"
    assert write.ready is False
    assert write.blockers == ("ledger_reconciliation_mismatch",)
    assert validation.valid is True
    assert validation.ready is False
    assert payload["ledger_reconciliation"]["reconciliation_status"] == "mismatched"
    assert payload["ledger_reconciliation"]["amount_matched"] is False
    assert payload["recovery_actions"] == ["rerun_ledger_reconciliation"]


def test_produce_payment_closure_receipt_unapproved_write_writes_blocked_evidence(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"

    write = produce_finance_approval_payment_closure_receipt(
        output_path=receipt_path,
        unapproved_write=True,
    )
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert write.passed is False
    assert write.status == "failed"
    assert write.ready is False
    assert write.blockers == ("unapproved_external_write",)
    assert validation.valid is True
    assert validation.ready is False
    assert payload["external_write"] is True
    assert payload["approved_external_write"] is False
    assert payload["recovery_actions"] == ["restore_approval_bound_payment_flow"]


def test_produce_payment_closure_receipt_cli_strict_blocks_failed_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"

    exit_code = main(["--output", str(receipt_path), "--missing-provider-receipt", "--strict", "--json"])
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert payload["status"] == "failed"
    assert payload["blockers"] == ["adapter_receipt_missing"]


def test_produce_payment_closure_receipt_cli_outputs_json(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"

    exit_code = main(["--output", str(receipt_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["ready"] is True
    assert payload["payment_provider_receipt_ref"].startswith("provider:payment:")


def test_produce_payment_closure_receipt_cli_accepts_provider_binding_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    receipt_path = tmp_path / "finance-payment-closure-receipt.json"
    binding_path = tmp_path / "finance-payment-provider-binding.json"
    binding_receipt, binding_errors = emit_finance_approval_payment_provider_binding_receipt(
        provider="stripe",
        env_reader=lambda name: "present" if name == "STRIPE_API_KEY" else "",
    )
    write_finance_payment_provider_binding_receipt(binding_receipt, binding_path)

    exit_code = main(
        [
            "--output",
            str(receipt_path),
            "--provider",
            "stripe",
            "--provider-binding-receipt",
            str(binding_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert binding_errors == ()
    assert exit_code == 0
    assert stdout_payload["ready"] is True
    assert stdout_payload["provider_binding_ref"] == binding_receipt.provider_binding_ref
    assert payload["status"] == "passed"
    assert binding_receipt.provider_binding_ref in payload["evidence_refs"]
