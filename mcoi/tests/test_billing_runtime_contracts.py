"""Tests for billing runtime contracts."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _billing_account(**overrides) -> BillingAccount:
    defaults = dict(
        account_id="acct-001",
        tenant_id="t-001",
        counterparty="cp-001",
        status=BillingStatus.ACTIVE,
        currency="USD",
        created_at=TS,
    )
    defaults.update(overrides)
    return BillingAccount(**defaults)


def _invoice(**overrides) -> InvoiceRecord:
    defaults = dict(
        invoice_id="inv-001",
        account_id="acct-001",
        tenant_id="t-001",
        status=InvoiceStatus.DRAFT,
        total_amount=100.0,
        currency="USD",
        issued_at=TS,
        due_at=TS2,
    )
    defaults.update(overrides)
    return InvoiceRecord(**defaults)


def _charge(**overrides) -> ChargeRecord:
    defaults = dict(
        charge_id="ch-001",
        invoice_id="inv-001",
        kind=ChargeKind.SERVICE,
        description="Compute usage",
        amount=50.0,
        scope_ref_id="svc-001",
        scope_ref_type="service",
        created_at=TS,
    )
    defaults.update(overrides)
    return ChargeRecord(**defaults)


def _credit(**overrides) -> CreditRecord:
    defaults = dict(
        credit_id="cr-001",
        account_id="acct-001",
        breach_id="br-001",
        disposition=CreditDisposition.PENDING,
        amount=25.0,
        reason="SLA breach credit",
        applied_at=TS,
    )
    defaults.update(overrides)
    return CreditRecord(**defaults)


def _penalty(**overrides) -> PenaltyRecord:
    defaults = dict(
        penalty_id="pen-001",
        account_id="acct-001",
        breach_id="br-001",
        amount=100.0,
        reason="Late payment",
        assessed_at=TS,
    )
    defaults.update(overrides)
    return PenaltyRecord(**defaults)


def _dispute(**overrides) -> DisputeRecord:
    defaults = dict(
        dispute_id="disp-001",
        invoice_id="inv-001",
        account_id="acct-001",
        status=DisputeStatus.OPEN,
        reason="Incorrect charge",
        amount=50.0,
        opened_at=TS,
        resolved_at="",
    )
    defaults.update(overrides)
    return DisputeRecord(**defaults)


def _revenue_snapshot(**overrides) -> RevenueSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        total_accounts=5,
        total_invoices=10,
        total_charges=20,
        total_credits=3,
        total_penalties=1,
        total_disputes=2,
        total_recognized_revenue=5000.0,
        total_pending_revenue=1000.0,
        total_violations=0,
        captured_at=TS,
    )
    defaults.update(overrides)
    return RevenueSnapshot(**defaults)


def _billing_decision(**overrides) -> BillingDecision:
    defaults = dict(
        decision_id="dec-001",
        account_id="acct-001",
        description="Approve credit",
        decided_by="admin-001",
        decided_at=TS,
    )
    defaults.update(overrides)
    return BillingDecision(**defaults)


def _billing_violation(**overrides) -> BillingViolation:
    defaults = dict(
        violation_id="viol-001",
        account_id="acct-001",
        tenant_id="t-001",
        operation="charge_create",
        reason="Duplicate charge",
        detected_at=TS,
    )
    defaults.update(overrides)
    return BillingViolation(**defaults)


def _billing_closure_report(**overrides) -> BillingClosureReport:
    defaults = dict(
        report_id="rpt-001",
        account_id="acct-001",
        tenant_id="t-001",
        total_invoices=10,
        total_charges=20,
        total_credits=3,
        total_penalties=1,
        total_disputes=2,
        total_revenue=5000.0,
        closed_at=TS,
    )
    defaults.update(overrides)
    return BillingClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestBillingStatus:
    def test_member_count(self):
        assert len(BillingStatus) == 4

    @pytest.mark.parametrize("member", list(BillingStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert BillingStatus.ACTIVE.value == "active"
        assert BillingStatus.SUSPENDED.value == "suspended"
        assert BillingStatus.CLOSED.value == "closed"
        assert BillingStatus.DELINQUENT.value == "delinquent"

    def test_membership(self):
        assert BillingStatus("active") is BillingStatus.ACTIVE

    def test_iteration(self):
        members = list(BillingStatus)
        assert len(members) == 4

    def test_string_representation(self):
        assert "ACTIVE" in repr(BillingStatus.ACTIVE)


class TestInvoiceStatus:
    def test_member_count(self):
        assert len(InvoiceStatus) == 6

    @pytest.mark.parametrize("member", list(InvoiceStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert InvoiceStatus.DRAFT.value == "draft"
        assert InvoiceStatus.ISSUED.value == "issued"
        assert InvoiceStatus.PAID.value == "paid"
        assert InvoiceStatus.OVERDUE.value == "overdue"
        assert InvoiceStatus.DISPUTED.value == "disputed"
        assert InvoiceStatus.VOIDED.value == "voided"

    def test_membership(self):
        assert InvoiceStatus("draft") is InvoiceStatus.DRAFT

    def test_iteration(self):
        members = list(InvoiceStatus)
        assert len(members) == 6

    def test_string_representation(self):
        assert "DRAFT" in repr(InvoiceStatus.DRAFT)


class TestChargeKind:
    def test_member_count(self):
        assert len(ChargeKind) == 6

    @pytest.mark.parametrize("member", list(ChargeKind))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert ChargeKind.SERVICE.value == "service"
        assert ChargeKind.USAGE.value == "usage"
        assert ChargeKind.SUBSCRIPTION.value == "subscription"
        assert ChargeKind.OVERAGE.value == "overage"
        assert ChargeKind.SETUP.value == "setup"
        assert ChargeKind.PROFESSIONAL_SERVICES.value == "professional_services"

    def test_membership(self):
        assert ChargeKind("service") is ChargeKind.SERVICE

    def test_iteration(self):
        members = list(ChargeKind)
        assert len(members) == 6

    def test_string_representation(self):
        assert "SERVICE" in repr(ChargeKind.SERVICE)


class TestCreditDisposition:
    def test_member_count(self):
        assert len(CreditDisposition) == 4

    @pytest.mark.parametrize("member", list(CreditDisposition))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert CreditDisposition.PENDING.value == "pending"
        assert CreditDisposition.APPLIED.value == "applied"
        assert CreditDisposition.EXPIRED.value == "expired"
        assert CreditDisposition.VOIDED.value == "voided"

    def test_membership(self):
        assert CreditDisposition("pending") is CreditDisposition.PENDING

    def test_iteration(self):
        members = list(CreditDisposition)
        assert len(members) == 4

    def test_string_representation(self):
        assert "PENDING" in repr(CreditDisposition.PENDING)


class TestDisputeStatus:
    def test_member_count(self):
        assert len(DisputeStatus) == 5

    @pytest.mark.parametrize("member", list(DisputeStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert DisputeStatus.OPEN.value == "open"
        assert DisputeStatus.UNDER_REVIEW.value == "under_review"
        assert DisputeStatus.RESOLVED_ACCEPTED.value == "resolved_accepted"
        assert DisputeStatus.RESOLVED_REJECTED.value == "resolved_rejected"
        assert DisputeStatus.WITHDRAWN.value == "withdrawn"

    def test_membership(self):
        assert DisputeStatus("open") is DisputeStatus.OPEN

    def test_iteration(self):
        members = list(DisputeStatus)
        assert len(members) == 5

    def test_string_representation(self):
        assert "OPEN" in repr(DisputeStatus.OPEN)


class TestRevenueRecognitionStatus:
    def test_member_count(self):
        assert len(RevenueRecognitionStatus) == 5

    @pytest.mark.parametrize("member", list(RevenueRecognitionStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert RevenueRecognitionStatus.PENDING.value == "pending"
        assert RevenueRecognitionStatus.RECOGNIZED.value == "recognized"
        assert RevenueRecognitionStatus.DEFERRED.value == "deferred"
        assert RevenueRecognitionStatus.DISPUTED.value == "disputed"
        assert RevenueRecognitionStatus.WRITTEN_OFF.value == "written_off"

    def test_membership(self):
        assert RevenueRecognitionStatus("pending") is RevenueRecognitionStatus.PENDING

    def test_iteration(self):
        members = list(RevenueRecognitionStatus)
        assert len(members) == 5

    def test_string_representation(self):
        assert "PENDING" in repr(RevenueRecognitionStatus.PENDING)


# ===================================================================
# BillingAccount tests
# ===================================================================


class TestBillingAccount:
    def test_happy_path(self):
        rec = _billing_account()
        assert rec.account_id == "acct-001"
        assert rec.tenant_id == "t-001"
        assert rec.counterparty == "cp-001"
        assert rec.status is BillingStatus.ACTIVE
        assert rec.currency == "USD"
        assert rec.created_at == TS

    def test_frozen(self):
        rec = _billing_account()
        with pytest.raises(AttributeError):
            rec.account_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(BillingAccount)

    def test_default_status(self):
        rec = _billing_account(status=BillingStatus.ACTIVE)
        assert rec.status is BillingStatus.ACTIVE

    def test_metadata_frozen(self):
        rec = _billing_account(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _billing_account(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _billing_account(metadata={"items": [1, 2, 3]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["account_id", "tenant_id", "counterparty", "currency"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _billing_account(**{field: ""})

    @pytest.mark.parametrize("field", ["account_id", "tenant_id", "counterparty", "currency"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _billing_account(**{field: "   "})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _billing_account(status="active")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            _billing_account(created_at="not-a-date")

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError):
            _billing_account(created_at="")

    def test_to_dict_preserves_enums(self):
        rec = _billing_account()
        d = rec.to_dict()
        assert isinstance(d["status"], BillingStatus)
        assert d["status"] is BillingStatus.ACTIVE

    def test_to_dict_returns_dict(self):
        rec = _billing_account()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _billing_account()
        d = rec.to_dict()
        expected_keys = {
            "account_id", "tenant_id", "counterparty", "status",
            "currency", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(BillingStatus))
    def test_all_statuses_accepted(self, status):
        rec = _billing_account(status=status)
        assert rec.status is status


# ===================================================================
# InvoiceRecord tests
# ===================================================================


class TestInvoiceRecord:
    def test_happy_path(self):
        rec = _invoice()
        assert rec.invoice_id == "inv-001"
        assert rec.account_id == "acct-001"
        assert rec.tenant_id == "t-001"
        assert rec.status is InvoiceStatus.DRAFT
        assert rec.total_amount == 100.0
        assert rec.currency == "USD"
        assert rec.issued_at == TS
        assert rec.due_at == TS2

    def test_frozen(self):
        rec = _invoice()
        with pytest.raises(AttributeError):
            rec.invoice_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(InvoiceRecord)

    def test_metadata_frozen(self):
        rec = _invoice(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _invoice(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _invoice(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["invoice_id", "account_id", "tenant_id", "currency"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _invoice(**{field: ""})

    @pytest.mark.parametrize("field", ["invoice_id", "account_id", "tenant_id", "currency"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _invoice(**{field: "   "})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _invoice(status="draft")

    def test_negative_total_amount_rejected(self):
        with pytest.raises(ValueError):
            _invoice(total_amount=-1.0)

    def test_zero_total_amount_accepted(self):
        rec = _invoice(total_amount=0.0)
        assert rec.total_amount == 0.0

    def test_invalid_issued_at_rejected(self):
        with pytest.raises(ValueError):
            _invoice(issued_at="not-a-date")

    def test_empty_issued_at_rejected(self):
        with pytest.raises(ValueError):
            _invoice(issued_at="")

    def test_invalid_due_at_rejected(self):
        with pytest.raises(ValueError):
            _invoice(due_at="not-a-date")

    def test_empty_due_at_rejected(self):
        with pytest.raises(ValueError):
            _invoice(due_at="")

    def test_to_dict_preserves_enums(self):
        rec = _invoice()
        d = rec.to_dict()
        assert isinstance(d["status"], InvoiceStatus)
        assert d["status"] is InvoiceStatus.DRAFT

    def test_to_dict_returns_dict(self):
        rec = _invoice()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _invoice()
        d = rec.to_dict()
        expected_keys = {
            "invoice_id", "account_id", "tenant_id", "status",
            "total_amount", "currency", "issued_at", "due_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(InvoiceStatus))
    def test_all_statuses_accepted(self, status):
        rec = _invoice(status=status)
        assert rec.status is status


# ===================================================================
# ChargeRecord tests
# ===================================================================


class TestChargeRecord:
    def test_happy_path(self):
        rec = _charge()
        assert rec.charge_id == "ch-001"
        assert rec.invoice_id == "inv-001"
        assert rec.kind is ChargeKind.SERVICE
        assert rec.description == "Compute usage"
        assert rec.amount == 50.0
        assert rec.scope_ref_id == "svc-001"
        assert rec.scope_ref_type == "service"
        assert rec.created_at == TS

    def test_frozen(self):
        rec = _charge()
        with pytest.raises(AttributeError):
            rec.charge_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(ChargeRecord)

    def test_metadata_frozen(self):
        rec = _charge(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _charge(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _charge(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["charge_id", "invoice_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _charge(**{field: ""})

    @pytest.mark.parametrize("field", ["charge_id", "invoice_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _charge(**{field: "   "})

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            _charge(kind="service")

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            _charge(amount=-1.0)

    def test_zero_amount_accepted(self):
        rec = _charge(amount=0.0)
        assert rec.amount == 0.0

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            _charge(created_at="not-a-date")

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError):
            _charge(created_at="")

    def test_to_dict_preserves_enums(self):
        rec = _charge()
        d = rec.to_dict()
        assert isinstance(d["kind"], ChargeKind)
        assert d["kind"] is ChargeKind.SERVICE

    def test_to_dict_returns_dict(self):
        rec = _charge()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _charge()
        d = rec.to_dict()
        expected_keys = {
            "charge_id", "invoice_id", "kind", "description",
            "amount", "scope_ref_id", "scope_ref_type", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("kind", list(ChargeKind))
    def test_all_kinds_accepted(self, kind):
        rec = _charge(kind=kind)
        assert rec.kind is kind

    def test_description_can_be_empty(self):
        rec = _charge(description="")
        assert rec.description == ""

    def test_scope_ref_id_can_be_empty(self):
        rec = _charge(scope_ref_id="")
        assert rec.scope_ref_id == ""


# ===================================================================
# CreditRecord tests
# ===================================================================


class TestCreditRecord:
    def test_happy_path(self):
        rec = _credit()
        assert rec.credit_id == "cr-001"
        assert rec.account_id == "acct-001"
        assert rec.breach_id == "br-001"
        assert rec.disposition is CreditDisposition.PENDING
        assert rec.amount == 25.0
        assert rec.reason == "SLA breach credit"
        assert rec.applied_at == TS

    def test_frozen(self):
        rec = _credit()
        with pytest.raises(AttributeError):
            rec.credit_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(CreditRecord)

    def test_metadata_frozen(self):
        rec = _credit(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _credit(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    @pytest.mark.parametrize("field", ["credit_id", "account_id", "breach_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _credit(**{field: ""})

    @pytest.mark.parametrize("field", ["credit_id", "account_id", "breach_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _credit(**{field: "   "})

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            _credit(disposition="pending")

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            _credit(amount=-1.0)

    def test_zero_amount_accepted(self):
        rec = _credit(amount=0.0)
        assert rec.amount == 0.0

    def test_invalid_applied_at_rejected(self):
        with pytest.raises(ValueError):
            _credit(applied_at="not-a-date")

    def test_empty_applied_at_rejected(self):
        with pytest.raises(ValueError):
            _credit(applied_at="")

    def test_to_dict_preserves_enums(self):
        rec = _credit()
        d = rec.to_dict()
        assert isinstance(d["disposition"], CreditDisposition)
        assert d["disposition"] is CreditDisposition.PENDING

    def test_to_dict_returns_dict(self):
        rec = _credit()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _credit()
        d = rec.to_dict()
        expected_keys = {
            "credit_id", "account_id", "breach_id", "disposition",
            "amount", "reason", "applied_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("disposition", list(CreditDisposition))
    def test_all_dispositions_accepted(self, disposition):
        rec = _credit(disposition=disposition)
        assert rec.disposition is disposition


# ===================================================================
# PenaltyRecord tests
# ===================================================================


class TestPenaltyRecord:
    def test_happy_path(self):
        rec = _penalty()
        assert rec.penalty_id == "pen-001"
        assert rec.account_id == "acct-001"
        assert rec.breach_id == "br-001"
        assert rec.amount == 100.0
        assert rec.reason == "Late payment"
        assert rec.assessed_at == TS

    def test_frozen(self):
        rec = _penalty()
        with pytest.raises(AttributeError):
            rec.penalty_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(PenaltyRecord)

    def test_metadata_frozen(self):
        rec = _penalty(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _penalty(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    @pytest.mark.parametrize("field", ["penalty_id", "account_id", "breach_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _penalty(**{field: ""})

    @pytest.mark.parametrize("field", ["penalty_id", "account_id", "breach_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _penalty(**{field: "   "})

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            _penalty(amount=-1.0)

    def test_zero_amount_accepted(self):
        rec = _penalty(amount=0.0)
        assert rec.amount == 0.0

    def test_invalid_assessed_at_rejected(self):
        with pytest.raises(ValueError):
            _penalty(assessed_at="not-a-date")

    def test_empty_assessed_at_rejected(self):
        with pytest.raises(ValueError):
            _penalty(assessed_at="")

    def test_to_dict_returns_dict(self):
        rec = _penalty()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _penalty()
        d = rec.to_dict()
        expected_keys = {
            "penalty_id", "account_id", "breach_id",
            "amount", "reason", "assessed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_reason_can_be_empty(self):
        rec = _penalty(reason="")
        assert rec.reason == ""


# ===================================================================
# DisputeRecord tests
# ===================================================================


class TestDisputeRecord:
    def test_happy_path(self):
        rec = _dispute()
        assert rec.dispute_id == "disp-001"
        assert rec.invoice_id == "inv-001"
        assert rec.account_id == "acct-001"
        assert rec.status is DisputeStatus.OPEN
        assert rec.reason == "Incorrect charge"
        assert rec.amount == 50.0
        assert rec.opened_at == TS

    def test_frozen(self):
        rec = _dispute()
        with pytest.raises(AttributeError):
            rec.dispute_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(DisputeRecord)

    def test_metadata_frozen(self):
        rec = _dispute(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _dispute(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _dispute(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["dispute_id", "invoice_id", "account_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _dispute(**{field: ""})

    @pytest.mark.parametrize("field", ["dispute_id", "invoice_id", "account_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _dispute(**{field: "   "})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _dispute(status="open")

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            _dispute(amount=-1.0)

    def test_zero_amount_accepted(self):
        rec = _dispute(amount=0.0)
        assert rec.amount == 0.0

    def test_invalid_opened_at_rejected(self):
        with pytest.raises(ValueError):
            _dispute(opened_at="not-a-date")

    def test_empty_opened_at_rejected(self):
        with pytest.raises(ValueError):
            _dispute(opened_at="")

    def test_resolved_at_optional_empty(self):
        rec = _dispute(resolved_at="")
        assert rec.resolved_at == ""

    def test_to_dict_preserves_enums(self):
        rec = _dispute()
        d = rec.to_dict()
        assert isinstance(d["status"], DisputeStatus)
        assert d["status"] is DisputeStatus.OPEN

    def test_to_dict_returns_dict(self):
        rec = _dispute()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _dispute()
        d = rec.to_dict()
        expected_keys = {
            "dispute_id", "invoice_id", "account_id", "status",
            "reason", "amount", "opened_at", "resolved_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(DisputeStatus))
    def test_all_statuses_accepted(self, status):
        rec = _dispute(status=status)
        assert rec.status is status


# ===================================================================
# RevenueSnapshot tests
# ===================================================================


class TestRevenueSnapshot:
    def test_happy_path(self):
        rec = _revenue_snapshot()
        assert rec.snapshot_id == "snap-001"
        assert rec.total_accounts == 5
        assert rec.total_invoices == 10
        assert rec.total_charges == 20
        assert rec.total_credits == 3
        assert rec.total_penalties == 1
        assert rec.total_disputes == 2
        assert rec.total_recognized_revenue == 5000.0
        assert rec.total_pending_revenue == 1000.0
        assert rec.total_violations == 0
        assert rec.captured_at == TS

    def test_frozen(self):
        rec = _revenue_snapshot()
        with pytest.raises(AttributeError):
            rec.snapshot_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(RevenueSnapshot)

    def test_metadata_frozen(self):
        rec = _revenue_snapshot(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _revenue_snapshot(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _revenue_snapshot(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _revenue_snapshot(snapshot_id="   ")

    @pytest.mark.parametrize("field", [
        "total_accounts", "total_invoices", "total_charges",
        "total_credits", "total_penalties", "total_disputes", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _revenue_snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_accounts", "total_invoices", "total_charges",
        "total_credits", "total_penalties", "total_disputes", "total_violations",
    ])
    def test_zero_int_accepted(self, field):
        rec = _revenue_snapshot(**{field: 0})
        assert getattr(rec, field) == 0

    @pytest.mark.parametrize("field", ["total_recognized_revenue", "total_pending_revenue"])
    def test_negative_float_rejected(self, field):
        with pytest.raises(ValueError):
            _revenue_snapshot(**{field: -1.0})

    @pytest.mark.parametrize("field", ["total_recognized_revenue", "total_pending_revenue"])
    def test_zero_float_accepted(self, field):
        rec = _revenue_snapshot(**{field: 0.0})
        assert getattr(rec, field) == 0.0

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError):
            _revenue_snapshot(captured_at="not-a-date")

    def test_empty_captured_at_rejected(self):
        with pytest.raises(ValueError):
            _revenue_snapshot(captured_at="")

    def test_to_dict_returns_dict(self):
        rec = _revenue_snapshot()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _revenue_snapshot()
        d = rec.to_dict()
        expected_keys = {
            "snapshot_id", "total_accounts", "total_invoices", "total_charges",
            "total_credits", "total_penalties", "total_disputes",
            "total_recognized_revenue", "total_pending_revenue",
            "total_violations", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# BillingDecision tests
# ===================================================================


class TestBillingDecision:
    def test_happy_path(self):
        rec = _billing_decision()
        assert rec.decision_id == "dec-001"
        assert rec.account_id == "acct-001"
        assert rec.description == "Approve credit"
        assert rec.decided_by == "admin-001"
        assert rec.decided_at == TS

    def test_frozen(self):
        rec = _billing_decision()
        with pytest.raises(AttributeError):
            rec.decision_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(BillingDecision)

    def test_metadata_frozen(self):
        rec = _billing_decision(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _billing_decision(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _billing_decision(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["decision_id", "account_id", "decided_by"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _billing_decision(**{field: ""})

    @pytest.mark.parametrize("field", ["decision_id", "account_id", "decided_by"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _billing_decision(**{field: "   "})

    def test_invalid_decided_at_rejected(self):
        with pytest.raises(ValueError):
            _billing_decision(decided_at="not-a-date")

    def test_empty_decided_at_rejected(self):
        with pytest.raises(ValueError):
            _billing_decision(decided_at="")

    def test_description_can_be_empty(self):
        rec = _billing_decision(description="")
        assert rec.description == ""

    def test_to_dict_returns_dict(self):
        rec = _billing_decision()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _billing_decision()
        d = rec.to_dict()
        expected_keys = {
            "decision_id", "account_id", "description",
            "decided_by", "decided_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# BillingViolation tests
# ===================================================================


class TestBillingViolation:
    def test_happy_path(self):
        rec = _billing_violation()
        assert rec.violation_id == "viol-001"
        assert rec.account_id == "acct-001"
        assert rec.tenant_id == "t-001"
        assert rec.operation == "charge_create"
        assert rec.reason == "Duplicate charge"
        assert rec.detected_at == TS

    def test_frozen(self):
        rec = _billing_violation()
        with pytest.raises(AttributeError):
            rec.violation_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(BillingViolation)

    def test_metadata_frozen(self):
        rec = _billing_violation(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _billing_violation(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _billing_violation(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["violation_id", "account_id", "tenant_id", "operation"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _billing_violation(**{field: ""})

    @pytest.mark.parametrize("field", ["violation_id", "account_id", "tenant_id", "operation"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _billing_violation(**{field: "   "})

    def test_invalid_detected_at_rejected(self):
        with pytest.raises(ValueError):
            _billing_violation(detected_at="not-a-date")

    def test_empty_detected_at_rejected(self):
        with pytest.raises(ValueError):
            _billing_violation(detected_at="")

    def test_reason_can_be_empty(self):
        rec = _billing_violation(reason="")
        assert rec.reason == ""

    def test_to_dict_returns_dict(self):
        rec = _billing_violation()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _billing_violation()
        d = rec.to_dict()
        expected_keys = {
            "violation_id", "account_id", "tenant_id",
            "operation", "reason", "detected_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# BillingClosureReport tests
# ===================================================================


class TestBillingClosureReport:
    def test_happy_path(self):
        rec = _billing_closure_report()
        assert rec.report_id == "rpt-001"
        assert rec.account_id == "acct-001"
        assert rec.tenant_id == "t-001"
        assert rec.total_invoices == 10
        assert rec.total_charges == 20
        assert rec.total_credits == 3
        assert rec.total_penalties == 1
        assert rec.total_disputes == 2
        assert rec.total_revenue == 5000.0
        assert rec.closed_at == TS

    def test_frozen(self):
        rec = _billing_closure_report()
        with pytest.raises(AttributeError):
            rec.report_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(BillingClosureReport)

    def test_metadata_frozen(self):
        rec = _billing_closure_report(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _billing_closure_report(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _billing_closure_report(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["report_id", "account_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _billing_closure_report(**{field: ""})

    @pytest.mark.parametrize("field", ["report_id", "account_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _billing_closure_report(**{field: "   "})

    @pytest.mark.parametrize("field", [
        "total_invoices", "total_charges", "total_credits",
        "total_penalties", "total_disputes",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _billing_closure_report(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_invoices", "total_charges", "total_credits",
        "total_penalties", "total_disputes",
    ])
    def test_zero_int_accepted(self, field):
        rec = _billing_closure_report(**{field: 0})
        assert getattr(rec, field) == 0

    def test_negative_total_revenue_rejected(self):
        with pytest.raises(ValueError):
            _billing_closure_report(total_revenue=-1.0)

    def test_zero_total_revenue_accepted(self):
        rec = _billing_closure_report(total_revenue=0.0)
        assert rec.total_revenue == 0.0

    def test_invalid_closed_at_rejected(self):
        with pytest.raises(ValueError):
            _billing_closure_report(closed_at="not-a-date")

    def test_empty_closed_at_rejected(self):
        with pytest.raises(ValueError):
            _billing_closure_report(closed_at="")

    def test_to_dict_returns_dict(self):
        rec = _billing_closure_report()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _billing_closure_report()
        d = rec.to_dict()
        expected_keys = {
            "report_id", "account_id", "tenant_id",
            "total_invoices", "total_charges", "total_credits",
            "total_penalties", "total_disputes", "total_revenue",
            "closed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# Cross-cutting datetime acceptance tests
# ===================================================================


class TestDatetimeAcceptance:
    """ISO datetime strings with timezone are accepted by all datetime fields."""

    def test_billing_account_accepts_iso_datetime(self):
        rec = _billing_account(created_at="2025-06-01T00:00:00Z")
        assert rec.created_at == "2025-06-01T00:00:00Z"

    def test_invoice_accepts_iso_datetime(self):
        rec = _invoice(issued_at="2025-06-01T00:00:00Z", due_at="2025-06-15T00:00:00Z")
        assert rec.issued_at == "2025-06-01T00:00:00Z"

    def test_charge_accepts_iso_datetime(self):
        rec = _charge(created_at="2025-06-01T00:00:00Z")
        assert rec.created_at == "2025-06-01T00:00:00Z"

    def test_credit_accepts_iso_datetime(self):
        rec = _credit(applied_at="2025-06-01T00:00:00Z")
        assert rec.applied_at == "2025-06-01T00:00:00Z"

    def test_penalty_accepts_iso_datetime(self):
        rec = _penalty(assessed_at="2025-06-01T00:00:00Z")
        assert rec.assessed_at == "2025-06-01T00:00:00Z"

    def test_dispute_accepts_iso_datetime(self):
        rec = _dispute(opened_at="2025-06-01T00:00:00Z")
        assert rec.opened_at == "2025-06-01T00:00:00Z"

    def test_revenue_snapshot_accepts_iso_datetime(self):
        rec = _revenue_snapshot(captured_at="2025-06-01T00:00:00Z")
        assert rec.captured_at == "2025-06-01T00:00:00Z"

    def test_billing_decision_accepts_iso_datetime(self):
        rec = _billing_decision(decided_at="2025-06-01T00:00:00Z")
        assert rec.decided_at == "2025-06-01T00:00:00Z"

    def test_billing_violation_accepts_iso_datetime(self):
        rec = _billing_violation(detected_at="2025-06-01T00:00:00Z")
        assert rec.detected_at == "2025-06-01T00:00:00Z"

    def test_billing_closure_report_accepts_iso_datetime(self):
        rec = _billing_closure_report(closed_at="2025-06-01T00:00:00Z")
        assert rec.closed_at == "2025-06-01T00:00:00Z"

    def test_date_only_string_accepted(self):
        """Python 3.11+ accepts date-only strings via datetime.fromisoformat()."""
        rec = _billing_account(created_at="2025-06-01")
        assert rec.created_at == "2025-06-01"
