"""Governed Payment Tests — Full pipeline.

Tests: Spend budget enforcement, idempotency, state machine lifecycle,
    approval flow, refund flow, provider integration, error handling.
"""

import sys
from pathlib import Path
from decimal import Decimal

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from skills.financial.core.spend_budget import SpendBudget, SpendBudgetManager  # noqa: E402
from skills.financial.core.transaction_ledger import TransactionLedger  # noqa: E402
from skills.financial.core.transaction_state import TxState  # noqa: E402
from skills.financial.core.idempotency import IdempotencyStore  # noqa: E402
from skills.financial.providers.stripe_provider import StripeProvider  # noqa: E402
from skills.financial.skills.governed_payment import GovernedPaymentExecutor  # noqa: E402


def _clock() -> str:
    return "2026-04-01T00:00:00Z"


def _executor(
    per_tx_limit: Decimal = Decimal("1000"),
    daily_limit: Decimal = Decimal("5000"),
    on_approval_needed=None,
) -> GovernedPaymentExecutor:
    spend = SpendBudgetManager()
    spend.register(SpendBudget(
        budget_id="sb1", tenant_id="t1", currency="USD",
        per_tx_limit=per_tx_limit, daily_limit=daily_limit,
        weekly_limit=Decimal("20000"), monthly_limit=Decimal("50000"),
    ))
    return GovernedPaymentExecutor(
        provider=StripeProvider(test_mode=True),
        spend_mgr=spend,
        ledger=TransactionLedger(),
        idempotency=IdempotencyStore(),
        clock=_clock,
        on_approval_needed=on_approval_needed,
    )


# ═══ Initiate Payment ═══


class TestInitiatePayment:
    def test_creates_pending_approval(self):
        ex = _executor()
        result = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD",
            destination="merchant@example.com", description="Test payment",
        )
        assert result.success
        assert result.state == "pending_approval"
        assert result.requires_approval
        assert result.tx_id != ""

    def test_over_budget_denied(self):
        ex = _executor(per_tx_limit=Decimal("50"))
        result = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD",
            destination="dest",
        )
        assert not result.success
        assert "spend budget denied" in result.error

    def test_daily_limit_enforced(self):
        ex = _executor(per_tx_limit=Decimal("1000"), daily_limit=Decimal("150"))
        ex.initiate_payment(tenant_id="t1", amount=Decimal("100"), currency="USD", destination="a")
        # Approve first to record spend
        tx1 = ex._ledger.query(tenant_id="t1")[0]
        ex.approve_and_execute(tx1.tx_id)
        # Second payment should fail daily limit
        result = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="b",
        )
        assert not result.success
        assert "daily" in result.error or "spend budget" in result.error

    def test_duplicate_returns_cached(self):
        ex = _executor()
        r1 = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="dest",
        )
        ex.approve_and_execute(r1.tx_id)
        # Same params → idempotent
        r2 = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="dest",
        )
        assert r2.success
        assert r2.state == "completed_duplicate"

    def test_in_flight_returns_conflict(self):
        ex = _executor()
        ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="dest",
        )
        # Same params while still pending → in_flight
        r2 = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="dest",
        )
        assert not r2.success
        assert "already in progress" in r2.error

    def test_no_budget_registered(self):
        ex = _executor()
        result = ex.initiate_payment(
            tenant_id="unknown", amount=Decimal("10"), currency="USD", destination="dest",
        )
        assert not result.success
        assert "no spend budget" in result.error

    def test_approval_notification_failure_counted_and_non_fatal(self):
        def fail_notification(tx_id: str, tenant_id: str, amount: str, currency: str) -> None:
            raise RuntimeError("secret notification backend")

        ex = _executor(on_approval_needed=fail_notification)
        result = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="dest",
        )
        entry = ex._ledger.get(result.tx_id)
        assert result.success is True
        assert result.requires_approval is True
        assert result.metadata["approval_notification_failed"] is True
        assert ex.approval_notification_failures == 1
        assert entry is not None
        assert entry.state == TxState.PENDING_APPROVAL
        assert "secret notification backend" not in result.error


# ═══ Approve and Execute ═══


class TestApproveAndExecute:
    def test_full_lifecycle(self):
        ex = _executor()
        init = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("250"), currency="USD",
            destination="vendor@example.com", actor_id="requester",
        )
        result = ex.approve_and_execute(init.tx_id, approver_id="manager")
        assert result.success
        assert result.state == "settled"
        assert result.provider_tx_id.startswith("pl_test_")
        assert result.amount == "250"

    def test_approve_nonexistent_tx(self):
        ex = _executor()
        result = ex.approve_and_execute("nonexistent")
        assert not result.success
        assert "not found" in result.error

    def test_approve_wrong_state(self):
        ex = _executor()
        init = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="d",
        )
        ex.approve_and_execute(init.tx_id)
        # Try to approve again (now SETTLED)
        result = ex.approve_and_execute(init.tx_id)
        assert not result.success
        assert "not in PENDING_APPROVAL" in result.error

    def test_ledger_has_full_transition_history(self):
        ex = _executor()
        init = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="d",
        )
        ex.approve_and_execute(init.tx_id)
        transitions = ex._ledger.get_transitions(init.tx_id)
        states = [t.to_state for t in transitions]
        assert TxState.PENDING_APPROVAL in states
        assert TxState.AUTHORIZED in states
        assert TxState.CAPTURED in states
        assert TxState.SETTLED in states


# ═══ Deny ═══


class TestDeny:
    def test_deny_pending(self):
        ex = _executor()
        init = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="d",
        )
        result = ex.deny(init.tx_id, reason="suspicious", actor_id="reviewer")
        assert result.success
        assert result.state == "rejected"

    def test_deny_nonexistent(self):
        ex = _executor()
        result = ex.deny("nonexistent")
        assert not result.success


# ═══ Refund ═══


class TestRefund:
    def test_refund_settled_tx(self):
        ex = _executor()
        init = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="d",
        )
        ex.approve_and_execute(init.tx_id)
        result = ex.refund(init.tx_id, reason="customer request", actor_id="support")
        assert result.success
        assert result.state == "refunded"
        assert result.provider_tx_id.startswith("re_test_")
        assert result.metadata["ledger_hash"]
        assert result.metadata["refund_provider_tx_id"] == result.provider_tx_id
        assert result.metadata["recipient_hash"]

    def test_refund_non_settled_denied(self):
        ex = _executor()
        init = ex.initiate_payment(
            tenant_id="t1", amount=Decimal("100"), currency="USD", destination="d",
        )
        result = ex.refund(init.tx_id, reason="too early")
        assert not result.success
        assert "SETTLED" in result.error

    def test_refund_nonexistent(self):
        ex = _executor()
        result = ex.refund("nonexistent")
        assert not result.success


# ═══ Stripe Provider ═══


class TestStripeProvider:
    def test_payment_link(self):
        p = StripeProvider(test_mode=True)
        result = p.create_payment_link(
            amount=Decimal("50"), currency="USD",
            idempotency_key="test-key",
        )
        assert result.success
        assert result.url.startswith("https://")
        assert result.provider_tx_id.startswith("pl_test_")

    def test_invoice(self):
        p = StripeProvider(test_mode=True)
        result = p.create_invoice(
            amount=Decimal("500"), currency="USD",
            customer_email="client@example.com",
        )
        assert result.success
        assert result.status == "draft"

    def test_refund(self):
        p = StripeProvider(test_mode=True)
        result = p.process_refund(provider_tx_id="ch_123")
        assert result.success
        assert result.provider_tx_id.startswith("re_test_")

    def test_payout(self):
        p = StripeProvider(test_mode=True)
        result = p.send_payout(
            amount=Decimal("1000"), currency="USD", destination="acct_123",
        )
        assert result.success
        assert result.status == "pending"

    def test_negative_amount_rejected(self):
        p = StripeProvider(test_mode=True)
        result = p.create_payment_link(amount=Decimal("-10"), currency="USD")
        assert not result.success
        assert "positive" in result.error

    def test_missing_destination_rejected(self):
        p = StripeProvider(test_mode=True)
        result = p.send_payout(amount=Decimal("100"), currency="USD", destination="")
        assert not result.success
        assert "destination" in result.error

    def test_call_count(self):
        p = StripeProvider(test_mode=True)
        assert p.call_count == 0
        p.create_payment_link(amount=Decimal("10"), currency="USD")
        p.create_invoice(amount=Decimal("20"), currency="USD")
        assert p.call_count == 2
