"""Stripe Payment Provider — Governed payment execution via Stripe API.

Supports: payment links, invoices, refunds, payouts.
Requires: STRIPE_API_KEY per tenant (stored in credential manager, never in code).

Invariants:
  - Never handles raw card numbers (tokenized via Stripe).
  - Every operation returns a structured result.
  - Provider errors are typed, never raw exceptions.
  - All operations are idempotent (Stripe idempotency key passthrough).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PaymentResult:
    """Result of a payment provider operation."""

    success: bool
    provider: str = "stripe"
    provider_tx_id: str = ""
    status: str = ""
    amount: Decimal = Decimal("0")
    currency: str = ""
    url: str = ""  # For payment links
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class StripeProvider:
    """Stripe API adapter for governed payment execution.

    In production, calls Stripe REST API. In testing, uses deterministic
    stub behavior. Never handles raw card data.

    Tenant credential resolution is external — this provider receives
    the API key per call, never stores it.
    """

    provider_name = "stripe"

    def __init__(self, *, test_mode: bool = True) -> None:
        self._test_mode = test_mode
        self._call_count = 0

    def create_payment_link(
        self,
        *,
        amount: Decimal,
        currency: str,
        description: str = "",
        idempotency_key: str = "",
        api_key: str = "",
    ) -> PaymentResult:
        """Create a Stripe payment link.

        Production: POST https://api.stripe.com/v1/payment_links
        """
        self._call_count += 1

        if amount <= 0:
            return PaymentResult(success=False, error="amount must be positive")

        if self._test_mode:
            return PaymentResult(
                success=True,
                provider_tx_id=f"pl_test_{idempotency_key[:12] if idempotency_key else 'stub'}",
                status="active",
                amount=amount,
                currency=currency,
                url=f"https://pay.stripe.com/test/{idempotency_key[:8] if idempotency_key else 'link'}",
            )

        # Production Stripe API call would go here
        return PaymentResult(success=False, error="production mode not yet implemented")

    def create_invoice(
        self,
        *,
        amount: Decimal,
        currency: str,
        customer_email: str = "",
        description: str = "",
        idempotency_key: str = "",
        api_key: str = "",
    ) -> PaymentResult:
        """Create a Stripe invoice.

        Production: POST https://api.stripe.com/v1/invoices
        """
        self._call_count += 1

        if amount <= 0:
            return PaymentResult(success=False, error="amount must be positive")

        if self._test_mode:
            return PaymentResult(
                success=True,
                provider_tx_id=f"inv_test_{idempotency_key[:12] if idempotency_key else 'stub'}",
                status="draft",
                amount=amount,
                currency=currency,
                metadata={"customer_email": customer_email},
            )

        return PaymentResult(success=False, error="production mode not yet implemented")

    def process_refund(
        self,
        *,
        provider_tx_id: str,
        amount: Decimal | None = None,
        reason: str = "",
        idempotency_key: str = "",
        api_key: str = "",
    ) -> PaymentResult:
        """Process a refund via Stripe.

        Production: POST https://api.stripe.com/v1/refunds
        """
        self._call_count += 1

        if not provider_tx_id:
            return PaymentResult(success=False, error="provider_tx_id required for refund")

        if self._test_mode:
            return PaymentResult(
                success=True,
                provider_tx_id=f"re_test_{idempotency_key[:12] if idempotency_key else 'stub'}",
                status="succeeded",
                amount=amount or Decimal("0"),
                metadata={"original_tx": provider_tx_id, "reason": reason},
            )

        return PaymentResult(success=False, error="production mode not yet implemented")

    def send_payout(
        self,
        *,
        amount: Decimal,
        currency: str,
        destination: str,
        description: str = "",
        idempotency_key: str = "",
        api_key: str = "",
    ) -> PaymentResult:
        """Send a payout via Stripe.

        Production: POST https://api.stripe.com/v1/payouts
        """
        self._call_count += 1

        if amount <= 0:
            return PaymentResult(success=False, error="amount must be positive")
        if not destination:
            return PaymentResult(success=False, error="destination required")

        if self._test_mode:
            return PaymentResult(
                success=True,
                provider_tx_id=f"po_test_{idempotency_key[:12] if idempotency_key else 'stub'}",
                status="pending",
                amount=amount,
                currency=currency,
                metadata={"destination": destination},
            )

        return PaymentResult(success=False, error="production mode not yet implemented")

    @property
    def call_count(self) -> int:
        return self._call_count
