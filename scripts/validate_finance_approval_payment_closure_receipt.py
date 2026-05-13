#!/usr/bin/env python3
"""Validate finance approval payment closure receipt readiness.

Purpose: reject malformed or unbound payment provider and ledger receipts
before finance approval payment closure promotion.
Governance scope: finance payment adapter evidence, approval-bound external
write, provider receipt identity, ledger reconciliation identity, and schema
conformance.
Dependencies: schemas/finance_approval_payment_closure_receipt.schema.json.
Invariants:
  - The adapter id is exactly finance.payment_adapter.
  - Ready receipts are passed, verification-passed, approval-bound writes.
  - Provider and ledger receipts must match the root closure receipt.
  - Failed receipts remain valid blocked evidence when require-ready is false.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_RECEIPT = REPO_ROOT / ".change_assurance" / "finance_approval_payment_closure_receipt.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_payment_closure_receipt.schema.json"
ADAPTER_ID = "finance.payment_adapter"
EFFECT_TYPE = "payment_sent_with_approval"
CAPABILITY_ID = "payment.execute.with_approval"
PROVIDER_REF_PREFIX = "provider:payment:"
LEDGER_REF_PREFIX = "ledger:reconciliation:"
PROVIDER_BINDING_REF_PREFIX = "provider-binding:"


@dataclass(frozen=True, slots=True)
class FinancePaymentClosureReceiptValidation:
    """Validation result for one finance payment closure receipt."""

    valid: bool
    ready: bool
    receipt_id: str
    receipt_path: str
    adapter_id: str
    status: str
    verification_status: str
    case_id: str
    tenant_id: str
    invoice_id: str
    effect_type: str
    capability_id: str
    payment_provider_receipt_ref: str
    ledger_reconciliation_ref: str
    external_write: bool
    approved_external_write: bool
    blockers: tuple[str, ...]
    recovery_actions: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["recovery_actions"] = list(self.recovery_actions)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_approval_payment_closure_receipt(
    *,
    receipt_path: Path = DEFAULT_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> FinancePaymentClosureReceiptValidation:
    """Validate one finance approval payment closure receipt."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance payment closure receipt schema", errors)
    receipt = _load_json_object(receipt_path, "finance payment closure receipt", errors)
    if not schema or not receipt:
        return _validation_result(receipt_path, receipt, errors)

    errors.extend(_validate_schema_instance(schema, receipt))
    _validate_semantics(receipt, errors)
    ready = _receipt_ready(receipt)
    if require_ready and not ready:
        errors.append("finance payment closure receipt ready must be true")
    return _validation_result(receipt_path, receipt, errors)


def _validate_semantics(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("adapter_id") != ADAPTER_ID:
        errors.append("adapter_id must be finance.payment_adapter")
    if receipt.get("status") not in {"passed", "failed"}:
        errors.append("status must be passed or failed")
    if receipt.get("verification_status") not in {"passed", "failed"}:
        errors.append("verification_status must be passed or failed")
    if receipt.get("status") == "passed" and receipt.get("verification_status") != "passed":
        errors.append("passed status requires verification_status=passed")
    if receipt.get("effect_type") != EFFECT_TYPE:
        errors.append("effect_type must be payment_sent_with_approval")
    if receipt.get("capability_id") != CAPABILITY_ID:
        errors.append("capability_id must be payment.execute.with_approval")

    blockers = receipt.get("blockers", [])
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
    elif receipt.get("status") == "passed" and blockers:
        errors.append("passed finance payment closure receipt must not carry blockers")

    if receipt.get("status") != "passed":
        return

    _validate_passed_root(receipt, errors)
    _validate_provider_receipt(receipt, errors)
    _validate_ledger_reconciliation(receipt, errors)


def _validate_passed_root(receipt: dict[str, Any], errors: list[str]) -> None:
    for field_name in ("case_id", "tenant_id", "invoice_id", "approval_id", "idempotency_key"):
        if not str(receipt.get(field_name, "")).strip():
            errors.append(f"passed finance payment closure receipt requires {field_name}")
    provider_ref = str(receipt.get("payment_provider_receipt_ref", "")).strip()
    ledger_ref = str(receipt.get("ledger_reconciliation_ref", "")).strip()
    if not provider_ref.startswith(PROVIDER_REF_PREFIX):
        errors.append("payment_provider_receipt_ref must start with provider:payment:")
    if not ledger_ref.startswith(LEDGER_REF_PREFIX):
        errors.append("ledger_reconciliation_ref must start with ledger:reconciliation:")
    if provider_ref and ledger_ref and provider_ref == ledger_ref:
        errors.append("payment_provider_receipt_ref and ledger_reconciliation_ref must differ")
    if receipt.get("external_write") is not True:
        errors.append("passed finance payment closure receipt requires external_write=true")
    if receipt.get("approved_external_write") is not True:
        errors.append("passed finance payment closure receipt requires approved_external_write=true")
    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append("evidence_refs must be a list")
    else:
        if provider_ref and provider_ref not in evidence_refs:
            errors.append("evidence_refs must include payment_provider_receipt_ref")
        if ledger_ref and ledger_ref not in evidence_refs:
            errors.append("evidence_refs must include ledger_reconciliation_ref")


def _validate_provider_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    provider_receipt = receipt.get("provider_receipt")
    if not isinstance(provider_receipt, dict):
        errors.append("passed finance payment closure receipt requires provider_receipt object")
        return
    if provider_receipt.get("receipt_ref") != receipt.get("payment_provider_receipt_ref"):
        errors.append("provider_receipt receipt_ref must match payment_provider_receipt_ref")
    if provider_receipt.get("provider_operation") != CAPABILITY_ID:
        errors.append("provider_receipt provider_operation must be payment.execute.with_approval")
    if provider_receipt.get("external_write") is not True:
        errors.append("provider_receipt external_write must be true")
    for field_name in ("approval_id", "idempotency_key"):
        if provider_receipt.get(field_name) != receipt.get(field_name):
            errors.append(f"provider_receipt {field_name} must match receipt {field_name}")
    if provider_receipt.get("amount") != receipt.get("amount"):
        errors.append("provider_receipt amount must match receipt amount")
    evidence_refs = provider_receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list) or provider_receipt.get("receipt_ref") not in evidence_refs:
        errors.append("provider_receipt evidence_refs must include provider receipt_ref")
    provider = str(provider_receipt.get("provider", ""))
    if provider != "sandbox":
        _validate_non_sandbox_provider_binding(receipt, provider_receipt, provider, errors)


def _validate_ledger_reconciliation(receipt: dict[str, Any], errors: list[str]) -> None:
    ledger_reconciliation = receipt.get("ledger_reconciliation")
    if not isinstance(ledger_reconciliation, dict):
        errors.append("passed finance payment closure receipt requires ledger_reconciliation object")
        return
    if ledger_reconciliation.get("receipt_ref") != receipt.get("ledger_reconciliation_ref"):
        errors.append("ledger_reconciliation receipt_ref must match ledger_reconciliation_ref")
    if ledger_reconciliation.get("payment_provider_receipt_ref") != receipt.get("payment_provider_receipt_ref"):
        errors.append("ledger_reconciliation payment_provider_receipt_ref must match root provider receipt")
    if ledger_reconciliation.get("invoice_id") != receipt.get("invoice_id"):
        errors.append("ledger_reconciliation invoice_id must match receipt invoice_id")
    if ledger_reconciliation.get("reconciliation_status") != "matched":
        errors.append("ledger_reconciliation reconciliation_status must be matched")
    if ledger_reconciliation.get("amount_matched") is not True:
        errors.append("ledger_reconciliation amount_matched must be true")
    if ledger_reconciliation.get("currency_matched") is not True:
        errors.append("ledger_reconciliation currency_matched must be true")
    evidence_refs = ledger_reconciliation.get("evidence_refs")
    if not isinstance(evidence_refs, list) or ledger_reconciliation.get("receipt_ref") not in evidence_refs:
        errors.append("ledger_reconciliation evidence_refs must include ledger receipt_ref")


def _validate_non_sandbox_provider_binding(
    receipt: dict[str, Any],
    provider_receipt: dict[str, Any],
    provider: str,
    errors: list[str],
) -> None:
    expected_prefix = f"{PROVIDER_BINDING_REF_PREFIX}{provider}:"
    root_evidence_refs = receipt.get("evidence_refs")
    provider_evidence_refs = provider_receipt.get("evidence_refs")
    if not isinstance(root_evidence_refs, list) or not any(
        str(ref).startswith(expected_prefix) for ref in root_evidence_refs
    ):
        errors.append("evidence_refs must include provider binding receipt for non-sandbox provider")
    if not isinstance(provider_evidence_refs, list) or not any(
        str(ref).startswith(expected_prefix) for ref in provider_evidence_refs
    ):
        errors.append("provider_receipt evidence_refs must include provider binding receipt for non-sandbox provider")


def _receipt_ready(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("adapter_id") == ADAPTER_ID
        and receipt.get("status") == "passed"
        and receipt.get("verification_status") == "passed"
        and receipt.get("effect_type") == EFFECT_TYPE
        and receipt.get("capability_id") == CAPABILITY_ID
        and receipt.get("external_write") is True
        and receipt.get("approved_external_write") is True
        and bool(str(receipt.get("case_id", "")).strip())
        and bool(str(receipt.get("tenant_id", "")).strip())
        and bool(str(receipt.get("invoice_id", "")).strip())
        and bool(str(receipt.get("approval_id", "")).strip())
        and bool(str(receipt.get("idempotency_key", "")).strip())
        and str(receipt.get("payment_provider_receipt_ref", "")).startswith(PROVIDER_REF_PREFIX)
        and str(receipt.get("ledger_reconciliation_ref", "")).startswith(LEDGER_REF_PREFIX)
        and _provider_receipt_ready(receipt)
        and _ledger_reconciliation_ready(receipt)
        and receipt.get("blockers") == []
    )


def _provider_receipt_ready(receipt: dict[str, Any]) -> bool:
    provider_receipt = receipt.get("provider_receipt")
    if not isinstance(provider_receipt, dict):
        return False
    evidence_refs = provider_receipt.get("evidence_refs")
    provider = str(provider_receipt.get("provider", ""))
    provider_binding_ready = True
    if provider != "sandbox":
        expected_prefix = f"{PROVIDER_BINDING_REF_PREFIX}{provider}:"
        root_evidence_refs = receipt.get("evidence_refs")
        provider_binding_ready = (
            isinstance(root_evidence_refs, list)
            and any(str(ref).startswith(expected_prefix) for ref in root_evidence_refs)
            and isinstance(evidence_refs, list)
            and any(str(ref).startswith(expected_prefix) for ref in evidence_refs)
        )
    return (
        provider_receipt.get("receipt_ref") == receipt.get("payment_provider_receipt_ref")
        and provider_receipt.get("provider_operation") == CAPABILITY_ID
        and provider_receipt.get("external_write") is True
        and provider_receipt.get("approval_id") == receipt.get("approval_id")
        and provider_receipt.get("idempotency_key") == receipt.get("idempotency_key")
        and provider_receipt.get("amount") == receipt.get("amount")
        and isinstance(evidence_refs, list)
        and provider_receipt.get("receipt_ref") in evidence_refs
        and provider_binding_ready
    )


def _ledger_reconciliation_ready(receipt: dict[str, Any]) -> bool:
    ledger_reconciliation = receipt.get("ledger_reconciliation")
    if not isinstance(ledger_reconciliation, dict):
        return False
    evidence_refs = ledger_reconciliation.get("evidence_refs")
    return (
        ledger_reconciliation.get("receipt_ref") == receipt.get("ledger_reconciliation_ref")
        and ledger_reconciliation.get("payment_provider_receipt_ref") == receipt.get("payment_provider_receipt_ref")
        and ledger_reconciliation.get("invoice_id") == receipt.get("invoice_id")
        and ledger_reconciliation.get("reconciliation_status") == "matched"
        and ledger_reconciliation.get("amount_matched") is True
        and ledger_reconciliation.get("currency_matched") is True
        and isinstance(evidence_refs, list)
        and ledger_reconciliation.get("receipt_ref") in evidence_refs
    )


def _validation_result(
    receipt_path: Path,
    receipt: dict[str, Any],
    errors: list[str],
) -> FinancePaymentClosureReceiptValidation:
    blockers = receipt.get("blockers", ())
    recovery_actions = receipt.get("recovery_actions", ())
    return FinancePaymentClosureReceiptValidation(
        valid=not errors,
        ready=not errors and _receipt_ready(receipt),
        receipt_id=str(receipt.get("receipt_id", "")),
        receipt_path=str(receipt_path),
        adapter_id=str(receipt.get("adapter_id", "")),
        status=str(receipt.get("status", "")),
        verification_status=str(receipt.get("verification_status", "")),
        case_id=str(receipt.get("case_id", "")),
        tenant_id=str(receipt.get("tenant_id", "")),
        invoice_id=str(receipt.get("invoice_id", "")),
        effect_type=str(receipt.get("effect_type", "")),
        capability_id=str(receipt.get("capability_id", "")),
        payment_provider_receipt_ref=str(receipt.get("payment_provider_receipt_ref", "")),
        ledger_reconciliation_ref=str(receipt.get("ledger_reconciliation_ref", "")),
        external_write=receipt.get("external_write") is True,
        approved_external_write=receipt.get("approved_external_write") is True,
        blockers=tuple(str(blocker) for blocker in blockers) if isinstance(blockers, list) else (),
        recovery_actions=(
            tuple(str(action) for action in recovery_actions)
            if isinstance(recovery_actions, list)
            else ()
        ),
        errors=tuple(errors),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance payment closure receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate finance payment closure receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance payment closure receipt validation."""
    args = parse_args(argv)
    result = validate_finance_approval_payment_closure_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"finance payment closure receipt ok ready={result.ready}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
