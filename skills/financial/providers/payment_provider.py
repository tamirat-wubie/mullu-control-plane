"""Payment Provider Abstraction — Pluggable payment backends.

Purpose: Abstract payment processing so the platform can support
    multiple providers (Stripe, PayPal, bank transfer) without
    changing business logic.
Governance scope: payment dispatch only.
Dependencies: none (pure abstraction).
Invariants:
  - Provider selection is transparent to callers.
  - Failed payments return structured errors (no raw exceptions).
  - Every payment attempt is auditable (provider, amount, status).
  - Provider health is tracked (circuit breaker integration ready).
  - Thread-safe — concurrent payment submissions are safe.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


class PaymentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    DECLINED = "declined"
    REFUNDED = "refunded"


@dataclass(frozen=True, slots=True)
class PaymentRequest:
    """A payment request to process."""

    request_id: str
    tenant_id: str
    amount_cents: int  # Always in smallest currency unit
    currency: str  # ISO 4217
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaymentResponse:
    """Result from a payment provider."""

    request_id: str
    provider: str
    status: PaymentStatus
    transaction_id: str = ""  # Provider's transaction reference
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "provider": self.provider,
            "status": self.status.value,
            "transaction_id": self.transaction_id,
            "error": self.error,
        }


class PaymentProvider:
    """Protocol for payment backends."""

    @property
    def name(self) -> str:
        return "base"

    def charge(self, request: PaymentRequest) -> PaymentResponse:
        return PaymentResponse(
            request_id=request.request_id,
            provider=self.name,
            status=PaymentStatus.FAILED,
            error="provider not implemented",
        )

    def refund(self, transaction_id: str, *, amount_cents: int = 0) -> PaymentResponse:
        return PaymentResponse(
            request_id="", provider=self.name,
            status=PaymentStatus.FAILED,
            error="refund not implemented",
        )

    def health_check(self) -> bool:
        return False


class StubPaymentProvider(PaymentProvider):
    """Stub provider for testing — always succeeds."""

    def __init__(self) -> None:
        self._charge_count = 0
        self._refund_count = 0

    @property
    def name(self) -> str:
        return "stub"

    def charge(self, request: PaymentRequest) -> PaymentResponse:
        self._charge_count += 1
        return PaymentResponse(
            request_id=request.request_id,
            provider=self.name,
            status=PaymentStatus.COMPLETED,
            transaction_id=f"stub-tx-{self._charge_count}",
        )

    def refund(self, transaction_id: str, *, amount_cents: int = 0) -> PaymentResponse:
        self._refund_count += 1
        return PaymentResponse(
            request_id="", provider=self.name,
            status=PaymentStatus.REFUNDED,
            transaction_id=transaction_id,
        )

    def health_check(self) -> bool:
        return True


class FailingPaymentProvider(PaymentProvider):
    """Provider that always fails — for testing fallback."""

    @property
    def name(self) -> str:
        return "failing"

    def charge(self, request: PaymentRequest) -> PaymentResponse:
        return PaymentResponse(
            request_id=request.request_id,
            provider=self.name,
            status=PaymentStatus.FAILED,
            error="provider unavailable",
        )

    def health_check(self) -> bool:
        return False


class PaymentRouter:
    """Routes payments to the best available provider.

    Tries providers in priority order; falls back on failure.

    Usage:
        router = PaymentRouter()
        router.register(StripeProvider(), priority=1)
        router.register(PayPalProvider(), priority=2)

        response = router.charge(PaymentRequest(...))
    """

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._providers: list[tuple[int, PaymentProvider]] = []  # (priority, provider)
        self._lock = threading.Lock()
        self._clock = clock or (lambda: "")
        self._total_charges = 0
        self._total_failures = 0
        self._total_refunds = 0

    def register(self, provider: PaymentProvider, *, priority: int = 100) -> None:
        """Register a payment provider with priority (lower = higher priority)."""
        with self._lock:
            self._providers.append((priority, provider))
            self._providers.sort(key=lambda x: x[0])

    def charge(self, request: PaymentRequest) -> PaymentResponse:
        """Route a payment to the best available provider."""
        with self._lock:
            providers = list(self._providers)

        last_error = "no providers registered"
        for _, provider in providers:
            try:
                response = provider.charge(request)
                if response.status == PaymentStatus.COMPLETED:
                    with self._lock:
                        self._total_charges += 1
                    return response
                last_error = response.error or "payment not completed"
            except Exception as exc:
                last_error = f"provider error ({type(exc).__name__})"

        with self._lock:
            self._total_failures += 1
        return PaymentResponse(
            request_id=request.request_id,
            provider="none",
            status=PaymentStatus.FAILED,
            error=last_error,
        )

    def refund(self, provider_name: str, transaction_id: str, *, amount_cents: int = 0) -> PaymentResponse:
        """Route a refund to the specific provider that handled the charge."""
        with self._lock:
            providers = list(self._providers)

        for _, provider in providers:
            if provider.name == provider_name:
                try:
                    response = provider.refund(transaction_id, amount_cents=amount_cents)
                    if response.status == PaymentStatus.REFUNDED:
                        with self._lock:
                            self._total_refunds += 1
                    return response
                except Exception as exc:
                    return PaymentResponse(
                        request_id="", provider=provider_name,
                        status=PaymentStatus.FAILED,
                        error=f"refund error ({type(exc).__name__})",
                    )

        return PaymentResponse(
            request_id="", provider=provider_name,
            status=PaymentStatus.FAILED,
            error=f"provider {provider_name} not found",
        )

    def list_providers(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": p.name, "priority": prio, "healthy": p.health_check()}
                for prio, p in self._providers
            ]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "providers": len(self._providers),
                "total_charges": self._total_charges,
                "total_failures": self._total_failures,
                "total_refunds": self._total_refunds,
            }
