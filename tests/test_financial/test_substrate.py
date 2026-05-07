"""Financial Substrate Tests.

Tests: Currency arithmetic, spend budgets, transaction state machine,
    idempotency, double-entry ledger.
"""

import sys
from pathlib import Path
from decimal import Decimal

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
from skills.financial.core.currency import Money, minor_units  # noqa: E402
from skills.financial.core.spend_budget import SpendBudget, SpendBudgetManager  # noqa: E402
from skills.financial.core.transaction_state import (  # noqa: E402
    TxState, transition, validate_transition, is_terminal, legal_next_states,
)
from skills.financial.core.idempotency import (  # noqa: E402
    IdempotencyStore, IdempotencyStatus, compute_key,
)
from skills.financial.core.transaction_ledger import TransactionLedger  # noqa: E402


# ═══ Currency ═══


class TestMoney:
    def test_create_from_decimal(self):
        m = Money(amount=Decimal("10.50"), currency="USD")
        assert m.amount == Decimal("10.50")
        assert m.currency == "USD"

    def test_create_from_string_coercion(self):
        m = Money(amount="10.50", currency="USD")
        assert m.amount == Decimal("10.50")

    def test_empty_currency_raises(self):
        with pytest.raises(ValueError, match="currency"):
            Money(amount=Decimal("1"), currency="")

    def test_addition(self):
        a = Money(Decimal("10"), "USD")
        b = Money(Decimal("5.50"), "USD")
        assert (a + b).amount == Decimal("15.50")

    def test_addition_currency_mismatch(self):
        with pytest.raises(ValueError, match="cannot add"):
            Money(Decimal("10"), "USD") + Money(Decimal("5"), "EUR")

    def test_subtraction(self):
        a = Money(Decimal("10"), "USD")
        b = Money(Decimal("3"), "USD")
        assert (a - b).amount == Decimal("7")

    def test_comparison(self):
        a = Money(Decimal("10"), "USD")
        b = Money(Decimal("5"), "USD")
        assert a > b
        assert b < a

    def test_rounding(self):
        m = Money(Decimal("10.555"), "USD")
        r = m.rounded()
        assert r.amount == Decimal("10.56")  # Banker's rounding

    def test_jpy_no_decimals(self):
        m = Money(Decimal("100.5"), "JPY")
        r = m.rounded()
        assert r.amount == Decimal("100")

    def test_display(self):
        m = Money(Decimal("1234.56"), "USD")
        assert m.display() == "USD 1,234.56"

    def test_zero(self):
        z = Money.zero("EUR")
        assert z.amount == Decimal("0")
        assert z.is_zero

    def test_from_str(self):
        m = Money.from_str("99.99", "GBP")
        assert m.amount == Decimal("99.99")

    def test_from_str_invalid(self):
        with pytest.raises(ValueError, match="invalid amount"):
            Money.from_str("not_a_number", "USD")

    def test_minor_units(self):
        assert minor_units("USD") == 2
        assert minor_units("JPY") == 0
        assert minor_units("BTC") == 8


# ═══ Spend Budget ═══


class TestSpendBudget:
    def test_check_within_limits(self):
        mgr = SpendBudgetManager()
        mgr.register(SpendBudget(
            budget_id="b1", tenant_id="t1", currency="USD",
            per_tx_limit=Decimal("100"), daily_limit=Decimal("1000"),
            weekly_limit=Decimal("5000"), monthly_limit=Decimal("20000"),
        ))
        result = mgr.check("t1", Decimal("50"), "USD")
        assert result.allowed

    def test_check_per_tx_exceeded(self):
        mgr = SpendBudgetManager()
        mgr.register(SpendBudget(
            budget_id="b1", tenant_id="t1", currency="USD",
            per_tx_limit=Decimal("100"), daily_limit=Decimal("1000"),
            weekly_limit=Decimal("5000"), monthly_limit=Decimal("20000"),
        ))
        result = mgr.check("t1", Decimal("150"), "USD")
        assert not result.allowed
        assert "per-transaction" in result.reason

    def test_check_daily_exceeded(self):
        mgr = SpendBudgetManager()
        mgr.register(SpendBudget(
            budget_id="b1", tenant_id="t1", currency="USD",
            per_tx_limit=Decimal("500"), daily_limit=Decimal("100"),
            weekly_limit=Decimal("5000"), monthly_limit=Decimal("20000"),
            spent_today=Decimal("80"),
        ))
        result = mgr.check("t1", Decimal("30"), "USD")
        assert not result.allowed
        assert "daily" in result.reason

    def test_check_currency_mismatch(self):
        mgr = SpendBudgetManager()
        mgr.register(SpendBudget(
            budget_id="b1", tenant_id="t1", currency="USD",
            per_tx_limit=Decimal("100"), daily_limit=Decimal("1000"),
            weekly_limit=Decimal("5000"), monthly_limit=Decimal("20000"),
        ))
        result = mgr.check("t1", Decimal("50"), "EUR")
        assert not result.allowed
        assert "currency mismatch" in result.reason

    def test_check_no_budget(self):
        mgr = SpendBudgetManager()
        result = mgr.check("unknown", Decimal("10"), "USD")
        assert not result.allowed

    def test_record_spend(self):
        mgr = SpendBudgetManager()
        mgr.register(SpendBudget(
            budget_id="b1", tenant_id="t1", currency="USD",
            per_tx_limit=Decimal("100"), daily_limit=Decimal("1000"),
            weekly_limit=Decimal("5000"), monthly_limit=Decimal("20000"),
        ))
        updated = mgr.record_spend("t1", Decimal("25"))
        assert updated.spent_today == Decimal("25")
        assert updated.spent_this_month == Decimal("25")


# ═══ Transaction State Machine ═══


class TestTransactionState:
    def test_legal_forward_transition(self):
        assert validate_transition(TxState.CREATED, TxState.PENDING_APPROVAL)
        assert validate_transition(TxState.PENDING_APPROVAL, TxState.AUTHORIZED)
        assert validate_transition(TxState.AUTHORIZED, TxState.CAPTURED)
        assert validate_transition(TxState.CAPTURED, TxState.SETTLED)

    def test_refund_flow(self):
        assert validate_transition(TxState.SETTLED, TxState.REFUND_PENDING)
        assert validate_transition(TxState.REFUND_PENDING, TxState.REFUNDED)

    def test_illegal_skip(self):
        assert not validate_transition(TxState.CREATED, TxState.SETTLED)

    def test_terminal_state(self):
        assert is_terminal(TxState.REFUNDED)
        assert is_terminal(TxState.FAILED)
        assert is_terminal(TxState.REJECTED)
        assert not is_terminal(TxState.CREATED)

    def test_transition_from_terminal_raises(self):
        with pytest.raises(ValueError, match="terminal"):
            transition(TxState.FAILED, TxState.CREATED)

    def test_illegal_transition_raises(self):
        with pytest.raises(ValueError, match="illegal"):
            transition(TxState.CREATED, TxState.SETTLED)

    def test_legal_transition_returns_record(self):
        t = transition(TxState.CREATED, TxState.PENDING_APPROVAL, reason="needs approval")
        assert t.from_state == TxState.CREATED
        assert t.to_state == TxState.PENDING_APPROVAL
        assert t.reason == "needs approval"

    def test_legal_next_states(self):
        nexts = legal_next_states(TxState.CREATED)
        assert TxState.PENDING_APPROVAL in nexts
        assert TxState.SETTLED not in nexts


# ═══ Idempotency ═══


class TestIdempotency:
    def test_compute_key_deterministic(self):
        k1 = compute_key("t1", "send_payment", "dest", "100", "USD")
        k2 = compute_key("t1", "send_payment", "dest", "100", "USD")
        assert k1 == k2

    def test_compute_key_different_for_different_params(self):
        k1 = compute_key("t1", "send_payment", "dest", "100", "USD")
        k2 = compute_key("t1", "send_payment", "dest", "200", "USD")
        assert k1 != k2

    def test_new_key(self):
        store = IdempotencyStore()
        assert store.check("new-key") is None

    def test_mark_in_flight(self):
        store = IdempotencyStore()
        record = store.mark_in_flight("key1")
        assert record.status == IdempotencyStatus.IN_FLIGHT
        check = store.check("key1")
        assert check.status == IdempotencyStatus.IN_FLIGHT

    def test_mark_completed(self):
        store = IdempotencyStore()
        store.mark_in_flight("key1")
        store.mark_completed("key1", {"tx_id": "tx123"})
        check = store.check("key1")
        assert check.status == IdempotencyStatus.COMPLETED
        assert check.result == {"tx_id": "tx123"}

    def test_mark_failed_allows_retry(self):
        store = IdempotencyStore()
        store.mark_in_flight("key1")
        store.mark_failed("key1")
        assert store.check("key1") is None  # Can retry

    def test_bounded_store(self):
        store = IdempotencyStore()
        for i in range(store.MAX_RECORDS + 10):
            store.mark_in_flight(f"key-{i}")
        assert store.record_count <= store.MAX_RECORDS


# ═══ Transaction Ledger ═══


class TestTransactionLedger:
    def test_create_transaction(self):
        ledger = TransactionLedger()
        entry = ledger.create(
            tx_id="tx1", idempotency_key="idem1", tenant_id="t1",
            debit_account="user:t1", credit_account="merchant:m1",
            amount=Decimal("50.00"), currency="USD", provider="stripe",
        )
        assert entry.state == TxState.CREATED
        assert entry.amount == Decimal("50.00")
        assert entry.proof_hash != ""

    def test_duplicate_create_raises(self):
        ledger = TransactionLedger()
        ledger.create(
            tx_id="tx1", idempotency_key="i1", tenant_id="t1",
            debit_account="a", credit_account="b",
            amount=Decimal("10"), currency="USD", provider="stripe",
        )
        with pytest.raises(ValueError, match="already exists"):
            ledger.create(
                tx_id="tx1", idempotency_key="i2", tenant_id="t1",
                debit_account="a", credit_account="b",
                amount=Decimal("10"), currency="USD", provider="stripe",
            )

    def test_advance_state(self):
        ledger = TransactionLedger()
        ledger.create(
            tx_id="tx1", idempotency_key="i1", tenant_id="t1",
            debit_account="a", credit_account="b",
            amount=Decimal("10"), currency="USD", provider="stripe",
        )
        updated = ledger.advance("tx1", TxState.PENDING_APPROVAL, reason="high risk")
        assert updated.state == TxState.PENDING_APPROVAL

    def test_full_lifecycle(self):
        ledger = TransactionLedger()
        ledger.create(
            tx_id="tx1", idempotency_key="i1", tenant_id="t1",
            debit_account="a", credit_account="b",
            amount=Decimal("100"), currency="USD", provider="stripe",
        )
        ledger.advance("tx1", TxState.PENDING_APPROVAL)
        ledger.advance("tx1", TxState.AUTHORIZED)
        ledger.advance("tx1", TxState.CAPTURED)
        ledger.advance("tx1", TxState.SETTLED)
        entry = ledger.get("tx1")
        assert entry.state == TxState.SETTLED
        transitions = ledger.get_transitions("tx1")
        assert len(transitions) == 4

    def test_refund_flow(self):
        ledger = TransactionLedger()
        ledger.create(
            tx_id="tx1", idempotency_key="i1", tenant_id="t1",
            debit_account="a", credit_account="b",
            amount=Decimal("100"), currency="USD", provider="stripe",
        )
        ledger.advance("tx1", TxState.AUTHORIZED)
        ledger.advance("tx1", TxState.CAPTURED)
        ledger.advance("tx1", TxState.SETTLED)
        ledger.advance("tx1", TxState.REFUND_PENDING, reason="customer request")
        ledger.advance("tx1", TxState.REFUNDED)
        assert ledger.get("tx1").state == TxState.REFUNDED

    def test_illegal_advance_raises(self):
        ledger = TransactionLedger()
        ledger.create(
            tx_id="tx1", idempotency_key="i1", tenant_id="t1",
            debit_account="a", credit_account="b",
            amount=Decimal("10"), currency="USD", provider="stripe",
        )
        with pytest.raises(ValueError, match="illegal"):
            ledger.advance("tx1", TxState.SETTLED)

    def test_query_by_tenant(self):
        ledger = TransactionLedger()
        ledger.create(tx_id="tx1", idempotency_key="i1", tenant_id="t1",
                      debit_account="a", credit_account="b", amount=Decimal("10"),
                      currency="USD", provider="stripe")
        ledger.create(tx_id="tx2", idempotency_key="i2", tenant_id="t2",
                      debit_account="a", credit_account="b", amount=Decimal("20"),
                      currency="USD", provider="stripe")
        assert len(ledger.query(tenant_id="t1")) == 1

    def test_summary(self):
        ledger = TransactionLedger()
        ledger.create(tx_id="tx1", idempotency_key="i1", tenant_id="t1",
                      debit_account="a", credit_account="b", amount=Decimal("10"),
                      currency="USD", provider="stripe")
        summary = ledger.summary()
        assert summary["transactions"] == 1
        assert "created" in summary["states"]
