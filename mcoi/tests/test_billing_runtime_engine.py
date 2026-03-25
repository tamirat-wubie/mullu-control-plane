"""Comprehensive tests for BillingRuntimeEngine.

Covers: account CRUD and lifecycle, invoice management, charge recording,
credit and penalty management, dispute handling, revenue computation,
violation detection, snapshots, state hashing, and six golden scenarios.
"""

import pytest

from mcoi_runtime.contracts.billing_runtime import (
    BillingAccount,
    BillingClosureReport,
    BillingDecision,
    BillingStatus,
    BillingViolation,
    ChargeKind,
    ChargeRecord,
    CreditDisposition,
    CreditRecord,
    DisputeRecord,
    DisputeStatus,
    InvoiceRecord,
    InvoiceStatus,
    PenaltyRecord,
    RevenueRecognitionStatus,
    RevenueSnapshot,
)
from mcoi_runtime.core.billing_runtime import BillingRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAST = "2020-01-01T00:00:00Z"
_PAST2 = "2020-06-15T00:00:00Z"
_FUTURE = "2099-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def engine(es):
    return BillingRuntimeEngine(es)


@pytest.fixture()
def account_engine(engine):
    """Engine with a single registered account."""
    engine.register_account("acct-1", "t1", "vendor-a")
    return engine


@pytest.fixture()
def invoice_engine(account_engine):
    """Engine with an account and a draft invoice."""
    account_engine.create_invoice("inv-1", "acct-1")
    return account_engine


@pytest.fixture()
def charged_invoice_engine(invoice_engine):
    """Engine with an account, invoice, and charges ready to issue."""
    invoice_engine.add_charge("ch-1", "inv-1", 100.0)
    invoice_engine.add_charge("ch-2", "inv-1", 50.0)
    return invoice_engine


@pytest.fixture()
def issued_invoice_engine(charged_invoice_engine):
    """Engine with an issued invoice."""
    charged_invoice_engine.issue_invoice("inv-1")
    return charged_invoice_engine


# ===================================================================
# 1. Constructor
# ===================================================================


class TestConstructor:
    def test_valid_construction(self, es):
        eng = BillingRuntimeEngine(es)
        assert eng.account_count == 0

    def test_invalid_event_spine_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            BillingRuntimeEngine("not-an-engine")

    def test_invalid_event_spine_none_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            BillingRuntimeEngine(None)

    def test_invalid_event_spine_int_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            BillingRuntimeEngine(42)

    def test_initial_account_count_zero(self, engine):
        assert engine.account_count == 0

    def test_initial_invoice_count_zero(self, engine):
        assert engine.invoice_count == 0

    def test_initial_charge_count_zero(self, engine):
        assert engine.charge_count == 0

    def test_initial_credit_count_zero(self, engine):
        assert engine.credit_count == 0

    def test_initial_penalty_count_zero(self, engine):
        assert engine.penalty_count == 0

    def test_initial_dispute_count_zero(self, engine):
        assert engine.dispute_count == 0

    def test_initial_decision_count_zero(self, engine):
        assert engine.decision_count == 0

    def test_initial_violation_count_zero(self, engine):
        assert engine.violation_count == 0


# ===================================================================
# 2. Accounts — register_account
# ===================================================================


class TestRegisterAccount:
    def test_register_returns_billing_account(self, engine):
        acct = engine.register_account("a1", "t1", "vendor-x")
        assert isinstance(acct, BillingAccount)

    def test_register_sets_account_id(self, engine):
        acct = engine.register_account("a1", "t1", "vendor-x")
        assert acct.account_id == "a1"

    def test_register_sets_tenant_id(self, engine):
        acct = engine.register_account("a1", "t1", "vendor-x")
        assert acct.tenant_id == "t1"

    def test_register_sets_counterparty(self, engine):
        acct = engine.register_account("a1", "t1", "vendor-x")
        assert acct.counterparty == "vendor-x"

    def test_register_sets_active_status(self, engine):
        acct = engine.register_account("a1", "t1", "vendor-x")
        assert acct.status == BillingStatus.ACTIVE

    def test_register_default_currency_usd(self, engine):
        acct = engine.register_account("a1", "t1", "vendor-x")
        assert acct.currency == "USD"

    def test_register_custom_currency(self, engine):
        acct = engine.register_account("a1", "t1", "vendor-x", currency="EUR")
        assert acct.currency == "EUR"

    def test_register_sets_created_at(self, engine):
        acct = engine.register_account("a1", "t1", "vendor-x")
        assert acct.created_at != ""

    def test_register_increments_account_count(self, engine):
        engine.register_account("a1", "t1", "vendor-x")
        assert engine.account_count == 1

    def test_register_emits_event(self, es, engine):
        engine.register_account("a1", "t1", "vendor-x")
        assert es.event_count >= 1

    def test_register_duplicate_raises(self, engine):
        engine.register_account("a1", "t1", "vendor-x")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate account_id"):
            engine.register_account("a1", "t1", "vendor-x")

    def test_register_multiple_accounts(self, engine):
        engine.register_account("a1", "t1", "vendor-x")
        engine.register_account("a2", "t1", "vendor-y")
        assert engine.account_count == 2

    def test_register_different_tenants(self, engine):
        engine.register_account("a1", "t1", "vendor-x")
        engine.register_account("a2", "t2", "vendor-y")
        assert engine.account_count == 2


# ===================================================================
# 3. Accounts — get_account
# ===================================================================


class TestGetAccount:
    def test_get_existing_account(self, engine):
        engine.register_account("a1", "t1", "vendor-x")
        acct = engine.get_account("a1")
        assert acct.account_id == "a1"

    def test_get_returns_billing_account(self, engine):
        engine.register_account("a1", "t1", "vendor-x")
        assert isinstance(engine.get_account("a1"), BillingAccount)

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown account_id"):
            engine.get_account("nonexistent")

    def test_get_preserves_fields(self, engine):
        engine.register_account("a1", "t1", "vendor-x", currency="GBP")
        acct = engine.get_account("a1")
        assert acct.tenant_id == "t1"
        assert acct.counterparty == "vendor-x"
        assert acct.currency == "GBP"


# ===================================================================
# 4. Accounts — suspend_account
# ===================================================================


class TestSuspendAccount:
    def test_suspend_active_account(self, account_engine):
        result = account_engine.suspend_account("acct-1")
        assert result.status == BillingStatus.SUSPENDED

    def test_suspend_returns_billing_account(self, account_engine):
        result = account_engine.suspend_account("acct-1")
        assert isinstance(result, BillingAccount)

    def test_suspend_preserves_account_id(self, account_engine):
        result = account_engine.suspend_account("acct-1")
        assert result.account_id == "acct-1"

    def test_suspend_preserves_tenant_id(self, account_engine):
        result = account_engine.suspend_account("acct-1")
        assert result.tenant_id == "t1"

    def test_suspend_preserves_counterparty(self, account_engine):
        result = account_engine.suspend_account("acct-1")
        assert result.counterparty == "vendor-a"

    def test_suspend_preserves_currency(self, account_engine):
        result = account_engine.suspend_account("acct-1")
        assert result.currency == "USD"

    def test_suspend_emits_event(self, es, account_engine):
        before = es.event_count
        account_engine.suspend_account("acct-1")
        assert es.event_count > before

    def test_suspend_non_active_raises(self, account_engine):
        account_engine.suspend_account("acct-1")
        with pytest.raises(RuntimeCoreInvariantError, match="ACTIVE"):
            account_engine.suspend_account("acct-1")

    def test_suspend_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.suspend_account("nonexistent")


# ===================================================================
# 5. Accounts — close_account
# ===================================================================


class TestCloseAccount:
    def test_close_active_account(self, account_engine):
        result = account_engine.close_account("acct-1")
        assert result.status == BillingStatus.CLOSED

    def test_close_suspended_account(self, account_engine):
        account_engine.suspend_account("acct-1")
        result = account_engine.close_account("acct-1")
        assert result.status == BillingStatus.CLOSED

    def test_close_returns_billing_account(self, account_engine):
        result = account_engine.close_account("acct-1")
        assert isinstance(result, BillingAccount)

    def test_close_preserves_account_id(self, account_engine):
        result = account_engine.close_account("acct-1")
        assert result.account_id == "acct-1"

    def test_close_preserves_tenant_id(self, account_engine):
        result = account_engine.close_account("acct-1")
        assert result.tenant_id == "t1"

    def test_close_emits_event(self, es, account_engine):
        before = es.event_count
        account_engine.close_account("acct-1")
        assert es.event_count > before

    def test_close_already_closed_raises(self, account_engine):
        account_engine.close_account("acct-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already closed"):
            account_engine.close_account("acct-1")

    def test_close_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.close_account("nonexistent")


# ===================================================================
# 6. Accounts — accounts_for_tenant
# ===================================================================


class TestAccountsForTenant:
    def test_empty_tenant(self, engine):
        result = engine.accounts_for_tenant("t1")
        assert result == ()

    def test_single_account(self, account_engine):
        result = account_engine.accounts_for_tenant("t1")
        assert len(result) == 1
        assert result[0].account_id == "acct-1"

    def test_returns_tuple(self, account_engine):
        result = account_engine.accounts_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_multiple_accounts_same_tenant(self, engine):
        engine.register_account("a1", "t1", "vendor-a")
        engine.register_account("a2", "t1", "vendor-b")
        result = engine.accounts_for_tenant("t1")
        assert len(result) == 2

    def test_different_tenants_isolated(self, engine):
        engine.register_account("a1", "t1", "vendor-a")
        engine.register_account("a2", "t2", "vendor-b")
        assert len(engine.accounts_for_tenant("t1")) == 1
        assert len(engine.accounts_for_tenant("t2")) == 1

    def test_nonexistent_tenant_returns_empty(self, engine):
        engine.register_account("a1", "t1", "vendor-a")
        assert engine.accounts_for_tenant("t999") == ()


# ===================================================================
# 7. Invoices — create_invoice
# ===================================================================


class TestCreateInvoice:
    def test_create_returns_invoice_record(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1")
        assert isinstance(inv, InvoiceRecord)

    def test_create_sets_invoice_id(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1")
        assert inv.invoice_id == "inv-1"

    def test_create_sets_account_id(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1")
        assert inv.account_id == "acct-1"

    def test_create_sets_draft_status(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1")
        assert inv.status == InvoiceStatus.DRAFT

    def test_create_sets_zero_total(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1")
        assert inv.total_amount == 0.0

    def test_create_auto_fills_currency_from_account(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1")
        assert inv.currency == "USD"

    def test_create_explicit_currency_overrides(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1", currency="EUR")
        assert inv.currency == "EUR"

    def test_create_auto_fills_currency_custom(self, engine):
        engine.register_account("a1", "t1", "vendor-a", currency="JPY")
        inv = engine.create_invoice("inv-1", "a1")
        assert inv.currency == "JPY"

    def test_create_sets_tenant_id_from_account(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1")
        assert inv.tenant_id == "t1"

    def test_create_with_due_at(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1", due_at=_FUTURE)
        assert inv.due_at == _FUTURE

    def test_create_default_due_at_auto_set(self, account_engine):
        inv = account_engine.create_invoice("inv-1", "acct-1")
        assert inv.due_at != ""

    def test_create_increments_invoice_count(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1")
        assert account_engine.invoice_count == 1

    def test_create_emits_event(self, es, account_engine):
        before = es.event_count
        account_engine.create_invoice("inv-1", "acct-1")
        assert es.event_count > before

    def test_create_duplicate_raises(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate invoice_id"):
            account_engine.create_invoice("inv-1", "acct-1")

    def test_create_unknown_account_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown account_id"):
            engine.create_invoice("inv-1", "nonexistent")

    def test_create_multiple_invoices(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1")
        account_engine.create_invoice("inv-2", "acct-1")
        assert account_engine.invoice_count == 2


# ===================================================================
# 8. Invoices — get_invoice
# ===================================================================


class TestGetInvoice:
    def test_get_existing(self, invoice_engine):
        inv = invoice_engine.get_invoice("inv-1")
        assert inv.invoice_id == "inv-1"

    def test_get_returns_invoice_record(self, invoice_engine):
        assert isinstance(invoice_engine.get_invoice("inv-1"), InvoiceRecord)

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown invoice_id"):
            engine.get_invoice("nonexistent")


# ===================================================================
# 9. Invoices — issue_invoice
# ===================================================================


class TestIssueInvoice:
    def test_issue_draft_succeeds(self, charged_invoice_engine):
        inv = charged_invoice_engine.issue_invoice("inv-1")
        assert inv.status == InvoiceStatus.ISSUED

    def test_issue_computes_total_from_charges(self, charged_invoice_engine):
        inv = charged_invoice_engine.issue_invoice("inv-1")
        assert inv.total_amount == 150.0

    def test_issue_returns_invoice_record(self, charged_invoice_engine):
        inv = charged_invoice_engine.issue_invoice("inv-1")
        assert isinstance(inv, InvoiceRecord)

    def test_issue_preserves_account_id(self, charged_invoice_engine):
        inv = charged_invoice_engine.issue_invoice("inv-1")
        assert inv.account_id == "acct-1"

    def test_issue_preserves_currency(self, charged_invoice_engine):
        inv = charged_invoice_engine.issue_invoice("inv-1")
        assert inv.currency == "USD"

    def test_issue_sets_issued_at(self, charged_invoice_engine):
        inv = charged_invoice_engine.issue_invoice("inv-1")
        assert inv.issued_at != ""

    def test_issue_emits_event(self, es, charged_invoice_engine):
        before = es.event_count
        charged_invoice_engine.issue_invoice("inv-1")
        assert es.event_count > before

    def test_issue_non_draft_raises(self, issued_invoice_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="DRAFT"):
            issued_invoice_engine.issue_invoice("inv-1")

    def test_issue_no_charges_total_zero(self, invoice_engine):
        inv = invoice_engine.issue_invoice("inv-1")
        assert inv.total_amount == 0.0
        assert inv.status == InvoiceStatus.ISSUED

    def test_issue_single_charge(self, invoice_engine):
        invoice_engine.add_charge("ch-1", "inv-1", 200.0)
        inv = invoice_engine.issue_invoice("inv-1")
        assert inv.total_amount == 200.0


# ===================================================================
# 10. Invoices — pay_invoice
# ===================================================================


class TestPayInvoice:
    def test_pay_issued_succeeds(self, issued_invoice_engine):
        inv = issued_invoice_engine.pay_invoice("inv-1")
        assert inv.status == InvoiceStatus.PAID

    def test_pay_returns_invoice_record(self, issued_invoice_engine):
        inv = issued_invoice_engine.pay_invoice("inv-1")
        assert isinstance(inv, InvoiceRecord)

    def test_pay_preserves_total(self, issued_invoice_engine):
        inv = issued_invoice_engine.pay_invoice("inv-1")
        assert inv.total_amount == 150.0

    def test_pay_preserves_account_id(self, issued_invoice_engine):
        inv = issued_invoice_engine.pay_invoice("inv-1")
        assert inv.account_id == "acct-1"

    def test_pay_emits_event(self, es, issued_invoice_engine):
        before = es.event_count
        issued_invoice_engine.pay_invoice("inv-1")
        assert es.event_count > before

    def test_pay_already_paid_raises(self, issued_invoice_engine):
        issued_invoice_engine.pay_invoice("inv-1")
        with pytest.raises(RuntimeCoreInvariantError):
            issued_invoice_engine.pay_invoice("inv-1")

    def test_pay_voided_raises(self, issued_invoice_engine):
        issued_invoice_engine.void_invoice("inv-1")
        with pytest.raises(RuntimeCoreInvariantError):
            issued_invoice_engine.pay_invoice("inv-1")

    def test_pay_draft_succeeds(self, invoice_engine):
        """Draft invoices are not terminal, so pay should work."""
        inv = invoice_engine.pay_invoice("inv-1")
        assert inv.status == InvoiceStatus.PAID

    def test_pay_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.pay_invoice("nonexistent")


# ===================================================================
# 11. Invoices — void_invoice
# ===================================================================


class TestVoidInvoice:
    def test_void_issued_succeeds(self, issued_invoice_engine):
        inv = issued_invoice_engine.void_invoice("inv-1")
        assert inv.status == InvoiceStatus.VOIDED

    def test_void_draft_succeeds(self, invoice_engine):
        inv = invoice_engine.void_invoice("inv-1")
        assert inv.status == InvoiceStatus.VOIDED

    def test_void_returns_invoice_record(self, issued_invoice_engine):
        inv = issued_invoice_engine.void_invoice("inv-1")
        assert isinstance(inv, InvoiceRecord)

    def test_void_preserves_total(self, issued_invoice_engine):
        inv = issued_invoice_engine.void_invoice("inv-1")
        assert inv.total_amount == 150.0

    def test_void_emits_event(self, es, issued_invoice_engine):
        before = es.event_count
        issued_invoice_engine.void_invoice("inv-1")
        assert es.event_count > before

    def test_void_already_voided_raises(self, issued_invoice_engine):
        issued_invoice_engine.void_invoice("inv-1")
        with pytest.raises(RuntimeCoreInvariantError):
            issued_invoice_engine.void_invoice("inv-1")

    def test_void_already_paid_raises(self, issued_invoice_engine):
        issued_invoice_engine.pay_invoice("inv-1")
        with pytest.raises(RuntimeCoreInvariantError):
            issued_invoice_engine.void_invoice("inv-1")

    def test_void_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.void_invoice("nonexistent")


# ===================================================================
# 12. Invoices — invoices_for_account
# ===================================================================


class TestInvoicesForAccount:
    def test_empty(self, account_engine):
        result = account_engine.invoices_for_account("acct-1")
        assert result == ()

    def test_returns_tuple(self, invoice_engine):
        result = invoice_engine.invoices_for_account("acct-1")
        assert isinstance(result, tuple)

    def test_single_invoice(self, invoice_engine):
        result = invoice_engine.invoices_for_account("acct-1")
        assert len(result) == 1

    def test_multiple_invoices(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1")
        account_engine.create_invoice("inv-2", "acct-1")
        result = account_engine.invoices_for_account("acct-1")
        assert len(result) == 2

    def test_different_accounts_isolated(self, engine):
        engine.register_account("a1", "t1", "vendor-a")
        engine.register_account("a2", "t1", "vendor-b")
        engine.create_invoice("inv-1", "a1")
        engine.create_invoice("inv-2", "a2")
        assert len(engine.invoices_for_account("a1")) == 1
        assert len(engine.invoices_for_account("a2")) == 1


# ===================================================================
# 13. Charges — add_charge
# ===================================================================


class TestAddCharge:
    def test_add_returns_charge_record(self, invoice_engine):
        ch = invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        assert isinstance(ch, ChargeRecord)

    def test_add_sets_charge_id(self, invoice_engine):
        ch = invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        assert ch.charge_id == "ch-1"

    def test_add_sets_invoice_id(self, invoice_engine):
        ch = invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        assert ch.invoice_id == "inv-1"

    def test_add_sets_amount(self, invoice_engine):
        ch = invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        assert ch.amount == 100.0

    def test_add_default_kind_service(self, invoice_engine):
        ch = invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        assert ch.kind == ChargeKind.SERVICE

    def test_add_custom_kind(self, invoice_engine):
        ch = invoice_engine.add_charge("ch-1", "inv-1", 100.0, kind=ChargeKind.OVERAGE)
        assert ch.kind == ChargeKind.OVERAGE

    def test_add_with_description(self, invoice_engine):
        ch = invoice_engine.add_charge("ch-1", "inv-1", 100.0, description="Test charge")
        assert ch.description == "Test charge"

    def test_add_with_scope_refs(self, invoice_engine):
        ch = invoice_engine.add_charge(
            "ch-1", "inv-1", 100.0,
            scope_ref_id="ref-1", scope_ref_type="contract",
        )
        assert ch.scope_ref_id == "ref-1"
        assert ch.scope_ref_type == "contract"

    def test_add_sets_created_at(self, invoice_engine):
        ch = invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        assert ch.created_at != ""

    def test_add_increments_charge_count(self, invoice_engine):
        invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        assert invoice_engine.charge_count == 1

    def test_add_emits_event(self, es, invoice_engine):
        before = es.event_count
        invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        assert es.event_count > before

    def test_add_duplicate_raises(self, invoice_engine):
        invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate charge_id"):
            invoice_engine.add_charge("ch-1", "inv-1", 50.0)

    def test_add_to_terminal_invoice_raises(self, issued_invoice_engine):
        issued_invoice_engine.pay_invoice("inv-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            issued_invoice_engine.add_charge("ch-new", "inv-1", 10.0)

    def test_add_to_voided_invoice_raises(self, invoice_engine):
        invoice_engine.void_invoice("inv-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            invoice_engine.add_charge("ch-1", "inv-1", 10.0)

    def test_add_unknown_invoice_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_charge("ch-1", "nonexistent", 10.0)

    def test_add_multiple_charges(self, invoice_engine):
        invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        invoice_engine.add_charge("ch-2", "inv-1", 50.0)
        assert invoice_engine.charge_count == 2


# ===================================================================
# 14. Charges — charges_for_invoice
# ===================================================================


class TestChargesForInvoice:
    def test_empty(self, invoice_engine):
        result = invoice_engine.charges_for_invoice("inv-1")
        assert result == ()

    def test_returns_tuple(self, charged_invoice_engine):
        result = charged_invoice_engine.charges_for_invoice("inv-1")
        assert isinstance(result, tuple)

    def test_correct_count(self, charged_invoice_engine):
        result = charged_invoice_engine.charges_for_invoice("inv-1")
        assert len(result) == 2

    def test_different_invoices_isolated(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1")
        account_engine.create_invoice("inv-2", "acct-1")
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.add_charge("ch-2", "inv-2", 50.0)
        assert len(account_engine.charges_for_invoice("inv-1")) == 1
        assert len(account_engine.charges_for_invoice("inv-2")) == 1


# ===================================================================
# 15. Credits — add_credit
# ===================================================================


class TestAddCredit:
    def test_add_returns_credit_record(self, account_engine):
        cr = account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert isinstance(cr, CreditRecord)

    def test_add_sets_credit_id(self, account_engine):
        cr = account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert cr.credit_id == "cr-1"

    def test_add_sets_account_id(self, account_engine):
        cr = account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert cr.account_id == "acct-1"

    def test_add_sets_breach_id(self, account_engine):
        cr = account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert cr.breach_id == "breach-1"

    def test_add_sets_amount(self, account_engine):
        cr = account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert cr.amount == 50.0

    def test_add_sets_applied_disposition(self, account_engine):
        cr = account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert cr.disposition == CreditDisposition.APPLIED

    def test_add_with_reason(self, account_engine):
        cr = account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0, reason="SLA breach")
        assert cr.reason == "SLA breach"

    def test_add_sets_applied_at(self, account_engine):
        cr = account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert cr.applied_at != ""

    def test_add_increments_credit_count(self, account_engine):
        account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert account_engine.credit_count == 1

    def test_add_emits_event(self, es, account_engine):
        before = es.event_count
        account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert es.event_count > before

    def test_add_duplicate_raises(self, account_engine):
        account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate credit_id"):
            account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)

    def test_add_unknown_account_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown account_id"):
            engine.add_credit("cr-1", "nonexistent", "breach-1", 50.0)

    def test_add_multiple_credits(self, account_engine):
        account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        account_engine.add_credit("cr-2", "acct-1", "breach-2", 25.0)
        assert account_engine.credit_count == 2


# ===================================================================
# 16. Credits — credits_for_account
# ===================================================================


class TestCreditsForAccount:
    def test_empty(self, account_engine):
        result = account_engine.credits_for_account("acct-1")
        assert result == ()

    def test_returns_tuple(self, account_engine):
        account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        result = account_engine.credits_for_account("acct-1")
        assert isinstance(result, tuple)

    def test_correct_count(self, account_engine):
        account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        account_engine.add_credit("cr-2", "acct-1", "breach-2", 25.0)
        result = account_engine.credits_for_account("acct-1")
        assert len(result) == 2

    def test_different_accounts_isolated(self, engine):
        engine.register_account("a1", "t1", "vendor-a")
        engine.register_account("a2", "t1", "vendor-b")
        engine.add_credit("cr-1", "a1", "breach-1", 50.0)
        engine.add_credit("cr-2", "a2", "breach-2", 25.0)
        assert len(engine.credits_for_account("a1")) == 1
        assert len(engine.credits_for_account("a2")) == 1


# ===================================================================
# 17. Penalties — add_penalty
# ===================================================================


class TestAddPenalty:
    def test_add_returns_penalty_record(self, account_engine):
        p = account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert isinstance(p, PenaltyRecord)

    def test_add_sets_penalty_id(self, account_engine):
        p = account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert p.penalty_id == "pen-1"

    def test_add_sets_account_id(self, account_engine):
        p = account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert p.account_id == "acct-1"

    def test_add_sets_breach_id(self, account_engine):
        p = account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert p.breach_id == "breach-1"

    def test_add_sets_amount(self, account_engine):
        p = account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert p.amount == 100.0

    def test_add_with_reason(self, account_engine):
        p = account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0, reason="Late payment")
        assert p.reason == "Late payment"

    def test_add_sets_assessed_at(self, account_engine):
        p = account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert p.assessed_at != ""

    def test_add_increments_penalty_count(self, account_engine):
        account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert account_engine.penalty_count == 1

    def test_add_emits_event(self, es, account_engine):
        before = es.event_count
        account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert es.event_count > before

    def test_add_duplicate_raises(self, account_engine):
        account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate penalty_id"):
            account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)

    def test_add_unknown_account_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown account_id"):
            engine.add_penalty("pen-1", "nonexistent", "breach-1", 100.0)

    def test_add_multiple_penalties(self, account_engine):
        account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        account_engine.add_penalty("pen-2", "acct-1", "breach-2", 50.0)
        assert account_engine.penalty_count == 2


# ===================================================================
# 18. Penalties — penalties_for_account
# ===================================================================


class TestPenaltiesForAccount:
    def test_empty(self, account_engine):
        result = account_engine.penalties_for_account("acct-1")
        assert result == ()

    def test_returns_tuple(self, account_engine):
        account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        result = account_engine.penalties_for_account("acct-1")
        assert isinstance(result, tuple)

    def test_correct_count(self, account_engine):
        account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        account_engine.add_penalty("pen-2", "acct-1", "breach-2", 50.0)
        assert len(account_engine.penalties_for_account("acct-1")) == 2

    def test_different_accounts_isolated(self, engine):
        engine.register_account("a1", "t1", "vendor-a")
        engine.register_account("a2", "t1", "vendor-b")
        engine.add_penalty("pen-1", "a1", "breach-1", 100.0)
        engine.add_penalty("pen-2", "a2", "breach-2", 50.0)
        assert len(engine.penalties_for_account("a1")) == 1
        assert len(engine.penalties_for_account("a2")) == 1


# ===================================================================
# 19. Disputes — open_dispute
# ===================================================================


class TestOpenDispute:
    def test_open_returns_dispute_record(self, issued_invoice_engine):
        d = issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert isinstance(d, DisputeRecord)

    def test_open_sets_dispute_id(self, issued_invoice_engine):
        d = issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert d.dispute_id == "disp-1"

    def test_open_sets_invoice_id(self, issued_invoice_engine):
        d = issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert d.invoice_id == "inv-1"

    def test_open_sets_account_id(self, issued_invoice_engine):
        d = issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert d.account_id == "acct-1"

    def test_open_sets_open_status(self, issued_invoice_engine):
        d = issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert d.status == DisputeStatus.OPEN

    def test_open_with_reason(self, issued_invoice_engine):
        d = issued_invoice_engine.open_dispute("disp-1", "inv-1", reason="Overcharged")
        assert d.reason == "Overcharged"

    def test_open_with_amount(self, issued_invoice_engine):
        d = issued_invoice_engine.open_dispute("disp-1", "inv-1", amount=50.0)
        assert d.amount == 50.0

    def test_open_default_amount_zero(self, issued_invoice_engine):
        d = issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert d.amount == 0.0

    def test_open_sets_opened_at(self, issued_invoice_engine):
        d = issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert d.opened_at != ""

    def test_open_moves_invoice_to_disputed(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        inv = issued_invoice_engine.get_invoice("inv-1")
        assert inv.status == InvoiceStatus.DISPUTED

    def test_open_on_draft_moves_to_disputed(self, invoice_engine):
        invoice_engine.open_dispute("disp-1", "inv-1")
        inv = invoice_engine.get_invoice("inv-1")
        assert inv.status == InvoiceStatus.DISPUTED

    def test_open_on_terminal_invoice_does_not_change_status(self, issued_invoice_engine):
        issued_invoice_engine.pay_invoice("inv-1")
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        inv = issued_invoice_engine.get_invoice("inv-1")
        assert inv.status == InvoiceStatus.PAID

    def test_open_increments_dispute_count(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert issued_invoice_engine.dispute_count == 1

    def test_open_emits_event(self, es, issued_invoice_engine):
        before = es.event_count
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert es.event_count > before

    def test_open_duplicate_raises(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate dispute_id"):
            issued_invoice_engine.open_dispute("disp-1", "inv-1")

    def test_open_unknown_invoice_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.open_dispute("disp-1", "nonexistent")

    def test_open_multiple_disputes(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        issued_invoice_engine.open_dispute("disp-2", "inv-1")
        assert issued_invoice_engine.dispute_count == 2


# ===================================================================
# 20. Disputes — resolve_dispute
# ===================================================================


class TestResolveDispute:
    def test_resolve_rejected(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        d = issued_invoice_engine.resolve_dispute("disp-1", accepted=False)
        assert d.status == DisputeStatus.RESOLVED_REJECTED

    def test_resolve_accepted(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1", amount=50.0)
        d = issued_invoice_engine.resolve_dispute("disp-1", accepted=True)
        assert d.status == DisputeStatus.RESOLVED_ACCEPTED

    def test_resolve_returns_dispute_record(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        d = issued_invoice_engine.resolve_dispute("disp-1")
        assert isinstance(d, DisputeRecord)

    def test_resolve_sets_resolved_at(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        d = issued_invoice_engine.resolve_dispute("disp-1")
        assert d.resolved_at != ""

    def test_resolve_preserves_dispute_id(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        d = issued_invoice_engine.resolve_dispute("disp-1")
        assert d.dispute_id == "disp-1"

    def test_resolve_preserves_invoice_id(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        d = issued_invoice_engine.resolve_dispute("disp-1")
        assert d.invoice_id == "inv-1"

    def test_resolve_preserves_amount(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1", amount=75.0)
        d = issued_invoice_engine.resolve_dispute("disp-1")
        assert d.amount == 75.0

    def test_resolve_accepted_auto_creates_credit(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1", amount=50.0)
        before = issued_invoice_engine.credit_count
        issued_invoice_engine.resolve_dispute("disp-1", accepted=True)
        assert issued_invoice_engine.credit_count == before + 1

    def test_resolve_accepted_zero_amount_no_credit(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1", amount=0.0)
        before = issued_invoice_engine.credit_count
        issued_invoice_engine.resolve_dispute("disp-1", accepted=True)
        assert issued_invoice_engine.credit_count == before

    def test_resolve_rejected_no_credit(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1", amount=50.0)
        before = issued_invoice_engine.credit_count
        issued_invoice_engine.resolve_dispute("disp-1", accepted=False)
        assert issued_invoice_engine.credit_count == before

    def test_resolve_emits_event(self, es, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        before = es.event_count
        issued_invoice_engine.resolve_dispute("disp-1")
        assert es.event_count > before

    def test_resolve_terminal_raises_accepted(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1", amount=50.0)
        issued_invoice_engine.resolve_dispute("disp-1", accepted=True)
        with pytest.raises(RuntimeCoreInvariantError):
            issued_invoice_engine.resolve_dispute("disp-1", accepted=True)

    def test_resolve_terminal_raises_rejected(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        issued_invoice_engine.resolve_dispute("disp-1", accepted=False)
        with pytest.raises(RuntimeCoreInvariantError):
            issued_invoice_engine.resolve_dispute("disp-1")

    def test_resolve_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown dispute_id"):
            engine.resolve_dispute("nonexistent")

    def test_resolve_default_rejected(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        d = issued_invoice_engine.resolve_dispute("disp-1")
        assert d.status == DisputeStatus.RESOLVED_REJECTED


# ===================================================================
# 21. Disputes — disputes_for_invoice
# ===================================================================


class TestDisputesForInvoice:
    def test_empty(self, issued_invoice_engine):
        result = issued_invoice_engine.disputes_for_invoice("inv-1")
        assert result == ()

    def test_returns_tuple(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        result = issued_invoice_engine.disputes_for_invoice("inv-1")
        assert isinstance(result, tuple)

    def test_correct_count(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        issued_invoice_engine.open_dispute("disp-2", "inv-1")
        assert len(issued_invoice_engine.disputes_for_invoice("inv-1")) == 2

    def test_different_invoices_isolated(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1")
        account_engine.create_invoice("inv-2", "acct-1")
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.add_charge("ch-2", "inv-2", 50.0)
        account_engine.issue_invoice("inv-1")
        account_engine.issue_invoice("inv-2")
        account_engine.open_dispute("disp-1", "inv-1")
        account_engine.open_dispute("disp-2", "inv-2")
        assert len(account_engine.disputes_for_invoice("inv-1")) == 1
        assert len(account_engine.disputes_for_invoice("inv-2")) == 1


# ===================================================================
# 22. Revenue computation
# ===================================================================


class TestRevenueComputation:
    def test_recognized_revenue_empty(self, engine):
        assert engine.compute_recognized_revenue() == 0.0

    def test_pending_revenue_empty(self, engine):
        assert engine.compute_pending_revenue() == 0.0

    def test_recognized_revenue_paid_invoice(self, issued_invoice_engine):
        issued_invoice_engine.pay_invoice("inv-1")
        assert issued_invoice_engine.compute_recognized_revenue() == 150.0

    def test_recognized_revenue_excludes_issued(self, issued_invoice_engine):
        assert issued_invoice_engine.compute_recognized_revenue() == 0.0

    def test_recognized_revenue_excludes_voided(self, issued_invoice_engine):
        issued_invoice_engine.void_invoice("inv-1")
        assert issued_invoice_engine.compute_recognized_revenue() == 0.0

    def test_pending_revenue_issued_invoice(self, issued_invoice_engine):
        assert issued_invoice_engine.compute_pending_revenue() == 150.0

    def test_pending_revenue_excludes_paid(self, issued_invoice_engine):
        issued_invoice_engine.pay_invoice("inv-1")
        assert issued_invoice_engine.compute_pending_revenue() == 0.0

    def test_pending_revenue_excludes_voided(self, issued_invoice_engine):
        issued_invoice_engine.void_invoice("inv-1")
        assert issued_invoice_engine.compute_pending_revenue() == 0.0

    def test_pending_revenue_includes_disputed(self, issued_invoice_engine):
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert issued_invoice_engine.compute_pending_revenue() == 150.0

    def test_pending_revenue_includes_overdue(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 200.0)
        account_engine.issue_invoice("inv-1")
        account_engine.detect_billing_violations()
        assert account_engine.compute_pending_revenue() == 200.0

    def test_recognized_multiple_paid(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1")
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.pay_invoice("inv-1")
        account_engine.create_invoice("inv-2", "acct-1")
        account_engine.add_charge("ch-2", "inv-2", 200.0)
        account_engine.issue_invoice("inv-2")
        account_engine.pay_invoice("inv-2")
        assert account_engine.compute_recognized_revenue() == 300.0

    def test_pending_excludes_draft(self, invoice_engine):
        assert invoice_engine.compute_pending_revenue() == 0.0

    def test_mixed_revenue(self, account_engine):
        # Paid invoice
        account_engine.create_invoice("inv-1", "acct-1")
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.pay_invoice("inv-1")
        # Issued invoice
        account_engine.create_invoice("inv-2", "acct-1")
        account_engine.add_charge("ch-2", "inv-2", 200.0)
        account_engine.issue_invoice("inv-2")
        assert account_engine.compute_recognized_revenue() == 100.0
        assert account_engine.compute_pending_revenue() == 200.0


# ===================================================================
# 23. Violation detection
# ===================================================================


class TestViolationDetection:
    def test_no_violations_empty(self, engine):
        result = engine.detect_billing_violations()
        assert result == ()

    def test_returns_tuple(self, engine):
        assert isinstance(engine.detect_billing_violations(), tuple)

    def test_overdue_invoice_detected(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        violations = account_engine.detect_billing_violations()
        assert len(violations) >= 1

    def test_overdue_marks_invoice_overdue(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.detect_billing_violations()
        inv = account_engine.get_invoice("inv-1")
        assert inv.status == InvoiceStatus.OVERDUE

    def test_overdue_violation_has_correct_operation(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        violations = account_engine.detect_billing_violations()
        overdue_violations = [v for v in violations if v.operation == "overdue_invoice"]
        assert len(overdue_violations) >= 1

    def test_overdue_violation_has_account_id(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        violations = account_engine.detect_billing_violations()
        assert all(v.account_id == "acct-1" for v in violations if v.operation == "overdue_invoice")

    def test_overdue_violation_has_tenant_id(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        violations = account_engine.detect_billing_violations()
        assert all(v.tenant_id == "t1" for v in violations if v.operation == "overdue_invoice")

    def test_overdue_violation_has_detected_at(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        violations = account_engine.detect_billing_violations()
        assert all(v.detected_at != "" for v in violations)

    def test_future_due_no_violation(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_FUTURE)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        violations = account_engine.detect_billing_violations()
        assert len(violations) == 0

    def test_delinquent_account_two_overdue(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.create_invoice("inv-2", "acct-1", due_at=_PAST2)
        account_engine.add_charge("ch-2", "inv-2", 50.0)
        account_engine.issue_invoice("inv-2")
        violations = account_engine.detect_billing_violations()
        delinquent = [v for v in violations if v.operation == "delinquent_account"]
        assert len(delinquent) == 1

    def test_delinquent_marks_account(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.create_invoice("inv-2", "acct-1", due_at=_PAST2)
        account_engine.add_charge("ch-2", "inv-2", 50.0)
        account_engine.issue_invoice("inv-2")
        account_engine.detect_billing_violations()
        acct = account_engine.get_account("acct-1")
        assert acct.status == BillingStatus.DELINQUENT

    def test_single_overdue_no_delinquent(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        violations = account_engine.detect_billing_violations()
        delinquent = [v for v in violations if v.operation == "delinquent_account"]
        assert len(delinquent) == 0

    def test_idempotent_second_scan_empty(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        first = account_engine.detect_billing_violations()
        assert len(first) >= 1
        second = account_engine.detect_billing_violations()
        assert second == ()

    def test_idempotent_violation_count_stable(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.detect_billing_violations()
        count_after_first = account_engine.violation_count
        account_engine.detect_billing_violations()
        assert account_engine.violation_count == count_after_first

    def test_emits_event_on_violations(self, es, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        before = es.event_count
        account_engine.detect_billing_violations()
        assert es.event_count > before

    def test_no_event_when_no_violations(self, es, engine):
        before = es.event_count
        engine.detect_billing_violations()
        assert es.event_count == before

    def test_paid_invoice_not_detected(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.pay_invoice("inv-1")
        violations = account_engine.detect_billing_violations()
        assert len(violations) == 0

    def test_voided_invoice_not_detected(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.void_invoice("inv-1")
        violations = account_engine.detect_billing_violations()
        assert len(violations) == 0

    def test_draft_invoice_not_detected(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        violations = account_engine.detect_billing_violations()
        assert len(violations) == 0


# ===================================================================
# 24. Violations — violations_for_account
# ===================================================================


class TestViolationsForAccount:
    def test_empty(self, account_engine):
        result = account_engine.violations_for_account("acct-1")
        assert result == ()

    def test_returns_tuple(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.detect_billing_violations()
        result = account_engine.violations_for_account("acct-1")
        assert isinstance(result, tuple)

    def test_correct_account(self, engine):
        engine.register_account("a1", "t1", "vendor-a")
        engine.register_account("a2", "t1", "vendor-b")
        engine.create_invoice("inv-1", "a1", due_at=_PAST)
        engine.add_charge("ch-1", "inv-1", 100.0)
        engine.issue_invoice("inv-1")
        engine.detect_billing_violations()
        assert len(engine.violations_for_account("a1")) >= 1
        assert len(engine.violations_for_account("a2")) == 0


# ===================================================================
# 25. Revenue snapshot
# ===================================================================


class TestRevenueSnapshot:
    def test_returns_revenue_snapshot(self, engine):
        snap = engine.revenue_snapshot("snap-1")
        assert isinstance(snap, RevenueSnapshot)

    def test_sets_snapshot_id(self, engine):
        snap = engine.revenue_snapshot("snap-1")
        assert snap.snapshot_id == "snap-1"

    def test_sets_captured_at(self, engine):
        snap = engine.revenue_snapshot("snap-1")
        assert snap.captured_at != ""

    def test_empty_engine_zeros(self, engine):
        snap = engine.revenue_snapshot("snap-1")
        assert snap.total_accounts == 0
        assert snap.total_invoices == 0
        assert snap.total_charges == 0
        assert snap.total_credits == 0
        assert snap.total_penalties == 0
        assert snap.total_disputes == 0
        assert snap.total_recognized_revenue == 0.0
        assert snap.total_pending_revenue == 0.0
        assert snap.total_violations == 0

    def test_snapshot_reflects_state(self, issued_invoice_engine):
        issued_invoice_engine.pay_invoice("inv-1")
        snap = issued_invoice_engine.revenue_snapshot("snap-1")
        assert snap.total_accounts == 1
        assert snap.total_invoices == 1
        assert snap.total_charges == 2
        assert snap.total_recognized_revenue == 150.0
        assert snap.total_pending_revenue == 0.0

    def test_duplicate_raises(self, engine):
        engine.revenue_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.revenue_snapshot("snap-1")

    def test_emits_event(self, es, engine):
        before = es.event_count
        engine.revenue_snapshot("snap-1")
        assert es.event_count > before

    def test_multiple_snapshots(self, engine):
        engine.revenue_snapshot("snap-1")
        engine.revenue_snapshot("snap-2")
        # Should not raise — different IDs

    def test_snapshot_pending_revenue(self, issued_invoice_engine):
        snap = issued_invoice_engine.revenue_snapshot("snap-1")
        assert snap.total_pending_revenue == 150.0

    def test_snapshot_violations_count(self, account_engine):
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.detect_billing_violations()
        snap = account_engine.revenue_snapshot("snap-1")
        assert snap.total_violations >= 1


# ===================================================================
# 26. State hash
# ===================================================================


class TestStateHash:
    def test_returns_string(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_returns_16_char_hex(self, engine):
        h = engine.state_hash()
        assert len(h) == 64
        int(h, 16)  # Should not raise

    def test_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_after_mutation(self, engine):
        h1 = engine.state_hash()
        engine.register_account("a1", "t1", "vendor-a")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_different_states_different_hashes(self, engine):
        engine.register_account("a1", "t1", "vendor-a")
        h1 = engine.state_hash()
        engine.register_account("a2", "t1", "vendor-b")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_empty_engine_consistent(self):
        es1 = EventSpineEngine()
        es2 = EventSpineEngine()
        e1 = BillingRuntimeEngine(es1)
        e2 = BillingRuntimeEngine(es2)
        assert e1.state_hash() == e2.state_hash()


# ===================================================================
# 27. Properties
# ===================================================================


class TestProperties:
    def test_account_count_increments(self, engine):
        assert engine.account_count == 0
        engine.register_account("a1", "t1", "v1")
        assert engine.account_count == 1
        engine.register_account("a2", "t1", "v2")
        assert engine.account_count == 2

    def test_invoice_count_increments(self, account_engine):
        assert account_engine.invoice_count == 0
        account_engine.create_invoice("inv-1", "acct-1")
        assert account_engine.invoice_count == 1

    def test_charge_count_increments(self, invoice_engine):
        assert invoice_engine.charge_count == 0
        invoice_engine.add_charge("ch-1", "inv-1", 100.0)
        assert invoice_engine.charge_count == 1

    def test_credit_count_increments(self, account_engine):
        assert account_engine.credit_count == 0
        account_engine.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        assert account_engine.credit_count == 1

    def test_penalty_count_increments(self, account_engine):
        assert account_engine.penalty_count == 0
        account_engine.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert account_engine.penalty_count == 1

    def test_dispute_count_increments(self, issued_invoice_engine):
        assert issued_invoice_engine.dispute_count == 0
        issued_invoice_engine.open_dispute("disp-1", "inv-1")
        assert issued_invoice_engine.dispute_count == 1

    def test_violation_count_increments(self, account_engine):
        assert account_engine.violation_count == 0
        account_engine.create_invoice("inv-1", "acct-1", due_at=_PAST)
        account_engine.add_charge("ch-1", "inv-1", 100.0)
        account_engine.issue_invoice("inv-1")
        account_engine.detect_billing_violations()
        assert account_engine.violation_count >= 1


# ===================================================================
# 28. Golden Scenario 1: Full invoice lifecycle
# ===================================================================


class TestGoldenFullInvoiceLifecycle:
    def test_lifecycle_account_creation(self, es):
        eng = BillingRuntimeEngine(es)
        acct = eng.register_account("acct-1", "t1", "vendor-a")
        assert acct.status == BillingStatus.ACTIVE

    def test_lifecycle_invoice_creation(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        inv = eng.create_invoice("inv-1", "acct-1")
        assert inv.status == InvoiceStatus.DRAFT

    def test_lifecycle_add_charges(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.create_invoice("inv-1", "acct-1")
        eng.add_charge("ch-1", "inv-1", 100.0)
        eng.add_charge("ch-2", "inv-1", 50.0, kind=ChargeKind.OVERAGE)
        assert eng.charge_count == 2

    def test_lifecycle_issue(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.create_invoice("inv-1", "acct-1")
        eng.add_charge("ch-1", "inv-1", 100.0)
        eng.add_charge("ch-2", "inv-1", 50.0)
        inv = eng.issue_invoice("inv-1")
        assert inv.status == InvoiceStatus.ISSUED
        assert inv.total_amount == 150.0

    def test_lifecycle_pay(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.create_invoice("inv-1", "acct-1")
        eng.add_charge("ch-1", "inv-1", 100.0)
        eng.add_charge("ch-2", "inv-1", 50.0)
        eng.issue_invoice("inv-1")
        inv = eng.pay_invoice("inv-1")
        assert inv.status == InvoiceStatus.PAID

    def test_lifecycle_recognized_revenue(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.create_invoice("inv-1", "acct-1")
        eng.add_charge("ch-1", "inv-1", 100.0)
        eng.add_charge("ch-2", "inv-1", 50.0)
        eng.issue_invoice("inv-1")
        eng.pay_invoice("inv-1")
        assert eng.compute_recognized_revenue() == 150.0

    def test_lifecycle_events_emitted(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.create_invoice("inv-1", "acct-1")
        eng.add_charge("ch-1", "inv-1", 100.0)
        eng.add_charge("ch-2", "inv-1", 50.0)
        eng.issue_invoice("inv-1")
        eng.pay_invoice("inv-1")
        # register + create + 2 charges + issue + pay = 6
        assert es.event_count >= 6

    def test_lifecycle_no_pending_after_pay(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.create_invoice("inv-1", "acct-1")
        eng.add_charge("ch-1", "inv-1", 100.0)
        eng.issue_invoice("inv-1")
        eng.pay_invoice("inv-1")
        assert eng.compute_pending_revenue() == 0.0

    def test_lifecycle_state_hash_changes(self, es):
        eng = BillingRuntimeEngine(es)
        h0 = eng.state_hash()
        eng.register_account("acct-1", "t1", "vendor-a")
        h1 = eng.state_hash()
        eng.create_invoice("inv-1", "acct-1")
        h2 = eng.state_hash()
        eng.add_charge("ch-1", "inv-1", 100.0)
        h3 = eng.state_hash()
        assert len({h0, h1, h2, h3}) == 4


# ===================================================================
# 29. Golden Scenario 2: Dispute flow
# ===================================================================


class TestGoldenDisputeFlow:
    def _setup(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.create_invoice("inv-1", "acct-1")
        eng.add_charge("ch-1", "inv-1", 200.0)
        eng.issue_invoice("inv-1")
        return eng

    def test_dispute_flow_open(self, es):
        eng = self._setup(es)
        d = eng.open_dispute("disp-1", "inv-1", reason="Overcharged", amount=100.0)
        assert d.status == DisputeStatus.OPEN

    def test_dispute_flow_invoice_disputed(self, es):
        eng = self._setup(es)
        eng.open_dispute("disp-1", "inv-1", amount=100.0)
        inv = eng.get_invoice("inv-1")
        assert inv.status == InvoiceStatus.DISPUTED

    def test_dispute_flow_pending_revenue_includes_disputed(self, es):
        eng = self._setup(es)
        eng.open_dispute("disp-1", "inv-1", amount=100.0)
        assert eng.compute_pending_revenue() == 200.0

    def test_dispute_flow_recognized_zero_while_disputed(self, es):
        eng = self._setup(es)
        eng.open_dispute("disp-1", "inv-1", amount=100.0)
        assert eng.compute_recognized_revenue() == 0.0

    def test_dispute_flow_resolve_accepted(self, es):
        eng = self._setup(es)
        eng.open_dispute("disp-1", "inv-1", amount=100.0)
        d = eng.resolve_dispute("disp-1", accepted=True)
        assert d.status == DisputeStatus.RESOLVED_ACCEPTED

    def test_dispute_flow_auto_credit(self, es):
        eng = self._setup(es)
        eng.open_dispute("disp-1", "inv-1", amount=100.0)
        eng.resolve_dispute("disp-1", accepted=True)
        assert eng.credit_count == 1

    def test_dispute_flow_credit_amount(self, es):
        eng = self._setup(es)
        eng.open_dispute("disp-1", "inv-1", amount=100.0)
        eng.resolve_dispute("disp-1", accepted=True)
        credits = eng.credits_for_account("acct-1")
        assert len(credits) == 1
        assert credits[0].amount == 100.0

    def test_dispute_flow_credit_disposition(self, es):
        eng = self._setup(es)
        eng.open_dispute("disp-1", "inv-1", amount=100.0)
        eng.resolve_dispute("disp-1", accepted=True)
        credits = eng.credits_for_account("acct-1")
        assert credits[0].disposition == CreditDisposition.APPLIED

    def test_dispute_flow_events(self, es):
        eng = self._setup(es)
        eng.open_dispute("disp-1", "inv-1", amount=100.0)
        eng.resolve_dispute("disp-1", accepted=True)
        # register + create + charge + issue + dispute_open + credit + resolve = 7
        assert es.event_count >= 7


# ===================================================================
# 30. Golden Scenario 3: Violation detection
# ===================================================================


class TestGoldenViolationDetection:
    def _setup(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.create_invoice("inv-1", "acct-1", due_at=_PAST)
        eng.add_charge("ch-1", "inv-1", 100.0)
        eng.issue_invoice("inv-1")
        eng.create_invoice("inv-2", "acct-1", due_at=_PAST2)
        eng.add_charge("ch-2", "inv-2", 50.0)
        eng.issue_invoice("inv-2")
        return eng

    def test_violation_detection_finds_violations(self, es):
        eng = self._setup(es)
        violations = eng.detect_billing_violations()
        assert len(violations) >= 2  # 2 overdue + 1 delinquent

    def test_violation_detection_overdue_count(self, es):
        eng = self._setup(es)
        violations = eng.detect_billing_violations()
        overdue = [v for v in violations if v.operation == "overdue_invoice"]
        assert len(overdue) == 2

    def test_violation_detection_delinquent_count(self, es):
        eng = self._setup(es)
        violations = eng.detect_billing_violations()
        delinquent = [v for v in violations if v.operation == "delinquent_account"]
        assert len(delinquent) == 1

    def test_violation_detection_invoices_overdue_status(self, es):
        eng = self._setup(es)
        eng.detect_billing_violations()
        assert eng.get_invoice("inv-1").status == InvoiceStatus.OVERDUE
        assert eng.get_invoice("inv-2").status == InvoiceStatus.OVERDUE

    def test_violation_detection_account_delinquent_status(self, es):
        eng = self._setup(es)
        eng.detect_billing_violations()
        assert eng.get_account("acct-1").status == BillingStatus.DELINQUENT

    def test_violation_detection_idempotent(self, es):
        eng = self._setup(es)
        first = eng.detect_billing_violations()
        assert len(first) >= 2
        second = eng.detect_billing_violations()
        assert second == ()

    def test_violation_detection_violation_count(self, es):
        eng = self._setup(es)
        eng.detect_billing_violations()
        assert eng.violation_count >= 3  # 2 overdue + 1 delinquent

    def test_violation_detection_violations_for_account(self, es):
        eng = self._setup(es)
        eng.detect_billing_violations()
        violations = eng.violations_for_account("acct-1")
        assert len(violations) >= 3

    def test_violation_detection_pending_revenue(self, es):
        eng = self._setup(es)
        eng.detect_billing_violations()
        # Overdue invoices count as pending
        assert eng.compute_pending_revenue() == 150.0


# ===================================================================
# 31. Golden Scenario 4: Credit and penalty flow
# ===================================================================


class TestGoldenCreditAndPenaltyFlow:
    def test_credit_flow(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        cr = eng.add_credit("cr-1", "acct-1", "breach-1", 50.0, reason="SLA breach")
        assert cr.disposition == CreditDisposition.APPLIED
        assert cr.amount == 50.0
        assert cr.reason == "SLA breach"
        assert eng.credit_count == 1

    def test_penalty_flow(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        p = eng.add_penalty("pen-1", "acct-1", "breach-1", 100.0, reason="Late delivery")
        assert p.amount == 100.0
        assert p.reason == "Late delivery"
        assert eng.penalty_count == 1

    def test_credit_and_penalty_combined(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        eng.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        assert eng.credit_count == 1
        assert eng.penalty_count == 1

    def test_credits_for_account_correct(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        eng.add_credit("cr-2", "acct-1", "breach-2", 25.0)
        credits = eng.credits_for_account("acct-1")
        assert len(credits) == 2
        amounts = {c.amount for c in credits}
        assert amounts == {50.0, 25.0}

    def test_penalties_for_account_correct(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        eng.add_penalty("pen-2", "acct-1", "breach-2", 75.0)
        penalties = eng.penalties_for_account("acct-1")
        assert len(penalties) == 2
        amounts = {p.amount for p in penalties}
        assert amounts == {100.0, 75.0}

    def test_events_emitted(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        eng.add_penalty("pen-1", "acct-1", "breach-1", 100.0)
        # register + credit + penalty = 3
        assert es.event_count >= 3


# ===================================================================
# 32. Golden Scenario 5: Multi-tenant isolation
# ===================================================================


class TestGoldenMultiTenantIsolation:
    def test_register_two_tenants(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("a1", "t1", "vendor-a")
        eng.register_account("a2", "t2", "vendor-b")
        assert eng.account_count == 2

    def test_accounts_for_tenant_t1(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("a1", "t1", "vendor-a")
        eng.register_account("a2", "t2", "vendor-b")
        t1_accounts = eng.accounts_for_tenant("t1")
        assert len(t1_accounts) == 1
        assert t1_accounts[0].account_id == "a1"

    def test_accounts_for_tenant_t2(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("a1", "t1", "vendor-a")
        eng.register_account("a2", "t2", "vendor-b")
        t2_accounts = eng.accounts_for_tenant("t2")
        assert len(t2_accounts) == 1
        assert t2_accounts[0].account_id == "a2"

    def test_multiple_accounts_per_tenant(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("a1", "t1", "vendor-a")
        eng.register_account("a2", "t1", "vendor-b")
        eng.register_account("a3", "t2", "vendor-c")
        assert len(eng.accounts_for_tenant("t1")) == 2
        assert len(eng.accounts_for_tenant("t2")) == 1

    def test_tenant_isolation_invoices(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("a1", "t1", "vendor-a")
        eng.register_account("a2", "t2", "vendor-b")
        eng.create_invoice("inv-1", "a1")
        eng.create_invoice("inv-2", "a2")
        assert len(eng.invoices_for_account("a1")) == 1
        assert len(eng.invoices_for_account("a2")) == 1

    def test_tenant_isolation_credits(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("a1", "t1", "vendor-a")
        eng.register_account("a2", "t2", "vendor-b")
        eng.add_credit("cr-1", "a1", "breach-1", 50.0)
        eng.add_credit("cr-2", "a2", "breach-2", 25.0)
        assert len(eng.credits_for_account("a1")) == 1
        assert len(eng.credits_for_account("a2")) == 1

    def test_tenant_isolation_penalties(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("a1", "t1", "vendor-a")
        eng.register_account("a2", "t2", "vendor-b")
        eng.add_penalty("pen-1", "a1", "breach-1", 100.0)
        eng.add_penalty("pen-2", "a2", "breach-2", 75.0)
        assert len(eng.penalties_for_account("a1")) == 1
        assert len(eng.penalties_for_account("a2")) == 1

    def test_nonexistent_tenant_empty(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("a1", "t1", "vendor-a")
        assert eng.accounts_for_tenant("t99") == ()


# ===================================================================
# 33. Golden Scenario 6: Revenue snapshot with mixed state
# ===================================================================


class TestGoldenRevenueSnapshotMixedState:
    def _setup(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")

        # Paid invoice
        eng.create_invoice("inv-paid", "acct-1")
        eng.add_charge("ch-paid", "inv-paid", 100.0)
        eng.issue_invoice("inv-paid")
        eng.pay_invoice("inv-paid")

        # Issued invoice
        eng.create_invoice("inv-issued", "acct-1")
        eng.add_charge("ch-issued", "inv-issued", 200.0)
        eng.issue_invoice("inv-issued")

        # Disputed invoice
        eng.create_invoice("inv-disputed", "acct-1")
        eng.add_charge("ch-disputed", "inv-disputed", 300.0)
        eng.issue_invoice("inv-disputed")
        eng.open_dispute("disp-1", "inv-disputed", amount=150.0)

        return eng

    def test_snapshot_total_accounts(self, es):
        eng = self._setup(es)
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_accounts == 1

    def test_snapshot_total_invoices(self, es):
        eng = self._setup(es)
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_invoices == 3

    def test_snapshot_total_charges(self, es):
        eng = self._setup(es)
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_charges == 3

    def test_snapshot_total_disputes(self, es):
        eng = self._setup(es)
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_disputes == 1

    def test_snapshot_recognized_revenue(self, es):
        eng = self._setup(es)
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_recognized_revenue == 100.0

    def test_snapshot_pending_revenue(self, es):
        eng = self._setup(es)
        snap = eng.revenue_snapshot("snap-1")
        # Issued (200) + Disputed (300) = 500
        assert snap.total_pending_revenue == 500.0

    def test_snapshot_no_violations(self, es):
        eng = self._setup(es)
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_violations == 0

    def test_snapshot_after_violations(self, es):
        eng = BillingRuntimeEngine(es)
        eng.register_account("acct-1", "t1", "vendor-a")
        eng.create_invoice("inv-1", "acct-1", due_at=_PAST)
        eng.add_charge("ch-1", "inv-1", 100.0)
        eng.issue_invoice("inv-1")
        eng.detect_billing_violations()
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_violations >= 1

    def test_snapshot_credits_and_penalties(self, es):
        eng = self._setup(es)
        eng.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        eng.add_penalty("pen-1", "acct-1", "breach-1", 75.0)
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_credits == 1
        assert snap.total_penalties == 1

    def test_snapshot_after_resolve_dispute_with_credit(self, es):
        eng = self._setup(es)
        eng.resolve_dispute("disp-1", accepted=True)
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_credits == 1
        assert snap.total_disputes == 1

    def test_snapshot_full_counts(self, es):
        eng = self._setup(es)
        eng.add_credit("cr-1", "acct-1", "breach-1", 50.0)
        eng.add_penalty("pen-1", "acct-1", "breach-1", 75.0)
        snap = eng.revenue_snapshot("snap-1")
        assert snap.total_accounts == 1
        assert snap.total_invoices == 3
        assert snap.total_charges == 3
        assert snap.total_credits == 1
        assert snap.total_penalties == 1
        assert snap.total_disputes == 1
        assert snap.total_recognized_revenue == 100.0
        assert snap.total_pending_revenue == 500.0
