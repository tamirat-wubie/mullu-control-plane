#!/usr/bin/env python3
"""Produce a finance approval payment closure receipt.

Purpose: emit deterministic sandbox payment-provider and ledger-reconciliation
receipt evidence for the finance approval payment closure contract.
Governance scope: approval-bound payment effect evidence, idempotency key
binding, provider receipt identity, ledger reconciliation identity, and blocked
failure evidence.
Dependencies: schemas/finance_approval_payment_closure_receipt.schema.json and
scripts.validate_finance_approval_payment_closure_receipt.
Invariants:
  - The default producer emits sandbox evidence only; no live provider is called.
  - Ready receipts bind provider and ledger evidence to the same approval.
  - Failed producer modes still write valid blocked evidence.
  - Raw provider responses and secrets are never written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_finance_approval_payment_closure_receipt import (  # noqa: E402
    DEFAULT_RECEIPT,
    PROVIDER_BINDING_REF_PREFIX,
    validate_finance_approval_payment_closure_receipt,
)

DEFAULT_CASE_ID = "case-success-001"
DEFAULT_TENANT_ID = "tenant-demo"
DEFAULT_INVOICE_ID = "INV-OK-001"
DEFAULT_APPROVAL_ID = "fin-approval-001"
DEFAULT_IDEMPOTENCY_KEY = "idempotency:case-success-001:payment"
DEFAULT_CURRENCY = "USD"
DEFAULT_MINOR_UNITS = 120_000


@dataclass(frozen=True, slots=True)
class FinancePaymentClosureReceiptWrite:
    """One finance payment closure receipt write result."""

    status: str
    ready: bool
    output_path: str
    receipt_id: str
    payment_provider_receipt_ref: str
    ledger_reconciliation_ref: str
    provider_binding_ref: str
    blockers: tuple[str, ...]
    validation_errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether the produced receipt is ready for closure."""
        return self.status == "passed" and self.ready and not self.blockers and not self.validation_errors

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready receipt write summary."""
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["validation_errors"] = list(self.validation_errors)
        return payload


def produce_finance_approval_payment_closure_receipt(
    *,
    output_path: Path = DEFAULT_RECEIPT,
    case_id: str = DEFAULT_CASE_ID,
    tenant_id: str = DEFAULT_TENANT_ID,
    invoice_id: str = DEFAULT_INVOICE_ID,
    approval_id: str = DEFAULT_APPROVAL_ID,
    idempotency_key: str = DEFAULT_IDEMPOTENCY_KEY,
    currency: str = DEFAULT_CURRENCY,
    minor_units: int = DEFAULT_MINOR_UNITS,
    provider: str = "sandbox",
    provider_binding_ref: str = "",
    missing_provider_receipt: bool = False,
    ledger_mismatch: bool = False,
    unapproved_write: bool = False,
    clock: Callable[[], str] | None = None,
) -> FinancePaymentClosureReceiptWrite:
    """Produce one deterministic finance approval payment closure receipt."""
    checked_at = (clock or _validation_clock)()
    amount = {"currency": currency.upper(), "minor_units": minor_units}
    payment_provider_receipt_ref = ""
    ledger_reconciliation_ref = ""
    blockers: list[str] = []
    provider_binding_blocker = _provider_binding_blocker(
        provider=provider,
        provider_binding_ref=provider_binding_ref,
    )
    if provider_binding_blocker:
        blockers.append(provider_binding_blocker)
    if missing_provider_receipt:
        blockers.append("adapter_receipt_missing")
    if ledger_mismatch:
        blockers.append("ledger_reconciliation_mismatch")
    if unapproved_write:
        blockers.append("unapproved_external_write")
    if not missing_provider_receipt and not provider_binding_blocker:
        payment_provider_receipt_ref = _provider_ref(
            case_id=case_id,
            invoice_id=invoice_id,
            approval_id=approval_id,
            idempotency_key=idempotency_key,
        )
        ledger_reconciliation_ref = _ledger_ref(
            payment_provider_receipt_ref=payment_provider_receipt_ref,
            invoice_id=invoice_id,
        )
    status = "passed" if not blockers else "failed"
    payload = _receipt_payload(
        checked_at=checked_at,
        status=status,
        case_id=case_id,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        approval_id=approval_id,
        idempotency_key=idempotency_key,
        amount=amount,
        provider=provider,
        provider_binding_ref=provider_binding_ref,
        payment_provider_receipt_ref=payment_provider_receipt_ref,
        ledger_reconciliation_ref=ledger_reconciliation_ref,
        ledger_mismatch=ledger_mismatch,
        unapproved_write=unapproved_write,
        blockers=blockers,
    )
    _write_json(output_path, payload)
    validation = validate_finance_approval_payment_closure_receipt(receipt_path=output_path)
    return FinancePaymentClosureReceiptWrite(
        status=str(payload["status"]),
        ready=validation.ready,
        output_path=str(output_path),
        receipt_id=str(payload["receipt_id"]),
        payment_provider_receipt_ref=payment_provider_receipt_ref,
        ledger_reconciliation_ref=ledger_reconciliation_ref,
        provider_binding_ref=provider_binding_ref,
        blockers=tuple(blockers),
        validation_errors=validation.errors,
    )


def _receipt_payload(
    *,
    checked_at: str,
    status: str,
    case_id: str,
    tenant_id: str,
    invoice_id: str,
    approval_id: str,
    idempotency_key: str,
    amount: dict[str, Any],
    provider: str,
    provider_binding_ref: str,
    payment_provider_receipt_ref: str,
    ledger_reconciliation_ref: str,
    ledger_mismatch: bool,
    unapproved_write: bool,
    blockers: list[str],
) -> dict[str, Any]:
    approved_external_write = not unapproved_write
    provider_receipt = _provider_receipt(
        provider=provider,
        provider_binding_ref=provider_binding_ref,
        payment_provider_receipt_ref=payment_provider_receipt_ref,
        approval_id=approval_id,
        idempotency_key=idempotency_key,
        amount=amount,
    )
    ledger_reconciliation = _ledger_reconciliation(
        payment_provider_receipt_ref=payment_provider_receipt_ref,
        ledger_reconciliation_ref=ledger_reconciliation_ref,
        invoice_id=invoice_id,
        ledger_mismatch=ledger_mismatch,
    )
    evidence_refs = [
        ref
        for ref in (payment_provider_receipt_ref, ledger_reconciliation_ref, provider_binding_ref)
        if ref
    ]
    payload: dict[str, Any] = {
        "receipt_id": _stable_id(
            "finance-payment-closure-receipt",
            {
                "case_id": case_id,
                "invoice_id": invoice_id,
                "approval_id": approval_id,
                "checked_at": checked_at,
                "status": status,
            },
        ),
        "adapter_id": "finance.payment_adapter",
        "status": status,
        "verification_status": "passed" if status == "passed" else "failed",
        "checked_at": checked_at,
        "case_id": case_id,
        "tenant_id": tenant_id,
        "invoice_id": invoice_id,
        "amount": amount,
        "effect_type": "payment_sent_with_approval",
        "capability_id": "payment.execute.with_approval",
        "approval_id": approval_id,
        "idempotency_key": idempotency_key,
        "payment_provider_receipt_ref": payment_provider_receipt_ref,
        "ledger_reconciliation_ref": ledger_reconciliation_ref,
        "external_write": bool(payment_provider_receipt_ref),
        "approved_external_write": approved_external_write,
        "evidence_refs": evidence_refs,
        "blockers": list(blockers),
    }
    if provider_receipt is not None:
        payload["provider_receipt"] = provider_receipt
    if ledger_reconciliation is not None:
        payload["ledger_reconciliation"] = ledger_reconciliation
    if blockers:
        payload["failure_class"] = blockers[0]
        payload["recovery_actions"] = _recovery_actions(blockers)
    return payload


def _provider_receipt(
    *,
    provider: str,
    provider_binding_ref: str,
    payment_provider_receipt_ref: str,
    approval_id: str,
    idempotency_key: str,
    amount: dict[str, Any],
) -> dict[str, Any] | None:
    if not payment_provider_receipt_ref:
        return None
    evidence_refs = [
        ref
        for ref in (payment_provider_receipt_ref, provider_binding_ref)
        if ref
    ]
    return {
        "receipt_ref": payment_provider_receipt_ref,
        "provider": provider,
        "provider_operation": "payment.execute.with_approval",
        "transaction_id_hash": _digest(
            {
                "provider": provider,
                "payment_provider_receipt_ref": payment_provider_receipt_ref,
                "idempotency_key": idempotency_key,
            }
        ),
        "amount": amount,
        "external_write": True,
        "approval_id": approval_id,
        "idempotency_key": idempotency_key,
        "evidence_refs": evidence_refs,
    }


def _ledger_reconciliation(
    *,
    payment_provider_receipt_ref: str,
    ledger_reconciliation_ref: str,
    invoice_id: str,
    ledger_mismatch: bool,
) -> dict[str, Any] | None:
    if not ledger_reconciliation_ref:
        return None
    return {
        "receipt_ref": ledger_reconciliation_ref,
        "payment_provider_receipt_ref": payment_provider_receipt_ref,
        "ledger_system": "sandbox-ledger",
        "reconciliation_status": "mismatched" if ledger_mismatch else "matched",
        "amount_matched": not ledger_mismatch,
        "currency_matched": not ledger_mismatch,
        "invoice_id": invoice_id,
        "evidence_refs": [ledger_reconciliation_ref],
    }


def _provider_ref(
    *,
    case_id: str,
    invoice_id: str,
    approval_id: str,
    idempotency_key: str,
) -> str:
    suffix = _digest(
        {
            "case_id": case_id,
            "invoice_id": invoice_id,
            "approval_id": approval_id,
            "idempotency_key": idempotency_key,
        }
    )[:16]
    return f"provider:payment:{suffix}"


def _ledger_ref(*, payment_provider_receipt_ref: str, invoice_id: str) -> str:
    suffix = _digest(
        {
            "payment_provider_receipt_ref": payment_provider_receipt_ref,
            "invoice_id": invoice_id,
        }
    )[:16]
    return f"ledger:reconciliation:{suffix}"


def _provider_binding_blocker(*, provider: str, provider_binding_ref: str) -> str:
    if provider == "sandbox":
        return ""
    if not provider_binding_ref:
        return "provider_binding_receipt_required"
    if not provider_binding_ref.startswith(f"{PROVIDER_BINDING_REF_PREFIX}{provider}:"):
        return "provider_binding_receipt_mismatch"
    return ""


def _recovery_actions(blockers: list[str]) -> list[str]:
    actions: list[str] = []
    if (
        "provider_binding_receipt_required" in blockers
        or "provider_binding_receipt_mismatch" in blockers
    ):
        actions.append("collect_provider_binding_receipt")
    if "adapter_receipt_missing" in blockers:
        actions.append("collect_payment_provider_receipt")
    if "ledger_reconciliation_mismatch" in blockers:
        actions.append("rerun_ledger_reconciliation")
    if "unapproved_external_write" in blockers:
        actions.append("restore_approval_bound_payment_flow")
    return actions


def _stable_id(prefix: str, material: Any) -> str:
    return f"{prefix}-{_digest(material)[:16]}"


def _digest(material: Any) -> str:
    return hashlib.sha256(
        json.dumps(_json_ready(material), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance payment closure receipt producer arguments."""
    parser = argparse.ArgumentParser(description="Produce a finance payment closure receipt.")
    parser.add_argument("--output", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--invoice-id", default=DEFAULT_INVOICE_ID)
    parser.add_argument("--approval-id", default=DEFAULT_APPROVAL_ID)
    parser.add_argument("--idempotency-key", default=DEFAULT_IDEMPOTENCY_KEY)
    parser.add_argument("--currency", default=DEFAULT_CURRENCY)
    parser.add_argument("--minor-units", type=int, default=DEFAULT_MINOR_UNITS)
    parser.add_argument(
        "--provider",
        choices=("sandbox", "stripe", "bank_ach", "manual_bank_portal"),
        default="sandbox",
    )
    parser.add_argument("--provider-binding-ref", default="")
    parser.add_argument("--missing-provider-receipt", action="store_true")
    parser.add_argument("--ledger-mismatch", action="store_true")
    parser.add_argument("--unapproved-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance payment closure receipt production."""
    args = parse_args(argv)
    write = produce_finance_approval_payment_closure_receipt(
        output_path=Path(args.output),
        case_id=args.case_id,
        tenant_id=args.tenant_id,
        invoice_id=args.invoice_id,
        approval_id=args.approval_id,
        idempotency_key=args.idempotency_key,
        currency=args.currency,
        minor_units=args.minor_units,
        provider=args.provider,
        provider_binding_ref=args.provider_binding_ref,
        missing_provider_receipt=args.missing_provider_receipt,
        ledger_mismatch=args.ledger_mismatch,
        unapproved_write=args.unapproved_write,
    )
    if args.json:
        print(json.dumps(write.as_dict(), indent=2, sort_keys=True))
    elif write.passed:
        print(f"finance payment closure receipt passed -> {write.output_path}")
    else:
        print(f"finance payment closure receipt blocked blockers={list(write.blockers)}")
    return 0 if write.passed or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
