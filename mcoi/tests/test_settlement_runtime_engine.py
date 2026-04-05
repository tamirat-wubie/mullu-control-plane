"""Comprehensive tests for SettlementRuntimeEngine.

Covers: settlement CRUD and lifecycle, payment recording, cash application,
credit application, collection case management, dunning notices, refunds,
writeoffs, dispute handling, revenue computation, violation detection,
aging snapshots, state hashing, and six golden scenarios.
"""

import pytest

from mcoi_runtime.contracts.settlement_runtime import (
    AgingSnapshot,
    CashApplication,
    CollectionCase,
    CollectionStatus,
    DunningNotice,
    DunningSeverity,
    PaymentMethodKind,
    PaymentRecord,
    PaymentStatus,
    RefundRecord,
    SettlementClosureReport,
    SettlementDecision,
    SettlementRecord,
    SettlementStatus,
    WriteoffDisposition,
    WriteoffRecord,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.settlement_runtime import SettlementRuntimeEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def engine(es):
    return SettlementRuntimeEngine(es)


@pytest.fixture()
def settlement_engine(engine):
    """Engine with a single settlement created."""
    engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
    return engine


@pytest.fixture()
def paid_engine(settlement_engine):
    """Engine with a settlement and a recorded payment."""
    settlement_engine.record_payment("pay-1", "inv-1", "acct-1", 1000.0)
    return settlement_engine


@pytest.fixture()
def partial_engine(settlement_engine):
    """Engine with a settlement and a partial payment applied."""
    settlement_engine.record_payment("pay-1", "inv-1", "acct-1", 400.0)
    settlement_engine.apply_cash("app-1", "sett-1", "pay-1", 400.0)
    return settlement_engine


@pytest.fixture()
def collection_engine(settlement_engine):
    """Engine with a settlement and an open collection case."""
    settlement_engine.open_collection_case("case-1", "inv-1", "acct-1", 1000.0)
    return settlement_engine


# ===========================================================================
# Settlement CRUD
# ===========================================================================


class TestCreateSettlement:
    def test_create_settlement_returns_record(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        assert isinstance(s, SettlementRecord)

    def test_create_settlement_fields(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        assert s.settlement_id == "sett-1"
        assert s.invoice_id == "inv-1"
        assert s.account_id == "acct-1"
        assert s.total_amount == 500.0

    def test_create_settlement_open_status(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        assert s.status == SettlementStatus.OPEN

    def test_create_settlement_outstanding_equals_total(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 750.0)
        assert s.outstanding == 750.0

    def test_create_settlement_paid_amount_zero(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        assert s.paid_amount == 0.0

    def test_create_settlement_credit_applied_zero(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        assert s.credit_applied == 0.0

    def test_create_settlement_default_currency(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        assert s.currency == "USD"

    def test_create_settlement_custom_currency(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0, currency="EUR")
        assert s.currency == "EUR"

    def test_create_settlement_has_created_at(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        assert s.created_at is not None

    def test_create_settlement_increments_count(self, engine):
        assert engine.settlement_count == 0
        engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        assert engine.settlement_count == 1

    def test_create_settlement_emits_event(self, es, engine):
        initial = es.event_count
        engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        assert es.event_count == initial + 1

    def test_create_settlement_duplicate_raises(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate settlement_id"):
            engine.create_settlement("sett-1", "inv-2", "acct-1", 500.0)

    def test_create_settlement_same_invoice_raises(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        with pytest.raises(RuntimeCoreInvariantError, match="already has a settlement"):
            engine.create_settlement("sett-2", "inv-1", "acct-1", 500.0)

    def test_create_settlement_same_invoice_message_is_bounded(self, engine):
        engine.create_settlement("sett-1", "inv-secret", "acct-1", 500.0)
        with pytest.raises(RuntimeCoreInvariantError, match="already has a settlement") as exc_info:
            engine.create_settlement("sett-2", "inv-secret", "acct-1", 500.0)
        message = str(exc_info.value)
        assert "already has a settlement" in message
        assert "inv-secret" not in message
        assert "sett-1" not in message

    def test_create_multiple_settlements_different_invoices(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        engine.create_settlement("sett-2", "inv-2", "acct-1", 300.0)
        assert engine.settlement_count == 2


class TestGetSettlement:
    def test_get_settlement_returns_record(self, settlement_engine):
        s = settlement_engine.get_settlement("sett-1")
        assert isinstance(s, SettlementRecord)
        assert s.settlement_id == "sett-1"

    def test_get_settlement_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown settlement_id"):
            engine.get_settlement("nonexistent")


class TestSettlementForInvoice:
    def test_settlement_for_invoice_returns_record(self, settlement_engine):
        s = settlement_engine.settlement_for_invoice("inv-1")
        assert s.settlement_id == "sett-1"

    def test_settlement_for_invoice_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="No settlement for invoice"):
            engine.settlement_for_invoice("inv-nonexistent")


class TestSettlementsForAccount:
    def test_settlements_for_account_returns_tuple(self, settlement_engine):
        result = settlement_engine.settlements_for_account("acct-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_settlements_for_account_empty(self, engine):
        result = engine.settlements_for_account("acct-nonexistent")
        assert result == ()

    def test_settlements_for_account_multiple(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        engine.create_settlement("sett-2", "inv-2", "acct-1", 300.0)
        result = engine.settlements_for_account("acct-1")
        assert len(result) == 2

    def test_settlements_for_account_filters_by_account(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        engine.create_settlement("sett-2", "inv-2", "acct-2", 300.0)
        result = engine.settlements_for_account("acct-1")
        assert len(result) == 1
        assert result[0].account_id == "acct-1"


# ===========================================================================
# Payments
# ===========================================================================


class TestRecordPayment:
    def test_record_payment_returns_record(self, engine):
        p = engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert isinstance(p, PaymentRecord)

    def test_record_payment_fields(self, engine):
        p = engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert p.payment_id == "pay-1"
        assert p.invoice_id == "inv-1"
        assert p.account_id == "acct-1"
        assert p.amount == 100.0

    def test_record_payment_cleared_status(self, engine):
        p = engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert p.status == PaymentStatus.CLEARED

    def test_record_payment_default_currency(self, engine):
        p = engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert p.currency == "USD"

    def test_record_payment_custom_currency(self, engine):
        p = engine.record_payment("pay-1", "inv-1", "acct-1", 100.0, currency="GBP")
        assert p.currency == "GBP"

    def test_record_payment_default_method(self, engine):
        p = engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert p.method == PaymentMethodKind.BANK_TRANSFER

    def test_record_payment_custom_method(self, engine):
        p = engine.record_payment(
            "pay-1", "inv-1", "acct-1", 100.0,
            method=PaymentMethodKind.CREDIT_CARD,
        )
        assert p.method == PaymentMethodKind.CREDIT_CARD

    def test_record_payment_default_reference(self, engine):
        p = engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert p.reference == ""

    def test_record_payment_custom_reference(self, engine):
        p = engine.record_payment("pay-1", "inv-1", "acct-1", 100.0, reference="REF-123")
        assert p.reference == "REF-123"

    def test_record_payment_has_received_at(self, engine):
        p = engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert p.received_at is not None

    def test_record_payment_increments_count(self, engine):
        assert engine.payment_count == 0
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert engine.payment_count == 1

    def test_record_payment_emits_event(self, es, engine):
        initial = es.event_count
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert es.event_count == initial + 1

    def test_record_payment_duplicate_raises(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate payment_id"):
            engine.record_payment("pay-1", "inv-2", "acct-1", 200.0)


class TestGetPayment:
    def test_get_payment_returns_record(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        p = engine.get_payment("pay-1")
        assert p.payment_id == "pay-1"

    def test_get_payment_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown payment_id"):
            engine.get_payment("nonexistent")


class TestPaymentsForInvoice:
    def test_payments_for_invoice_returns_tuple(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        result = engine.payments_for_invoice("inv-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_payments_for_invoice_empty(self, engine):
        assert engine.payments_for_invoice("inv-nonexistent") == ()

    def test_payments_for_invoice_multiple(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_payment("pay-2", "inv-1", "acct-1", 200.0)
        result = engine.payments_for_invoice("inv-1")
        assert len(result) == 2

    def test_payments_for_invoice_filters(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_payment("pay-2", "inv-2", "acct-1", 200.0)
        result = engine.payments_for_invoice("inv-1")
        assert len(result) == 1


# ===========================================================================
# Cash Application
# ===========================================================================


class TestApplyCash:
    def test_apply_cash_returns_application(self, paid_engine):
        app = paid_engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        assert isinstance(app, CashApplication)

    def test_apply_cash_fields(self, paid_engine):
        app = paid_engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        assert app.application_id == "app-1"
        assert app.settlement_id == "sett-1"
        assert app.payment_id == "pay-1"
        assert app.amount == 500.0

    def test_apply_cash_has_applied_at(self, paid_engine):
        app = paid_engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        assert app.applied_at is not None

    def test_apply_cash_updates_paid_amount(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        s = paid_engine.get_settlement("sett-1")
        assert s.paid_amount == 500.0

    def test_apply_cash_updates_outstanding(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        s = paid_engine.get_settlement("sett-1")
        assert s.outstanding == 500.0

    def test_apply_cash_full_amount_settles(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        s = paid_engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.SETTLED
        assert s.outstanding == 0.0
        assert s.paid_amount == 1000.0

    def test_apply_cash_partial_amount_partial_status(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 300.0)
        s = paid_engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.PARTIAL

    def test_apply_cash_caps_at_outstanding(self, paid_engine):
        app = paid_engine.apply_cash("app-1", "sett-1", "pay-1", 5000.0)
        assert app.amount == 1000.0  # capped at outstanding
        s = paid_engine.get_settlement("sett-1")
        assert s.outstanding == 0.0
        assert s.status == SettlementStatus.SETTLED

    def test_apply_cash_increments_count(self, paid_engine):
        assert paid_engine.application_count == 0
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        assert paid_engine.application_count == 1

    def test_apply_cash_emits_event(self, es, paid_engine):
        initial = es.event_count
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        assert es.event_count > initial

    def test_apply_cash_duplicate_raises(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate application_id"):
            paid_engine.apply_cash("app-1", "sett-1", "pay-1", 200.0)

    def test_apply_cash_terminal_settlement_raises(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        # Settlement is now SETTLED
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot apply cash"):
            paid_engine.apply_cash("app-2", "sett-1", "pay-1", 100.0)

    def test_apply_cash_unknown_payment_raises(self, settlement_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown payment_id"):
            settlement_engine.apply_cash("app-1", "sett-1", "pay-nonexistent", 100.0)

    def test_apply_cash_unknown_settlement_raises(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown settlement_id"):
            engine.apply_cash("app-1", "sett-nonexistent", "pay-1", 100.0)

    def test_apply_cash_multiple_applications(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 300.0)
        paid_engine.apply_cash("app-2", "sett-1", "pay-1", 700.0)
        s = paid_engine.get_settlement("sett-1")
        assert s.paid_amount == 1000.0
        assert s.outstanding == 0.0
        assert s.status == SettlementStatus.SETTLED

    def test_apply_cash_second_application_capped(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 800.0)
        app2 = paid_engine.apply_cash("app-2", "sett-1", "pay-1", 500.0)
        assert app2.amount == 200.0  # capped at remaining 200

    def test_apply_cash_written_off_settlement_raises(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 100.0)
        engine.record_writeoff("wo-1", "sett-1", "acct-1", 100.0)
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot apply cash"):
            engine.apply_cash("app-1", "sett-1", "pay-1", 50.0)


class TestApplyCredit:
    def test_apply_credit_returns_application(self, settlement_engine):
        app = settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 200.0)
        assert isinstance(app, CashApplication)

    def test_apply_credit_fields(self, settlement_engine):
        app = settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 200.0)
        assert app.application_id == "app-1"
        assert app.settlement_id == "sett-1"
        assert app.payment_id == "credit-1"
        assert app.amount == 200.0

    def test_apply_credit_updates_credit_applied(self, settlement_engine):
        settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 200.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.credit_applied == 200.0

    def test_apply_credit_updates_outstanding(self, settlement_engine):
        settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 200.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.outstanding == 800.0

    def test_apply_credit_does_not_update_paid_amount(self, settlement_engine):
        settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 200.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.paid_amount == 0.0

    def test_apply_credit_partial_status(self, settlement_engine):
        settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 200.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.PARTIAL

    def test_apply_credit_full_settles(self, settlement_engine):
        settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 1000.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.SETTLED
        assert s.outstanding == 0.0

    def test_apply_credit_caps_at_outstanding(self, settlement_engine):
        app = settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 5000.0)
        assert app.amount == 1000.0

    def test_apply_credit_duplicate_raises(self, settlement_engine):
        settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 200.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate application_id"):
            settlement_engine.apply_credit("app-1", "sett-1", "credit-2", 100.0)

    def test_apply_credit_terminal_settlement_raises(self, settlement_engine):
        settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 1000.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot apply credit"):
            settlement_engine.apply_credit("app-2", "sett-1", "credit-2", 100.0)

    def test_apply_credit_emits_event(self, es, settlement_engine):
        initial = es.event_count
        settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 200.0)
        assert es.event_count > initial

    def test_apply_credit_increments_application_count(self, settlement_engine):
        assert settlement_engine.application_count == 0
        settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 200.0)
        assert settlement_engine.application_count == 1


class TestApplicationsForSettlement:
    def test_applications_for_settlement_returns_tuple(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        result = paid_engine.applications_for_settlement("sett-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_applications_for_settlement_empty(self, settlement_engine):
        result = settlement_engine.applications_for_settlement("sett-1")
        assert result == ()

    def test_applications_for_settlement_multiple(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 300.0)
        paid_engine.apply_cash("app-2", "sett-1", "pay-1", 200.0)
        result = paid_engine.applications_for_settlement("sett-1")
        assert len(result) == 2

    def test_applications_for_settlement_filters(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.create_settlement("sett-2", "inv-2", "acct-1", 500.0)
        engine.record_payment("pay-1", "inv-1", "acct-1", 1000.0)
        engine.apply_cash("app-1", "sett-1", "pay-1", 300.0)
        engine.apply_credit("app-2", "sett-2", "credit-1", 100.0)
        result = engine.applications_for_settlement("sett-1")
        assert len(result) == 1
        assert result[0].application_id == "app-1"


# ===========================================================================
# Collection Cases
# ===========================================================================


class TestOpenCollectionCase:
    def test_open_collection_case_returns_record(self, engine):
        c = engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        assert isinstance(c, CollectionCase)

    def test_open_collection_case_fields(self, engine):
        c = engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        assert c.case_id == "case-1"
        assert c.invoice_id == "inv-1"
        assert c.account_id == "acct-1"
        assert c.outstanding_amount == 500.0

    def test_open_collection_case_open_status(self, engine):
        c = engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        assert c.status == CollectionStatus.OPEN

    def test_open_collection_case_dunning_count_zero(self, engine):
        c = engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        assert c.dunning_count == 0

    def test_open_collection_case_has_opened_at(self, engine):
        c = engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        assert c.opened_at is not None

    def test_open_collection_case_increments_count(self, engine):
        assert engine.collection_count == 0
        engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        assert engine.collection_count == 1

    def test_open_collection_case_emits_event(self, es, engine):
        initial = es.event_count
        engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        assert es.event_count == initial + 1

    def test_open_collection_case_duplicate_raises(self, engine):
        engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate case_id"):
            engine.open_collection_case("case-1", "inv-2", "acct-1", 300.0)


class TestGetCollectionCase:
    def test_get_collection_case_returns_record(self, collection_engine):
        c = collection_engine.get_collection_case("case-1")
        assert c.case_id == "case-1"

    def test_get_collection_case_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.get_collection_case("nonexistent")


class TestEscalateCollection:
    def test_escalate_collection_returns_record(self, collection_engine):
        c = collection_engine.escalate_collection("case-1")
        assert isinstance(c, CollectionCase)
        assert c.status == CollectionStatus.ESCALATED

    def test_escalate_collection_emits_event(self, es, collection_engine):
        initial = es.event_count
        collection_engine.escalate_collection("case-1")
        assert es.event_count > initial

    def test_escalate_resolved_raises(self, collection_engine):
        collection_engine.resolve_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate"):
            collection_engine.escalate_collection("case-1")

    def test_escalate_closed_raises(self, collection_engine):
        collection_engine.close_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate"):
            collection_engine.escalate_collection("case-1")

    def test_escalate_from_in_progress(self, collection_engine):
        collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        c = collection_engine.escalate_collection("case-1")
        assert c.status == CollectionStatus.ESCALATED

    def test_escalate_from_paused(self, collection_engine):
        collection_engine.pause_collection("case-1")
        c = collection_engine.escalate_collection("case-1")
        assert c.status == CollectionStatus.ESCALATED


class TestPauseCollection:
    def test_pause_collection_returns_paused(self, collection_engine):
        c = collection_engine.pause_collection("case-1")
        assert c.status == CollectionStatus.PAUSED

    def test_pause_collection_emits_event(self, es, collection_engine):
        initial = es.event_count
        collection_engine.pause_collection("case-1")
        assert es.event_count > initial

    def test_pause_resolved_raises(self, collection_engine):
        collection_engine.resolve_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot pause"):
            collection_engine.pause_collection("case-1")

    def test_pause_closed_raises(self, collection_engine):
        collection_engine.close_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot pause"):
            collection_engine.pause_collection("case-1")

    def test_pause_already_paused_succeeds(self, collection_engine):
        collection_engine.pause_collection("case-1")
        c = collection_engine.pause_collection("case-1")
        assert c.status == CollectionStatus.PAUSED


class TestResumeCollection:
    def test_resume_collection_returns_in_progress(self, collection_engine):
        collection_engine.pause_collection("case-1")
        c = collection_engine.resume_collection("case-1")
        assert c.status == CollectionStatus.IN_PROGRESS

    def test_resume_collection_emits_event(self, es, collection_engine):
        collection_engine.pause_collection("case-1")
        initial = es.event_count
        collection_engine.resume_collection("case-1")
        assert es.event_count > initial

    def test_resume_not_paused_raises(self, collection_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="resume paused"):
            collection_engine.resume_collection("case-1")

    def test_resume_escalated_raises(self, collection_engine):
        collection_engine.escalate_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="resume paused"):
            collection_engine.resume_collection("case-1")

    def test_resume_resolved_raises(self, collection_engine):
        collection_engine.resolve_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="resume paused"):
            collection_engine.resume_collection("case-1")


class TestResolveCollection:
    def test_resolve_collection_returns_resolved(self, collection_engine):
        c = collection_engine.resolve_collection("case-1")
        assert c.status == CollectionStatus.RESOLVED

    def test_resolve_collection_zeroes_outstanding(self, collection_engine):
        c = collection_engine.resolve_collection("case-1")
        assert c.outstanding_amount == 0.0

    def test_resolve_collection_sets_closed_at(self, collection_engine):
        c = collection_engine.resolve_collection("case-1")
        assert c.closed_at is not None

    def test_resolve_collection_emits_event(self, es, collection_engine):
        initial = es.event_count
        collection_engine.resolve_collection("case-1")
        assert es.event_count > initial

    def test_resolve_already_resolved_raises(self, collection_engine):
        collection_engine.resolve_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot resolve"):
            collection_engine.resolve_collection("case-1")

    def test_resolve_closed_raises(self, collection_engine):
        collection_engine.close_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot resolve"):
            collection_engine.resolve_collection("case-1")


class TestCloseCollection:
    def test_close_collection_returns_closed(self, collection_engine):
        c = collection_engine.close_collection("case-1")
        assert c.status == CollectionStatus.CLOSED

    def test_close_collection_sets_closed_at(self, collection_engine):
        c = collection_engine.close_collection("case-1")
        assert c.closed_at is not None

    def test_close_collection_preserves_outstanding(self, collection_engine):
        c = collection_engine.close_collection("case-1")
        assert c.outstanding_amount == 1000.0

    def test_close_collection_emits_event(self, es, collection_engine):
        initial = es.event_count
        collection_engine.close_collection("case-1")
        assert es.event_count > initial

    def test_close_already_closed_raises(self, collection_engine):
        collection_engine.close_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Collection already closed"):
            collection_engine.close_collection("case-1")

    def test_close_resolved_collection_succeeds(self, collection_engine):
        collection_engine.resolve_collection("case-1")
        c = collection_engine.close_collection("case-1")
        assert c.status == CollectionStatus.CLOSED


class TestCollectionsForAccount:
    def test_collections_for_account_returns_tuple(self, collection_engine):
        result = collection_engine.collections_for_account("acct-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_collections_for_account_empty(self, engine):
        assert engine.collections_for_account("acct-1") == ()

    def test_collections_for_account_filters(self, engine):
        engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        engine.open_collection_case("case-2", "inv-2", "acct-2", 300.0)
        result = engine.collections_for_account("acct-1")
        assert len(result) == 1
        assert result[0].account_id == "acct-1"


# ===========================================================================
# Dunning Notices
# ===========================================================================


class TestIssueDunningNotice:
    def test_issue_dunning_notice_returns_record(self, collection_engine):
        n = collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert isinstance(n, DunningNotice)

    def test_issue_dunning_notice_fields(self, collection_engine):
        n = collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert n.notice_id == "dn-1"
        assert n.case_id == "case-1"
        assert n.account_id == "acct-1"

    def test_issue_dunning_notice_default_severity(self, collection_engine):
        n = collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert n.severity == DunningSeverity.REMINDER

    def test_issue_dunning_notice_custom_severity(self, collection_engine):
        n = collection_engine.issue_dunning_notice(
            "dn-1", "case-1", "acct-1", severity=DunningSeverity.FINAL_NOTICE,
        )
        assert n.severity == DunningSeverity.FINAL_NOTICE

    def test_issue_dunning_notice_default_message(self, collection_engine):
        n = collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert n.message == ""

    def test_issue_dunning_notice_custom_message(self, collection_engine):
        n = collection_engine.issue_dunning_notice(
            "dn-1", "case-1", "acct-1", message="Please pay immediately",
        )
        assert n.message == "Please pay immediately"

    def test_issue_dunning_notice_has_sent_at(self, collection_engine):
        n = collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert n.sent_at is not None

    def test_issue_dunning_notice_increments_dunning_count_on_case(self, collection_engine):
        collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        c = collection_engine.get_collection_case("case-1")
        assert c.dunning_count == 1

    def test_issue_dunning_notice_increments_engine_dunning_count(self, collection_engine):
        assert collection_engine.dunning_count == 0
        collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert collection_engine.dunning_count == 1

    def test_issue_dunning_notice_transitions_open_to_in_progress(self, collection_engine):
        c = collection_engine.get_collection_case("case-1")
        assert c.status == CollectionStatus.OPEN
        collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        c = collection_engine.get_collection_case("case-1")
        assert c.status == CollectionStatus.IN_PROGRESS

    def test_issue_dunning_notice_preserves_non_open_status(self, collection_engine):
        collection_engine.escalate_collection("case-1")
        collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        c = collection_engine.get_collection_case("case-1")
        assert c.status == CollectionStatus.ESCALATED

    def test_issue_dunning_notice_emits_event(self, es, collection_engine):
        initial = es.event_count
        collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert es.event_count > initial

    def test_issue_dunning_notice_duplicate_raises(self, collection_engine):
        collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate notice_id"):
            collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")

    def test_issue_dunning_notice_terminal_collection_raises(self, collection_engine):
        collection_engine.resolve_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot issue dunning"):
            collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")

    def test_issue_dunning_notice_closed_collection_raises(self, collection_engine):
        collection_engine.close_collection("case-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot issue dunning"):
            collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")

    def test_issue_multiple_dunning_notices(self, collection_engine):
        for i in range(5):
            collection_engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")
        c = collection_engine.get_collection_case("case-1")
        assert c.dunning_count == 5
        assert collection_engine.dunning_count == 5


class TestNoticesForCase:
    def test_notices_for_case_returns_tuple(self, collection_engine):
        collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        result = collection_engine.notices_for_case("case-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_notices_for_case_empty(self, collection_engine):
        assert collection_engine.notices_for_case("case-1") == ()

    def test_notices_for_case_filters(self, engine):
        engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        engine.open_collection_case("case-2", "inv-2", "acct-2", 300.0)
        engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        engine.issue_dunning_notice("dn-2", "case-2", "acct-2")
        result = engine.notices_for_case("case-1")
        assert len(result) == 1
        assert result[0].case_id == "case-1"


# ===========================================================================
# Refunds
# ===========================================================================


class TestRecordRefund:
    def test_record_refund_returns_record(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        r = engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        assert isinstance(r, RefundRecord)

    def test_record_refund_fields(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        r = engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        assert r.refund_id == "ref-1"
        assert r.payment_id == "pay-1"
        assert r.account_id == "acct-1"
        assert r.amount == 50.0

    def test_record_refund_default_reason(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        r = engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        assert r.reason == ""

    def test_record_refund_custom_reason(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        r = engine.record_refund("ref-1", "pay-1", "acct-1", 50.0, reason="duplicate")
        assert r.reason == "duplicate"

    def test_record_refund_has_refunded_at(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        r = engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        assert r.refunded_at is not None

    def test_record_refund_increments_count(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        assert engine.refund_count == 0
        engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        assert engine.refund_count == 1

    def test_record_refund_emits_event(self, es, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        initial = es.event_count
        engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        assert es.event_count > initial

    def test_record_refund_duplicate_raises(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate refund_id"):
            engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)

    def test_record_refund_unknown_payment_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown payment_id"):
            engine.record_refund("ref-1", "pay-nonexistent", "acct-1", 50.0)

    def test_record_refund_partial_keeps_cleared(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        p = engine.get_payment("pay-1")
        assert p.status == PaymentStatus.CLEARED

    def test_record_refund_full_reverses_payment(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 100.0)
        p = engine.get_payment("pay-1")
        assert p.status == PaymentStatus.REVERSED

    def test_record_refund_incremental_full_reverses_payment(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 60.0)
        p = engine.get_payment("pay-1")
        assert p.status == PaymentStatus.CLEARED
        engine.record_refund("ref-2", "pay-1", "acct-1", 40.0)
        p = engine.get_payment("pay-1")
        assert p.status == PaymentStatus.REVERSED

    def test_record_refund_over_amount_reverses_payment(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 150.0)
        p = engine.get_payment("pay-1")
        assert p.status == PaymentStatus.REVERSED


class TestRefundsForPayment:
    def test_refunds_for_payment_returns_tuple(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        result = engine.refunds_for_payment("pay-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_refunds_for_payment_empty(self, engine):
        assert engine.refunds_for_payment("pay-nonexistent") == ()

    def test_refunds_for_payment_filters(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_payment("pay-2", "inv-2", "acct-1", 200.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        engine.record_refund("ref-2", "pay-2", "acct-1", 75.0)
        result = engine.refunds_for_payment("pay-1")
        assert len(result) == 1
        assert result[0].payment_id == "pay-1"


# ===========================================================================
# Writeoffs
# ===========================================================================


class TestRecordWriteoff:
    def test_record_writeoff_returns_record(self, settlement_engine):
        wo = settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        assert isinstance(wo, WriteoffRecord)

    def test_record_writeoff_fields(self, settlement_engine):
        wo = settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        assert wo.writeoff_id == "wo-1"
        assert wo.settlement_id == "sett-1"
        assert wo.account_id == "acct-1"
        assert wo.amount == 200.0

    def test_record_writeoff_disposition_approved(self, settlement_engine):
        wo = settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        assert wo.disposition == WriteoffDisposition.APPROVED

    def test_record_writeoff_default_reason(self, settlement_engine):
        wo = settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        assert wo.reason == ""

    def test_record_writeoff_custom_reason(self, settlement_engine):
        wo = settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0, reason="uncollectable")
        assert wo.reason == "uncollectable"

    def test_record_writeoff_has_written_off_at(self, settlement_engine):
        wo = settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        assert wo.written_off_at is not None

    def test_record_writeoff_reduces_outstanding(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.outstanding == 800.0

    def test_record_writeoff_full_marks_written_off(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 1000.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.WRITTEN_OFF
        assert s.outstanding == 0.0

    def test_record_writeoff_partial_keeps_status(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 500.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.OPEN

    def test_record_writeoff_caps_at_outstanding(self, settlement_engine):
        wo = settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 5000.0)
        assert wo.amount == 1000.0
        s = settlement_engine.get_settlement("sett-1")
        assert s.outstanding == 0.0

    def test_record_writeoff_increments_count(self, settlement_engine):
        assert settlement_engine.writeoff_count == 0
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        assert settlement_engine.writeoff_count == 1

    def test_record_writeoff_emits_event(self, es, settlement_engine):
        initial = es.event_count
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        assert es.event_count > initial

    def test_record_writeoff_duplicate_raises(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate writeoff_id"):
            settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 100.0)

    def test_record_writeoff_terminal_settlement_raises(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 1000.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot write off"):
            settlement_engine.record_writeoff("wo-2", "sett-1", "acct-1", 100.0)

    def test_record_writeoff_settled_raises(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot write off"):
            paid_engine.record_writeoff("wo-1", "sett-1", "acct-1", 100.0)

    def test_record_writeoff_incremental_full(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 400.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.outstanding == 600.0
        assert s.status == SettlementStatus.OPEN
        settlement_engine.record_writeoff("wo-2", "sett-1", "acct-1", 600.0)
        s = settlement_engine.get_settlement("sett-1")
        assert s.outstanding == 0.0
        assert s.status == SettlementStatus.WRITTEN_OFF


class TestWriteoffsForSettlement:
    def test_writeoffs_for_settlement_returns_tuple(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        result = settlement_engine.writeoffs_for_settlement("sett-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_writeoffs_for_settlement_empty(self, settlement_engine):
        assert settlement_engine.writeoffs_for_settlement("sett-1") == ()

    def test_writeoffs_for_settlement_filters(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.create_settlement("sett-2", "inv-2", "acct-1", 500.0)
        engine.record_writeoff("wo-1", "sett-1", "acct-1", 200.0)
        engine.record_writeoff("wo-2", "sett-2", "acct-1", 100.0)
        result = engine.writeoffs_for_settlement("sett-1")
        assert len(result) == 1
        assert result[0].settlement_id == "sett-1"


# ===========================================================================
# Dispute
# ===========================================================================


class TestMarkSettlementDisputed:
    def test_mark_settlement_disputed_returns_record(self, settlement_engine):
        s = settlement_engine.mark_settlement_disputed("sett-1")
        assert isinstance(s, SettlementRecord)
        assert s.status == SettlementStatus.DISPUTED

    def test_mark_settlement_disputed_preserves_amounts(self, settlement_engine):
        s = settlement_engine.mark_settlement_disputed("sett-1")
        assert s.total_amount == 1000.0
        assert s.outstanding == 1000.0

    def test_mark_settlement_disputed_emits_event(self, es, settlement_engine):
        initial = es.event_count
        settlement_engine.mark_settlement_disputed("sett-1")
        assert es.event_count > initial

    def test_mark_settlement_disputed_settled_raises(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot dispute"):
            paid_engine.mark_settlement_disputed("sett-1")

    def test_mark_settlement_disputed_written_off_raises(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 1000.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot dispute"):
            settlement_engine.mark_settlement_disputed("sett-1")

    def test_mark_settlement_disputed_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown settlement_id"):
            engine.mark_settlement_disputed("nonexistent")

    def test_mark_settlement_disputed_from_partial(self, partial_engine):
        s = partial_engine.mark_settlement_disputed("sett-1")
        assert s.status == SettlementStatus.DISPUTED


# ===========================================================================
# Revenue Computations
# ===========================================================================


class TestComputeTotalCollected:
    def test_compute_total_collected_empty(self, engine):
        assert engine.compute_total_collected() == 0.0

    def test_compute_total_collected_single_payment(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        assert engine.compute_total_collected() == 500.0

    def test_compute_total_collected_multiple_payments(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        engine.record_payment("pay-2", "inv-2", "acct-1", 300.0)
        assert engine.compute_total_collected() == 800.0

    def test_compute_total_collected_minus_refunds(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 100.0)
        assert engine.compute_total_collected() == 400.0

    def test_compute_total_collected_reversed_payment_excluded(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 500.0)
        # Payment is reversed (not CLEARED), so excluded; refunds still subtracted
        assert engine.compute_total_collected() == 0.0

    def test_compute_total_collected_non_negative(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 200.0)
        assert engine.compute_total_collected() == 0.0  # max(0, ...)


class TestComputeTotalOutstanding:
    def test_compute_total_outstanding_empty(self, engine):
        assert engine.compute_total_outstanding() == 0.0

    def test_compute_total_outstanding_open_settlement(self, settlement_engine):
        assert settlement_engine.compute_total_outstanding() == 1000.0

    def test_compute_total_outstanding_partial_included(self, partial_engine):
        assert partial_engine.compute_total_outstanding() == 600.0

    def test_compute_total_outstanding_settled_excluded(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        assert paid_engine.compute_total_outstanding() == 0.0

    def test_compute_total_outstanding_written_off_excluded(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 1000.0)
        assert settlement_engine.compute_total_outstanding() == 0.0

    def test_compute_total_outstanding_disputed_included(self, settlement_engine):
        settlement_engine.mark_settlement_disputed("sett-1")
        assert settlement_engine.compute_total_outstanding() == 1000.0

    def test_compute_total_outstanding_multiple(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.create_settlement("sett-2", "inv-2", "acct-1", 500.0)
        assert engine.compute_total_outstanding() == 1500.0


class TestComputeTotalDisputed:
    def test_compute_total_disputed_empty(self, engine):
        assert engine.compute_total_disputed() == 0.0

    def test_compute_total_disputed_no_disputed(self, settlement_engine):
        assert settlement_engine.compute_total_disputed() == 0.0

    def test_compute_total_disputed_single(self, settlement_engine):
        settlement_engine.mark_settlement_disputed("sett-1")
        assert settlement_engine.compute_total_disputed() == 1000.0

    def test_compute_total_disputed_multiple(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.create_settlement("sett-2", "inv-2", "acct-1", 500.0)
        engine.mark_settlement_disputed("sett-1")
        engine.mark_settlement_disputed("sett-2")
        assert engine.compute_total_disputed() == 1500.0

    def test_compute_total_disputed_partial_disputed(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.record_payment("pay-1", "inv-1", "acct-1", 400.0)
        engine.apply_cash("app-1", "sett-1", "pay-1", 400.0)
        engine.mark_settlement_disputed("sett-1")
        assert engine.compute_total_disputed() == 600.0


# ===========================================================================
# Violation Detection
# ===========================================================================


class TestDetectSettlementViolations:
    def test_detect_violations_empty(self, engine):
        result = engine.detect_settlement_violations()
        assert result == ()

    def test_detect_violations_open_no_payment(self, settlement_engine):
        result = settlement_engine.detect_settlement_violations()
        assert len(result) == 1
        assert "no payments" in result[0].description.lower()

    def test_detect_violations_3_dunning_escalation(self, collection_engine):
        for i in range(3):
            collection_engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")
        result = collection_engine.detect_settlement_violations()
        # Should produce escalation decision + no_payment decision
        escalation_decisions = [d for d in result if "dunning" in d.description.lower()]
        assert len(escalation_decisions) == 1

    def test_detect_violation_descriptions_are_bounded(self, collection_engine):
        for i in range(3):
            collection_engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")
        result = collection_engine.detect_settlement_violations()
        descriptions = {d.description for d in result}
        assert "Collection case requires dunning escalation" in descriptions
        assert "Settlement has no payments applied" in descriptions
        assert all("case-1" not in description for description in descriptions)

    def test_detect_violations_auto_escalates_collection(self, collection_engine):
        for i in range(3):
            collection_engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")
        c = collection_engine.get_collection_case("case-1")
        assert c.status == CollectionStatus.IN_PROGRESS
        collection_engine.detect_settlement_violations()
        c = collection_engine.get_collection_case("case-1")
        assert c.status == CollectionStatus.ESCALATED

    def test_detect_violations_idempotent(self, settlement_engine):
        first = settlement_engine.detect_settlement_violations()
        assert len(first) > 0
        second = settlement_engine.detect_settlement_violations()
        assert second == ()

    def test_detect_violations_decision_count(self, settlement_engine):
        assert settlement_engine.decision_count == 0
        settlement_engine.detect_settlement_violations()
        assert settlement_engine.decision_count > 0

    def test_detect_violations_emits_event(self, es, settlement_engine):
        initial = es.event_count
        settlement_engine.detect_settlement_violations()
        assert es.event_count > initial

    def test_detect_violations_no_event_when_no_violations(self, es, engine):
        initial = es.event_count
        engine.detect_settlement_violations()
        assert es.event_count == initial

    def test_detect_violations_settled_not_flagged(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        result = paid_engine.detect_settlement_violations()
        assert result == ()

    def test_detect_violations_partial_not_flagged_as_no_payment(self, partial_engine):
        result = partial_engine.detect_settlement_violations()
        no_payment = [d for d in result if "no payments" in d.description.lower()]
        assert len(no_payment) == 0

    def test_detect_violations_3_dunning_already_escalated_no_re_escalate(self, collection_engine):
        collection_engine.escalate_collection("case-1")
        for i in range(3):
            collection_engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")
        collection_engine.detect_settlement_violations()
        # Should still be ESCALATED (not erroring)
        c = collection_engine.get_collection_case("case-1")
        assert c.status == CollectionStatus.ESCALATED

    def test_detect_violations_paused_collection_not_auto_escalated(self, collection_engine):
        for i in range(3):
            collection_engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")
        collection_engine.pause_collection("case-1")
        collection_engine.detect_settlement_violations()
        c = collection_engine.get_collection_case("case-1")
        assert c.status == CollectionStatus.PAUSED

    def test_detect_violations_resolved_collection_skipped(self, collection_engine):
        for i in range(3):
            collection_engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")
        collection_engine.resolve_collection("case-1")
        result = collection_engine.detect_settlement_violations()
        escalation_decisions = [d for d in result if "dunning" in d.description.lower()]
        assert len(escalation_decisions) == 0


class TestDecisionsForSettlement:
    def test_decisions_for_settlement_returns_tuple(self, settlement_engine):
        settlement_engine.detect_settlement_violations()
        result = settlement_engine.decisions_for_settlement("sett-1")
        assert isinstance(result, tuple)

    def test_decisions_for_settlement_empty(self, engine):
        assert engine.decisions_for_settlement("sett-1") == ()

    def test_decisions_for_settlement_filters(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.create_settlement("sett-2", "inv-2", "acct-2", 500.0)
        engine.detect_settlement_violations()
        result1 = engine.decisions_for_settlement("sett-1")
        result2 = engine.decisions_for_settlement("sett-2")
        assert len(result1) == 1
        assert len(result2) == 1


# ===========================================================================
# Aging Snapshot
# ===========================================================================


class TestAgingSnapshot:
    def test_aging_snapshot_returns_record(self, engine):
        snap = engine.aging_snapshot("snap-1")
        assert isinstance(snap, AgingSnapshot)

    def test_aging_snapshot_fields_empty(self, engine):
        snap = engine.aging_snapshot("snap-1")
        assert snap.snapshot_id == "snap-1"
        assert snap.total_settlements == 0
        assert snap.total_open == 0
        assert snap.total_partial == 0
        assert snap.total_settled == 0
        assert snap.total_disputed == 0
        assert snap.total_written_off == 0
        assert snap.total_outstanding == 0.0
        assert snap.total_collected == 0.0
        assert snap.total_refunded == 0.0
        assert snap.total_collection_cases == 0

    def test_aging_snapshot_has_captured_at(self, engine):
        snap = engine.aging_snapshot("snap-1")
        assert snap.captured_at is not None

    def test_aging_snapshot_duplicate_raises(self, engine):
        engine.aging_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.aging_snapshot("snap-1")

    def test_aging_snapshot_emits_event(self, es, engine):
        initial = es.event_count
        engine.aging_snapshot("snap-1")
        assert es.event_count > initial

    def test_aging_snapshot_open_count(self, settlement_engine):
        snap = settlement_engine.aging_snapshot("snap-1")
        assert snap.total_open == 1
        assert snap.total_settlements == 1

    def test_aging_snapshot_partial_count(self, partial_engine):
        snap = partial_engine.aging_snapshot("snap-1")
        assert snap.total_partial == 1

    def test_aging_snapshot_settled_count(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        snap = paid_engine.aging_snapshot("snap-1")
        assert snap.total_settled == 1
        assert snap.total_open == 0

    def test_aging_snapshot_disputed_count(self, settlement_engine):
        settlement_engine.mark_settlement_disputed("sett-1")
        snap = settlement_engine.aging_snapshot("snap-1")
        assert snap.total_disputed == 1

    def test_aging_snapshot_written_off_count(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 1000.0)
        snap = settlement_engine.aging_snapshot("snap-1")
        assert snap.total_written_off == 1

    def test_aging_snapshot_outstanding(self, settlement_engine):
        snap = settlement_engine.aging_snapshot("snap-1")
        assert snap.total_outstanding == 1000.0

    def test_aging_snapshot_collected(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        snap = engine.aging_snapshot("snap-1")
        assert snap.total_collected == 500.0

    def test_aging_snapshot_refunded(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 100.0)
        snap = engine.aging_snapshot("snap-1")
        assert snap.total_refunded == 100.0

    def test_aging_snapshot_collection_cases(self, collection_engine):
        snap = collection_engine.aging_snapshot("snap-1")
        assert snap.total_collection_cases == 1


# ===========================================================================
# Properties
# ===========================================================================


class TestProperties:
    def test_initial_counts_zero(self, engine):
        assert engine.payment_count == 0
        assert engine.settlement_count == 0
        assert engine.collection_count == 0
        assert engine.dunning_count == 0
        assert engine.application_count == 0
        assert engine.refund_count == 0
        assert engine.writeoff_count == 0
        assert engine.decision_count == 0

    def test_payment_count(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_payment("pay-2", "inv-2", "acct-1", 200.0)
        assert engine.payment_count == 2

    def test_settlement_count(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 100.0)
        assert engine.settlement_count == 1

    def test_collection_count(self, engine):
        engine.open_collection_case("case-1", "inv-1", "acct-1", 100.0)
        assert engine.collection_count == 1

    def test_dunning_count(self, collection_engine):
        collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert collection_engine.dunning_count == 1

    def test_application_count(self, paid_engine):
        paid_engine.apply_cash("app-1", "sett-1", "pay-1", 100.0)
        assert paid_engine.application_count == 1

    def test_refund_count(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)
        assert engine.refund_count == 1

    def test_writeoff_count(self, settlement_engine):
        settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 100.0)
        assert settlement_engine.writeoff_count == 1

    def test_decision_count(self, settlement_engine):
        settlement_engine.detect_settlement_violations()
        assert settlement_engine.decision_count > 0


# ===========================================================================
# State Hash
# ===========================================================================


class TestStateHash:
    def test_state_hash_returns_16_char_hex(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64
        int(h, 16)  # should not raise

    def test_state_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_state_hash_changes_after_settlement(self, engine):
        h1 = engine.state_hash()
        engine.create_settlement("sett-1", "inv-1", "acct-1", 100.0)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_after_payment(self, engine):
        h1 = engine.state_hash()
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_after_collection(self, engine):
        h1 = engine.state_hash()
        engine.open_collection_case("case-1", "inv-1", "acct-1", 100.0)
        h2 = engine.state_hash()
        assert h1 != h2


# ===========================================================================
# Constructor Guard
# ===========================================================================


class TestConstructor:
    def test_constructor_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            SettlementRuntimeEngine("not_an_engine")

    def test_constructor_requires_event_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            SettlementRuntimeEngine(None)

    def test_constructor_accepts_event_spine(self):
        es = EventSpineEngine()
        eng = SettlementRuntimeEngine(es)
        assert eng.settlement_count == 0


# ===========================================================================
# Golden Scenarios
# ===========================================================================


class TestGoldenScenario1InvoicePaidInFull:
    """Create settlement -> record payment -> apply cash -> verify SETTLED."""

    def test_full_flow(self, es, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        assert s.status == SettlementStatus.OPEN
        assert s.outstanding == 1000.0

        p = engine.record_payment("pay-1", "inv-1", "acct-1", 1000.0)
        assert p.status == PaymentStatus.CLEARED

        app = engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        assert app.amount == 1000.0

        s = engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.SETTLED
        assert s.outstanding == 0.0
        assert s.paid_amount == 1000.0

        assert engine.settlement_count == 1
        assert engine.payment_count == 1
        assert engine.application_count == 1
        assert es.event_count == 3  # create + payment + cash_applied

    def test_outstanding_is_zero(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        assert engine.compute_total_outstanding() == 0.0

    def test_total_collected(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 500.0)
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        assert engine.compute_total_collected() == 500.0


class TestGoldenScenario2PartialPaymentAndAging:
    """Create settlement -> record partial payment -> apply cash -> verify PARTIAL."""

    def test_partial_flow(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.record_payment("pay-1", "inv-1", "acct-1", 400.0)
        engine.apply_cash("app-1", "sett-1", "pay-1", 400.0)

        s = engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.PARTIAL
        assert s.paid_amount == 400.0
        assert s.outstanding == 600.0

    def test_partial_outstanding_computed(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.record_payment("pay-1", "inv-1", "acct-1", 400.0)
        engine.apply_cash("app-1", "sett-1", "pay-1", 400.0)
        assert engine.compute_total_outstanding() == 600.0

    def test_partial_snapshot_counts(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.record_payment("pay-1", "inv-1", "acct-1", 400.0)
        engine.apply_cash("app-1", "sett-1", "pay-1", 400.0)
        snap = engine.aging_snapshot("snap-1")
        assert snap.total_partial == 1
        assert snap.total_open == 0


class TestGoldenScenario3OverdueCollectionDunning:
    """Create settlement -> open collection -> issue 3 dunning notices."""

    def test_dunning_flow(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.open_collection_case("case-1", "inv-1", "acct-1", 1000.0)

        for i in range(3):
            engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")

        c = engine.get_collection_case("case-1")
        assert c.dunning_count == 3
        assert c.status == CollectionStatus.IN_PROGRESS

    def test_dunning_three_triggers_violation(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.open_collection_case("case-1", "inv-1", "acct-1", 1000.0)
        for i in range(3):
            engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")

        violations = engine.detect_settlement_violations()
        assert len(violations) >= 1  # at least escalation decision

    def test_dunning_auto_escalation(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.open_collection_case("case-1", "inv-1", "acct-1", 1000.0)
        for i in range(3):
            engine.issue_dunning_notice(f"dn-{i}", "case-1", "acct-1")

        engine.detect_settlement_violations()
        c = engine.get_collection_case("case-1")
        assert c.status == CollectionStatus.ESCALATED


class TestGoldenScenario4DisputePausesCollection:
    """Create settlement -> open collection -> dispute -> pause collection."""

    def test_dispute_pause_flow(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.open_collection_case("case-1", "inv-1", "acct-1", 1000.0)

        s = engine.mark_settlement_disputed("sett-1")
        assert s.status == SettlementStatus.DISPUTED

        c = engine.pause_collection("case-1")
        assert c.status == CollectionStatus.PAUSED

    def test_dispute_and_pause_statuses(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.open_collection_case("case-1", "inv-1", "acct-1", 1000.0)
        engine.mark_settlement_disputed("sett-1")
        engine.pause_collection("case-1")

        s = engine.get_settlement("sett-1")
        c = engine.get_collection_case("case-1")
        assert s.status == SettlementStatus.DISPUTED
        assert c.status == CollectionStatus.PAUSED


class TestGoldenScenario5CreditAndPenaltyAffectBalance:
    """Create settlement -> apply_credit -> verify outstanding reduced."""

    def test_credit_reduces_outstanding(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.apply_credit("app-1", "sett-1", "credit-1", 300.0)

        s = engine.get_settlement("sett-1")
        assert s.outstanding == 700.0
        assert s.credit_applied == 300.0
        assert s.paid_amount == 0.0

    def test_credit_then_payment(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.apply_credit("app-1", "sett-1", "credit-1", 300.0)

        s = engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.PARTIAL

        engine.record_payment("pay-1", "inv-1", "acct-1", 700.0)
        engine.apply_cash("app-2", "sett-1", "pay-1", 700.0)

        s = engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.SETTLED
        assert s.outstanding == 0.0
        assert s.credit_applied == 300.0
        assert s.paid_amount == 700.0


class TestGoldenScenario6SnapshotReflectsMixedState:
    """Create multiple settlements in different states -> snapshot -> verify."""

    def test_mixed_state_snapshot(self, engine):
        # OPEN settlement
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)

        # PARTIAL settlement
        engine.create_settlement("sett-2", "inv-2", "acct-1", 500.0)
        engine.record_payment("pay-1", "inv-2", "acct-1", 200.0)
        engine.apply_cash("app-1", "sett-2", "pay-1", 200.0)

        # SETTLED settlement
        engine.create_settlement("sett-3", "inv-3", "acct-1", 300.0)
        engine.record_payment("pay-2", "inv-3", "acct-1", 300.0)
        engine.apply_cash("app-2", "sett-3", "pay-2", 300.0)

        # DISPUTED settlement
        engine.create_settlement("sett-4", "inv-4", "acct-2", 800.0)
        engine.mark_settlement_disputed("sett-4")

        # WRITTEN_OFF settlement
        engine.create_settlement("sett-5", "inv-5", "acct-2", 200.0)
        engine.record_writeoff("wo-1", "sett-5", "acct-2", 200.0)

        # Collection case
        engine.open_collection_case("case-1", "inv-1", "acct-1", 1000.0)

        # Refund
        engine.record_refund("ref-1", "pay-1", "acct-1", 50.0)

        snap = engine.aging_snapshot("snap-1")

        assert snap.total_settlements == 5
        assert snap.total_open == 1
        assert snap.total_partial == 1
        assert snap.total_settled == 1
        assert snap.total_disputed == 1
        assert snap.total_written_off == 1
        assert snap.total_collection_cases == 1
        assert snap.total_refunded == 50.0
        # outstanding = sett-1 (1000) + sett-2 (300) + sett-4 (800) = 2100
        # (SETTLED and WRITTEN_OFF are terminal, DISPUTED is non-terminal)
        assert snap.total_outstanding == 2100.0
        # collected = pay-1 (200 CLEARED) + pay-2 (300 CLEARED) - refund (50) = 450
        assert snap.total_collected == 450.0

    def test_mixed_state_snapshot_multiple_snapshots(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        snap1 = engine.aging_snapshot("snap-1")
        assert snap1.total_open == 1

        engine.record_payment("pay-1", "inv-1", "acct-1", 1000.0)
        engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        snap2 = engine.aging_snapshot("snap-2")
        assert snap2.total_settled == 1
        assert snap2.total_open == 0


# ===========================================================================
# Edge Cases and Integration
# ===========================================================================


class TestEdgeCases:
    def test_zero_amount_settlement(self, engine):
        s = engine.create_settlement("sett-1", "inv-1", "acct-1", 0.0)
        assert s.outstanding == 0.0
        assert s.status == SettlementStatus.OPEN

    def test_apply_cash_zero_amount(self, paid_engine):
        app = paid_engine.apply_cash("app-1", "sett-1", "pay-1", 0.0)
        assert app.amount == 0.0

    def test_apply_credit_zero_amount(self, settlement_engine):
        app = settlement_engine.apply_credit("app-1", "sett-1", "credit-1", 0.0)
        assert app.amount == 0.0

    def test_writeoff_zero_amount(self, settlement_engine):
        wo = settlement_engine.record_writeoff("wo-1", "sett-1", "acct-1", 0.0)
        assert wo.amount == 0.0

    def test_refund_zero_amount(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        r = engine.record_refund("ref-1", "pay-1", "acct-1", 0.0)
        assert r.amount == 0.0

    def test_multiple_accounts_isolated(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.create_settlement("sett-2", "inv-2", "acct-2", 500.0)
        assert len(engine.settlements_for_account("acct-1")) == 1
        assert len(engine.settlements_for_account("acct-2")) == 1

    def test_cash_and_credit_combined_settle(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.apply_credit("app-1", "sett-1", "credit-1", 500.0)
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        engine.apply_cash("app-2", "sett-1", "pay-1", 500.0)
        s = engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.SETTLED
        assert s.outstanding == 0.0
        assert s.credit_applied == 500.0
        assert s.paid_amount == 500.0

    def test_dispute_then_apply_cash_still_works(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.mark_settlement_disputed("sett-1")
        engine.record_payment("pay-1", "inv-1", "acct-1", 1000.0)
        app = engine.apply_cash("app-1", "sett-1", "pay-1", 1000.0)
        s = engine.get_settlement("sett-1")
        assert s.status == SettlementStatus.SETTLED

    def test_collection_lifecycle_open_escalate_pause_resume_resolve_close(self, engine):
        engine.open_collection_case("case-1", "inv-1", "acct-1", 500.0)
        c = engine.escalate_collection("case-1")
        assert c.status == CollectionStatus.ESCALATED
        c = engine.pause_collection("case-1")
        assert c.status == CollectionStatus.PAUSED
        c = engine.resume_collection("case-1")
        assert c.status == CollectionStatus.IN_PROGRESS
        c = engine.resolve_collection("case-1")
        assert c.status == CollectionStatus.RESOLVED
        assert c.outstanding_amount == 0.0
        c = engine.close_collection("case-1")
        assert c.status == CollectionStatus.CLOSED

    def test_multiple_refunds_same_payment(self, engine):
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        engine.record_refund("ref-1", "pay-1", "acct-1", 30.0)
        engine.record_refund("ref-2", "pay-1", "acct-1", 30.0)
        assert engine.refund_count == 2
        result = engine.refunds_for_payment("pay-1")
        assert len(result) == 2

    def test_state_hash_changes_on_each_operation(self, engine):
        hashes = set()
        hashes.add(engine.state_hash())
        engine.create_settlement("sett-1", "inv-1", "acct-1", 100.0)
        hashes.add(engine.state_hash())
        engine.record_payment("pay-1", "inv-1", "acct-1", 100.0)
        hashes.add(engine.state_hash())
        engine.apply_cash("app-1", "sett-1", "pay-1", 100.0)
        hashes.add(engine.state_hash())
        # At minimum, empty vs settlement vs payment should differ
        assert len(hashes) >= 3

    def test_dunning_on_paused_collection_allowed(self, collection_engine):
        collection_engine.pause_collection("case-1")
        # PAUSED is not terminal, so dunning should be allowed
        n = collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert n.notice_id == "dn-1"

    def test_dunning_on_escalated_collection_allowed(self, collection_engine):
        collection_engine.escalate_collection("case-1")
        n = collection_engine.issue_dunning_notice("dn-1", "case-1", "acct-1")
        assert n.notice_id == "dn-1"

    def test_apply_cash_on_disputed_settlement_allowed(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.mark_settlement_disputed("sett-1")
        engine.record_payment("pay-1", "inv-1", "acct-1", 500.0)
        app = engine.apply_cash("app-1", "sett-1", "pay-1", 500.0)
        assert app.amount == 500.0

    def test_apply_credit_on_disputed_settlement_allowed(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.mark_settlement_disputed("sett-1")
        app = engine.apply_credit("app-1", "sett-1", "credit-1", 500.0)
        assert app.amount == 500.0

    def test_writeoff_on_disputed_settlement_allowed(self, engine):
        engine.create_settlement("sett-1", "inv-1", "acct-1", 1000.0)
        engine.mark_settlement_disputed("sett-1")
        wo = engine.record_writeoff("wo-1", "sett-1", "acct-1", 500.0)
        assert wo.amount == 500.0
