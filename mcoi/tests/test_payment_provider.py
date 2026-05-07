"""Payment Provider Abstraction Tests."""

import pytest
from skills.financial.providers.payment_provider import (
    FailingPaymentProvider,
    PaymentProvider,
    PaymentRequest,
    PaymentResponse,
    PaymentRouter,
    PaymentStatus,
    StubPaymentProvider,
)


def _request(amount=1000):
    return PaymentRequest(
        request_id="req-1", tenant_id="t1",
        amount_cents=amount, currency="USD", description="Test",
    )


class TestStubProvider:
    def test_charge_succeeds(self):
        p = StubPaymentProvider()
        r = p.charge(_request())
        assert r.status == PaymentStatus.COMPLETED
        assert r.provider == "stub"
        assert r.transaction_id.startswith("stub-tx-")

    def test_refund_succeeds(self):
        p = StubPaymentProvider()
        r = p.refund("tx-123")
        assert r.status == PaymentStatus.REFUNDED

    def test_health_check(self):
        assert StubPaymentProvider().health_check() is True


class TestFailingProvider:
    def test_charge_fails(self):
        p = FailingPaymentProvider()
        r = p.charge(_request())
        assert r.status == PaymentStatus.FAILED

    def test_health_check(self):
        assert FailingPaymentProvider().health_check() is False


class TestPaymentRouter:
    def test_route_to_first_provider(self):
        router = PaymentRouter()
        router.register(StubPaymentProvider(), priority=1)
        r = router.charge(_request())
        assert r.status == PaymentStatus.COMPLETED
        assert r.provider == "stub"

    def test_fallback_on_failure(self):
        router = PaymentRouter()
        router.register(FailingPaymentProvider(), priority=1)
        router.register(StubPaymentProvider(), priority=2)
        r = router.charge(_request())
        assert r.status == PaymentStatus.COMPLETED
        assert r.provider == "stub"

    def test_all_fail(self):
        router = PaymentRouter()
        router.register(FailingPaymentProvider(), priority=1)
        r = router.charge(_request())
        assert r.status == PaymentStatus.FAILED

    def test_no_providers(self):
        router = PaymentRouter()
        r = router.charge(_request())
        assert r.status == PaymentStatus.FAILED
        assert "no providers" in r.error

    def test_priority_ordering(self):
        router = PaymentRouter()
        router.register(StubPaymentProvider(), priority=2)
        router.register(FailingPaymentProvider(), priority=1)
        r = router.charge(_request())
        # Failing has higher priority (1), but fails → falls back to stub (2)
        assert r.status == PaymentStatus.COMPLETED

    def test_refund_routes_to_provider(self):
        router = PaymentRouter()
        router.register(StubPaymentProvider(), priority=1)
        r = router.refund("stub", "tx-123")
        assert r.status == PaymentStatus.REFUNDED

    def test_refund_unknown_provider(self):
        router = PaymentRouter()
        r = router.refund("nonexistent", "tx-123")
        assert r.status == PaymentStatus.FAILED

    def test_list_providers(self):
        router = PaymentRouter()
        router.register(StubPaymentProvider(), priority=1)
        router.register(FailingPaymentProvider(), priority=2)
        providers = router.list_providers()
        assert len(providers) == 2
        assert providers[0]["name"] == "stub"

    def test_summary(self):
        router = PaymentRouter()
        router.register(StubPaymentProvider())
        router.charge(_request())
        s = router.summary()
        assert s["total_charges"] == 1
        assert s["providers"] == 1

    def test_response_to_dict(self):
        r = PaymentResponse(
            request_id="r1", provider="stripe",
            status=PaymentStatus.COMPLETED, transaction_id="tx-1",
        )
        d = r.to_dict()
        assert d["status"] == "completed"
        assert d["provider"] == "stripe"


class TestBaseProvider:
    def test_defaults(self):
        p = PaymentProvider()
        r = p.charge(_request())
        assert r.status == PaymentStatus.FAILED
        assert p.health_check() is False
