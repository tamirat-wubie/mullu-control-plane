"""Tests for settlement runtime contracts."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _payment(**overrides) -> PaymentRecord:
    defaults = dict(
        payment_id="pay-001",
        invoice_id="inv-001",
        account_id="acct-001",
        amount=100.0,
        currency="USD",
        method=PaymentMethodKind.BANK_TRANSFER,
        status=PaymentStatus.PENDING,
        reference="ref-001",
        received_at=TS,
    )
    defaults.update(overrides)
    return PaymentRecord(**defaults)


def _settlement(**overrides) -> SettlementRecord:
    defaults = dict(
        settlement_id="stl-001",
        invoice_id="inv-001",
        account_id="acct-001",
        total_amount=1000.0,
        paid_amount=500.0,
        credit_applied=100.0,
        outstanding=400.0,
        status=SettlementStatus.OPEN,
        currency="USD",
        created_at=TS,
    )
    defaults.update(overrides)
    return SettlementRecord(**defaults)


def _collection_case(**overrides) -> CollectionCase:
    defaults = dict(
        case_id="case-001",
        invoice_id="inv-001",
        account_id="acct-001",
        status=CollectionStatus.OPEN,
        outstanding_amount=500.0,
        dunning_count=0,
        opened_at=TS,
        closed_at="",
    )
    defaults.update(overrides)
    return CollectionCase(**defaults)


def _dunning_notice(**overrides) -> DunningNotice:
    defaults = dict(
        notice_id="dn-001",
        case_id="case-001",
        account_id="acct-001",
        severity=DunningSeverity.REMINDER,
        message="Please pay your invoice.",
        sent_at=TS,
    )
    defaults.update(overrides)
    return DunningNotice(**defaults)


def _cash_application(**overrides) -> CashApplication:
    defaults = dict(
        application_id="app-001",
        settlement_id="stl-001",
        payment_id="pay-001",
        amount=250.0,
        applied_at=TS,
    )
    defaults.update(overrides)
    return CashApplication(**defaults)


def _refund(**overrides) -> RefundRecord:
    defaults = dict(
        refund_id="ref-001",
        payment_id="pay-001",
        account_id="acct-001",
        amount=50.0,
        reason="Overpayment",
        refunded_at=TS,
    )
    defaults.update(overrides)
    return RefundRecord(**defaults)


def _writeoff(**overrides) -> WriteoffRecord:
    defaults = dict(
        writeoff_id="wo-001",
        settlement_id="stl-001",
        account_id="acct-001",
        amount=200.0,
        disposition=WriteoffDisposition.PENDING,
        reason="Uncollectable",
        written_off_at=TS,
    )
    defaults.update(overrides)
    return WriteoffRecord(**defaults)


def _aging_snapshot(**overrides) -> AgingSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        total_settlements=10,
        total_open=3,
        total_partial=2,
        total_settled=4,
        total_disputed=1,
        total_written_off=0,
        total_outstanding=5000.0,
        total_collected=3000.0,
        total_refunded=200.0,
        total_collection_cases=2,
        captured_at=TS,
    )
    defaults.update(overrides)
    return AgingSnapshot(**defaults)


def _settlement_decision(**overrides) -> SettlementDecision:
    defaults = dict(
        decision_id="dec-001",
        settlement_id="stl-001",
        description="Approve partial settlement",
        decided_by="admin-001",
        decided_at=TS,
    )
    defaults.update(overrides)
    return SettlementDecision(**defaults)


def _closure_report(**overrides) -> SettlementClosureReport:
    defaults = dict(
        report_id="rpt-001",
        account_id="acct-001",
        total_settlements=10,
        total_payments=15,
        total_refunds=2,
        total_writeoffs=1,
        total_collection_cases=3,
        total_collected=8000.0,
        total_outstanding=2000.0,
        closed_at=TS,
    )
    defaults.update(overrides)
    return SettlementClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestPaymentStatus:
    def test_member_count(self):
        assert len(PaymentStatus) == 4

    @pytest.mark.parametrize("member", list(PaymentStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.CLEARED.value == "cleared"
        assert PaymentStatus.FAILED.value == "failed"
        assert PaymentStatus.REVERSED.value == "reversed"

    def test_membership(self):
        assert PaymentStatus("pending") is PaymentStatus.PENDING

    def test_iteration(self):
        members = list(PaymentStatus)
        assert len(members) == 4

    def test_string_representation(self):
        assert "PENDING" in repr(PaymentStatus.PENDING)


class TestSettlementStatus:
    def test_member_count(self):
        assert len(SettlementStatus) == 5

    @pytest.mark.parametrize("member", list(SettlementStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert SettlementStatus.OPEN.value == "open"
        assert SettlementStatus.PARTIAL.value == "partial"
        assert SettlementStatus.SETTLED.value == "settled"
        assert SettlementStatus.DISPUTED.value == "disputed"
        assert SettlementStatus.WRITTEN_OFF.value == "written_off"

    def test_membership(self):
        assert SettlementStatus("open") is SettlementStatus.OPEN

    def test_iteration(self):
        members = list(SettlementStatus)
        assert len(members) == 5

    def test_string_representation(self):
        assert "OPEN" in repr(SettlementStatus.OPEN)


class TestCollectionStatus:
    def test_member_count(self):
        assert len(CollectionStatus) == 6

    @pytest.mark.parametrize("member", list(CollectionStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert CollectionStatus.OPEN.value == "open"
        assert CollectionStatus.IN_PROGRESS.value == "in_progress"
        assert CollectionStatus.PAUSED.value == "paused"
        assert CollectionStatus.RESOLVED.value == "resolved"
        assert CollectionStatus.ESCALATED.value == "escalated"
        assert CollectionStatus.CLOSED.value == "closed"

    def test_membership(self):
        assert CollectionStatus("open") is CollectionStatus.OPEN

    def test_iteration(self):
        members = list(CollectionStatus)
        assert len(members) == 6

    def test_string_representation(self):
        assert "OPEN" in repr(CollectionStatus.OPEN)


class TestWriteoffDisposition:
    def test_member_count(self):
        assert len(WriteoffDisposition) == 4

    @pytest.mark.parametrize("member", list(WriteoffDisposition))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert WriteoffDisposition.PENDING.value == "pending"
        assert WriteoffDisposition.APPROVED.value == "approved"
        assert WriteoffDisposition.REJECTED.value == "rejected"
        assert WriteoffDisposition.REVERSED.value == "reversed"

    def test_membership(self):
        assert WriteoffDisposition("pending") is WriteoffDisposition.PENDING

    def test_iteration(self):
        members = list(WriteoffDisposition)
        assert len(members) == 4

    def test_string_representation(self):
        assert "PENDING" in repr(WriteoffDisposition.PENDING)


class TestPaymentMethodKind:
    def test_member_count(self):
        assert len(PaymentMethodKind) == 6

    @pytest.mark.parametrize("member", list(PaymentMethodKind))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert PaymentMethodKind.BANK_TRANSFER.value == "bank_transfer"
        assert PaymentMethodKind.CREDIT_CARD.value == "credit_card"
        assert PaymentMethodKind.CHECK.value == "check"
        assert PaymentMethodKind.WIRE.value == "wire"
        assert PaymentMethodKind.ACH.value == "ach"
        assert PaymentMethodKind.CRYPTO.value == "crypto"

    def test_membership(self):
        assert PaymentMethodKind("bank_transfer") is PaymentMethodKind.BANK_TRANSFER

    def test_iteration(self):
        members = list(PaymentMethodKind)
        assert len(members) == 6

    def test_string_representation(self):
        assert "BANK_TRANSFER" in repr(PaymentMethodKind.BANK_TRANSFER)


class TestDunningSeverity:
    def test_member_count(self):
        assert len(DunningSeverity) == 4

    @pytest.mark.parametrize("member", list(DunningSeverity))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert DunningSeverity.REMINDER.value == "reminder"
        assert DunningSeverity.WARNING.value == "warning"
        assert DunningSeverity.FINAL_NOTICE.value == "final_notice"
        assert DunningSeverity.ESCALATION.value == "escalation"

    def test_membership(self):
        assert DunningSeverity("reminder") is DunningSeverity.REMINDER

    def test_iteration(self):
        members = list(DunningSeverity)
        assert len(members) == 4

    def test_string_representation(self):
        assert "REMINDER" in repr(DunningSeverity.REMINDER)


# ===================================================================
# PaymentRecord tests
# ===================================================================


class TestPaymentRecord:
    def test_happy_path(self):
        rec = _payment()
        assert rec.payment_id == "pay-001"
        assert rec.invoice_id == "inv-001"
        assert rec.account_id == "acct-001"
        assert rec.amount == 100.0
        assert rec.currency == "USD"
        assert rec.method is PaymentMethodKind.BANK_TRANSFER
        assert rec.status is PaymentStatus.PENDING
        assert rec.reference == "ref-001"
        assert rec.received_at == TS

    def test_frozen(self):
        rec = _payment()
        with pytest.raises(AttributeError):
            rec.payment_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(PaymentRecord)

    def test_metadata_frozen(self):
        rec = _payment(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _payment(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _payment(metadata={"items": [1, 2, 3]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["payment_id", "invoice_id", "account_id", "currency"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _payment(**{field: ""})

    @pytest.mark.parametrize("field", ["payment_id", "invoice_id", "account_id", "currency"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _payment(**{field: "   "})

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            _payment(amount=-1.0)

    def test_zero_amount_accepted(self):
        rec = _payment(amount=0.0)
        assert rec.amount == 0.0

    def test_invalid_method_rejected(self):
        with pytest.raises(ValueError):
            _payment(method="bank_transfer")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _payment(status="pending")

    def test_empty_received_at_rejected(self):
        with pytest.raises(ValueError):
            _payment(received_at="")

    def test_invalid_received_at_rejected(self):
        with pytest.raises(ValueError):
            _payment(received_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _payment()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_status_enum(self):
        rec = _payment()
        d = rec.to_dict()
        assert isinstance(d["status"], PaymentStatus)
        assert d["status"] is PaymentStatus.PENDING

    def test_to_dict_preserves_method_enum(self):
        rec = _payment()
        d = rec.to_dict()
        assert isinstance(d["method"], PaymentMethodKind)
        assert d["method"] is PaymentMethodKind.BANK_TRANSFER

    def test_to_dict_keys(self):
        rec = _payment()
        d = rec.to_dict()
        expected_keys = {
            "payment_id", "invoice_id", "account_id", "amount",
            "currency", "method", "status", "reference",
            "received_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(PaymentStatus))
    def test_all_statuses_accepted(self, status):
        rec = _payment(status=status)
        assert rec.status is status

    @pytest.mark.parametrize("method", list(PaymentMethodKind))
    def test_all_methods_accepted(self, method):
        rec = _payment(method=method)
        assert rec.method is method


# ===================================================================
# SettlementRecord tests
# ===================================================================


class TestSettlementRecord:
    def test_happy_path(self):
        rec = _settlement()
        assert rec.settlement_id == "stl-001"
        assert rec.invoice_id == "inv-001"
        assert rec.account_id == "acct-001"
        assert rec.total_amount == 1000.0
        assert rec.paid_amount == 500.0
        assert rec.credit_applied == 100.0
        assert rec.outstanding == 400.0
        assert rec.status is SettlementStatus.OPEN
        assert rec.currency == "USD"
        assert rec.created_at == TS

    def test_frozen(self):
        rec = _settlement()
        with pytest.raises(AttributeError):
            rec.settlement_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(SettlementRecord)

    def test_metadata_frozen(self):
        rec = _settlement(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _settlement(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _settlement(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["settlement_id", "invoice_id", "account_id", "currency"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _settlement(**{field: ""})

    @pytest.mark.parametrize("field", ["settlement_id", "invoice_id", "account_id", "currency"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _settlement(**{field: "   "})

    @pytest.mark.parametrize("field", ["total_amount", "paid_amount", "credit_applied", "outstanding"])
    def test_negative_float_rejected(self, field):
        with pytest.raises(ValueError):
            _settlement(**{field: -1.0})

    @pytest.mark.parametrize("field", ["total_amount", "paid_amount", "credit_applied", "outstanding"])
    def test_zero_float_accepted(self, field):
        rec = _settlement(**{field: 0.0})
        assert getattr(rec, field) == 0.0

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _settlement(status="open")

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError):
            _settlement(created_at="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            _settlement(created_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _settlement()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enums(self):
        rec = _settlement()
        d = rec.to_dict()
        assert isinstance(d["status"], SettlementStatus)
        assert d["status"] is SettlementStatus.OPEN

    def test_to_dict_keys(self):
        rec = _settlement()
        d = rec.to_dict()
        expected_keys = {
            "settlement_id", "invoice_id", "account_id", "total_amount",
            "paid_amount", "credit_applied", "outstanding", "status",
            "currency", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(SettlementStatus))
    def test_all_statuses_accepted(self, status):
        rec = _settlement(status=status)
        assert rec.status is status


# ===================================================================
# CollectionCase tests
# ===================================================================


class TestCollectionCase:
    def test_happy_path(self):
        rec = _collection_case()
        assert rec.case_id == "case-001"
        assert rec.invoice_id == "inv-001"
        assert rec.account_id == "acct-001"
        assert rec.status is CollectionStatus.OPEN
        assert rec.outstanding_amount == 500.0
        assert rec.dunning_count == 0
        assert rec.opened_at == TS
        assert rec.closed_at == ""

    def test_frozen(self):
        rec = _collection_case()
        with pytest.raises(AttributeError):
            rec.case_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(CollectionCase)

    def test_metadata_frozen(self):
        rec = _collection_case(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _collection_case(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _collection_case(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["case_id", "invoice_id", "account_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _collection_case(**{field: ""})

    @pytest.mark.parametrize("field", ["case_id", "invoice_id", "account_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _collection_case(**{field: "   "})

    def test_negative_outstanding_amount_rejected(self):
        with pytest.raises(ValueError):
            _collection_case(outstanding_amount=-1.0)

    def test_zero_outstanding_amount_accepted(self):
        rec = _collection_case(outstanding_amount=0.0)
        assert rec.outstanding_amount == 0.0

    def test_negative_dunning_count_rejected(self):
        with pytest.raises(ValueError):
            _collection_case(dunning_count=-1)

    def test_zero_dunning_count_accepted(self):
        rec = _collection_case(dunning_count=0)
        assert rec.dunning_count == 0

    def test_positive_dunning_count_accepted(self):
        rec = _collection_case(dunning_count=5)
        assert rec.dunning_count == 5

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _collection_case(status="open")

    def test_empty_opened_at_rejected(self):
        with pytest.raises(ValueError):
            _collection_case(opened_at="")

    def test_invalid_opened_at_rejected(self):
        with pytest.raises(ValueError):
            _collection_case(opened_at="not-a-date")

    def test_closed_at_empty_accepted(self):
        rec = _collection_case(closed_at="")
        assert rec.closed_at == ""

    def test_closed_at_valid_datetime_accepted(self):
        rec = _collection_case(closed_at=TS2)
        assert rec.closed_at == TS2

    def test_closed_at_invalid_rejected(self):
        with pytest.raises(ValueError):
            _collection_case(closed_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _collection_case()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enums(self):
        rec = _collection_case()
        d = rec.to_dict()
        assert isinstance(d["status"], CollectionStatus)
        assert d["status"] is CollectionStatus.OPEN

    def test_to_dict_keys(self):
        rec = _collection_case()
        d = rec.to_dict()
        expected_keys = {
            "case_id", "invoice_id", "account_id", "status",
            "outstanding_amount", "dunning_count", "opened_at",
            "closed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(CollectionStatus))
    def test_all_statuses_accepted(self, status):
        rec = _collection_case(status=status)
        assert rec.status is status


# ===================================================================
# DunningNotice tests
# ===================================================================


class TestDunningNotice:
    def test_happy_path(self):
        rec = _dunning_notice()
        assert rec.notice_id == "dn-001"
        assert rec.case_id == "case-001"
        assert rec.account_id == "acct-001"
        assert rec.severity is DunningSeverity.REMINDER
        assert rec.message == "Please pay your invoice."
        assert rec.sent_at == TS

    def test_frozen(self):
        rec = _dunning_notice()
        with pytest.raises(AttributeError):
            rec.notice_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(DunningNotice)

    def test_metadata_frozen(self):
        rec = _dunning_notice(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _dunning_notice(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _dunning_notice(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["notice_id", "case_id", "account_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _dunning_notice(**{field: ""})

    @pytest.mark.parametrize("field", ["notice_id", "case_id", "account_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _dunning_notice(**{field: "   "})

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError):
            _dunning_notice(severity="reminder")

    def test_empty_sent_at_rejected(self):
        with pytest.raises(ValueError):
            _dunning_notice(sent_at="")

    def test_invalid_sent_at_rejected(self):
        with pytest.raises(ValueError):
            _dunning_notice(sent_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _dunning_notice()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enums(self):
        rec = _dunning_notice()
        d = rec.to_dict()
        assert isinstance(d["severity"], DunningSeverity)
        assert d["severity"] is DunningSeverity.REMINDER

    def test_to_dict_keys(self):
        rec = _dunning_notice()
        d = rec.to_dict()
        expected_keys = {
            "notice_id", "case_id", "account_id", "severity",
            "message", "sent_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("severity", list(DunningSeverity))
    def test_all_severities_accepted(self, severity):
        rec = _dunning_notice(severity=severity)
        assert rec.severity is severity


# ===================================================================
# CashApplication tests
# ===================================================================


class TestCashApplication:
    def test_happy_path(self):
        rec = _cash_application()
        assert rec.application_id == "app-001"
        assert rec.settlement_id == "stl-001"
        assert rec.payment_id == "pay-001"
        assert rec.amount == 250.0
        assert rec.applied_at == TS

    def test_frozen(self):
        rec = _cash_application()
        with pytest.raises(AttributeError):
            rec.application_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(CashApplication)

    def test_metadata_frozen(self):
        rec = _cash_application(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _cash_application(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _cash_application(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["application_id", "settlement_id", "payment_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _cash_application(**{field: ""})

    @pytest.mark.parametrize("field", ["application_id", "settlement_id", "payment_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _cash_application(**{field: "   "})

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            _cash_application(amount=-1.0)

    def test_zero_amount_accepted(self):
        rec = _cash_application(amount=0.0)
        assert rec.amount == 0.0

    def test_empty_applied_at_rejected(self):
        with pytest.raises(ValueError):
            _cash_application(applied_at="")

    def test_invalid_applied_at_rejected(self):
        with pytest.raises(ValueError):
            _cash_application(applied_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _cash_application()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _cash_application()
        d = rec.to_dict()
        expected_keys = {
            "application_id", "settlement_id", "payment_id",
            "amount", "applied_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# RefundRecord tests
# ===================================================================


class TestRefundRecord:
    def test_happy_path(self):
        rec = _refund()
        assert rec.refund_id == "ref-001"
        assert rec.payment_id == "pay-001"
        assert rec.account_id == "acct-001"
        assert rec.amount == 50.0
        assert rec.reason == "Overpayment"
        assert rec.refunded_at == TS

    def test_frozen(self):
        rec = _refund()
        with pytest.raises(AttributeError):
            rec.refund_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(RefundRecord)

    def test_metadata_frozen(self):
        rec = _refund(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _refund(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _refund(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["refund_id", "payment_id", "account_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _refund(**{field: ""})

    @pytest.mark.parametrize("field", ["refund_id", "payment_id", "account_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _refund(**{field: "   "})

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            _refund(amount=-1.0)

    def test_zero_amount_accepted(self):
        rec = _refund(amount=0.0)
        assert rec.amount == 0.0

    def test_empty_refunded_at_rejected(self):
        with pytest.raises(ValueError):
            _refund(refunded_at="")

    def test_invalid_refunded_at_rejected(self):
        with pytest.raises(ValueError):
            _refund(refunded_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _refund()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _refund()
        d = rec.to_dict()
        expected_keys = {
            "refund_id", "payment_id", "account_id",
            "amount", "reason", "refunded_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# WriteoffRecord tests
# ===================================================================


class TestWriteoffRecord:
    def test_happy_path(self):
        rec = _writeoff()
        assert rec.writeoff_id == "wo-001"
        assert rec.settlement_id == "stl-001"
        assert rec.account_id == "acct-001"
        assert rec.amount == 200.0
        assert rec.disposition is WriteoffDisposition.PENDING
        assert rec.reason == "Uncollectable"
        assert rec.written_off_at == TS

    def test_frozen(self):
        rec = _writeoff()
        with pytest.raises(AttributeError):
            rec.writeoff_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(WriteoffRecord)

    def test_metadata_frozen(self):
        rec = _writeoff(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _writeoff(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _writeoff(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["writeoff_id", "settlement_id", "account_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _writeoff(**{field: ""})

    @pytest.mark.parametrize("field", ["writeoff_id", "settlement_id", "account_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _writeoff(**{field: "   "})

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            _writeoff(amount=-1.0)

    def test_zero_amount_accepted(self):
        rec = _writeoff(amount=0.0)
        assert rec.amount == 0.0

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            _writeoff(disposition="pending")

    def test_empty_written_off_at_rejected(self):
        with pytest.raises(ValueError):
            _writeoff(written_off_at="")

    def test_invalid_written_off_at_rejected(self):
        with pytest.raises(ValueError):
            _writeoff(written_off_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _writeoff()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enums(self):
        rec = _writeoff()
        d = rec.to_dict()
        assert isinstance(d["disposition"], WriteoffDisposition)
        assert d["disposition"] is WriteoffDisposition.PENDING

    def test_to_dict_keys(self):
        rec = _writeoff()
        d = rec.to_dict()
        expected_keys = {
            "writeoff_id", "settlement_id", "account_id",
            "amount", "disposition", "reason", "written_off_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("disposition", list(WriteoffDisposition))
    def test_all_dispositions_accepted(self, disposition):
        rec = _writeoff(disposition=disposition)
        assert rec.disposition is disposition


# ===================================================================
# AgingSnapshot tests
# ===================================================================


class TestAgingSnapshot:
    def test_happy_path(self):
        rec = _aging_snapshot()
        assert rec.snapshot_id == "snap-001"
        assert rec.total_settlements == 10
        assert rec.total_open == 3
        assert rec.total_partial == 2
        assert rec.total_settled == 4
        assert rec.total_disputed == 1
        assert rec.total_written_off == 0
        assert rec.total_outstanding == 5000.0
        assert rec.total_collected == 3000.0
        assert rec.total_refunded == 200.0
        assert rec.total_collection_cases == 2
        assert rec.captured_at == TS

    def test_frozen(self):
        rec = _aging_snapshot()
        with pytest.raises(AttributeError):
            rec.snapshot_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(AgingSnapshot)

    def test_metadata_frozen(self):
        rec = _aging_snapshot(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _aging_snapshot(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _aging_snapshot(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _aging_snapshot(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _aging_snapshot(snapshot_id="   ")

    @pytest.mark.parametrize("field", [
        "total_settlements", "total_open", "total_partial", "total_settled",
        "total_disputed", "total_written_off", "total_collection_cases",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _aging_snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_settlements", "total_open", "total_partial", "total_settled",
        "total_disputed", "total_written_off", "total_collection_cases",
    ])
    def test_zero_int_accepted(self, field):
        rec = _aging_snapshot(**{field: 0})
        assert getattr(rec, field) == 0

    @pytest.mark.parametrize("field", [
        "total_outstanding", "total_collected", "total_refunded",
    ])
    def test_negative_float_rejected(self, field):
        with pytest.raises(ValueError):
            _aging_snapshot(**{field: -1.0})

    @pytest.mark.parametrize("field", [
        "total_outstanding", "total_collected", "total_refunded",
    ])
    def test_zero_float_accepted(self, field):
        rec = _aging_snapshot(**{field: 0.0})
        assert getattr(rec, field) == 0.0

    def test_empty_captured_at_rejected(self):
        with pytest.raises(ValueError):
            _aging_snapshot(captured_at="")

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError):
            _aging_snapshot(captured_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _aging_snapshot()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _aging_snapshot()
        d = rec.to_dict()
        expected_keys = {
            "snapshot_id", "total_settlements", "total_open", "total_partial",
            "total_settled", "total_disputed", "total_written_off",
            "total_outstanding", "total_collected", "total_refunded",
            "total_collection_cases", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# SettlementDecision tests
# ===================================================================


class TestSettlementDecision:
    def test_happy_path(self):
        rec = _settlement_decision()
        assert rec.decision_id == "dec-001"
        assert rec.settlement_id == "stl-001"
        assert rec.description == "Approve partial settlement"
        assert rec.decided_by == "admin-001"
        assert rec.decided_at == TS

    def test_frozen(self):
        rec = _settlement_decision()
        with pytest.raises(AttributeError):
            rec.decision_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(SettlementDecision)

    def test_metadata_frozen(self):
        rec = _settlement_decision(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _settlement_decision(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _settlement_decision(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["decision_id", "settlement_id", "decided_by"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _settlement_decision(**{field: ""})

    @pytest.mark.parametrize("field", ["decision_id", "settlement_id", "decided_by"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _settlement_decision(**{field: "   "})

    def test_empty_decided_at_rejected(self):
        with pytest.raises(ValueError):
            _settlement_decision(decided_at="")

    def test_invalid_decided_at_rejected(self):
        with pytest.raises(ValueError):
            _settlement_decision(decided_at="not-a-date")

    def test_description_can_be_empty(self):
        rec = _settlement_decision(description="")
        assert rec.description == ""

    def test_to_dict_returns_dict(self):
        rec = _settlement_decision()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _settlement_decision()
        d = rec.to_dict()
        expected_keys = {
            "decision_id", "settlement_id", "description",
            "decided_by", "decided_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# SettlementClosureReport tests
# ===================================================================


class TestSettlementClosureReport:
    def test_happy_path(self):
        rec = _closure_report()
        assert rec.report_id == "rpt-001"
        assert rec.account_id == "acct-001"
        assert rec.total_settlements == 10
        assert rec.total_payments == 15
        assert rec.total_refunds == 2
        assert rec.total_writeoffs == 1
        assert rec.total_collection_cases == 3
        assert rec.total_collected == 8000.0
        assert rec.total_outstanding == 2000.0
        assert rec.closed_at == TS

    def test_frozen(self):
        rec = _closure_report()
        with pytest.raises(AttributeError):
            rec.report_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(SettlementClosureReport)

    def test_metadata_frozen(self):
        rec = _closure_report(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _closure_report(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _closure_report(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["report_id", "account_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: ""})

    @pytest.mark.parametrize("field", ["report_id", "account_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: "   "})

    @pytest.mark.parametrize("field", [
        "total_settlements", "total_payments", "total_refunds",
        "total_writeoffs", "total_collection_cases",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_settlements", "total_payments", "total_refunds",
        "total_writeoffs", "total_collection_cases",
    ])
    def test_zero_int_accepted(self, field):
        rec = _closure_report(**{field: 0})
        assert getattr(rec, field) == 0

    @pytest.mark.parametrize("field", ["total_collected", "total_outstanding"])
    def test_negative_float_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: -1.0})

    @pytest.mark.parametrize("field", ["total_collected", "total_outstanding"])
    def test_zero_float_accepted(self, field):
        rec = _closure_report(**{field: 0.0})
        assert getattr(rec, field) == 0.0

    def test_empty_closed_at_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at="")

    def test_invalid_closed_at_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _closure_report()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _closure_report()
        d = rec.to_dict()
        expected_keys = {
            "report_id", "account_id", "total_settlements",
            "total_payments", "total_refunds", "total_writeoffs",
            "total_collection_cases", "total_collected",
            "total_outstanding", "closed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys
