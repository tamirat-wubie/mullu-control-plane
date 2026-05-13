"""Tests for finance payment-provider binding example receipts.

Purpose: prove committed reviewer fixtures validate the non-sandbox payment
closure binding chain without live provider credentials.
Governance scope: example receipt readiness, provider-binding evidence refs,
and approval-bound payment closure evidence.
Dependencies: examples finance payment binding and closure receipts.
Invariants:
  - The provider binding example is ready and redacted.
  - The closure example is ready only when bound to the provider receipt.
  - The examples use deterministic Stripe-scoped receipt references.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validate_finance_approval_payment_closure_receipt import (
    validate_finance_approval_payment_closure_receipt,
)
from scripts.validate_finance_approval_payment_provider_binding_receipt import (
    validate_finance_approval_payment_provider_binding_receipt,
)

ROOT = Path(__file__).resolve().parent.parent
BINDING_EXAMPLE = ROOT / "examples" / "finance_payment_provider_binding_receipt_stripe.json"
CLOSURE_EXAMPLE = ROOT / "examples" / "finance_payment_closure_receipt_stripe_bound.json"


def test_finance_payment_provider_binding_example_is_ready() -> None:
    result = validate_finance_approval_payment_provider_binding_receipt(
        receipt_path=BINDING_EXAMPLE,
        require_ready=True,
    )

    assert result.valid is True
    assert result.ready is True
    assert result.provider == "stripe"
    assert result.provider_binding_ref == "provider-binding:stripe:660bfb37d537d381"
    assert result.errors == ()


def test_finance_payment_closure_example_binds_provider_receipt() -> None:
    result = validate_finance_approval_payment_closure_receipt(
        receipt_path=CLOSURE_EXAMPLE,
        provider_binding_receipt_path=BINDING_EXAMPLE,
        require_ready=True,
    )

    assert result.valid is True
    assert result.ready is True
    assert result.status == "passed"
    assert result.payment_provider_receipt_ref == "provider:payment:8ac03556c6863c0d"
    assert result.ledger_reconciliation_ref == "ledger:reconciliation:07bddb6bfce7b3c2"
    assert result.errors == ()
